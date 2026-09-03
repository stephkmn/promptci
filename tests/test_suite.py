from __future__ import annotations

import json
import shutil

import pytest

from promptci.graders import make_grader
from promptci.suite.schema import Case, Suite, load_suite, render_prompt
from tests.conftest import EXAMPLES


def test_json_extract_suite_loads(json_extract_suite):
    s = json_extract_suite
    assert s.name == "json_extract"
    assert len(s.cases) >= 10
    assert s.grader.type == "json_schema"
    assert s.params.as_dict() == {"temperature": 0.0, "max_tokens": 200}
    assert len({c.id for c in s.cases}) == len(s.cases)
    # every case has a demo reply so the zero-setup demo covers the whole suite
    assert set(s.fake_responses) == {c.id for c in s.cases}


def test_render_prompt_substitutes_inputs(json_extract_suite):
    c = json_extract_suite.cases[0]
    text = render_prompt(json_extract_suite, c)
    assert c.inputs["text"] in text
    assert "{{" not in text


def test_render_prompt_fails_on_undefined_variable():
    s = Suite(
        name="x",
        prompt="{{ inputs.missing }}",
        grader={"type": "exact"},
        cases=[Case(id="a", inputs={}, expected="1")],
    )
    with pytest.raises(Exception, match="missing"):
        render_prompt(s, s.cases[0])


def test_content_hash_ignores_description_and_fake_responses(json_extract_suite):
    s = json_extract_suite
    h = s.content_hash()
    assert s.model_copy(update={"description": "other"}).content_hash() == h
    assert s.model_copy(update={"fake_responses": None}).content_hash() == h
    assert s.model_copy(update={"prompt": s.prompt + " "}).content_hash() != h


def test_suite_rejects_unknown_grader_and_duplicate_ids():
    with pytest.raises(ValueError, match="unknown grader"):
        Suite(name="x", prompt="p", grader={"type": "vibes"}, cases=[Case(id="a")])
    with pytest.raises(ValueError, match="duplicate"):
        Suite(name="x", prompt="p", grader={"type": "exact"}, cases=[Case(id="a"), Case(id="a")])
    with pytest.raises(ValueError, match="cases"):
        Suite(name="x", prompt="p", grader={"type": "exact"})


def test_dataset_jsonl_is_merged_and_limit_applies(tmp_path):
    src = EXAMPLES / "gsm8k" / "suite.yaml"
    shutil.copy(src, tmp_path / "suite.yaml")
    rows = [
        {"id": f"extra_{i}", "inputs": {"question": f"What is {i}+{i}?"}, "expected": str(2 * i)}
        for i in range(3)
    ]
    (tmp_path / "cases.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8"
    )
    s = load_suite(tmp_path / "suite.yaml")
    assert len(s.cases) == 5 + 3
    assert s.cases[-1].id == "extra_2"
    assert len(load_suite(tmp_path / "suite.yaml", limit=2).cases) == 2


def test_missing_dataset_gives_clear_error():
    with pytest.raises(FileNotFoundError, match="download"):
        load_suite(EXAMPLES / "gsm8k" / "suite.yaml")


@pytest.mark.parametrize("name", ["json_extract", "humaneval", "summarize_judge"])
def test_all_example_suites_validate_and_build_grader(name):
    """Suites using not-yet-implemented graders must still load and construct."""
    path = EXAMPLES / name / "suite.yaml"
    if name == "humaneval":
        # dataset not downloaded in tests; load the inline part only
        import yaml

        raw = yaml.safe_load(path.read_text())
        raw.pop("dataset")
        s = Suite.model_validate(raw)
    else:
        s = load_suite(path)
    make_grader(s.grader)
    render_prompt(s, s.cases[0])
