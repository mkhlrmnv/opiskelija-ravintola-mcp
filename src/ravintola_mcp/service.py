"""Menu service: fetches menus through adapters (cached) and answers dish and macro queries.

Adapter failures become ``Menu.error`` so one broken site never fails a multi-restaurant call.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import difflib
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import httpx

from ravintola_mcp.adapters import ADAPTERS
from ravintola_mcp.adapters.base import USER_AGENT, MenuAdapter, slugify
from ravintola_mcp.cache import MenuCache
from ravintola_mcp.models import Dish, Lang, Macros, Menu, Restaurant
from ravintola_mcp.restaurants import RESTAURANTS, resolve_restaurant

logger = logging.getLogger(__name__)

SortBy = Literal["protein_desc", "kcal_asc", "kcal_desc", "protein_per_kcal_desc"]

HTTP_TIMEOUT_S = 15.0
MIXED_BASIS_NOTE = (
    "These dishes mix per-portion and per-100 g macro values; compare them with care "
    "(see macro_basis)."
)


class MenuService:
    def __init__(
        self,
        adapters: Mapping[str, MenuAdapter] | None = None,
        client: httpx.AsyncClient | None = None,
        cache: MenuCache | None = None,
    ) -> None:
        self._adapters: Mapping[str, MenuAdapter] = ADAPTERS if adapters is None else adapters
        self._client = client
        self._own_client = False
        self._cache = MenuCache() if cache is None else cache

    async def aclose(self) -> None:
        """Close the HTTP client, but only if this service created it."""
        if self._own_client and self._client is not None:
            await self._client.aclose()
            self._client = None
            self._own_client = False

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=HTTP_TIMEOUT_S,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            self._own_client = True
        return self._client

    async def get_menu(self, restaurant: str, day: dt.date, lang: Lang) -> Menu:
        spec = resolve_restaurant(restaurant)
        return await self._cache.get_or_fetch(
            (spec.id, day, lang), lambda: self._fetch(spec, day, lang)
        )

    async def get_menus(
        self, restaurants: list[str] | None, day: dt.date, lang: Lang
    ) -> list[Menu]:
        """Menus for the given restaurants (duplicates dropped); all restaurants if none given."""
        if restaurants:
            ids = list(dict.fromkeys(resolve_restaurant(name).id for name in restaurants))
        else:
            ids = [r.id for r in RESTAURANTS]
        return list(await asyncio.gather(*(self.get_menu(i, day, lang) for i in ids)))

    async def _fetch(self, spec: Restaurant, day: dt.date, lang: Lang) -> Menu:
        adapter = self._adapters.get(spec.provider)
        if adapter is None:
            return _error_menu(
                spec, day, lang, f"Adapter for provider '{spec.provider}' is not implemented yet"
            )
        try:
            return await adapter.fetch_menu(spec, day, lang, self._http())
        except Exception as exc:
            logger.warning("Menu fetch failed for %s on %s", spec.id, day, exc_info=True)
            return _error_menu(spec, day, lang, f"Failed to fetch menu: {_describe(exc)}")

    @staticmethod
    def find_dish(menu: Menu, dish: str) -> Dish:
        """Find a dish by id, exact name, name substring, then fuzzy name (slug-insensitive)."""
        if not menu.dishes:
            detail = f": {menu.error}" if menu.error else ""
            raise ValueError(
                f"No dishes available for {menu.restaurant_name} on {menu.date}{detail}"
            )
        query = dish.strip()
        for candidate in menu.dishes:
            if candidate.id.lower() == query.lower():
                return candidate
        slug = slugify(query)
        if not slug:
            raise ValueError(_dish_not_found(menu, dish))
        named = [(d, slugify(d.name)) for d in menu.dishes]
        for candidate, name in named:
            if name == slug:
                return candidate
        contained = [(d, name) for d, name in named if slug in name]
        if contained:
            return max(contained, key=lambda item: _ratio(slug, item[1]))[0]
        close = difflib.get_close_matches(slug, [name for _, name in named], n=1, cutoff=0.6)
        if close:
            return next(d for d, name in named if name == close[0])
        raise ValueError(_dish_not_found(menu, dish))

    @staticmethod
    def search_by_macros(
        menus: Sequence[Menu],
        *,
        min_protein_g: float | None = None,
        max_kcal: float | None = None,
        min_kcal: float | None = None,
        max_fat_g: float | None = None,
        max_carbs_g: float | None = None,
        diets: list[str] | None = None,
        sort_by: SortBy = "protein_desc",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Filter and sort dishes that have whole-dish macros. Pure function: no I/O.

        Multi-component dishes (nutrition per component) are not considered: their per-100 g
        values cannot be summed into a dish total. A dish lacking a field that an active filter or
        sort needs is excluded (or sorted last).
        """
        if limit < 1:
            raise ValueError("limit must be at least 1")
        wanted_diets = {d.strip().lower() for d in diets or [] if d.strip()}

        pool: list[tuple[Menu, Dish, Macros]] = []
        for menu in menus:
            for dish in menu.dishes:
                if dish.macros is not None and not dish.macros.is_empty():
                    pool.append((menu, dish, dish.macros))
        mixed_basis = {macros.basis for _, _, macros in pool} >= {"portion", "100g"}

        ranked: list[tuple[tuple[bool, float], dict[str, Any]]] = []
        for menu, dish, macros in pool:
            kcal = macros.energy_kcal
            if not (
                _at_least(macros.protein_g, min_protein_g)
                and _at_least(kcal, min_kcal)
                and _at_most(kcal, max_kcal)
                and _at_most(macros.fat_g, max_fat_g)
                and _at_most(macros.carbohydrates_g, max_carbs_g)
                and wanted_diets <= {d.lower() for d in dish.diets}
            ):
                continue
            row: dict[str, Any] = {
                "restaurant_id": menu.restaurant_id,
                "restaurant_name": menu.restaurant_name,
                "dish": dish.model_dump(mode="json"),
                "macro_basis": macros.basis,
            }
            ranked.append((_sort_key(sort_by, macros.protein_g, kcal), row))

        ranked.sort(key=lambda item: item[0])
        rows = [row for _, row in ranked[:limit]]
        if mixed_basis:
            for row in rows:
                row["note"] = MIXED_BASIS_NOTE
        return rows


def _error_menu(spec: Restaurant, day: dt.date, lang: Lang, message: str) -> Menu:
    return Menu(
        restaurant_id=spec.id,
        restaurant_name=spec.name,
        date=day,
        lang=lang,
        source_url=spec.url,
        error=message,
    )


def _describe(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def _dish_not_found(menu: Menu, dish: str) -> str:
    names = ", ".join(d.name for d in menu.dishes)
    return (
        f"No dish matching {dish!r} at {menu.restaurant_name} on {menu.date}. "
        f"Available dishes: {names}"
    )


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _at_least(value: float | None, minimum: float | None) -> bool:
    return minimum is None or (value is not None and value >= minimum)


def _at_most(value: float | None, maximum: float | None) -> bool:
    return maximum is None or (value is not None and value <= maximum)


def _sort_key(sort_by: SortBy, protein: float | None, kcal: float | None) -> tuple[bool, float]:
    """(missing, value): dishes missing the sort field go last; ``*_desc`` sorts negate."""
    value: float | None
    if sort_by == "protein_desc":
        value = protein
    elif sort_by == "protein_per_kcal_desc":
        value = protein / kcal if protein is not None and kcal else None
    else:
        value = kcal
    if value is None:
        return (True, 0.0)
    return (False, -value if sort_by.endswith("_desc") else value)
