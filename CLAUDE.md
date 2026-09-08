# CLAUDE.md

## Project

PromptCI is a regression-testing framework for LLM applications: YAML eval suites,
cached model calls, SQLite results with provenance, statistical comparison of runs,
judge validation against human labels, and a CI gate that fails a PR on regression.
The owner is Stephanie, an undergraduate building this for her portfolio. She is
learning; explain why, not just what.

## Setup and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                          # must pass before and after every change
ruff check . && ruff format --check .
promptci run examples/json_extract/suite.yaml --model replay/any --limit 12   # zero-setup demo
promptci run examples/json_extract/suite.yaml --model ollama/qwen2.5:7b
```

`make check` runs lint and tests. `make demo-cache` regenerates `cache/ci/` from the
fake provider; only do that if the json_extract prompt or fake_responses changed.

## Layout

- `src/promptci/providers/`: `Provider` protocol, `Completion` dataclass, Ollama,
  OpenAI-compatible, Anthropic, Replay (cache-only), Fake (tests and demo).
- `src/promptci/cache/`: content-addressed disk cache; `CachedProvider` wraps any provider.
- `src/promptci/suite/`: pydantic schema, YAML and JSONL loading, Jinja2 prompt rendering.
- `src/promptci/graders/`: one file per grader; `make_grader(spec)` registry.
- `src/promptci/runner/`: async execution, retries, per-case timeout.
- `src/promptci/store/`: SQLite `runs` and `results` tables, `summarize`.
- `src/promptci/stats/`: bootstrap CI, permutation test, regression verdict. McNemar and
  power helper are M2.
- `src/promptci/report/`: Markdown now, HTML in M2.
- `src/promptci/judge_validation/`: M4.
- `examples/`: one directory per suite, with a `suite.yaml` and a download script where
  the data is not committed.
- `docs/milestones/M1..M5`: task prompts. Read the one being worked on before starting.

## Code style

- Python 3.11+. Type hints on every function signature. Docstrings on every public
  module, class, and function; the docstring says what the thing is for and any
  non-obvious decision.
- `ruff check` and `ruff format` clean (config in pyproject.toml, line length 100).
- No bare `except:`. Catch the specific exception. If a broad catch is needed (the runner
  recording a failed case), comment why.
- Async where I/O happens; graders that do no I/O stay synchronous.
- Tests in `tests/`, one file per module. New behavior gets a test in the same PR.
  Unimplemented planned features get `xfail(strict=True)` tests, never skipped tests.
- Tests use `FakeProvider`. Never call a real model from a test.
- No new dependency without a one-line reason in the commit message. The core
  dependency list is deliberately short.

## Definition of done for any change

1. `pytest -q` passes. `ruff check .` and `ruff format --check .` pass.
2. If a CLI flag or suite YAML field changed, README.md and the relevant docstring
   are updated in the same commit.
3. If behavior changed, a test changed or was added.
4. The commit message says what and why, in one or two sentences.

## Rules about results

- Every number reported anywhere (README, docs, results/, resume) comes from a run
  whose row exists in `results/promptci.db` with `git_sha`, `suite_hash`, and
  `started_at`, and whose exact command is written next to the number.
- Reported results go in `results/` as Markdown exported with `promptci summarize --md`
  or `promptci compare`, committed together with the database.
- Never type a number into a report by hand. Never round in a way that changes the
  conclusion. Never delete a run because it looked bad; run again and report both.
- A comparison is reported with its CI and n, always. "A beat B" without an interval
  is not a result.
- If the cache was used, say so (cache hit rate is in the summary). A 100 percent
  cache-hit run is a replay, not a new measurement, and its latency numbers are the
  original run's.

## Rules about providers and keys

- Default provider is Ollama at `localhost:11434`. Everything must run end to end on
  Ollama alone.
- Every provider implements `complete(prompt, model, **params) -> Completion` and is
  used through `CachedProvider`. Never bypass the cache.
- API keys come from environment variables only (`OPENAI_API_KEY`, `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`). Never write a key into
  a file in this repo, a test, a log line, or a cache entry. Cache entries store the
  prompt and response only.
- `ReplayProvider` never makes a network call. CI uses it exclusively.
- Prices in `src/promptci/prices.yaml` carry a `checked` date. Update it when editing.

## When unsure, ask Stephanie

Do not decide these alone. Stop and ask, with the options laid out:

- Changing what a metric means (how `score`, `passed`, or `pass_rate` is computed;
  how errors count toward the mean; what `regression_threshold` is).
- Changing a dataset split, subset size, seed, or the set of case ids in a committed
  `case_ids.txt`.
- Adding, enabling, or running anything that costs money (a paid API call, a larger
  model on a paid endpoint), including "just to test".
- Removing or weakening a test, marking a failing test xfail, or loosening a grader
  to make more cases pass.
- Changing the cache key function (it invalidates every committed cache entry).
- Picking the judge model or the rubric text for M4.
- Anything that would make a reported number look better without a code reason.
