"""Content-addressed on-disk cache for completions.

Every completion PromptCI makes goes through this cache. The key is the sha256 of
(provider, model, params, prompt), so the same request against the same model with
the same decoding parameters is never paid for twice, and a committed cache directory
lets CI replay a run with no network and no API key.

Layout on disk::

    <root>/
      ab/
        ab12cd...ef.json    # one file per completion

Each file holds the request (so the cache is inspectable) and the response.
The two-character prefix directory keeps any single directory from growing to
tens of thousands of entries.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from promptci.providers.base import Completion, Provider


def _canonical_params(params: dict[str, Any]) -> str:
    """Stable JSON for a params dict. Keys sorted, floats kept as given.

    None values are dropped so that ``{"temperature": None}`` and ``{}`` hash the same.
    """
    cleaned = {k: v for k, v in params.items() if v is not None}
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"))


def cache_key(provider: str, model: str, params: dict[str, Any], prompt: str) -> str:
    """sha256 over the four fields that define a request.

    The fields are length-prefixed before hashing so that no combination of
    (model, prompt) can collide with a different split of the same bytes.
    """
    h = hashlib.sha256()
    for part in (provider, model, _canonical_params(params), prompt):
        b = part.encode("utf-8")
        h.update(str(len(b)).encode("ascii"))
        h.update(b"\0")
        h.update(b)
    return h.hexdigest()


class DiskCache:
    """Read/write cache rooted at a directory."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def has(self, key: str) -> bool:
        return self.path_for(key).exists()

    def get(self, key: str) -> Completion | None:
        """Return the cached completion, or None on a miss.

        A corrupt file is treated as a miss rather than an error, so one bad
        entry cannot take down a whole run. It will be overwritten on the next put.
        """
        p = self.path_for(key)
        if not p.exists():
            return None
        try:
            with p.open("r", encoding="utf-8") as f:
                entry = json.load(f)
            c = Completion.from_dict(entry["response"])
        except (OSError, ValueError, KeyError):
            return None
        c.cached = True
        return c

    def put(
        self,
        key: str,
        completion: Completion,
        *,
        provider: str,
        model: str,
        params: dict[str, Any],
        prompt: str,
    ) -> Path:
        """Write atomically: write to a temp file in the same directory, then rename."""
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "key": key,
            "request": {
                "provider": provider,
                "model": model,
                "params": json.loads(_canonical_params(params)),
                "prompt": prompt,
            },
            "response": completion.to_dict(),
        }
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=1, sort_keys=True, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, p)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return p

    def __len__(self) -> int:
        return sum(1 for _ in self.root.glob("*/*.json"))

    def keys(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*/*.json"))


class CachedProvider:
    """Wrap any provider so every call is checked against, then written to, a DiskCache.

    This is the object the runner talks to. `name` is passed through so cache keys
    are computed with the underlying provider's name, not "cached".
    """

    def __init__(self, inner: Provider, cache: DiskCache, *, write: bool = True):
        self.inner = inner
        self.cache = cache
        self.write = write
        self.name = inner.name
        self.hits = 0
        self.misses = 0

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        key = cache_key(self.name, model, params, prompt)
        hit = self.cache.get(key)
        if hit is not None:
            self.hits += 1
            return hit
        self.misses += 1
        completion = await self.inner.complete(prompt, model, **params)
        if self.write:
            self.cache.put(
                key, completion, provider=self.name, model=model, params=params, prompt=prompt
            )
        return completion
