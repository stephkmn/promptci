# M5: CI regression gate, release, and write-up

## Goal

At the end of this milestone a pull request that degrades a suite's score fails a
GitHub check and gets a comparison table as a comment, with no API calls in CI. The
package is installable from PyPI, the README has badges and a demo GIF, and
`docs/WRITEUP.md` tells the M2 and M4 stories with the real numbers.

## Read first

- `.github/workflows/eval.yml` (works for the demo suite; the TODOs are yours)
- `.github/workflows/ci.yml`
- `src/promptci/providers/replay.py`
- `results/README.md`
- `docs/EVALUATION.md`
- The GitHub Actions docs page on `pull-requests: write` permissions and on
  `actions/github-script`.
- The Python Packaging User Guide page "Packaging Python Projects" (the TestPyPI
  section) and the PyPI page on trusted publishing.

## Tasks

1. Record a CI baseline with a real model. Run json_extract-60 and GSM8K-200 (or a
   50-case GSM8K subset if the cache is too large) with your primary Ollama model so
   every completion is in `cache/ci/`. Check `cache/ci` size with `promptci cache
   stats`; if it is over 20 MB, switch GSM8K CI to `--limit 50` and document why.
   Commit the cache.

2. Generalize `eval.yml`: a matrix over the suites that have committed cache
   (json_extract, gsm8k), each using `replay/ollama/<model>` from
   `configs/models.yaml`. The baseline run uses main's suite file, the candidate uses
   the PR's, both against the PR's cache (the PR must include any new cache entries).
   One combined PR comment, updated in place. Upload the HTML comparison reports as a
   workflow artifact. Commit.

3. Prove the gate works with three pull requests, each from a branch:
   - PR A: change a comment in the suite. Expect: no detectable change, check passes.
   - PR B: change the prompt so that the replay misses. Expect: the run errors with
     `CacheMissError` and the check fails with a message saying to re-record. Then
     re-record locally with Ollama, commit the new cache to the branch, and watch the
     comparison run for real.
   - PR C: deliberately weaken the prompt (remove the field list from json_extract)
     and re-record. Expect: regression verdict, check fails, comment shows the worst
     regressions.
   Merge A and the fixed B; close C without merging. Link all three in the README
   under "CI in action". Commit.

4. Add `promptci ci-comment <compare.md>` (or equivalent) that trims the comparison
   to what fits in a PR comment, or confirm the current Markdown is under GitHub's
   comment size limit for a 200-case worst-regressions table. Commit.

5. README polish: badges for CI status, eval status, PyPI version, Python versions,
   license. A "Results" section with the M1 table, the M2 50-vs-200 comparison, and
   the M4 agreement table, each linking to the file in `results/`. Commit.

6. Demo GIF: record a 2-minute terminal session (`asciinema` or a screen recorder,
   then convert to GIF with `agg` or similar) showing `promptci run` on Ollama for
   5 cases, `summarize`, `compare` with a regression, and the HTML report opening.
   Keep it under 5 MB. Put it in `docs/demo.gif` and embed it at the top of the
   README. Commit.

7. Release. Bump the version to 0.1.0 in `pyproject.toml` and `__init__.py`, add a
   `CHANGELOG.md`, build with `python -m build`, check with `twine check dist/*`, and
   upload to TestPyPI. In a fresh venv, `pip install -i https://test.pypi.org/simple/
   --extra-index-url https://pypi.org/simple promptci` and run the demo command. If
   it works, upload to PyPI, tag `v0.1.0`, and create a GitHub release. Set up
   trusted publishing with a `release.yml` workflow on tag push so the next release
   needs no token. Commit.

8. Write `docs/WRITEUP.md`, about 800 to 1200 words, blog style, for a reader who
   builds with LLMs but has not thought about eval statistics. Structure: the
   problem (two numbers, which is better), the 50 vs 200 experiment with the actual
   intervals, what a regression gate should therefore check, then the judge
   validation numbers and what they mean for anyone using an LLM judge in CI. End
   with what you would do next. Every number links to `results/`. Commit.

9. Ask two people to install from PyPI and run the demo following only the README.
   Fix whatever they hit. Commit.

## Acceptance criteria

- The three demonstration PRs exist on GitHub with the expected check outcomes, and
  the README links them.
- `eval.yml` runs with no network access to any model provider (verify: the job's
  log shows 100 percent cache hit rate for each suite).
- `pip install promptci` in a fresh venv works and `promptci run
  examples/json_extract/suite.yaml --model replay/any` works from a clone.
- `docs/demo.gif` exists, under 5 MB, embedded in README.
- `docs/WRITEUP.md` exists; every number in it appears in a file under `results/`.
- README badges render (CI, eval, PyPI, Python, license).
- A `v0.1.0` tag and GitHub release exist.

## Report back

The URLs of the repo, the three PRs, the PyPI page, and the write-up. The size of
`cache/ci/`. The wall time of the eval workflow. The names of the two people who
tested the install and what they hit.

## Do not

- Do not put an API key in a GitHub secret for the eval workflow. The whole point is
  that CI needs none. (A token for PyPI publishing is different and should use trusted
  publishing anyway.)
- Do not let the eval workflow pass on a cache miss. A miss is a failure.
- Do not force-push over the demonstration PRs after they have run; the history is
  the evidence.
- Do not report a write-up number that is not in `results/`.
- Do not upload to PyPI before TestPyPI works in a fresh venv.
- Do not skip, delete, or xfail failing tests.

## Stephanie's own work

1. Write `docs/WRITEUP.md` yourself. Claude may check it for errors and clarity, but
   the sentences are yours. This is the document you will link in applications.
2. Do the PyPI release steps yourself, including the trusted publishing setup, so you
   can describe the process.
3. Record the demo GIF yourself.
4. Review `eval.yml` line by line and be able to explain what each step does and what
   happens when it fails.
