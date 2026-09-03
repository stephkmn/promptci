"""SQLite result store.

Two tables. `runs` records one row per `promptci run` invocation with enough
provenance to reproduce it (suite hash, model, params, git SHA). `results` records
one row per case. Nothing is ever aggregated at write time; summaries are computed
on read so a fix to the summary code never requires re-running anything.

The default database path is ``results/promptci.db`` relative to the current
directory. Commit the ``results/`` directory when a run backs a reported number.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    suite_name   TEXT NOT NULL,
    suite_hash   TEXT NOT NULL,
    suite_path   TEXT,
    model        TEXT NOT NULL,
    params_json  TEXT NOT NULL,
    git_sha      TEXT,
    label        TEXT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    n_cases      INTEGER
);
CREATE TABLE IF NOT EXISTS results (
    run_id              TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    case_id             TEXT NOT NULL,
    output              TEXT,
    score               REAL,
    passed              INTEGER,
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    latency_ms          REAL DEFAULT 0,
    cost_usd            REAL DEFAULT 0,
    cached              INTEGER DEFAULT 0,
    error               TEXT,
    grader_details_json TEXT,
    PRIMARY KEY (run_id, case_id)
);
CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
"""


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def git_sha(cwd: str | Path | None = None) -> str | None:
    """Short git SHA of the working tree, with ``-dirty`` if there are uncommitted changes."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return f"{sha}-dirty" if status else sha
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass
class RunRecord:
    run_id: str
    suite_name: str
    suite_hash: str
    model: str
    params: dict[str, Any]
    started_at: str
    finished_at: str | None = None
    git_sha: str | None = None
    label: str | None = None
    suite_path: str | None = None
    n_cases: int | None = None


@dataclass
class ResultRecord:
    run_id: str
    case_id: str
    output: str | None
    score: float | None
    passed: bool | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cached: bool = False
    error: str | None = None
    grader_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunSummary:
    run_id: str
    suite_name: str
    model: str
    n_cases: int
    n_errors: int
    mean_score: float
    pass_rate: float | None
    mean_latency_ms: float
    p95_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    cache_hit_rate: float

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ResultStore:
    def __init__(self, path: str | Path = "results/promptci.db"):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> ResultStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- runs ---------------------------------------------------------------

    def create_run(
        self,
        *,
        suite_name: str,
        suite_hash: str,
        model: str,
        params: dict[str, Any],
        suite_path: str | None = None,
        label: str | None = None,
        sha: str | None = None,
        n_cases: int | None = None,
        run_id: str | None = None,
    ) -> RunRecord:
        rec = RunRecord(
            run_id=run_id or uuid.uuid4().hex[:12],
            suite_name=suite_name,
            suite_hash=suite_hash,
            model=model,
            params=params,
            started_at=utcnow(),
            git_sha=sha,
            label=label,
            suite_path=suite_path,
            n_cases=n_cases,
        )
        self.conn.execute(
            "INSERT INTO runs (run_id, suite_name, suite_hash, suite_path, model, params_json,"
            " git_sha, label, started_at, n_cases) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                rec.run_id,
                rec.suite_name,
                rec.suite_hash,
                rec.suite_path,
                rec.model,
                json.dumps(rec.params, sort_keys=True),
                rec.git_sha,
                rec.label,
                rec.started_at,
                rec.n_cases,
            ),
        )
        self.conn.commit()
        return rec

    def finish_run(self, run_id: str) -> None:
        self.conn.execute("UPDATE runs SET finished_at = ? WHERE run_id = ?", (utcnow(), run_id))
        self.conn.commit()

    def get_run(self, run_id: str) -> RunRecord:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            # allow unique prefix match, the way git does
            rows = self.conn.execute(
                "SELECT * FROM runs WHERE run_id LIKE ?", (f"{run_id}%",)
            ).fetchall()
            if len(rows) == 1:
                row = rows[0]
            elif len(rows) > 1:
                raise KeyError(f"run id prefix {run_id!r} is ambiguous")
            else:
                raise KeyError(f"no run {run_id!r}")
        return RunRecord(
            run_id=row["run_id"],
            suite_name=row["suite_name"],
            suite_hash=row["suite_hash"],
            model=row["model"],
            params=json.loads(row["params_json"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            git_sha=row["git_sha"],
            label=row["label"],
            suite_path=row["suite_path"],
            n_cases=row["n_cases"],
        )

    def list_runs(self, suite_name: str | None = None, limit: int = 50) -> list[RunRecord]:
        q = "SELECT run_id FROM runs"
        args: tuple[Any, ...] = ()
        if suite_name:
            q += " WHERE suite_name = ?"
            args = (suite_name,)
        q += " ORDER BY started_at DESC LIMIT ?"
        rows = self.conn.execute(q, (*args, limit)).fetchall()
        return [self.get_run(r["run_id"]) for r in rows]

    # -- results ------------------------------------------------------------

    def add_result(self, r: ResultRecord) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO results (run_id, case_id, output, score, passed,"
            " prompt_tokens, completion_tokens, latency_ms, cost_usd, cached, error,"
            " grader_details_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.run_id,
                r.case_id,
                r.output,
                r.score,
                None if r.passed is None else int(r.passed),
                r.prompt_tokens,
                r.completion_tokens,
                r.latency_ms,
                r.cost_usd,
                int(r.cached),
                r.error,
                json.dumps(r.grader_details, default=str),
            ),
        )
        self.conn.commit()

    def add_results(self, results: list[ResultRecord]) -> None:
        for r in results:
            self.add_result(r)

    def get_results(self, run_id: str) -> list[ResultRecord]:
        run = self.get_run(run_id)
        rows = self.conn.execute(
            "SELECT * FROM results WHERE run_id = ? ORDER BY case_id", (run.run_id,)
        ).fetchall()
        return [
            ResultRecord(
                run_id=row["run_id"],
                case_id=row["case_id"],
                output=row["output"],
                score=row["score"],
                passed=None if row["passed"] is None else bool(row["passed"]),
                prompt_tokens=row["prompt_tokens"] or 0,
                completion_tokens=row["completion_tokens"] or 0,
                latency_ms=row["latency_ms"] or 0.0,
                cost_usd=row["cost_usd"] or 0.0,
                cached=bool(row["cached"]),
                error=row["error"],
                grader_details=json.loads(row["grader_details_json"] or "{}"),
            )
            for row in rows
        ]

    # -- summary ------------------------------------------------------------

    def summarize(self, run_id: str) -> RunSummary:
        run = self.get_run(run_id)
        results = self.get_results(run.run_id)
        return summarize_results(run, results)


def _percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile. Good enough for latency reporting; no numpy needed here."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(q * (len(s) - 1))))
    return float(s[k])


def summarize_results(run: RunRecord, results: list[ResultRecord]) -> RunSummary:
    scored = [r for r in results if r.error is None and r.score is not None]
    scores = [float(r.score) for r in scored]  # type: ignore[arg-type]
    passes = [r.passed for r in scored if r.passed is not None]
    latencies = [r.latency_ms for r in results if r.error is None]
    n = len(results)
    return RunSummary(
        run_id=run.run_id,
        suite_name=run.suite_name,
        model=run.model,
        n_cases=n,
        n_errors=sum(1 for r in results if r.error is not None),
        # errored cases count as score 0: an eval that crashes on a case did not pass it
        mean_score=(sum(scores) / n) if n else 0.0,
        pass_rate=(sum(1 for p in passes if p) / n) if passes and n else None,
        mean_latency_ms=(sum(latencies) / len(latencies)) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 0.95),
        prompt_tokens=sum(r.prompt_tokens for r in results),
        completion_tokens=sum(r.completion_tokens for r in results),
        total_cost_usd=sum(r.cost_usd for r in results),
        cache_hit_rate=(sum(1 for r in results if r.cached) / n) if n else 0.0,
    )
