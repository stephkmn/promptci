from __future__ import annotations

import pytest

from promptci.store.sqlite import ResultRecord, ResultStore


def _store(tmp_path) -> ResultStore:
    return ResultStore(tmp_path / "t.db")


def test_create_run_and_fetch(tmp_path):
    with _store(tmp_path) as s:
        run = s.create_run(
            suite_name="demo",
            suite_hash="abc",
            model="fake/m",
            params={"temperature": 0.0},
            label="baseline",
            sha="deadbeef",
            n_cases=2,
        )
        got = s.get_run(run.run_id)
        assert got.suite_name == "demo" and got.params == {"temperature": 0.0}
        assert got.label == "baseline" and got.git_sha == "deadbeef"
        assert got.finished_at is None
        s.finish_run(run.run_id)
        assert s.get_run(run.run_id).finished_at is not None
        # prefix lookup, like git
        assert s.get_run(run.run_id[:6]).run_id == run.run_id
        with pytest.raises(KeyError):
            s.get_run("nope")


def test_results_and_summary(tmp_path):
    with _store(tmp_path) as s:
        run = s.create_run(suite_name="demo", suite_hash="h", model="fake/m", params={})
        rows = [
            ResultRecord(run.run_id, "c1", "out", 1.0, True, 10, 5, 100.0, 0.001, cached=True),
            ResultRecord(run.run_id, "c2", "out", 0.5, False, 10, 5, 300.0, 0.001),
            ResultRecord(run.run_id, "c3", "out", 0.0, False, 10, 5, 200.0, 0.001),
            ResultRecord(run.run_id, "c4", None, None, None, error="ProviderError: boom"),
        ]
        s.add_results(rows)
        summary = s.summarize(run.run_id)
        assert summary.n_cases == 4 and summary.n_errors == 1
        # errored case counts as 0 in the mean; it did not pass
        assert summary.mean_score == pytest.approx(1.5 / 4)
        assert summary.pass_rate == pytest.approx(1 / 4)
        assert summary.mean_latency_ms == pytest.approx(200.0)
        assert summary.p95_latency_ms == 300.0
        assert summary.prompt_tokens == 30 and summary.completion_tokens == 15
        assert summary.total_cost_usd == pytest.approx(0.003)
        assert summary.cache_hit_rate == pytest.approx(1 / 4)

        back = s.get_results(run.run_id)
        assert [r.case_id for r in back] == ["c1", "c2", "c3", "c4"]
        assert back[3].error and back[3].score is None and back[3].passed is None
        assert back[0].cached is True and back[1].cached is False


def test_add_result_replaces_same_case(tmp_path):
    with _store(tmp_path) as s:
        run = s.create_run(suite_name="d", suite_hash="h", model="m", params={})
        s.add_result(ResultRecord(run.run_id, "c1", "a", 0.0, False))
        s.add_result(ResultRecord(run.run_id, "c1", "b", 1.0, True))
        rows = s.get_results(run.run_id)
        assert len(rows) == 1 and rows[0].output == "b"


def test_list_runs_filters_by_suite(tmp_path):
    with _store(tmp_path) as s:
        s.create_run(suite_name="a", suite_hash="h", model="m", params={})
        s.create_run(suite_name="b", suite_hash="h", model="m", params={})
        assert len(s.list_runs()) == 2
        assert [r.suite_name for r in s.list_runs("a")] == ["a"]
