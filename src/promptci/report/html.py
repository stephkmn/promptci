"""Self-contained HTML reports (M2). Not implemented yet.

Requirements when you build this:

- One HTML file, inline CSS, no JavaScript dependencies fetched from the network.
  It must open from a file:// URL with no build step.
- `run_report_html(run, summary, results)`: the same tables as the Markdown report
  plus a per-case table with the rendered prompt, output, expected, score and grader
  details in a collapsible block.
- `comparison_report_html(cmp, results_a, results_b)`: side-by-side per-case outputs,
  colored by delta, the worst regressions first, and the CI printed as a sentence a
  non-statistician can read: "B scored 0.03 lower on average; the 95% interval is
  [-0.07, +0.01], so this run cannot tell whether B is worse."
- Escape everything with `html.escape`. Model output is untrusted.
"""

from __future__ import annotations

from typing import Any


def run_report_html(*args: Any, **kwargs: Any) -> str:
    raise NotImplementedError("HTML run report is implemented in milestone M2")


def comparison_report_html(*args: Any, **kwargs: Any) -> str:
    raise NotImplementedError("HTML comparison report is implemented in milestone M2")
