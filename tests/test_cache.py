from __future__ import annotations

import pytest

from promptci.cache.disk import CachedProvider, DiskCache, cache_key
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
