from __future__ import annotations

import pytest

from promptci.cache.disk import CachedProvider, DiskCache
from promptci.providers import make_provider
from promptci.providers.base import CacheMissError, ProviderError, parse_model_string
from promptci.providers.fake import FakeProvider
from promptci.providers.replay import ReplayProvider


def test_parse_model_string():
    assert parse_model_string("ollama/qwen2.5:7b") == ("ollama", "qwen2.5:7b")
    assert parse_model_string("openrouter/meta-llama/llama-3.1-8b") == (
        "openrouter",
        "meta-llama/llama-3.1-8b",
    )
    with pytest.raises(ValueError):
        parse_model_string("qwen2.5:7b")
    with pytest.raises(ValueError):
        parse_model_string("/x")


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic():
    f = FakeProvider(responses={"hello": "world"})
    a = await f.complete("hello", "m")
    b = await f.complete("hello", "m")
    assert a.text == b.text == "world"
    unknown = await f.complete("???", "m")
    assert unknown.text.startswith("[fake:")
    assert unknown.text == (await f.complete("???", "m")).text


@pytest.mark.asyncio
async def test_replay_exact_source_and_any(tmp_path):
    fake = FakeProvider(responses={"q": "a"})
    cached = CachedProvider(fake, DiskCache(tmp_path))
    await cached.complete("q", "demo", temperature=0.0)

    replay = ReplayProvider(tmp_path)
    exact = await replay.complete("q", "fake/demo", temperature=0.0)
    assert exact.text == "a" and exact.cached

    anyhit = await replay.complete("q", "any", temperature=0.0)
    assert anyhit.text == "a"

    with pytest.raises(CacheMissError):
        await replay.complete("q", "fake/demo", temperature=0.7)
    with pytest.raises(CacheMissError):
        await replay.complete("never asked", "any", temperature=0.0)
    with pytest.raises(ProviderError):
        await replay.complete("q", "no-slash-here", temperature=0.0)


@pytest.mark.asyncio
async def test_replay_any_is_ambiguous_when_two_models_recorded(tmp_path):
    cache = DiskCache(tmp_path)
    await CachedProvider(FakeProvider(responses={"q": "a"}), cache).complete("q", "m1")
    await CachedProvider(FakeProvider(responses={"q": "b"}), cache).complete("q", "m2")
    replay = ReplayProvider(tmp_path)
    with pytest.raises(ProviderError, match="ambiguous"):
        await replay.complete("q", "any")


def test_make_provider_registry(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    p, m = make_provider("replay/any", tmp_path)
    assert isinstance(p, ReplayProvider) and m == "any"
    p, m = make_provider("fake/demo", tmp_path)
    assert isinstance(p, FakeProvider) and m == "demo"
    with pytest.raises(ProviderError):
        make_provider("nosuch/model", tmp_path)
    # paid providers refuse to construct without a key rather than failing later
    with pytest.raises(ProviderError, match="API_KEY"):
        make_provider("groq/llama-3.1-8b-instant", tmp_path)
