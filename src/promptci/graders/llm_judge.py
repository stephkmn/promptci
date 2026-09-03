"""LLM-as-judge graders (M4). Not implemented yet.

Two graders live here.

`LLMJudgeGrader` (type ``llm_judge``): single-answer grading. The judge model reads a
rubric, the task input, optionally a reference answer, and the candidate output, and
returns an integer score 1-5. The grader maps that to [0, 1] as ``(score - 1) / 4``.
`passed` is None unless `pass_threshold` is set.

Options:
    judge_model: model string for the judge, e.g. ``ollama/qwen2.5:7b``. Must differ
        from the candidate model when you can manage it; a model grading itself is
        systematically generous.
    rubric: text describing what 1 through 5 mean. Required.
    reference_field: which key of `case.expected` (or `case.inputs`) holds a reference
        answer to show the judge. Optional.
    pass_threshold: score in 1-5 at or above which `passed` is True. Optional.
    parse: how to find the score in the judge output. Default: last integer 1-5 on a
        line starting with "Score:" (case-insensitive), falling back to the last
        standalone digit 1-5.

`PairwiseJudgeGrader` (type ``pairwise_judge``): A vs B. The case's `inputs` hold the
question and two answers. The judge is asked twice, once with A first and once with B
first. The verdicts are combined:
    - both say A: A wins (score 1.0 for A)
    - both say B: B wins (0.0)
    - they disagree: tie by position bias (0.5), and `details["position_biased"]` = True

Position bias rate over a run is the fraction of cases where the two orderings
disagreed. Report it; it is often 10-30% for small judges.

Both graders call the judge through the same provider registry and cache as the
candidate, so judge calls are cached and replayable in CI too.

Implementation note: the runner passes the judge provider in at construction time
(`judge=...`) so the grader does not build its own HTTP client per case.
"""

from __future__ import annotations

from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.suite.schema import Case

DEFAULT_RUBRIC = """Score the answer from 1 to 5.
5: fully correct, complete, and clearly written.
4: correct with a minor omission or wording issue.
3: partially correct; a reader would need to fix something.
2: mostly wrong or missing key content.
1: wrong, empty, or off topic.
Reply with your reasoning, then a final line "Score: N"."""


class LLMJudgeGrader(Grader):
    type = "llm_judge"

    def __init__(self, judge: Any = None, **options: Any):
        super().__init__(**options)
        self.judge = judge
        self.judge_model: str | None = options.get("judge_model")
        self.rubric: str = options.get("rubric", DEFAULT_RUBRIC)
        self.pass_threshold: int | None = options.get("pass_threshold")

    async def agrade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("llm_judge grader is implemented in milestone M4")

    def grade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("llm_judge grader is implemented in milestone M4")


class PairwiseJudgeGrader(Grader):
    type = "pairwise_judge"

    def __init__(self, judge: Any = None, **options: Any):
        super().__init__(**options)
        self.judge = judge
        self.judge_model: str | None = options.get("judge_model")

    async def agrade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("pairwise_judge grader is implemented in milestone M4")

    def grade(self, output: str, case: Case) -> GradeResult:
        raise NotImplementedError("pairwise_judge grader is implemented in milestone M4")
