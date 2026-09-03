"""AnthropicProvider: optional, only usable when ANTHROPIC_API_KEY is set.

Uses the Messages API directly over httpx so the core package does not depend on
the `anthropic` SDK. Not exercised by unit tests.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from promptci.pricing import cost_usd
from promptci.providers.base import Completion, ProviderError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, timeout_s: float = 120.0):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderError("Set ANTHROPIC_API_KEY to use the anthropic provider")
        self.timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_s,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": API_VERSION,
                    "content-type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": int(params.get("max_tokens", 1024)),
            "messages": [{"role": "user", "content": prompt}],
        }
        if "system" in params:
            body["system"] = str(params["system"])
        for k in ("temperature", "top_p", "top_k"):
            if params.get(k) is not None:
                body[k] = params[k]
        if params.get("stop"):
            body["stop_sequences"] = list(params["stop"])

        client = self._client_or_create()
        t0 = time.perf_counter()
        try:
            resp = await client.post(API_URL, json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"anthropic request failed: {e}") from e
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code != 200:
            raise ProviderError(f"anthropic returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage") or {}
        pt = int(usage.get("input_tokens", 0) or 0)
        ct = int(usage.get("output_tokens", 0) or 0)
        return Completion(
            text=text,
            prompt_tokens=pt,
            completion_tokens=ct,
            latency_ms=latency_ms,
            cost_usd=cost_usd(self.name, model, pt, ct),
            raw=data,
        )
