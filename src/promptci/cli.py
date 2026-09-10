"""PromptCI command line.

    promptci run SUITE --model ollama/qwen2.5:7b     run a suite, print a summary
    promptci summarize RUN_ID                        summary table for a past run
    promptci runs                                    list recent runs
    promptci compare RUN_A RUN_B                     paired comparison with CI
    promptci validate SUITE                          check a suite file loads
    promptci cache stats                             what the completion cache holds

Every completion goes through the disk cache. Which directory depends on the provider
unless ``--cache-dir`` says otherwise: ``replay/...`` reads ``cache/ci``, the committed
fixture that lets CI and the zero-setup demo replay a run for free, while anything that
can reach a real model writes to ``cache/local``, which is gitignored.

That split exists because ``replay/any`` resolves a prompt by finding the single entry
that recorded it. A real model's response sitting next to the fixture's makes that
lookup ambiguous and breaks the demo, so the two never share a directory.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from promptci import __version__
from promptci.cache.disk import CachedProvider, DiskCache, read_cache_stats
from promptci.graders import make_grader
from promptci.providers import make_provider
from promptci.providers.base import ProviderError, parse_model_string
from promptci.providers.fake import FakeProvider
from promptci.providers.replay import ReplayProvider
from promptci.report.markdown import comparison_markdown, run_summary_markdown
from promptci.runner.run import Runner, RunnerConfig
from promptci.stats.compare import compare_scores
from promptci.store.sqlite import ResultStore, git_sha
from promptci.suite.schema import Suite, load_suite, render_prompt

app = typer.Typer(
    name="promptci",
    help="Regression testing for LLM applications.",
    no_args_is_help=True,
    add_completion=False,
)
cache_app = typer.Typer(
    help="Inspect the completion cache.",
    no_args_is_help=True,
)
app.add_typer(cache_app, name="cache")
console = Console()
err_console = Console(stderr=True)

# Two cache defaults, chosen by provider in `_default_cache_dir`. `replay/` reads the
# committed fixture; anything that can call a model writes to the gitignored directory
# so real responses never land in `cache/ci`.
DEFAULT_CACHE_REPLAY = "cache/ci"
DEFAULT_CACHE_LOCAL = "cache/local"
DEFAULT_DB = "results/promptci.db"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"promptci {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    """Regression testing for LLM applications."""


def _fail(msg: str, code: int = 1) -> None:
    err_console.print(f"[red]error:[/red] {msg}")
    raise typer.Exit(code)


def _format_bytes(n: int) -> str:
    """Size for a human reading a table. Powers of 1024, since that is what `du` reports.

    The JSON output keeps raw bytes; only the table is rounded.
    """
    if n < 1024:
        return f"{n} B"
    size = n / 1024
    for unit in ("KB", "MB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _default_cache_dir(model_string: str) -> Path:
    """Cache directory to use when `--cache-dir` was not given.

    `replay/...` serves from the committed fixture, so the zero-setup demo works in a
    fresh clone with no flags. Every other provider can reach a real model, and its
    responses must not join the fixture: a prompt recorded by two models makes
    `replay/any` ambiguous and breaks the demo.
    """
    if model_string.startswith("replay/"):
        return Path(DEFAULT_CACHE_REPLAY)
    return Path(DEFAULT_CACHE_LOCAL)


def _build_provider(model_string: str, suite: Suite, cache_dir: Path, *, write_cache: bool):
    """Provider for a model string, wrapped in the cache unless it is a replay."""
    try:
        raw, model = make_provider(model_string, cache_dir)
    except (ValueError, ProviderError) as e:
        _fail(str(e))
    if isinstance(raw, ReplayProvider):
        return raw, model
    if isinstance(raw, FakeProvider) and suite.fake_responses:
        # The suite maps case_id -> reply. FakeProvider only sees prompts, so render
        # each case's prompt here to build the lookup.
        by_prompt = {}
        for case in suite.cases:
            if case.id in suite.fake_responses:
                by_prompt[render_prompt(suite, case)] = suite.fake_responses[case.id]
        raw = FakeProvider(responses=by_prompt)
    return CachedProvider(raw, DiskCache(cache_dir), write=write_cache), model


@app.command()
def run(
    suite_path: Annotated[Path, typer.Argument(help="Path to a suite YAML file.")],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="provider/model, e.g. ollama/qwen2.5:7b, replay/any, fake/demo.",
        ),
    ],
    cache_dir: Annotated[
        Path | None,
        typer.Option(
            help="Completion cache directory. Default: cache/ci for replay/ models, "
            "the gitignored cache/local for everything else."
        ),
    ] = None,
    db: Annotated[Path, typer.Option(help="SQLite results database.")] = Path(DEFAULT_DB),
    limit: Annotated[
        int | None, typer.Option(help="Only run the first N cases (smoke test).")
    ] = None,
    concurrency: Annotated[int, typer.Option(min=1, help="Parallel requests.")] = 4,
    label: Annotated[
        str | None, typer.Option(help="Free-text label stored with the run, e.g. 'cot-prompt'.")
    ] = None,
    no_cache_write: Annotated[
        bool, typer.Option("--no-cache-write", help="Read the cache but do not add to it.")
    ] = False,
    json_out: Annotated[
        bool, typer.Option("--json", help="Print the summary as JSON instead of a table.")
    ] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="No progress bar.")] = False,
) -> None:
    """Run a suite against a model and store every result."""
    try:
        suite = load_suite(suite_path, limit=limit)
    except (OSError, ValueError) as e:
        _fail(f"could not load suite: {e}")
    try:
        parse_model_string(model)
    except ValueError as e:
        _fail(str(e))

    # Captured before anything below touches the working tree. `ResultStore` creates the
    # SQLite file, and a default `--db` puts it inside the repo, so computing the sha
    # afterwards makes the run's own artifact show up in `git status` and every row gets
    # recorded as `-dirty`. Read once, here, and pass the same value down both branches.
    sha = git_sha()

    if cache_dir is None:
        cache_dir = _default_cache_dir(model)
    provider, model_name = _build_provider(model, suite, cache_dir, write_cache=not no_cache_write)
    try:
        grader = make_grader(suite.grader)
    except (ValueError, KeyError) as e:
        _fail(f"bad grader spec: {e}")

    store = ResultStore(db)
    runner = Runner(provider, model_name, grader, store, RunnerConfig(concurrency=concurrency))

    async def _go():
        if quiet or json_out:
            return await runner.run(
                suite, model_string=model, suite_path=str(suite_path), label=label, sha=sha
            )
        with Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"{suite.name} on {model}", total=len(suite.cases))
            return await runner.run(
                suite,
                model_string=model,
                suite_path=str(suite_path),
                label=label,
                sha=sha,
                on_result=lambda _rec: progress.advance(task),
            )

    run_rec = asyncio.run(_go())
    summary = store.summarize(run_rec.run_id)
    results = store.get_results(run_rec.run_id)

    if json_out:
        # plain stdout, not rich, so `promptci run ... --json | jq` works in CI
        sys.stdout.write(json.dumps(summary.as_dict(), indent=2) + "\n")
    else:
        _print_summary_table(summary)
        errors = [r for r in results if r.error]
        if errors:
            err_console.print(f"[yellow]{len(errors)} case(s) errored. First:[/yellow]")
            for r in errors[:3]:
                err_console.print(f"  {r.case_id}: {r.error}")
        console.print(
            f"\nrun_id: [bold]{run_rec.run_id}[/bold]   (promptci summarize {run_rec.run_id})"
        )
    store.close()
    if summary.n_errors == summary.n_cases and summary.n_cases > 0:
        raise typer.Exit(2)


def _print_summary_table(s) -> None:
    t = Table(title=f"{s.suite_name} on {s.model}", show_header=True)
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("Cases", str(s.n_cases))
    t.add_row("Errors", str(s.n_errors))
    t.add_row("Mean score", f"{s.mean_score:.3f}")
    t.add_row("Pass rate", "n/a" if s.pass_rate is None else f"{100 * s.pass_rate:.1f}%")
    t.add_row("Mean latency", f"{s.mean_latency_ms:.0f} ms")
    t.add_row("p95 latency", f"{s.p95_latency_ms:.0f} ms")
    t.add_row("Tokens (prompt / completion)", f"{s.prompt_tokens} / {s.completion_tokens}")
    t.add_row("Total cost", f"${s.total_cost_usd:.4f}")
    t.add_row("Cache hit rate", f"{100 * s.cache_hit_rate:.0f}%")
    console.print(t)


@app.command()
def summarize(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    db: Annotated[Path, typer.Option()] = Path(DEFAULT_DB),
    markdown: Annotated[
        bool, typer.Option("--markdown", "--md", help="Print Markdown instead of a table.")
    ] = False,
    worst: Annotated[int, typer.Option(help="How many lowest-scoring cases to list.")] = 5,
) -> None:
    """Print the summary for a stored run."""
    store = ResultStore(db)
    try:
        run_rec = store.get_run(run_id)
    except KeyError as e:
        _fail(str(e))
    summary = store.summarize(run_rec.run_id)
    results = store.get_results(run_rec.run_id)
    if markdown:
        sys.stdout.write(run_summary_markdown(run_rec, summary, results, worst=worst))
    else:
        _print_summary_table(summary)
        console.print(
            f"suite hash {run_rec.suite_hash}, git {run_rec.git_sha or 'unknown'}, "
            f"label {run_rec.label or '-'}, started {run_rec.started_at}"
        )
    store.close()


@app.command()
def runs(
    db: Annotated[Path, typer.Option()] = Path(DEFAULT_DB),
    suite: Annotated[str | None, typer.Option(help="Filter by suite name.")] = None,
    limit: Annotated[int, typer.Option()] = 20,
) -> None:
    """List recent runs."""
    store = ResultStore(db)
    t = Table(show_header=True)
    for col in ("run_id", "suite", "model", "label", "cases", "mean", "pass", "started"):
        t.add_column(col)
    for r in store.list_runs(suite, limit):
        s = store.summarize(r.run_id)
        t.add_row(
            r.run_id,
            r.suite_name,
            r.model,
            r.label or "",
            str(s.n_cases),
            f"{s.mean_score:.3f}",
            "n/a" if s.pass_rate is None else f"{100 * s.pass_rate:.0f}%",
            r.started_at,
        )
    console.print(t)
    store.close()


@app.command()
def compare(
    run_a: Annotated[str, typer.Argument(help="Baseline run id.")],
    run_b: Annotated[str, typer.Argument(help="Candidate run id.")],
    db: Annotated[Path, typer.Option()] = Path(DEFAULT_DB),
    threshold: Annotated[
        float | None,
        typer.Option(help="Regression threshold on mean score. Default: the suite's value."),
    ] = None,
    resamples: Annotated[int, typer.Option()] = 10_000,
    seed: Annotated[int, typer.Option()] = 0,
    markdown: Annotated[bool, typer.Option("--markdown", "--md")] = False,
    fail_on_regression: Annotated[
        bool, typer.Option("--fail-on-regression", help="Exit 3 if B regressed vs A.")
    ] = False,
) -> None:
    """Paired comparison of two runs: mean delta, bootstrap CI, permutation p-value.

    McNemar, the power helper, and the HTML report are added in milestone M2.
    """
    store = ResultStore(db)
    try:
        ra, rb = store.get_run(run_a), store.get_run(run_b)
    except KeyError as e:
        _fail(str(e))
    if ra.suite_hash != rb.suite_hash:
        err_console.print(
            "[yellow]warning:[/yellow] suite hashes differ; comparing only shared case ids. "
            "If you changed the prompt on purpose that is expected."
        )
    thr = threshold
    if thr is None:
        thr = 0.02
        if ra.suite_path and Path(ra.suite_path).exists():
            try:
                thr = load_suite(ra.suite_path).compare.regression_threshold
            except (OSError, ValueError):
                pass

    def _scores(run_id: str) -> dict[str, float]:
        return {
            r.case_id: (r.score if r.score is not None else 0.0) for r in store.get_results(run_id)
        }

    try:
        cmp = compare_scores(
            _scores(ra.run_id),
            _scores(rb.run_id),
            threshold=thr,
            resamples=resamples,
            seed=seed,
            run_a=ra.run_id,
            run_b=rb.run_id,
        )
    except ValueError as e:
        _fail(str(e))
    store.close()
    sys.stdout.write(comparison_markdown(cmp))
    if fail_on_regression and cmp.is_regression:
        raise typer.Exit(3)


@app.command()
def validate(
    suite_path: Annotated[Path, typer.Argument()],
    show: Annotated[int, typer.Option(help="Render the first N prompts.")] = 1,
) -> None:
    """Load a suite, build its grader, and render a prompt. Catches YAML mistakes early."""
    try:
        suite = load_suite(suite_path)
        make_grader(suite.grader)
        for case in suite.cases[:show]:
            console.rule(f"case {case.id}")
            console.print(render_prompt(suite, case))
    except (OSError, ValueError, KeyError) as e:
        _fail(str(e))
    console.print(
        f"[green]ok[/green] {suite.name}: {len(suite.cases)} cases, grader {suite.grader.type}, "
        f"hash {suite.content_hash()}"
    )


@cache_app.command("stats")
def cache_stats(
    cache_dir: Annotated[
        Path,
        typer.Option(
            help="Cache directory to inspect. Default: the gitignored cache/local, where "
            "real model runs are recorded. Pass cache/ci for the committed replay fixture."
        ),
    ] = Path(DEFAULT_CACHE_LOCAL),
    json_out: Annotated[
        bool, typer.Option("--json", help="Print raw byte counts as JSON instead of a table.")
    ] = False,
) -> None:
    """Show how many completions a cache holds, its size, and which models recorded them.

    Unlike `run`, there is no model string here to pick a default directory from, so
    this defaults to `cache/local`: the fixture in `cache/ci` is small, committed, and
    already visible in git, while what accumulates unseen is the local one.
    """
    if not cache_dir.is_dir():
        _fail(
            f"no cache directory at {cache_dir}. Nothing has been cached there yet, or the "
            f"path is wrong; the committed fixture is {DEFAULT_CACHE_REPLAY}."
        )
    stats = read_cache_stats(cache_dir)

    if json_out:
        # plain stdout, not rich, so `promptci cache stats --json | jq` works
        sys.stdout.write(json.dumps(stats.as_dict(), indent=2) + "\n")
        return

    t = Table(title=f"cache {cache_dir}", show_header=True)
    t.add_column("Provider")
    t.add_column("Model")
    t.add_column("Entries", justify="right")
    t.add_column("Size", justify="right")
    for g in stats.groups:
        t.add_row(g.provider, g.model, str(g.entries), _format_bytes(g.total_bytes))
    t.add_section()
    t.add_row("TOTAL", "", str(stats.entries), _format_bytes(stats.total_bytes))
    console.print(t)
    if stats.entries == 0:
        console.print("cache is empty")
    if stats.unreadable:
        err_console.print(
            f"[yellow]{stats.unreadable} entr(y/ies) could not be read[/yellow] and are listed "
            "as '?'. Each one is a cache miss the next time it is requested, then overwritten."
        )


if __name__ == "__main__":  # pragma: no cover
    app()
