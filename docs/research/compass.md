# Compass Group / Food & Co (Espoo, Aalto) menu data sources

Status: research only, nothing committed.

## 0. Access constraint (read first)

- `www.compass-group.fi` does NOT resolve from this session (`getaddrinfo ENOTFOUND`). None of the four target pages (A Bloc, TUAS, Dipoli, Alvari) could be fetched, so **nothing below is observed directly on compass-group.fi**.
- `www.aalto.fi` and `help.valota.live` also fail to resolve. Those sites would have helped with cost IDs and opening hours.
- Everything Compass-specific below is **secondhand**: read from third-party GitHub repos (code or README), or from search-engine summaries. Each item is labelled OBSERVED (in a third-party source's code/README/example) or UNVERIFIED (search summary or inference).
- To finish the job, `www.compass-group.fi` (and ideally `www.aalto.fi`) must be allowed in the session network settings. Then re-run the checks in section 9.

## 1. Endpoints seen in third-party code (OBSERVED in source, but not against compass-group.fi)

| Endpoint | Params seen | Source | Date of evidence |
|---|---|---|---|
| `https://www.compass-group.fi/menuapi/feed/json` | `costNumber=<id>&language=fi` | Kanttiinit/kitchen README debug example: `https://www.compass-group.fi/menuapi/feed/json?costNumber=0190&language=fi` (quoted in its README as `feed/json\?costNumber\=0190\&language\=fi`) | not dated |
| `https://www.compass-group.fi/menuapi/feed/rss/current-week` | `costNumber=3024&language=fi` | Vincit/lunch-assistant README (Kuopio team, "RestaurantMenuURL") | ~2023 |
| `https://www.compass-group.fi/menuapi/feed/rss/current-day` | `costNumber=0605&language=fi` | MCP README `mtpajula/tekuila-mcp` (via WebFetch of its README) | not dated |
| `https://www.compass-group.fi/menuapi/day-menus` | `costCenter=<id>&date=<Mon Jun 24 2024>&language=en\|fi` | gist `matiasraisanen/4f997855f0d6452d6016400b83f93750` (AlmaTalo lunch script, code read via WebFetch) | the gist's example date is 2024-06-24 |
| `https://www.compass-group.fi/menuapi/feed/json` (commented out) | `costNumber=<id>` | same gist, not executed | - |

Notes:
- `costNumber` (feed/json, feed/rss) and `costCenter` (day-menus) are **different parameter names for the same kind of ID**. Use whichever the endpoint wants; the examples are not consistent.
- The gist's `date` format is `Mon Jun 24 2024` (weekday, month, day, year), URL-encoded. This is OBSERVED in the gist's code. Whether the current API still accepts it in 2026 is UNVERIFIED.
- The newer `/menuapi/week-menus?costCenter=...&date=...&language=...` endpoint the brief mentions was **not found** in any source. It is UNVERIFIED and should not be used until checked.
- Search summaries also mention "JSON feeds include lunch times" (a code comment in the gist). OBSERVED as a comment only.

## 2. IDs table

Restaurant names are only known where a source says so. Aalto IDs were **NOT FOUND** in any source.

| Restaurant | Cost ID | Status |
|---|---|---|
| A Bloc (Espoo, Aalto) | - | NOT FOUND |
| TUAS (Aalto) | - | NOT FOUND |
| Dipoli (restaurants) | - | NOT FOUND (multiple lines; see section 5) |
| Alvari (Otaniemi) | - | NOT FOUND |
| AlmaTalo (Helsinki) | 3097 | OBSERVED in gist (Helsinki, not our campus) |
| Aallon Huippu (Helsinki) | 3117 | OBSERVED in gist; also `costNumber=3117` in a search-result snippet |
| Oodi (Helsinki) | 0980 | OBSERVED in gist |
| (unknown) | 0190 | OBSERVED in Kanttiinit README example, restaurant name not given |
| (unknown, Kuopio team) | 3024 | OBSERVED in Vincit README, restaurant name not given |
| (unknown) | 0605 | OBSERVED in tekuila README, restaurant name not given |

Gotcha: the four Espoo IDs are what the server needs. Get them from the page source of the four compass-group.fi pages (see section 9), or from the Aalto campus page.

## 3. Response structure (JSON, OBSERVED in gist code only)

The gist reads only these keys from the `day-menus` response (AlmaTalo / Aallon Huippu):

```
responseJSON["menuPackages"]          -> list
responseJSON["menuPackages"][i]["meals"] -> list
responseJSON["menuPackages"][i]["meals"][j]["name"] -> dish name
```

- `menuPackages[0]` = buffet, `[1]` = soup, `[2]` = chef's corner, according to the gist's own comments. This layout may be specific to those restaurants and is UNVERIFIED for A Bloc / TUAS / Dipoli / Alvari.
- The gist hardcodes the lunch time `"10:45-13:30"` and does not read any time field.
- No raw JSON sample was observed. The trimmed sample below is the **shape** the gist code implies, not a captured response:

```json
{
  "menuPackages": [
    { "meals": [ { "name": "<dish name>" } ] },
    { "meals": [ { "name": "<soup name>" } ] },
    { "meals": [ { "name": "<chef's corner dish>" } ] }
  ]
}
```

- Keys NOT observed anywhere: `SetMenus`, `days`, `price`, `diets`, `allergens`, `lunch` times, `nutrition`/`energy`/`protein`/`carbohydrate`/`fat`/`salt`/`sugar`/`fiber`. The search summary says A Bloc / Alvari pages embed JSON-LD menu blocks with diet tags and allergen codes. This is UNVERIFIED.

## 4. Diet codes

- No Compass diet-code legend was observed in any source. Codes seen in the unrelated Otaniemi data file (G, L, VL, M, VE, VS, KA, SO, PA, SE, KASVIS, from other restaurants) are NOT evidence for Compass.
- A Helsinki school-lunch Compass menu uses an asterisk for dishes that meet Finnish nutrition recommendations (search summary of `hel.fi` PDF snippet, not fetched). UNVERIFIED for our restaurants.

## 5. Dipoli and multiple lines

- Not resolved. An Aalto campus-page search summary says Dipoli is run as "Dipoli Reima" and "Metso" lines, with some student-priced meals. This is UNVERIFIED because aalto.fi did not resolve.
- No source shows how a Dipoli restaurant is split into lines in the API, or whether a line is lunch, cafe or dinner. Each Dipoli line probably needs its own cost ID. UNVERIFIED.
- Third-party aggregator `lounaat.info` has a "Lounas Food & Co Dipoli, Espoo" page (URL seen in search results, not fetched).

## 6. Macros (kcal, protein, carbs, fat, fibre, salt, sugar)

- **Not found** in any Compass endpoint in any source. None of the code samples read a nutrition field.
- The Sydänmerkki (heart symbol) partnership announced by Compass Group Finland on 13.10.2025 (press release, seen only as a search snippet) is a possible route to health flags, but says nothing about per-dish macros. UNVERIFIED.
- Possible alternative if Compass has no nutrition data: Finnish food composition database Fineli, matched by dish name. Suggestion only, NOT checked here.

## 7. Opening hours

- Not in any API source observed. The Alvari lunch hours "11.00–14.30" come from an aalto.fi search summary (UNVERIFIED, page not fetched).
- Maukas and Nova Maukas hours in the Otaniemi data file belong to other restaurants and are not relevant.

## 8. Gotchas

1. The brief's URL slug is `foodco`, but search results show the English site uses `food--co` (e.g. `https://www.compass-group.fi/en/ravintolat-ja-ruokalistat/food--co/kaupungit/espoo/alvari/`). Both are UNVERIFIED for route validity.
2. Parameter names differ: `costNumber` (feed/json, feed/rss) vs `costCenter` (day-menus).
3. `date` format on day-menus is `Mon Jun 24 2024`, not ISO. ISO support is UNVERIFIED.
4. The feeds and parsers in our sources are 2023–2024 vintage. Status in 2026 is UNVERIFIED.
5. Several sources disagree on the number of restaurants (one repo says 5 and 6 in the same README). Not Compass-specific.
6. Espoo restaurant hours and lines can change by season (search summary: Silinteri at Alvari in summer). UNVERIFIED.

## 9. Unverified / needs in-container check

Once `www.compass-group.fi` is allowed, check these in order:

1. Open each of the four pages (A Bloc, TUAS, Dipoli, Alvari) and view the page source. Look for `costNumber`, `costCenter`, `cost-center`, `data-*` attributes, script `src` or `fetch(` URLs, and any `menuapi` string.
2. Fetch `https://www.compass-group.fi/menuapi/feed/json?costNumber=<id>&language=fi` with each ID. Save the raw JSON, then record its real top-level keys, the day list, dish names, prices, diet codes and any nutrition fields.
3. Fetch `https://www.compass-group.fi/menuapi/day-menus?costCenter=<id>&date=<Mon Jun 24 2024 style>&language=fi` and compare with step 2.
4. Test `https://www.compass-group.fi/menuapi/week-menus?costCenter=<id>&date=<YYYY-MM-DD>&language=en`. It is in the brief but not in any source here. Record success or 404.
5. Check whether any response, or a JSON-LD block on the page, carries kcal or nutrient values. Record the exact key names and units (per portion or per 100 g).
6. For Dipoli, list every line the page or API shows, with its cost ID and lunch/cafe/dinner type.
7. Check `https://www.aalto.fi/en/campus/campus-restaurants-and-cafes` for opening hours and the Dipoli line structure.

## 10. Summary of confidence

- Feed URL shape `menuapi/feed/json?costNumber=<id>&language=fi`: moderate confidence, observed in third-party README/code examples, not on the live site.
- `day-menus` shape with `costCenter` and `menuPackages[].meals[].name`: moderate confidence, observed in one gist's code (2024).
- Espoo cost IDs for A Bloc / TUAS / Dipoli / Alvari: NONE found. Low.
- `week-menus` endpoint: NOT FOUND. Treat as unverified.
- Macros from Compass: NOT FOUND. No evidence the API exposes them.
