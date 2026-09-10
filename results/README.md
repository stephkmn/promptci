# results/

`promptci.db` is the SQLite store every `promptci run` writes to by default.

Rules (also in CLAUDE.md):

- Every number that appears in the README, a milestone report, or a resume bullet must
  come from a run whose row is in this database, with its `git_sha`, `suite_hash`, and
  `started_at`.
- When a milestone is done, export the runs that back its reported numbers to a
  Markdown file in this directory (`promptci summarize <run_id> --md > results/M1_gsm8k_qwen.md`)
  and commit both the Markdown and the database.
- Never edit the database by hand. If a run was wrong, run it again and reference the
  new run id.

## GSM8K runs

`gsm8k` was originally graded with `exact` (runs `d67e924ecc74` qwen2.5:7b and
`ba27755a7098` llama3.2:3b, exported as `M1_gsm8k_*.md`). That grader compares strings,
so it scored `#### 6.00` as wrong against expected `6`. The suite now uses
`numeric_tolerance` with `require_extract_match: true`; the regraded replays are
`c32af276cb40` and `443655ebfd66`, exported as `M1_gsm8k_*_numeric.md`.
`M1_gsm8k_grader_change.md` has the reasoning and both before/after comparisons. The
original runs are kept, not replaced — they are what `exact` measured.
