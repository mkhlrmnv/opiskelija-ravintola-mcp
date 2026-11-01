# Compass Group / Food & Co (Espoo, Aalto): verified menu and macro sources

Status: verified live on 2026-11-01 (Sunday) from this machine, through the outbound proxy.
Adapter: `src/ravintola_mcp/adapters/compass.py`. Fixtures: `tests/fixtures/compass/`.
All facts below were observed with plain GET requests unless marked otherwise.

## 1. Summary

- **Macros are published.** Each meal links to a recipe, and each recipe has nutrition values
  per 100 g (kcal, kJ, protein, carbohydrates, sugars, fat, saturated fat, fibre, salt).
  No portion weight is published.
- A single day's menu is one call: `/menuapi/day-menus`. No week endpoint is needed.
- Lunch hours exist only as free text in a directory endpoint, which needs a content id.
- The Kanttiinit `feed/json` endpoint is unreliable for a given date (see section 3).

## 2. Endpoints

Base: `https://www.compass-group.fi`. Every endpoint below answered 200 for the ids given, except where noted.

| Endpoint | Parameters | Result | Used |
|---|---|---|---|
| `/menuapi/day-menus` | `costCenter=<id>`, `language=fi\|en`, `date=YYYY-MM-DD` (an ISO datetime also works) | One day: `{dayOfWeek, date, menuPackages[], html, isManualMenu}` | yes |
| `/menuapi/recipes/<recipeId>` | `language=fi\|en` | Recipe with `nutritionalValues`; 404 for an unknown id | yes |
| `/api/restaurant-search` | `q=<name>`, `language`, `pageSize`, `page` | `{hits:[{title, contentId, url, ...}]}` | yes (only if no `content_id`) |
| `/api/restaurant-search/details` | `id=<contentId>`, `language` | `{costCenter, openingHoursHtml, ...}` | yes (hours) |
| `/menuapi/week-menus` | `costCenter`, `language`, `date` (any date in the ISO week) | `{weekNumber, menus:[day, ...]}`, Mon-Fri (A Bloc also Sat and Sun) | no |
| `/menuapi/feed/json` | `costNumber`, `language` | `{MenusForDays:[...]}` | no, see below |
| `/menuapi/diets` | `costCenter` (required) | `[]` for Alvari; 400 without `costCenter` | no, no legend |
| `/menuapi/assortments` | `costCenter` | empty body for Alvari | no |

Observed behaviour:
- `feed/json` (the Kanttiinit example) is not usable for a date. Alvari (`0190`, fi) returned
  `MenusForDays: []` for Monday 2026-11-02. Dipoli (`3101`, en) returned one day, dated
  2026-11-01, so it looks like a "current day" feed that may be stale.
- An unknown `costCenter` returns 200 with an empty day, which is identical to a closed day.
- `language=sv` returns Swedish menu text. Only `fi` and `en` are supported.
- `date` as a plain `YYYY-MM-DD` and as an ISO datetime both work.

Where the endpoints come from: the restaurant page loads `/dist/assets/main.*.js`, whose
generated client (chunk `theme-compass-group.*.js`) defines `menuapi.dayMenusList`,
`menuapi.weekMenusList`, `menuapi.recipesDetail`, and so on. The page's HTML also embeds the
current day as `window.__INITIAL_MENU__`.

## 3. Restaurant ids (cost numbers and directory content ids)

Each directory `details` response reports `costCenter`, so the content id can be checked
against the registry's cost number.

| Restaurant (registry id) | costCenter | Directory title | contentId |
|---|---|---|---|
| A Bloc (`a-bloc`) | 3087 | A Bloc | 3371 |
| TUAS (`tuas`) | 0199 | TUAS/Aalto-yliopisto | 3321 |
| Dipoli (`dipoli`) | 3101 | Dipoli ravintolat | 3684 |
| Alvari (`alvari`) | 0190 | Alvari | 3445 |

Dipoli is one cost number with several lines (see section 5), not one per line.

## 4. Day menu JSON

```
{ "dayOfWeek": "Monday", "date": "2026-11-02T00:00:00", "menuPackages": [...],
  "html": null, "isManualMenu": false }
menuPackages[]: { "sortOrder", "name", "price", "meals": [...], "bundles": [...] }
meals[]:        { "name", "recipeId", "diets": [...], "bundleId", "labels", "iconUrl",
                  "dietsManuallyEdited", "ingredients": null }
bundles[]:      { "id", "name", "displayName", "labels", "mealIds" }
```

- `menuPackages[].name` is the line or station name. It is often blank (A Bloc, Alvari, TUAS
  and Dipoli all have unnamed packages), and English names differ from Finnish ones.
- `price` is free text: `opiskelija 3,10 € / henkilökunta 7,45 € / vieras 10,00 €`.
  It is blank on soups and some packages.
- Packages with no meals are price-only items (`Jälkiruoka` 1,50 €, `Dessert` 1,60 €)
  or empty stubs (TUAS `Fresh Bufee`, a salad buffet). The adapter yields no dishes for them.
- `meals[].name` can end in `\n` and contain double spaces. The adapter squashes whitespace.
- `meals[].diets` can hold a joined string such as `"A ILM"` instead of separate codes.
- `recipeId` 0 means the meal has no recipe. Its nutrition is never published (see section 6).
- `html` and `isManualMenu` were `null` and `false` on every observed day. A manually
  entered menu has not been observed, so the adapter only adds a note when `html` is set.
- Closed day: `menuPackages: []` (verified: Alvari Sunday 2026-11-01, Dipoli Saturday
  2026-11-07, Alvari Saturday 2026-11-07).

Lines seen on the Monday 2026-11-02 week (fi names):

| Restaurant | Lines (packages with meals) |
|---|---|
| A Bloc | Vegaaninen Kasvislounas, Lounas, Wicked Rabbit Buffet 11-13.30, Chef's Kitchen, Pizzat |
| TUAS | Kasvislounas, Lounas, Erikoisannos (special dish), plus Fresh Bufee (salad buffet, no meals) |
| Dipoli | Vegaaninen kasvislounas, Lounas I, Lounas II, Grillistä Klo 11.00-14.00 (two packages), Jälkiruoka |
| Alvari | Vegaaninen soppa, Vegaaninen Kasvislounas, Lounas, Special dish (Silinteri, Alvari) |

Adapter output for Monday 2026-11-02 (fi and en alike): A Bloc 16 dishes, TUAS 10, Dipoli 12,
Alvari 9. English line names differ, for example "Vegan vegetarian lunch".

## 5. Set menus (bundles)

Dipoli sells multi-component sets. A set appears as a `bundles[]` entry whose `mealIds`
point at the component meals, and each component meal has `bundleId` set to the bundle's id.
Example: the Dipoli line `Grillistä Klo 11.00-14.00` has two bundles, `Crispy chicken (G, L, M)`
with potato salad, and `Pestorossojogurttia` with seasonal vegetables.

Decision in the adapter: each component is its own `Dish`, because nutrition is per 100 g
and sets have no portion weights. Summing component values would be meaningless. The component
gets `description = "Part of set: <bundle displayName>"`, which keeps the set context.
Standalone meals have no description.

## 6. Macros (nutrition per recipe)

- Source: `/menuapi/recipes/<recipeId>?language=fi`. The `recipeId` is on each meal.
- Shape: `{recipeId, name, ingredientsCleaned, nutritionalValues:[{name, amount, unit}],
  kgCO2ePer100g, diets, lastModified}`.
- Nutrient names and units, consistent across all recipes checked:
  `EnergyKcal` (kcal), `EnergyKj` (kJ), `Protein` (g), `Carbohydrates` (g), `Sugar` (g),
  `Fat` (g), `FatSaturated` (g), `Fiber` (g), `Salt` (g).
- **Basis: per 100 g.** The site's nutrition table is headed "per 100g". The energy values
  agree (kJ / 4.184 = kcal). `Macros.basis = "100g"`, `portion_g = None`.
- Coverage over the 123 distinct recipes on the four restaurants' fi weeks:
  122 have `nutritionalValues`. Energy, protein, carbohydrates, sugar, fat and saturated fat
  are always present. Fibre is present in 119 and salt in 116, so those two are optional.
- Dishes without macros: every one checked (A Bloc 4, TUAS 2, Dipoli 2) has `recipeId` 0,
  and Alvari has none. No dish with a real recipe lacked nutrition.
- Verified sample: "Basilikalla maustettua tomaattikeittoa" (recipe 14167) is 51 kcal, 214 kJ,
  protein 1.3 g, carbohydrates 5.7 g, sugar 3.5 g, fat 2.5 g, saturated fat 0.2 g,
  fibre 1.3 g, salt 0.6 g, all per 100 g.
- Cost: one recipe call per distinct recipe. A restaurant day has about 10-20 of them,
  fetched 8 at a time. The adapter reports lookups that fail for reasons other than 404
  in `Menu.notes`.

Diet and allergen code legend. It was read from the site's JS filter code, not from the
translated labels, which are loaded at runtime. The API has no legend endpoint.

| Code | Meaning (from the UI filter) |
|---|---|
| `*` | Heart symbol (Sydänmerkki): meets Finnish nutrition recommendations |
| `ILM` | Climate-friendly (low CO2e) |
| `G` | Gluten-free |
| `L` | Low lactose |
| `M` | Dairy-free |
| `Veg` | Vegan filter (vegan and vegetarian dishes) |
| `VS` | Contains fresh garlic |
| `A` | Contains allergens (no allergen names are published) |
| `VL` | Seen on Dipoli dishes, not in the UI legend, so the meaning is unverified |

The adapter keeps every code in `Dish.diets` except `A`, which goes to `Dish.allergens`.

## 7. Lunch hours

- Source: `/api/restaurant-search/details?id=<contentId>&language=fi` returns `openingHoursHtml`.
  It is free text, one block per outlet, and differs per restaurant. Examples:
  - Alvari: `Alvari (Y-siipi)`, `MA-PE 8.00-15.00`, `lounas 11.00-14.30`, and more outlets.
  - TUAS: `Avoinna:` / `ma-to 8.00-14.00` / `Lounas:` / `ma-pe 10.30-14.00`.
  - Dipoli: `Avoinna ma-pe klo 8.00-15.30`, `Aamiainen tarjolla klo 8.00-10.00`, `Lounas tarjolla klo 11.00-15.00`.
- The English details for Alvari have an empty `openingHoursHtml`, so `lunch_hours` is `None`.
- `lunch_hours` in the adapter is this text flattened with `"; "`. It includes opening and
  breakfast hours as well as lunch, because the site does not mark lunch hours separately.
  Treat it as free text.
- `lunchHoursToday` in the search hit is only for the current day, so it is not used.

## 8. Language

- `language=en` returns the same structure with English names and categories,
  for example "Tomato soup with basil" and "Vegan vegetarian lunch". The day and recipe calls
  both take `language`.
- Page slugs differ by language: Finnish `/ravintolat-ja-ruokalistat/foodco/...`,
  English `/en/ravintolat-ja-ruokalistat/food--co/...`. The registry uses the Finnish URLs.
- The adapter falls back to Finnish when the English day call fails (HTTP error). This has not
  been triggered by real data. A 200 response with an empty English menu is not a fallback case.

## 9. Gotchas

1. An unknown `costCenter` returns 200 with an empty day, the same as a closed day.
2. `feed/json` is stale or empty for arbitrary dates. Use `day-menus`.
3. Recipe `0` means no recipe, so no nutrition exists for that meal.
4. Macros are per 100 g. Do not compare them with per-portion values, and do not sum a set.
5. `diets` can contain a joined string (`"A ILM"`) and an `A` allergen flag.
6. Package names are often blank. Dish categories then come from nothing and are `None`.
7. Alvari has no English opening hours.
8. Recipe calls are per recipe, not per day, so a day costs one call per distinct recipe.

## 10. Recommendations for shared files (not edited here)

- `src/ravintola_mcp/adapters/__init__.py`: register the adapter with
  `from ravintola_mcp.adapters.compass import CompassAdapter` and `ADAPTERS["compass"] = CompassAdapter()`.
- `restaurants.py` (optional): add `content_id` to each Compass restaurant's `config`
  (A Bloc `3371`, TUAS `3321`, Dipoli `3684`, Alvari `3445`). The adapter then skips the
  name search, which is one request per menu fetch. The adapter already reads `content_id`
  when it is present.
- No model changes are needed. `Macros` covers every published field, and `Dish.allergens`
  holds the `A` flag.
