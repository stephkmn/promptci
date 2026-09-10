from __future__ import annotations

import json

import pytest

from promptci.cache.disk import UNKNOWN, CachedProvider, DiskCache, cache_key, read_cache_stats
from promptci.providers.base import Completion
from promptci.providers.fake import FakeProvider


def test_cache_key_is_deterministic_and_order_independent():
    k1 = cache_key("ollama", "m", {"temperature": 0.0, "max_tokens": 10}, "hi")
    k2 = cache_key("ollama", "m", {"max_tokens": 10, "temperature": 0.0}, "hi")
    assert k1 == k2
    assert len(k1) == 64


def test_cache_key_changes_with_every_field():
    base = cache_key("ollama", "m", {"t": 0}, "hi")
    assert cache_key("openai", "m", {"t": 0}, "hi") != base
    assert cache_key("ollama", "m2", {"t": 0}, "hi") != base
    assert cache_key("ollama", "m", {"t": 1}, "hi") != base
    assert cache_key("ollama", "m", {"t": 0}, "hi!") != base


def test_cache_key_ignores_none_params():
    assert cache_key("p", "m", {"seed": None}, "x") == cache_key("p", "m", {}, "x")


def test_cache_key_is_not_confused_by_moving_bytes_between_fields():
    # "ab" + "c" vs "a" + "bc" would collide with naive concatenation
    assert cache_key("p", "ab", {}, "c") != cache_key("p", "a", {}, "bc")


def test_disk_cache_roundtrip(tmp_path):
    cache = DiskCache(tmp_path / "c")
    key = cache_key("fake", "m", {"temperature": 0.0}, "prompt")
    assert cache.get(key) is None
    assert not cache.has(key)
    c = Completion(text="out", prompt_tokens=3, completion_tokens=2, latency_ms=12.5, raw={"a": 1})
    path = cache.put(
        key, c, provider="fake", model="m", params={"temperature": 0.0}, prompt="prompt"
    )
    assert path.exists()
    got = cache.get(key)
    assert got is not None
    assert got.text == "out"
    assert got.prompt_tokens == 3
    assert got.latency_ms == 12.5
    assert got.raw == {"a": 1}
    assert got.cached is True
    assert len(cache) == 1
    assert cache.keys() == [key]


def test_disk_cache_corrupt_entry_is_a_miss(tmp_path):
    cache = DiskCache(tmp_path)
    key = "ab" + "0" * 62
    p = cache.path_for(key)
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert cache.get(key) is None


@pytest.mark.asyncio
async def test_cached_provider_hits_second_time(tmp_path):
    fake = FakeProvider(responses={"q": "a"})
    cp = CachedProvider(fake, DiskCache(tmp_path))
    c1 = await cp.complete("q", "m", temperature=0.0)
    c2 = await cp.complete("q", "m", temperature=0.0)
    assert c1.text == c2.text == "a"
    assert c1.cached is False and c2.cached is True
    assert len(fake.calls) == 1
    assert (cp.hits, cp.misses) == (1, 1)


@pytest.mark.asyncio
async def test_cached_provider_no_write_mode(tmp_path):
    fake = FakeProvider(responses={"q": "a"})
    cp = CachedProvider(fake, DiskCache(tmp_path), write=False)
    await cp.complete("q", "m")
    await cp.complete("q", "m")
    assert len(fake.calls) == 2


def _put(cache: DiskCache, provider: str, model: str, prompt: str) -> None:
    """Record one completion the way `CachedProvider` would, for the stats tests."""
    key = cache_key(provider, model, {}, prompt)
    cache.put(
        key,
        Completion(text="out", prompt_tokens=1, completion_tokens=1, latency_ms=1.0),
        provider=provider,
        model=model,
        params={},
        prompt=prompt,
    )


def test_cache_stats_groups_by_provider_and_model(tmp_path):
    """Entries and bytes are totalled, and split per (provider, model), biggest first."""
    cache = DiskCache(tmp_path / "c")
    _put(cache, "ollama", "qwen2.5:7b", "one")
    _put(cache, "ollama", "qwen2.5:7b", "two")
    _put(cache, "ollama", "llama3.2:3b", "one")
    _put(cache, "fake", "demo", "one")

    stats = cache.stats()
    assert stats.root == tmp_path / "c"
    assert stats.entries == 4
    assert stats.unreadable == 0
    assert [(g.provider, g.model, g.entries) for g in stats.groups] == [
        ("ollama", "qwen2.5:7b", 2),
        ("fake", "demo", 1),
        ("ollama", "llama3.2:3b", 1),
    ]
    # Sizes are real file sizes and add up to the total.
    assert all(g.total_bytes > 0 for g in stats.groups)
    assert sum(g.total_bytes for g in stats.groups) == stats.total_bytes


def test_cache_stats_reports_corrupt_entries_instead_of_raising(tmp_path):
    """One bad file must not hide the rest; it is counted and labelled unknown.

    Same tolerance as `DiskCache.get`, which treats a corrupt entry as a miss.
    """
    cache = DiskCache(tmp_path)
    _put(cache, "ollama", "qwen2.5:7b", "one")
    bad = cache.path_for("ab" + "0" * 62)
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json")

    stats = cache.stats()
    assert stats.entries == 2
    assert stats.unreadable == 1
    assert (UNKNOWN, UNKNOWN, 1) in [(g.provider, g.model, g.entries) for g in stats.groups]


def test_cache_stats_on_a_missing_dir_is_empty_and_creates_nothing(tmp_path):
    """Inspecting a cache must not bring one into being: `DiskCache.__init__` would."""
    missing = tmp_path / "not-there"
    stats = read_cache_stats(missing)
    assert (stats.entries, stats.total_bytes, stats.unreadable, stats.groups) == (0, 0, 0, [])
    assert not missing.exists()


def test_cache_stats_as_dict_is_json_serializable(tmp_path):
    """`--json` output must survive `json.dumps`, so the Path becomes a string."""
    cache = DiskCache(tmp_path)
    _put(cache, "fake", "demo", "one")
    d = cache.stats().as_dict()
    assert d["root"] == str(tmp_path)
    assert json.loads(json.dumps(d))["groups"][0]["model"] == "demo"
