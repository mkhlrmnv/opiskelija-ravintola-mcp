# opiskelija-ravintola-mcp

MCP server (stdio) that returns lunch menus and per-dish nutrition (macros) for Finnish
student restaurants on the Aalto Otaniemi campus and Unicafe Kaivopiha in Helsinki. Data comes
straight from each restaurant's own public feed with plain HTTP GET; no browser automation.

## Restaurants

| id                  | Restaurant                   | Source                  | Macros                     |
|---------------------|------------------------------|-------------------------|----------------------------|
| `a-bloc`            | A Bloc                       | Compass Group (FoodCo)  | per 100 g                  |
| `tuas`              | TUAS                         | Compass Group (FoodCo)  | per 100 g                  |
| `dipoli`            | Dipoli                       | Compass Group (FoodCo)  | per 100 g                  |
| `alvari`            | Alvari                       | Compass Group (FoodCo)  | per 100 g                  |
| `kvarkki`           | Aalto Kvarkki                | Sodexo                  | per 100 g, per component   |
| `t-talo`            | Tietotekniikan talo (T-talo) | Sodexo                  | per 100 g, per component   |
| `kipsari`           | Kipsari Väre                 | kipsari.com RSS         | not published              |
| `taffa`             | Täffä                        | newapi.tf.fi            | pending (host not allowed) |
| `menssa`            | Menssa                       | menssa.fi               | pending (host not allowed) |
| `unicafe-kaivopiha` | Unicafe Kaivopiha            | unicafe.fi              | pending (host not allowed) |

"Pending" restaurants are registered but return an error until their adapter is implemented;
the data hosts were unreachable from the development environment (see `docs/PLAN.md`).
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

Nutrition is reported exactly as published. Compass and Sodexo publish values per 100 g
(`macros.basis = "100g"`) without portion weights, so they compare dishes but are not
per-portion totals. Results are cached in memory for 30 minutes (2 minutes for failures).

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
uv run pytest            # offline tests against recorded responses in tests/fixtures/
uv run pytest -m live    # smoke tests against the real sites
uv run ruff check . && uv run ruff format .
```

Each provider is one adapter in `src/ravintola_mcp/adapters/` implementing `MenuAdapter`;
restaurants and their provider ids live in `src/ravintola_mcp/restaurants.py`. How each data
source was found and what it contains is documented in `docs/research/`.
