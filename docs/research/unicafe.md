# Unicafe (Kaivopiha) data source research

Status: BLOCKED at the data source. The adapter is NOT implemented. The site that users open, menu.unicafe.fi, is a static React app. Its menu data comes only from `https://unicafe.fi/wp-json/swiss/v1/...`, and `unicafe.fi` is on the session's blocked-host list. Items below are labelled VERIFIED (seen in a response or in the shipped JS bundle in this session), INFERRED, or UNVERIFIED.

## Host allowlist needed

Add `unicafe.fi` (and `www.unicafe.fi` if redirects use it) to the session network allowlist. The adapter cannot work without it. Everything else needed is already reachable.

| Host | Result this session | Role |
|---|---|---|
| `https://menu.unicafe.fi` | 200, reachable (via proxy) | Static SPA shell only. No data API. |
| `https://unicafe.fi` | `curl` exit 000 (blocked) | **Real data source.** Required. |
| `https://messi.hyyravintolat.fi` | DNS fails over http. CONNECT returns 403 from the egress proxy (refused by policy). | Old HYY API used by `unicafe-cli`. Not usable here. |
| `https://kitchen.kanttiinit.fi` | 200, reachable | Third-party aggregator. Has Kaivopiha data (see section 5). Not the official source. |
| `https://kanttiinit.fi` | `curl` exit 000 | Not usable here. |

## 1. Where menu.unicafe.fi gets its data (VERIFIED)

- `GET https://menu.unicafe.fi/` returns a 2.7 kB HTML shell. It loads `/static/js/2.ddce8e18.chunk.js` and `/static/js/main.799fa323.chunk.js`. Title "UniCafe Menu", app name `unicafe-pwa`.
- `https://menu.unicafe.fi/api` and `https://menu.unicafe.fi/wp-json/swiss/v1/restaurants?lang=fi` both return the same HTML shell (SPA fallback, byte-identical to `/`). The site has no API of its own.
- The only data request in `main.799fa323.chunk.js` is an axios GET built by:

  ```js
  function O(e, t) {
    return "https://unicafe.fi/wp-json/swiss/v1" + "/" + e + "?lang=" + t
  }
  // in the restaurants thunk: E.a.get(O("restaurants", lang))
  ```

  So the single endpoint is **`GET https://unicafe.fi/wp-json/swiss/v1/restaurants?lang=<lang>`**. The app reads `response.data` as a list of restaurants. It has no date parameter. It fetches all restaurants and all days, and filters on the client.
- Client-side normalisation seen in the bundle:
  - Each restaurant's id is `restaurant.menuData.id` (copied to `restaurant.id`).
  - `restaurant.menuData.menus[].date` looks like `"Ma 2.11"` (Finnish abbreviation, space, day.month). It is rewritten to `"Monday 2.11"`. Accepted abbreviations: Ma/Må/Mon, Ti/Tis/Tue, Ke/Ons/Wed, To/Tors/Thu, Pe/Fre/Fri, La/Lör/Sat, Su/Sön/Sun.
  - The app skips a refetch when its cached copy is less than 5 units old (the unit is probably minutes; UNVERIFIED).
- Languages: the UI strings contain `fi`, `sv` and `en` tables, so `lang` is one of `fi`, `sv`, `en` (VERIFIED from the UI string tables; the API's own handling of `lang` is UNVERIFIED).
- Allergen and diet labels: the bundle contains a translation table (fi, sv, en) for allergens such as "sisältää gluteenia" / "may contain gluten", "selleriä" / "celery", "sinappia" / "mustard", "soijaa" / "soy", "sulfiitteja" / "sulphites", "valkosipulia" / "garlic", "äyriäisiä" / "shellfish". Diet codes and their meaning are UNVERIFIED (the app has filters for vegan, vegetarian, fish, dessert, special, lunch, sideDish).
- Nutrition: the UI has a string "Ravintoarvo 100g" / "Näringsvärde 100 g" / "Nutrition 100g". That suggests a per-100 g nutrition display, but the bundle contains no nutrition field names, so this is INFERRED only. Confirm against a real response before writing any macro mapping.

## 2. Kaivopiha identity (VERIFIED from Kanttiinit's list, not from Unicafe)

- Kanttiinit's `GET https://kitchen.kanttiinit.fi/restaurants` returns a JSON list of 48 restaurants. Kaivopiha is:
  - `id: 12`, `name: "Kaivopiha"`, `areaId: 7`, `priceCategory: "student"`, `address: "Mannerheimintie 3 B, 00100 Helsinki"`
  - `url: https://unicafe.fi/restaurants/kaivopiha/`
  - `menuUrl: https://unicafe.fi/wp-json/swiss/v1/restaurants?lang=%lang%#kaivopiha`, which confirms that Kaivopiha's menu is the `restaurants` list filtered by slug `kaivopiha`.
- The Unicafe slug or id used in the `restaurants` response is still UNVERIFIED. The `#kaivopiha` fragment and the `menuData.id` field are the likely keys. Confirm the exact value from a real response once `unicafe.fi` is reachable.
- Kanttiinit `openingHours` for Kaivopiha: `["11:00 - 19:45" x5, "11:30 - 17:00", null]`. Assuming index 0 is Monday (INFERRED), that is Mon to Fri 11:00-19:45, Sat 11:30-17:00, Sun closed. Kanttiinit data is secondary. Confirm on unicafe.fi.
- Hours from older snippets (19:00 vs 19:45) conflict. Prefer the value from the live restaurants response.

## 3. Request parameters and response shape

- Date: NOT a request parameter. Each restaurant object carries its menus, and the client picks the day. The adapter must filter by date, but the exact day key format (for example `"2.11"` after the `Ma` abbreviation is stripped, or a full ISO date) is UNVERIFIED until a real response is read.
- Lang: `?lang=fi|sv|en` (INFERRED from the app's UI language handling; a fallback to `fi` must be tested).
- Dish structure, prices, diet codes, allergen codes and macros: UNVERIFIED. No live Unicafe response was obtained.

## 4. Macros

- No nutrition field names appear anywhere in the shipped bundle. Only the "Ravintoarvo 100g" label appears (see section 1).
- Per the project rule, do not map macros until a real response shows them. If no per-dish macros exist, the adapter should return `macros=None` for all dishes.
- Do not use Sodexo nutrition values as a stand-in for Unicafe.

## 5. Kanttiinit fallback (reachable, third-party, not implemented)

`GET https://kitchen.kanttiinit.fi/menus?restaurants=12&days=2026-11-02` returned 200 (JSON, 424 bytes):

```json
{"12": {"2026-11-02": [
  {"title": "Seitan - Hoi Sin bowl", "properties": []},
  {"title": "Maggara-harissapata", "properties": ["G"]},
  {"title": "Lihamakaronilaatikko (broileri)", "properties": ["L"]}
]}}
```

- 7 dishes for Monday 2026-11-02. Each has only `title` and `properties` (diet codes G, L, M seen). No prices, no allergens, no nutrition, no description. Kanttiinit's own menu source is Unicafe, so this is a reshaped copy and may lag the official site.
- Use only with a decision from the project owner, since it is a third-party aggregator with unknown terms. It gives no macros, so it would not meet the macro goals of this adapter.

## 6. Other leads (checked)

- `unicafe-cli` 0.1.2 (npm, github.com/aapzu/unicafe-cli): uses `http://messi.hyyravintolat.fi/publicapi/restaurants` and `/publicapi/restaurant/{id}`. That host is blocked and the API looks legacy. Not usable.
- VarjoCafe: an older scraper, not compatible with the current site (from earlier search snippet, not re-checked).

## 7. Gotchas

- `menu.unicafe.fi` returns 200 for any path, including unknown API paths. Do not treat a 200 as proof of an API. Check `content-type` and the body.
- Hours and macro availability cannot be inferred from the shell or the bundle. Only the data endpoint can confirm them.

## Next steps once unicafe.fi is allowlisted

1. `curl https://unicafe.fi/wp-json/swiss/v1/restaurants?lang=fi` and save a trimmed Kaivopiha-only sample under `tests/fixtures/unicafe/`.
2. Repeat with `lang=en` and `lang=sv` to test the language fallback.
3. Record the exact key for Kaivopiha, the day key format, the dish fields, diet and allergen codes, price fields, and whether nutrition fields exist (with their unit and basis).
4. Then implement `src/ravintola_mcp/adapters/unicafe.py` and `tests/test_unicafe.py`.

Registry config (already in `restaurants.py`, unchanged in this run): `id="unicafe-kaivopiha"`, `provider="unicafe"`, `url="https://menu.unicafe.fi"`. The Unicafe slug or id should go into `config`, for example `config={"slug": "kaivopiha"}`, after verification. It is not added yet because `restaurants.py` is out of scope for this run.
