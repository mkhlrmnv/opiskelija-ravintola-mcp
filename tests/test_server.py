import json
from collections.abc import Iterator

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from ravintola_mcp import server
from ravintola_mcp.dates import resolve_date
from ravintola_mcp.models import DishComponent, Macros
from ravintola_mcp.restaurants import RESTAURANTS
from ravintola_mcp.service import MenuService
from tests.fakes import FakeAdapter, make_dish, make_menu

ISO = "2026-11-02"


@pytest.fixture
def service(http_client: httpx.AsyncClient) -> Iterator[MenuService]:
    menus = {
        "a-bloc": make_menu(
            "a-bloc",
            "A Bloc",
            [
                make_dish(
                    "kana",
                    "Kana",
                    macros=Macros(basis="portion", protein_g=40, energy_kcal=600),
                    diets=["G"],
                ),
                make_dish("salad", "Salaatti"),
                make_dish(
                    "lihapullat",
                    "Lihapullia ja muusia",
                    components=[
                        DishComponent(
                            name="Lihapyöryköitä",
                            macros=Macros(basis="100g", energy_kj=913.5, protein_g=14.0),
                        ),
                        DishComponent(
                            name="Perunamuusia",
                            macros=Macros(basis="100g", energy_kj=336.7, protein_g=2.0),
                        ),
                        DishComponent(name="Kastike"),  # no values published
                    ],
                ),
            ],
        ),
        "tuas": make_menu("tuas", "TUAS", [make_dish("pasta", "Pasta")]),
    }
    adapters = {
        "compass": FakeAdapter("compass", menus=menus),
        "sodexo": FakeAdapter("sodexo", failures={"kvarkki": RuntimeError("site down")}),
    }
    previous = server._service
    fake = MenuService(adapters=adapters, client=http_client)
    server.set_service(fake)
    yield fake
    server.set_service(previous)


def test_list_restaurants_hides_provider_internals() -> None:
    result = server.list_restaurants()
    assert len(result) == len(RESTAURANTS)
    assert set(result[0]) == {"id", "name", "aliases", "campus", "operator", "url"}
    assert all(r["operator"] for r in result)


def test_server_instructions_carry_the_disclaimer() -> None:
    assert server.DISCLAIMER in (server.mcp.instructions or "")
    assert "not affiliated" in server.DISCLAIMER


async def test_get_menu_strips_macros_and_flags_availability(service: MenuService) -> None:
    menu = await server.get_menu("A Bloc", ISO)
    assert isinstance(menu, dict)
    assert menu["restaurant_id"] == "a-bloc"
    assert menu["date"] == ISO
    assert menu["macros_available"] is True
    assert [d["name"] for d in menu["dishes"]] == ["Kana", "Salaatti", "Lihapullia ja muusia"]
    assert all("macros" not in d for d in menu["dishes"])


async def test_get_menu_strips_component_macros_but_keeps_names(service: MenuService) -> None:
    menu = await server.get_menu("A Bloc", ISO)
    assert isinstance(menu, dict)
    components = menu["dishes"][2]["components"]
    assert [c["name"] for c in components] == ["Lihapyöryköitä", "Perunamuusia", "Kastike"]
    assert all(set(c) == {"name"} for c in components)


async def test_get_menu_reports_when_no_macros_are_published(service: MenuService) -> None:
    menu = await server.get_menu("tuas", ISO)
    assert isinstance(menu, dict)
    assert menu["macros_available"] is False


async def test_get_menu_without_restaurant_returns_every_menu(service: MenuService) -> None:
    menus = await server.get_menu(None, ISO)
    assert isinstance(menus, list)
    assert len(menus) == len(RESTAURANTS)
    assert all("macros_available" in m for m in menus)


async def test_get_full_menu_includes_macros(service: MenuService) -> None:
    menu = await server.get_full_menu("a-bloc", ISO)
    assert isinstance(menu, dict)
    assert menu["dishes"][0]["macros"]["protein_g"] == 40
    assert menu["dishes"][1]["macros"] is None
    assert menu["macros_available"] is True
    multi = menu["dishes"][2]
    assert multi["macros"] is None
    assert multi["components"][0] == {
        "name": "Lihapyöryköitä",
        "macros": {
            "basis": "100g",
            "portion_g": None,
            "energy_kcal": 218.3,
            "energy_kj": 913.5,
            "protein_g": 14.0,
            "carbohydrates_g": None,
            "sugars_g": None,
            "fat_g": None,
            "saturated_fat_g": None,
            "fibre_g": None,
            "salt_g": None,
        },
    }
    assert multi["components"][2]["macros"] is None


async def test_failed_restaurant_is_reported_in_its_menu(service: MenuService) -> None:
    menu = await server.get_menu("kvarkki", ISO)
    assert isinstance(menu, dict)
    assert menu["error"] == "Failed to fetch menu: site down"
    assert menu["dishes"] == []


async def test_weekday_names_are_accepted(service: MenuService) -> None:
    menu = await server.get_menu("tuas", "maanantai")
    assert isinstance(menu, dict)
    assert menu["date"] == resolve_date("maanantai").isoformat()


async def test_get_macros_returns_values(service: MenuService) -> None:
    result = await server.get_macros("a-bloc", "kana", ISO)
    assert result["dish_id"] == "kana"
    assert result["dish_name"] == "Kana"
    assert result["macros"]["energy_kcal"] == 600
    assert result["message"] is None
    assert result["source"] == "Source: Compass Group Finland (FoodCo) (compass-group.fi)"
    assert result["disclaimer"] == server.DISCLAIMER


async def test_get_macros_explains_when_site_publishes_none(service: MenuService) -> None:
    result = await server.get_macros("a-bloc", "Salaatti", ISO)
    assert result["macros"] is None
    assert result["components"] == []
    assert "publishes no nutrition values" in result["message"]


async def test_get_macros_returns_components_for_multi_component_dish(
    service: MenuService,
) -> None:
    result = await server.get_macros("a-bloc", "Lihapullia", ISO)
    assert result["dish_id"] == "lihapullat"
    assert result["macros"] is None
    assert result["message"] is None
    assert [c["name"] for c in result["components"]] == [
        "Lihapyöryköitä",
        "Perunamuusia",
        "Kastike",
    ]
    assert result["components"][0]["macros"]["protein_g"] == 14.0
    assert result["components"][2]["macros"] is None


async def test_get_macros_message_when_neither_dish_nor_components_have_values(
    http_client: httpx.AsyncClient,
) -> None:
    dish = make_dish("bare", "Bare", components=[DishComponent(name="Osa")])
    menus = {"a-bloc": make_menu("a-bloc", "A Bloc", [dish])}
    fake = MenuService(
        adapters={"compass": FakeAdapter("compass", menus=menus)}, client=http_client
    )
    previous = server._service
    server.set_service(fake)
    try:
        result = await server.get_macros("a-bloc", "Bare", ISO)
    finally:
        server.set_service(previous)
    assert result["components"] == [{"name": "Osa", "macros": None}]
    assert "publishes no nutrition values" in result["message"]


async def test_get_macros_unknown_dish_lists_available_names(service: MenuService) -> None:
    with pytest.raises(ValueError, match="Available dishes: Kana, Salaatti"):
        await server.get_macros("a-bloc", "Pizza", ISO)


async def test_get_macros_on_unavailable_menu_raises(service: MenuService) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        await server.get_macros("kvarkki", ISO)


async def test_search_dishes_by_macros_returns_json_rows(service: MenuService) -> None:
    rows = await server.search_dishes_by_macros(date=ISO, min_protein_g=30)
    assert [r["dish"]["name"] for r in rows] == ["Kana"]
    json.dumps(rows)


async def test_search_can_be_limited_to_some_restaurants(service: MenuService) -> None:
    assert await server.search_dishes_by_macros(date=ISO, restaurants=["tuas"]) == []


async def test_invalid_restaurant_and_date_raise_value_error(service: MenuService) -> None:
    with pytest.raises(ValueError, match="Unknown restaurant"):
        await server.get_menu("Pizzeria", ISO)
    with pytest.raises(ValueError, match="Unrecognised date"):
        await server.get_menu("a-bloc", "soon")


async def test_tools_are_registered_with_descriptions() -> None:
    tools = {t.name: t for t in await server.mcp.list_tools()}
    assert set(tools) == {
        "list_restaurants",
        "get_menu",
        "get_full_menu",
        "get_macros",
        "search_dishes_by_macros",
    }
    assert all(t.description for t in tools.values())
    assert "tomorrow" in (tools["get_menu"].description or "")


async def test_invalid_restaurant_surfaces_as_tool_error(service: MenuService) -> None:
    with pytest.raises(ToolError, match="Unknown restaurant"):
        await server.mcp.call_tool("get_menu", {"restaurant": "Pizzeria"})
