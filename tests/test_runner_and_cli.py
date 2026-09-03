"""End-to-end: runner with FakeProvider, then the CLI against the committed demo cache."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from promptci.cache.disk import CachedProvider, DiskCache
from promptci.cli import app
from promptci.graders import make_grader
from promptci.providers.base import ProviderError
from promptci.providers.fake import FakeProvider
from promptci.runner.run import Runner, RunnerConfig
from promptci.store.sqlite import ResultStore
from promptci.suite.schema import render_prompt
from tests.conftest import EXAMPLES, REPO


@pytest.mark.asyncio
async def test_runner_end_to_end_with_fake(tmp_path, json_extract_suite):
    suite = json_extract_suite
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


def test_cli_demo_replays_from_committed_cache(tmp_path):
    """`promptci run examples/json_extract/suite.yaml --model replay/any` from cache/ci."""
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
    assert r.exit_code == 0 and "12 cases" in r.output


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
