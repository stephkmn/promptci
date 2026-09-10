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
from dataclasses import asdict, dataclass
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


UNKNOWN = "?"
"""Provider/model shown for an entry whose request could not be read."""


@dataclass(frozen=True)
class CacheGroup:
    """Entry count and on-disk size for one (provider, model) pair in a cache directory."""

    provider: str
    model: str
    entries: int
    total_bytes: int


@dataclass(frozen=True)
class CacheStats:
    """What a cache directory holds: totals plus a per-(provider, model) breakdown.

    `total_bytes` is the size of the entry files on disk, unreadable ones included.
    `unreadable` counts entries whose request could not be parsed; they are reported
    rather than raised so one bad file cannot hide the rest, which matches
    `DiskCache.get` treating a corrupt entry as a miss. Those entries are grouped
    under provider and model `UNKNOWN`.
    """

    root: Path
    entries: int
    total_bytes: int
    unreadable: int
    groups: list[CacheGroup]

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready form for `promptci cache stats --json`. Sizes stay in raw bytes."""
        d = asdict(self)
        d["root"] = str(self.root)
        return d


def read_cache_stats(root: str | Path) -> CacheStats:
    """Count and group the entries under `root`, creating and writing nothing.

    Deliberately a function on a path rather than only a `DiskCache` method: the
    constructor creates its root directory, and inspecting a cache must not bring one
    into being. A missing directory reports zero entries instead of raising, so the
    caller decides whether "nothing cached yet" is an error.

    Every entry file is opened, because the provider and model are inside the JSON and
    not in the path. That is O(entries) and fine at the sizes this cache reaches; if a
    cache ever grows to where it is not, the fix is an index, not a guess from the path.
    """
    root = Path(root)
    counts: dict[tuple[str, str], list[int]] = {}
    entries = 0
    total_bytes = 0
    unreadable = 0
    for path in root.glob("*/*.json"):
        entries += 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total_bytes += size
        provider, model = UNKNOWN, UNKNOWN
        try:
            with path.open("r", encoding="utf-8") as f:
                request = json.load(f)["request"]
            provider, model = str(request["provider"]), str(request["model"])
        except (OSError, ValueError, KeyError, TypeError):
            # Same tolerance as `get`: a corrupt or foreign file is counted, not fatal.
            unreadable += 1
        slot = counts.setdefault((provider, model), [0, 0])
        slot[0] += 1
        slot[1] += size
    groups = [
        CacheGroup(provider=p, model=m, entries=n, total_bytes=b)
        for (p, m), (n, b) in counts.items()
    ]
    groups.sort(key=lambda g: (-g.entries, g.provider, g.model))
    return CacheStats(
        root=root,
        entries=entries,
        total_bytes=total_bytes,
        unreadable=unreadable,
        groups=groups,
    )


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

    def stats(self) -> CacheStats:
        """Entries, size, and the (provider, model) breakdown for this cache."""
        return read_cache_stats(self.root)


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
