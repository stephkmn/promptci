"""Provider registry.

`make_provider(model_string, cache_dir)` turns ``ollama/qwen2.5:7b`` into a
provider object wrapped in the disk cache. Add new backends here.
"""

from __future__ import annotations

from pathlib import Path

from promptci.providers.base import (
    CacheMissError,
    Completion,
    Provider,
    ProviderError,
    parse_model_string,
)
from promptci.providers.fake import FakeProvider

# ReplayProvider is imported lazily inside make_provider: it depends on
# promptci.cache.disk, which depends on promptci.providers.base, and importing it
# here would make that a cycle.

__all__ = [
    "CacheMissError",
    "Completion",
    "FakeProvider",
    "Provider",
    "ProviderError",
    "make_provider",
    "parse_model_string",
]

OPENAI_COMPAT_PREFIXES = ("openai", "groq", "openrouter", "gemini")


def make_provider(model_string: str, cache_dir: str | Path) -> tuple[Provider, str]:
    """Build the raw (uncached) provider for a model string.

    Returns ``(provider, model_name)``. The caller wraps it in `CachedProvider`;
    `ReplayProvider` is the exception, it reads the cache itself and is never wrapped
    for writing.
    """
    prefix, model = parse_model_string(model_string)
    if prefix == "replay":
        from promptci.providers.replay import ReplayProvider

        return ReplayProvider(cache_dir), model
    if prefix == "fake":
        # Demo/testing provider. The suite's `fake_responses` block, if any, is
        # attached by the CLI after construction.
        return FakeProvider(), model
    if prefix == "ollama":
        from promptci.providers.ollama import OllamaProvider

        return OllamaProvider(), model
    if prefix in OPENAI_COMPAT_PREFIXES:
        from promptci.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(name=prefix), model
    if prefix == "anthropic":
        from promptci.providers.anthropic import AnthropicProvider

        return AnthropicProvider(), model
    raise ProviderError(
        f"Unknown provider {prefix!r}. Known: replay, fake, ollama, "
        f"{', '.join(OPENAI_COMPAT_PREFIXES)}, anthropic"
    )
