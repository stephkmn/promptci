"""Token pricing table.

Prices are USD per 1M tokens, split into input and output. They come from
``prices.yaml`` next to this module, and can be overridden by a user file passed
to `load_prices`. Local providers (ollama, fake, replay) always cost zero.

Prices change. The shipped table has a ``checked`` date per entry; update it when
you add a model, and say so in the commit message.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

FREE_PROVIDERS = {"ollama", "fake", "replay"}
_DEFAULT_FILE = Path(__file__).with_name("prices.yaml")


@lru_cache(maxsize=4)
def load_prices(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{"provider/model": {"input": float, "output": float, ...}}``."""
    p = Path(path) if path else _DEFAULT_FILE
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data.get("models", {})


def cost_usd(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    prices: dict[str, dict[str, Any]] | None = None,
) -> float:
    """Dollar cost of one call. Unknown paid models cost 0.0 and the caller should warn."""
    if provider in FREE_PROVIDERS:
        return 0.0
    table = prices if prices is not None else load_prices()
    entry = table.get(f"{provider}/{model}") or table.get(model)
    if not entry:
        return 0.0
    return (prompt_tokens * float(entry.get("input", 0.0)) / 1e6) + (
        completion_tokens * float(entry.get("output", 0.0)) / 1e6
    )
