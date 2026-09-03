"""Markdown report rendering. Plain string building, no template engine, so the
output is easy to paste into a PR comment or a README."""

from __future__ import annotations

from promptci.stats.compare import ComparisonResult
from promptci.store.sqlite import ResultRecord, RunRecord, RunSummary


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def run_summary_markdown(
    run: RunRecord,
    summary: RunSummary,
    results: list[ResultRecord] | None = None,
    *,
    worst: int = 5,
) -> str:
    lines = [
        f"## Run `{run.run_id}`: {run.suite_name} on `{run.model}`",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cases | {summary.n_cases} |",
        f"| Errors | {summary.n_errors} |",
        f"| Mean score | {summary.mean_score:.3f} |",
        f"| Pass rate | {_fmt_pct(summary.pass_rate)} |",
        f"| Mean latency | {summary.mean_latency_ms:.0f} ms |",
        f"| p95 latency | {summary.p95_latency_ms:.0f} ms |",
        f"| Prompt tokens | {summary.prompt_tokens} |",
        f"| Completion tokens | {summary.completion_tokens} |",
        f"| Total cost | ${summary.total_cost_usd:.4f} |",
        f"| Cache hit rate | {_fmt_pct(summary.cache_hit_rate)} |",
        "",
        f"Suite hash `{run.suite_hash}`, git `{run.git_sha or 'unknown'}`, "
        f"started {run.started_at}, finished {run.finished_at or 'in progress'}.",
    ]
    if results:
        failing = [r for r in results if r.error is not None or (r.score or 0.0) < 1.0]
        failing.sort(key=lambda r: r.score if r.score is not None else -1.0)
        if failing:
            lines += ["", f"### Lowest-scoring cases (up to {worst})", ""]
            lines += ["| Case | Score | Output (truncated) | Note |", "|---|---|---|---|"]
            for r in failing[:worst]:
                out = (r.output or "").replace("\n", " ").replace("|", "\\|")[:80]
                note = r.error or _short_details(r)
                score = "err" if r.score is None else f"{r.score:.2f}"
                lines.append(f"| {r.case_id} | {score} | {out} | {note} |")
    return "\n".join(lines) + "\n"


def _short_details(r: ResultRecord) -> str:
    d = r.grader_details
    if "wrong" in d and d["wrong"]:
        return "wrong: " + ", ".join(sorted(d["wrong"]))
    if "schema_errors" in d:
        return "schema: " + "; ".join(d["schema_errors"][:2])
    if "error" in d:
        return str(d["error"])
    return ""


def comparison_markdown(cmp: ComparisonResult, *, worst: int = 10) -> str:
    verdict = (
        "REGRESSION"
        if cmp.is_regression
        else "improvement"
        if cmp.is_improvement
        else "no detectable change"
    )
    lines = [
        f"## Compare `{cmp.run_a}` (A) vs `{cmp.run_b}` (B)",
        "",
        f"Verdict: **{verdict}** (threshold {cmp.regression_threshold:.3f}, "
        f"{cmp.n_paired} paired cases)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Mean A | {cmp.mean_a:.3f} |",
        f"| Mean B | {cmp.mean_b:.3f} |",
        f"| Mean delta (B - A) | {cmp.mean_delta:+.3f} |",
        f"| 95% bootstrap CI | [{cmp.ci.low:+.3f}, {cmp.ci.high:+.3f}] "
        f"({cmp.ci.resamples} resamples, seed {cmp.ci.seed}) |",
        f"| Permutation p-value | {cmp.permutation.p_value:.4f} |",
    ]
    if cmp.mcnemar is not None:
        m = cmp.mcnemar
        lines.append(
            f"| McNemar (A only / B only / p) | {m.a_only} / {m.b_only} / {m.p_value:.4f} |"
        )
    regressions = sorted(cmp.per_case, key=lambda r: r["delta"])[:worst]
    regressions = [r for r in regressions if r["delta"] < 0]
    if regressions:
        lines += ["", f"### Worst regressions (up to {worst})", ""]
        lines += ["| Case | A | B | Delta |", "|---|---|---|---|"]
        for r in regressions:
            lines.append(f"| {r['case_id']} | {r['a']:.2f} | {r['b']:.2f} | {r['delta']:+.2f} |")
    return "\n".join(lines) + "\n"
