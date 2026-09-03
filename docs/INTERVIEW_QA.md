# Interview questions about PromptCI

Questions an interviewer is likely to ask, with notes on what a good answer covers.
The notes are not scripts. Fill them with your own numbers and your own decisions.
If you did not make a decision yourself, say so and explain what you would decide now.

## 1. Walk me through what happens when I run `promptci run suite.yaml --model ollama/qwen2.5:7b`.

Good answer covers: YAML parsed and validated with pydantic; Jinja2 prompt rendered per
case; the provider built from the `provider/model` string and wrapped in the cache;
cache key is sha256 of (provider, model, params, prompt); async tasks under a
semaphore; retries with backoff on provider errors; grading; one row per case in
SQLite with tokens, latency, cost, and the run row with suite hash and git SHA;
summary computed on read. Bonus: why the summary is computed at read time (a bug fix in
the summary never requires re-running).

## 2. Why cache completions? What are the risks?

Cost and reproducibility: the same request is never paid for twice, and CI can replay
a run with no keys. Risks: at temperature > 0 the cache freezes one sample and hides
variance; a stale cache can mask a provider change; the key must include every
parameter that affects output. Mention that `ReplayProvider` fails on a miss on
purpose, and what that failure means (someone changed the prompt without re-recording).

## 3. Model A scored 71 percent and model B scored 73 percent on 50 cases. Which is better?

The answer is "cannot tell". Explain paired deltas, the bootstrap CI on the mean
delta, and what the interval looked like in your M2 experiment at n = 50 versus 200.
Give the power number: how many cases to detect a 2-point difference with pass/fail
scores. Say "no detectable change at this sample size", and explain why that is not
the same as "no change".

## 4. Why bootstrap instead of a t-test?

Both would often agree. Bootstrap needs no normality assumption, handles scores that
are 0/1 or bounded in [0, 1], and is easy to explain and to seed. Know its assumption:
cases are independent draws from the population you care about. Know its weakness:
percentile intervals can be off for very skewed deltas or tiny n. Mention the
permutation test as the exact-under-the-null companion, and McNemar for pass/fail.

## 5. What is your regression rule and why that rule?

"Regression if the CI upper bound is below minus the threshold." Explain the two
alternatives you rejected: "mean went down" (fires on noise constantly) and "p < 0.05"
(fires on tiny real differences nobody cares about). Explain how you picked the
threshold for each suite and what would change it. If you have the PR C demo from M5,
describe it.

## 6. How do you know your LLM judge is any good?

Agreement with human labels on MT-Bench and SummEval, the numbers, the human-human
ceiling from the paper, and the position bias rate you measured by swapping order.
Then the decision: is the small judge usable for a gate, and at what threshold. If
you found the judge favored the first position, say by how much and what you did
about it (both orderings, disagreement counted as a tie).

## 7. Why should the judge be a different model from the one being evaluated?

Self-enhancement bias (the MT-Bench paper measured it). A model prefers its own
phrasing. Also practical: if you are comparing two candidates, a judge that is one of
them is not neutral. Mention that your validation would catch it: run the judge
against human labels on outputs from itself and from another model and compare.

## 8. Your code_exec grader runs model-written Python. How is that safe?

It is not a sandbox and you should say so before they do. It is a subprocess with a
timeout, resource limits (CPU, memory, file size, open files), a temp directory, an
empty environment, and network removed via `unshare` when available. It protects
against accidents (infinite loops, memory bombs), not against a hostile model. What
would make it safe: a container or a microVM (gVisor, Firecracker), and why you did
not add one (dependency weight for a portfolio project; documented as future work).

## 9. What is pass@k and why not just count "any sample passed"?

The unbiased estimator from the Codex paper: `1 - C(n-c, k) / C(n, k)`, averaged over
problems. "Any of n samples passed" estimates pass@n, not pass@k for k < n, and it is
biased upward. Do the n = 5, c = 2, k = 1 example out loud: the naive rate gives 1,
the estimator gives 0.4.

## 10. How does CI run evals without an API key?

`ReplayProvider` serves only from the committed cache and errors on a miss. The
workflow runs main's suite and the PR's suite against the same cache, compares, posts
a comment, and fails on regression. Explain what a PR author must do when they change
a prompt (re-record locally, commit the cache), and why a miss failing the build is
the right default.

## 11. What did you get wrong the first time?

Have two real examples from NOTES.md. Typical ones from this project: a grader that
accepted a wrong answer because normalization was too aggressive; an expected value
you wrote incorrectly and found during failure review; latency numbers that changed
with concurrency; the Ollama provider not matching the documented response on first
run. Interviewers ask this to see if you review your own work.

## 12. How would you scale this to 10,000 cases or 20 models?

Concurrency is already a semaphore; the store is SQLite and would move to Postgres or
DuckDB; the cache would move to object storage keyed the same way; runs would shard
by case id. The stats already scale (bootstrap is vectorized in numpy). The real
bottleneck is the model, so talk about batching endpoints and cost. Show you know
which parts are the framework's problem and which are the provider's.

## 13. Where do the cost numbers come from and can I trust them?

A prices table in the repo with a checked date per row, tokens as reported by the
provider, zero for local models. Say plainly that token counts from Ollama depend on
the model's tokenizer and that API providers' counts are authoritative for billing.
Mention that you do not report dollars for local models, only tokens and wall time.

## 14. What would you do with two more weeks?

Pick from: a proper sandbox; more graders (embedding similarity with a threshold you
validate); per-tag breakdowns so a regression on one category is visible; a
`promptci bisect` over prompt versions; multiple judges with majority vote and its
effect on agreement; a Postgres store. Pick two and say why those.

## 15. Why did you build this instead of using an existing eval framework?

Honest answer: to learn what those frameworks hide, and to have a thing you can
explain to the last line. Know two or three existing tools (promptfoo, Inspect,
lm-evaluation-harness, DeepEval) and one specific thing each does differently from
yours, so this does not sound like you did not look. What yours does that is uncommon
at small scale: paired bootstrap CIs and a regression rule in CI, judge validation
built in, replay-from-cache CI with no keys.
