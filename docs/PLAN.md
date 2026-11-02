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
| taffa    | Täffä                        | done   | `newapi.tf.fi/taffa/{fi,en}/json/week/` (current week only); no macros published |
| menssa   | Menssa                       | done   | `menssa.fi/lounas/` HTML (current week only); no macros published; pizzas left out |
| unicafe  | Kaivopiha                    | done   | `unicafe.fi/wp-json/swiss/v1/restaurants?lang=` (~1 MB, all restaurants, cached); per 100 g macros |

Provider ids were taken from Kanttiinit's restaurant list
(`https://kitchen.kanttiinit.fi/restaurants`), which records each restaurant's upstream feed.
Hosts the server needs: www.compass-group.fi, www.sodexo.fi, www.kipsari.com, newapi.tf.fi,
menssa.fi, unicafe.fi.

## Next steps (optional)

1. Cache Compass recipe nutrition across days (recipes are static) to cut requests.
2. Unicafe dish descriptions carry full ingredient lists (up to ~2k chars); consider trimming
   them in `get_menu` if responses get too long for the calling model.
3. Täffä and Menssa only publish the current week; Compass, Sodexo and Unicafe accept any date.
