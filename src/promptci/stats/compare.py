"""Paired comparison of two runs.

Everything here works on paired per-case scores: run A and run B were graded on the
same cases, so the natural quantity is the per-case delta ``b - a``, not the two
means in isolation. Pairing removes the between-case variance (some cases are just
hard for everyone), which is why a paired test on 200 cases can detect a difference
that an unpaired one cannot.

Implemented now:

- `bootstrap_mean_ci`: percentile bootstrap CI of the mean delta. Seeded, so the
  number in your report is reproducible.
- `paired_permutation_test`: two-sided p-value for "mean delta is 0" by randomly
  flipping the sign of each delta. Exact reasoning: under the null, A and B are
  exchangeable within each pair, so each delta is equally likely to be +d or -d.

To implement in M2 (stubs below raise NotImplementedError):

- `mcnemar_test`: for binary pass/fail, only the discordant pairs (A passed and B
  failed, or the reverse) carry information. Use the exact binomial version, not the
  chi-square approximation, because discordant counts are often small.
- `power_cases_needed`: how many cases you need to detect a mean delta `d` with 80%
  power at alpha 0.05 given the observed standard deviation of deltas. The two-sided
  normal approximation ``n = ((z_{1-a/2} + z_{power}) * sd / d) ** 2`` is enough.
- `compare_runs`: glue that pulls two runs from the store, aligns cases by id,
  calls the functions above, and applies the regression rule.

Regression rule (used by the CI gate): flag a regression when the upper bound of the
95% CI of the mean delta is below ``-threshold``. That is deliberately conservative.
"Mean delta is negative" is not a regression; "we are confident it is at least
`threshold` worse" is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BootstrapCI:
    mean: float
    low: float
    high: float
    level: float
    resamples: int
    seed: int


def bootstrap_mean_ci(
    deltas: list[float] | np.ndarray,
    *,
    resamples: int = 10_000,
    level: float = 0.95,
    seed: int = 0,
) -> BootstrapCI:
    """Percentile bootstrap confidence interval for the mean of `deltas`.

    With n < 2 the interval collapses to the point estimate; there is nothing to
    resample. The percentile method is used because it needs no distributional
    assumption and is easy to explain. BCa would be tighter for skewed deltas,
    but deltas of scores in [0, 1] are rarely skewed enough to matter.
    """
    d = np.asarray(deltas, dtype=float)
    if d.size == 0:
        raise ValueError("no deltas")
    mean = float(d.mean())
    if d.size < 2:
        return BootstrapCI(mean, mean, mean, level, 0, seed)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(resamples, d.size))
    means = d[idx].mean(axis=1)
    alpha = (1.0 - level) / 2.0
    low, high = np.quantile(means, [alpha, 1.0 - alpha])
    return BootstrapCI(mean, float(low), float(high), level, resamples, seed)


@dataclass
class PermutationResult:
    observed_mean: float
    p_value: float
    permutations: int
    seed: int


def paired_permutation_test(
    deltas: list[float] | np.ndarray,
    *,
    permutations: int = 10_000,
    seed: int = 0,
) -> PermutationResult:
    """Two-sided sign-flip permutation test for mean(delta) == 0.

    The p-value uses the (k + 1) / (N + 1) correction so it is never exactly 0,
    which would be a claim no finite number of permutations can support.
    Pairs with delta exactly 0 contribute nothing under any sign flip; they stay in
    the mean so the statistic matches the reported mean delta.
    """
    d = np.asarray(deltas, dtype=float)
    if d.size == 0:
        raise ValueError("no deltas")
    observed = float(d.mean())
    if np.all(d == 0):
        return PermutationResult(observed, 1.0, 0, seed)
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(permutations, d.size))
    perm_means = (signs * d).mean(axis=1)
    k = int(np.sum(np.abs(perm_means) >= abs(observed) - 1e-12))
    p = (k + 1) / (permutations + 1)
    return PermutationResult(observed, float(min(p, 1.0)), permutations, seed)


@dataclass
class McNemarResult:
    a_only: int  # A passed, B failed
    b_only: int  # B passed, A failed
    both: int
    neither: int
    p_value: float


def mcnemar_test(a_passed: list[bool], b_passed: list[bool]) -> McNemarResult:
    """Exact McNemar test on paired pass/fail outcomes. Implemented in M2."""
    raise NotImplementedError("mcnemar_test is implemented in milestone M2")


def power_cases_needed(
    sd_delta: float, d: float, *, power: float = 0.80, alpha: float = 0.05
) -> int:
    """Cases needed to detect mean delta `d` given per-case delta sd. Implemented in M2."""
    raise NotImplementedError("power_cases_needed is implemented in milestone M2")


@dataclass
class ComparisonResult:
    run_a: str
    run_b: str
    n_paired: int
    mean_a: float
    mean_b: float
    mean_delta: float
    ci: BootstrapCI
    permutation: PermutationResult
    mcnemar: McNemarResult | None
    regression_threshold: float
    is_regression: bool
    is_improvement: bool
    per_case: list[dict[str, Any]] = field(default_factory=list)


def regression_verdict(ci: BootstrapCI, threshold: float) -> tuple[bool, bool]:
    """(is_regression, is_improvement) from the CI and the configured threshold.

    Regression: the whole interval sits below -threshold.
    Improvement: the whole interval sits above +threshold.
    Anything else is "no detectable change at this sample size", which is a
    different statement from "no change".
    """
    return ci.high < -threshold, ci.low > threshold


def align_paired(
    a: dict[str, float], b: dict[str, float]
) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Intersect two case_id -> score maps. Cases missing from either side are dropped
    and the caller should report how many."""
    ids = sorted(set(a) & set(b))
    return ids, np.array([a[i] for i in ids]), np.array([b[i] for i in ids])


def compare_scores(
    a: dict[str, float],
    b: dict[str, float],
    *,
    threshold: float = 0.02,
    resamples: int = 10_000,
    seed: int = 0,
    run_a: str = "A",
    run_b: str = "B",
) -> ComparisonResult:
    """Compare two case_id -> score maps. The store-aware wrapper is written in M2."""
    ids, sa, sb = align_paired(a, b)
    if not ids:
        raise ValueError("runs share no case ids; are they from the same suite?")
    deltas = sb - sa
    ci = bootstrap_mean_ci(deltas, resamples=resamples, seed=seed)
    perm = paired_permutation_test(deltas, permutations=resamples, seed=seed)
    reg, imp = regression_verdict(ci, threshold)
    per_case = [
        {"case_id": i, "a": float(x), "b": float(y), "delta": float(y - x)}
        for i, x, y in zip(ids, sa, sb, strict=True)
    ]
    return ComparisonResult(
        run_a=run_a,
        run_b=run_b,
        n_paired=len(ids),
        mean_a=float(sa.mean()),
        mean_b=float(sb.mean()),
        mean_delta=float(deltas.mean()),
        ci=ci,
        permutation=perm,
        mcnemar=None,
        regression_threshold=threshold,
        is_regression=reg,
        is_improvement=imp,
        per_case=per_case,
    )
