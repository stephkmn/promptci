"""Regex grader.

Options:

    pattern: regex the output must match (uses `re.search`). If omitted, the case's
        `expected` is used as the pattern, so one suite can have a different pattern per case.
    flags: list of re flag names, e.g. ["IGNORECASE", "MULTILINE"]. Default [].
    full_match: if true, the whole output (after strip) must match. Default false.
    invert: if true, pass when the pattern does NOT match. Useful for "never say X" checks.
"""

from __future__ import annotations

import re
from typing import Any

from promptci.graders.base import Grader, GradeResult
from promptci.suite.schema import Case


def _flags(names: list[str]) -> int:
    value = 0
    for n in names:
        try:
            value |= getattr(re, n)
        except AttributeError as e:
            raise ValueError(f"unknown re flag {n!r}") from e
    return value


class RegexGrader(Grader):
    type = "regex"

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.pattern: str | None = options.get("pattern")
        self.flags = _flags(list(options.get("flags", [])))
        self.full_match = bool(options.get("full_match", False))
        self.invert = bool(options.get("invert", False))
        if self.pattern is not None:
            re.compile(self.pattern, self.flags)

    def grade(self, output: str, case: Case) -> GradeResult:
        pattern = self.pattern if self.pattern is not None else case.expected
        if not isinstance(pattern, str):
            raise ValueError(
                f"case {case.id}: regex grader needs a `pattern` option or a string `expected`"
            )
        rx = re.compile(pattern, self.flags)
        text = output.strip() if self.full_match else output
        m = rx.fullmatch(text) if self.full_match else rx.search(text)
        matched = m is not None
        ok = (not matched) if self.invert else matched
        return GradeResult(
            score=1.0 if ok else 0.0,
            passed=ok,
            details={"pattern": pattern, "matched": matched, "match": m.group(0) if m else None},
        )
