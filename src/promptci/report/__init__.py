"""Markdown and HTML reports.

`run_summary_markdown` works now and backs `promptci summarize`. The HTML report and
the comparison report are M2 work; see `promptci.report.html`.
"""

from promptci.report.markdown import comparison_markdown, run_summary_markdown

__all__ = ["comparison_markdown", "run_summary_markdown"]
