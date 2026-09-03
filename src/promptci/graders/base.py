"""Grader protocol and GradeResult.

A grader looks at a model output and the case's expected value and returns a score in
[0, 1]. `passed` is a hard yes/no when the grader has one (exact match does, an LLM
judge giving 3/5 does not, so it leaves `passed` as None unless a threshold is set).

Graders are synchronous unless they need a model (llm_judge, pairwise_judge) or a
subprocess (code_exec); those implement `agrade`. The runner calls `agrade` on
everything and the base class adapts sync graders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from promptci.suite.schema import Case


@dataclass
class GradeResult:
    score: float
    passed: bool | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be in [0, 1], got {self.score}")


class Grader:
    """Base class. Subclasses implement `grade` (sync) or override `agrade` (async)."""

    type: str = "base"

    def __init__(self, **options: Any):
        self.options = options

    def grade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError

    async def agrade(self, output: str, case: Case) -> GradeResult:
        return self.grade(output, case)
