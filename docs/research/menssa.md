# Menssa (Otaniemi) data-source research

Status: **VERIFIED** against the live site on 2026-11-02 (Monday), via the proxy with plain HTTPS
GET. The earlier 2026-11-01 attempt (DNS failure in the research session) is superseded.

## 1. Operator and address

- Footer on every page: "Copyright 2026 Menssa Lounasravintola".
- Address on `/yhteystiedot/`: Otakaari 7 B, 02150 Espoo (Otaniemi).
- Site stack: WordPress with the DT The7 theme. Lunch content comes from a site plugin
  (`lms`, REST namespace `lms/v1`). No third-party menu system (Jamix, Aromi, Mealdoo, Fazer,
  Sodexo, Compass) appears in scripts, iframes or links.

## 2. How the menu is delivered

- `https://menssa.fi/lounas/` is **server-rendered HTML**. A plain GET returns the full week
  (about 84 KB, mostly CSS and JS). No JavaScript is needed. Adapter: `adapters/menssa.py`.
- Markup used by the adapter (plugin classes, all present on the page):
  - `section` per weekday: `h3` with the Finnish weekday name ("Maanantai"), a date line
    `d.m.` without a year ("2.11.").
  - Per dish: `.lms-front-dish-name` (Finnish), `.lms-front-en-name` (English),
    `.lms-front-allergens` and `.lms-front-dietary` (codes), `.lms-front-price` (always empty).
  - Pizza table: `.lms-pizza-row` with `.lms-pizza-name`, `.lms-pizza-desc`, and two
    `.lms-pizza-price` columns (student, normal).
  - Prices: `.lms-site-price-card` (`h4` title, rows labelled "Opiskelijat / Students").
- The WordPress page `/wp-json/wp/v2/pages/1100` (slug `lounas`) has **empty content**: the
  menu is not stored in the post body, so the page REST endpoint is useless for menus.
- `GET /wp-json/lms/v1/lunch/today` returns JSON for the day (`name_fi`, `name_en`,
  `allergens`, `dietary`, `price`, `display` prices, `footer`). It **ignores any date parameter**
  (`?date=2026-11-04` and `?day=` still return Monday 2 Nov). It holds no nutrition. Verified
  identical to the HTML for Monday (fixture `lms-lunch-today-2026-11-02.json`). Not used by the
  adapter because it cannot serve other days. `/wp-json/lms/v1/lunch/week` is 404.
- `/wp-json/menssa-tv/v1/lunch` returns the same data for a TV display (same limitation).

## 3. Dates and weeks

- The page lists **one Monday-Friday week**, the current one (on 2026-11-02: 2.11.-6.11.).
  There is no date parameter and no week selector. Week title "Week 4" appears only in the JSON.
- Days outside the shown week (for example Sunday 2026-11-08, or Monday 2026-11-09 before it is
  published) produce no section, so the adapter returns empty dishes and a note. The adapter
  matches the date line `d.m.` against the requested day and uses the requested year.
- Opening hours are Monday-Saturday 11:00-19:00, Sunday by agreement (from `/yhteystiedot/`).
  These are restaurant hours, not lunch hours, so `lunch_hours` stays None.

## 4. Language

- English is on the **same page**: every daily dish has a `.lms-front-en-name`. Monday's six
  dishes all have English names.
- There is no English URL: `/en/` (404), `/en/lounas/` (301 to `/lounas/`), `/lounas/?lang=en`
  (same Finnish page, query ignored). The `<html>` tag is `lang="fi"`.
- Pizza names and descriptions are Finnish only (for example "jauhelihakastike"). Pizza names
  are language-neutral, so no fallback note is raised for them.

## 5. Diet codes and allergens

Legend on `https://menssa.fi/menu/` (not on `/lounas/`):

- Diets: G = gluten-free, L = lactose-free, M = milk-free, VL = low lactose.
- Allergen markers: K (egg), KA (fish), PA (sweet pepper), PÄ (nuts), SE (celery), SI (mustard),
  SM (sesame), SO (soya), VS (garlic).
- Published on the lunch list: "G" (16 dishes), "L, G" (6 dishes), "L" (1), and the `dietary`
  span "vegan, S" (12 dishes). "S" is **not** in the legend, so its meaning is unknown. The adapter
  keeps it as published in `diets`.
- The adapter puts codes from the allergen list into `allergens` and every other code into `diets`.
  No allergen-marker code is published on the lunch list today.
- "KAIKKI RUOKAMME OVAT LAKTOOSITTOMIA!" ("all our food is lactose-free") appears on `/menu/`.
  This is a general claim and is not used in the data.

## 6. Prices

- Per-dish price cells are **empty**. Prices are per lunch type on `/lounas/`:
  - NORMAL LUNCH (main course, soup, salad, bread): staff 10,00 EUR, **students 5,90 EUR**,
    guests 12,00 EUR.
  - SOUP LUNCH (soup, salad, bread): staff 7,90 EUR, **students 3,20 EUR**, guests 9,40 EUR.
- Pizzas: student 5,90 EUR, normal 11,00 EUR (Fantasia 3: 6,90 / 12,00).
- The adapter puts pizza prices in `Dish.price` as "5,90 € (opiskelija) / 11,00 € (norm.)" and
  lunch-type student prices in a menu note, since the page does not say which dish is which.
- The lunch footer from the JSON ("Lounaaseen kuuluu alkusalaatti, vesi ja kahvi / tee", i.e.
  starter salad, water and coffee/tea included) is not on the HTML page. Not used.

## 7. Nutrition / macros

- **None published.** The lunch page, the pizza table, the `/menu/` page, and the JSON endpoints
  contain no kcal, protein, carbohydrate, fat, fibre, salt or sugar values. A search of the
  page for "kcal", "proteiin", "ravintoarvo", "nutri" found nothing.
- Therefore `Macros` stays None for every dish and `macros_available` is False.

## 8. Standing items

- Each published day lists the same standing items: "JASMIN RIISI" (rice), "Kasvikset"
  (vegetables), "ERIKOIS SALAATTIPÖYTÄ" (special salad table), plus the 12 pizzas from the
  `/lounas/` pizza table. The adapter includes them as dishes (category "Pizza" for pizzas).

## 9. Live result, 2026-11-02 (Monday)

- Lunch dishes: 6 (Herkkusieni keitto, Mexican kanaa, Soya Bolognese, JASMIN RIISI,
  Kasvikset, ERIKOIS SALAATTIPÖYTÄ). Pizzas: 12. Total: 18 dishes.
- Macros published: no. Notes: student-price note only.

## 10. Fixtures

- `tests/fixtures/menssa/lounas-2026-11-02.html`: the lunch wrapper, the price block and the
  pizza table from `/lounas/`, unchanged, with the rest of the page removed (about 14 KB).
- `tests/fixtures/menssa/lms-lunch-today-2026-11-02.json`: the `lms/v1/lunch/today` response
  for the same day. Used to cross-check names and codes.

## 11. Gotchas

- The date line has no year; the adapter takes the requested day's year.
- A weekday heading without a date line never matches (fails closed to an empty menu).
- If the lunch list is missing entirely (no weekday headings), the adapter raises `AdapterError`
  so the layout change is visible, instead of returning an empty menu.
- Diet codes are published as text and some are in the wrong span: "G" and "L" appear in
  `.lms-front-allergens`, but per the legend they are diets. The adapter sorts them by legend.
- The `/menu/` legend and the `/lounas/` data can drift; re-check the legend when a new code
  appears.

## 12. Registry and shared-file changes (not made here)

- `src/ravintola_mcp/adapters/__init__.py`: import `MenssaAdapter` from
  `ravintola_mcp.adapters.menssa` and add it to `ADAPTERS` (keyed by `provider = "menssa"`).
- `src/ravintola_mcp/restaurants.py`: the Menssa entry (`provider="menssa"`,
  `url="https://menssa.fi"`) already exists. Optionally set `url="https://menssa.fi/lounas/"` so
  the public menu page is the restaurant URL. The adapter fetches `/lounas/` regardless.
  Aliases could include "menssa lounasravintola" if wanted.
