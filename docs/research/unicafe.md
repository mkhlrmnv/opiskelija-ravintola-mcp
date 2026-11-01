# Unicafe (Kaivopiha) data source research

Status: BLOCKED. Direct fetches of both target hosts failed at DNS resolution (`getaddrinfo ENOTFOUND`), which means the session's network policy does not allow them. Nothing below about endpoints, IDs, field names or macros has been observed directly. Items are labelled OBSERVED (seen in a search snippet), INFERRED, or UNVERIFIED.

## What was attempted

| Target | Method | Result |
|---|---|---|
| https://menu.unicafe.fi | WebFetch | ENOTFOUND. Host not in session's allowed network domains. |
| https://unicafe.fi/wp-json/swiss/v1/restaurants/?lang=en | WebFetch | ENOTFOUND on unicafe.fi. |
| https://unicafe.fi (main site) | not retried | Same host, same policy block. |

Per the tool guidance, further host attempts were stopped after both failed. Only WebSearch (which works) was used after that.

## 1. How menu.unicafe.fi gets its data

- UNVERIFIED. No JS bundle, API base URL or restaurant ID was observed.
- The `/wp-json/swiss/v1/restaurants/` path was not confirmed. A search for it returned nothing Unicafe-specific. Treat it as a candidate only.
- Which of the two is current: UNKNOWN. Needs an in-session check.
- Kaivopiha ID or slug: UNKNOWN. The only "UniCafe Kaivopiha" ID found was on spinach.guide (venue 107846). That is a third-party listing, not Unicafe's ID, so it must not be used.

## 2. Requesting a date and language

- UNVERIFIED. No query parameters (date, lang) were observed.
- Language values fi/en/sv are assumed from site structure (`/en/` paths exist on unicafe.fi, and a Swedish version of the studies.helsinki.fi notices exists). Not confirmed for the API.

## 3. Response structure (days, dishes, prices, diet codes, allergens)

- UNVERIFIED. No response body was seen.
- Search snippets confirm only that unicafe.fi has a "special diets and prices" page (https://unicafe.fi/en/special-diets-and-prices/). It was not fetched, so its contents are unknown.

## 4. Macros and nutrition

- No evidence found that Unicafe publishes per-dish kcal, protein, carbs, fat, fibre, salt, sugar or saturated fat. The search results found no Unicafe nutrition table.
- The nutrition tables that did appear were from Sodexo, which lists values per 100 g. That is a different chain and is not a valid source for Unicafe.
- Conclusion: macros are UNVERIFIED and may not exist at all. Plan for a fallback (for example, matching dish names to a nutrition database) until a check of the actual menu data proves otherwise.

## 5. Plain GET vs. JS rendering

- UNKNOWN. Not observed. The menu app is mentioned as a mobile app, which suggests a JSON backend, but this is INFERRED.

## 6. Opening and lunch hours (Kaivopiha)

Secondhand, conflicting, and undated. Do not rely on these.

- A unicafe.fi news item (undated in the snippet, mentions "from 23 August") gives Kaivopiha weekdays and lunch 11:00-19:00. Source: https://unicafe.fi/en/news/unicafe-serves-on-all-campuses-five-restaurants-open-from-23-aug
- A studies.helsinki.fi page says Kaivopiha serves lunch on weekdays until 19:45 and Saturdays until 17:00 (undated). The search snippet did not identify the exact page URL for this claim, so the source is UNVERIFIED.
- Myöha, a separate bar-restaurant in Kaivopiha's new wing, is listed with lunch Mon-Fri 11-14. Do not confuse it with Kaivopiha.

## Other leads (from search snippets, not opened)

- VarjoCafe (github.com/luontola/varjocafe): an older scraper of Unicafe lunch menus. Per the snippet, it is not compatible with the 2022 Unicafe website and is unmaintained. Useful for ideas, not as a current source.
- unicafe-cli npm package (v0.1.2, unpkg README): a CLI that shows Unicafe menus. Per the snippet, it supports `-r` (list restaurants), `-w` (week), `-e` (English). It is the most promising lead for the real endpoint. Its source would show the URL it calls. Not opened because the host was not allowed.
- Not relevant: TUM-Dev/eat-api (TUM canteens), Sodexo pages (different chain), dqbd/suz-lunch, grigorig/mittagv2, iugx/ru-menu.

## Gotchas

- Both target hosts are blocked from this container. Every field name, URL and ID above is unverified.
- Search snippets are secondhand and some are undated or from the 2020-2022 period, so they may be stale.
- Hours from snippets conflict (19:00 vs 19:45). Pick a source after checking the live site.
- Do not use Sodexo nutrition data as a stand-in for Unicafe.

## Unverified / needs in-container check

1. Allow `menu.unicafe.fi` and `unicafe.fi` in the session network settings (or run the check from a machine that can reach them).
2. Fetch `https://menu.unicafe.fi` and capture the script `src` URLs and any API base URL from the page source.
3. Open the JS bundle(s) and search for `api`, `wp-json`, `restaurants`, `lang`, `date`. Record the exact endpoint paths.
4. Call the restaurant list endpoint (current and old) and record Kaivopiha's ID or slug in each.
5. Call the daily menu endpoint for one known date in fi, en and sv. Save a trimmed raw JSON sample.
6. Check for nutrition fields. Record exact names, units (per 100 g or per portion) and whether they are null for most dishes.
7. Check whether the menu is in the first HTML (plain GET is enough) or only after JS runs.
8. Read https://unicafe.fi/en/special-diets-and-prices/ for diet codes and allergen definitions.
9. Inspect the unicafe-cli npm package source (on npm or unpkg) to confirm the endpoint it calls.
10. Confirm Kaivopiha's current weekday hours on the live site.

Recommendation: the MCP design should not assume macros exist for Unicafe until step 6 is done. Plan for a per-dish fallback.

No files were committed.
