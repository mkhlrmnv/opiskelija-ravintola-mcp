import json

import pytest

from ravintola_mcp.models import Macros, Menu
from ravintola_mcp.service import MIXED_BASIS_NOTE, MenuService, SortBy
from tests.fakes import make_dish, make_menu


def _menus() -> list[Menu]:
    kana = make_dish(
        "kana",
        "Kana",
        macros=Macros(basis="portion", protein_g=40, energy_kcal=600, fat_g=20, carbohydrates_g=60),
        diets=["G"],
    )
    pasta = make_dish(
        "pasta",
        "Pasta",
        macros=Macros(
            basis="portion", protein_g=20, energy_kcal=800, fat_g=30, carbohydrates_g=100
        ),
    )
    salad = make_dish("salad", "Salaatti")  # no macros at all
    tofu = make_dish(
        "tofu",
        "Tofu",
        macros=Macros(basis="portion", protein_g=25),  # protein only, no energy
        diets=["VEG", "G"],
    )
    lohi = make_dish(
        "lohi",
        "Lohi",
        macros=Macros(basis="portion", protein_g=35, energy_kj=2092, fat_g=10),  # 500 kcal
        diets=["G", "L"],
    )
    return [
        make_menu("a-bloc", "A Bloc", [kana, pasta, salad, tofu]),
        make_menu("tuas", "TUAS", [lohi]),
    ]


def _names(rows: list[dict]) -> list[str]:
    return [row["dish"]["name"] for row in rows]


def test_only_dishes_with_macros_are_returned() -> None:
    rows = MenuService.search_by_macros(_menus())
    assert sorted(_names(rows)) == ["Kana", "Lohi", "Pasta", "Tofu"]


def test_row_shape_keeps_full_dish_and_basis() -> None:
    row = MenuService.search_by_macros(_menus(), min_protein_g=40)[0]
    assert set(row) == {"restaurant_id", "restaurant_name", "dish", "macro_basis"}
    assert row["restaurant_id"] == "a-bloc"
    assert row["restaurant_name"] == "A Bloc"
    assert row["macro_basis"] == "portion"
    assert row["dish"]["macros"]["protein_g"] == 40
    assert row["dish"]["diets"] == ["G"]


def test_min_protein_excludes_dishes_below_or_missing_the_value() -> None:
    assert _names(MenuService.search_by_macros(_menus(), min_protein_g=30)) == ["Kana", "Lohi"]


def test_max_kcal_excludes_dishes_without_energy() -> None:
    rows = MenuService.search_by_macros(_menus(), max_kcal=650)
    assert sorted(_names(rows)) == ["Kana", "Lohi"]


def test_kcal_is_derived_from_kj_when_kcal_is_missing() -> None:
    rows = MenuService.search_by_macros(_menus(), max_kcal=550)
    assert _names(rows) == ["Lohi"]
    rows = MenuService.search_by_macros(_menus(), min_kcal=550)
    assert _names(rows) == ["Kana", "Pasta"]


def test_fat_and_carb_limits() -> None:
    assert _names(MenuService.search_by_macros(_menus(), max_fat_g=15)) == ["Lohi"]
    assert _names(MenuService.search_by_macros(_menus(), max_carbs_g=80)) == ["Kana"]


def test_diets_are_case_insensitive_and_must_all_match() -> None:
    assert _names(MenuService.search_by_macros(_menus(), diets=["g"])) == ["Kana", "Lohi", "Tofu"]
    assert _names(MenuService.search_by_macros(_menus(), diets=["g", "l"])) == ["Lohi"]
    assert MenuService.search_by_macros(_menus(), diets=["G", "VEG", "L"]) == []


@pytest.mark.parametrize(
    ("sort_by", "expected"),
    [
        ("protein_desc", ["Kana", "Lohi", "Tofu", "Pasta"]),
        ("kcal_asc", ["Lohi", "Kana", "Pasta", "Tofu"]),  # Tofu has no kcal: last
        ("kcal_desc", ["Pasta", "Kana", "Lohi", "Tofu"]),
        ("protein_per_kcal_desc", ["Lohi", "Kana", "Pasta", "Tofu"]),  # Tofu: no kcal: last
    ],
)
def test_sorting(sort_by: SortBy, expected: list[str]) -> None:
    rows = MenuService.search_by_macros(_menus(), sort_by=sort_by)
    assert _names(rows) == expected


def test_limit_is_applied_after_sorting() -> None:
    assert _names(MenuService.search_by_macros(_menus(), limit=2)) == ["Kana", "Lohi"]


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit"):
        MenuService.search_by_macros(_menus(), limit=0)


def test_no_note_when_all_values_share_a_basis() -> None:
    rows = MenuService.search_by_macros(_menus())
    assert all("note" not in row for row in rows)


def test_note_on_every_row_when_portion_and_100g_are_mixed() -> None:
    menus = _menus()
    per_100g = make_dish("soup", "Keitto", macros=Macros(basis="100g", energy_kcal=50, protein_g=3))
    menus.append(make_menu("kvarkki", "Aalto Kvarkki", [per_100g]))
    rows = MenuService.search_by_macros(menus, min_protein_g=3)
    assert len(rows) == 5
    assert all(row["note"] == MIXED_BASIS_NOTE for row in rows)
    assert {row["macro_basis"] for row in rows} == {"portion", "100g"}


def test_rows_are_json_serialisable() -> None:
    rows = MenuService.search_by_macros(_menus(), min_protein_g=20)
    json.dumps(rows)
