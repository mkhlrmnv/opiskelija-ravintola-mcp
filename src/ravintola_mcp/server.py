"""MCP server (stdio) for Finnish student-restaurant lunch menus and per-dish macros."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from ravintola_mcp.dates import resolve_date
from ravintola_mcp.models import Lang, Macros, Menu
from ravintola_mcp.restaurants import RESTAURANTS
from ravintola_mcp.service import MenuService, SortBy


@asynccontextmanager
async def _lifespan(_app: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await _service.aclose()


mcp = FastMCP("opiskelija-ravintola", lifespan=_lifespan)
_service = MenuService()


def set_service(service: MenuService) -> None:
    """Replace the service used by the tools (for tests or embedding)."""
    global _service
    _service = service


def _menu_to_dict(menu: Menu, *, include_macros: bool) -> dict[str, Any]:
    data = menu.model_dump(mode="json")
    data["macros_available"] = menu.macros_available
    if not include_macros:
        for dish in data["dishes"]:
            del dish["macros"]
            for component in dish["components"]:
                del component["macros"]  # component names stay: they describe the menu
    return data


def _has_values(macros: Macros | None) -> bool:
    return macros is not None and not macros.is_empty()


async def _menus_response(
    restaurant: str | None, date: str | None, lang: Lang, *, include_macros: bool
) -> dict[str, Any] | list[dict[str, Any]]:
    day = resolve_date(date)
    if restaurant is None or not restaurant.strip():
        menus = await _service.get_menus(None, day, lang)
        return [_menu_to_dict(m, include_macros=include_macros) for m in menus]
    menu = await _service.get_menu(restaurant, day, lang)
    return _menu_to_dict(menu, include_macros=include_macros)


@mcp.tool()
def list_restaurants() -> list[dict[str, Any]]:
    """List the supported student restaurants (Otaniemi and Helsinki city centre).

    Each entry has an id, display name, aliases, campus and public menu page. The id, name or
    any alias can be passed as the `restaurant` argument of the other tools.
    """
    return [
        {"id": r.id, "name": r.name, "aliases": r.aliases, "campus": r.campus, "url": r.url}
        for r in RESTAURANTS
    ]


@mcp.tool()
async def get_menu(
    restaurant: str | None = None, date: str | None = None, lang: Lang = "en"
) -> dict[str, Any] | list[dict[str, Any]]:
    """Get the lunch menu of one restaurant, or of all restaurants if `restaurant` is omitted.

    Dishes are returned without nutrition values (component names are kept); use get_full_menu
    for macros, or get_macros for one dish. `restaurant` takes an id, name or alias (e.g.
    'a-bloc', 'A Bloc', 'täffä', 'kaivopiha'). `date` defaults to today (Europe/Helsinki) and
    accepts 'today', 'tomorrow', 'yesterday', an English or Finnish weekday name (next
    occurrence, e.g. 'friday' or 'perjantai') or an ISO date 'YYYY-MM-DD'. `lang` is 'en'
    (default) or 'fi', the language of
    the dish texts. A menu with a non-null `error` could not be fetched; `macros_available` says
    whether the site publishes nutrition values for the menu.
    """
    return await _menus_response(restaurant, date, lang, include_macros=False)


@mcp.tool()
async def get_full_menu(
    restaurant: str | None = None, date: str | None = None, lang: Lang = "en"
) -> dict[str, Any] | list[dict[str, Any]]:
    """Get lunch menus including per-dish nutrition values (macros) where the site publishes them.

    Same arguments as get_menu: `restaurant` is optional (all restaurants when omitted). `date`
    defaults to today (Europe/Helsinki) and accepts 'today', 'tomorrow', 'yesterday', an English
    or Finnish weekday name (next occurrence, e.g. 'friday' or 'perjantai') or an ISO date
    'YYYY-MM-DD'. `lang` is 'en' (default) or 'fi'. Each dish's `macros` is null when unpublished;
    `macros.basis` says whether values are per portion or per 100 g. Multi-component dishes have
    `macros` null and list the per-100 g nutrition of each part in `components` (name and macros).
    """
    return await _menus_response(restaurant, date, lang, include_macros=True)


@mcp.tool()
async def get_macros(
    restaurant: str, dish: str, date: str | None = None, lang: Lang = "en"
) -> dict[str, Any]:
    """Get the nutrition values of one dish on a given day.

    `dish` matches a dish id, its exact name, or part of its name (fuzzy matching is used too);
    if nothing matches, the error lists the available dish names. `date` defaults to today
    (Europe/Helsinki) and accepts 'today', 'tomorrow', 'yesterday', an English or Finnish weekday
    name (next occurrence) or an ISO date 'YYYY-MM-DD'. `macros` is the nutrition of the dish as
    a whole, null when the site publishes none. Multi-component dishes have `macros` null and
    list the per-100 g nutrition of each part in `components` (name and macros; a part's macros
    are null when unpublished). `message` explains when neither form of nutrition is published.
    """
    day = resolve_date(date)
    menu = await _service.get_menu(restaurant, day, lang)
    if menu.error:
        raise ValueError(f"Menu for {menu.restaurant_name} on {day} is unavailable: {menu.error}")
    found = _service.find_dish(menu, dish)
    has_macros = _has_values(found.macros)
    has_component_macros = any(_has_values(c.macros) for c in found.components)
    return {
        "restaurant": menu.restaurant_id,
        "restaurant_name": menu.restaurant_name,
        "date": day.isoformat(),
        "dish_id": found.id,
        "dish_name": found.name,
        "macros": found.macros.model_dump(mode="json") if has_macros else None,
        "components": [c.model_dump(mode="json") for c in found.components],
        "message": None
        if has_macros or has_component_macros
        else "The site publishes no nutrition values for this dish.",
    }


@mcp.tool()
async def search_dishes_by_macros(
    date: str | None = None,
    restaurants: list[str] | None = None,
    min_protein_g: float | None = None,
    max_kcal: float | None = None,
    min_kcal: float | None = None,
    max_fat_g: float | None = None,
    max_carbs_g: float | None = None,
    diets: list[str] | None = None,
    sort_by: SortBy = "protein_desc",
    limit: int = 20,
    lang: Lang = "en",
) -> list[dict[str, Any]]:
    """Find dishes that match nutrition targets on one day, across one or more restaurants.

    Only dishes with published whole-dish macros are considered; a dish missing a value that a
    filter needs is left out. Multi-component dishes (nutrition published per component) are not
    searchable; use get_macros to see their components. `restaurants` takes ids, names or
    aliases (all restaurants when omitted). `diets` are diet codes as published by the sites
    (e.g. 'G', 'L', 'VEG'); all of them must be present. `sort_by` is one of 'protein_desc'
    (default), 'kcal_asc', 'kcal_desc' or 'protein_per_kcal_desc'. `date` defaults to today
    (Europe/Helsinki) and accepts 'today', 'tomorrow', 'yesterday', an English or Finnish weekday
    name (next occurrence) or an ISO date 'YYYY-MM-DD'. Restaurants whose menu could not be
    fetched are skipped. `lang` is 'en' (default) or 'fi'. Each row has restaurant_id,
    restaurant_name, dish and macro_basis; a `note` is added to every row when the results mix
    per-portion and per-100 g values.
    """
    day = resolve_date(date)
    menus = await _service.get_menus(restaurants, day, lang)
    return _service.search_by_macros(
        menus,
        min_protein_g=min_protein_g,
        max_kcal=max_kcal,
        min_kcal=min_kcal,
        max_fat_g=max_fat_g,
        max_carbs_g=max_carbs_g,
        diets=diets,
        sort_by=sort_by,
        limit=limit,
    )


def main() -> None:
    mcp.run(transport="stdio")
