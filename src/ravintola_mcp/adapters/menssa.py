"""Menssa adapter: the weekly lunch list on https://menssa.fi/lounas/ (Otaniemi).

Verified 2026-11-02 (details in docs/research/menssa.md):
- The WordPress page renders the current Monday-Friday list on the server. Each weekday is a
  section headed by its Finnish weekday name and carrying a ``d.m.`` date line; each dish has a
  Finnish name, an English twin (``.lms-front-en-name``) and diet codes. Nothing is priced per
  dish: student prices are listed per lunch type.
- The page has no date parameter and shows one week only. Other days get empty dishes and a note.
- The site publishes no nutrition data (page or ``/wp-json/lms/v1``), so no macros are set.
- The pizza table on the same page is a standing à la carte offer, not lunch: it is not listed
  as dishes, only mentioned in a note.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Final

import httpx
from bs4 import BeautifulSoup, Tag

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, slugify
from ravintola_mcp.models import Dish, Lang, Menu, Restaurant

MENU_URL: Final = "https://menssa.fi/lounas/"
NO_MENU_NOTE: Final = (
    "No lunch menu is published for this day. menssa.fi lists one Monday-Friday week at a time."
)
PIZZA_NOTE: Final = "Pizzas are also available à la carte (see menssa.fi/lounas/)."
FI_WEEKDAYS: Final = frozenset({"maanantai", "tiistai", "keskiviikko", "torstai", "perjantai"})
# Codes from the legend on menssa.fi/menu/ that name an allergen; the other codes (G, L, M, VL,
# "vegan", ...) are diets.
ALLERGEN_CODES: Final = frozenset({"K", "KA", "PA", "PÄ", "SE", "SI", "SM", "SO", "VS"})
_DATE_LINE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.\s*$")  # "2.11."
_STUDENT_LABEL = re.compile(r"opiskelij|student", re.IGNORECASE)


class MenssaAdapter(MenuAdapter):
    provider = "menssa"

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        soup = BeautifulSoup(await _get_page(client), "html.parser")
        menu = Menu(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            date=day,
            lang=lang,
            source_url=MENU_URL,
        )
        sections = _weekday_sections(soup)
        if not sections:
            raise AdapterError(
                f"Menssa lunch list not found on {MENU_URL}; layout may have changed"
            )

        section = next((s for s in sections if _published_on(s, day)), None)
        rows = section.select(".lms-front-dish") if section is not None else []
        if not rows:
            menu.notes.append(NO_MENU_NOTE)
            return menu

        used_ids: set[str] = set()
        dishes: list[Dish] = []
        english_missing = 0
        for row in rows:
            name_fi = _text(row.select_one(".lms-front-dish-name"))
            if not name_fi:
                continue
            name_en = _text(row.select_one(".lms-front-en-name"))
            if lang == "en" and not name_en:
                english_missing += 1
            diets, allergens = _codes(row)
            dishes.append(
                Dish(
                    id=_unique_id(slugify(name_fi) or "dish", used_ids),
                    name=(name_en if lang == "en" and name_en else name_fi),
                    diets=diets,
                    allergens=allergens,
                )
            )
        if not dishes:
            menu.notes.append(NO_MENU_NOTE)
            return menu

        menu.notes.extend(_language_notes(lang, english_missing, len(dishes)))
        menu.dishes = dishes
        if prices := _student_price_note(soup):
            menu.notes.append(prices)
        if soup.select_one(".lms-pizza-row") is not None:
            menu.notes.append(PIZZA_NOTE)
        return menu


async def _get_page(client: httpx.AsyncClient) -> str:
    try:
        response = await client.get(MENU_URL)
    except httpx.HTTPError as exc:
        raise AdapterError(f"Menssa request failed: {exc}") from exc
    if response.status_code != 200:
        raise AdapterError(f"Menssa returned HTTP {response.status_code} for {MENU_URL}")
    return response.text


def _weekday_sections(soup: BeautifulSoup) -> list[Tag]:
    """The section around each Finnish weekday heading, in page order."""
    sections: list[Tag] = []
    for heading in soup.find_all("h3"):
        parent = heading.parent
        if isinstance(parent, Tag) and _text(heading).lower() in FI_WEEKDAYS:
            sections.append(parent)
    return sections


def _published_on(section: Tag, day: dt.date) -> bool:
    """True when the section's date line (``d.m.``, no year) names the requested day."""
    line = section.find(string=_DATE_LINE)
    match = _DATE_LINE.match(line) if line is not None else None
    return match is not None and (int(match[2]), int(match[1])) == (day.month, day.day)


def _codes(row: Tag) -> tuple[list[str], list[str]]:
    """(diets, allergens) from a dish row's code spans, in published order without repeats."""
    diets: dict[str, None] = {}
    allergens: dict[str, None] = {}
    for css in (".lms-front-allergens", ".lms-front-dietary"):
        for node in row.select(css):
            for code in _split_list(_text(node)):
                target = allergens if code.upper() in ALLERGEN_CODES else diets
                target[code] = None
    return list(diets), list(allergens)


def _student_price_note(soup: BeautifulSoup) -> str | None:
    prices: list[str] = []
    for card in soup.select(".lms-site-price-card"):
        title = _text(card.select_one("h4"))
        for row in card.select(".lms-site-price-row"):
            label = _text(row.select_one(".lms-site-price-label"))
            value = _text(row.select_one(".lms-site-price-value"))
            if title and value and _STUDENT_LABEL.search(label):
                prices.append(f"{title} {value}")
    if not prices:
        return None
    return "Student prices as published: " + "; ".join(prices) + "."


def _language_notes(lang: Lang, english_missing: int, dish_count: int) -> list[str]:
    if lang != "en" or english_missing == 0:
        return []
    if english_missing == dish_count:
        return ["English names are not published for this menu; Finnish shown."]
    return [f"English names are missing for {english_missing} dish(es); Finnish shown for those."]


def _unique_id(base: str, used: set[str]) -> str:
    candidate, suffix = base, 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node is not None else ""


def _split_list(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split(",")) if item]
