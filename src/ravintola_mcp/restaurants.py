"""Registry of supported restaurants and name/alias resolution.

Provider-specific ids in ``config`` were taken from Kanttiinit's restaurant list
(https://kitchen.kanttiinit.fi/restaurants), which records each restaurant's upstream feed.
"""

from __future__ import annotations

from ravintola_mcp.adapters.base import slugify
from ravintola_mcp.models import Restaurant

_COMPASS = "https://www.compass-group.fi/ravintolat-ja-ruokalistat/foodco/kaupungit/espoo"

RESTAURANTS: list[Restaurant] = [
    Restaurant(
        id="a-bloc",
        name="A Bloc",
        aliases=["abloc", "a block", "ablock"],
        campus="Otaniemi",
        provider="compass",
        operator="Compass Group Finland (FoodCo)",
        url=f"{_COMPASS}/a-bloc/",
        config={"cost_number": "3087", "content_id": "3371"},
    ),
    Restaurant(
        id="tuas",
        name="TUAS",
        aliases=["tuas aalto"],
        campus="Otaniemi",
        provider="compass",
        operator="Compass Group Finland (FoodCo)",
        url=f"{_COMPASS}/tuas-aalto-yliopisto/",
        config={"cost_number": "0199", "content_id": "3321"},
    ),
    Restaurant(
        id="t-talo",
        name="Tietotekniikan talo (T-talo)",
        aliases=["ttalo", "tietotekniikan talo", "cs building", "computer science building"],
        campus="Otaniemi",
        provider="sodexo",
        operator="Sodexo",
        url="https://www.sodexo.fi/ravintolat/espoo/aalto-tietotekniikantalo",
        config={"restaurant_id": "6754"},
    ),
    Restaurant(
        id="taffa",
        name="Täffä",
        aliases=["täffä", "tf", "teknologforeningen"],
        campus="Otaniemi",
        provider="taffa",
        operator="Teknologföreningen (Täffä)",
        url="https://lunch.tf.fi",
    ),
    Restaurant(
        id="menssa",
        name="Menssa",
        aliases=[],
        campus="Otaniemi",
        provider="menssa",
        operator="Menssa",
        url="https://menssa.fi/lounas/",
    ),
    Restaurant(
        id="kvarkki",
        name="Aalto Kvarkki",
        aliases=["aalto kvarkki"],
        campus="Otaniemi",
        provider="sodexo",
        operator="Sodexo",
        url="https://www.sodexo.fi/ravintolat/espoo/aalto-kvarkki",
        config={"restaurant_id": "86"},
    ),
    Restaurant(
        id="kipsari",
        name="Kipsari Väre",
        aliases=["kipsari vare", "vare", "väre"],
        campus="Otaniemi",
        provider="kipsari",
        operator="Kipsari",
        url="https://www.kipsari.com",
        config={"feed": "rss-vare"},
    ),
    Restaurant(
        id="dipoli",
        name="Dipoli",
        aliases=["dipoli ravintolat"],
        campus="Otaniemi",
        provider="compass",
        operator="Compass Group Finland (FoodCo)",
        url=f"{_COMPASS}/dipoli-ravintolat/",
        config={"cost_number": "3101", "content_id": "3684"},
    ),
    Restaurant(
        id="alvari",
        name="Alvari",
        aliases=[],
        campus="Otaniemi",
        provider="compass",
        operator="Compass Group Finland (FoodCo)",
        url=f"{_COMPASS}/alvari/",
        config={"cost_number": "0190", "content_id": "3445"},
    ),
    Restaurant(
        id="unicafe-kaivopiha",
        name="Unicafe Kaivopiha",
        aliases=["kaivopiha", "unicafe", "unicafe keskusta"],
        campus="Helsinki city centre",
        provider="unicafe",
        operator="Unicafe",
        url="https://menu.unicafe.fi",
        config={"slug": "kaivopiha"},
    ),
]

_BY_KEY: dict[str, Restaurant] = {}
for _r in RESTAURANTS:
    for _key in (_r.id, _r.name, *_r.aliases):
        _BY_KEY[slugify(_key).replace("-", "")] = _r


def resolve_restaurant(name: str) -> Restaurant:
    """Resolve an id, display name or alias (case/diacritic/punctuation-insensitive)."""
    key = slugify(name).replace("-", "")
    if key in _BY_KEY:
        return _BY_KEY[key]
    matches = {r.id: r for k, r in _BY_KEY.items() if key and (key in k or k in key)}
    if len(matches) == 1:
        return next(iter(matches.values()))
    known = ", ".join(r.id for r in RESTAURANTS)
    raise ValueError(f"Unknown restaurant {name!r}. Known restaurants: {known}")
