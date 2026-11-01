"""Adapter contract: one adapter per menu provider (Compass, Sodexo, ...)."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from abc import ABC, abstractmethod

import httpx

from ravintola_mcp.models import Lang, Menu, Restaurant

USER_AGENT = "opiskelija-ravintola-mcp/0.1 (+https://github.com/mkhlrmnv/opiskelija-ravintola-mcp)"


class AdapterError(RuntimeError):
    """Raised when a provider responds but the data cannot be fetched or parsed."""


class MenuAdapter(ABC):
    """Fetches and normalises one day's lunch menu for restaurants served by a provider.

    Implementations must:
    - use the shared ``httpx.AsyncClient`` (plain GET) unless the site genuinely needs JS;
    - return an empty ``dishes`` list (not raise) when the restaurant is closed that day;
    - fill ``Dish.macros`` only with values actually published by the site;
    - fall back to Finnish when ``lang="en"`` is unavailable and add a note saying so.
    """

    provider: str

    @abstractmethod
    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu: ...


def slugify(text: str) -> str:
    """ASCII slug used for dish ids and fuzzy restaurant/dish matching."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")


def parse_number(value: object) -> float | None:
    """Parse '12,5 g' / '12.5' / 12 into a float; None for blanks or junk."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    return float(match.group().replace(",", ".")) if match else None
