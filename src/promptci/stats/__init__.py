"""Statistics for comparing runs."""

from promptci.stats.compare import (
    BootstrapCI,
    ComparisonResult,
    McNemarResult,
    PermutationResult,
    align_paired,
    bootstrap_mean_ci,
    compare_scores,
    mcnemar_test,
    paired_permutation_test,
    power_cases_needed,
    regression_verdict,
)

__all__ = [
    "BootstrapCI",
    "ComparisonResult",
    "McNemarResult",
    "PermutationResult",
    "align_paired",
    "bootstrap_mean_ci",
    "compare_scores",
    "mcnemar_test",
    "paired_permutation_test",
    "power_cases_needed",
    "regression_verdict",
]
