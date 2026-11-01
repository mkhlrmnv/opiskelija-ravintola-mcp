"""Provider -> adapter registry. Each provider adapter is added to ``ADAPTERS`` when implemented."""

from __future__ import annotations

from ravintola_mcp.adapters.base import MenuAdapter
from ravintola_mcp.adapters.kipsari import KipsariAdapter
from ravintola_mcp.adapters.sodexo import SodexoAdapter

ADAPTERS: dict[str, MenuAdapter] = {
    adapter.provider: adapter for adapter in (KipsariAdapter(), SodexoAdapter())
}


def get_adapter(provider: str) -> MenuAdapter | None:
    return ADAPTERS.get(provider)
