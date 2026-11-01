# Sodexo Aalto Kvarkki: data source research

**Status: PARTIAL.** `www.sodexo.fi` and `flavoriadatacatalog.tt.utu.fi` both failed DNS resolution in this session (`getaddrinfo ENOTFOUND`). No Sodexo page or JSON body was fetched. Everything below comes from WebSearch result URLs and search-summarizer paraphrases. Nothing was checked against a live response. No raw JSON sample exists to trim.

Legend used below:
- **OBSERVED**: a URL string appeared in search results. I did not open its content.
- **SECONDHAND**: a claim from a search summary of content the summarizer read. Not checked by me.
- **UNVERIFIED**: not confirmed by any source I could read.

---

## 1. Endpoints

OBSERVED URL strings (search results, 2026 crawl dates):
- `https://www.sodexo.fi/ruokalistat/output/daily_json/3305493/2026-06-04`
- `https://www.sodexo.fi/en/ruokalistat/output/daily_json/3305493/2026-04-22`
- `https://www.sodexo.fi/en/ruokalistat/output/weekly_json/3305493`

Pattern (OBSERVED from URLs):
- `/ruokalistat/output/daily_json/{restaurantId}/{YYYY-MM-DD}`
- `/ruokalistat/output/weekly_json/{restaurantId}`
- A `/en/` prefix variant also exists.

Currency: UNVERIFIED. The URLs were indexed with dates from April to June 2026, which suggests they were live when crawled. No response body was read, and the endpoints are undocumented.

## 2. Kvarkki restaurant ID

**NOT FOUND.** Every search hit used ID `3305493`. SECONDHAND: the summarizer says its meta block names "Ravintolat Hilla ja Mustikka", not Kvarkki. So `3305493` is probably not Kvarkki.

SECONDHAND: a Turku catalog page cites `weekly_json` with ID `102`. UNVERIFIED and unrelated to Kvarkki.

How to find the ID once sodexo.fi is reachable (plan, not yet done):
1. Fetch `https://www.sodexo.fi/ravintolat/espoo/aalto-kvarkki` and search the HTML for `ruokalistat/output`, `restaurantId`, `restaurant_id`, or `data-` attributes.
2. Check the Espoo restaurant listing and the Kvarkki page's menu widget for the numeric ID.
3. Probe candidate IDs against `weekly_json/{id}` and compare the restaurant name in the response meta block. Do not brute-force.

## 3. Date request and language

- Date goes in the path as `YYYY-MM-DD` (OBSERVED from URLs).
- Both `/en/` and root paths exist. SECONDHAND: titles come in both `title_fi` and `title_en` fields. UNVERIFIED whether the `/en/` path changes the response language.

## 4. Response structure (all SECONDHAND / UNVERIFIED)

Reported by the summarizer:
- A `meta` block with the restaurant name, a reference URL, and `restaurant_mashie_id`. Example value for `3305493`: `FI166090`. The Mashie ID is a separate identifier from the path ID.
- A `courses` object keyed by number. Each course has `title_fi` and `title_en`.
- Some courses have a `recipes` object with a name, an `ingredients` list (sometimes empty), and its own nutrients string.
- Allergen and diet-code fields, and price data. The exact key names were not confirmed. The summarizer mentioned "allergens" and "dietcodes".

## 5. Macros

SECONDHAND: there are no separate numeric macro fields. Nutrition sits in one pipe-delimited `nutrients` string. The example as reported:

```
Energia/Energy: 574.25 kJ | Energia/Energy: 136.99 kcal | Rasva/Fat: 2.08 g | Hiilihydraatit/Carbohydrate: 23.51 g | Proteiinit/Protein: 3.92 g
```

Mapping implied by that example (UNVERIFIED):
- kcal: label `Energia/Energy`, unit `kcal`. The same label also appears in `kJ`, so parse by unit, not by label alone.
- fat: `Rasva/Fat`, grams.
- carbohydrate: `Hiilihydraatit/Carbohydrate`, grams.
- protein: `Proteiinit/Protein`, grams.
- fibre, salt, sugar, saturated fat: not in any snippet. UNVERIFIED whether they exist.
- Per portion or per 100 g: UNVERIFIED. The example values look like a portion, but I cannot confirm this.
- Recipe-level nutrients: SECONDHAND, they exist.

Sanity check on the example: Atwater factors (4/4/9 kcal per g of protein/carbs/fat) give 4×3.92 + 4×23.51 + 9×2.08 ≈ 128 kcal, against 136.99 kcal stated. Plausible given rounding and method differences. Useful as a validation rule with a tolerance.

## 6. Lunch hours

SECONDHAND only, likely stale: Mon–Fri 08:00–15:00, lunch 10:30–14:00. The summary cited a 2017 Aalto news item and an Aalto page (`https://www.aalto.fi/fi/kampus/kampusravintolat`). That page's content was not read. UNVERIFIED.

## 7. Other Kvarkki facts (SECONDHAND)

- Operator: Sodexo Oy, Otakaari 3, Otaniemi, Espoo. A finder.fi listing is named "Sodexo Ravintola Aalto Kvarkki" (URL seen, content not read).
- Dish pages on sodexo.fi (`/en/node/{n}`) are tagged to Kvarkki. Which node IDs map to Kvarkki is UNVERIFIED, and I did not rely on any specific node.
- Example dish: "Grillattua broilerinfilettä", dated 29.4.2026, priced 11,80 €. Single-day page, not a weekly menu. UNVERIFIED.
- Student-meal period "15.6.–9.8." was cited. That is well before today (2026-11-01), so the figure is stale.

## 8. Gotchas

1. **Blocked network.** `www.sodexo.fi` and `flavoriadatacatalog.tt.utu.fi` do not resolve from this session. Both must be allowed in the session network settings before anything can be verified.
2. **Two IDs.** The path ID (`3305493`) and `restaurant_mashie_id` (`FI166090`) are different. Use the path ID for URLs.
3. **Nutrition is one string.** It must be parsed. Labels are bilingual (`Energia/Energy`). Energy appears twice, in kJ and kcal.
4. **Missing values.** Some courses have empty `ingredients` lists. Treat a missing nutrient as `null`, not `0`.
5. **Incomplete 2026 data.** SECONDHAND: a Turku catalog note says 2026 menu names and data were missing for some entries. Handle empty `title_fi` and `title_en`.
6. **No official docs.** These endpoints are undocumented and may change without notice. Terms of use: UNVERIFIED, check before shipping.
7. **Empty days.** Behaviour for weekends and holidays is UNVERIFIED. Expect empty or missing `courses`.

## 9. Provisional field mapping (UNVERIFIED)

| Target | Source (reported, unconfirmed) |
|---|---|
| restaurant name | `meta.*` (exact key UNVERIFIED) |
| dish name (fi) | `courses[n].title_fi` |
| dish name (en) | `courses[n].title_en` |
| kcal | `nutrients`, label `Energia/Energy`, unit `kcal` |
| protein g | `nutrients`, `Proteiinit/Protein` |
| carbs g | `nutrients`, `Hiilihydraatit/Carbohydrate` |
| fat g | `nutrients`, `Rasva/Fat` |
| fibre, salt, sugar, sat. fat | not seen, UNVERIFIED |
| price | key UNVERIFIED |
| diet codes, allergens | keys UNVERIFIED (`dietcodes`, `allergens` mentioned) |

## 10. Unverified / needs in-container check

- [ ] Allow `www.sodexo.fi` (and the UTU catalog host, optional) in the session network settings.
- [ ] Confirm the endpoints return JSON today: fetch `daily_json` and `weekly_json` for a known weekday with `3305493`.
- [ ] Find Kvarkki's numeric ID from the Kvarkki page HTML or by probing `weekly_json`. Check the restaurant name in the meta block.
- [ ] Save one raw response to the scratchpad and record exact key names: courses, prices, diet codes, allergens, meta.
- [ ] Confirm whether `nutrients` is present for every course, and whether values are per portion.
- [ ] Check whether fibre, salt, sugar and saturated fat appear anywhere.
- [ ] Check the `/en/` vs root path language behaviour.
- [ ] Confirm lunch hours from the current Aalto or Sodexo page.
- [ ] Check Sodexo's terms of use for automated access.
- [ ] Confirm the behaviour for empty days (weekends, holidays).

## Sources (URLs seen in search results, not opened)

- https://www.sodexo.fi/ruokalistat/output/daily_json/3305493/2026-06-04
- https://www.sodexo.fi/en/ruokalistat/output/daily_json/3305493/2026-04-22
- https://www.sodexo.fi/en/ruokalistat/output/weekly_json/3305493
- https://www.aalto.fi/en/news/sodexo-has-opened-a-restaurant-at-kvarkki-852017
- https://www.aalto.fi/fi/kampus/kampusravintolat
- https://www.finder.fi/Henkil%C3%B6st%C3%B6ravintola/Sodexo+Ravintola+Aalto+Kvarkki/Espoo/yhteystiedot/1666568
- https://flavoriadatacatalog.tt.utu.fi/docs/kitchen-menu (not reachable)
