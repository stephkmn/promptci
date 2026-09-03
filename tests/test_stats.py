from __future__ import annotations

import numpy as np
import pytest

from promptci.stats.compare import (
    bootstrap_mean_ci,
    compare_scores,
    mcnemar_test,
    paired_permutation_test,
    power_cases_needed,
    regression_verdict,
)


def test_identical_runs_give_ci_containing_zero_and_p_one():
    deltas = np.zeros(100)
    ci = bootstrap_mean_ci(deltas, resamples=2000, seed=1)
    assert ci.low <= 0.0 <= ci.high
    assert ci.mean == 0.0
    p = paired_permutation_test(deltas, permutations=2000, seed=1)
    assert p.p_value == 1.0


def test_noise_only_ci_contains_zero():
    rng = np.random.default_rng(42)
    deltas = rng.normal(0.0, 0.3, size=200)
    ci = bootstrap_mean_ci(deltas, resamples=5000, seed=0)
    assert ci.low < 0.0 < ci.high
    p = paired_permutation_test(deltas, permutations=5000, seed=0)
    assert p.p_value > 0.05


def test_shifted_deltas_exclude_zero_and_small_p():
    rng = np.random.default_rng(7)
    deltas = rng.normal(0.10, 0.2, size=200)  # true mean +0.10, sd 0.2, se ~0.014
    ci = bootstrap_mean_ci(deltas, resamples=5000, seed=0)
    assert ci.low > 0.0
    assert 0.06 < ci.mean < 0.14
    p = paired_permutation_test(deltas, permutations=5000, seed=0)
    assert p.p_value < 0.01


def test_bootstrap_is_seeded_and_reproducible():
    d = [0.1, -0.2, 0.3, 0.0, 0.05]
    a = bootstrap_mean_ci(d, resamples=1000, seed=3)
    b = bootstrap_mean_ci(d, resamples=1000, seed=3)
    c = bootstrap_mean_ci(d, resamples=1000, seed=4)
    assert (a.low, a.high) == (b.low, b.high)
    assert (a.low, a.high) != (c.low, c.high)


def test_bootstrap_ci_width_shrinks_with_n():
    """The whole point of M2: 50 cases is noisier than 200."""
    rng = np.random.default_rng(0)
    pop = rng.choice([-1.0, 0.0, 1.0], size=200, p=[0.15, 0.7, 0.15])
    small = bootstrap_mean_ci(pop[:50], resamples=3000, seed=0)
    large = bootstrap_mean_ci(pop, resamples=3000, seed=0)
    assert (small.high - small.low) > (large.high - large.low)


def test_permutation_p_never_exactly_zero():
    p = paired_permutation_test(np.full(30, 0.5), permutations=999, seed=0)
    assert 0.0 < p.p_value <= 1.0 / 1000 + 1e-12


def test_regression_verdict_rule():
    from promptci.stats.compare import BootstrapCI

    assert regression_verdict(BootstrapCI(-0.05, -0.08, -0.03, 0.95, 1, 0), 0.02) == (True, False)
    assert regression_verdict(BootstrapCI(-0.05, -0.08, 0.01, 0.95, 1, 0), 0.02) == (False, False)
    assert regression_verdict(BootstrapCI(0.05, 0.03, 0.08, 0.95, 1, 0), 0.02) == (False, True)
    # inside the threshold band on both sides: not a regression even if all-negative
    assert regression_verdict(BootstrapCI(-0.01, -0.015, -0.005, 0.95, 1, 0), 0.02) == (
        False,
        False,
    )


def test_compare_scores_aligns_on_shared_ids():
    a = {"c1": 1.0, "c2": 0.0, "c3": 1.0, "only_a": 1.0}
    b = {"c1": 1.0, "c2": 1.0, "c3": 0.0, "only_b": 0.0}
    cmp = compare_scores(a, b, resamples=500, threshold=0.05)
    assert cmp.n_paired == 3
    assert cmp.mean_delta == pytest.approx(0.0)
    assert [r["case_id"] for r in cmp.per_case] == ["c1", "c2", "c3"]
    assert cmp.is_regression is False and cmp.is_improvement is False
    with pytest.raises(ValueError, match="share no case"):
        compare_scores({"x": 1.0}, {"y": 1.0})


@pytest.mark.xfail(reason="McNemar is milestone M2", raises=NotImplementedError, strict=True)
def test_mcnemar_not_implemented():
    mcnemar_test([True, False], [False, True])


@pytest.mark.xfail(reason="power helper is milestone M2", raises=NotImplementedError, strict=True)
def test_power_not_implemented():
    power_cases_needed(0.3, 0.05)
