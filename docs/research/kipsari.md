# Kipsari: data source research

Status: **BLOCKED for direct inspection.** `https://www.kipsari.com` did not resolve from the research session (`getaddrinfo ENOTFOUND`). The host is most likely outside the session's allowed network domains. Nothing below about the site's HTML, JSON, menu delivery, or macros has been observed directly. Everything is either search-snippet evidence (secondary, summarised by a search model) or marked UNVERIFIED.

## What was observed

| Item | Status | Source |
|---|---|---|
| `www.kipsari.com` fetch | FAILED, DNS does not resolve | WebFetch error |
| Kipsari has two Otaniemi-area locations: Studio Kipsari (Otakaari 7) and Kipsari Väre (Otaniementie 14) | Search snippets, consistent across sources | aalto.fi, visitespoo.fi, studios.aalto.fi |
| Studio Kipsari serves soup & salad lunch for students and staff, vegan/vegetarian leaning, plus café items | Search snippet from aalto.fi | https://aalto.fi/en/locations/studio-kipsari |
| Menu is pointed to Facebook (Studio Kipsari page) and to kipsari.com | Search snippet from Aalto Studios | https://studios.aalto.fi/studio-kipsari/ |
| Hours: Studio Kipsari lunch 8:30-14:30 (Mon-Fri); Väre 9:00-18:00, lunch until closing (Mon-Fri); Väre Sunday closed | Search snippet, Visit Espoo and Spinach Guide. Conflicts with older Aalto campus list (summer closures) | https://visitespoo.fi/node/1180, https://spinach.guide/venues/kipsari-vare-96485/ |
| Summer student-price meal period for Väre (15.6.-16.8.) | Search snippet, seasonal, date-dependent | https://www.aalto.fi/fi/kampus/kampusravintolat |
| A Helsinki listing places Kipsari on Hämeentie (flagship) | Search snippet, conflicts with the Otaniemi location list; may be a different business or outdated | https://www.citylikeyou.com/helsinki/people/pekka-kuivamaki/places/kipsari |

## Answers to the six questions

1. **How the lunch menu is delivered.** UNVERIFIED. Aalto's own pages say the weekly menu lives on Facebook and on kipsari.com. No JSON or API endpoint was observed. Candidates to check in-container: plain server-rendered HTML, a Wix/Squarespace/WordPress page, or a menu PDF or image. Do not assume any of these.
2. **Date selection.** UNVERIFIED. Snippets say "weekly menu", which suggests only the current week is shown. Confirm once the site is reachable.
3. **Structure (dish names, diet codes, prices, fi/en).** UNVERIFIED. Snippets describe soup, salad and bread, vegan and vegetarian options and café items. No price or diet-code format was observed.
4. **Macros/nutrition.** UNVERIFIED, and likely absent. No snippet mentions kcal, protein or any nutrition data for Kipsari. Assume none until proven otherwise.
5. **Plain GET vs. Playwright.** UNVERIFIED. Cannot tell without the page. Try a plain GET first once the host is allowed.
6. **Lunch hours.** Snippet-level only, from Visit Espoo and Spinach Guide: Studio Kipsari 8:30-14:30 Mon-Fri; Väre 9:00-18:00 Mon-Fri, Sunday closed. Conflicting and possibly stale sources. Verify on the official site.

## Leads (not verified)

- `https://studios.aalto.fi/sv/wp-json/wp/v2/posts/1395` and `https://studios.aalto.fi/fi/wp-json/wp/v2/posts/1395` appeared in search results. They suggest the Aalto Studios site is WordPress with a REST API. This is a **different site** from kipsari.com, and I did not fetch it. Only useful as a fallback for hours or menu text if kipsari.com stays unreachable. Whether that site has the weekly menu is UNVERIFIED.
- `https://onecampus.aalto.fi/kipsari-a-student-restaurant/index.html` appeared in search results. Not fetched. May describe the restaurant rather than the menu.

## Sample data

None. No HTML or JSON was retrieved from kipsari.com, so no trimmed sample can be given without inventing one.

## Suggested parsing approach

Not final. Decide after the page is inspected:
- If the menu is in HTML, parse the lunch block by stable container class or heading, and store each dish as `{name, diet_codes, price}`.
- If the menu is a PDF or image, treat it as a separate pipeline with OCR and flag it as higher risk.
- If the menu comes from a JSON endpoint, record the exact URL, method, headers and response shape in a follow-up doc.
- Macros: plan for "unavailable" unless the site or a partner publishes them.

## Gotchas

- Hours differ across Visit Espoo, Spinach Guide and the Aalto campus list. Do not hard-code any of them.
- Two Kipsari locations exist, plus a Helsinki listing. Make sure the scraper targets the correct one.
- The Facebook page is the stated menu source. Scraping Facebook is out of scope and likely blocked.
- Summer schedule and closures change the expected output. Handle empty days without error.

## Unverified / needs in-container check

1. Whitelist `www.kipsari.com` in the session's network settings (or confirm it resolves from the in-container environment). Then repeat the fetch.
2. Capture the raw HTML of the home page and any lunch or menu sub-page. Note every script `src`, iframe `src` and XHR/fetch URL.
3. Check whether the menu appears in the server-rendered HTML or only after JS runs. If only after JS, note which request supplies the data.
4. Find the date mechanism: is there a date parameter, a week selector, or only the current week?
5. Confirm dish, diet-code and price formats, and whether fi/en versions exist.
6. Check for any nutrition data (kcal, macros). Expect none.
7. Confirm lunch hours for each location from the official site and note any summer schedule.
8. Confirm which location(s) belong in scope.

## Summary of confidence

- High confidence that Kipsari has two Otaniemi-area locations and that the weekly menu is pointed to Facebook and kipsari.com.
- Medium-low confidence on hours, which come from third-party snippets and conflict.
- No confidence yet on delivery mechanism, date handling, dish structure, or macros. All UNVERIFIED.
