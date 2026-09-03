"""Judge validation against human labels (M4). Not implemented yet.

The question this package answers: when the LLM judge says an answer is good, do
humans agree? Without this number, an llm_judge score is a number with no units.

Planned modules:

`datasets.py`
    Loaders that return a common record shape regardless of source:
    ``{"id", "question", "answer_a", "answer_b", "human_winner"}`` for pairwise data
    and ``{"id", "source", "summary", "human_scores": {dim: float}}`` for rated data.
    Sources: ``lmsys/mt_bench_human_judgments`` (pairwise) and SummEval (per-dimension
    ratings: coherence, consistency, fluency, relevance) via the ``mteb/summeval``
    mirror or the original GitHub release. Both are loaded with the `datasets` library
    (``pip install "promptci[datasets]"``). Column names on the Hub change; the loader
    should print the columns it found and fail with a clear message if a required one
    is missing. Verify the columns yourself before trusting any agreement number.

`agreement.py`
    `cohens_kappa(labels_a, labels_b)` for nominal labels, `weighted_kappa` (quadratic)
    for ordinal 1-5 scores, `spearman(x, y)` for continuous scores, and
    `position_bias_rate(verdicts_ab, verdicts_ba)` for pairwise judges. scipy has
    Spearman; kappa is 15 lines and worth writing yourself so you can explain it.

`run.py`
    `validate_pairwise(judge_model, n)` and `validate_summeval(judge_model, n)`: run
    the judge over n items (cached, so re-runs are free), compute agreement, and write
    a Markdown table to ``results/judge_validation/``.
"""


def validate_pairwise(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("judge validation is implemented in milestone M4")


def validate_summeval(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("judge validation is implemented in milestone M4")
