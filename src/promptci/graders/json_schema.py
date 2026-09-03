"""JSON schema grader with optional field-level exact match.

Scoring, in order:

1. Find JSON in the output. The grader accepts the whole output as JSON, or the first
   fenced ```json block, or the first balanced {...} / [...] region. Models wrap JSON
   in prose more often than not, so being strict here would measure formatting, not
   extraction.
2. Validate against `schema` (a JSON Schema dict). Invalid means score 0.
3. If `compare_expected` is true and the case has `expected`, compare field by field.
   Score is the fraction of expected top-level keys whose value matches exactly
   (after the same normalization as `exact`: strings are stripped, and numbers compare
   as floats). `passed` is true only when all fields match.
   If `compare_expected` is false, a valid document scores 1.

Options:

    schema: JSON Schema dict. Required unless `compare_expected` is true and you only
        want field matching (then `schema` may be omitted).
    compare_expected: bool, default true.
    fields: optional list of keys to compare. Default: all keys in `expected`.
    string_normalize: normalize steps applied to string values before comparison.
        Default ["strip", "lower", "collapse_whitespace"].
    extra_keys_penalty: if true, an output key not in `expected` counts as one wrong
        field. Default false. Turn on when hallucinated fields matter.

`details` lists which fields matched and which did not, so the per-case diff in the
report says exactly what went wrong.
"""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema

from promptci.graders.base import Grader, GradeResult
from promptci.graders.exact import normalize
from promptci.suite.schema import Case

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def find_json(text: str) -> Any:
    """Parse JSON out of model output. Raises ValueError if none can be found."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    for m in _FENCE.finditer(text):
        try:
            return json.loads(m.group(1))
        except ValueError:
            continue
    # first balanced object or array
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except ValueError:
                            break
            start = text.find(opener, start + 1)
    raise ValueError("no JSON found in output")


def _values_equal(got: Any, want: Any, steps: list[str]) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return got is want
    if isinstance(want, int | float) and isinstance(got, int | float):
        return abs(float(got) - float(want)) < 1e-9
    if isinstance(want, str) and isinstance(got, str):
        return normalize(got, steps) == normalize(want, steps)
    if isinstance(want, str) and isinstance(got, int | float):
        return normalize(str(got), steps) == normalize(want, steps)
    if isinstance(want, list) and isinstance(got, list):
        return len(got) == len(want) and all(
            _values_equal(g, w, steps) for g, w in zip(got, want, strict=True)
        )
    if isinstance(want, dict) and isinstance(got, dict):
        return set(got) == set(want) and all(_values_equal(got[k], want[k], steps) for k in want)
    return got == want


class JsonSchemaGrader(Grader):
    type = "json_schema"

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.schema: dict[str, Any] | None = options.get("schema")
        self.compare_expected = bool(options.get("compare_expected", True))
        self.fields: list[str] | None = options.get("fields")
        self.steps: list[str] = list(
            options.get("string_normalize", ["strip", "lower", "collapse_whitespace"])
        )
        self.extra_keys_penalty = bool(options.get("extra_keys_penalty", False))
        if self.schema is None and not self.compare_expected:
            raise ValueError("json_schema grader needs `schema` or `compare_expected: true`")
        if self.schema is not None:
            jsonschema.Draft202012Validator.check_schema(self.schema)
            self._validator = jsonschema.Draft202012Validator(self.schema)
        else:
            self._validator = None

    def grade(self, output: str, case: Case) -> GradeResult:
        try:
            doc = find_json(output)
        except ValueError as e:
            return GradeResult(0.0, False, {"error": str(e), "stage": "parse"})

        if self._validator is not None:
            errors = sorted(self._validator.iter_errors(doc), key=lambda e: list(e.path))
            if errors:
                return GradeResult(
                    0.0,
                    False,
                    {
                        "stage": "schema",
                        "schema_errors": [
                            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                            for e in errors[:10]
                        ],
                    },
                )

        if not self.compare_expected or case.expected is None:
            return GradeResult(1.0, True, {"stage": "schema", "parsed": doc})

        if not isinstance(case.expected, dict) or not isinstance(doc, dict):
            ok = _values_equal(doc, case.expected, self.steps)
            return GradeResult(1.0 if ok else 0.0, ok, {"stage": "compare", "parsed": doc})

        keys = self.fields if self.fields is not None else list(case.expected.keys())
        matched: list[str] = []
        wrong: dict[str, dict[str, Any]] = {}
        for k in keys:
            want = case.expected.get(k)
            got = doc.get(k, "<missing>")
            if k in doc and _values_equal(got, want, self.steps):
                matched.append(k)
            else:
                wrong[k] = {"expected": want, "got": got}
        extra = sorted(set(doc) - set(case.expected)) if self.extra_keys_penalty else []
        total = len(keys) + len(extra)
        score = (len(matched) / total) if total else 1.0
        passed = not wrong and not extra
        return GradeResult(
            score,
            passed,
            {"stage": "compare", "matched": matched, "wrong": wrong, "extra_keys": extra},
        )
