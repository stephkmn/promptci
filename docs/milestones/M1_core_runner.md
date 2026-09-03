# M1: Core runner, two suites, two local models

## Goal

At the end of this milestone PromptCI runs real evaluation suites against real local
models and stores every result. You will have GSM8K-200 and a 60-case json_extract
suite measured on two Ollama models, with a results table (pass rate, mean and p95
latency, tokens) that you produced and can explain line by line.

## Read first

- `CLAUDE.md` (rules, especially the results and "ask Stephanie" sections)
- `docs/EVALUATION.md` (what counts as a valid number)
- `src/promptci/providers/base.py`, `src/promptci/providers/ollama.py`
- `src/promptci/cache/disk.py`
- `src/promptci/suite/schema.py`
- `src/promptci/graders/exact.py`, `src/promptci/graders/json_schema.py`
- `src/promptci/runner/run.py`, `src/promptci/store/sqlite.py`, `src/promptci/cli.py`
- `examples/json_extract/suite.yaml`, `examples/gsm8k/suite.yaml`, `examples/gsm8k/README.md`
- `tests/test_runner_and_cli.py`

## Tasks

1. Confirm the skeleton on your machine: `pytest -q`, `ruff check .`, and the replay
   demo command from `docs/00_START_HERE.md`. Commit nothing yet; this is a check.

2. Pick your two models. Run `ollama list`, pull two instruction-tuned models of
   different sizes that fit your memory (suggested: `qwen2.5:7b` and `llama3.2:3b`;
   on 8 GB use `qwen2.5:3b` and `llama3.2:1b`). Time one request by hand. Write the
   choice and the reason into `configs/models.yaml`. Commit.

3. Smoke-test Ollama through PromptCI:
   `promptci run examples/json_extract/suite.yaml --model ollama/<model> --limit 3`.
   If it fails, fix `providers/ollama.py` (it was written against the documented API
   but never run against a live server). Add a test that uses a small fake HTTP
   response if you had to change how the response is parsed. Commit.

4. Write the 60 json_extract cases. Extend the inline `cases:` list or move to
   `cases.jsonl` (then set `dataset: cases.jsonl` and remove the ignore rule for that
   file in `.gitignore`, since these hand-written cases must be committed). Cover:
   prices with thousands separators and decimal commas, six or more currencies, stock
   status stated indirectly ("ships next quarter", "last one left"), distractor
   numbers (weights, model numbers, dimensions), two prices in one text (sale vs
   original), and at least 6 cases with a null price. Write every expected value by
   hand and check each one twice. Do this before you look at any model's output on
   them. Then run `promptci validate examples/json_extract/suite.yaml`. Commit.

5. Download GSM8K: `pip install "promptci[datasets]"` then
   `python examples/gsm8k/download.py --n 200 --seed 0`. Check that `cases.jsonl`
   has 200 lines and `case_ids.txt` is committed. Run `promptci validate` on the suite
   and read three rendered prompts. Commit `case_ids.txt`.

6. Run json_extract-60 on both models with `--concurrency 1` and a `--label`.
   Then run `promptci summarize <run_id> --md` for each and read the lowest-scoring
   cases. For each model, classify the failures by hand into: wrong value, missing
   field, invalid JSON, schema violation. Write the counts in `results/M1_json_extract_failures.md`.
   If a failure is caused by your expected value being wrong, fix the case, note it in
   the commit message, and re-run both models. Commit results (Markdown and the db).

7. Run GSM8K-200 on both models with `--concurrency 1`. This may take 20 to 60
   minutes per model on a laptop. Run it in a second terminal while you do task 8.
   When done, `summarize --md` each run into `results/`. Look at 10 failing outputs per
   model and count how many are "wrong number" versus "right number, no `####` line".
   Write those counts under the summary. Commit.

8. Add `promptci cache stats [--cache-dir]` (entries, total size, breakdown by
   provider and model) so you can see what the cache holds. Add a test. Commit.

9. Add a `--params` override to `promptci run` (for example
   `--params temperature=0.7,max_tokens=256`) so a suite can be run with different
   decoding settings without editing the YAML. The override must be part of the
   cache key (it already is, if you pass it through `suite.params`) and stored in the
   run's `params_json`. Add a test that two runs with different `--params` get
   different cache keys. Update README. Commit.

10. Build the M1 results table (see Report back) in `results/M1_summary.md` from the
    run ids, and add a short "Results so far" section to the README that links to it.
    Commit.

## Acceptance criteria

- `pytest -q` passes; `ruff check .` and `ruff format --check .` pass.
- `examples/json_extract/` has 60 cases; `promptci validate` reports 60.
- `examples/gsm8k/case_ids.txt` has 200 ids and is committed; `cases.jsonl` is not.
- `promptci runs` lists at least 4 finished runs: 2 models x 2 suites, each with
  `n_errors` at most 2 percent of cases.
- `results/M1_summary.md` exists with the table below, and every number in it can be
  reproduced with `promptci summarize <run_id>` against the committed `results/promptci.db`.
- `results/M1_json_extract_failures.md` exists with failure categories and counts.
- `promptci cache stats` works and has a test.
- `promptci run --params ...` works, is documented in README, and has a test.
- Every completion from the four runs is in `cache/ci/` (check with `cache stats`),
  and `promptci run examples/json_extract/suite.yaml --model replay/ollama/<model>`
  reproduces the json_extract summary with 100 percent cache hit rate.

## Report back

A table with 4 rows (2 models x 2 suites) and these columns: suite, model, n cases,
n errors, pass rate, mean score, mean latency ms, p95 latency ms, prompt tokens,
completion tokens, run id, git SHA. Plus: your hardware, the concurrency used, and
the two failure-category breakdowns. Every cell is `[measure this]` until you have
run it.

Also: one paragraph on which model you would deploy for json extraction and why,
using the numbers.

## Do not

- Do not type any number into a results file by hand. Export from `summarize --md`.
- Do not tune the prompt against the 60 json_extract cases or the 200 GSM8K cases.
  If you want to iterate on a prompt, do it on the 5 inline samples or a separate
  dev set.
- Do not change a grader to make more cases pass without writing down why the old
  behavior was wrong.
- Do not skip, delete, or xfail a failing test to get CI green.
- Do not add a dependency without a one-line reason in the commit message.
- Do not run a paid API. This milestone is Ollama only.
- Do not commit `cases.jsonl` for GSM8K (it is redistributed data; the ids are enough).

## Stephanie's own work

1. Write the 60 json_extract cases yourself. Claude can suggest categories, but you
   write the texts and the expected values. An interviewer who asks "how do you know
   your labels are right" should hear "I wrote and double-checked each one".
2. Do the failure classification by reading model outputs, not by asking Claude to
   summarize them. You will find at least one grader or dataset bug this way.
3. Write the deploy-decision paragraph in Report back yourself.
4. Read the Ollama `/api/generate` documentation and confirm that `prompt_eval_count`
   and `eval_count` are what the provider reads. Note any surprise (for example,
   whether a cached prompt prefix changes the reported count).
