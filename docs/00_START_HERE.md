# Start here

This file tells you what to do on day one and how to work through the milestones.
Read it once, all the way through, before you open a terminal.

## What you are building

PromptCI is a small framework that answers the question "did this prompt or model
change make things better, and how sure are we". It runs an evaluation suite against
a model, stores every result, compares two runs with a confidence interval, checks
that the LLM judge agrees with humans, and fails a pull request when quality drops.

The skeleton already works. Providers, cache, suite loading, four graders, the
database, the runner, and the `run`, `summarize`, and `compare` commands are
implemented and tested. Your job over the next weeks is to make it measure real
models on real data, add the statistics that make a comparison trustworthy, and
publish it. Each milestone in `docs/milestones/` is a self-contained task prompt.

## Day one, in order

1. Install Python 3.11 or newer and Ollama (https://ollama.com). Run `ollama serve` in
   one terminal and `ollama pull qwen2.5:7b` and `ollama pull llama3.2:3b` in another.
   If your laptop has 8 GB of memory, use `qwen2.5:3b` instead of `7b`. Run
   `ollama run qwen2.5:7b "say hi"` to confirm it works. If it takes more than 20
   seconds to answer, pick a smaller model. Record what you chose in
   `configs/models.yaml`.

2. Create a public GitHub repository named `promptci` today, before you write any
   code. Copy this project into it and make the first commit. The commit history is
   part of what interviewers look at: a repo with 40 small commits over three weeks
   reads as real work, a single "initial commit" with everything in it does not.
   Commit after every task in a milestone, not after every milestone.

3. Set up the environment and confirm the skeleton works:

   ```bash
   cd promptci
   python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   pytest -q                    # expect: 56 passed, 5 xfailed (the xfails are planned work)
   ruff check .
   promptci run examples/json_extract/suite.yaml --model replay/any
   ```

   The last command prints a summary table in under a second. It is replaying cached
   replies from a fake provider, so the numbers say nothing about any model. It proves
   the pipeline works end to end. Run `promptci summarize <run_id>` with the id it
   printed, and `promptci runs`.

4. Run one real model on the demo suite:

   ```bash
   promptci run examples/json_extract/suite.yaml --model ollama/qwen2.5:7b
   ```

   Read the output. Then run `promptci summarize <run_id> --md` and look at the
   lowest-scoring cases table. Open `examples/json_extract/suite.yaml` and find the
   case the model got wrong. This is the loop you will live in.

5. Read `CLAUDE.md`, `docs/EVALUATION.md`, and `docs/milestones/M1_core_runner.md`.
   Then start M1.

## How to work with Claude on this

You have two tools. Use whichever fits the moment; both read the same files.

In Cowork (desktop): add the `promptci` folder to the workspace. Open
`docs/00_START_HERE.md` so you have it in view. Then tell Claude:

> Read CLAUDE.md and docs/milestones/M1_core_runner.md and start M1. Work through the
> tasks in order and stop after each one so I can review and commit.

In Claude Code (terminal): `cd promptci`, run `claude`, and give the same instruction.
Claude Code reads `CLAUDE.md` automatically when it starts in the repo.

Some habits that make the difference between a project you can defend and one you
cannot:

- Read every diff before you commit it. If you do not understand a line, ask Claude
  to explain it, and if the explanation does not convince you, ask it to simplify.
  In an interview you will be asked about a specific line.
- The `Stephanie's own work` section in each milestone lists things you do yourself.
  They are chosen because they are the parts an interviewer will probe.
- When Claude proposes a number, ask where it came from. `CLAUDE.md` forbids invented
  numbers, but you are the last check.
- Keep a `NOTES.md` in the repo root (or a private file, your choice) with one dated
  paragraph per session: what you tried, what surprised you, what you would do
  differently. The M5 write-up comes from these notes.

## Order of work and rough time

| Milestone | What you have at the end | Time (part-time) |
|---|---|---|
| M1 core runner | Two local models measured on GSM8K-200 and json_extract-60, a results table | 5 to 7 days |
| M2 compare and stats | `compare` with CI, p-value, McNemar, power; the 50-vs-200 experiment | 4 to 6 days |
| M3 code exec | HumanEval pass@1 on a local model | 3 to 4 days |
| M4 judge validation | Judge agreement with humans on two public datasets | 5 to 7 days |
| M5 CI and release | Regression gate on PRs, package on PyPI, write-up | 3 to 4 days |

M1 and M2 together produce the first resume bullet. Do them before anything else.
M3 to M5 are stretch; each one adds a bullet or strengthens one.

## When something breaks

- `pytest` fails on a fresh clone: check `python --version` (3.11+) and that you
  installed with `pip install -e ".[dev]"`, not plain `pip install .`.
- `promptci run ... --model ollama/...` errors with "Is 'ollama serve' running?":
  start Ollama. If it runs but every case errors with a timeout, the model is too
  large for your machine; pick a smaller one.
- `replay/...` errors with `CacheMissError`: the prompt or params changed since the
  cache was recorded. That is the intended behavior. Re-record with the real model
  and commit the new cache files.
- A test you did not touch starts failing: do not mark it xfail. Find out why.
