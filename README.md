# opiskelija-ravintola-mcp

MCP server (stdio) that returns lunch menus and per-dish nutrition (macros) for Finnish
student restaurants on the Aalto Otaniemi campus and Unicafe Kaivopiha in Helsinki. Data comes
straight from each restaurant's own public feed with plain HTTP GET; no browser automation.

> **Unofficial.** This project is not affiliated with or endorsed by Compass Group, Sodexo,
> Unicafe, Teknologföreningen (Täffä), Menssa or Kipsari. Menus, diet codes, allergens and
> nutrition values are relayed as each operator publishes them and may be incomplete, outdated
> or wrong. **If you have an allergy or a special diet, always confirm with the restaurant
> staff.**

## Restaurants

| id                  | Restaurant                   | Data published by       | Macros                     |
|---------------------|------------------------------|-------------------------|----------------------------|
| `a-bloc`            | A Bloc                       | Compass Group (FoodCo)  | per 100 g                  |
| `tuas`              | TUAS                         | Compass Group (FoodCo)  | per 100 g                  |
| `dipoli`            | Dipoli                       | Compass Group (FoodCo)  | per 100 g                  |
| `alvari`            | Alvari                       | Compass Group (FoodCo)  | per 100 g                  |
| `kvarkki`           | Aalto Kvarkki                | Sodexo                  | per 100 g, per component   |
| `t-talo`            | Tietotekniikan talo (T-talo) | Sodexo                  | per 100 g, per component   |
| `unicafe-kaivopiha` | Unicafe Kaivopiha            | Unicafe                 | per 100 g                  |
| `kipsari`           | Kipsari Väre                 | Kipsari                 | not published              |
| `taffa`             | Täffä                        | Teknologföreningen      | not published              |
| `menssa`            | Menssa                       | Menssa                  | not published              |

Restaurant arguments accept the id, the name or an alias, ignoring case and accents
(`"A Block"`, `"täffä"`, `"väre"`, `"kaivopiha"`).

## Tools

| Tool                      | Returns                                                             |
|---------------------------|---------------------------------------------------------------------|
| `list_restaurants`        | Supported restaurants with ids, aliases, campus and menu page.      |
| `get_menu`                | Menu without nutrition. Omit `restaurant` to get every restaurant.  |
| `get_full_menu`           | Menu with nutrition per dish (and per component where published).   |
| `get_macros`              | Nutrition of one dish, matched by id, name or fuzzy name.           |
| `search_dishes_by_macros` | Dishes across restaurants filtered by protein/kcal/fat/carbs/diets. |

Common arguments: `date` defaults to today in Europe/Helsinki and accepts `today`, `tomorrow`,
`yesterday`, an English or Finnish weekday (`friday`, `perjantai` = next occurrence) or an ISO
date. `lang` is `en` (default) or `fi`; a site without English falls back to Finnish with a note.

Nutrition is reported exactly as published. Compass, Sodexo and Unicafe publish values per 100 g
(`macros.basis = "100g"`) without portion weights, so they compare dishes but are not
per-portion totals. Results are cached in memory for 30 minutes (2 minutes for failures).

## Data sources and fair use

All menu data belongs to the restaurant operators listed above. Every menu returned by the
server carries a `source` credit line (e.g. `Source: Sodexo (sodexo.fi)`) and the operator's
`source_url`. The server is meant to run locally, for your own personal, non-commercial use: it
fetches public pages and feeds on your machine, identifies itself with its User-Agent, and
caches results so each site sees only a few requests. Respect the operators' terms of use. In
particular, Compass Group and Sodexo allow only non-commercial use, so do not host this as a
public service or use it commercially without their permission.

The test fixtures in `tests/fixtures/` are synthetic: they mirror the structure of each site's
responses with invented values and contain no data from the restaurants.

## Install and use

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/mkhlrmnv/opiskelija-ravintola-mcp.git
cd opiskelija-ravintola-mcp
uv sync
```

Claude Code:

```bash
claude mcp add opiskelija-ravintola -- uv --directory /path/to/opiskelija-ravintola-mcp run opiskelija-ravintola-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "opiskelija-ravintola": {
      "command": "uv",
      "args": ["--directory", "/path/to/opiskelija-ravintola-mcp", "run", "opiskelija-ravintola-mcp"]
    }
  }
}
```

## Development

```bash
uv run pytest            # offline tests against synthetic fixtures in tests/fixtures/
uv run pytest -m live    # smoke tests against the real sites
uv run ruff check . && uv run ruff format .
```

CI (`.github/workflows/ci.yml`) runs on every pull request and every push to `main`: ruff lint
and format checks plus the offline tests on Python 3.11–3.13, and a gitleaks scan of the full
git history. Live tests are not run in CI.

Each provider is one adapter in `src/ravintola_mcp/adapters/` implementing `MenuAdapter`;
restaurants and their provider ids live in `src/ravintola_mcp/restaurants.py`. How each data
source was found and what it contains is documented in `docs/research/`.

## License

The code is released under the [MIT License](LICENSE). The license covers this software only,
not the menu data it retrieves, which remains the property of the restaurant operators.
