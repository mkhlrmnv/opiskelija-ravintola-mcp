"""Sodexo adapter: the public JSON feed behind www.sodexo.fi restaurant pages.

Verified 2026-11-01 (details in docs/research/sodexo.md):
- ``GET /ruokalistat/output/daily_json/{restaurant_id}/{YYYY-MM-DD}``; ``/en`` prefix for English.
  A closed or unpublished day returns ``"courses": []``.
- Courses carry ``title_fi``/``title_en``, ``category``, ``dietcodes``, ``price`` (three price
  columns, as published) and ``additionalDietInfo`` allergens (``allergens_fi``/``allergens_en``).
- Recipes (a course's components) carry ``nutrients``: one ``" | "`` separated string such as
  ``"Energia kj/Energia kj: 420.65 kj | Rasva/Rasva: 4.41 rasva | ..."``. Values are per 100 g.
  Each nutrient is identified by its unit token, since the labels are bilingual.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from typing import Any

import httpx

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, parse_number, slugify
from ravintola_mcp.models import Dish, DishComponent, Lang, Macros, Menu, Restaurant

BASE_URL = "https://www.sodexo.fi"
NO_MENU_NOTE = "No lunch menu is published for this day (closed, or not yet published)."
MULTI_COMPONENT_NOTE = (
    "Sodexo publishes nutrition per 100 g for each component of a dish. For the {count} "
    "multi-component dish(es), nutrition is listed per component in `components`; the dish "
    "itself has no macros."
)

# Sodexo unit token -> Macros field. Energy is published in kJ only; the kcal twin is filled in
# by the Macros model validator. Sugars are not published.
NUTRIENT_FIELDS: dict[str, str] = {
    "kj": "energy_kj",
    "proteiin": "protein_g",
    "hiilihyd": "carbohydrates_g",
    "rasva": "fat_g",
    "rasva-ty": "saturated_fat_g",
    "kuitu": "fibre_g",
    "suola": "salt_g",
}
_NUTRIENT_RE = re.compile(
    r"^(?P<label>[^:]+):\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>[^\s|]+)$"
)


def daily_url(restaurant_id: str, day: dt.date, lang: Lang) -> str:
    prefix = "/en" if lang == "en" else ""
    return f"{BASE_URL}{prefix}/ruokalistat/output/daily_json/{restaurant_id}/{day.isoformat()}"


def parse_macros(nutrients: str) -> Macros | None:
    """Map a Sodexo nutrient string to per-100 g Macros; None when no known nutrient is present.

    Values use a dot as decimal separator in practice; commas are accepted as well.
    """
    values: dict[str, float] = {}
    for part in nutrients.split("|"):
        match = _NUTRIENT_RE.match(part.strip())
        if match is None:
            continue
        field = NUTRIENT_FIELDS.get(match["unit"].lower())
        number = parse_number(match["value"])
        if field is not None and number is not None:
            values[field] = number
    if not values:
        return None
    return Macros(basis="100g", **values)


class SodexoAdapter(MenuAdapter):
    provider = "sodexo"

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        restaurant_id = restaurant.config.get("restaurant_id")
        if not restaurant_id:
            raise AdapterError(f"{restaurant.id}: no Sodexo restaurant_id configured")
        payload = await _get_json(client, daily_url(restaurant_id, day, lang))

        menu = Menu(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            date=day,
            lang=lang,
            source_url=restaurant.url,
        )
        courses = payload.get("courses")
        if not isinstance(courses, dict) or not courses:
            menu.notes.append(NO_MENU_NOTE)
            return menu

        used_ids: set[str] = set()
        english_missing = 0
        multi_component = 0
        for key in sorted(courses, key=_numeric_key):
            course = courses[key]
            if not isinstance(course, dict):
                continue
            title_fi = _text(course.get("title_fi"))
            title = title_fi or _text(course.get("title_en"))
            if not title:
                continue
            title_en = _text(course.get("title_en"))
            if lang == "en" and not title_en:
                english_missing += 1
            recipes = _recipes(course)
            components = [name for name in (_text(r.get("name")) for r in recipes) if name]
            if len(recipes) > 1:
                multi_component += 1
            # Per-100 g values only describe a dish when it has exactly one component; otherwise
            # each component keeps its own values.
            macros: Macros | None = None
            dish_components: list[DishComponent] = []
            if len(recipes) == 1:
                macros = parse_macros(_text(recipes[0].get("nutrients")))
            elif len(recipes) > 1:
                dish_components = _dish_components(recipes)
            menu.dishes.append(
                Dish(
                    id=_unique_id(slugify(title) or f"course-{key}", used_ids),
                    name=(title_en if lang == "en" else title_fi) or title,
                    category=_text(course.get("category")) or None,
                    description=", ".join(components) if len(components) > 1 else None,
                    diets=_split_list(course.get("dietcodes")),
                    allergens=_allergens(course, lang),
                    price=_text(course.get("price")) or None,
                    macros=macros,
                    components=dish_components,
                )
            )

        if not menu.dishes:
            menu.notes.append(NO_MENU_NOTE)
            return menu
        if english_missing == len(menu.dishes):
            menu.notes.append("English names are not published for this menu; Finnish shown.")
        elif english_missing:
            menu.notes.append(
                f"English names are missing for {english_missing} dish(es); "
                "Finnish shown for those."
            )
        if multi_component:
            menu.notes.append(MULTI_COMPONENT_NOTE.format(count=multi_component))
        return menu


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise AdapterError(f"Sodexo request failed: {exc}") from exc
    if response.status_code != 200:
        raise AdapterError(f"Sodexo returned HTTP {response.status_code} for {url}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AdapterError(f"Sodexo response is not JSON: {url}") from exc
    if not isinstance(payload, dict):
        raise AdapterError(f"Unexpected Sodexo response shape: {url}")
    return payload


def _numeric_key(key: str) -> int:
    return int(key) if key.isdigit() else 10**9


def _recipes(course: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    recipes = course.get("recipes")
    if not isinstance(recipes, dict):
        return []
    return [
        recipe
        for _, recipe in sorted(recipes.items(), key=lambda kv: _numeric_key(kv[0]))
        if isinstance(recipe, dict)
    ]


def _dish_components(recipes: list[Mapping[str, Any]]) -> list[DishComponent]:
    """Named recipes of a multi-component course, in published order, with their own macros."""
    parts: list[DishComponent] = []
    for recipe in recipes:
        name = _text(recipe.get("name"))
        if name:
            macros = parse_macros(_text(recipe.get("nutrients")))
            parts.append(DishComponent(name=name, macros=macros))
    return parts


def _allergens(course: Mapping[str, Any], lang: Lang) -> list[str]:
    """Course-level allergens (they include sauces and toppings), else the recipes' union."""
    fields = (f"allergens_{lang}", "allergens_fi")
    info = course.get("additionalDietInfo")
    if isinstance(info, dict):
        for field in fields:
            if _text(info.get(field)):
                return _split_list(info[field])
    found: dict[str, None] = {}
    for recipe in _recipes(course):
        for field in fields:
            if _text(recipe.get(field)):
                for allergen in _split_list(recipe[field]):
                    found.setdefault(allergen)
                break
    return list(found)


def _unique_id(base: str, used: set[str]) -> str:
    candidate, n = base, 2
    while candidate in used:
        candidate = f"{base}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def _text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _split_list(value: object) -> list[str]:
    return [item for item in (part.strip() for part in _text(value).split(",")) if item]
