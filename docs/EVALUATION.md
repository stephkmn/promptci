# Evaluation protocol

This document defines what counts as a valid number in this project. If a number in a
report does not follow these rules, it is not a result, it is an anecdote.

## Metrics

Per case, a grader returns `score` in [0, 1] and, when the task has a clear right
answer, `passed` (true/false). The grader decides both; the runner and store never
modify them.

Per run, `promptci summarize` reports:

| metric | definition | notes |
|---|---|---|
| mean score | sum of scores / number of cases | errored cases count as 0 |
| pass rate | number passed / number of cases | only when the grader sets `passed`; errored cases count as not passed |
| mean latency, p95 latency | over cases that returned a completion | milliseconds, wall clock at the client; p95 is nearest-rank |
| prompt tokens, completion tokens | as reported by the provider | Ollama reports both; if a provider reports 0, say so |
| total cost | sum over cases of tokens times price from `prices.yaml` | $0 for local models; prices must be checked against the provider page and dated |
| cache hit rate | cached completions / cases | a 100 percent hit rate means a replay, and latency is the original run's |

Errored cases (provider failure after retries, grader exception) are recorded with
`error` set and are counted as failures in the mean. The error count is reported next
to the mean. Dropping them would inflate the score; a system that crashes on 5 percent
of inputs did not pass those inputs.

## Datasets

| suite | source | size used | why this size |
|---|---|---|---|
| json_extract | hand-written, in this repo | 60 | small enough to hand-verify every expected value; large enough that a 10-point difference is detectable (see power) |
| gsm8k | `openai/gsm8k` test split | 200, seeded sample, ids committed in `case_ids.txt` | the M2 experiment needs 200 vs 50; 200 gives a CI half-width around 0.05 for a pass rate near 0.7 |
| humaneval | `openai/openai_humaneval` | 164 (all) | small dataset, run it all |
| summarize_judge | hand-written passages, extend with a public summarization set | 5 shipped; 50+ for real use | judge scoring is expensive on a laptop |
| MT-Bench human judgments | `lmsys/mt_bench_human_judgments` | at least 200 pairs | for judge validation only, never for model scoring |
| SummEval | `mteb/summeval` or the original release | all 100 source docs x 16 systems if you can, else a seeded 200-summary subset | per-dimension human ratings |

Rules:

- The set of case ids used in any reported run is committed (inline in the suite or
  in `case_ids.txt`). Two runs are comparable only if they share the suite hash or you
  explicitly say which cases overlap.
- Never look at the test cases while writing the prompt beyond the five inline
  samples. If you tune the prompt against the cases you report on, the number is
  meaningless. For json_extract, write the 60 cases before you look at any model
  output on them, then freeze them.
- Never change a case's expected value to match a model output. If the expected value
  is wrong, fix it, note the fix in the commit message, and re-run every affected run.

## Statistical protocol for comparing two runs

Two runs A and B are compared on the cases they share, by case id. The quantity of
interest is the per-case delta `d_i = score_B(i) - score_A(i)`. Pairing matters:
some cases are hard for every model, and pairing removes that shared variance.

Report, always together:

1. n, the number of paired cases.
2. mean A, mean B, mean delta.
3. 95 percent bootstrap confidence interval of the mean delta (percentile method,
   10,000 resamples, seed recorded).
4. Two-sided paired permutation p-value (sign flips, 10,000 permutations, seed
   recorded).
5. For binary pass/fail graders, McNemar's exact test on the discordant pairs (M2).

Interpretation rules:

- Regression: CI upper bound < -threshold. Improvement: CI lower bound > +threshold.
  Anything else: "no detectable change at this sample size". That phrase is different
  from "no change", and you should use it exactly.
- The threshold is set per suite in `compare.regression_threshold`. The default
  0.02 means "we care about a 2 point drop in mean score". Justify the value you pick
  in the suite file comment. A stricter threshold needs more cases to be detectable.
- A p-value below 0.05 with a CI that includes -threshold is "significant but too
  small to matter at our threshold". Say that, do not round it to "better".
- Never report a comparison of two runs that used different case sets without
  saying how many cases overlapped.

## Power: how many cases do you need

Before running a comparison, ask what difference you want to detect. With per-case
delta standard deviation `sd` (for pass/fail deltas in {-1, 0, 1} it is usually
0.3 to 0.5), 80 percent power, and alpha 0.05, the cases needed to detect a mean
delta `d` is about `((1.96 + 0.84) * sd / d) ^ 2`. For `sd = 0.4` and `d = 0.05`
that is about 500 cases. For `d = 0.10` it is about 125. This is why a 50-case eval
can only reliably detect differences around 15 points, and why "model A got 71 percent
and model B got 73 percent on 50 cases" is noise. M2 implements this helper and
makes you run the experiment that shows it.

## Judge validity (M4)

An LLM judge's score is a measurement instrument, and instruments are calibrated.
Before any `llm_judge` or `pairwise_judge` number is reported, report the judge's
agreement with humans on a public labeled set:

- Pairwise (MT-Bench human judgments): agreement rate with the human winner, Cohen's
  kappa, and position bias rate (fraction of pairs where swapping A and B changed the
  verdict). Report both with ties included and excluded.
- Scored (SummEval): Spearman correlation between judge score and mean human rating,
  per dimension (coherence, consistency, fluency, relevance).

Report these for the small local judge you will actually use and for one stronger
model if you can get free-tier access. The gap between them is the finding.

The judge model must not be the model being evaluated. Self-grading is biased toward
the model's own style and the bias is not small.

## Latency and cost

- Latency is measured at the client, includes network time, and depends on the
  machine. Report the hardware (CPU or GPU, memory) next to any latency number for
  local models.
- Concurrency changes latency. Report the concurrency setting. For local Ollama,
  concurrency above 1 or 2 usually increases per-request latency because the model is
  shared; measure with `--concurrency 1` when latency is the point.
- Cost for local models is $0 in API terms. If you want to say something about local
  cost, report tokens per case and wall-clock time, not dollars.

## What a reported result looks like

```
GSM8K-200 (seed 0, case_ids.txt @ [git sha]), [model] via Ollama, temperature 0,
max_tokens 512, concurrency [N], [machine, memory].
Run [run_id]: pass rate [measure this] ([k]/200), [n] errors, mean latency [measure this] ms,
p95 [measure this] ms, prompt tokens [measure this], completion tokens [measure this], cost $0.
Command: promptci run examples/gsm8k/suite.yaml --model ollama/[model] --concurrency [N]
```

Every field in that block exists for a reason. Leave one out and someone will ask.
