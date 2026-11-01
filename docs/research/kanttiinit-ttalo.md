# Research: T-talo (Tietotekniikan talo, Aalto/Otaniemi) menu and macro sources

Status: PARTIAL. Kanttiinit and every Sodexo/Aalto host were unreachable from this session (DNS `ENOTFOUND`, session network allowlist). Findings below come from WebSearch snippets only. Nothing was fetched directly from a live endpoint.

## 1. Kanttiinit (restaurant id 2)

- `https://kanttiinit.fi/restaurant/2`: NOT FETCHED. `getaddrinfo ENOTFOUND kanttiinit.fi`.
- `https://kitchen.kanttiinit.fi/restaurants`: NOT FETCHED. `getaddrinfo ENOTFOUND kitchen.kanttiinit.fi`.
- Endpoint shape (`/menus?restaurants=2&days=YYYY-MM-DD`, `lang` param): UNVERIFIED, recalled from memory of the historical API. Not confirmed by any observed response.
- No search result documented a Kanttiinit API. Kanttiinit is described as a lunch-menu app for Helsinki-area student restaurants. It is unclear whether it has any nutrition data. Treat it as having none until shown otherwise.

## 2. Operator of T-talo

- WebSearch (Aalto campus restaurant listing, cited as `https://www.aalto.fi/fi/kampus/kampusravintolat`, page not fetched) says the Tietotekniikan talo restaurant at Konemiehentie 2 is run by **Sodexo**. Source: search snippet only.
- Sodexo restaurant page: `https://www.sodexo.fi/en/restaurants/restaurant-aalto-tietotekniikantalo` (listed as "Restaurant Aalto Tietotekniikantalo"). Page not fetched. Snippet shows:
  - Hours: "We are open 09.00 - 18.00. Lunchtime 10.30 - 18.00."
  - Menus in RSS and JSON (weekly and daily), plus printable versions.
  - Dish lines with three price points (3,10 EUR / 7,35 EUR / 9,90 EUR). Customer-group mapping not shown.
  - Cached menu dates were mid-October 2026, so stale relative to today (2026-11-01).
- Subway in the same building (Subway Otaniemi) is a separate operator. It is not the source of the T-talo menu.
- Conflict: Aalto building hours (search snippet) list T-talo as Konemiehentie 2A, Mon-Thu 07:45-20:00, Fri 07:45-18:00. Sodexo lists 09-18. These may refer to the building versus the restaurant. Verify in container.

## 3. Sodexo JSON endpoints (recommended source, pending verification)

Pattern observed in search results (URLs only, no response fetched):

- `https://www.sodexo.fi/ruokalistat/output/daily_json/{id}/{YYYY-MM-DD}`
- `https://www.sodexo.fi/en/ruokalistat/output/daily_json/{id}/{YYYY-MM-DD}` (English variant)
- `https://www.sodexo.fi/ruokalistat/output/weekly_json/{id}` (only one reference found, from a Turku data catalog, which says 2026 Finnish and English menu names were missing in that feed)

Examples seen in search results, IDs as they appear in URLs:
- `daily_json/109/2026-05-08` (en)
- `daily_json/3305493/2026-06-04` (fi and en)

Observed per search snippet (not fetched; from a snippet describing response content):
- `meta` block: generation timestamp, reference URL and title, `restaurant_mashie_id` (example value `FI166090`).
- `courses` object: Finnish and English titles, category, diet codes, allergens, prices, recipes.
- A nutrients field labelled "Energia/Energy" is said to exist. No numeric values were seen.
- The number in the path (109, 3305493) does NOT appear to equal `restaurant_mashie_id`. Relationship unknown.

**T-talo's Sodexo path id: NOT FOUND.** Do not guess it. Find it via the restaurant page's JSON link or by inspecting `daily_json` for a known date.

## 4. Macro availability

- Sodexo Finland restaurant pages have a "Raaka-aineet ja ravintoarvot" (ingredients and nutrition) section per dish, plus per-dish allergens. Whether this shows kcal, protein, carbs, fat, fibre, salt, sugar and saturated fat was NOT confirmed from a fetched page. The snippet mentions the section and the nutrients field, not values.
- Kanttiinit: no macro evidence found.
- Expected field mapping (UNVERIFIED until a JSON sample is seen): `courses[*].nutrients` or similar, with keys for energy (kcal/kJ), protein, carbs, fat, fibre, salt, sugar, saturates.

## 5. Language and diet properties

- Sodexo JSON: Finnish and English titles, separate fields. Diet codes in brackets in dish names, e.g. `(M,V)`, `(M,G,V)`, `(M,G,V,Pähkinätön)`. Snippet also mentions vegetarian icons.
- Likely meanings, from general knowledge and UNVERIFIED: G = gluten-free, L = lactose-free, M = dairy-free, V = vegan, Pähkinätön = nut-free. Confirm on Sodexo before relying on them.
- Allergen lists are provided in Finnish and English.

## 6. Opening hours

- Sodexo: 09:00-18:00, lunch 10:30-18:00 (snippet).
- Aalto building: Mon-Thu 07:45-20:00, Fri 07:45-18:00 (snippet). Conflicts with Sodexo above.

## Recommended source

Sodexo `daily_json` for the T-talo restaurant, with the path id found in container.

Reasons:
- It is the operator's own feed, so it is the authoritative menu.
- It is structured JSON, not HTML, which matches the preferred plain-HTTP approach.
- It has bilingual titles and allergen/diet data.
- It may carry nutrient fields, which Kanttiinit probably lacks.

Kanttiinit remains a fallback for menu structure if its API is verified.

## Gotchas

- Sodexo feeds can lag or be empty. One snippet mentions "No mealdata found for this date" on some days. Handle empty `courses`.
- Menu changes and label changes are possible, per Sodexo's own notice.
- Feed dates in search snippets are old (Oct 2026 for the restaurant page; Apr-Aug 2026 for daily_json examples). Do not treat any snippet data as current.
- Do not scrape `kanttiinit.fi`. If it is used, check its terms.
- Do not hardcode IDs from URL examples. The path id for T-talo is unknown.

## Unverified / needs in-container check

1. Allow `www.sodexo.fi` (and `sodexo.fi`) and `kanttiinit.fi` / `kitchen.kanttiinit.fi` in the session network settings, then re-fetch.
2. Get the Sodexo path id for Restaurant Aalto Tietotekniikantalo. Check the restaurant page's JSON links or the RSS link.
3. Fetch one real `daily_json/{id}/{date}` response. Record the exact top-level keys, the `courses` item shape, and the nutrient field names and units.
4. Confirm whether kcal and macros are present for T-talo dishes, or only some dishes.
5. Confirm the diet code legend (G, L, M, V, Pähkinätön, etc.) from Sodexo's own page.
6. Confirm opening hours: Sodexo 09-18 versus Aalto building 07:45-20:00.
7. Confirm Kanttiinit's current endpoints and restaurant id 2, if Kanttiinit is kept as a fallback.
8. Check whether `weekly_json/{id}` returns usable data, since the Turku catalog reports missing names for 2026.
9. Check Sodexo's terms of use for the JSON endpoints.
