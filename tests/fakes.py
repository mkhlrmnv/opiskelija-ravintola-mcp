"""Test doubles: a scripted menu adapter and small builders for dishes and menus."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Mapping

import httpx

from ravintola_mcp.adapters.base import MenuAdapter
from ravintola_mcp.models import Dish, Lang, Macros, Menu, Restaurant

DAY = dt.date(2026, 11, 2)


class FakeAdapter(MenuAdapter):
    """Serves canned menus keyed by restaurant id; can fail or delay per restaurant."""

    def __init__(
        self,
        provider: str,
        menus: Mapping[str, Menu] | None = None,
        failures: Mapping[str, Exception] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.provider = provider
        self.menus = dict(menus or {})
        self.failures = dict(failures or {})
        self.delay = delay
        self.calls: list[tuple[str, dt.date, Lang]] = []

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        self.calls.append((restaurant.id, day, lang))
        if self.delay:
            await asyncio.sleep(self.delay)
        if restaurant.id in self.failures:
            raise self.failures[restaurant.id]
        menu = self.menus.get(restaurant.id)
        if menu is None:
            return Menu(
                restaurant_id=restaurant.id,
                restaurant_name=restaurant.name,
                date=day,
                lang=lang,
                notes=["closed"],
            )
        return menu.model_copy(update={"date": day, "lang": lang})


def make_dish(
    dish_id: str,
    name: str,
    *,
    macros: Macros | None = None,
    diets: list[str] | None = None,
) -> Dish:
    return Dish(id=dish_id, name=name, macros=macros, diets=diets or [])


def make_menu(
    restaurant_id: str,
    restaurant_name: str,
    dishes: list[Dish] | None = None,
    *,
    day: dt.date = DAY,
    lang: Lang = "en",
    error: str | None = None,
) -> Menu:
    return Menu(
        restaurant_id=restaurant_id,
        restaurant_name=restaurant_name,
        date=day,
        lang=lang,
        dishes=dishes or [],
        error=error,
    )
