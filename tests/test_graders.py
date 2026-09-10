from __future__ import annotations

import pytest

from promptci.graders import make_grader
from promptci.graders.base import GradeResult
from promptci.graders.exact import ExactGrader
from promptci.graders.json_schema import JsonSchemaGrader, find_json
from promptci.graders.numeric import NumericToleranceGrader
from promptci.graders.regex import RegexGrader
from promptci.suite.schema import Case, GraderSpec

# -- GradeResult ---------------------------------------------------------------


def test_grade_result_rejects_out_of_range():
    with pytest.raises(ValueError):
        GradeResult(score=1.5)
    GradeResult(score=0.0)
    GradeResult(score=1.0)


# -- exact ---------------------------------------------------------------------


def test_exact_default_strip():
    g = ExactGrader()
    c = Case(id="a", expected="Paris")
    assert g.grade("  Paris\n", c).passed is True
    assert g.grade("paris", c).passed is False


def test_exact_with_normalization_and_list_expected():
    g = ExactGrader(normalize=["strip", "lower", "strip_punctuation", "collapse_whitespace"])
    c = Case(id="a", expected=["New York", "NYC"])
    assert g.grade("new   york.", c).score == 1.0
    assert g.grade("nyc!", c).score == 1.0
    assert g.grade("Boston", c).score == 0.0


def test_exact_gsm8k_style_extraction():
    g = ExactGrader(extract=r"####\s*\$?(-?[\d,]*\.?\d+)", normalize=["strip", "remove_commas"])
    c = Case(id="a", expected="1234")
    out = "First 600, then 634 more.\n#### 600\nActually the total is\n#### $1,234"
    r = g.grade(out, c)
    assert r.passed is True
    assert r.details["pattern_matched"] is True
    assert r.details["extracted"] == "1,234"
    # no marker: whole output graded, fails, and details say the pattern did not match
    r2 = g.grade("The answer is 1234", c)
    assert r2.passed is False and r2.details["pattern_matched"] is False


def test_exact_rejects_bad_normalize_step():
    with pytest.raises(ValueError):
        ExactGrader(normalize=["shout"])


# -- regex ---------------------------------------------------------------------


def test_regex_pattern_option_and_flags():
    g = RegexGrader(pattern=r"^yes\b", flags=["IGNORECASE", "MULTILINE"])
    c = Case(id="a")
    assert g.grade("Reasoning...\nYES, it is.", c).passed is True
    assert g.grade("no", c).passed is False


def test_regex_from_expected_and_invert():
    g = RegexGrader()
    assert g.grade("the cat sat", Case(id="a", expected=r"c.t")).score == 1.0
    inv = RegexGrader(pattern="sorry", invert=True, flags=["IGNORECASE"])
    assert inv.grade("Sorry, I cannot help", Case(id="a")).passed is False
    assert inv.grade("Here you go", Case(id="a")).passed is True


# -- json_schema ---------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "required": ["name", "price"],
    "properties": {"name": {"type": "string"}, "price": {"type": ["number", "null"]}},
}


def test_find_json_handles_prose_and_fences():
    assert find_json('{"a": 1}') == {"a": 1}
    assert find_json('Sure!\n```json\n{"a": 1}\n```\nDone.') == {"a": 1}
    assert find_json('The result: {"a": {"b": "}"}} ok') == {"a": {"b": "}"}}
    assert find_json("[1, 2]") == [1, 2]
    with pytest.raises(ValueError):
        find_json("no json here")


def test_json_schema_field_match_partial_score():
    g = JsonSchemaGrader(schema=SCHEMA)
    c = Case(id="a", expected={"name": "Lamp", "price": 49.99})
    full = g.grade('{"name": " lamp ", "price": 49.99}', c)
    assert full.score == 1.0 and full.passed is True
    half = g.grade('{"name": "Lamp", "price": 38}', c)
    assert half.score == 0.5 and half.passed is False
    assert half.details["wrong"] == {"price": {"expected": 49.99, "got": 38}}


def test_json_schema_invalid_documents_score_zero():
    g = JsonSchemaGrader(schema=SCHEMA)
    c = Case(id="a", expected={"name": "Lamp", "price": 1})
    assert g.grade("not json", c).details["stage"] == "parse"
    r = g.grade('{"name": 5, "price": 1}', c)
    assert r.score == 0.0 and r.details["stage"] == "schema"
    assert any("name" in e for e in r.details["schema_errors"])


def test_json_schema_extra_keys_penalty_and_no_compare():
    g = JsonSchemaGrader(schema=SCHEMA, extra_keys_penalty=True)
    c = Case(id="a", expected={"name": "Lamp", "price": 1})
    r = g.grade('{"name": "Lamp", "price": 1, "color": "red"}', c)
    assert r.score == pytest.approx(2 / 3) and r.passed is False
    g2 = JsonSchemaGrader(schema=SCHEMA, compare_expected=False)
    assert g2.grade('{"name": "x", "price": null}', c).score == 1.0


def test_json_schema_demo_responses_grade_as_documented(json_extract_suite):
    """The suite file documents which demo replies are wrong. Check that claim."""
    g = make_grader(json_extract_suite.grader)
    by_id = {c.id: c for c in json_extract_suite.cases}
    passed = {
        cid: g.grade(reply, by_id[cid]).passed
        for cid, reply in json_extract_suite.fake_responses.items()
    }
    assert {k for k, v in passed.items() if not v} == {"c005", "c010", "c011"}
    assert passed["c007"] is True  # fenced JSON must still parse


# -- numeric -------------------------------------------------------------------

GSM8K_PATTERN = r"####\s*\$?(-?[\d,]*\.?\d+)"


def test_numeric_tolerance():
    g = NumericToleranceGrader(abs_tol=0.01)
    assert g.grade("The answer is about 3.14159.", Case(id="a", expected=3.14)).passed is True
    assert g.grade("I get 1,000 then 2,000", Case(id="a", expected=2000)).passed is True
    assert g.grade("no digits", Case(id="a", expected=1)).passed is False
    rel = NumericToleranceGrader(rel_tol=0.05)
    assert rel.grade("104", Case(id="a", expected=100)).passed is True


def test_numeric_grades_decimal_form_of_an_integer():
    """An output of "#### 6.00" is right when the case expects "6".

    This is why gsm8k uses numeric_tolerance and not exact: string equality scored
    the decimal form as wrong.
    """
    g = NumericToleranceGrader(extract=GSM8K_PATTERN)
    c = Case(id="a", expected="6")
    assert g.grade("... so $4.00 + $2.00 = $6.00\n\n#### 6.00", c).passed is True
    assert g.grade("#### 6", c).passed is True
    assert g.grade("#### 7", c).passed is False


def test_numeric_require_extract_match_fails_unformatted_output():
    """A model that ignores the "#### N" instruction fails instead of being rescued
    by the fallback scan of its prose."""
    prose = "To find the discount, multiply the price. The answer is 70"
    c = Case(id="a", expected="70")
    lenient = NumericToleranceGrader(extract=GSM8K_PATTERN)
    assert lenient.grade(prose, c).passed is True  # falls back to the last number
    strict = NumericToleranceGrader(extract=GSM8K_PATTERN, require_extract_match=True)
    r = strict.grade(prose, c)
    assert r.passed is False
    assert r.details["error"] == "output did not match the extract pattern"
    assert strict.grade("#### 70", c).passed is True


def test_numeric_require_extract_match_needs_a_pattern():
    with pytest.raises(ValueError, match="require_extract_match"):
        NumericToleranceGrader(require_extract_match=True)


# -- registry and stubs ---------------------------------------------------------


def test_make_grader_passes_options():
    g = make_grader(GraderSpec(type="exact", normalize=["lower"]))
    assert isinstance(g, ExactGrader) and g.steps == ["lower"]


@pytest.mark.xfail(
    reason="code_exec grader is milestone M3", raises=NotImplementedError, strict=True
)
def test_code_exec_grader_not_implemented():
    g = make_grader(GraderSpec(type="code_exec"))
    g.grade("return 1", Case(id="a", inputs={"prompt": "def f():", "test": "", "entry_point": "f"}))


@pytest.mark.xfail(
    reason="llm_judge grader is milestone M4", raises=NotImplementedError, strict=True
)
def test_llm_judge_grader_not_implemented():
    make_grader(GraderSpec(type="llm_judge", judge_model="fake/j")).grade("x", Case(id="a"))


@pytest.mark.xfail(
    reason="pairwise_judge grader is milestone M4", raises=NotImplementedError, strict=True
)
def test_pairwise_judge_grader_not_implemented():
    make_grader(GraderSpec(type="pairwise_judge", judge_model="fake/j")).grade("x", Case(id="a"))
