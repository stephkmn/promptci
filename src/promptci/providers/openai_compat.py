"""OpenAICompatProvider: any endpoint that speaks the OpenAI chat completions API.

This covers OpenAI itself, Groq, OpenRouter, Together, Gemini's OpenAI-compatible
endpoint, vLLM, and LM Studio. One class, configured by base URL and key.

Preset names (used as the provider prefix in model strings) and their env vars:

======== ============================================== ==================
prefix   base_url                                        key env var
======== ============================================== ==================
openai   https://api.openai.com/v1                       OPENAI_API_KEY
groq     https://api.groq.com/openai/v1                  GROQ_API_KEY
openrouter https://openrouter.ai/api/v1                  OPENROUTER_API_KEY
gemini   https://generativelanguage.googleapis.com/v1beta/openai  GEMINI_API_KEY
======== ============================================== ==================

Never put a key in a config file or commit one. Keys come from the environment.

Not exercised by the unit tests (they use FakeProvider).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from promptci.pricing import cost_usd
from promptci.providers.base import Completion, ProviderError

PRESETS: dict[str, tuple[str, str]] = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
}

_PASSTHROUGH = {"temperature", "top_p", "max_tokens", "seed", "stop", "presence_penalty"}


class OpenAICompatProvider:
    def __init__(
        self,
        name: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 120.0,
    ):
        self.name = name
        preset_url, key_env = PRESETS.get(name, (None, f"{name.upper()}_API_KEY"))
        self.base_url = (base_url or preset_url or "").rstrip("/")
        if not self.base_url:
            raise ProviderError(f"No base_url for provider {name!r}; pass one explicitly")
        self.api_key = api_key or os.environ.get(key_env)
        if not self.api_key:
            raise ProviderError(f"Set {key_env} to use provider {name!r}")
        self.timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_s,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        messages: list[dict[str, str]] = []
        if "system" in params:
            messages.append({"role": "system", "content": str(params["system"])})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"model": model, "messages": messages}
        for k, v in params.items():
            if k in _PASSTHROUGH and v is not None:
                body[k] = v

        client = self._client_or_create()
        t0 = time.perf_counter()
        try:
            resp = await client.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} request failed: {e}") from e
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code == 429:
            raise ProviderError(f"{self.name} rate limited (429): {resp.text[:200]}")
        if resp.status_code != 200:
            raise ProviderError(f"{self.name} returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"{self.name} response missing choices: {data}") from e
        usage = data.get("usage") or {}
        pt = int(usage.get("prompt_tokens", 0) or 0)
        ct = int(usage.get("completion_tokens", 0) or 0)
        return Completion(
            text=text,
            prompt_tokens=pt,
            completion_tokens=ct,
            latency_ms=latency_ms,
            cost_usd=cost_usd(self.name, model, pt, ct),
            raw=data,
        )
