# Täffä (Teknologföreningen, Otaniemi) - data source research

Status: **BLOCKED - menu data source is not reachable.** `https://lunch.tf.fi` is reachable through the proxy (HTTP 200), but it does not serve any menu data. The upstream menu feed is `https://newapi.tf.fi/taffa/fi/json/week/`, which is on the network block list. No adapter was implemented (gate failed, see section 4).

Verified 2026-11-01 (Sunday, restaurant closed; no weekday menu was available to check).

## 1. Verified findings

### lunch.tf.fi (reachable)

- `GET https://lunch.tf.fi` returns a 743-byte React SPA shell: `<title>Täffä lunch</title>`, an empty `<div id="root">`, `/static/js/main.600004f5.js` and `/static/css/main.6349c2e6.css`. No menu markup is in the HTML. The only other external host is `fonts.googleapis.com` (Material Icons).
- The JS bundle (CRA build, `lunch-client`) has one backend base, the relative `api/`, so requests go to `https://lunch.tf.fi/api/`. The bundle references no host other than lunch.tf.fi and third-party libraries. Nothing refers to newapi.tf.fi.
- Menu calls in the bundle:
  - `GET api/menu/today/{lang}` (default view)
  - `GET api/menu/week/{lang}` (the Today/Week toggle)
  - `{lang}` is the i18n language code. Other endpoints in the bundle: `hours/{lang}`, `prices/{lang}`, `posts/{lang}`, `announcements/{lang}`, `messages/{lang}`.

Probes (plain HTTPS through the proxy; TLS verification never disabled):

| URL | Result |
|---|---|
| `/api/menu/today/fi`, `/en`, `/sv` | 200 `text/html`, 743 bytes = SPA shell |
| `/api/menu/week/fi`, `/en`, `/sv` | 200 SPA shell |
| `/api/menu/fi/today`, `/api/menu/today`, `/api/menu`, `/api/menu/today/fi/`, `/api/menu/today/fi?date=2026-11-02`, `/api/menu/today/fi-FI` | 200 SPA shell |
| `/api/prices/fi`, `/en`, `/sv` | 200 `application/json`, body `[]` |
| `/api/posts/fi`, `/en` | 200 `application/json`, body `[]` |
| `/api/hours/fi`, `/en`, `/sv` | 200, empty body |
| `/api/announcements/fi`, `/api/messages/fi` | 200, empty body |
| `/api/hours`, `/api/prices`, `/api/week`, `/api/today`, `/api/lunch`, `/api/nonexistent` | 200 SPA shell |

- Server is Express (`x-powered-by: Express`). Unknown routes fall back to the static `index.html`. The reachable API looks like a generic `/api/<key>/<lang>` store (prices, posts, hours, announcements, messages). No menu route of any shape is served. Sending `Accept: application/json` does not change the result.
- Conclusion: lunch.tf.fi serves no menu data itself. Its menu must come from a server-side upstream that is not visible from here.

### Upstream feed (blocked)

- `https://kitchen.kanttiinit.fi/restaurants` (JSON, reachable) lists Täffä as id 3, `areaId` 7, `priceCategory: "student"`, address `Otakaari 27, 02150 Espoo`, with opening hours and `menuUrl: "https://newapi.tf.fi/taffa/fi/json/week/"`. This confirms newapi.tf.fi as the Täffä menu feed. Fetching it is blocked here. Its structure, date handling and language support are UNVERIFIED.
- The address is the A Blanc location (Otakaari 27), which matches the temporary move from Urdsgjallar.

## 2. Answers to the six questions

1. **Delivery mechanism:** Client-rendered SPA. The menu is not in the HTML and lunch.tf.fi does not serve it. The upstream is the JSON feed on newapi.tf.fi (per Kanttiinit's config). Blocked.
2. **Date selection:** The client only uses `today` and `week`, with no date parameter. Whether the newapi feed accepts a date is UNVERIFIED. Kanttiinit's `menuUrl` uses `/week/` with no date.
3. **Structure and fi/sv/en:** UNVERIFIED. No menu response was obtained in any language.
4. **Macros/nutrition:** No nutrition fields in any reachable response. Upstream UNVERIFIED. Do not assume macros exist.
5. **Plain GET vs. JS rendering:** The page needs JS, but the data is a plain JSON feed that Kanttiinit fetches directly, so a plain httpx GET should be enough once the feed is reachable. UNVERIFIED.
6. **Lunch hours:** Kanttiinit's list carries opening hours for Täffä. lunch.tf.fi `hours/fi` is empty. Exact values UNVERIFIED for A Blanc.

## 3. Samples

No fixtures were saved (`tests/fixtures/taffa/` was not created). The only real responses are the lunch.tf.fi SPA shell and the empty/`[]` API bodies listed above.

## 4. Action needed

- **Allowlist `newapi.tf.fi`** for the MCP runtime, specifically `GET https://newapi.tf.fi/taffa/fi/json/week/`. This is the blocker. `tf.fi` is not needed for this adapter.
- Optional alternative (not implemented, needs a decision on whether a third-party aggregator is acceptable): Kanttiinit (`kitchen.kanttiinit.fi`) is reachable, but I did not identify or verify a Täffä menu endpoint on it. Its terms of use would need checking first.

## 5. Adapter plan (provisional, once newapi.tf.fi is reachable)

- Plain `httpx` GET of the week JSON. Select the requested weekday; return an empty `dishes` list with a note when the day is missing (closed).
- Verify the fi/sv/en behaviour and the dish, diet and price fields from the real response before writing the parser.
- Set `Dish.macros` only if the feed actually publishes nutrition values, otherwise `None`.
- Language fallback to fi with a note if en is missing.

## 6. Checklist

- [ ] Allowlist `newapi.tf.fi` in the session/runtime network policy.
- [ ] Re-fetch `https://newapi.tf.fi/taffa/fi/json/week/` and record the JSON shape.
- [ ] Check whether a date parameter is accepted, and what the feed returns on a closed day (Sunday).
- [ ] Record dish name, diet, price and language fields.
- [ ] Check for nutrition/macro fields (expected absent).
- [ ] Confirm A Blanc lunch hours.
- [ ] Re-run the lunch.tf.fi gate (`/api/menu/today/fi`); it should be re-checked in case the site starts serving menus itself.
