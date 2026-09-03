"""Suite schema and loader.

A suite is a YAML file that says what to ask the model, what a correct answer looks
like, and how to grade it. Example::

    name: json_extract
    prompt: |
      Extract the fields as JSON.
      Text: {{ inputs.text }}
    params:
      temperature: 0.0
      max_tokens: 256
    grader:
      type: json_schema
      schema: { type: object, required: [product, price] }
      compare_expected: true
    cases:
      - id: c001
        inputs: { text: "Blue widget, $4.99" }
        expected: { product: "Blue widget", price: 4.99 }
        tags: [products]

Large case sets live in a JSONL file referenced by ``dataset:`` (one case per line,
same fields as an inline case). Inline ``cases`` and ``dataset`` may both be present;
they are concatenated, inline first.

The prompt is a Jinja2 template rendered with ``inputs`` (the case's inputs dict),
``expected`` (useful for few-shot suites, use with care) and ``case_id``.
Undefined variables raise, so a typo in the template fails loudly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GRADER_TYPES = (
    "exact",
    "regex",
    "json_schema",
    "numeric_tolerance",
    "code_exec",
    "llm_judge",
    "pairwise_judge",
)


class Case(BaseModel):
    """One evaluation item."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_is_filename_safe(cls, v: str) -> str:
        bad = set('/\\:*?"<>| \t\n')
        if any(ch in bad for ch in v):
            raise ValueError(f"case id {v!r} contains a character not allowed in ids")
        return v


class GraderSpec(BaseModel):
    """Grader type plus its options. Options differ per grader, so extras are allowed
    and each grader validates its own."""

    model_config = ConfigDict(extra="allow")

    type: str

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in GRADER_TYPES:
            raise ValueError(f"unknown grader type {v!r}; known: {', '.join(GRADER_TYPES)}")
        return v

    def options(self) -> dict[str, Any]:
        """Everything except `type`."""
        return {k: v for k, v in self.model_dump().items() if k != "type"}


class ModelParams(BaseModel):
    """Decoding parameters. Kept generic; each provider maps them to its own names."""

    model_config = ConfigDict(extra="allow")

    temperature: float | None = 0.0
    max_tokens: int | None = 512
    top_p: float | None = None
    seed: int | None = None
    stop: list[str] | None = None
    system: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Drop None so they do not affect the cache key."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class CompareConfig(BaseModel):
    """Thresholds used by `promptci compare` and the CI gate."""

    model_config = ConfigDict(extra="forbid")

    regression_threshold: float = Field(default=0.02, ge=0.0, le=1.0)
    bootstrap_resamples: int = Field(default=10_000, ge=100)
    seed: int = 0


class Suite(BaseModel):
    """A complete evaluation suite."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    prompt: str = Field(min_length=1)
    params: ModelParams = Field(default_factory=ModelParams)
    grader: GraderSpec
    cases: list[Case] = Field(default_factory=list)
    dataset: str | None = None
    compare: CompareConfig = Field(default_factory=CompareConfig)
    fake_responses: dict[str, str] | None = Field(
        default=None,
        description=(
            "Demo only: case_id -> reply text for the `fake/` provider. "
            "Lets the shipped examples run with zero setup. Ignored by real providers."
        ),
    )

    @model_validator(mode="after")
    def _has_cases_or_dataset(self) -> Suite:
        if not self.cases and not self.dataset:
            raise ValueError("suite needs inline `cases` or a `dataset` path")
        ids = [c.id for c in self.cases]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate case ids: {sorted(dupes)}")
        return self

    def content_hash(self) -> str:
        """sha256 over everything that changes the meaning of a run.

        Includes prompt, params, grader and all cases. Excludes description and
        fake_responses. Two runs with the same hash are comparable case by case.
        """
        payload = {
            "name": self.name,
            "prompt": self.prompt,
            "params": self.params.as_dict(),
            "grader": self.grader.model_dump(),
            "cases": [c.model_dump() for c in self.cases],
        }
        s = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


_env = Environment(undefined=StrictUndefined, keep_trailing_newline=False, autoescape=False)


def render_prompt(suite: Suite, case: Case) -> str:
    """Render the suite's Jinja2 prompt for one case."""
    tmpl = _env.from_string(suite.prompt)
    return tmpl.render(inputs=case.inputs, expected=case.expected, case_id=case.id)


def load_cases_jsonl(path: str | Path) -> list[Case]:
    """Read cases from JSONL. Blank lines are skipped. Errors name the line number."""
    cases: list[Case] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cases.append(Case.model_validate(obj))
            except (ValueError, TypeError) as e:
                raise ValueError(f"{path}:{lineno}: {e}") from e
    return cases


def load_suite(path: str | Path, *, limit: int | None = None) -> Suite:
    """Load a suite from YAML, pulling in the JSONL dataset if one is named.

    `limit` keeps the first N cases. It exists so you can smoke-test a suite on
    5 cases before spending an hour on 200.
    """
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{p}: top level must be a mapping")
    suite = Suite.model_validate(raw)
    if suite.dataset:
        ds_path = (p.parent / suite.dataset).resolve()
        if not ds_path.exists():
            raise FileNotFoundError(
                f"{p}: dataset {suite.dataset!r} not found at {ds_path}. "
                "Run the example's download script first."
            )
        extra = load_cases_jsonl(ds_path)
        seen = {c.id for c in suite.cases}
        for c in extra:
            if c.id in seen:
                raise ValueError(f"{ds_path}: case id {c.id!r} duplicates an inline case")
            seen.add(c.id)
        suite = suite.model_copy(update={"cases": suite.cases + extra})
    if limit is not None:
        suite = suite.model_copy(update={"cases": suite.cases[:limit]})
    return suite
