"""Täffä (Teknologföreningen, Otaniemi) adapter: the weekly JSON feed behind lunch.tf.fi.

Verified 2026-11-02 (details in docs/research/taffa.md):
- ``GET https://newapi.tf.fi/taffa/{fi,en}/json/week/`` returns a JSON list with one object per
  weekday of the current week: ``day`` (ISO date), ``dayName`` and one key per menu line, whose
  value is the dish text with its diet codes in a trailing parenthesis.
- The ``?date=`` parameter is ignored and dated paths fail, so only the current week is served.
- The English feed has the same days and lines, with English tags and occasional ``Unnamed
  dish`` placeholders. Diet codes are the same in both languages, so they come from the Finnish
  feed.
- The feed publishes no nutrition, prices or opening hours.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from typing import Any, Final

import httpx

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, slugify
from ravintola_mcp.models import Dish, Lang, Menu, Restaurant

BASE_URL: Final = "https://newapi.tf.fi/taffa"
_META_KEYS: Final = frozenset({"day", "dayName"})
_PLACEHOLDER_NAMES: Final = frozenset({"unnamed dish"})
_TAG_GROUP: Final = re.compile(r"\s*\(([^()]*)\)\s*$")
# Tags that can trail a dish, in Finnish and English. A trailing parenthesis is only read as tags
# when it holds one of these, so names such as "Hernekeitto (myös vegaani)" stay intact.
_KNOWN_TAGS: Final = frozenset(
    {
        "a",
        "g",
        "km",
        "l",
        "m",
        "vl",
        "veg",
        "soijaton",
        "ei sisällä pähkinöitä",
        "contains allergens",
        "contains no eggs",
        "contains no nuts",
        "gluten free",
        "lactose free",
        "low lactose",
        "milk free",
        "soy free",
        "vegan",
    }
)
# Finnish menu line -> English menu line. The keys differ by language, and a week may add the
# "Leivonnaiset" / "Pastry" line.
_FI_TO_EN_CATEGORY: Final[dict[str, str]] = {
    "Liha/kala": "Fish/meat",
    "Kasvisruoka": "Vegetarian option",
    "Delisalaatti": "Salad",
    "Keitto": "Soup",
    "A la carte": "A la carte",
    "Leivonnaiset": "Pastry",
}
_EN_TO_FI_CATEGORY: Final[dict[str, str]] = {en: fi for fi, en in _FI_TO_EN_CATEGORY.items()}

NO_MENU_NOTE = "No lunch menu is listed for this day. The restaurant may be closed."
NO_ENGLISH_NOTE = "No English menu for this date; showing the Finnish menu."
NO_FEED_DAYS_NOTE = "Täffä's menu feed lists no days, so no menu is available for {date}."
OUT_OF_WEEK_NOTE = (
    "Täffä's menu feed only covers the current week ({first} to {last}); "
    "no menu is available for {date}."
)


class TaffaAdapter(MenuAdapter):
    provider = "taffa"

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        fi_days = await _load_week(client, "fi")
        fi_entry = _find_day(fi_days, day)
        entry, menu_lang = fi_entry, lang
        notes: list[str] = []
        if lang == "en":
            en_entry = _find_day(await _load_week(client, "en"), day)
            if en_entry is not None:
                entry = en_entry
            elif fi_entry is not None:
                menu_lang = "fi"
                notes.append(NO_ENGLISH_NOTE)
        url = week_url(menu_lang)

        dishes, english_fallbacks = (
            _dishes(entry, fi_entry, menu_lang) if entry is not None else ([], 0)
        )
        if not dishes:
            notes.append(_missing_day_note(day, fi_days))
        elif english_fallbacks == len(dishes):
            notes.append("English names are not published for this menu; Finnish shown.")
        elif english_fallbacks:
            notes.append(
                f"English names are missing for {english_fallbacks} dish(es); "
                "Finnish shown for those."
            )
        return Menu(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            date=day,
            lang=menu_lang,
            dishes=dishes,
            source_url=url,
            notes=notes,
        )


def week_url(lang: Lang) -> str:
    return f"{BASE_URL}/{lang}/json/week/"


async def _load_week(client: httpx.AsyncClient, lang: Lang) -> list[Mapping[str, Any]]:
    url = week_url(lang)
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise AdapterError(f"Täffä request failed: {exc}") from exc
    if response.status_code != 200:
        raise AdapterError(f"Täffä returned HTTP {response.status_code} for {url}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AdapterError(f"Täffä response is not JSON: {url}") from exc
    if not isinstance(payload, list) or not all(isinstance(entry, dict) for entry in payload):
        raise AdapterError(f"Unexpected Täffä response shape: {url}")
    return payload


def _entry_date(entry: Mapping[str, Any]) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(entry.get("day", "")))
    except ValueError:
        return None


def _find_day(days: list[Mapping[str, Any]], day: dt.date) -> Mapping[str, Any] | None:
    return next((entry for entry in days if _entry_date(entry) == day), None)


def _missing_day_note(day: dt.date, fi_days: list[Mapping[str, Any]]) -> str:
    """Explain a day without dishes: closed inside the feed's week, outside it otherwise."""
    dates = sorted(date for date in map(_entry_date, fi_days) if date is not None)
    if not dates:
        return NO_FEED_DAYS_NOTE.format(date=f"{day:%d.%m.%Y}")
    if dates[0] <= day <= dates[-1]:
        return NO_MENU_NOTE
    return OUT_OF_WEEK_NOTE.format(
        first=f"{dates[0]:%d.%m.%Y}", last=f"{dates[-1]:%d.%m.%Y}", date=f"{day:%d.%m.%Y}"
    )


def _dishes(
    entry: Mapping[str, Any], fi_entry: Mapping[str, Any] | None, lang: Lang
) -> tuple[list[Dish], int]:
    """Dishes of one day, and how many English names fell back to the Finnish line."""
    fi_lines = _lines(fi_entry) if fi_entry is not None else {}
    dishes: list[Dish] = []
    used_ids: set[str] = set()
    fallbacks = 0
    for category, text in _lines(entry).items():
        name, diets = _split_tags(text)
        if lang == "en":
            # Codes come from the Finnish line; the English tags are only used for display.
            fi_name, diets = _split_tags(fi_lines.get(_EN_TO_FI_CATEGORY.get(category, ""), ""))
            if fi_name and (not name or name.lower() in _PLACEHOLDER_NAMES):
                name = fi_name
                fallbacks += 1
        if not name:
            continue
        dishes.append(
            Dish(
                id=_unique_id(slugify(name) or "dish", used_ids),
                name=name,
                category=category,
                diets=diets,
            )
        )
    return dishes, fallbacks


def _lines(entry: Mapping[str, Any]) -> dict[str, str]:
    """Menu lines of one day in published order: category -> dish text (blank lines dropped)."""
    return {
        key: _text(value) for key, value in entry.items() if key not in _META_KEYS and _text(value)
    }


def _split_tags(text: str) -> tuple[str, list[str]]:
    """Dish name and trailing diet codes, e.g. ``'Kana (A, G)'`` -> ``('Kana', ['A', 'G'])``."""
    match = _TAG_GROUP.search(text)
    if match is None:
        return text, []
    tags = [tag.strip() for tag in match[1].split(",") if tag.strip()]
    if not any(tag.lower() in _KNOWN_TAGS for tag in tags):
        return text, []
    return text[: match.start()].strip(), tags


def _unique_id(base: str, used: set[str]) -> str:
    candidate, n = base, 2
    while candidate in used:
        candidate = f"{base}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def _text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""
