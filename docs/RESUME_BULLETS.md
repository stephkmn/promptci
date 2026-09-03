# Resume bullets

Templates in the style of your current resume: past tense, verb first, specific tech,
specific numbers. Every `[N]` is filled from a committed run in `results/`. Do not
fill a blank from memory; open the results file and copy the number.

Project title line for the resume:

**PromptCI, regression testing framework for LLM applications** (Python, Typer,
pydantic, SQLite, numpy, GitHub Actions) | github.com/[YOUR_GITHUB]/promptci | PyPI

## Bullets

1. Built an open-source evaluation framework (pytest for prompts) with a provider
   abstraction over Ollama, OpenAI-compatible, and Anthropic APIs, a content-addressed
   completion cache, and a SQLite result store recording tokens, latency, cost, and
   git SHA per case; evaluated [2] local models on GSM8K-200 and a 60-case
   hand-labeled extraction suite ([N] percent and [N] percent pass rate on GSM8K,
   p95 latency [N] s and [N] s).
   *Produced by M1. Numbers from `results/M1_summary.md`.*

2. Implemented paired statistical comparison of evaluation runs (seeded bootstrap 95
   percent CI, permutation test, exact McNemar, power analysis) and showed that a
   50-case eval of two prompt variants yielded a CI of [low, high] including zero while
   the 200-case eval gave [low, high], motivating a CI regression gate that fails only
   when the interval upper bound falls below a fixed threshold.
   *Produced by M2. Numbers from `results/M2_cot_50.md` and `results/M2_cot_200.md`.*

3. Validated LLM-as-judge grading against [N] MT-Bench human preference pairs and
   [N] SummEval summaries: a local [judge model] reached [N] percent agreement
   (kappa [N]) with a [N] percent position-bias rate versus [N] percent (kappa [N])
   for [stronger model]; documented when a small judge is and is not usable for a
   CI gate.
   *Produced by M4. Numbers from `results/judge_validation/`.*

4. Shipped a GitHub Actions regression gate that replays evaluation suites from a
   committed cache with zero API calls, posts a paired comparison table as a PR
   comment, and blocks merges on regression; published the package to PyPI with
   [N] tests and a sandboxed HumanEval code-execution grader (pass@1 [N] percent
   for [model], n = 164).
   *Produced by M3 and M5. Numbers from `results/M3_humaneval.md` and the repo.*

If you only complete M1 and M2, use bullets 1 and 2 and change the title line to drop
PyPI. Two strong bullets beat four with blanks.

## A bad example, and why the good one is better

Bad:

> Developed an AI evaluation tool using Python and LLMs to test prompts and compare
> model performance with a user-friendly CLI.

Everything in this sentence could be said about a 100-line script. "AI evaluation
tool" does not say what was measured. "Compare model performance" does not say how,
and the reader assumes "printed two percentages". "User-friendly" is an opinion. There
is no dataset, no number, no evidence anyone other than you ran it.

Bullet 2 above says which statistical methods (a reader who knows them knows you had
to get the pairing right), gives a concrete result with intervals (which shows you
understand what the intervals mean), and states the design decision that followed
(the gate rule). Each clause is checkable in the repo. That is what "engineering
judgment" looks like on a resume: a decision, the evidence for it, and the number.

## Talking about it in one sentence

If someone asks what the project is, in the elevator: "It is a test runner for LLM
prompts. You write cases in YAML, it runs them against any model, caches everything,
and when you compare two runs it gives you a confidence interval instead of two
percentages. The interesting part was checking whether the LLM judge agreed with
humans; it agreed [N] percent of the time, and swapping the order of the two answers
flipped its verdict [N] percent of the time."
