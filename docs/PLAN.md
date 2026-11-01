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

## Adapter work breakdown

| Provider    | Restaurants                       | Leads (UNVERIFIED, see docs/research/)                                   |
|-------------|-----------------------------------|--------------------------------------------------------------------------|
| compass     | A Bloc, TUAS, Dipoli, Alvari      | `menuapi/feed/json?costNumber=&language=`, `menuapi/day-menus?costCenter=`; cost ids unknown; macros unknown (maybe recipe endpoint) |
| sodexo      | Kvarkki, likely T-talo            | `ruokalistat/output/daily_json/{id}/{date}`; ids unknown; pipe-delimited nutrient strings reported |
| kanttiinit  | T-talo (fallback only)            | `kitchen.kanttiinit.fi/menus?restaurants=2&days=`; no macros expected      |
| taffa       | Täffä                             | lunch.tf.fi; Täffä moved to A Blanc (Otakaari 27) in Oct 2026             |
| menssa      | Menssa                            | nothing verified                                                         |
| kipsari     | Kipsari (Studio + Väre?)          | nothing verified; possibly Facebook-only                                 |
| unicafe     | Kaivopiha                         | menu.unicafe.fi backend unknown; old `unicafe.fi/wp-json/swiss/v1/restaurants` |

## Status / next steps

1. Done: core contracts, registry, service, cache, date parsing, MCP tools, tests with fakes.
2. Blocked until a session starts with network access to the restaurant domains
   (the first session's container was created before the allowlist was changed).
3. Next: re-run per-site research in-container (curl the pages, find ids/endpoints,
   save raw responses as fixtures), then one Haiku agent per adapter, then live smoke tests
   (`pytest -m live`), README usage + Claude Desktop/Code config.
