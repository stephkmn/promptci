# PromptCI

Regression testing for LLM applications. Define an evaluation suite in YAML, run it
against any model, store every result with provenance, compare two runs with proper
statistics, validate the LLM judge against human labels, and fail a pull request when
quality regresses.

Think of it as pytest for prompts and models.

```
pip install -e ".[dev]"
promptci run examples/json_extract/suite.yaml --model replay/any      # zero-setup demo
promptci run examples/json_extract/suite.yaml --model ollama/qwen2.5:7b
promptci compare <run_a> <run_b>
```

Status: skeleton. M1 core is implemented and tested (providers, cache, suite schema,
four graders, SQLite store, runner, CLI `run`/`summarize`/`compare`). The statistics
module has bootstrap CI and a paired permutation test with tests against known cases.
See `docs/milestones/` for what comes next.

## Why this exists

Teams building on LLMs spend most of their engineering time on evaluation, not
prompting. The hard parts are not "call the model": they are knowing whether a change
made things better, at what cost, with what confidence, and whether the grader you
used can be trusted. PromptCI is a small framework that takes each of those seriously:

- Every completion is cached by content hash, so re-running is free and CI can replay
  a run with no API key.
- Every result row carries tokens, latency, cost, the suite hash, and the git SHA.
- Comparing two runs gives a paired bootstrap confidence interval and a permutation
  p-value, not two percentages and a guess.
- The LLM judge is checked against human labels before its scores are used for
  anything, and pairwise judging measures its own position bias.
- The CI gate is a rule with a threshold, written down, applied by a machine.

## Architecture

```
promptci run suite.yaml --model ollama/qwen2.5:7b
        |
        v
   suite/        YAML + Jinja2 prompt + cases (inline or JSONL)      pydantic
        |
        v
   runner/       async, semaphore, retries, per-case timeout
        |                  |
        v                  v
   providers/          cache/          sha256(provider, model, params, prompt) -> JSON file
   ollama              (every call goes through it; replay/ reads it and never calls out)
   openai-compat
   anthropic
   replay, fake
        |
        v
   graders/      exact, regex, json_schema, numeric_tolerance      [M3] code_exec
                                                                    [M4] llm_judge, pairwise_judge
        |
        v
   store/        SQLite: runs(run_id, suite_hash, model, params, git_sha, ...)
                         results(run_id, case_id, output, score, passed, tokens, latency, cost, ...)
        |
        v
   stats/        summary; compare: paired deltas, bootstrap CI, permutation test
                 [M2] McNemar, power helper, regression verdict wired to CI
   report/       Markdown now; [M2] self-contained HTML
   judge_validation/   [M4] kappa and Spearman against MT-Bench and SummEval labels
```

Model strings are `provider/model`: `ollama/qwen2.5:7b`, `groq/llama-3.1-8b-instant`,
`openrouter/meta-llama/llama-3.1-8b-instruct`, `anthropic/claude-3-5-haiku-latest`,
`replay/ollama/qwen2.5:7b` (serve from cache, error on miss), `replay/any` (demo),
`fake/demo` (deterministic offline provider used by tests and to build the demo cache).

## Quick start

Python 3.11 or newer.

```bash
git clone https://github.com/[YOUR_GITHUB]/promptci && cd promptci
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q                                              # 56 passed, 5 xfailed (planned work)
promptci run examples/json_extract/suite.yaml --model replay/any
```

The last command replays 12 cases from `cache/ci/` in under a second and prints a
summary table. The cached replies come from a deterministic fake provider, so this
is a demo of the pipeline, not a measurement of any model. To measure a model:

```bash
ollama pull qwen2.5:7b
promptci run examples/json_extract/suite.yaml --model ollama/qwen2.5:7b
promptci summarize <run_id>
promptci runs
```

## Writing a suite

```yaml
name: json_extract
prompt: |
  Extract the fields as JSON. Text: {{ inputs.text }}
params: { temperature: 0.0, max_tokens: 200 }
grader:
  type: json_schema
  schema: { type: object, required: [name, price] }
  compare_expected: true
compare:
  regression_threshold: 0.03
cases:
  - id: c001
    inputs: { text: "Aurora Desk Lamp, $49.99" }
    expected: { name: "Aurora Desk Lamp", price: 49.99 }
dataset: cases.jsonl        # optional; one case per line, same fields
```

Graders return a score in [0, 1] and, when it makes sense, a hard pass/fail:

| type | what it checks | options |
|---|---|---|
| `exact` | normalized string equality, with optional regex extraction (GSM8K `#### N`) | `normalize`, `extract`, `extract_last` |
| `regex` | `re.search` match, optionally inverted | `pattern`, `flags`, `full_match`, `invert` |
| `json_schema` | parses JSON out of prose, validates schema, field-level match vs `expected` | `schema`, `compare_expected`, `fields`, `extra_keys_penalty` |
| `numeric_tolerance` | last number in output within tolerance | `abs_tol`, `rel_tol`, `extract` |
| `code_exec` (M3) | runs candidate code against tests in a subprocess | `timeout_s`, `memory_mb` |
| `llm_judge` (M4) | rubric-based 1-5 score from a separate judge model | `judge_model`, `rubric`, `pass_threshold` |
| `pairwise_judge` (M4) | A vs B with order swap; reports position bias | `judge_model` |

## Comparing runs

```
$ promptci compare 07c7e08ccb9b 6b2f211ff667
## Compare `07c7e08ccb9b` (A) vs `6b2f211ff667` (B)

Verdict: **no detectable change** (threshold 0.030, 12 paired cases)

| Metric | Value |
|---|---|
| Mean A | 0.938 |
| Mean B | 0.938 |
| Mean delta (B - A) | +0.000 |
| 95% bootstrap CI | [+0.000, +0.000] (10000 resamples, seed 0) |
| Permutation p-value | 1.0000 |
```

The regression rule: B regressed if the upper bound of the 95% CI of the mean per-case
delta is below `-regression_threshold`. "Mean went down" is not a regression. "We are
confident it went down by at least the threshold" is. `--fail-on-regression` exits 3,
which is what `.github/workflows/eval.yml` uses.

## Examples shipped

| suite | grader | data |
|---|---|---|
| `examples/json_extract` | json_schema + field match | 12 hand-written cases inline (M1 extends to 60) |
| `examples/gsm8k` | exact with `#### N` extraction | 5 inline; `download.py` fetches a seeded 200-item test subset |
| `examples/humaneval` | code_exec (M3) | 1 inline; `download.py` fetches all 164 |
| `examples/summarize_judge` | llm_judge (M4) | 5 short passages inline |

## What "done" looks like

Milestones are in `docs/milestones/`. The short version:

1. M1: run GSM8K-200 and json_extract-60 on two local models; a table with pass rate,
   mean and p95 latency, and tokens per model.
2. M2: `compare` with bootstrap CI, permutation test, McNemar, power helper, HTML
   report; an experiment showing a 50-case eval cannot distinguish two prompts that a
   200-case eval can.
3. M3: sandboxed `code_exec`; HumanEval pass@1 with the unbiased estimator.
4. M4: `llm_judge` and `pairwise_judge`; judge agreement with humans (kappa, Spearman)
   on MT-Bench and SummEval for a small local judge versus a stronger one.
5. M5: CI regression gate with PR comment; PyPI release; a write-up of the M2 and M4
   findings.

## Honest limits

- `code_exec` (when implemented) is a subprocess with a timeout and resource limits.
  It is not a security sandbox. Do not run untrusted code from an untrusted model on a
  machine you care about.
- Cost numbers come from `src/promptci/prices.yaml`, which you must verify against the
  provider's current pricing page. Local models are $0.
- An LLM judge's score means nothing until its agreement with humans is measured (M4).
- Bootstrap and permutation tests assume cases are independent draws from the
  population you care about. Two hundred GSM8K problems tell you about GSM8K.

## License

MIT. See LICENSE.
