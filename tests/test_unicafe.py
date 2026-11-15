"""Unicafe adapter tests: fixtures served via respx, plus a ``live`` check.

Fixtures are synthetic: they mirror the structure of unicafe.fi responses with invented values.
"""

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
    id="unicafe-testiravintola",
    name="Unicafe Testiravintola",
    campus="Testikampus",
    provider="unicafe",
    url="https://menu.unicafe.fi",
    config={"slug": "testiravintola"},
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
    assert menu.lunch_hours == "Ma–Pe 10:00-18:00; La 12:00-16:00; Su Suljettu"
    assert [d.name for d in menu.dishes] == [
        "Kasvisbowl testi",
        "Kasvispyöryköitä testi",
        "Tofupata testi",
        "Testileipa",
        "Broileripasta testi (broileri)",
    ]
    assert menu.notes == ["2 side dish(es) or dessert(s) left out: only lunch dishes are listed."]

    bowl = menu.dishes[0]
    assert bowl.id == "kasvisbowl-testi"
    assert bowl.category == "Vegaanilounas"
    assert bowl.diets == ["KELA", "Veg"]
    assert bowl.allergens == ["kaura", "seesami", "soija"]
    assert bowl.price is None
    assert bowl.components == []
    assert bowl.description is not None and bowl.description.startswith("Testikaura")
    assert bowl.macros is not None
    assert bowl.macros.model_dump() == {
        "basis": "100g",
        "portion_g": None,
        "energy_kcal": 120.0,
        "energy_kj": 502.0,
        "protein_g": 7.0,
        "carbohydrates_g": 13.0,
        "sugars_g": 2.5,
        "fat_g": 4.5,
        "saturated_fat_g": 0.6,
        "fibre_g": 3.1,
        "salt_g": 0.55,
    }


async def test_dish_without_nutrition_has_no_macros() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "fi")

    testileipa = next(d for d in menu.dishes if d.name == "Testileipa")
    assert testileipa.macros is None
    assert testileipa.category == "Lounas"
    assert menu.macros_available


async def test_sugars_published_as_upper_bound_are_not_stored() -> None:
    menu = await _menu(KAIVOPIHA, MONDAY, "fi")

    pasta = next(d for d in menu.dishes if d.name.startswith("Broileripasta"))
    assert pasta.macros is not None
    assert pasta.macros.sugars_g is None  # the feed shows "<0,5g"
    assert pasta.macros.fat_g == 3.6
    assert pasta.diets == ["KELA", "L"]


def test_parse_nutrition_finnish_and_english_labels_agree() -> None:
    finnish = (
        "Energia 502kJ, energia 120kcal, rasva 4,5g, josta tyydyttynyttä rasvaa 0,6g, "
        "hiilihydraatit 13g, josta sokereita 2,5g, proteiini 7,0g, suola 0,55g, "
        "ravintokuitua 3,1g, laktoosia 0g."
    )
    english = (
        "Energy 502kJ, energy 120kcal, fat 4.5g, of which saturated fat 0.6g, carbohydrate 13g, "
        "of which sugars 2.5g, protein 7.0g, salt 0.55g, fibre 3.1g, lactose 0g."
    )
    expected = parse_nutrition(finnish)
    assert expected == parse_nutrition(english)
    assert expected is not None
    assert expected.basis == "100g"
    assert expected.energy_kj == 502.0
    assert expected.saturated_fat_g == 0.6


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
    assert menu.lunch_hours == "Mon–Fri 10:00-18:00; Sat 12:00-16:00; Sun Closed"
    assert menu.dishes[0].name == "Vegetable bowl test"
    assert menu.dishes[0].allergens[0] == "oat"
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

    assert menu.restaurant_id == "unicafe-testiravintola"
    assert menu.restaurant_name == "Unicafe Testiravintola"
    assert [d.name for d in menu.dishes] == ["Testipizza kasviksilla"]
    assert menu.dishes[0].category == "Päivän erikoinen"
    assert menu.notes == [
        "Testitiedote: lounas tarjolla klo 13.30 saakka"
    ]  # announcement, not a dish
    assert menu.lunch_hours == "Ma–Pe 09:30-13:30; La–Su Suljettu"


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
    assert menu.dishes[0].name == "Kasvisbowl testi"


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
    day["data"].append(copy.deepcopy(day["data"][3]))  # second "Testileipa"
    day["data"][0]["price"] = {"value": {"student": "3.10", "graduate": "6.35"}, "name": "Lounas"}

    menu = await _menu(KAIVOPIHA, MONDAY, "fi", feed={"fi": payload})

    assert menu.dishes[3].id == "testileipa"
    assert menu.dishes[5].id == "testileipa-2"
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
