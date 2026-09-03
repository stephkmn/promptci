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
