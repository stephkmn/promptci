"""Grader registry. `make_grader(spec)` builds a grader from a suite's GraderSpec."""

from __future__ import annotations

from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.graders.code_exec import CodeExecGrader
from promptci.graders.exact import ExactGrader
from promptci.graders.json_schema import JsonSchemaGrader
from promptci.graders.llm_judge import LLMJudgeGrader, PairwiseJudgeGrader
from promptci.graders.numeric import NumericToleranceGrader
from promptci.graders.regex import RegexGrader
from promptci.suite.schema import GraderSpec

__all__ = [
    "CodeExecGrader",
    "ExactGrader",
    "GradeResult",
    "Grader",
    "JsonSchemaGrader",
    "LLMJudgeGrader",
    "NumericToleranceGrader",
    "PairwiseJudgeGrader",
    "RegexGrader",
    "make_grader",
]

REGISTRY: dict[str, type[Grader]] = {
    "exact": ExactGrader,
    "regex": RegexGrader,
    "json_schema": JsonSchemaGrader,
    "numeric_tolerance": NumericToleranceGrader,
    "code_exec": CodeExecGrader,
    "llm_judge": LLMJudgeGrader,
    "pairwise_judge": PairwiseJudgeGrader,
}


def make_grader(spec: GraderSpec, **extra: Any) -> Grader:
    """Instantiate the grader named by `spec.type` with its options.

    `extra` is for runtime objects a grader needs but a YAML file cannot hold,
    such as the judge provider for llm_judge.
    """
    cls = REGISTRY[spec.type]
    return cls(**spec.options(), **extra)
