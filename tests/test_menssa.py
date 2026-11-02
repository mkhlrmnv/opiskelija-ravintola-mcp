"""Menssa adapter tests: offline parsing of a saved lunch page, plus one live check (-m live)."""

from __future__ import annotations

import copy
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import respx
from bs4 import BeautifulSoup

from ravintola_mcp.adapters.base import AdapterError
from ravintola_mcp.adapters.menssa import MENU_URL, NO_MENU_NOTE, MenssaAdapter
from ravintola_mcp.models import Lang, Menu
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "menssa"
MENSSA = next(r for r in RESTAURANTS if r.id == "menssa")
MONDAY = dt.date(2026, 11, 2)
FRIDAY = dt.date(2026, 11, 6)
SUNDAY = dt.date(2026, 11, 8)
NEXT_MONDAY = dt.date(2026, 11, 9)
MONDAY_DAILY = [
    "Herkkusieni keitto",
    "Mexican kanaa",
    "Soya Bolognese",
    "JASMIN RIISI",
    "Kasvikset",
    "ERIKOIS SALAATTIPÖYTÄ",
]


def _page() -> str:
    return (FIXTURES / "lounas-2026-11-02.html").read_text(encoding="utf-8")


def _edited(mutate: Callable[[BeautifulSoup], None]) -> str:
    soup = BeautifulSoup(_page(), "html.parser")
    mutate(soup)
    return str(soup)


async def _fetch(
    day: dt.date, lang: Lang = "fi", html: str | None = None, status: int = 200
) -> Menu:
    body = _page() if html is None else html
    response = httpx.Response(status, text=body, headers={"content-type": "text/html"})
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=True) as mock:
        mock.get(MENU_URL).mock(return_value=response)
        return await MenssaAdapter().fetch_menu(MENSSA, day, lang, client)


def _daily(menu: Menu) -> list[str]:
    return [d.name for d in menu.dishes if d.category is None]


async def test_monday_lunch_list_without_pizzas() -> None:
    menu = await _fetch(MONDAY)

    assert menu.error is None
    assert menu.restaurant_id == "menssa"
    assert menu.restaurant_name == "Menssa"
    assert menu.date == MONDAY
    assert menu.lang == "fi"
    assert menu.source_url == MENU_URL
    assert menu.lunch_hours is None
    assert _daily(menu) == MONDAY_DAILY
    assert all(d.category is None for d in menu.dishes)
    assert any("à la carte" in note for note in menu.notes)


async def test_monday_dish_fields_are_mapped() -> None:
    menu = await _fetch(MONDAY)

    soup_dish = next(d for d in menu.dishes if d.id == "herkkusieni-keitto")
    assert soup_dish.diets == ["G"]
    assert soup_dish.allergens == []
    assert soup_dish.category is None
    assert soup_dish.price is None
    assert soup_dish.macros is None
    assert soup_dish.components == []

    mexican = next(d for d in menu.dishes if d.id == "mexican-kanaa")
    assert mexican.diets == ["L", "G"]

    rice = next(d for d in menu.dishes if d.id == "jasmin-riisi")
    assert rice.diets == ["G", "vegan", "S"]


async def test_allergen_codes_are_split_from_diets() -> None:
    def add_allergen_codes(soup: BeautifulSoup) -> None:
        span = soup.select_one(".lms-front-allergens")
        assert span is not None
        span.string = "G, KA, SO"

    menu = await _fetch(MONDAY, html=_edited(add_allergen_codes))

    assert menu.dishes[0].diets == ["G"]
    assert menu.dishes[0].allergens == ["KA", "SO"]


async def test_english_request_uses_english_names_with_same_ids() -> None:
    fi = await _fetch(MONDAY, "fi")
    en = await _fetch(MONDAY, "en")

    assert en.lang == "en"
    assert _daily(en) == [
        "Mushroom soup",
        "Mexican chicken",
        "Soya Bolognese",
        "JASMIN RICE",
        "Vegetables",
        "SPECIAL SALAD TABLE",
    ]
    assert [d.id for d in en.dishes] == [d.id for d in fi.dishes]
    assert en.notes == [
        "Student prices as published: NORMAL LUNCH 5,90 €; SOUP LUNCH 3,20 €.",
        "Pizzas are also available à la carte (see menssa.fi/lounas/).",
    ]


async def test_missing_english_names_fall_back_to_finnish_with_note() -> None:
    def drop_two_english_names(soup: BeautifulSoup) -> None:
        for node in soup.select(".lms-front-en-name")[:2]:
            node.decompose()

    menu = await _fetch(MONDAY, "en", html=_edited(drop_two_english_names))

    assert menu.lang == "en"
    assert _daily(menu)[:2] == ["Herkkusieni keitto", "Mexican kanaa"]
    assert "English names are missing for 2 dish(es); Finnish shown for those." in menu.notes


async def test_no_english_names_at_all_is_noted() -> None:
    html = _edited(lambda soup: [n.decompose() for n in soup.select(".lms-front-en-name")])

    menu = await _fetch(MONDAY, "en", html=html)

    assert _daily(menu) == MONDAY_DAILY
    assert "English names are not published for this menu; Finnish shown." in menu.notes


async def test_selects_the_requested_day() -> None:
    menu = await _fetch(FRIDAY)

    assert menu.date == FRIDAY
    assert _daily(menu) == [
        "Porkkanasosekeitto",
        "Kalaa kasviksilla",
        "JASMIN RIISI",
        "Kasvikset",
        "ERIKOIS SALAATTIPÖYTÄ",
    ]
    assert menu.dishes[0].diets == ["L", "G"]


@pytest.mark.parametrize("day", [SUNDAY, NEXT_MONDAY])
async def test_day_outside_the_published_week_is_empty_with_note(day: dt.date) -> None:
    menu = await _fetch(day)

    assert menu.error is None
    assert menu.dishes == []
    assert menu.date == day
    assert menu.notes == [NO_MENU_NOTE]


async def test_day_row_without_dishes_is_empty_with_note() -> None:
    def drop_monday_dishes(soup: BeautifulSoup) -> None:
        for section in soup.select("section.lms-front-day"):
            if section.h3 and section.h3.get_text(strip=True) == "Maanantai":
                for row in section.select(".lms-front-dish"):
                    row.decompose()

    menu = await _fetch(MONDAY, html=_edited(drop_monday_dishes))

    assert menu.dishes == []
    assert menu.notes == [NO_MENU_NOTE]


async def test_duplicate_dish_rows_get_unique_ids() -> None:
    def duplicate_first_dish(soup: BeautifulSoup) -> None:
        first = soup.select_one(".lms-front-dish")
        assert first is not None
        first.insert_after(copy.copy(first))

    menu = await _fetch(MONDAY, html=_edited(duplicate_first_dish))

    assert menu.dishes[0].id == "herkkusieni-keitto"
    assert menu.dishes[1].id == "herkkusieni-keitto-2"
    ids = [d.id for d in menu.dishes]
    assert len(ids) == len(set(ids))


async def test_no_macros_are_published_so_none_are_set() -> None:
    menu = await _fetch(MONDAY)

    assert menu.macros_available is False
    assert all(d.macros is None and not d.components for d in menu.dishes)


async def test_student_prices_are_noted_once() -> None:
    menu = await _fetch(MONDAY)

    assert [n for n in menu.notes if n.startswith("Student prices")] == [
        "Student prices as published: NORMAL LUNCH 5,90 €; SOUP LUNCH 3,20 €."
    ]


async def test_daily_names_match_the_site_json_feed() -> None:
    feed = json.loads((FIXTURES / "lms-lunch-today-2026-11-02.json").read_text(encoding="utf-8"))
    items = feed["items"]

    fi = await _fetch(MONDAY, "fi")
    en = await _fetch(MONDAY, "en")

    assert _daily(fi) == [item["name_fi"] for item in items]
    assert _daily(en) == [item["name_en"] for item in items]
    daily = [d for d in fi.dishes if d.category is None]
    for dish, item in zip(daily, items, strict=True):
        published = {c.strip() for c in f"{item['allergens']},{item['dietary']}".split(",")}
        assert published - {""} == set(dish.diets) | set(dish.allergens)


async def test_page_without_weekday_headings_is_an_adapter_error() -> None:
    with pytest.raises(AdapterError, match="lunch list not found"):
        await _fetch(MONDAY, html="<html><body><h3>Lounas tulossa</h3></body></html>")


async def test_http_error_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="HTTP 503"):
        await _fetch(MONDAY, status=503)


@pytest.mark.live
async def test_live_lunch_list_for_the_next_published_weekday() -> None:
    """Hits menssa.fi/lounas/: the first Monday-Friday menu published in the next two weeks."""
    adapter = MenssaAdapter()
    start = dt.date.today()
    menu: Menu | None = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for offset in range(14):
            day = start + dt.timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            candidate = await adapter.fetch_menu(MENSSA, day, "fi", client)
            assert candidate.error is None
            if candidate.dishes:
                menu = candidate
                break
    if menu is None:
        pytest.skip("menssa.fi lists no lunch menu for the next two weeks")

    daily = [d for d in menu.dishes if d.category is None]
    print(f"\nmenssa {menu.date}: {len(daily)} lunch dishes")
    print(f"  e.g. {daily[0].name} diets={daily[0].diets}")
    print(f"  macros published: {menu.macros_available}; notes: {menu.notes}")
    assert len(daily) >= 3
    assert menu.lang == "fi"
