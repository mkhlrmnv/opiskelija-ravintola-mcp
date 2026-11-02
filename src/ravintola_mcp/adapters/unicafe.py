"""Unicafe adapter: the JSON list behind menu.unicafe.fi (Kaivopiha is one entry in it).

Verified 2026-11-02 (details in docs/research/unicafe.md):
- ``GET https://unicafe.fi/wp-json/swiss/v1/restaurants?lang=fi|en`` returns every Unicafe
  restaurant (about 1 MB). No filter works, so the parsed list is cached per language.
- Each restaurant has a ``slug`` and ``menuData.menus``: about two weeks of days, labelled
  ``"Ma 02.11."`` with no year. A closed day has ``data: []``.
- ``price.name`` is the menu line (``Lounas``, ``Vegaanilounas``, ``Lisäke``, ``Jälkiruoka``) and
  stays Finnish in every language. Side dishes and desserts are not lunch dishes.
- ``meta["0"]`` holds diet codes (G, L, M, VL, Veg, KELA, Ilmastovalinta), ``meta["1"]`` the
  allergens and ``meta["2"]`` repeats the climate flag.
- ``nutrition`` is one free-text string per dish, e.g. ``"Energia 481kJ, energia 115kcal, rasva
  4,0g, ..."``. The site labels it "Ravintoarvo 100g", so the values are per 100 g.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import time
from collections.abc import Callable
from functools import partial
from typing import Any

import httpx

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, parse_number, slugify
from ravintola_mcp.models import Dish, Lang, Macros, Menu, Restaurant

ENDPOINT = "https://unicafe.fi/wp-json/swiss/v1/restaurants"
CACHE_TTL_S = 600.0
# Menu lines that are not lunch dishes (the site's own UI treats them the same way).
NON_LUNCH_LINES = frozenset({"Lisäke", "Jälkiruoka"})
ANNOUNCEMENT_LINE = "Tiedote"
NO_MENU_NOTE = "No lunch menu is published for this day (closed, or not published yet)."
EN_FALLBACK_NOTE = "English menu unavailable; showing the Finnish menu."
NON_LUNCH_NOTE = "{count} side dish(es) or dessert(s) left out: only lunch dishes are listed."

# Nutrition label (lowercase, Finnish or English as published) -> Macros field. Energy is
# matched by its unit instead, because its label differs by language. Labels with a "<" value
# (an upper bound such as "<0,5g") are skipped.
NUTRIENT_FIELDS: dict[str, str] = {
    "rasva": "fat_g",
    "fat": "fat_g",
    "josta tyydyttynyttä rasvaa": "saturated_fat_g",
    "of which saturated fat": "saturated_fat_g",
    "hiilihydraatit": "carbohydrates_g",
    "carbohydrate": "carbohydrates_g",
    "josta sokereita": "sugars_g",
    "of which sugars": "sugars_g",
    "proteiini": "protein_g",
    "protein": "protein_g",
    "suola": "salt_g",
    "salt": "salt_g",
    "ravintokuitua": "fibre_g",
    "fibre": "fibre_g",
}
_NUTRIENT_RE = re.compile(
    r"^(?P<label>.+?)\s+(?P<value><?\d+(?:[.,]\d+)?)\s*(?P<unit>kJ|kcal|g)$", re.IGNORECASE
)
_DAY_LABEL_RE = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.")


class UnicafeAdapter(MenuAdapter):
    provider = "unicafe"

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, ttl_s: float = CACHE_TTL_S
    ) -> None:
        self._clock = clock
        self._ttl_s = ttl_s
        self._cache: dict[Lang, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        slug = restaurant.config.get("slug")
        if not slug:
            raise AdapterError(f"{restaurant.id}: no Unicafe slug in the registry config")
        if lang == "en":
            return await self._english_menu(restaurant, slug, day, client)
        return await self._menu(restaurant, slug, day, "fi", client)

    async def _english_menu(
        self, restaurant: Restaurant, slug: str, day: dt.date, client: httpx.AsyncClient
    ) -> Menu:
        try:
            english: Menu | None = await self._menu(restaurant, slug, day, "en", client)
        except AdapterError:
            english = None
        if english is not None and english.dishes:
            return english
        finnish = await self._menu(restaurant, slug, day, "fi", client)
        if not finnish.dishes:
            # Nothing to show in either language (closed day): keep the English notes if any.
            return english if english is not None else finnish
        finnish.notes.insert(0, EN_FALLBACK_NOTE)
        return finnish

    async def _menu(
        self, restaurant: Restaurant, slug: str, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        entries = await self._restaurant_entries(client, lang)
        entry = next((row for row in entries if row.get("slug") == slug), None)
        if entry is None:
            raise AdapterError(f"Unicafe has no restaurant with slug {slug!r} (lang={lang})")
        menu_data = _dict(entry.get("menuData"))
        days = _labelled_days(menu_data.get("menus"), day)
        lunch_hours = _lunch_hours(menu_data)
        build = partial(_build_menu, restaurant, day, lang, lunch_hours=lunch_hours)

        match = next((row for published, row in days if published == day), None)
        if match is None:
            dates = [published for published, _ in days]
            if not dates:
                return build(notes=["Unicafe publishes no menu for this restaurant."])
            span = f"{min(dates).isoformat()} to {max(dates).isoformat()}"
            return build(
                notes=[f"No menu is published for {day.isoformat()}; the feed covers {span}."]
            )

        dishes, skipped, announcements = _dishes(match.get("data"))
        notes: list[str] = []
        message = _text(match.get("message"))
        if message:
            notes.append(message)
        notes.extend(announcements)
        if not dishes:
            notes.append(NO_MENU_NOTE)
        if skipped:
            notes.append(NON_LUNCH_NOTE.format(count=skipped))
        return build(dishes=dishes, notes=notes)

    async def _restaurant_entries(
        self, client: httpx.AsyncClient, lang: Lang
    ) -> list[dict[str, Any]]:
        """All restaurants for one language; one download serves every date within the TTL."""
        fresh = self._fresh(lang)
        if fresh is not None:
            return fresh
        async with self._lock:
            fresh = self._fresh(lang)  # another request may have filled it while we waited
            if fresh is not None:
                return fresh
            entries = await _download(client, lang)
            self._cache[lang] = (self._clock(), entries)
            return entries

    def _fresh(self, lang: Lang) -> list[dict[str, Any]] | None:
        stored = self._cache.get(lang)
        if stored is None or self._clock() - stored[0] >= self._ttl_s:
            return None
        return stored[1]


def parse_nutrition(text: str) -> Macros | None:
    """Map a Unicafe nutrition string to per-100 g Macros; None when nothing usable is present."""
    values: dict[str, float] = {}
    for part in re.split(r",\s+", text.strip().rstrip(".")):
        match = _NUTRIENT_RE.match(part.strip())
        if match is None or match["value"].startswith("<"):
            continue
        number = parse_number(match["value"])
        if number is None:
            continue
        unit = match["unit"].lower()
        if unit == "kj":
            values["energy_kj"] = number
        elif unit == "kcal":
            values["energy_kcal"] = number
        elif (field := NUTRIENT_FIELDS.get(match["label"].lower())) is not None:
            values[field] = number
    return Macros(basis="100g", **values) if values else None


async def _download(client: httpx.AsyncClient, lang: Lang) -> list[dict[str, Any]]:
    try:
        response = await client.get(ENDPOINT, params={"lang": lang})
    except httpx.HTTPError as exc:
        raise AdapterError(f"Unicafe request failed: {exc}") from exc
    if response.status_code != 200:
        raise AdapterError(f"Unicafe returned HTTP {response.status_code} (lang={lang})")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AdapterError("Unicafe response is not JSON") from exc
    if not isinstance(payload, list):
        raise AdapterError("Unexpected Unicafe response shape")
    return [row for row in payload if isinstance(row, dict)]


def _labelled_days(menus: object, near: dt.date) -> list[tuple[dt.date, dict[str, Any]]]:
    days: list[tuple[dt.date, dict[str, Any]]] = []
    for row in menus if isinstance(menus, list) else []:
        if not isinstance(row, dict):
            continue
        published = _label_date(_text(row.get("date")), near)
        if published is not None:
            days.append((published, row))
    return days


def _label_date(label: str, near: dt.date) -> dt.date | None:
    """Turn a label such as 'Ma 02.11.' into a date; the feed omits the year, so take the
    candidate year closest to ``near`` (the requested day)."""
    match = _DAY_LABEL_RE.search(label)
    if match is None:
        return None
    candidates: list[dt.date] = []
    for year in (near.year - 1, near.year, near.year + 1):
        try:
            candidates.append(dt.date(year, int(match["month"]), int(match["day"])))
        except ValueError:
            continue
    return min(candidates, key=lambda candidate: abs((candidate - near).days), default=None)


def _dishes(items: object) -> tuple[list[Dish], int, list[str]]:
    """Lunch dishes of one day in published order, the count of side dishes and desserts left
    out, and the announcement lines ('Tiedote')."""
    dishes: list[Dish] = []
    used_ids: set[str] = set()
    skipped = 0
    announcements: list[str] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        price = _dict(item.get("price"))
        line = _text(price.get("name"))
        if not name:
            continue
        if line == ANNOUNCEMENT_LINE:
            announcements.append(name)
            continue
        if line in NON_LUNCH_LINES:
            skipped += 1
            continue
        meta = _dict(item.get("meta"))
        dishes.append(
            Dish(
                id=_unique_id(slugify(name) or "dish", used_ids),
                name=name,
                category=line or None,
                description=_text(item.get("ingredients")) or None,
                diets=_strings(meta.get("0")),
                allergens=_strings(meta.get("1")),
                price=_price_text(price.get("value")),
                macros=parse_nutrition(_text(item.get("nutrition"))),
            )
        )
    return dishes, skipped, announcements


def _lunch_hours(menu_data: dict[str, Any]) -> str | None:
    """Published lunch opening hours, e.g. 'Ma–Pe 11:00-19:45; La 11:30-17:00; Su Suljettu'."""
    lunch = _dict(_dict(menu_data.get("visitingHours")).get("lounas"))
    rows = lunch.get("items")
    parts = [
        f"{_text(row.get('label'))} {_text(row.get('hours'))}".strip()
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict) and _text(row.get("hours"))
    ]
    return "; ".join(parts) or None


def _build_menu(
    restaurant: Restaurant,
    day: dt.date,
    lang: Lang,
    *,
    lunch_hours: str | None,
    dishes: list[Dish] | None = None,
    notes: list[str] | None = None,
) -> Menu:
    return Menu(
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
        date=day,
        lang=lang,
        dishes=dishes or [],
        lunch_hours=lunch_hours,
        source_url=restaurant.url,
        notes=notes or [],
    )


def _price_text(value: object) -> str | None:
    """Price as published. Kaivopiha publishes none (an empty list); other Unicafe restaurants
    publish a dict of price groups such as ``{"student": "3.10", "graduate": "6.35"}``."""
    if not isinstance(value, dict):
        return None
    parts = [f"{group} {_text(price)}" for group, price in value.items() if _text(price)]
    return ", ".join(parts) or None


def _unique_id(base: str, used: set[str]) -> str:
    candidate, n = base, 2
    while candidate in used:
        candidate = f"{base}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_text(item) for item in value) if text]


def _text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""
