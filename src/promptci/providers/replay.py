"""ReplayProvider: serve completions from the disk cache only.

Used in CI so that evaluation runs are free, deterministic, and need no API key.
Two model-string forms are accepted:

``replay/<source>/<model>``
    Exact lookup. ``replay/ollama/qwen2.5:7b`` returns what ``ollama/qwen2.5:7b``
    recorded for the same prompt and params. This is what CI should use.

``replay/any``
    Match on (params, prompt) only, ignoring which provider and model recorded the
    entry. Convenient for demos. It raises if two different models recorded the
    same prompt, because then "any" is ambiguous.

On a cache miss it raises `CacheMissError`. CI should treat that as a failure: it
means someone changed the suite or prompt without re-recording the cache.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from promptci.cache.disk import DiskCache, _canonical_params, cache_key
from promptci.providers.base import CacheMissError, Completion, ProviderError

ANY = "any"


class ReplayProvider:
    """Read-only provider backed by a DiskCache."""

    name = "replay"

    def __init__(self, cache_dir: str | Path):
        self.cache = DiskCache(cache_dir)
        self._index: dict[tuple[str, str], list[str]] | None = None

    def _build_index(self) -> dict[tuple[str, str], list[str]]:
        """Map (canonical params, prompt) -> list of cache keys. Built lazily, once."""
        index: dict[tuple[str, str], list[str]] = {}
        for p in self.cache.root.glob("*/*.json"):
            try:
                entry = json.loads(p.read_text(encoding="utf-8"))
                req = entry["request"]
                k = (_canonical_params(req.get("params", {})), req["prompt"])
            except (OSError, ValueError, KeyError):
                continue
            index.setdefault(k, []).append(entry["key"])
        return index

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        if model == ANY:
            return self._complete_any(prompt, params)
        if "/" not in model:
            raise ProviderError(
                f"Replay model must be 'replay/any' or 'replay/<source>/<model>', "
                f"got 'replay/{model}'"
            )
        source, _, source_model = model.partition("/")
        key = cache_key(source, source_model, params, prompt)
        hit = self.cache.get(key)
        if hit is None:
            raise CacheMissError(
                f"No cached completion for {source}/{source_model} params={params!r} "
                f"prompt[:60]={prompt[:60]!r} in {self.cache.root}. "
                "Re-record the cache with the real provider and commit it."
            )
        return hit

    def _complete_any(self, prompt: str, params: dict[str, Any]) -> Completion:
        if self._index is None:
            self._index = self._build_index()
        keys = self._index.get((_canonical_params(params), prompt), [])
        if not keys:
            raise CacheMissError(
                f"No cached completion for prompt[:60]={prompt[:60]!r} params={params!r} "
                f"in {self.cache.root}"
            )
        if len(keys) > 1:
            raise ProviderError(
                f"'replay/any' is ambiguous: {len(keys)} models recorded this prompt. "
                "Use 'replay/<source>/<model>'."
            )
        hit = self.cache.get(keys[0])
        if hit is None:  # pragma: no cover - index and disk disagree
            raise CacheMissError(f"Cache entry {keys[0]} vanished")
        return hit
