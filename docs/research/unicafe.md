# Unicafe (Kaivopiha) data source research

Status: IMPLEMENTED in `src/ravintola_mcp/adapters/unicafe.py`, verified live on 2026-11-02. This replaces the earlier BLOCKED note: `unicafe.fi` is reachable through the proxy now. Items are VERIFIED (seen in a live response, a fixture, or the shipped JS bundle) or INFERRED.

## 1. Endpoint and filtering (VERIFIED)

- Only data call: `GET https://unicafe.fi/wp-json/swiss/v1/restaurants?lang=<fi|en|sv>`. Response: `application/json; charset=UTF-8`, one list of all 21 Unicafe restaurants.
- Size: fi 1,026,115 bytes, en 900,817 bytes, sv 997,676 bytes. Every request downloads all of it.
- No filter exists. `&slug=kaivopiha` and `&id=2543` return the same full 1,026,115-byte body. `/restaurants/kaivopiha` and `/restaurants/2543` return 404. `lang=xx` returns HTTP 500 (HTML).
- Mitigation: the adapter caches the parsed list per language for 10 minutes (`CACHE_TTL_S`, injectable clock), and concurrent requests share one download.
- No date parameter. Each restaurant carries its own menu days, and the adapter picks the day.

## 2. Kaivopiha identity (VERIFIED)

- `slug`: `kaivopiha`. `id`: 2543. `title`: "Kaivopiha". Permalink `https://unicafe.fi/restaurants/kaivopiha/`. Address Mannerheimintie 3, Helsinki.
- Kanttiinit (`kitchen.kanttiinit.fi`, restaurant id 12) points at the same feed (`menuUrl` = `.../restaurants?lang=%lang%#kaivopiha`).

## 3. Date range and structure (VERIFIED)

- `menuData.menus` holds 14 days, from `Ma 02.11.` to `Su 15.11.` for the 2026-11-02 fetch (fi and en alike). Each day is `{date, message, data}`.
- `date` is a weekday abbreviation and `DD.MM.`, with no year (fi: Ma Ti Ke To Pe La Su; en: Mon Tue Wed ...). The adapter takes the candidate year nearest the requested day, so a range crossing New Year works.
- Sundays are listed with `data: []` (closed). `message` was `null` on every day seen.
- Dishes per day (Mon 02.11): 7 lines, of which 5 are lunch dishes and 2 are a side dish and a dessert. Lines per day in the first week (Mon to Sun): 7, 7, 7, 7, 7, 6, 0.
- Per dish: `name`, `ingredients` (free text, up to ~1,900 chars), `nutrition` (one string), `meta` (`"0"` diets, `"1"` allergens, `"2"` climate flag) and `price` (`{"value": [...], "name": "<menu line>"}`).

## 4. Lunch filter and menu lines (VERIFIED)

- `price.name` is the menu line. It stays Finnish in every language: `Vegaanilounas` (33 items in the week), `Lounas` (25), `Lisäke` (12), `Jälkiruoka` (12).
- Lunch dishes: everything except `Lisäke` (side dish) and `Jälkiruoka` (dessert). The site's bundle treats the same two categories as non-main dishes (`p = "dessert" !== f.id && "sideDish" !== f.id`).
- `Tiedote` (announcement) is not a dish. It appears on other restaurants (Viikuna: "Pizzaa tarjolla klo:13.30 saakka") and becomes a note.
- Kaivopiha's `Patonkibaari` (bread bar, `Lounas`) appears daily with no nutrition and no ingredients. It is kept as a dish with `macros: null`.

## 5. Nutrition (VERIFIED basis: per 100 g)

- Shape: one free-text string per dish, e.g. `Energia 481kJ, energia 115kcal, rasva 4,0g, josta tyydyttynyttä rasvaa 0,4g, hiilihydraatit 12g, josta sokereita 3,8g, proteiini 8,2g, suola 0,64g, ravintokuitua 2,3g, laktoosia 0g.` Parts are split on `", "` (the decimal comma is part of the number).
- Labels, identical in the fi and en payloads: Energia/energy (kJ and kcal), rasva/fat, josta tyydyttynyttä rasvaa/of which saturated fat, hiilihydraatit/carbohydrate, josta sokereita/of which sugars, proteiini/protein, suola/salt, ravintokuitua/fibre, laktoosia/lactose (no `Macros` field, dropped). Energy kJ = kcal × 4.184 holds (481 / 4.184 = 115).
- Values with a `<` (for example `josta sokereita <0,5g`) are upper bounds. They are not stored, so `sugars_g` is `null` there. Fibre is missing on one dish of 70.
- Basis evidence: the shipped bundle has the food-details label `"Ravintoarvo 100g"` (fi), `"Näringsvärde 100 g"` (sv) and `"Nutritional information per 100 g"` (en). The sample values are consistent with per-100 g: a casserole at 111 kcal and 12 g carbohydrate per portion would be too little for a full serving. Macros are therefore mapped with `basis="100g"` and `portion_g=None`.
- Fields filled: `energy_kj`, `energy_kcal` (both, since both are published), `fat_g`, `saturated_fat_g`, `carbohydrates_g`, `sugars_g`, `protein_g`, `salt_g`, `fibre_g`.

## 6. Diets, allergens, price, hours

- Diet codes (`meta["0"]`), kept as published. The bundle maps them as: `G` gluten-free, `L` lactose-free, `M` milk-free, `VL` low-lactose, `Veg` vegan, `Ilmastovalinta` low carbon footprint. `KELA` (45 occurrences) is not in that map; its meaning is UNVERIFIED. The adapter keeps it in `diets` as published.
- Allergens (`meta["1"]`): plain text in each language, for example `gluteenia sisältävät viljat` / `cereals containing gluten`, `rikkidioksidi ja sulfiitit` / `sulfur dioxide and sulfits`. `meta["2"]` only repeats `Ilmastovalinta` and is not used.
- Price: Kaivopiha's `price.value` is always `[]` in every language, so `Dish.price` is `null`. Other Unicafe restaurants publish `{"student": "3.10", "graduate": "6.35", "contract": "7.30", ...}`; the adapter formats such a dict as text. The dict shape is VERIFIED on other restaurants; Kaivopiha never reaches that branch.
- Lunch hours (`menuData.visitingHours.lounas.items`): Mon–Fri 11:00-19:45, Sat 11:30-17:00, Sun closed. Adapter output (fi): `Ma–Pe 11:00-19:45; La 11:30-17:00; Su Suljettu`. The en output is `Mon–Fri ...; Sun Closed`.

## 7. Languages

- `lang=en` has the same structure, translated names and nutrition labels (`Seitan & Hoi sin bowl`). The day labels are in English (`Mon 02.11.`). The `price.name` categories are still Finnish.
- `sv` exists but `Lang` is `en|fi`, so the adapter does not use it.
- Fallback: when the en feed errors, or its day has no dishes while fi has some, the adapter returns the fi menu with `lang="fi"` and the note "English menu unavailable; showing the Finnish menu." (same as Compass). A closed day in both languages returns the en menu with the closed note.

## 8. Live check (2026-11-02, Monday, VERIFIED)

- `adapter.fetch_menu(kaivopiha, 2026-11-02, "fi")`: 5 lunch dishes, no error, lunch hours as above, 2 side dish/dessert lines left out.
- Example: `Seitan - Hoi Sin bowl` (Vegaanilounas), diets `KELA`, `Veg`; macros basis `100g`: energy 115 kcal / 481 kJ, protein 8.2 g, carbohydrate 12 g, sugars 3.8 g, fat 4.0 g, saturated fat 0.4 g, fibre 2.3 g, salt 0.64 g.
- `2026-11-08` (Sunday): 0 dishes, note "No lunch menu is published for this day". `2026-11-20`: 0 dishes, note "No menu is published for 2026-11-20; the feed covers 2026-11-02 to 2026-11-15."

## 9. Registry config needed (not applied: `restaurants.py` is out of scope for this change)

- `src/ravintola_mcp/restaurants.py`, entry `unicafe-kaivopiha`: add `config={"slug": "kaivopiha"}`. Without it the adapter raises "no Unicafe slug in the registry config".
- `src/ravintola_mcp/adapters/__init__.py`: `from ravintola_mcp.adapters.unicafe import UnicafeAdapter` and add `UnicafeAdapter()` to `ADAPTERS`.

## 10. Fixtures and tests

- `tests/fixtures/unicafe/restaurants-fi.json` and `restaurants-en.json`: trimmed real responses. Kaivopiha keeps Mon 02.11, Tue 03.11 and Sun 08.11. Viikuna (second restaurant, for selection tests) keeps Mon 02.11 with two items. Restaurant objects and dish fields are unchanged.
- `tests/test_unicafe.py`: 20 offline tests (respx) and one `live` test. `uv run pytest -q tests/test_unicafe.py` and `uv run pytest -m live tests/test_unicafe.py` both pass.

## 11. Open points

- `KELA` meaning is unverified (kept as a diet code).
- Side dishes and desserts are excluded from `get_menu` results. If the macro search should include them, drop `NON_LUNCH_LINES` in `adapters/unicafe.py`.
- The feed covers about two weeks ahead. Dates beyond that return the "No menu is published" note.
- The lunch-hours string comes from the feed. It is not checked against the site's rendered page.
