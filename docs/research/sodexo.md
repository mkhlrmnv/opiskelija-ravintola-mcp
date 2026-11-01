# Sodexo student restaurants (Aalto Kvarkki, T-talo): data source

**Status: VERIFIED** against live `www.sodexo.fi` on 2026-11-01 (Sunday). The adapter is in
`src/ravintola_mcp/adapters/sodexo.py`, its fixtures are in `tests/fixtures/sodexo/`, and the live
test passed (`uv run pytest -m live tests/test_sodexo.py`). The earlier version of this note was
built from search results only; it is replaced by this one.

Restaurants (registry `config["restaurant_id"]`):

| Registry id | Name | Path id (`restaurant_id`) | Mashie id (`meta.restaurant_mashie_id`) | Lunch hours (site HTML) |
|---|---|---|---|---|
| `kvarkki` | Aalto Kvarkki | `86` | `211` | Mon-Fri 09:00-15:00, lunch 10:30-15:00 |
| `t-talo` | Tietotekniikan talo (T-talo) | `6754` | `213` | Mon-Fri 09:00-18:00, lunch 10:30-18:00 |

The path id `86` is confirmed as Kvarkki by `meta.ref_title`. The earlier `3305493` lead from search
results is not used. Registry `url` values resolve (HTTP 200):
`https://www.sodexo.fi/ravintolat/espoo/aalto-kvarkki` and `.../espoo/aalto-tietotekniikantalo`.
The canonical pages in `meta.ref_url` are `.../ravintolat/ravintola-aalto-kvarkki` and
`.../ravintola-aalto-tietotekniikantalo`.

Legend: **OBSERVED** = seen in a response body or page HTML; **INFERRED** = my conclusion from
OBSERVED data.

---

## 1. Endpoints

OBSERVED (all return `200 application/json` unless noted):

- `GET https://www.sodexo.fi/ruokalistat/output/daily_json/{id}/{YYYY-MM-DD}`: one day. **Used by the adapter.**
- `GET https://www.sodexo.fi/en/ruokalistat/output/daily_json/{id}/{YYYY-MM-DD}`: same payload
  (byte-identical `courses`; only `meta.ref_url` differs). The adapter uses this for `lang="en"`.
- `GET .../ruokalistat/output/weekly_json/{id}`: the current Mon-Fri week only (`timeperiod`
  "26.10. - 1.11."), with `mealdates` keyed by Finnish or English weekday names. Not used.
- `GET .../weekly_json/{id}/{date}`: `404` (HTML). Dates are not accepted here.

Date handling (OBSERVED): any date works in `daily_json`. Past days (2026-10-26 to 10-30) and
future published days (2026-11-02 to 11-06) return data. Days with nothing published return
`200` with `"courses": []`. For example, 2026-11-01 (Sunday), 2026-11-09 and 2026-11-16
(next week, not yet published) all returned that. 2026-01-05 also returned an empty list, so
history is not guaranteed.

## 2. Response shape (`daily_json`)

```jsonc
{
  "meta": { "generated_timestamp": 1793552256, "ref_url": "...", "ref_title": "Ravintola Aalto Kvarkki ",
            "restaurant_mashie_id": "211" },
  "courses": {                      // object keyed "1", "2", ...; or [] when closed
    "1": {
      "title_fi": "Soija-juures burgundia ja täysjyväkauraa",
      "title_en": "Soy and root vegetable Bourguignon with whole-grain oats",
      "category": "Kasvislounas",   // menu line, e.g. "Lounas Uni 1", "Lounaspatonki", "Popular"
      "meal_category": null,
      "dietcodes": "G, M",          // course-level diet codes, as published
      "properties": "G, M",
      "additionalDietInfo": {
        "allergens_fi": "Kaura, Rikkidioksidi ja sulfiitit, ...",   // course-level, lists sauces too
        "allergens_en": "Oat, Sulfur dioxide and sulfits, ...",
        "allergens": "...", "dietcodeImages": ["...svg", ...]
      },
      "price": "3,10 € / 7,35 € / 9,90 €",
      "recipes": {                  // one entry per component
        "0": { "name": "Soija-juures burgundia", "ingredients": "...", "dietcodes": "G, M",
               "allergens_fi": "...", "allergens_en": "...",
               "nutrients": "Energia kj/Energia kj: 265.63 kj | Rasva/Rasva: 2.51 rasva | ..." },
        "1": { "name": "Täysjyväkauraa", "nutrients": "..." }
      }
    }
  }
}
```

Some courses have `meat_origin_fi`/`meat_origin_en` (5 of 97 in the sample). The adapter ignores them.
`recipes` can be absent or empty (14 of 97 courses, e.g. the "Popular" Subway breads).

## 3. Language

- `title_en` is present and non-empty for all 97 sampled courses. The `/en/` payload differs from
  the root one only in `meta.ref_url` and the weekday names of `weekly_json`.
- The adapter falls back to `title_fi` per dish when `title_en` is empty, and adds a menu note
  (`English names are missing for N dish(es)...`, or `...not published for this menu...`).
  The fallback path is covered by tests with a modified fixture; it was never observed in live data.

## 4. Macros (the priority)

**Source:** `recipes[k].nutrients`, one string, fields separated by ` | `:
`Energia kj/Energia kj: 420.65 kj | Rasva/Rasva: 4.41 rasva | Rasva, tyydyttyneet/...: 1.95 rasva-ty | Hiilihydraatit/...: 11.28 hiilihyd | Proteiini/...: 2.69 proteiin | Suola/...: 0.80 suola | Ravintokuitu/...: 2.80 kuitu | Rauta/...: 0.00 rauta | C-vitamiini/...: 0.00 c-vit`

The label is bilingual-ish and repeated. Parsing therefore keys on the **unit token**, the last
word before the separator. Observed vocabulary (176 recipes in daily data, all with the same nine
fields):

| Unit token | Nutrient | Maps to | Unit |
|---|---|---|---|
| `kj` | Energia | `energy_kj` | kJ |
| `rasva` | Rasva (fat) | `fat_g` | g |
| `rasva-ty` | Rasva, tyydyttyneet | `saturated_fat_g` | g |
| `hiilihyd` | Hiilihydraatit | `carbohydrates_g` | g |
| `proteiin` | Proteiini | `protein_g` | g |
| `suola` | Suola (salt) | `salt_g` | g |
| `kuitu` | Ravintokuitu | `fibre_g` | g |
| `rauta` | Rauta (iron) | not mapped | mg (INFERRED) |
| `c-vit` | C-vitamiini | not mapped | mg (INFERRED) |

Not published: **energy in kcal** (only kJ; `energy_kcal` stays `None`, and the service derives
kcal from kJ), **sugars**, and **portion weight** (`portion_g` stays `None`).

**Basis: per 100 g.** OBSERVED in the HTML of both restaurant pages: the nutrition table is headed
`Ravintoarvotiedot / 100 g`. The adapter sets `Macros.basis = "100g"`. Values are consistent with
per-100 g, for example cooked rice at 477 kJ, 24.6 g carbs and 2.5 g protein.

**Decimal format:** dots in the feed (`420.65`). Prices use commas (`3,10 €`). The parser
accepts both (`parse_number`). No comma-decimal nutrient values were observed.

**Atwater check:** kcal from `4·protein + 4·carbs + 9·fat` divided by `kJ/4.184`, over 83 first
recipes: median 0.98, range 0.85-1.52. The published values are internally consistent.

**Multi-component dishes (important).** 57 of 97 courses have 2 or more recipes, and each
component has its own per-100 g values. The adapter sets `macros` only when a course has exactly
one recipe with nutrients. Reasons:
- A course's total macros cannot be computed from per-100 g values without component weights.
- The component order is not reliable: "Vegan burger, French fries" lists the fries as recipe 0,
  and "Cheeseburger, French fries" lists the burger first. Taking recipe 0 would give wrong numbers.
- Matching recipe names to the Finnish title was tried; it gave ties in most multi-component cases.

For multi-component courses `description` lists the component names, and the menu gets a note.
**Coverage is therefore low: about 26 of 97 dishes (27%) in the sample have macros.**
The real fix is a shared-model change (see section 9).

## 5. Diets, allergens, prices, categories

- `dietcodes` is a comma-separated list, as published: `G` (gluten-free), `L` (lactose-free),
  `M` (dairy-free), `VL` (low-lactose). Observed set: `G, L, M, VL`. No `VEG` code was observed in
  the feed; vegan dishes are identified by category ("Vegaani lounas").
- Allergens: the course-level `additionalDietInfo.allergens_{fi|en}` is used first. It is the
  "Aterian sisältämät allergeenit" list and includes sauces and toppings that recipes omit. In
  the fixture days, where both lists exist, the course list was a superset of the recipe union in
  14 of 15 courses and equal in the other one. If that is
  missing, the adapter takes the union of recipe `allergens_{lang}`.
- `price`: the three-column text, kept as published (for example `3,10 € / 7,35 € / 9,90 €`).
  Some courses have two columns (`3,10 € / 5,90 €`). The column labels are NOT in the HTML or
  JSON. The first column is probably the student price, but this is **UNVERIFIED**.
- `category`: the menu line (`Lounas Uni 1`, `Lounas 2 Uni`, `Lounaspatonki`, `Keittolounas`,
  `Lautasannos 1 Uni`, `Vegaani lounas`, `Kasvislounas`, `Keitto-vegaani`, `Jälkiruoka`, `Popular`).
- Course titles sometimes carry a time window or portion text, for example
  `Cheeseburger, French fries 11:00–14:00` or `(8kpl/annos)`. The name keeps this text.

## 6. Lunch hours

Not in the JSON. The restaurant HTML page shows "Viikon aukioloajat" (weekly opening hours) with
the lunch slot, for example `Lounas 10.30 - 15.00`, as in the table in section 0. The adapter
returns `lunch_hours=None` and does not scrape HTML. This is a deliberate choice, since it would be
an extra request and a fragile parse. A follow-up could parse it once per day.

## 7. Gotchas

1. **Closed or unpublished days** return `"courses": []` (a list, not an object). The adapter
   returns `dishes=[]` with a note, and no error.
2. **Next week may be unpublished.** As of 2026-11-01 (Sunday) the following Monday-Friday
   returned empty. The publishing time was not determined.
3. **Multi-component dishes** have per-component macros only (section 4).
4. **Two ids:** the path id (`86`, `6754`) is used in URLs; `restaurant_mashie_id` (`211`, `213`) is
   a separate system id. Do not use it in URLs.
5. **Not an official API.** The endpoints are undocumented and may change. Terms of use are
   **UNVERIFIED**; the site is publicly reachable and this adapter makes one cached GET per
   restaurant-day. Check the terms before relying on this widely.
6. **Free-text noise:** titles with trailing spaces, double spaces, and `&` in names. The adapter
   collapses whitespace.
7. **Access:** `www.sodexo.fi` answered from this machine through the configured HTTPS proxy.
   httpx picks the proxy up from the environment. TLS verification stays on.

## 8. Fixtures and tests

- `tests/fixtures/sodexo/kvarkki_daily_2026-11-02.json`: full Monday response, 5 courses (Finnish).
- `tests/fixtures/sodexo/kvarkki_daily_2026-11-02_en.json`: `/en/` variant of the same day.
- `tests/fixtures/sodexo/t-talo_daily_2026-11-02.json`: full Monday response for T-talo.
- `tests/fixtures/sodexo/kvarkki_daily_2026-11-01_closed.json`: closed Sunday (`"courses": []`).

These are the raw responses, not trimmed. The menu responses are about 14-20 KB each and contain no cookies or
secrets. Tests in `tests/test_sodexo.py` use respx, so they run offline. The `live` test fetches
the next published weekday for both restaurants.

## 9. Recommended shared-file changes (not made; other agents own these files)

- **`models.py`:** to expose macros for multi-component dishes, add an optional list of
  components, for example `Dish.components: list[Component]` with `name` and `macros`. This would
  raise Sodexo macro coverage from about 27% to every component of every dish, and would let callers
  see which part the values describe.
- **`restaurants.py`:** no change needed. The `kvarkki` (`86`) and `t-talo` (`6754`) entries are
  correct. The `url` values resolve.
- **`adapters/__init__.py`:** register the adapter: `ADAPTERS["sodexo"] = SodexoAdapter()`.

## 10. Open items

- [ ] Confirm which price column is the student price (not labelled in the feed or the HTML).
- [ ] Confirm Sodexo's terms of use for automated access.
- [ ] Decide whether to parse weekly lunch hours from the restaurant page (section 6).
- [ ] Watch for a `kcal` or `sugar` nutrient appearing in the feed; neither has been observed.

## Sources

- https://www.sodexo.fi/ruokalistat/output/daily_json/86/2026-11-02 (fetched 2026-11-01)
- https://www.sodexo.fi/en/ruokalistat/output/daily_json/86/2026-11-02
- https://www.sodexo.fi/ruokalistat/output/daily_json/6754/2026-11-02
- https://www.sodexo.fi/ruokalistat/output/weekly_json/86
- https://www.sodexo.fi/ravintolat/ravintola-aalto-kvarkki (HTML: nutrition basis, opening hours)
- https://www.sodexo.fi/ravintolat/ravintola-aalto-tietotekniikantalo (HTML: opening hours)
