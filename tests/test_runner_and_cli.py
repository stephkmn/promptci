"""End-to-end: runner with FakeProvider, then the CLI against the committed demo cache."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from promptci.cache.disk import CachedProvider, DiskCache, _canonical_params
from promptci.cli import (
    DEFAULT_CACHE_LOCAL,
    DEFAULT_CACHE_REPLAY,
    _default_cache_dir,
    app,
)
from promptci.graders import make_grader
from promptci.providers.base import ProviderError
from promptci.providers.fake import FakeProvider
from promptci.runner.run import Runner, RunnerConfig
from promptci.store.sqlite import ResultStore
from promptci.suite.schema import render_prompt
from tests.conftest import EXAMPLES, REPO


@pytest.mark.asyncio
async def test_runner_end_to_end_with_fake(tmp_path, json_extract_suite):
    # Only the inline cases have recorded demo replies, so run that subset. This is the
    # `--limit 12` the CLI demo uses, expressed against the loaded suite.
    full = json_extract_suite
    demo_cases = [c for c in full.cases if c.id in full.fake_responses]
    suite = full.model_copy(update={"cases": demo_cases})
    replies = {render_prompt(suite, c): suite.fake_responses[c.id] for c in suite.cases}
    provider = CachedProvider(FakeProvider(responses=replies), DiskCache(tmp_path / "cache"))
    store = ResultStore(tmp_path / "r.db")
    runner = Runner(provider, "demo", make_grader(suite.grader), store, RunnerConfig(concurrency=3))
    seen = []
    run = await runner.run(suite, model_string="fake/demo", on_result=seen.append)
    assert len(seen) == len(suite.cases)
    s = store.summarize(run.run_id)
    assert s.n_cases == 12 and s.n_errors == 0
    assert s.pass_rate == pytest.approx(9 / 12)
    assert s.mean_score > s.pass_rate  # partial credit on the 3 wrong ones
    assert s.total_cost_usd == 0.0
    assert run.finished_at is not None and run.n_cases == 12
    # second run is served entirely from cache
    run2 = await runner.run(suite, model_string="fake/demo")
    assert store.summarize(run2.run_id).cache_hit_rate == 1.0


class _Flaky:
    name = "flaky"

    def __init__(self, fail_times: int):
        self.remaining = fail_times
        self.calls = 0

    async def complete(self, prompt, model, **params):
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise ProviderError("transient")
        return await FakeProvider(responses={prompt: "ok"}).complete(prompt, model, **params)


@pytest.mark.asyncio
async def test_runner_retries_then_records_error(tmp_path):
    from promptci.suite.schema import Case, Suite

    suite = Suite(
        name="s",
        prompt="{{ inputs.q }}",
        grader={"type": "exact"},
        cases=[Case(id="a", inputs={"q": "x"}, expected="ok")],
    )
    store = ResultStore(tmp_path / "r.db")
    cfg = RunnerConfig(max_retries=2, backoff_base_s=0.0)
    ok_provider = _Flaky(fail_times=2)
    run = await Runner(ok_provider, "m", make_grader(suite.grader), store, cfg).run(
        suite, model_string="flaky/m"
    )
    assert ok_provider.calls == 3
    assert store.summarize(run.run_id).pass_rate == 1.0

    bad_provider = _Flaky(fail_times=10)
    run = await Runner(bad_provider, "m", make_grader(suite.grader), store, cfg).run(
        suite, model_string="flaky/m"
    )
    assert bad_provider.calls == 3
    res = store.get_results(run.run_id)
    assert res[0].error and "transient" in res[0].error
    assert store.summarize(run.run_id).n_errors == 1


def test_runner_config_rejects_bad_max_retries_and_concurrency():
    """Bad values fail at construction, not confusingly mid-run.

    A negative max_retries would skip the retry loop and trip the assert after it; a
    concurrency below 1 would build a semaphore no case can acquire and hang forever.
    """
    with pytest.raises(ValueError, match="max_retries must be >= 0"):
        RunnerConfig(max_retries=-1)
    assert RunnerConfig(max_retries=0).max_retries == 0  # zero means "try once"
    for bad in (0, -1):
        with pytest.raises(ValueError, match="concurrency must be >= 1"):
            RunnerConfig(concurrency=bad)
    assert RunnerConfig(concurrency=1).concurrency == 1


def test_cli_rejects_zero_concurrency(tmp_path):
    """`--concurrency 0` is a usage error, not a hung run."""
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(EXAMPLES / "json_extract" / "suite.yaml"),
            "--model",
            "replay/any",
            "--concurrency",
            "0",
            "--db",
            str(tmp_path / "x.db"),
        ],
    )
    assert result.exit_code == 2
    assert "concurrency" in result.output


def test_cli_demo_replays_from_committed_cache(tmp_path):
    """`promptci run examples/json_extract/suite.yaml --model replay/any --limit 12`.

    `--limit 12` selects the inline cases, the only ones `cache/ci/` recorded. A
    full-suite replay misses on the 60 in cases.jsonl.
    """
    runner = CliRunner()
    db = tmp_path / "demo.db"
    result = runner.invoke(
        app,
        [
            "run",
            str(EXAMPLES / "json_extract" / "suite.yaml"),
            "--model",
            "replay/any",
            "--cache-dir",
            str(REPO / "cache" / "ci"),
            "--db",
            str(db),
            "--limit",
            "12",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"n_errors": 0' in result.output
    assert '"n_cases": 12' in result.output

    with ResultStore(db) as store:
        run_id = store.list_runs()[0].run_id
    summ = runner.invoke(app, ["summarize", run_id, "--db", str(db), "--md"])
    assert summ.exit_code == 0, summ.output
    assert "Pass rate | 75.0%" in summ.output
    assert "c005" in summ.output  # lowest-scoring cases table names the wrong ones

    cmp = runner.invoke(app, ["compare", run_id, run_id, "--db", str(db), "--resamples", "500"])
    assert cmp.exit_code == 0, cmp.output
    assert "no detectable change" in cmp.output


@pytest.mark.parametrize(
    ("model_string", "expected"),
    [
        ("replay/any", DEFAULT_CACHE_REPLAY),
        ("replay/ollama/qwen2.5:7b", DEFAULT_CACHE_REPLAY),
        ("ollama/qwen2.5:7b", DEFAULT_CACHE_LOCAL),
        ("fake/demo", DEFAULT_CACHE_LOCAL),
        ("anthropic/claude-3-5-haiku-latest", DEFAULT_CACHE_LOCAL),
    ],
)
def test_default_cache_dir_keeps_real_models_out_of_the_fixture(model_string, expected):
    """`replay/` defaults to the committed fixture; anything else to the gitignored dir.

    Two properties at once: the zero-setup demo works in a fresh clone with no flags
    (which needs `cache/ci`, since `cache/local` is gitignored and absent there), and a
    real model run cannot land in the fixture. Both matter because `replay/any` raises
    on a prompt recorded by two models, which breaks the demo.
    """
    assert _default_cache_dir(model_string) == Path(expected)


def test_committed_cache_has_one_provider_per_prompt():
    """`replay/any` needs each (params, prompt) in `cache/ci` recorded by exactly one model.

    Guards the ambiguity directly rather than through the demo: a second provider's
    entry for a prompt already in the fixture makes `replay/any` raise on that case.
    """
    by_request: dict[tuple[str, str], list[str]] = {}
    for entry_path in (REPO / "cache" / "ci").glob("*/*.json"):
        req = json.loads(entry_path.read_text(encoding="utf-8"))["request"]
        key = (_canonical_params(req.get("params", {})), req["prompt"])
        by_request.setdefault(key, []).append(f"{req['provider']}/{req['model']}")

    assert by_request, "committed cache is empty"
    ambiguous = {
        prompt[:60]: sorted(models) for (_, prompt), models in by_request.items() if len(models) > 1
    }
    assert not ambiguous, f"prompts recorded by more than one model: {ambiguous}"


def test_run_records_a_clean_sha_when_the_db_lives_in_the_repo(tmp_path, monkeypatch):
    """The run's own SQLite file must not make the run look like it came from a dirty tree.

    `git_sha` shells out to `git status --porcelain`, so it reports whatever is on disk
    when it is called. `ResultStore` creates the database, and `--db` defaults to a path
    inside the repo, so reading the sha after building the store recorded `<sha>-dirty`
    on every row of an otherwise clean checkout. Provenance has to describe the code that
    produced the run, not the artifact the run just wrote.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not installed")

    repo = tmp_path / "repo"
    (repo / "examples" / "json_extract").mkdir(parents=True)
    shutil.copy(EXAMPLES / "json_extract" / "suite.yaml", repo / "examples" / "json_extract")
    # The suite declares `dataset: cases.jsonl`, so the fixture needs it to load at all.
    shutil.copy(EXAMPLES / "json_extract" / "cases.jsonl", repo / "examples" / "json_extract")
    shutil.copytree(REPO / "cache" / "ci", repo / "cache" / "ci")

    def run_git(*args: str) -> None:
        subprocess.run([git, *args], cwd=repo, check=True, capture_output=True)

    run_git("init", "-q")
    run_git("config", "user.email", "t@example.invalid")
    run_git("config", "user.name", "t")
    run_git("add", "-A")
    run_git("commit", "-qm", "fixture")
    head = subprocess.run(
        [git, "rev-parse", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    # `git_sha` reads the process working directory, so the CLI has to run from the repo.
    monkeypatch.chdir(repo)
    db = repo / "results" / "promptci.db"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "examples/json_extract/suite.yaml",
            "--model",
            "replay/any",
            "--cache-dir",
            "cache/ci",
            "--db",
            str(db),
            "--limit",
            "12",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert db.exists(), "the run should have created the database inside the repo"

    with ResultStore(db) as store:
        assert store.list_runs()[0].git_sha == head


def test_cli_replay_miss_exits_nonzero(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            str(EXAMPLES / "json_extract" / "suite.yaml"),
            "--model",
            "replay/any",
            "--cache-dir",
            str(tmp_path / "empty"),
            "--db",
            str(tmp_path / "x.db"),
            "--quiet",
        ],
    )
    assert result.exit_code == 2
    assert "errored" in result.output or "CacheMissError" in result.output


def test_cli_validate(tmp_path):
    runner = CliRunner()
    r = runner.invoke(app, ["validate", str(EXAMPLES / "json_extract" / "suite.yaml")])
    assert r.exit_code == 0 and "72 cases" in r.output


def test_console_script_is_installed():
    exe = shutil.which("promptci")
    if exe is None:
        pytest.skip("promptci not on PATH (not installed with pip -e)")
    out = subprocess.run(
        [exe, "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert out.returncode == 0 and "promptci" in out.stdout


def test_module_entrypoint():
    out = subprocess.run(
        [sys.executable, "-m", "promptci.cli", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert out.returncode == 0 and "promptci" in out.stdout
