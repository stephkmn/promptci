# GSM8K grader change: `exact` -> `numeric_tolerance`

## Why

`ExactGrader` compares strings. On `gsm8k_test_0258` qwen2.5:7b answered `#### 6.00`
against an expected value of `6`. The `####` extraction matched and the arithmetic was
right, but `"6.00" != "6"`, so the case scored 0. That is a formatting difference being
reported as a wrong answer.

The suite now uses `numeric_tolerance`, which parses both sides as floats and compares
with `abs_tol=1e-6`.

## The part that needed a decision

`numeric_tolerance` falls back to scanning the whole output for the last number when its
`extract` pattern does not match. A plain swap would therefore also have passed every
case where the model never wrote `#### N` at all — 11 llama3.2:3b cases, whose outputs are
prose that ignores the requested format. That would have moved llama's pass rate by
roughly 5 points and halved the measured qwen-minus-llama gap, none of it from better
arithmetic.

The suite's stated contract is that ignoring the output format is a failure, so a
`require_extract_match: true` option was added to the grader and enabled here. A missing
`####` still fails. The only cases that change are ones where the format was followed and
the value was right.

## Commands

```
promptci run examples/gsm8k/suite.yaml -m replay/ollama/qwen2.5:7b \
  --cache-dir cache/local --label regrade-numeric-tolerance      # run c32af276cb40
promptci run examples/gsm8k/suite.yaml -m replay/ollama/llama3.2:3b \
  --cache-dir cache/local --label regrade-numeric-tolerance      # run 443655ebfd66
promptci compare d67e924ecc74 c32af276cb40
promptci compare ba27755a7098 443655ebfd66
```

Both new runs are 100% cache hits against `cache/local`, served by `ReplayProvider`, which
errors on a miss rather than calling a model. They are replays of the original runs
(`d67e924ecc74`, `ba27755a7098`): the outputs and the latency and token numbers are the
originals', and only the grading is new. No model was called and nothing was spent.

The original `exact`-graded runs are kept: `M1_gsm8k_qwen2.5:7b.md`,
`M1_gsm8k_llama3.2:3b.md`.

## qwen2.5:7b, exact (A) vs numeric_tolerance (B)

### Compare `d67e924ecc74` (A) vs `c32af276cb40` (B)

Verdict: **no detectable change** (threshold 0.030, 205 paired cases)

| Metric | Value |
|---|---|
| Mean A | 0.776 |
| Mean B | 0.780 |
| Mean delta (B - A) | +0.005 |
| 95% bootstrap CI | [+0.000, +0.015] (10000 resamples, seed 0) |
| Permutation p-value | 1.0000 |

One case changed: `gsm8k_test_0258`, `#### 6.00` vs expected `6`. The CI includes zero and
the verdict is no detectable change, which is the honest reading — this is a single-case
grading fix, not a measurable difference in model quality.

## llama3.2:3b, exact (A) vs numeric_tolerance (B)

### Compare `ba27755a7098` (A) vs `443655ebfd66` (B)

Verdict: **no detectable change** (threshold 0.030, 205 paired cases)

| Metric | Value |
|---|---|
| Mean A | 0.693 |
| Mean B | 0.693 |
| Mean delta (B - A) | +0.000 |
| 95% bootstrap CI | [+0.000, +0.000] (10000 resamples, seed 0) |
| Permutation p-value | 1.0000 |

No case changed. llama3.2:3b never produced a decimal form of an integer after a `####`,
and `require_extract_match` keeps its 11 unformatted outputs failing as they did before.
