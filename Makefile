.PHONY: install test lint format demo demo-cache clean check

PY ?= python

install:
	$(PY) -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

check: lint test

# Zero-setup demo: replays the 12 json_extract cases from the committed cache.
demo:
	promptci run examples/json_extract/suite.yaml --model replay/any

# Regenerate the committed demo cache from the deterministic fake provider.
# Only needed if you change the json_extract prompt or its fake_responses.
# --cache-dir is explicit because fake/demo defaults to the gitignored cache/local.
demo-cache:
	rm -rf cache/ci
	promptci run examples/json_extract/suite.yaml --model fake/demo --cache-dir cache/ci --db /tmp/promptci-demo-cache.db

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
