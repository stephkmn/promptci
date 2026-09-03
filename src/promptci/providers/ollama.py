"""OllamaProvider: local models over Ollama's HTTP API.

Talks to ``POST /api/generate`` (non-streaming). Ollama reports token counts as
``prompt_eval_count`` and ``eval_count``, and its own wall-clock as ``total_duration``
in nanoseconds. Cost is always zero.

Start Ollama with ``ollama serve`` and pull a model with ``ollama pull qwen2.5:7b``.
The base URL can be overridden with the ``OLLAMA_HOST`` environment variable.

This module is not exercised by the unit tests (they use FakeProvider). Test it
manually with ``promptci run examples/json_extract/suite.yaml --model ollama/qwen2.5:7b``.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from promptci.providers.base import Completion, ProviderError

DEFAULT_BASE_URL = "http://localhost:11434"

# Map PromptCI's generic parameter names onto Ollama's `options` block.
_OPTION_NAMES = {
    "temperature": "temperature",
    "top_p": "top_p",
    "top_k": "top_k",
    "seed": "seed",
    "max_tokens": "num_predict",
    "stop": "stop",
    "num_ctx": "num_ctx",
}


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str | None = None, timeout_s: float = 300.0):
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_s)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        options = {_OPTION_NAMES[k]: v for k, v in params.items() if k in _OPTION_NAMES}
        unknown = set(params) - set(_OPTION_NAMES) - {"system"}
        if unknown:
            raise ProviderError(f"OllamaProvider does not understand params: {sorted(unknown)}")
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if "system" in params:
            body["system"] = params["system"]

        client = self._client_or_create()
        t0 = time.perf_counter()
        try:
            resp = await client.post("/api/generate", json=body)
        except httpx.HTTPError as e:
            raise ProviderError(
                f"Ollama request failed at {self.base_url}: {e}. Is 'ollama serve' running?"
            ) from e
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code != 200:
            raise ProviderError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return Completion(
            text=data.get("response", ""),
            prompt_tokens=int(data.get("prompt_eval_count", 0) or 0),
            completion_tokens=int(data.get("eval_count", 0) or 0),
            latency_ms=latency_ms,
            cost_usd=0.0,
            raw={k: v for k, v in data.items() if k not in ("context",)},
        )
