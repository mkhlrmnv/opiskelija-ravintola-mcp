"""Compass adapter tests: recorded responses served by a stub transport, plus one live check.

Fixtures are synthetic: they mirror the structure of compass-group.fi responses with
invented values.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from ravintola_mcp.adapters.base import USER_AGENT, AdapterError
from ravintola_mcp.adapters.compass import CompassAdapter
from ravintola_mcp.models import Lang, Menu, Restaurant
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "compass"
MONDAY = dt.date(2026, 11, 2)
SUNDAY = dt.date(2026, 11, 1)
ALVARI = next(r for r in RESTAURANTS if r.id == "alvari")
DIPOLI = next(r for r in RESTAURANTS if r.id == "dipoli")
EMPTY_DAY = {"dayOfWeek": "Monday", "date": "2026-11-02T00:00:00", "menuPackages": []}

Handler = Callable[[httpx.Request], httpx.Response]


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _response(body: bytes | dict[str, Any], status: int = 200) -> httpx.Response:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return httpx.Response(status, content=content, headers={"content-type": "application/json"})


class CompassStub:
    """Answers like the live API from recorded responses. Unknown cost numbers get an empty
    day (as the live API does) and unrecorded recipes get a 404."""

    def __init__(
        self,
        *,
        days: dict[tuple[str, str], bytes | dict[str, Any] | httpx.Response] | None = None,
        recipes: dict[int, httpx.Response] | None = None,
        search: httpx.Response | None = None,
        details: httpx.Response | None = None,
    ) -> None:
        self.days: dict[tuple[str, str], bytes | dict[str, Any] | httpx.Response] = {
            ("0190", "fi"): _fixture("synthetic-day-alvari-2026-11-02-fi.json"),
            ("0190", "en"): _fixture("synthetic-day-alvari-2026-11-02-en.json"),
            ("3101", "fi"): _fixture("synthetic-day-dipoli-2026-11-02-fi.json"),
        }
        self.days.update(days or {})
        self.recipes: dict[int, httpx.Response] = {
            40001: _response(_fixture("synthetic-recipe-40001-fi.json")),
            40002: _response(_fixture("synthetic-recipe-40002-fi.json")),
        }
        self.recipes.update(recipes or {})
        self.search = search or _response(_fixture("synthetic-restaurant-search-alvari.json"))
        self.details = details or _response(_fixture("synthetic-restaurant-details-alvari-fi.json"))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        query = dict(request.url.params)
        if path == "/menuapi/day-menus":
            entry = self.days.get((query["costCenter"], query["language"]))
            if entry is None:
                return _response(EMPTY_DAY)
            return entry if isinstance(entry, httpx.Response) else _response(entry)
        if path.startswith("/menuapi/recipes/"):
            recipe_id = int(path.rsplit("/", 1)[1])
            return self.recipes.get(recipe_id) or _response({"status": 404}, status=404)
        if path == "/api/restaurant-search":
            return self.search
        if path == "/api/restaurant-search/details":
            return self.details
        return httpx.Response(404)


async def _fetch(
    restaurant: Restaurant,
    stub: CompassStub,
    *,
    day: dt.date = MONDAY,
    lang: Lang = "fi",
) -> Menu:
    transport = httpx.MockTransport(stub)
    async with httpx.AsyncClient(transport=transport, headers={"User-Agent": USER_AGENT}) as client:
        return await CompassAdapter().fetch_menu(restaurant, day, lang, client)


def _by_name(menu: Menu, name: str) -> Any:
    return next(d for d in menu.dishes if d.name == name)


async def test_monday_lines_become_dishes_with_category_price_and_diets() -> None:
    menu = await _fetch(ALVARI, CompassStub())

    assert menu.lang == "fi"
    assert menu.notes == []
    assert menu.source_url == ALVARI.url
    assert menu.restaurant_id == "alvari"
    assert len(menu.dishes) == 9

    soup = _by_name(menu, "Testikeitto basilikalla")
    assert soup.id == "esimerkkisoppa-testikeitto-basilikalla"
    assert soup.category == "Esimerkkisoppa"
    assert soup.price is None
    assert soup.diets == ["*", "G", "ILM", "L", "M", "Veg", "VS"]
    assert soup.allergens == []
    assert soup.description is None

    curry = _by_name(menu, "Testikikhernecurry")
    assert curry.category == "Esimerkki kasvislounas"
    assert curry.price.startswith("opiskelija 2,40 €")
    assert curry.allergens == ["A"]
    assert "A" not in curry.diets

    names = [d.name for d in menu.dishes]
    assert "Esimerkkijogurttikastiketta" in names  # trailing newline from the site is stripped
    assert len({d.id for d in menu.dishes}) == len(menu.dishes)


async def test_macros_come_from_recipe_endpoint_per_100g() -> None:
    menu = await _fetch(ALVARI, CompassStub())

    soup = _by_name(menu, "Testikeitto basilikalla").macros
    assert soup is not None
    assert soup.basis == "100g"
    assert soup.portion_g is None
    assert soup.energy_kcal == 48
    assert soup.energy_kj == 201
    assert soup.protein_g == 1.1
    assert soup.carbohydrates_g == 5.4
    assert soup.sugars_g == 3.2
    assert soup.fat_g == 2.1
    assert soup.saturated_fat_g == 0.3
    assert soup.fibre_g == 1.2
    assert soup.salt_g == 0.5

    curry = _by_name(menu, "Testikikhernecurry").macros
    assert curry is not None and curry.energy_kcal == 112 and curry.protein_g == 5.9


async def test_recipe_without_nutrition_is_not_a_failure() -> None:
    # Recipe 40005 is not recorded, so the stub answers 404, which means "no nutrition".
    menu = await _fetch(ALVARI, CompassStub())

    assert _by_name(menu, "Esimerkkijogurttikastiketta").macros is None
    assert not any("Nutrition" in note for note in menu.notes)


async def test_recipe_server_error_is_reported_in_notes() -> None:
    stub = CompassStub(recipes={40001: httpx.Response(500)})
    menu = await _fetch(ALVARI, stub)

    assert _by_name(menu, "Testikeitto basilikalla").macros is None
    assert "Nutrition could not be fetched for 1 recipe(s)." in menu.notes


async def test_closed_day_has_no_dishes_and_a_note() -> None:
    closed = _fixture("synthetic-day-alvari-2026-11-01-fi-closed.json")
    menu = await _fetch(ALVARI, CompassStub(days={("0190", "fi"): closed}), day=SUNDAY)

    assert menu.dishes == []
    assert menu.notes == ["Closed, or no lunch menu published for this day."]
    assert menu.date == SUNDAY


async def test_english_menu_uses_english_names() -> None:
    menu = await _fetch(ALVARI, CompassStub(), lang="en")

    assert menu.lang == "en"
    assert menu.notes == []
    soup = _by_name(menu, "Test soup with basil")
    assert soup.category == "Example soup"
    assert soup.macros is not None and soup.macros.energy_kcal == 48


async def test_english_failure_falls_back_to_finnish_with_note() -> None:
    stub = CompassStub(days={("0190", "en"): httpx.Response(503)})
    menu = await _fetch(ALVARI, stub, lang="en")

    assert menu.lang == "fi"
    assert menu.notes == ["English menu unavailable; showing the Finnish menu."]
    assert len(menu.dishes) == 9
    assert menu.dishes[0].name == "Testikeitto basilikalla"


async def test_set_menu_components_are_separate_dishes_with_set_context() -> None:
    menu = await _fetch(DIPOLI, CompassStub())

    crokettes = _by_name(menu, "Testikroketteja")
    assert crokettes.category == "Esimerkki kasvislounas"
    assert crokettes.description is not None
    assert crokettes.description.startswith("Part of set: Testikroketteja (*, G, ILM")
    assert crokettes.macros is None  # recipe 40010 is not recorded

    potatoes = _by_name(menu, "Paahdettua testiperunaa")
    assert potatoes.description is None  # standalone meal, not part of a set

    assert menu.notes == []
    assert len(menu.dishes) == 12
    assert len({d.id for d in menu.dishes}) == len(menu.dishes)


async def test_lunch_hours_come_from_directory_details() -> None:
    menu = await _fetch(ALVARI, CompassStub())

    assert menu.lunch_hours is not None
    assert "lounas 10.30-14.00" in menu.lunch_hours
    assert "Testikahvila (H-siipi)" in menu.lunch_hours


async def test_directory_failure_leaves_hours_unset_and_menu_intact() -> None:
    # Without a configured content_id the adapter has to search the directory first.
    alvari = ALVARI.model_copy(update={"config": {"cost_number": "0190"}})
    stub = CompassStub(search=httpx.Response(500))
    menu = await _fetch(alvari, stub)

    assert menu.lunch_hours is None
    assert len(menu.dishes) == 9


async def test_duplicate_dish_ids_get_numeric_suffixes() -> None:
    line = {"name": "Testimuusi", "recipeId": 0, "diets": ["G"], "bundleId": None}
    day = {
        "menuPackages": [
            {"name": "Lounas", "price": "", "meals": [line], "bundles": []},
            {"name": "Lounas", "price": "", "meals": [line], "bundles": []},
        ]
    }
    menu = await _fetch(ALVARI, CompassStub(days={("0190", "fi"): day}))

    assert [d.id for d in menu.dishes] == ["lounas-testimuusi", "lounas-testimuusi-2"]


async def test_free_text_day_is_reported_not_parsed() -> None:
    day = {"menuPackages": [], "html": "<p>Erikoispäivä</p>", "isManualMenu": True}
    menu = await _fetch(ALVARI, CompassStub(days={("0190", "fi"): day}))

    assert menu.dishes == []
    assert menu.notes == ["Free-text menu, not parsed."]


async def test_missing_cost_number_is_an_adapter_error() -> None:
    restaurant = ALVARI.model_copy(update={"config": {}})
    with pytest.raises(AdapterError, match="cost_number"):
        await _fetch(restaurant, CompassStub())


async def test_unexpected_http_status_on_day_menu_raises() -> None:
    stub = CompassStub(days={("0190", "fi"): httpx.Response(500)})
    with pytest.raises(AdapterError, match="HTTP 500"):
        await _fetch(ALVARI, stub)


@pytest.mark.live
async def test_live_weekday_menu_for_every_compass_restaurant() -> None:
    today = dt.date.today()
    day = today + dt.timedelta(days=1)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    compass = [r for r in RESTAURANTS if r.provider == "compass"]
    adapter = CompassAdapter()

    async with httpx.AsyncClient(
        timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        menus = await asyncio.gather(*(adapter.fetch_menu(r, day, "fi", client) for r in compass))

    for restaurant, menu in zip(compass, menus, strict=True):
        assert menu.restaurant_id == restaurant.id
        assert menu.dishes, f"{restaurant.id} has no dishes on {day}: {menu.notes}"
        assert len({d.id for d in menu.dishes}) == len(menu.dishes)
        assert all(d.name and d.id for d in menu.dishes)
        assert any(d.macros is not None for d in menu.dishes), restaurant.id
