# M2: Compare two runs with statistics you can defend

## Goal

At the end of this milestone `promptci compare A B` reports a paired bootstrap CI,
permutation p-value, McNemar test, and a regression verdict, plus a self-contained HTML
report. You will have run one experiment that shows why evaluation size matters: the
same two prompts compared on 50 cases and on 200 cases, with the 50-case interval
including zero and the 200-case interval (possibly) not.

## Read first

- `docs/EVALUATION.md`, sections "Statistical protocol" and "Power"
- `src/promptci/stats/compare.py` (bootstrap and permutation are done; McNemar, power
  and the store-aware wrapper are stubs with docstrings)
- `tests/test_stats.py`
- `src/promptci/report/markdown.py`, `src/promptci/report/html.py`
- `src/promptci/cli.py`, the `compare` command
- The section "Bootstrap Confidence Intervals" in any intro stats text, or Efron and
  Tibshirani, "An Introduction to the Bootstrap", chapter 13 (percentile method).
  Twenty minutes, not a semester.

## Tasks

1. Implement `mcnemar_test` in `stats/compare.py`. Use the exact binomial test on the
   discordant pairs: with `b` = A-only passes and `c` = B-only passes, the p-value is
   the two-sided binomial probability of seeing something at least as extreme as
   `min(b, c)` out of `b + c` with p = 0.5. Return counts too. Replace the xfail test
   with real tests: (10, 10) discordant gives p = 1; (0, 12) gives p < 0.001; no
   discordant pairs gives p = 1. Commit.

2. Implement `power_cases_needed(sd_delta, d, power=0.8, alpha=0.05)` using the
   normal approximation in the docstring. Test against a hand-computed value: with
   sd 0.4 and d 0.1 expect about 125 (accept 120 to 130). Add
   `promptci power --sd 0.4 --delta 0.05` that prints the answer and a sentence.
   Commit.

3. Implement `compare_runs(store, run_a, run_b, threshold)` that pulls both runs,
   aligns cases by id, reports how many were dropped from each side, uses
   `passed` for McNemar when both runs have it, and returns `ComparisonResult` with
   `mcnemar` filled in. Wire the CLI `compare` command to it. Add the observed
   `sd_delta` and the `power_cases_needed` value for the suite's threshold to the
   Markdown output, so every comparison says how many cases it would have needed.
   Commit.

4. Build the HTML reports in `report/html.py` following the requirements in its
   docstring. Add `promptci report <run_id> --html out.html` and
   `promptci compare A B --html out.html`. Test: the file is produced, contains every
   case id, and contains no unescaped `<script` from a model output that includes
   one (write a case whose fake output is `<script>alert(1)</script>`). Commit.

5. Prepare the experiment. Copy `examples/gsm8k/suite.yaml` to
   `examples/gsm8k/suite_cot.yaml` and change only the prompt: add "Think step by
   step before giving the final answer." Keep `dataset`, params, and grader the same
   so the case ids match. Commit.

6. Run the experiment on your primary model, `--concurrency 1`:
   - `suite.yaml` on all 200 (you already have this run from M1; reuse the run id)
   - `suite_cot.yaml` on all 200
   Then `promptci compare <plain_200> <cot_200> --html results/M2_cot_200.html`.
   Then compare the first 50 only: run both suites with `--limit 50` (these hit the
   cache and take seconds) and compare those two run ids.
   Save both Markdown outputs to `results/M2_cot_50.md` and `results/M2_cot_200.md`.
   Commit.

7. Do the same for json_extract-60 with a prompt variant of your choice (for
   example, adding one worked example to the prompt). Compare at 60 and at 20.
   Commit results.

8. Update `eval.yml` if the `compare` output format changed. Update README's
   "Comparing runs" section with real output from task 6 (the actual table, with run
   ids). Commit.

## Acceptance criteria

- `pytest -q` passes with no xfail left in `tests/test_stats.py`; ruff clean.
- `promptci compare A B` prints: n paired, means, mean delta, 95 percent CI with
  resamples and seed, permutation p, McNemar counts and p (when applicable), observed
  sd of deltas, cases needed at the threshold, verdict.
- `promptci compare A B --fail-on-regression` exits 3 on a regression and 0 otherwise;
  test with two fake runs.
- `promptci report <run_id> --html` and `compare --html` produce files that open in a
  browser with no network access.
- `results/M2_cot_50.md` and `results/M2_cot_200.md` exist, come from committed runs,
  and the 50-case CI is wider than the 200-case CI.
- `promptci power --sd 0.4 --delta 0.05` prints a number near 500.

## Report back

1. The 50-case and 200-case comparison tables side by side, for GSM8K plain vs CoT.
   Columns: n, mean A, mean B, delta, CI low, CI high, permutation p, McNemar p,
   verdict. All values `[measure this]`.
2. One paragraph: did the 50-case comparison reach the same verdict as the 200-case
   one? If the 200-case CI still includes zero, say so, and report how many cases the
   power helper says you would need for the observed delta.
3. The json_extract variant comparison, same format.
4. Latency and completion-token cost of CoT versus plain (CoT writes more tokens; how
   much more, and what did it buy).

## Do not

- Do not pick the 50 cases after seeing results. `--limit 50` takes the first 50 by
  file order, which was fixed before any run.
- Do not run more than the two prompt variants per suite and report the best pair.
  If you try a third variant, report all three.
- Do not describe a CI that includes zero as "no difference". Use "no detectable
  change at n = 50".
- Do not change `regression_threshold` after seeing the comparison.
- Do not implement McNemar with the chi-square approximation; discordant counts here
  are small.
- Do not skip, delete, or xfail failing tests. Do not add dependencies (scipy is
  allowed under the `datasets` extra only, not core).

## Stephanie's own work

1. Derive the power formula on paper from the two-sided z-test and check it against
   the code. Be able to explain where 1.96 and 0.84 come from.
2. Pick the `regression_threshold` for each shipped suite and write a two-sentence
   justification in each suite file, before running the comparisons.
3. Write the Report back paragraph 2 yourself. This is the paragraph you will say
   out loud in interviews.
4. Review the HTML report in a browser and fix at least one thing about it that you
   find confusing, without asking Claude first what is wrong with it.
