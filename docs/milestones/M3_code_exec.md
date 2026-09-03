# M3: Code execution grader and HumanEval pass@1

## Goal

At the end of this milestone the `code_exec` grader runs model-written Python against
HumanEval's test functions in a subprocess with a timeout and resource limits, and you
have a HumanEval pass@1 number for at least one local model, with the unbiased pass@k
estimator implemented for k > 1.

## Read first

- `src/promptci/graders/code_exec.py` (the docstring is the design)
- `examples/humaneval/suite.yaml`, `examples/humaneval/download.py`
- Chen et al. 2021, "Evaluating Large Language Models Trained on Code", section 2.1
  (the pass@k estimator and why the naive one is biased) and appendix on the
  execution sandbox. Ten minutes.
- Python docs for `subprocess.run` (`timeout`, `env`, `cwd`) and `resource.setrlimit`
  (`RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NOFILE`, `RLIMIT_FSIZE`).

## Tasks

1. Implement `CodeExecGrader.agrade`. Assemble the program from
   `case.inputs["prompt"]`, the model output, `case.inputs["test"]`, and
   `check(<entry_point>)`. Write it to a fresh `tempfile.TemporaryDirectory`, run
   `sys.executable -I <file>` with `cwd` set to that directory, `env={}` plus a
   minimal `PATH`, and `timeout=timeout_s`. Use `asyncio.to_thread` so the runner's
   concurrency still applies. Score 1.0 on exit code 0, else 0.0. `details` carries
   `reason` (ok, timeout, nonzero_exit, exception), truncated stdout and stderr, and
   the wall time. Commit.

2. Add resource limits via `preexec_fn` on Linux and macOS (`RLIMIT_CPU` = timeout + 1,
   `RLIMIT_AS` = memory_mb, `RLIMIT_FSIZE` small, `RLIMIT_NOFILE` small). Skip them on
   Windows with a warning. On Linux, if `unshare` is on PATH, run under
   `unshare -n` to remove network; detect and record in `details["network_blocked"]`
   whether that happened. Commit.

3. Strip markdown fences and a leading repeated function signature from the model
   output before assembling (models often echo the `def` line). Make this a documented
   `clean_completion` option, default on, and record in details whether it fired.
   Commit.

4. Tests, all using hand-written candidate code, no model:
   - a correct solution to `HumanEval_0` scores 1
   - an incorrect solution scores 0 with `reason == "nonzero_exit"`
   - `while True: pass` scores 0 with `reason == "timeout"` and finishes within
     `timeout_s + 2` seconds
   - a solution that allocates 2 GB scores 0 (skip on Windows)
   - a solution that tries `open("/etc/hostname")` outside the temp dir: document
     whether it succeeds; it will, because this is not a sandbox, and the test should
     assert the documented behavior, not a wish
   - a solution that writes a file: the file is gone after grading
   Remove the xfail. Commit.

5. Add sampling support: `promptci run --samples k` calls the model k times per case
   with `seed` varied 0..k-1 (part of the cache key, so each sample is cached), stores
   `sample_idx` in results (schema migration: add the column with a default of 0, and
   a test that an old database still opens), and `summarize` reports pass@1 with the
   unbiased estimator from the paper: `1 - C(n - c, k) / C(n, k)` averaged over cases,
   where `n` is samples per case and `c` the number that passed. With k = 1 this
   equals the plain pass rate; test that. Commit.

6. Download HumanEval (`python examples/humaneval/download.py`), run it on your
   primary model at temperature 0 with `--concurrency 1`, and then at temperature 0.8
   with `--samples 5` if your machine can afford 820 completions (it may take a few
   hours; leave it overnight). Summarize into `results/M3_humaneval.md`. Read 10
   failures and classify: wrong logic, syntax error, echoed signature, timeout,
   import of an unavailable module. Commit.

7. Write a "Not a sandbox" section in README stating exactly what the grader does
   and does not protect against, with the test from task 4 as evidence. Commit.

## Acceptance criteria

- `pytest -q` passes with no xfail for code_exec; ruff clean.
- `promptci run examples/humaneval/suite.yaml --model ollama/<model> --limit 5` runs
  and grades.
- An infinite loop case finishes within `timeout_s + 2` seconds (timed in a test).
- `results/M3_humaneval.md` reports pass@1 for at least one model with n = 164, the
  error count, mean latency, and the failure classification. If you ran k = 5, it
  also reports pass@1 from the unbiased estimator and the naive "any sample passed"
  rate next to it, so the difference is visible.
- README has the "Not a sandbox" section.

## Report back

pass@1 for each model and temperature you ran, n = 164, with error count and mean
latency; the failure classification counts; whether `unshare -n` was available on
your machine; and one sentence on how far your number is from the model card's
reported HumanEval score and the two most likely reasons for the gap (prompt format
and completion cleaning are the usual ones). All numbers `[measure this]`.

## Do not

- Do not run model-generated code outside the subprocess, ever, including "just to
  see why it failed". Copy it into the subprocess harness.
- Do not claim the grader is a sandbox anywhere.
- Do not silently retry a timeout with a longer limit. Timeouts are failures.
- Do not use the naive `any(sample passed)` as pass@1 when k > 1.
- Do not add a container dependency (Docker) to the core path. It can be an optional
  later improvement; document it as such.
- Do not skip, delete, or xfail failing tests.

## Stephanie's own work

1. Work through the pass@k estimator derivation in the paper until you can explain
   why the naive estimator is biased upward, and check the implementation against a
   hand-computed example (n = 5, c = 2, k = 1 and k = 3).
2. Write the "Not a sandbox" README section yourself.
3. Read 10 HumanEval failures and do the classification.
4. Decide the default `timeout_s` and `memory_mb` from what you observed, and write
   why in the grader docstring.
