"""Provider -> adapter registry. Each provider adapter is added to ``ADAPTERS`` when implemented."""

from __future__ import annotations

from ravintola_mcp.adapters.base import MenuAdapter

ADAPTERS: dict[str, MenuAdapter] = {}


def get_adapter(provider: str) -> MenuAdapter | None:
    return ADAPTERS.get(provider)
