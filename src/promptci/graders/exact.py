"""Exact-match grader with normalization and answer extraction.

Options (all optional):

    normalize: list of steps applied to both output and expected, in order.
        Known steps: "strip", "lower", "collapse_whitespace", "strip_punctuation",
        "remove_commas" (for numbers like 1,234).
        Default: ["strip"].
    extract: a regex with one capture group. If given, the grader searches the
        model output for it and grades the captured text instead of the whole output.
        GSM8K uses ``"####\\s*(-?[\\d,\\.]+)"`` to pull the final number.
        If the regex does not match, the output is graded as-is (and details records it).
    extract_last: if true and `extract` matches several times, use the last match.
        Default true, because models often restate the answer at the end.

`expected` may be a string, number, or list of acceptable strings.
"""

from __future__ import annotations

import re
import string
from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.suite.schema import Case

_WS = re.compile(r"\s+")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize(text: str, steps: list[str]) -> str:
    for step in steps:
        if step == "strip":
            text = text.strip()
        elif step == "lower":
            text = text.lower()
        elif step == "collapse_whitespace":
            text = _WS.sub(" ", text).strip()
        elif step == "strip_punctuation":
            text = text.translate(_PUNCT_TABLE)
        elif step == "remove_commas":
            text = text.replace(",", "")
        else:
            raise ValueError(f"unknown normalize step {step!r}")
    return text


def extract(text: str, pattern: str | None, *, last: bool = True) -> tuple[str, bool]:
    """Return (extracted_text, matched). If no pattern or no match, return input unchanged."""
    if not pattern:
        return text, False
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL))
    if not matches:
        return text, False
    m = matches[-1] if last else matches[0]
    return (m.group(1) if m.groups() else m.group(0)), True


class ExactGrader(Grader):
    type = "exact"

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.steps: list[str] = list(options.get("normalize", ["strip"]))
        self.pattern: str | None = options.get("extract")
        self.extract_last: bool = bool(options.get("extract_last", True))
        normalize("", self.steps)  # fail fast on a bad step name
        if self.pattern:
            re.compile(self.pattern)

    def grade(self, output: str, case: Case) -> GradeResult:
        candidates: list[Any] = (
            list(case.expected) if isinstance(case.expected, list | tuple) else [case.expected]
        )
        extracted, matched = extract(output, self.pattern, last=self.extract_last)
        got = normalize(extracted, self.steps)
        want = [normalize(str(c), self.steps) for c in candidates]
        ok = got in want
        return GradeResult(
            score=1.0 if ok else 0.0,
            passed=ok,
            details={"extracted": extracted, "pattern_matched": matched, "normalized": got},
        )
