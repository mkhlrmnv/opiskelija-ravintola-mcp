"""Sodexo adapter tests: offline fixtures via respx, plus a live check marked ``live``.

Fixtures are synthetic: they mirror the structure of sodexo.fi responses with invented values.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from ravintola_mcp.adapters.base import AdapterError
from ravintola_mcp.adapters.sodexo import BASE_URL, SodexoAdapter, daily_url, parse_macros
from ravintola_mcp.models import Lang, Menu, Restaurant
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "sodexo"
MONDAY = dt.date(2026, 11, 2)
SUNDAY = dt.date(2026, 11, 1)
KVARKKI = next(r for r in RESTAURANTS if r.id == "kvarkki")
T_TALO = next(r for r in RESTAURANTS if r.id == "t-talo")

KVARKKI_FI_URL = f"{BASE_URL}/ruokalistat/output/daily_json/86/2026-11-02"
KVARKKI_EN_URL = f"{BASE_URL}/en/ruokalistat/output/daily_json/86/2026-11-02"
T_TALO_FI_URL = f"{BASE_URL}/ruokalistat/output/daily_json/6754/2026-11-02"
KVARKKI_CLOSED_URL = f"{BASE_URL}/ruokalistat/output/daily_json/86/2026-11-01"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _fixture_json(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(_fixture_bytes(name))
    return payload


async def _fetch(
    restaurant: Restaurant, day: dt.date, lang: Lang, route_url: str, response: httpx.Response
) -> Menu:
    async with httpx.AsyncClient() as client, respx.mock(assert_all_called=True) as mock:
        mock.get(route_url).mock(return_value=response)
        return await SodexoAdapter().fetch_menu(restaurant, day, lang, client)


def _ok(content: bytes) -> httpx.Response:
    return httpx.Response(200, content=content, headers={"content-type": "application/json"})


def _ok_json(payload: dict[str, Any]) -> httpx.Response:
    return _ok(json.dumps(payload).encode())


async def test_normal_day_maps_courses_and_macros() -> None:
    menu = await _fetch(
        KVARKKI, MONDAY, "fi", KVARKKI_FI_URL, _ok(_fixture_bytes("kvarkki_daily_2026-11-02.json"))
    )

    assert menu.error is None
    assert menu.restaurant_id == "kvarkki"
    assert menu.restaurant_name == "Aalto Kvarkki"
    assert menu.lang == "fi"
    assert menu.source_url == KVARKKI.url
    assert menu.lunch_hours is None  # not in the JSON feed
    assert len(menu.dishes) == 5
    assert menu.macros_available

    baguette = next(d for d in menu.dishes if d.id == "tomaatti-juustopatonki")
    assert baguette.name == "Tomaatti-juustopatonki"
    assert baguette.category == "Patonkilounas"
    assert baguette.diets == ["G", "L"]
    assert baguette.price == "2,50 € / 4,50 € / 4,50 €"
    assert "Maito" in baguette.allergens
    assert baguette.description is None
    assert baguette.macros is not None
    assert baguette.macros.model_dump() == {
        "basis": "100g",
        "portion_g": None,
        "energy_kcal": 239.0,
        "energy_kj": 1000.0,
        "protein_g": 8.0,
        "carbohydrates_g": 30.0,
        "sugars_g": None,
        "fat_g": 11.0,
        "saturated_fat_g": 3.5,
        "fibre_g": 1.5,
        "salt_g": 0.9,
    }


async def test_multi_component_dishes_have_no_macros_but_list_components() -> None:
    menu = await _fetch(
        KVARKKI, MONDAY, "fi", KVARKKI_FI_URL, _ok(_fixture_bytes("kvarkki_daily_2026-11-02.json"))
    )

    burger = next(d for d in menu.dishes if d.id.startswith("juustohampurilainen"))
    assert burger.macros is None
    assert burger.description == "Juustohampurilainen, Ranskalaisia perunoita"
    assert [c.name for c in burger.components] == ["Juustohampurilainen", "Ranskalaisia perunoita"]
    assert all(c.macros is not None and c.macros.basis == "100g" for c in burger.components)
    assert burger.components[0].macros is not None
    assert burger.components[0].macros.energy_kj == 800.0
    assert burger.components[0].macros.fat_g == 12.0
    assert burger.components[1].macros is not None
    assert burger.components[1].macros.energy_kj == 600.0
    assert any("4 multi-component" in note for note in menu.notes)


async def test_multi_component_course_keeps_recipe_order_and_per_part_values() -> None:
    menu = await _fetch(
        T_TALO, MONDAY, "fi", T_TALO_FI_URL, _ok(_fixture_bytes("t-talo_daily_2026-11-02.json"))
    )

    dish = next(d for d in menu.dishes if any(c.name == "Tomaattikastiketta" for c in d.components))
    assert dish.macros is None
    assert [c.name for c in dish.components] == [
        "Possupyöryköitä",
        "Tomaattikastiketta",
        "Keitettyjä perunoita",
    ]
    sauce = dish.components[1].macros
    assert sauce is not None
    assert sauce.basis == "100g"
    assert sauce.energy_kj == 240.0
    assert sauce.protein_g == 0.6
    assert sauce.energy_kcal == 57.4  # filled from kJ by the Macros model


async def test_single_recipe_course_has_macros_and_no_components() -> None:
    menu = await _fetch(
        T_TALO, MONDAY, "fi", T_TALO_FI_URL, _ok(_fixture_bytes("t-talo_daily_2026-11-02.json"))
    )

    dessert = next(d for d in menu.dishes if d.id == "vadelmajogurtti")
    assert dessert.macros is not None
    assert dessert.components == []


async def test_t_talo_dessert_has_macros_and_student_price_text() -> None:
    menu = await _fetch(
        T_TALO, MONDAY, "fi", T_TALO_FI_URL, _ok(_fixture_bytes("t-talo_daily_2026-11-02.json"))
    )

    assert menu.restaurant_id == "t-talo"
    assert menu.source_url == T_TALO.url
    dessert = next(d for d in menu.dishes if d.id == "vadelmajogurtti")
    assert dessert.category == "Makeat lisukkeet"
    assert dessert.price == "1,50 € / 1,50 € / 1,50 €"
    assert dessert.macros is not None
    assert dessert.macros.protein_g == 6.5
    assert dessert.macros.saturated_fat_g == 4.2
    subway = next(d for d in menu.dishes if d.category == "Suosikki")
    assert subway.macros is None


async def test_parse_macros_handles_decimal_commas_and_skips_unknown_units() -> None:
    macros = parse_macros(
        "Energia kj/Energia kj: 312,50 kj | Proteiini/Proteiini: 3,25 proteiin | "
        "Suola/Suola: 0,70 suola | Rauta/Rauta: 0.00 rauta | C-vitamiini/C-vitamiini: 0.00 c-vit"
    )

    assert macros is not None
    assert macros.basis == "100g"
    assert macros.energy_kj == 312.5
    assert macros.protein_g == 3.25
    assert macros.salt_g == 0.7
    assert macros.fat_g is None
    assert parse_macros("Rauta/Rauta: 0.00 rauta | C-vitamiini/C-vitamiini: 0.00 c-vit") is None
    assert parse_macros("") is None


async def test_closed_day_returns_empty_menu_with_note() -> None:
    menu = await _fetch(
        KVARKKI,
        SUNDAY,
        "fi",
        KVARKKI_CLOSED_URL,
        _ok(_fixture_bytes("kvarkki_daily_2026-11-01_closed.json")),
    )

    assert menu.dishes == []
    assert menu.error is None
    assert menu.notes == ["No lunch menu is published for this day (closed, or not yet published)."]


async def test_english_request_uses_en_path_and_english_names() -> None:
    menu = await _fetch(
        KVARKKI,
        MONDAY,
        "en",
        KVARKKI_EN_URL,
        _ok(_fixture_bytes("kvarkki_daily_2026-11-02_en.json")),
    )

    assert menu.lang == "en"
    assert menu.dishes[0].name == "Vegetable stew with brown rice"
    assert not any("English names" in note for note in menu.notes)


async def test_missing_english_names_fall_back_to_finnish_with_note() -> None:
    payload = _fixture_json("kvarkki_daily_2026-11-02_en.json")
    payload["courses"]["1"]["title_en"] = ""
    payload["courses"]["2"]["title_en"] = "   "

    menu = await _fetch(KVARKKI, MONDAY, "en", KVARKKI_EN_URL, _ok_json(payload))

    assert menu.dishes[0].name == "Kasvispataa ja ruskeaa riisiä"
    assert menu.dishes[1].name == payload["courses"]["2"]["title_fi"].strip()
    assert menu.dishes[2].name == "Cheeseburger with french fries 11:00–14:00"
    assert "English names are missing for 2 dish(es); Finnish shown for those." in menu.notes


async def test_no_english_names_at_all_is_noted() -> None:
    payload = _fixture_json("kvarkki_daily_2026-11-02_en.json")
    for course in payload["courses"].values():
        course["title_en"] = ""

    menu = await _fetch(KVARKKI, MONDAY, "en", KVARKKI_EN_URL, _ok_json(payload))

    assert all(d.name for d in menu.dishes)
    assert "English names are not published for this menu; Finnish shown." in menu.notes


async def test_duplicate_titles_get_unique_ids() -> None:
    payload = copy.deepcopy(_fixture_json("kvarkki_daily_2026-11-02.json"))
    payload["courses"]["6"] = copy.deepcopy(payload["courses"]["5"])

    menu = await _fetch(KVARKKI, MONDAY, "fi", KVARKKI_FI_URL, _ok_json(payload))

    ids = [d.id for d in menu.dishes]
    assert len(ids) == len(set(ids)) == 6
    assert ids[-2:] == ["tomaatti-juustopatonki", "tomaatti-juustopatonki-2"]


async def test_courses_as_list_are_treated_as_closed_day() -> None:
    menu = await _fetch(
        KVARKKI, SUNDAY, "fi", KVARKKI_CLOSED_URL, _ok_json({"meta": {}, "courses": []})
    )
    assert menu.dishes == []


async def test_http_error_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="HTTP 404"):
        await _fetch(KVARKKI, MONDAY, "fi", KVARKKI_FI_URL, httpx.Response(404, text="nope"))


async def test_non_json_body_raises_adapter_error() -> None:
    with pytest.raises(AdapterError, match="not JSON"):
        await _fetch(KVARKKI, MONDAY, "fi", KVARKKI_FI_URL, httpx.Response(200, text="<html>"))


async def test_missing_restaurant_id_raises_adapter_error() -> None:
    no_id = KVARKKI.model_copy(update={"config": {}})
    async with httpx.AsyncClient() as client:
        with pytest.raises(AdapterError, match="restaurant_id"):
            await SodexoAdapter().fetch_menu(no_id, MONDAY, "fi", client)


def test_daily_url_uses_en_prefix_only_for_english() -> None:
    assert daily_url("86", MONDAY, "fi") == KVARKKI_FI_URL
    assert daily_url("86", MONDAY, "en") == KVARKKI_EN_URL


@pytest.mark.live
async def test_live_weekday_menus_for_both_restaurants() -> None:
    """Hits www.sodexo.fi: the next published weekday menu for each restaurant."""
    adapter = SodexoAdapter()
    start = dt.date.today()
    async with httpx.AsyncClient(timeout=15.0) as client:
        for restaurant in (KVARKKI, T_TALO):
            menu = None
            for offset in range(14):
                day = start + dt.timedelta(days=offset)
                if day.weekday() >= 5:
                    continue
                candidate = await adapter.fetch_menu(restaurant, day, "fi", client)
                assert candidate.error is None
                if candidate.dishes:
                    menu = candidate
                    break
            assert menu is not None, f"no published weekday menu for {restaurant.id} in 2 weeks"

            # Nutrition sits on the dish for single-component courses and on the components
            # otherwise; which kind a given day has depends on the real menu.
            published = [d.macros for d in menu.dishes if d.macros is not None] + [
                c.macros for d in menu.dishes for c in d.components if c.macros is not None
            ]
            print(f"  nutrition entries (dishes + components): {len(published)}")
            assert len(menu.dishes) >= 3
            assert published, f"{restaurant.id} publishes no nutrition at all"
            for macros in published:
                assert macros.basis == "100g"
                assert macros.energy_kj is not None and macros.energy_kj > 0
                assert macros.protein_g is not None and macros.protein_g >= 0
