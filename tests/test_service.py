import re

import httpx
import pytest

from ravintola_mcp.adapters.base import USER_AGENT
from ravintola_mcp.models import Menu
from ravintola_mcp.restaurants import RESTAURANTS
from ravintola_mcp.service import MenuService
from tests.fakes import DAY, FakeAdapter, make_dish, make_menu


@pytest.fixture
def compass() -> FakeAdapter:
    menus = {
        "a-bloc": make_menu(
            "a-bloc",
            "A Bloc",
            [make_dish("kasvispihvi", "Kasvispihvi"), make_dish("lohi", "Lohikeitto")],
        )
    }
    return FakeAdapter("compass", menus=menus)


@pytest.fixture
def sodexo() -> FakeAdapter:
    return FakeAdapter("sodexo", failures={"kvarkki": RuntimeError("site down")})


@pytest.fixture
def service(
    compass: FakeAdapter, sodexo: FakeAdapter, http_client: httpx.AsyncClient
) -> MenuService:
    return MenuService(adapters={"compass": compass, "sodexo": sodexo}, client=http_client)


async def test_get_menu_fetches_once_and_then_serves_from_cache(
    service: MenuService, compass: FakeAdapter
) -> None:
    first = await service.get_menu("A Bloc", DAY, "en")
    second = await service.get_menu("a-bloc", DAY, "en")
    assert first.restaurant_name == "A Bloc"
    assert first.date == DAY
    assert [d.name for d in first.dishes] == ["Kasvispihvi", "Lohikeitto"]
    assert second is first
    assert compass.calls == [("a-bloc", DAY, "en")]


async def test_unregistered_provider_returns_not_implemented_error_menu(
    service: MenuService,
) -> None:
    menu = await service.get_menu("menssa", DAY, "en")
    assert menu.error == "Adapter for provider 'menssa' is not implemented yet"
    assert menu.dishes == []


async def test_adapter_exception_becomes_error_message_only(service: MenuService) -> None:
    menu = await service.get_menu("kvarkki", DAY, "en")
    assert menu.error == "Failed to fetch menu: site down"
    assert menu.restaurant_id == "kvarkki"
    assert menu.source_url is not None


async def test_exception_without_message_reports_its_class(
    http_client: httpx.AsyncClient,
) -> None:
    adapter = FakeAdapter("compass", failures={"a-bloc": TimeoutError()})
    service = MenuService(adapters={"compass": adapter}, client=http_client)
    menu = await service.get_menu("a-bloc", DAY, "en")
    assert menu.error == "Failed to fetch menu: TimeoutError"


async def test_get_menus_for_all_restaurants_isolates_failures(service: MenuService) -> None:
    menus = await service.get_menus(None, DAY, "en")
    assert [m.restaurant_id for m in menus] == [r.id for r in RESTAURANTS]
    by_id = {m.restaurant_id: m for m in menus}
    assert by_id["kvarkki"].error == "Failed to fetch menu: site down"
    assert by_id["a-bloc"].error is None
    assert len(by_id["a-bloc"].dishes) == 2
    assert by_id["tuas"].notes == ["closed"]
    assert by_id["taffa"].error == "Adapter for provider 'taffa' is not implemented yet"


async def test_get_menus_resolves_aliases_and_drops_duplicates(service: MenuService) -> None:
    menus = await service.get_menus(["tuas", "A Bloc", "a-bloc"], DAY, "en")
    assert [m.restaurant_id for m in menus] == ["tuas", "a-bloc"]


async def test_get_menus_with_empty_list_means_all_restaurants(service: MenuService) -> None:
    menus = await service.get_menus([], DAY, "en")
    assert len(menus) == len(RESTAURANTS)


async def test_get_menu_rejects_unknown_restaurant(service: MenuService) -> None:
    with pytest.raises(ValueError, match="Unknown restaurant"):
        await service.get_menu("Pizzeria", DAY, "en")


async def test_aclose_does_not_close_injected_client(
    service: MenuService, http_client: httpx.AsyncClient
) -> None:
    await service.aclose()
    assert not http_client.is_closed


async def test_owned_client_is_created_lazily_with_user_agent_and_closed() -> None:
    adapter = FakeAdapter("compass")
    service = MenuService(adapters={"compass": adapter})
    await service.get_menu("a-bloc", DAY, "en")
    client = service._http()
    assert client.headers["user-agent"] == USER_AGENT
    assert client.follow_redirects
    await service.aclose()
    assert client.is_closed


def _dish_menu() -> Menu:
    return make_menu(
        "a-bloc",
        "A Bloc",
        [
            make_dish("d1", "Lohikeitto"),
            make_dish("d2", "Kasvispihvi ja riisi"),
            make_dish("d3", "Kana curry"),
            make_dish("d4", "Kana wrap"),
        ],
    )


@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("d2", "Kasvispihvi ja riisi"),  # exact id
        ("LOHIKEITTO", "Lohikeitto"),  # exact name, case-insensitive
        ("  Kasvispihvi ja riisi ", "Kasvispihvi ja riisi"),
        ("kasvispihvi", "Kasvispihvi ja riisi"),  # substring
        ("kana", "Kana wrap"),  # several substrings: best difflib ratio wins
        ("Lohikeitot", "Lohikeitto"),  # typo: fuzzy match
    ],
)
def test_find_dish_matching_strategies(query: str, expected_name: str) -> None:
    assert MenuService.find_dish(_dish_menu(), query).name == expected_name


def test_find_dish_unknown_lists_available_dishes() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Available dishes: Lohikeitto, Kasvispihvi ja riisi, Kana curry, Kana wrap"
        ),
    ):
        MenuService.find_dish(_dish_menu(), "Pizza")


def test_find_dish_on_empty_query_raises() -> None:
    with pytest.raises(ValueError, match="No dish matching"):
        MenuService.find_dish(_dish_menu(), "  !!  ")


def test_find_dish_on_menu_without_dishes_mentions_error() -> None:
    menu = make_menu("a-bloc", "A Bloc", error="Failed to fetch menu: boom")
    with pytest.raises(ValueError, match="No dishes available.*Failed to fetch menu: boom"):
        MenuService.find_dish(menu, "Lohikeitto")
