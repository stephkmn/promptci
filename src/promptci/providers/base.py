"""Provider protocol and the Completion record every provider returns.

A provider turns a prompt into a completion. Everything else in PromptCI (cache,
runner, store) only sees `Completion` objects, so adding a new backend means
implementing one class with one async method.

Model strings have the form ``provider/model``, for example ``ollama/qwen2.5:7b``
or ``openai/gpt-4o-mini``. `parse_model_string` splits them.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Completion:
    """One model response plus the accounting that goes with it.

    Attributes:
        text: The model's output text.
        prompt_tokens: Tokens in the prompt, as reported by the provider (0 if unknown).
        completion_tokens: Tokens generated (0 if unknown).
        latency_ms: Wall-clock time for the request in milliseconds.
        cost_usd: Dollar cost of this call. Zero for local models.
        raw: The untouched provider response, kept for debugging. Not used by graders.
        cached: True if this completion was served from the on-disk cache.
    """

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the cache. `cached` is not stored; it is set on read."""
        d = asdict(self)
        d.pop("cached", None)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Completion:
        """Rebuild from a cache entry."""
        return cls(
            text=d["text"],
            prompt_tokens=int(d.get("prompt_tokens", 0)),
            completion_tokens=int(d.get("completion_tokens", 0)),
            latency_ms=float(d.get("latency_ms", 0.0)),
            cost_usd=float(d.get("cost_usd", 0.0)),
            raw=d.get("raw", {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


@runtime_checkable
class Provider(Protocol):
    """Anything that can complete a prompt.

    Implementations must be safe to call concurrently from many asyncio tasks.
    `name` is the provider prefix used in model strings (``ollama``, ``openai``, ``replay``).
    """

    name: str

    async def complete(self, prompt: str, model: str, **params: Any) -> Completion:
        """Complete `prompt` with `model`. `params` are decoding parameters such as
        temperature and max_tokens. Raise `ProviderError` on failure."""
        ...


class ProviderError(RuntimeError):
    """Raised when a provider cannot return a completion."""


class CacheMissError(ProviderError):
    """Raised by ReplayProvider when the requested completion is not in the cache."""


def parse_model_string(model: str) -> tuple[str, str]:
    """Split ``provider/model`` into its two parts.

    >>> parse_model_string("ollama/qwen2.5:7b")
    ('ollama', 'qwen2.5:7b')
    >>> parse_model_string("openrouter/meta-llama/llama-3.1-8b-instruct")
    ('openrouter', 'meta-llama/llama-3.1-8b-instruct')
    """
    if "/" not in model:
        raise ValueError(
            f"Model string {model!r} must look like 'provider/model', e.g. 'ollama/qwen2.5:7b'"
        )
    provider, _, name = model.partition("/")
    if not provider or not name:
        raise ValueError(f"Model string {model!r} has an empty provider or model part")
    return provider, name
