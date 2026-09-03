from __future__ import annotations

from pathlib import Path

import pytest

from promptci.suite.schema import Case, Suite, load_suite

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"


@pytest.fixture
def json_extract_suite() -> Suite:
    return load_suite(EXAMPLES / "json_extract" / "suite.yaml")


@pytest.fixture
def case() -> Case:
    return Case(id="t1", inputs={"x": "hello"}, expected="42")
