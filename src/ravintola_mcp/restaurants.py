"""Registry of supported restaurants and name/alias resolution.

Provider-specific ids in ``config`` are filled in as each adapter is implemented
(see docs/research/ for how they were found).
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
        url=f"{_COMPASS}/a-bloc/",
    ),
    Restaurant(
        id="tuas",
        name="TUAS",
        aliases=["tuas aalto"],
        campus="Otaniemi",
        provider="compass",
        url=f"{_COMPASS}/tuas-aalto-yliopisto/",
    ),
    Restaurant(
        id="t-talo",
        name="Tietotekniikan talo (T-talo)",
        aliases=["ttalo", "tietotekniikan talo", "cs building", "computer science building"],
        campus="Otaniemi",
        provider="kanttiinit",
        url="https://kanttiinit.fi/restaurant/2",
        config={"restaurant_id": "2"},
    ),
    Restaurant(
        id="taffa",
        name="Täffä",
        aliases=["täffä", "tf", "teknologforeningen"],
        campus="Otaniemi",
        provider="taffa",
        url="https://lunch.tf.fi",
    ),
    Restaurant(
        id="menssa",
        name="Menssa",
        aliases=[],
        campus="Otaniemi",
        provider="menssa",
        url="https://menssa.fi",
    ),
    Restaurant(
        id="kvarkki",
        name="Aalto Kvarkki",
        aliases=["aalto kvarkki"],
        campus="Otaniemi",
        provider="sodexo",
        url="https://www.sodexo.fi/ravintolat/espoo/aalto-kvarkki",
    ),
    Restaurant(
        id="kipsari",
        name="Kipsari",
        aliases=[],
        campus="Otaniemi",
        provider="kipsari",
        url="https://www.kipsari.com",
    ),
    Restaurant(
        id="dipoli",
        name="Dipoli",
        aliases=["dipoli ravintolat"],
        campus="Otaniemi",
        provider="compass",
        url=f"{_COMPASS}/dipoli-ravintolat/",
    ),
    Restaurant(
        id="alvari",
        name="Alvari",
        aliases=[],
        campus="Otaniemi",
        provider="compass",
        url=f"{_COMPASS}/alvari/",
    ),
    Restaurant(
        id="unicafe-kaivopiha",
        name="Unicafe Kaivopiha",
        aliases=["kaivopiha", "unicafe", "unicafe keskusta"],
        campus="Helsinki city centre",
        provider="unicafe",
        url="https://menu.unicafe.fi",
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
