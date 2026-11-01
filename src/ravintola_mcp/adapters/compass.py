"""Compass Group (FoodCo) adapter for restaurants on www.compass-group.fi (Espoo, Aalto).

Endpoints, all plain GET and found in the restaurant page's JS bundle, checked live
(details in docs/research/compass.md):

- ``/menuapi/day-menus?costCenter=<id>&language=fi|en&date=YYYY-MM-DD``: one day's menu.
- ``/menuapi/recipes/<recipeId>?language=fi|en``: nutrition per recipe, always per 100 g.
- ``/api/restaurant-search`` and ``/api/restaurant-search/details``: directory entry with
  free-text opening and lunch hours.

Mapping rules:
- Each meal line in a menu package becomes one Dish; the package name is its category.
- A meal inside a set (bundle) stays its own Dish, so it keeps its own macros. The set's
  display name goes into the description. Macros of a set are not summed: values are per
  100 g and no portion weights are published.
- Packages without meal lines (price-only headers, empty buffet stubs) yield no dishes.
  Every package that has meal lines is served at lunch, so none is filtered out.
- Diet codes are kept as published, except ``A`` (contains allergens), which goes to
  ``allergens`` because the site publishes no per-allergen names.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, parse_number, slugify
from ravintola_mcp.models import Dish, Lang, Macros, Menu, Restaurant

BASE_URL = "https://www.compass-group.fi"
MAX_RECIPE_REQUESTS = 8
MAX_DIRECTORY_CANDIDATES = 3
ALLERGEN_FLAG = "A"

# Recipe nutrient name -> (Macros field, unit the site publishes it in).
NUTRIENTS: dict[str, tuple[str, str]] = {
    "EnergyKcal": ("energy_kcal", "kcal"),
    "EnergyKj": ("energy_kj", "kj"),
    "Protein": ("protein_g", "g"),
    "Carbohydrates": ("carbohydrates_g", "g"),
    "Sugar": ("sugars_g", "g"),
    "Fat": ("fat_g", "g"),
    "FatSaturated": ("saturated_fat_g", "g"),
    "Fiber": ("fibre_g", "g"),
    "Salt": ("salt_g", "g"),
}

_BLOCK_TAG = re.compile(r"<\s*/?(?:br|p|li|div|h[1-6])\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


class _NotFound(AdapterError):
    """HTTP 404 from the Compass API: the resource does not exist, which is not a failure."""


@dataclass(frozen=True)
class _Line:
    """One meal line of a menu package, before ids and macros are attached."""

    category: str | None
    name: str
    description: str | None
    diets: tuple[str, ...]
    allergens: tuple[str, ...]
    price: str | None
    recipe_id: int


class CompassAdapter(MenuAdapter):
    provider = "compass"

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        cost_number = restaurant.config.get("cost_number")
        if not cost_number:
            raise AdapterError(f"{restaurant.id}: no cost_number in the registry config")

        notes: list[str] = []
        content_lang: Lang = lang
        try:
            day_payload = await _day_menu(client, cost_number, day, lang)
        except AdapterError:
            if lang != "en":
                raise
            day_payload = await _day_menu(client, cost_number, day, "fi")
            content_lang = "fi"
            notes.append("English menu unavailable; showing the Finnish menu.")

        lines = _lines(day_payload.get("menuPackages") or [])
        recipe_ids = {line.recipe_id for line in lines if line.recipe_id}
        (macros, failures), hours = await asyncio.gather(
            _recipe_macros(client, recipe_ids, content_lang),
            _lunch_hours(client, restaurant, cost_number, lang),
        )
        if failures:
            notes.append(f"Nutrition could not be fetched for {failures} recipe(s).")

        dishes = _dishes(lines, macros)
        if not dishes:
            # Closed days and unknown cost numbers look the same to the API, so say both.
            notes.append(
                "Free-text menu, not parsed."
                if day_payload.get("html")
                else "Closed, or no lunch menu published for this day."
            )

        return Menu(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            date=day,
            lang=content_lang,
            dishes=dishes,
            lunch_hours=hours,
            source_url=restaurant.url,
            notes=notes,
        )


async def _get_json(
    client: httpx.AsyncClient, path: str, params: Mapping[str, str | int]
) -> dict[str, Any]:
    response = await client.get(f"{BASE_URL}{path}", params=params)
    if response.status_code == 404:
        raise _NotFound(f"Compass API {path} answered HTTP 404")
    if response.status_code != 200:
        raise AdapterError(f"Compass API {path} answered HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AdapterError(f"Compass API {path} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AdapterError(f"Compass API {path} returned an unexpected payload")
    return payload


async def _day_menu(
    client: httpx.AsyncClient, cost_number: str, day: dt.date, lang: Lang
) -> dict[str, Any]:
    return await _get_json(
        client,
        "/menuapi/day-menus",
        {"costCenter": cost_number, "language": lang, "date": day.isoformat()},
    )


def _lines(packages: list[dict[str, Any]]) -> list[_Line]:
    lines: list[_Line] = []
    for package in packages:
        category = _squash(package.get("name")) or None
        price = _squash(package.get("price")) or None
        set_names = {
            str(bundle.get("id")): _squash(bundle.get("displayName") or bundle.get("name"))
            for bundle in package.get("bundles") or []
        }
        for meal in package.get("meals") or []:
            name = _squash(meal.get("name"))
            if not name:
                continue
            bundle_id = meal.get("bundleId")
            set_name = set_names.get(str(bundle_id)) if bundle_id else None
            codes = _codes(meal.get("diets") or [])
            lines.append(
                _Line(
                    category=category,
                    name=name,
                    description=f"Part of set: {set_name}" if set_name else None,
                    diets=tuple(c for c in codes if c != ALLERGEN_FLAG),
                    allergens=(ALLERGEN_FLAG,) if ALLERGEN_FLAG in codes else (),
                    price=price,
                    recipe_id=int(meal.get("recipeId") or 0),
                )
            )
    return lines


def _codes(raw: list[Any]) -> list[str]:
    """Split diet entries; the site sometimes joins codes with a space or comma ('A ILM')."""
    return list(dict.fromkeys(c for item in raw for c in re.split(r"[\s,]+", str(item)) if c))


def _dishes(lines: list[_Line], macros: dict[int, Macros]) -> list[Dish]:
    used: set[str] = set()
    dishes: list[Dish] = []
    for line in lines:
        base = slugify(f"{line.category or ''} {line.name}") or "dish"
        dish_id, suffix = base, 1
        while dish_id in used:
            suffix += 1
            dish_id = f"{base}-{suffix}"
        used.add(dish_id)
        dishes.append(
            Dish(
                id=dish_id,
                name=line.name,
                category=line.category,
                description=line.description,
                diets=list(line.diets),
                allergens=list(line.allergens),
                price=line.price,
                macros=macros.get(line.recipe_id),
            )
        )
    return dishes


async def _recipe_macros(
    client: httpx.AsyncClient, recipe_ids: set[int], lang: Lang
) -> tuple[dict[int, Macros], int]:
    """Nutrition per recipe id, plus how many lookups failed for reasons other than 404."""
    gate = asyncio.Semaphore(MAX_RECIPE_REQUESTS)

    async def fetch(recipe_id: int) -> tuple[int, Macros | None, bool]:
        async with gate:
            try:
                recipe = await _get_json(
                    client, f"/menuapi/recipes/{recipe_id}", {"language": lang}
                )
            except _NotFound:
                return recipe_id, None, False
            except (AdapterError, httpx.HTTPError):
                return recipe_id, None, True
        return recipe_id, _macros(recipe), False

    results = await asyncio.gather(*(fetch(rid) for rid in sorted(recipe_ids)))
    macros = {rid: found for rid, found, _ in results if found is not None}
    return macros, sum(failed for *_, failed in results)


def _macros(recipe: dict[str, Any]) -> Macros | None:
    fields: dict[str, float] = {}
    for item in recipe.get("nutritionalValues") or []:
        spec = NUTRIENTS.get(str(item.get("name")))
        if spec is None or str(item.get("unit", "")).casefold() != spec[1]:
            continue
        value = parse_number(item.get("amount"))
        if value is not None:
            fields[spec[0]] = value
    return Macros(basis="100g", **fields) if fields else None


async def _lunch_hours(
    client: httpx.AsyncClient, restaurant: Restaurant, cost_number: str, lang: Lang
) -> str | None:
    """Best effort: the directory's free-text hours. Errors leave them unset."""
    try:
        details = await _directory_details(client, restaurant, cost_number, lang)
    except (AdapterError, httpx.HTTPError):
        return None
    if details is None:
        return None
    return _hours_text(str(details.get("openingHoursHtml") or "")) or None


async def _directory_details(
    client: httpx.AsyncClient, restaurant: Restaurant, cost_number: str, lang: Lang
) -> dict[str, Any] | None:
    """Directory entry whose costCenter matches ours (name search finds the content id)."""
    configured = restaurant.config.get("content_id")
    if configured:
        candidates = [configured]
    else:
        search = await _get_json(
            client,
            "/api/restaurant-search",
            {"q": restaurant.name, "language": lang, "pageSize": 10, "page": 1},
        )
        wanted = restaurant.name.casefold()
        candidates = [
            str(hit["contentId"])
            for hit in search.get("hits") or []
            if hit.get("contentId") and str(hit.get("title", "")).casefold().startswith(wanted)
        ]
    for content_id in candidates[:MAX_DIRECTORY_CANDIDATES]:
        details = await _get_json(
            client, "/api/restaurant-search/details", {"id": content_id, "language": lang}
        )
        if str(details.get("costCenter")) == cost_number:
            return details
    return None


def _hours_text(markup: str) -> str:
    """Flatten the hours HTML into '; '-separated lines, keeping the outlet headings."""
    pieces = (_squash(_TAG.sub("", piece)) for piece in _BLOCK_TAG.split(markup))
    return "; ".join(dict.fromkeys(p for p in pieces if p))


def _squash(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
