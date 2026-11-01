import datetime as dt

import pytest

from ravintola_mcp.models import Dish, DishComponent, Macros, Menu


def test_kj_only_fills_kcal() -> None:
    macros = Macros(basis="100g", energy_kj=2092)
    assert macros.energy_kcal == 500.0
    assert macros.energy_kj == 2092


def test_kcal_only_fills_kj() -> None:
    macros = Macros(basis="portion", energy_kcal=600)
    assert macros.energy_kj == 2510.4
    assert macros.energy_kcal == 600


def test_kj_to_kcal_is_rounded_to_one_decimal() -> None:
    assert Macros(energy_kj=989.8).energy_kcal == 236.6


def test_both_energy_units_are_left_untouched() -> None:
    macros = Macros(energy_kcal=500, energy_kj=2100)
    assert macros.energy_kcal == 500
    assert macros.energy_kj == 2100


def test_no_energy_stays_unset() -> None:
    macros = Macros(protein_g=10)
    assert macros.energy_kcal is None
    assert macros.energy_kj is None


def _menu(dishes: list[Dish]) -> Menu:
    return Menu(
        restaurant_id="t-talo",
        restaurant_name="T-talo",
        date=dt.date(2026, 11, 2),
        lang="fi",
        dishes=dishes,
    )


def test_macros_available_when_only_a_component_has_macros() -> None:
    dish = Dish(
        id="lihapullat",
        name="Lihapullat",
        components=[
            DishComponent(name="Lihapyöryköitä", macros=Macros(basis="100g", protein_g=14.0)),
            DishComponent(name="Kastike"),
        ],
    )
    assert _menu([dish]).macros_available is True


def test_macros_not_available_when_components_have_no_values() -> None:
    dish = Dish(
        id="lihapullat",
        name="Lihapullat",
        components=[DishComponent(name="Lihapyöryköitä"), DishComponent(name="Kastike")],
    )
    assert _menu([dish]).macros_available is False


@pytest.mark.parametrize("with_components", [False, True])
def test_macros_available_when_only_the_dish_has_macros(with_components: bool) -> None:
    components = [DishComponent(name="Osa")] if with_components else []
    dish = Dish(
        id="kana",
        name="Kana",
        macros=Macros(basis="portion", protein_g=40),
        components=components,
    )
    assert _menu([dish]).macros_available is True
