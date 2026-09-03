# M4: LLM judges, position bias, and validation against human labels

## Goal

At the end of this milestone `llm_judge` and `pairwise_judge` work, pairwise judging
measures its own position bias by swapping the order, and you have measured how well
your judge agrees with human labels on two public datasets (MT-Bench human judgments
and SummEval), for a small local judge and, if you can get free access, a stronger one.
The finding is the gap between the two.

## Read first

- `src/promptci/graders/llm_judge.py` (the docstring is the design)
- `src/promptci/judge_validation/__init__.py`
- `examples/summarize_judge/suite.yaml`
- `docs/EVALUATION.md`, section "Judge validity"
- Zheng et al. 2023, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena",
  sections 3 (position bias, verbosity bias, self-enhancement bias) and 4.2
  (agreement with humans). Twenty minutes. Note their reported human-human agreement,
  so you know what ceiling to compare a judge against.
- Fabbri et al. 2021, "SummEval", section 4 for what the four dimensions mean.
- Wikipedia on Cohen's kappa is enough for the formula.

## Tasks

1. Implement `LLMJudgeGrader.agrade`. Build the judge prompt from the rubric, the
   case inputs, an optional reference, and the candidate output. Call the judge
   through the same `make_provider` and `CachedProvider` path as the candidate, so
   judge calls are cached. Parse `Score: N`; if parsing fails, score is None with
   `details["parse_error"]` and the runner records it as an error (do not default to
   3). Map to `(N - 1) / 4`. Wire the judge provider in `cli.py` (`make_grader(spec,
   judge=...)`). Tests with `FakeProvider` as judge: a reply of "Score: 5" gives 1.0,
   "Score: 1" gives 0.0, garbage gives an error. Remove the xfail. Commit.

2. Implement `PairwiseJudgeGrader.agrade`. The case inputs hold `question`,
   `answer_a`, `answer_b`. Ask the judge twice, once with A first and once with B
   first, using a prompt that asks for exactly `A`, `B`, or `tie`. Combine as in the
   docstring. Record both raw verdicts and `position_biased` in details. Tests with a
   FakeProvider whose reply depends on which answer is first. Commit.

3. Add `promptci judge-bias <run_id>` that reports, for a pairwise run, the fraction
   of cases where the two orderings disagreed, and which position won when they did
   (first or second). Commit.

4. Write the dataset loaders in `judge_validation/datasets.py`. Load
   `lmsys/mt_bench_human_judgments` with `datasets`; print the columns and the first
   row; map to the common record shape. Do the same for SummEval via `mteb/summeval`
   (fall back to the original GitHub release if the mirror's schema does not have the
   four human ratings). Both loaders take `n` and `seed` and return a reproducible
   subset. Check the column names yourself: they change between mirrors, and a loader
   that silently reads the wrong column produces a confident wrong number. Commit.

5. Implement `agreement.py`: `cohens_kappa`, quadratic `weighted_kappa`, `spearman`
   (scipy is under the `datasets` extra; write Spearman by hand if you prefer, it is
   rank then Pearson), and `position_bias_rate`. Test kappa against a textbook example
   and against perfect and chance agreement. Commit.

6. Implement `validate_pairwise(judge_model, n, seed)` and `validate_summeval(...)`,
   with a CLI `promptci validate-judge --dataset mtbench --judge ollama/<model> --n 200`.
   Both write a Markdown table to `results/judge_validation/`. Commit.

7. Run MT-Bench validation with your small local judge on n = 200 pairs. Report
   agreement with the human winner (ties included and excluded), kappa, and position
   bias rate. Then, if you have a free-tier key (Groq or OpenRouter), run the same 200
   pairs with a larger model. Ask the professor before using anything that costs money.
   Commit results.

8. Run SummEval validation with the same judge(s): Spearman per dimension on at least
   200 summaries. Use a rubric per dimension (four judge calls per summary). Commit
   results.

9. Run `examples/summarize_judge` on your primary candidate model with the small judge,
   and, if you have it, the strong judge. Compare the two score distributions. Extend
   the suite to at least 30 passages first (public news text or your own writing).
   Commit.

10. Write `docs/JUDGE_FINDINGS.md`: the agreement table, the position bias table, and
    three paragraphs: what the numbers say, what the human-human ceiling from the
    paper is, and whether you would trust the small judge for a CI gate (and at what
    threshold). Commit.

## Acceptance criteria

- `pytest -q` passes with no xfail for either judge grader; ruff clean.
- `promptci run examples/summarize_judge/suite.yaml --model ollama/<candidate>` runs
  with a judge different from the candidate and reports mean score and pass rate at
  the rubric threshold.
- `promptci judge-bias <run_id>` prints a position bias rate for a pairwise run.
- `promptci validate-judge --dataset mtbench --judge <model> --n 200` and
  `--dataset summeval` both run and write Markdown results.
- `results/judge_validation/` has at least two tables (MT-Bench and SummEval) for the
  small judge, and two more if a strong judge was available.
- `docs/JUDGE_FINDINGS.md` exists and every number in it links to a results file.
- The loaders print the columns they used, and the results file records the dataset
  revision or download date.

## Report back

1. MT-Bench: for each judge, n, agreement with humans (ties in / ties out), Cohen's
   kappa, position bias rate, and which position was favored. `[measure this]`.
2. SummEval: for each judge, Spearman per dimension with n. `[measure this]`.
3. The human-human agreement figure from the MT-Bench paper, cited with section.
4. The paragraph on whether the small judge is usable for a CI gate.
5. Judge cost: total judge tokens and wall time per 100 items, per judge.

## Do not

- Do not use the candidate model as its own judge in any reported number.
- Do not drop pairs where the judge output failed to parse; count them and report
  the parse failure rate.
- Do not report agreement on fewer than 100 items.
- Do not tune the rubric on the same items you report agreement on. Use 50 items to
  iterate, then freeze the rubric, then measure on a disjoint 200.
- Do not run a paid API without asking. Free tiers are fine; watch rate limits and
  let the runner's backoff handle 429s.
- Do not skip, delete, or xfail failing tests.

## Stephanie's own work

1. Read section 3 and 4.2 of the MT-Bench paper and write down (in NOTES.md) the
   human-human agreement number and the position bias rates they report, before you
   run anything. Your numbers should be compared to theirs.
2. Verify the dataset columns by opening the first three rows of each dataset
   yourself and checking that the label you use means what you think it means.
3. Write the rubrics for the four SummEval dimensions yourself, from the paper's
   definitions.
4. Write the "would you trust it for a CI gate" paragraph yourself.
