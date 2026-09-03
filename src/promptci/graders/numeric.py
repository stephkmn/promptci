"""Numeric tolerance grader.

Pulls the first (or last) number out of the output and compares to `expected`.

Options:

    abs_tol: absolute tolerance. Default 1e-6.
    rel_tol: relative tolerance. Default 0.0. Passes if either tolerance is met.
    extract: regex with one capture group to locate the number first (same idea as
        `exact`). Default: the last number-looking token in the output.
    use_last: when scanning for bare numbers, take the last one. Default true.
"""

from __future__ import annotations

import math
import re
from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.graders.exact import extract
from promptci.suite.schema import Case

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?")


def parse_number(text: str) -> float:
    return float(text.replace(",", "").strip())


class NumericToleranceGrader(Grader):
    type = "numeric_tolerance"

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.abs_tol = float(options.get("abs_tol", 1e-6))
        self.rel_tol = float(options.get("rel_tol", 0.0))
        self.pattern: str | None = options.get("extract")
        self.use_last = bool(options.get("use_last", True))

    def grade(self, output: str, case: Case) -> GradeResult:
        try:
            want = float(case.expected)
        except (TypeError, ValueError) as e:
            raise ValueError(f"case {case.id}: expected must be numeric") from e
        text, _ = extract(output, self.pattern, last=self.use_last)
        nums = _NUMBER.findall(text)
        if not nums:
            return GradeResult(0.0, False, {"error": "no number in output"})
        raw = nums[-1] if self.use_last else nums[0]
        try:
            got = parse_number(raw)
        except ValueError:
            return GradeResult(0.0, False, {"error": f"could not parse {raw!r}"})
        ok = math.isclose(got, want, rel_tol=self.rel_tol, abs_tol=self.abs_tol)
        return GradeResult(
            1.0 if ok else 0.0, ok, {"got": got, "expected": want, "abs_error": abs(got - want)}
        )
