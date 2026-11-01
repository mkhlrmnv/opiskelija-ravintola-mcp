# Täffä (Teknologföreningen, Otaniemi) - data source research

Status: **BLOCKED for direct inspection.** Neither `https://lunch.tf.fi` nor `https://tf.fi` could be fetched from this session (DNS resolution failed: `getaddrinfo ENOTFOUND`, i.e. the hosts are outside the session's allowed network domains). Nothing below about the lunch.tf.fi page structure was observed. Everything marked UNVERIFIED must be checked in-container once the hosts are allowed.

Action needed: add `lunch.tf.fi` and `tf.fi` to the session's allowed network domains, then re-run this research.

## 1. Observed (from search snippets only, not from fetching the site)

Sources: WebSearch results, which summarize these pages:

- Täffä Lunch moved to the A Blanc shopping centre (Otakaari 27) while its home building Urdsgjallar is renovated. Opened Tuesday 6 October (2026, by weekday match). Expected return to Urdsgjallar in autumn 2028.
  - https://www.aalto.fi/en/news/taffa-lunch-has-opened-at-shopping-centre-a-blanc
  - https://www.aalto.fi/en/news/new-restaurant-operator-to-open-at-a-blanc-after-renovation-taffa-lunch-moving-into-the-centre
- Restaurant has 150+ seats, operated by Teknologföreningen (TF).
- Menu includes the signature Wednesday spaghetti (per snippet: "familiar, iconic Täffä spaghetti"), a Thursday burger and a Friday salmon dish. Vegetarian options are being expanded. The café side has wraps, sandwiches and overnight oats.
- Aalto's campus restaurant pages say hours, prices and daily menus are on each restaurant's own site, and point to kanttiinit.fi for Otaniemi daily menus.
  - https://www.aalto.fi/en/campus/campus-restaurants-and-cafes
- Kanttiinit "Folio" aggregator pages exist with URL pattern `https://folio.kanttiinit.fi/en/area/1/YYYY-MM-DD` (area 1 appears to be "A Bloc"). Search snippets show a Täffä entry on an older page (2025-03-27). Only the URLs and titles were seen, the page content was not fetched.
  - https://folio.kanttiinit.fi/en/area/1/2025-03-27
- No Täffä-specific hits were found for Jamix, Aromi, Mealdoo or any nutrition data. Search for macros returned only Sodexo and US school results, which are not relevant.

## 2. Answers to the six questions

1. **Menu delivery mechanism: UNVERIFIED.** The lunch.tf.fi page could not be fetched. Whether it is server-rendered HTML, a JSON endpoint, an iframe to a third-party system, or RSS is unknown. Candidate leads only: (a) Kanttiinit Folio, which is observed to carry Täffä data as a third-party aggregator; (b) a possible iframe/third-party menu system on lunch.tf.fi. Neither is confirmed.
2. **Date selection: UNVERIFIED.** Kanttiinit's observed URL pattern is date-based (`/en/area/1/YYYY-MM-DD`), but whether Täffä is served there with reliable per-date data is not verified.
3. **Structure (dish names, diet codes, prices, fi/sv/en): UNVERIFIED.** Language variants are observed on aalto.fi (`/fi/`, `/sv/`, `/en/`) and on Folio (`/en/` path). No dish-level structure was observed for Täffä.
4. **Macros/nutrition: UNVERIFIED, no evidence found.** No Täffä nutrition data appeared in any result. Do not assume kcal/macros exist. Need to check lunch.tf.fi, Kanttiinit, and any Täffä app.
5. **Plain GET vs. Playwright: UNVERIFIED.** Cannot be determined without fetching.
6. **Lunch hours: UNVERIFIED.** No hours for the A Blanc location were found in search results. Aalto's pages defer to the restaurant's own site.

## 3. Sample of what was actually observed

Only search-result titles and URLs were observed. No HTML or JSON from lunch.tf.fi or tf.fi was received, so no raw sample is included.

```
https://folio.kanttiinit.fi/en/area/1/2025-03-27
  title: "Today Tomorrow Th 27/3/2025 • Finnish EnglishA Bloc"
```

## 4. Suggested parsing approach (provisional)

Do not implement until the in-container check is done.

- If lunch.tf.fi is server-rendered HTML: plain HTTP GET, parse with a DOM parser, select by the markup actually seen. Do not guess selectors now.
- If it calls a JSON endpoint: use the exact URL and field names observed in the page's network calls. Nothing should be inferred.
- If it is an iframe to Jamix/Aromi/Mealdoo/Kanttiinit or similar: fetch the iframe `src` directly over plain GET, if the vendor serves it that way.
- If JS rendering is required: Playwright as last resort, per the brief.
- Kanttiinit Folio as a fallback source is plausible but unverified, including its terms of use and whether it has a stable machine-readable API.

## 5. Gotchas

- The restaurant moved to A Blanc, so any hard-coded address or hours from Urdsgjallar-era sources is out of date.
- Aalto pages and Folio snippets may be stale. The most recent Folio Täffä entry seen was 2025-03-27 (a 2025 A Bloc page). Current-week data needs live confirmation.
- Date in the search summary says "opened on Tuesday 6 October". Year was inferred as 2026 from the weekday match, not stated directly in the text.
- Today is 2026-11-01 per the session date. Any menu data found must be for this week, not the snippet dates.

## 6. Unverified / needs in-container check

- [ ] Allow `lunch.tf.fi` and `tf.fi` in session network settings, then re-fetch both.
- [ ] Identify the menu delivery mechanism (HTML / JSON / iframe / RSS).
- [ ] Capture exact URLs for the menu, including any date parameter.
- [ ] Confirm whether a specific past or future date can be requested, or only the current week.
- [ ] Record dish name, diet code, price and language fields from the real markup.
- [ ] Check for any nutrition/macro fields. Expected to be absent, but unverified.
- [ ] Confirm lunch hours at the A Blanc location.
- [ ] Check Kanttiinit Folio for Täffä coverage and its terms before using it as a source.
- [ ] Confirm which Täffä-related host (if any) is in the allowed domains for the MCP server's runtime.

## 7. Not done

- No commits. No changes to the repo beyond creating this file.
- No endpoints were invented. Every URL above was seen in a search result.
