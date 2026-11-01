import pytest

from ravintola_mcp.restaurants import resolve_restaurant


@pytest.mark.parametrize(
    ("name", "expected_id"),
    [
        ("a-bloc", "a-bloc"),
        ("A Bloc", "a-bloc"),
        ("A Block", "a-bloc"),
        ("täffä", "taffa"),
        ("Täffä", "taffa"),
        ("T-talo", "t-talo"),
        ("tietotekniikan talo", "t-talo"),
        ("kaivopiha", "unicafe-kaivopiha"),
    ],
)
def test_resolves_ids_names_and_aliases(name: str, expected_id: str) -> None:
    assert resolve_restaurant(name).id == expected_id


def test_unknown_restaurant_raises_with_known_ids() -> None:
    with pytest.raises(ValueError, match="Unknown restaurant 'Pizzeria'.*a-bloc"):
        resolve_restaurant("Pizzeria")
