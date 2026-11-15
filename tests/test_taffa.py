"""Täffä adapter tests: offline fixtures via respx, plus a live check marked ``live``.

Fixtures are synthetic: they mirror the structure of newapi.tf.fi responses with invented values.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from ravintola_mcp.adapters.base import AdapterError
from ravintola_mcp.adapters.taffa import NO_ENGLISH_NOTE, NO_MENU_NOTE, TaffaAdapter, week_url
from ravintola_mcp.models import Lang, Menu
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "taffa"
TAFFA = next(r for r in RESTAURANTS if r.id == "taffa")
FI_URL = week_url("fi")
EN_URL = week_url("en")
MONDAY = dt.date(2026, 11, 2)
WEDNESDAY = dt.date(2026, 11, 4)
THURSDAY = dt.date(2026, 11, 5)
FRIDAY = dt.date(2026, 11, 6)
SATURDAY = dt.date(2026, 11, 7)
NEXT_MONDAY = dt.date(2026, 11, 9)
PREVIOUS_MONDAY = dt.date(2026, 10, 26)
WEEK_NOTE = "only covers the current week (02.11.2026 to 06.11.2026)"


def _week(lang: str) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads(
        (FIXTURES / f"week-{lang}-2026-11-02.json").read_bytes()
    )
    return payload


def _without_day(
    days: list[dict[str, Any]], day: dt.date, replacement: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """The feed with one day removed, or replaced by ``replacement`` when given."""
    result: list[dict[str, Any]] = []
    for entry in days:
        if entry["day"] != day.isoformat():
            result.append(entry)
        elif replacement is not None:
            result.append(replacement)
    return result


async def _fetch(
    day: dt.date,
    lang: Lang,
    *,
    fi: Any = None,
    en: Any = None,
) -> Menu:
    """Fetch one day with the weekly feeds served from the fixtures unless overridden."""
    fi_reply = _reply(_week("fi") if fi is None else fi)
    en_reply = _reply(_week("en") if en is None else en)
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=False) as mock:
        mock.get(FI_URL).mock(return_value=fi_reply)
        mock.get(EN_URL).mock(return_value=en_reply)
        return await TaffaAdapter().fetch_menu(TAFFA, day, lang, client)


def _reply(payload: Any) -> httpx.Response:
    if isinstance(payload, httpx.Response):
        return payload
    return httpx.Response(200, json=payload)


async def test_finnish_day_maps_lines_and_diet_codes() -> None:
    menu = await _fetch(MONDAY, "fi")

    assert menu.error is None
    assert menu.restaurant_id == "taffa"
    assert menu.restaurant_name == "Täffä"
    assert menu.lang == "fi"
    assert menu.source_url == FI_URL
    assert menu.lunch_hours is None  # not published by the feed
    assert menu.notes == []
    assert [d.category for d in menu.dishes] == [
        "Liha/kala",
        "Kasvisruoka",
        "Delisalaatti",
        "A la carte",
        "Keitto",
    ]

    meat = menu.dishes[0]
    assert meat.id == "kalapyorykat-paprikakastike-perunasosetta"
    assert meat.name == "Kalapyörykät, paprikakastike, perunasosetta"
    assert meat.diets == []  # this line carries no codes

    veg = next(d for d in menu.dishes if d.category == "Kasvisruoka")
    assert veg.name == "Kasvispihvit, valkosipulimajoneesi"
    assert veg.diets == ["A", "Ei sisällä pähkinöitä", "G", "KM", "M", "Soijaton", "Veg"]


async def test_feed_publishes_no_nutrition_price_or_allergen_names() -> None:
    menu = await _fetch(MONDAY, "fi")

    assert not menu.macros_available
    assert all(
        d.macros is None and d.components == [] and d.price is None and d.allergens == []
        for d in menu.dishes
    )


async def test_english_names_and_categories_with_finnish_diet_codes() -> None:
    menu = await _fetch(THURSDAY, "en")

    assert menu.lang == "en"
    assert menu.source_url == EN_URL
    assert menu.notes == []
    assert [d.category for d in menu.dishes] == [
        "Fish/meat",
        "Pastry",
        "Vegetarian option",
        "Salad",
        "A la carte",
        "Soup",
    ]

    pancake = next(d for d in menu.dishes if d.category == "Pastry")
    assert pancake.id == "quark-pancake"
    assert pancake.name == "Quark pancake"
    assert pancake.diets == ["Ei sisällä pähkinöitä", "L", "Soijaton"]

    pea_soup = next(d for d in menu.dishes if d.category == "Soup")
    assert pea_soup.name == "Lentil soup (also vegan)"  # the parenthesis is part of the name
    assert pea_soup.diets == ["A", "Ei sisällä pähkinöitä", "G", "KM", "M", "Soijaton"]


async def test_unnamed_english_dish_falls_back_to_finnish_name() -> None:
    menu = await _fetch(FRIDAY, "en")

    dish = next(d for d in menu.dishes if d.category == "Fish/meat")
    assert dish.name == "Yrttibroileri"
    assert dish.diets == ["G", "L", "M"]
    assert menu.notes == ["English names are missing for 1 dish(es); Finnish shown for those."]


async def test_missing_english_day_falls_back_to_finnish_menu() -> None:
    en = _without_day(_week("en"), THURSDAY)

    menu = await _fetch(THURSDAY, "en", en=en)
    finnish = await _fetch(THURSDAY, "fi")

    assert menu.lang == "fi"
    assert menu.source_url == FI_URL
    assert menu.notes == [NO_ENGLISH_NOTE]
    assert [d.name for d in menu.dishes] == [d.name for d in finnish.dishes]


@pytest.mark.parametrize("day", [SATURDAY, NEXT_MONDAY, PREVIOUS_MONDAY])
async def test_date_outside_the_current_week_has_no_dishes(day: dt.date) -> None:
    menu = await _fetch(day, "en")

    assert menu.dishes == []
    assert menu.error is None
    assert menu.lang == "en"
    assert menu.date == day
    assert len(menu.notes) == 1
    assert WEEK_NOTE in menu.notes[0]


@pytest.mark.parametrize("replacement", [None, {"day": "2026-11-04", "dayName": "Keskiviikko"}])
async def test_closed_weekday_inside_the_week_has_no_dishes(
    replacement: dict[str, Any] | None,
) -> None:
    fi = _without_day(_week("fi"), WEDNESDAY, replacement)
    en = _without_day(_week("en"), WEDNESDAY, replacement)

    menu = await _fetch(WEDNESDAY, "en", fi=fi, en=en)

    assert menu.dishes == []
    assert menu.notes == [NO_MENU_NOTE]


async def test_dish_ids_are_slugs_made_unique_within_the_day() -> None:
    day = {
        "day": "2026-11-02",
        "dayName": "Maanantai",
        "Liha/kala": "Lohi (G)",
        "Keitto": "Lohi (G, L)",
    }

    menu = await _fetch(MONDAY, "fi", fi=[day])

    assert [d.id for d in menu.dishes] == ["lohi", "lohi-2"]


async def test_parenthesis_without_diet_codes_stays_in_the_name() -> None:
    day = {"day": "2026-11-02", "dayName": "Maanantai", "Keitto": "Linssikeitto (myös vegaani)"}

    menu = await _fetch(MONDAY, "fi", fi=[day])

    assert menu.dishes[0].name == "Linssikeitto (myös vegaani)"
    assert menu.dishes[0].diets == []


async def test_http_error_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="HTTP 500"):
        await _fetch(MONDAY, "fi", fi=httpx.Response(500))


async def test_non_json_feed_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="not JSON"):
        await _fetch(MONDAY, "fi", fi=httpx.Response(200, content=b"<html>lunch</html>"))


async def test_unexpected_feed_shape_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="Unexpected"):
        await _fetch(MONDAY, "fi", fi={"day": "2026-11-02"})


@pytest.mark.live
async def test_live_current_week_feed_has_dishes_with_diet_codes() -> None:
    """Hits newapi.tf.fi: the first day from today in the current week that has dishes."""
    adapter = TaffaAdapter()
    start = dt.date.today()
    menu = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for offset in range(7):
            day = start + dt.timedelta(days=offset)
            candidate = await adapter.fetch_menu(TAFFA, day, "en", client)
            assert candidate.error is None
            if candidate.dishes:
                menu = candidate
                break

    assert menu is not None, "no day with dishes in the current week's feed"
    print(f"\n{menu.date}: {len(menu.dishes)} dishes, e.g. {menu.dishes[0]}")
    assert menu.lang == "en"
    assert menu.source_url == EN_URL
    assert len(menu.dishes) >= 3
    assert all(d.name for d in menu.dishes)
    assert any(d.diets for d in menu.dishes)
    assert not menu.macros_available
