# Kipsari: data source research

Status: **VERIFIED** against live responses on 2026-11-01 (Sunday, ISO week 44). The feeds show week 45. Fixtures are in `tests/fixtures/kipsari/`. The adapter is `src/ravintola_mcp/adapters/kipsari.py`.

## Sources

| Source | Content | Notes |
|---|---|---|
| `https://www.kipsari.com/rss-vare/` | Kipsari Väre lunch, Finnish, RSS 2.0 | Primary menu source. Plain GET, no JS. |
| `https://www.kipsari.com/rss-vare-english/` | Kipsari Väre lunch, English, RSS 2.0 | Same week and structure, English text. |
| `https://www.kipsari.com/qr_menu/vare-2/` | Same Väre menu as HTML (Quick Restaurant Menu plugin) | Correct UTF-8. Alternative if the RSS breaks. |
| `https://www.kipsari.com/` | Homepage: opening hours, prices, diet legend | Not used by the adapter. |
| `https://www.kipsari.com/feed/` | WordPress news feed | No menu content. |

## Locations

- **Väre** (Otaniementie 14): menu published as above. Hours from the homepage: Mon-Fri 9:00-18:00, lunch 11:00-18:00.
- **Studio** (Otakaari 7): no menu feed. `/rss-studio/` returns 404. The homepage Studio block (including the `[studio_menu]` shortcode and its hours) is inside an HTML comment and is not rendered. `/studio/` redirects to `/qr_menu/studio-2/`, which is an empty template for week 45 with no dishes. Studio is not registered.

## Feed structure (verified)

- Channel `<description>` gives the week: `Lounas – vko 45` (fi) and `Lunch – week 45` (en).
- One `<item>` per weekday, Mon-Fri. Only the current week is present; no week or date parameter exists.
- Item `<title>`: `Ma, 02.11.2026` (fi) or `Mon, 2026-11-02` (en). The date is the only key, since there is no `pubDate` or `guid`.
- Item `<description>` (CDATA HTML) holds `<span>` lines: the hot main dish, then `Salaattilounas`/`Salad lunch` and `Leipäateria`/`Bread meal`, which are standing lines and appear every day.
- Diet codes trail the main dish in parentheses, e.g. `(*, VE, G)`. Codes seen: `VE` (vegan), `G` (gluten-free), `*` (meets nutrition recommendations, per the site legend). `L`/`M` were not seen.
- **Encoding gotcha:** some fi items are double-encoded UTF-8 (`VihreÃ¤` for `Vihreä`), while others are correct (`Leipäateria`). The adapter repairs each span with a per-line latin-1 to UTF-8 round trip.
- No allergens, prices, descriptions or nutrition in the feed.

## Language

- English feed exists and carries translated dish names. Dish ids are slugs of the displayed name, so they differ between fi and en.
- If the English feed or the requested date is missing, the adapter falls back to Finnish and adds a note.

## Prices and hours (homepage, not parsed)

- Prices, dated `1.1.2026`: lunch 7,00 €, students 3,10 €, civil service 6,00 €, buffet 10,20 €. Not in the feed, so `Dish.price` stays `None`.
- Väre hours as above. Not wired into `Menu.lunch_hours`.

## Macros

None published anywhere: not in the feeds, the HTML QR pages or the homepage. `Dish.macros` stays `None`.

## Adapter behaviour

- Config: `feed` (default `rss-vare`) and optional `feed_en` (default `<feed>-english`).
- Finnish feed 404: `AdapterError`. English feed 404: silent fallback to Finnish.
- Date with no item (weekend, holiday, outside the feed's week): empty `dishes` plus a note. No error.

## Registry (shared change, not made here)

```python
# restaurants.py: existing Kipsari entry works as is (config defaults to rss-vare).
# Optional, explicit:
Restaurant(id="kipsari", ..., provider="kipsari", url="https://www.kipsari.com",
           config={"feed": "rss-vare"})
# adapters/__init__.py:
ADAPTERS["kipsari"] = KipsariAdapter()
```

## Open questions

- Publishing schedule: the week 45 feed was live by Sunday 1 Nov. The exact weekly update time is not verified.
- Whether Studio will publish its own menu later. A new location would need its own feed slug in `config`.
