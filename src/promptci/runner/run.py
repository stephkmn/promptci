"""Async suite runner.

For each case: render the prompt, call the (cached) provider, grade, write a result
row. Cases run concurrently under a semaphore. Provider errors are retried with
exponential backoff; a case that still fails is recorded with `error` set and score
None, so one flaky request does not abort a 200-case run and the summary can report
the error count honestly.

The runner never fabricates a score for a failed case. It records None and the
summary counts it as 0 with `n_errors` incremented.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from promptci.graders.base import Grader
from promptci.providers.base import CacheMissError, Provider, ProviderError
from promptci.store.sqlite import ResultRecord, ResultStore, RunRecord
from promptci.suite.schema import Case, Suite, render_prompt


@dataclass
class RunnerConfig:
    concurrency: int = 4
    max_retries: int = 3
    backoff_base_s: float = 1.0
    per_case_timeout_s: float = 300.0
    seed: int = 0


ProgressCallback = Callable[[ResultRecord], None]


class Runner:
    def __init__(
        self,
        provider: Provider,
        model: str,
        grader: Grader,
        store: ResultStore,
        config: RunnerConfig | None = None,
    ):
        self.provider = provider
        self.model = model
        self.grader = grader
        self.store = store
        self.config = config or RunnerConfig()
        self._rng = random.Random(self.config.seed)

    async def _complete_with_retries(self, prompt: str, params: dict[str, Any]):
        last: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.provider.complete(prompt, self.model, **params),
                    timeout=self.config.per_case_timeout_s,
                )
            except CacheMissError:
                raise  # replay misses are not transient; retrying wastes time
            except (ProviderError, TimeoutError, OSError) as e:
                last = e
                if attempt == self.config.max_retries:
                    break
                delay = self.config.backoff_base_s * (2**attempt) + self._rng.uniform(0, 0.25)
                await asyncio.sleep(delay)
        assert last is not None
        raise last

    async def _run_case(
        self, run: RunRecord, suite: Suite, case: Case, sem: asyncio.Semaphore
    ) -> ResultRecord:
        params = suite.params.as_dict()
        async with sem:
            prompt = render_prompt(suite, case)
            try:
                completion = await self._complete_with_retries(prompt, params)
            except Exception as e:  # noqa: BLE001 - recorded, not swallowed
                return ResultRecord(
                    run_id=run.run_id,
                    case_id=case.id,
                    output=None,
                    score=None,
                    passed=None,
                    error=f"{type(e).__name__}: {e}",
                )
            try:
                grade = await self.grader.agrade(completion.text, case)
            except Exception as e:  # noqa: BLE001
                return ResultRecord(
                    run_id=run.run_id,
                    case_id=case.id,
                    output=completion.text,
                    score=None,
                    passed=None,
                    prompt_tokens=completion.prompt_tokens,
                    completion_tokens=completion.completion_tokens,
                    latency_ms=completion.latency_ms,
                    cost_usd=completion.cost_usd,
                    cached=completion.cached,
                    error=f"grader {type(e).__name__}: {e}",
                )
        return ResultRecord(
            run_id=run.run_id,
            case_id=case.id,
            output=completion.text,
            score=grade.score,
            passed=grade.passed,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            latency_ms=completion.latency_ms,
            cost_usd=completion.cost_usd,
            cached=completion.cached,
            grader_details=grade.details,
        )

    async def run(
        self,
        suite: Suite,
        *,
        model_string: str,
        suite_path: str | None = None,
        label: str | None = None,
        sha: str | None = None,
        on_result: ProgressCallback | None = None,
    ) -> RunRecord:
        """Run every case in `suite` and return the run record.

        Results are written as they finish. Case order in the database is by
        case_id, not by completion time, so concurrency does not affect what
        `promptci summarize` prints.
        """
        run = self.store.create_run(
            suite_name=suite.name,
            suite_hash=suite.content_hash(),
            model=model_string,
            params=suite.params.as_dict(),
            suite_path=suite_path,
            label=label,
            sha=sha,
            n_cases=len(suite.cases),
        )
        sem = asyncio.Semaphore(self.config.concurrency)
        tasks = [asyncio.create_task(self._run_case(run, suite, case, sem)) for case in suite.cases]
        for fut in asyncio.as_completed(tasks):
            rec = await fut
            self.store.add_result(rec)
            if on_result is not None:
                on_result(rec)
        self.store.finish_run(run.run_id)
        return self.store.get_run(run.run_id)
