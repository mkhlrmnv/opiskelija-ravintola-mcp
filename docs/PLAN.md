# Project plan

MCP server (stdio) that returns lunch menus and per-dish macros for Finnish student
restaurants. Python, official `mcp` SDK (FastMCP), `httpx` for plain GET, Playwright only
as an optional `[browser]` extra for sites that genuinely need JS.

## Decisions (agreed with the owner)

- Transport: stdio only.
- Language: every tool takes `lang="en"|"fi"`, default `en`; fall back to Finnish with a note.
- Macros: scrape whatever each site publishes; if a site has none, return the menu as-is
  (`macros = null`). No estimation.
- Tools: `list_restaurants`, `get_menu` (no macros), `get_full_menu` (menu + macros),
  `get_macros` (one dish), `search_dishes_by_macros`. `restaurant=None` means all restaurants.
- Date defaults to today in Europe/Helsinki; accepts today/tomorrow/weekday names/ISO.
- Lunch only. Dipoli: all lunch lines. Unicafe: Kaivopiha only.
- Commit directly to `main`, small conventional commits.

## Architecture

```
src/ravintola_mcp/
  models.py        Macros, Dish, Menu, Restaurant (contracts — keep stable)
  restaurants.py   registry + alias resolution; provider ids live in Restaurant.config
  adapters/base.py MenuAdapter ABC + slugify/parse_number helpers
  adapters/<provider>.py   one per provider, registered in adapters/__init__.py ADAPTERS
  dates.py, cache.py, service.py (MenuService), server.py (FastMCP tools)
tests/fixtures/<provider>/  recorded real responses; adapter tests parse these offline
```

Adapter rules: plain GET first; empty `dishes` (not an exception) when closed; only
published macro values; record the `basis` (per portion vs per 100 g).

## Adapter status

| Provider | Restaurants                  | Status | Source / notes                                                    |
|----------|------------------------------|--------|-------------------------------------------------------------------|
| compass  | A Bloc, TUAS, Dipoli, Alvari | done   | `menuapi/day-menus` + `menuapi/recipes/<id>` (per 100 g macros)    |
| sodexo   | Kvarkki, T-talo              | done   | `ruokalistat/output/daily_json/{id}/{date}` (per-component macros) |
| kipsari  | Kipsari Väre                 | done   | `kipsari.com/rss-vare[-english]/`; no macros published; Studio has no feed |
| taffa    | Täffä                        | later  | data only on `newapi.tf.fi/taffa/{lang}/json/week/`: host must be allowlisted |
| menssa   | Menssa                       | later  | `menssa.fi/lounas/`: bare `menssa.fi` must be allowlisted          |
| unicafe  | Kaivopiha                    | later  | `unicafe.fi/wp-json/swiss/v1/restaurants?lang=`: host must be allowlisted |

Provider ids were taken from Kanttiinit's restaurant list
(`https://kitchen.kanttiinit.fi/restaurants`), which records each restaurant's upstream feed.
Kanttiinit itself (`/menus?restaurants=<id>&days=<date>`) is reachable and serves menus without
macros for the blocked restaurants (Täffä 3, Menssa 84, Kaivopiha 12): a possible stop-gap.

## Next steps

1. Allowlist `newapi.tf.fi`, `menssa.fi` and `unicafe.fi`, then implement the three remaining
   adapters the same way (live research, fixtures, offline + live tests).
2. Optional: cache Compass recipe nutrition across days (recipes are static) to cut requests.
