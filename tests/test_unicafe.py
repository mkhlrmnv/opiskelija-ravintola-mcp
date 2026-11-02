"""Unicafe adapter tests: trimmed real responses served via respx, plus a ``live`` check."""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from ravintola_mcp.adapters.base import USER_AGENT, AdapterError
from ravintola_mcp.adapters.unicafe import (
    EN_FALLBACK_NOTE,
    ENDPOINT,
    NO_MENU_NOTE,
    UnicafeAdapter,
    _label_date,
    parse_nutrition,
)
from ravintola_mcp.models import Lang, Menu, Restaurant
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "unicafe"
MONDAY = dt.date(2026, 11, 2)
TUESDAY = dt.date(2026, 11, 3)
SUNDAY = dt.date(2026, 11, 8)
OUT_OF_RANGE = dt.date(2026, 11, 20)

KAIVOPIHA = next(r for r in RESTAURANTS if r.id == "unicafe-kaivopiha").model_copy(
    update={"config": {"slug": "kaivopiha"}}
)
VIIKUNA = Restaurant(
    id="unicafe-viikuna",
    name="Unicafe Viikuna",
    campus="Otaniemi",
    provider="unicafe",
    url="https://menu.unicafe.fi",
    config={"slug": "viikuna"},
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _fixture(lang: Lang) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = json.loads(
        (FIXTURES / f"restaurants-{lang}.json").read_text(encoding="utf-8")
    )
    return payload


def _response(body: object) -> httpx.Response:
    if isinstance(body, httpx.Response):
        return body
    return httpx.Response(
        200,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json; charset=UTF-8"},
    )


def _kaivopiha_day(payload: list[dict[str, Any]], date_label: str) -> dict[str, Any]:
    entry = next(row for row in payload if row["slug"] == "kaivopiha")
    return next(menu for menu in entry["menuData"]["menus"] if menu["date"] == date_label)


async def _menu(
    restaurant: Restaurant,
    day: dt.date,
    lang: Lang,
    feed: dict[Lang, object] | None = None,
    adapter: UnicafeAdapter | None = None,
) -> Menu:
    """One fetch against mocked feeds; ``feed`` overrides the fixture or a status for a language."""
    bodies: dict[Lang, object] = {"fi": _fixture("fi"), "en": _fixture("en")} | (feed or {})
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=False) as mock:
        for code, body in bodies.items():
            mock.get(ENDPOINT, params={"lang": code}).mock(return_value=_response(body))
        return await (adapter or UnicafeAdapter()).fetch_menu(restaurant, day, lang, client)


async def test_monday_lunch_dishes_with_macros_per_100g() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "fi")

    assert menu.error is None
    assert menu.restaurant_id == "unicafe-kaivopiha"
    assert menu.restaurant_name == "Unicafe Kaivopiha"
    assert menu.lang == "fi"
    assert menu.source_url == "https://menu.unicafe.fi"
    assert menu.lunch_hours == "Ma–Pe 11:00-19:45; La 11:30-17:00; Su Suljettu"
    assert [d.name for d in menu.dishes] == [
        "Seitan - Hoi Sin bowl",
        "Maggara-harissapata",
        "Falafel-kasvispyöryköitä, soijajugurtti tzatziki",
        "Patonkibaari",
        "Lihamakaronilaatikko (broileri)",
    ]
    assert menu.notes == ["2 side dish(es) or dessert(s) left out: only lunch dishes are listed."]

    seitan = menu.dishes[0]
    assert seitan.id == "seitan-hoi-sin-bowl"
    assert seitan.category == "Vegaanilounas"
    assert seitan.diets == ["KELA", "Veg"]
    assert seitan.allergens == [
        "gluteenia sisältävät viljat",
        "kaura",
        "seesaminsiemenet",
        "soijapavut",
        "vehnä",
    ]
    assert seitan.price is None
    assert seitan.components == []
    assert seitan.description is not None and seitan.description.startswith("Gluteenitonta")
    assert seitan.macros is not None
    assert seitan.macros.model_dump() == {
        "basis": "100g",
        "portion_g": None,
        "energy_kcal": 115.0,
        "energy_kj": 481.0,
        "protein_g": 8.2,
        "carbohydrates_g": 12.0,
        "sugars_g": 3.8,
        "fat_g": 4.0,
        "saturated_fat_g": 0.4,
        "fibre_g": 2.3,
        "salt_g": 0.64,
    }


async def test_dish_without_nutrition_has_no_macros() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "fi")

    baguette = next(d for d in menu.dishes if d.name == "Patonkibaari")
    assert baguette.macros is None
    assert baguette.category == "Lounas"
    assert menu.macros_available


async def test_sugars_published_as_upper_bound_are_not_stored() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "fi")

    lihamakaroni = next(d for d in menu.dishes if d.name.startswith("Lihamakaroni"))
    assert lihamakaroni.macros is not None
    assert lihamakaroni.macros.sugars_g is None  # the site shows "<0,5g"
    assert lihamakaroni.macros.fat_g == 3.4
    assert lihamakaroni.diets == ["KELA", "L"]


def test_parse_nutrition_finnish_and_english_labels_agree() -> None:
    finnish = (
        "Energia 481kJ, energia 115kcal, rasva 4,0g, josta tyydyttynyttä rasvaa 0,4g, "
        "hiilihydraatit 12g, josta sokereita 3,8g, proteiini 8,2g, suola 0,64g, "
        "ravintokuitua 2,3g, laktoosia 0g."
    )
    english = (
        "Energy 481kJ, energy 115kcal, fat 4.0g, of which saturated fat 0.4g, carbohydrate 12g, "
        "of which sugars 3.8g, protein 8.2g, salt 0.64g, fibre 2.3g, lactose 0g."
    )
    expected = parse_nutrition(finnish)
    assert expected == parse_nutrition(english)
    assert expected is not None
    assert expected.basis == "100g"
    assert expected.energy_kj == 481.0
    assert expected.saturated_fat_g == 0.4


def test_parse_nutrition_fills_missing_energy_unit_and_skips_junk() -> None:
    macros = parse_nutrition("energia 155kcal, rasva 7,8g")
    assert macros is not None
    assert macros.energy_kcal == 155
    assert macros.energy_kj == pytest.approx(648.5, abs=0.1)

    assert parse_nutrition("") is None
    assert parse_nutrition("laktoosia 0g") is None
    assert parse_nutrition("josta sokereita <0,5g") is None


def test_label_dates_pick_the_year_nearest_the_request() -> None:
    assert _label_date("Ma 02.11.", MONDAY) == MONDAY
    assert _label_date("Ti 29.12.", dt.date(2026, 12, 28)) == dt.date(2026, 12, 29)
    assert _label_date("To 01.01.", dt.date(2026, 12, 31)) == dt.date(2027, 1, 1)
    assert _label_date("no date here", MONDAY) is None


async def test_english_menu_uses_english_names_and_same_macros() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "en")
    finnish = await _menu(KAIVOPIHA, MONDAY, "fi")

    assert menu.lang == "en"
    assert menu.notes == finnish.notes
    assert menu.lunch_hours == "Mon–Fri 11:00-19:45; Sat 11:30-17:00; Sun Closed"
    assert menu.dishes[0].name == "Seitan & Hoi sin bowl"
    assert menu.dishes[0].allergens[0] == "cereals containing gluten"
    assert menu.dishes[0].macros == finnish.dishes[0].macros


async def test_closed_sunday_gives_no_dishes_and_a_note() -> None:
    menu = await _menu(KAIVOPIHA, SUNDAY, "fi")

    assert menu.dishes == []
    assert menu.error is None
    assert menu.notes == [NO_MENU_NOTE]
    assert menu.lunch_hours is not None


async def test_english_closed_day_keeps_english_without_fallback_note() -> None:
    menu = await _menu(KAIVOPIHA, SUNDAY, "en")

    assert menu.lang == "en"
    assert menu.dishes == []
    assert menu.notes == [NO_MENU_NOTE]


async def test_day_outside_the_feed_gives_the_published_range() -> None:
    menu = await _menu(KAIVOPIHA, OUT_OF_RANGE, "fi")

    assert menu.dishes == []
    assert menu.notes == [
        "No menu is published for 2026-11-20; the feed covers 2026-11-02 to 2026-11-08."
    ]


async def test_restaurant_selection_uses_the_configured_slug() -> None:
    menu = await _menu(VIIKUNA, MONDAY, "fi")

    assert menu.restaurant_id == "unicafe-viikuna"
    assert menu.restaurant_name == "Unicafe Viikuna"
    assert [d.name for d in menu.dishes] == ["Pizza nyhtökaura-ananas"]
    assert menu.dishes[0].category == "Päivän erikoinen"
    assert menu.notes == ["Pizzaa tarjolla klo:13.30 saakka"]  # announcement, not a dish
    assert menu.lunch_hours == "Ma–Pe 10:30-14:00; La–Su Suljettu"


async def test_unknown_slug_raises_adapter_error() -> None:
    missing = VIIKUNA.model_copy(update={"config": {"slug": "nope"}})
    with pytest.raises(AdapterError, match="no restaurant with slug 'nope'"):
        await _menu(missing, MONDAY, "fi")


async def test_missing_slug_config_raises_adapter_error() -> None:
    unconfigured = VIIKUNA.model_copy(update={"config": {}})
    with pytest.raises(AdapterError, match="no Unicafe slug"):
        await _menu(unconfigured, MONDAY, "fi")


async def test_http_error_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="HTTP 500"):
        await _menu(KAIVOPIHA, MONDAY, "fi", feed={"fi": httpx.Response(500, content=b"<html>")})


async def test_non_json_response_raises_adapter_error() -> None:
    body = httpx.Response(200, content=b"<html>not json</html>")
    with pytest.raises(AdapterError, match="not JSON"):
        await _menu(KAIVOPIHA, MONDAY, "fi", feed={"fi": body})


async def test_english_feed_without_the_day_falls_back_to_finnish() -> None:
    english = copy.deepcopy(_fixture("en"))
    entry = next(row for row in english if row["slug"] == "kaivopiha")
    entry["menuData"]["menus"] = [
        m for m in entry["menuData"]["menus"] if m["date"] != "Mon 02.11."
    ]

    menu = await _menu(KAIVOPIHA, MONDAY, "en", feed={"en": english})

    assert menu.lang == "fi"
    assert menu.notes[0] == EN_FALLBACK_NOTE
    assert menu.dishes[0].name == "Seitan - Hoi Sin bowl"


async def test_english_feed_error_falls_back_to_finnish() -> None:
    menu = await _menu(
        KAIVOPIHA, MONDAY, "en", feed={"en": httpx.Response(503, content=b"unavailable")}
    )

    assert menu.lang == "fi"
    assert menu.notes[0] == EN_FALLBACK_NOTE
    assert len(menu.dishes) == 5


async def test_duplicate_dish_names_get_unique_ids_and_prices_are_formatted() -> None:
    payload = copy.deepcopy(_fixture("fi"))
    day = _kaivopiha_day(payload, "Ma 02.11.")
    day["data"].append(copy.deepcopy(day["data"][3]))  # second "Patonkibaari"
    day["data"][0]["price"] = {"value": {"student": "3.10", "graduate": "6.35"}, "name": "Lounas"}

    menu = await _menu(KAIVOPIHA, MONDAY, "fi", feed={"fi": payload})

    assert menu.dishes[3].id == "patonkibaari"
    assert menu.dishes[5].id == "patonkibaari-2"
    assert menu.dishes[0].price == "student 3.10, graduate 6.35"


async def test_adapter_caches_each_language_for_the_ttl() -> None:
    clock = FakeClock()
    adapter = UnicafeAdapter(clock=clock, ttl_s=600.0)
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=False) as mock:
        fi = mock.get(ENDPOINT, params={"lang": "fi"}).mock(return_value=_response(_fixture("fi")))
        en = mock.get(ENDPOINT, params={"lang": "en"}).mock(return_value=_response(_fixture("en")))

        for day in (MONDAY, TUESDAY, SUNDAY):
            await adapter.fetch_menu(KAIVOPIHA, day, "fi", client)
        assert fi.call_count == 1

        clock.now = 599.0
        await adapter.fetch_menu(KAIVOPIHA, MONDAY, "fi", client)
        assert fi.call_count == 1

        clock.now = 600.0
        await adapter.fetch_menu(KAIVOPIHA, MONDAY, "fi", client)
        assert fi.call_count == 2

        await adapter.fetch_menu(KAIVOPIHA, MONDAY, "en", client)
        await adapter.fetch_menu(KAIVOPIHA, TUESDAY, "en", client)
        assert en.call_count == 1
        assert fi.call_count == 2


async def test_concurrent_requests_share_one_download() -> None:
    adapter = UnicafeAdapter()
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=False) as mock:
        fi = mock.get(ENDPOINT, params={"lang": "fi"}).mock(return_value=_response(_fixture("fi")))
        await asyncio.gather(
            *(adapter.fetch_menu(KAIVOPIHA, day, "fi", client) for day in (MONDAY, TUESDAY))
        )
    assert fi.call_count == 1


@pytest.mark.live
async def test_live_lunch_menu_for_kaivopiha() -> None:
    day = dt.date.today()
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)

    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        menu = await UnicafeAdapter().fetch_menu(KAIVOPIHA, day, "fi", client)

    assert menu.error is None
    assert menu.dishes, menu.notes
    assert menu.lunch_hours is not None
    assert any(d.macros is not None and d.macros.basis == "100g" for d in menu.dishes)
