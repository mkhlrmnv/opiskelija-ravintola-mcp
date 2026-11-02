# Täffä (Teknologföreningen, Otaniemi) - data source research

Status: **implemented** in `src/ravintola_mcp/adapters/taffa.py` (provider `taffa`). Verified
2026-11-02 (Monday, restaurant open). Adapter is not yet registered in `adapters/__init__.py`
(see section 6).

## 1. Source

The menu data is the JSON feed on `newapi.tf.fi`, which Kanttiinit also lists as Täffä's
`menuUrl` (`https://newapi.tf.fi/taffa/fi/json/week/`). It is reachable through the proxy; TLS
verification was never disabled.

`https://lunch.tf.fi` is a React SPA. Its HTML holds no menu, and its own API (`/api/menu/...`,
`/api/hours/...`) returns the SPA shell or empty values. The SPA's menu calls
(`menu/{today|week}/{lang}`, from the JS bundle `main.600004f5.js`) go to lunch.tf.fi's backend,
not to newapi, and the adapter does not use them.

## 2. Endpoints (probed 2026-11-02)

| URL | Result |
|---|---|
| `GET https://newapi.tf.fi/taffa/fi/json/week/` | 200 JSON list, 5 days (Mon 02.11. to Fri 06.11.2026), 2387 bytes |
| `GET .../taffa/en/json/week/` | 200 JSON list, same 5 days, 2986 bytes |
| `GET .../taffa/sv/json/week/` | 200 JSON list, same 5 days (not used: the model's `Lang` is `en`/`fi`) |
| `GET .../taffa/fi/json/week/?date=2026-11-03` and `?date=2026-11-06` | 200, both bodies byte-identical to the plain week. **The date parameter is ignored.** |
| `GET .../taffa/fi/json/today/` | 200, one JSON object (the Monday), 574 bytes. Not used: the week feed already has the day. |
| `GET .../taffa/fi/json/week/2026-11-09/`, `.../week/2026-10-26/`, `.../week/1/` | 500 (HTML error page). Dated paths are not supported. |
| `GET .../taffa/fi/json/day/...`, `.../fi/json/2026-11-03/`, `.../fi/json/`, `.../fi/json/hours/`, `.../fi/json/prices/` | 404 |
| `GET .../taffa/fi/json/week` (no slash) | 308 to `.../week/` |

Conclusion: **only the current week is served.** Each language has its own week feed.

## 3. JSON shape

A list with one object per weekday. Keys: `day` (ISO date), `dayName` (localised), and one key
per menu line. Lines are not fixed: Thursday 05.11 also has a `Leivonnaiset` / `Pastry` line.

```json
{"day": "2026-11-02", "dayName": "Maanantai",
 "Liha/kala": "Lohipyöryköitä, kermaviilikastike, perunamuussia",
 "Kasvisruoka": "Kasvispyörykät, chilimajoneesi (A, Ei sisällä pähkinöitä, G, KM, M, Soijaton, Veg)",
 "Delisalaatti": "Taboulehsalaattia ja tomaattihummus (A, Ei sisällä pähkinöitä, KM, M, Soijaton, Veg)",
 "A la carte": "Pintasavustettua kassleria, ... (A, Ei sisällä pähkinöitä, G, KM, L, Soijaton)",
 "Keitto": "Paprika-vuohenjuustokeitto (A, Ei sisällä pähkinöitä, G, KM, Soijaton, VL)"}
```

- The dish text is the name followed by a trailing parenthesis of tags. Names can contain
  parentheses (`Hernekeitto (myös vegaani)`), so a trailing group only counts as tags when it holds
  a known tag.
- Some names carry double spaces; the adapter collapses whitespace.
- The English feed uses the same days and the same line order, with English keys
  (`Fish/meat`, `Vegetarian option`, `Salad`, `Soup`, `Pastry`, `A la carte`) and English tags
  (`(Contains allergens, Gluten free, Vegan)`). The Swedish feed uses Swedish keys and tags.
- One English line is a placeholder: Friday's `Fish/meat` reads `Unnamed dish (Gluten free,
  Lactose free, Milk free)`, while Finnish says `Dukkah-broileri (G, L, M)`. The adapter uses the
  Finnish name for it and adds a note.

## 4. Diet codes (verified)

The Finnish feed's codes are the same codes the English feed spells out. The mapping below comes
from pairing each dish's Finnish codes with its English tags across the whole week (all 5 days).
For each code, the number of dishes carrying it equals the number carrying the English tag. The
single `VL` dish (Monday's soup) reads `Low lactose` in English.

| Code (fi) | Meaning (en tag) | Dishes in the week |
|---|---|---|
| `A` | Contains allergens (generic flag; specific allergens are not named) | 20 |
| `Ei sisällä pähkinöitä` | Contains no nuts | 19 |
| `KM` | Contains no eggs (kananmunaton) | 15 |
| `G` | Gluten free | 11 |
| `L` | Lactose free | 9 |
| `VL` | Low lactose | 1 |
| `M` | Milk free | 13 |
| `Soijaton` | Soy free | 13 |
| `Veg` | Vegan | 6 |

The adapter returns these codes in `Dish.diets`, for both languages, as published (the same
convention as `search_by_macros`'s `diets` filter). `Dish.allergens` stays empty: the feed only
says "contains allergens" and never names the allergens.

## 5. Other fields

- **Nutrition:** none. Searched all three language feeds and `today/` for `kcal`, `kj`, `energ`,
  `protein`, `fat`, `carb`, `rasva`, `hiilihyd` and similar: no matches. `Dish.macros` and
  `Dish.components` are always empty, so `macros_available` is false for Täffä.
- **Prices:** none in the feed (no `€`). lunch.tf.fi `api/prices/fi` returns `[]`. `Dish.price` is
  None.
- **Lunch hours:** not in the feed. lunch.tf.fi `api/hours/fi` returns an empty body. Kanttiinit's
  restaurant list has opening hours for Täffä, but they were not verified against a Täffä source.
  `Menu.lunch_hours` is None.
- **Closed days:** no closed day was observed. The Monday-to-Friday week has a full entry for each
  day. The adapter handles both a missing entry and an entry without menu lines as "closed", with
  a note. The shape of a real closed day is **unverified**.
- **Weekend and week rollover:** Monday only. It is unverified whether the feed moves to the next
  week on Friday, Saturday or Sunday, and what `week/` returns then. The adapter reports dates
  outside the feed's week as "no menu, feed covers only the current week".

## 6. Adapter behaviour

- `TaffaAdapter` (`provider = "taffa"`), plain `httpx` GET via the shared client.
- Date selection: the feed's `day` values must match the requested date. A date inside the feed's
  span with no entry means closed. A date outside the span means empty dishes plus a note
  naming the feed's range (`02.11.2026 to 06.11.2026`).
- `lang="en"` fetches both the English week (names, categories, tags) and the Finnish week (diet
  codes, and the fallback when the English week lacks the day). `lang="fi"` fetches only the
  Finnish week. A missing English day falls back to Finnish with a note.
- Category keys differ by language, so English lines are paired with Finnish lines through a fixed
  map (`_FI_TO_EN_CATEGORY`). Swedish is not implemented: the shared `Lang` type is `en`/`fi`.
- `Menu.source_url` is the week feed URL that supplied the menu lines (`.../en/json/week/` or
  `.../fi/json/week/`). The Finnish feed is always used for diet codes.
- Dish ids are ASCII slugs of the name, de-duplicated within the day (`lohi`, `lohi-2`).

## 7. Live result

`uv run pytest -m live tests/test_taffa.py` on 2026-11-02 (Monday): 5 dishes, example
`salmon-balls-sour-cream-sauce-mashed-potatoes`, category `Fish/meat`, name `Salmon balls, sour
cream sauce, mashed potatoes`, `diets=[]`, `macros=None`.

## 8. Fixtures

- `tests/fixtures/taffa/week-fi-2026-11-02.json` - Finnish week, as received.
- `tests/fixtures/taffa/week-en-2026-11-02.json` - English week, as received.

Closed-day and out-of-week cases are built from these fixtures in `tests/test_taffa.py`, not stored
as separate fixtures, because no real closed-day response was observed.

## 9. Still open

- [ ] Real closed-day response shape (a weekend or holiday, if the feed serves one).
- [ ] Whether the feed rolls over to next week before Monday, and when.
- [ ] Opening hours for the current location, from a Täffä source.
- [ ] Register `TaffaAdapter` in `src/ravintola_mcp/adapters/__init__.py` (shared file).

## 10. Registry and shared changes needed

- `src/ravintola_mcp/adapters/__init__.py`: `from ravintola_mcp.adapters.taffa import TaffaAdapter`,
  and add `TaffaAdapter()` to the `ADAPTERS` tuple. Until this is done the service returns "Adapter
  for provider 'taffa' is not implemented yet".
- `src/ravintola_mcp/restaurants.py`: the `taffa` entry (`provider="taffa"`, `url="https://lunch.tf.fi"`)
  already matches the adapter. No `config` keys are needed; the feed URLs are fixed in the adapter.
- Runtime network allowlist: `newapi.tf.fi` must be reachable over HTTPS. It was blocked in an
  earlier session; it works now.
