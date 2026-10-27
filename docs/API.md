# HoloNet Galactic Atlas API - Reference

Base URL: `http://localhost:8000/api`

Interactive docs (generated from the code, always up to date):

| | URL |
|---|---|
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI 3 schema | http://localhost:8000/api/schema/ (snapshot: [`openapi.yaml`](openapi.yaml)) |

## Conventions

- **JSON** in and out. Send `Content-Type: application/json` on `POST`/`PUT`/`PATCH`.
- **Flexible lookups.** Every `{id}` path segment accepts a numeric id, a slug or the exact
  name (case-insensitive): `/planets/1/`, `/planets/yavin-iv/` and `/planets/Yavin IV/` are the same planet.
  Films are looked up by title instead of name.
- **Pagination.** List endpoints return `{count, next, previous, results}`, 10 items per page.
  Use `?page=2` and `?page_size=50` (max 100). Regions, climates and terrains are not paginated.
- **Search & ordering.** Lists accept `?search=<text>` and `?ordering=<field>` (prefix `-` for descending).
- **Relations on write vs. read.** Foreign keys / many-to-many fields are **written as ids**
  (`"homeworld": 1`, `"species": [1, 2]`) and **read back as summaries**
  (`{"id": 1, "name": "Tatooine", "slug": "tatooine"}`).
  Planet `climates` and `terrains` are written and read as **names**; unknown names are created automatically.
- **Slugs** are generated from the name on create and are read-only.
- **No authentication** - the API is an open demo.

### Status codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created (`POST`) |
| 204 | Deleted (`DELETE`, empty body) |
| 400 | Validation error - body is `{field: [messages]}` |
| 404 | Resource not found - `{"detail": "..."}` |
| 422 | Request is valid but cannot be processed (e.g. route to an uncharted planet) |

---

## Planets

| Method | Path | Description |
|---|---|---|
| GET | `/planets/` | List planets |
| POST | `/planets/` | Create a planet |
| GET | `/planets/{id}/` | Get a planet by id, slug or name |
| PUT | `/planets/{id}/` | Replace a planet |
| PATCH | `/planets/{id}/` | Partially update a planet |
| DELETE | `/planets/{id}/` | Delete a planet (residents/species keep existing with `homeworld = null`) |
| GET | `/planets/{id}/people/` | Notable people whose homeworld is this planet |
| GET | `/planets/{id}/species/` | Native species + species of the planet's residents |
| GET | `/planets/{id}/films/` | Films the planet appears in |
| GET | `/planets/{id}/nearest/?limit=5` | Closest charted planets (1-50) |
| GET | `/planets/distance/?from=&to=[&starship=]` | Distance and optional travel time |

**List filters:** `name` (contains), `climate`, `terrain`, `region` (region slug), `charted` (`true`/`false`),
`min_population`, `max_population`, `search`, `ordering` (`id`, `name`, `population`, `diameter`,
`surface_water`, `resident_count`).

```
GET /api/planets/?climate=arid&region=outer-rim&ordering=-population
```

**Planet object**

| Field | Type | Notes |
|---|---|---|
| `id` | int | read-only |
| `name` | string | required, unique |
| `slug` | string | read-only |
| `region` | int → object | region id on write |
| `grid_square` | string \| null | galactic grid square, e.g. `"R-16"` (column A-Z, row 1-25). `null` = uncharted |
| `grid_x`, `grid_y` | int \| null | read-only, derived from `grid_square` |
| `climates`, `terrains` | string[] | names |
| `rotation_period` | int \| null | hours |
| `orbital_period` | int \| null | days |
| `diameter` | int \| null | km |
| `gravity` | string | |
| `surface_water` | decimal \| null | percent, 0-100 |
| `population` | int \| null | |
| `resident_count` | int | read-only |
| `created_at`, `updated_at` | datetime | read-only |

**Create**

```http
POST /api/planets/
{
  "name": "Jakku",
  "region": 7,
  "grid_square": "M-21",
  "climates": ["arid"],
  "terrains": ["desert", "starship graveyard"],
  "population": 2000
}
```

`201 Created` - returns the planet with `"slug": "jakku"`, `"grid_x": 13, "grid_y": 21`.

**Species on a planet** - `GET /api/planets/naboo/species/`

```json
{
  "planet": {"id": 8, "name": "Naboo", "slug": "naboo"},
  "native_species": [{"id": 12, "name": "Gungan", "slug": "gungan", "classification": "amphibian", "language": "Gungan basic"}],
  "resident_species": [
    {"id": 1, "name": "Human", "slug": "human", "residents": 7},
    {"id": 12, "name": "Gungan", "slug": "gungan", "residents": 3},
    {"id": 2, "name": "Droid", "slug": "droid", "residents": 1}
  ]
}
```

### Navigation

SWAPI has no coordinates, so each planet stores its position on the galactic grid (`grid_x`, `grid_y`),
seeded for 36 well-known worlds; the rest are *uncharted* until you `PATCH` a `grid_square` onto them.

- distance = Euclidean distance in grid squares; 1 square ≈ 6,000 light years
  (planets in the same square count as ¼ square apart)
- travel time = grid squares × 6 h × hyperdrive rating (Class 1 ≈ 6 h per square; Class 0.5 is twice as fast)

The nearest-planet query is computed in PostgreSQL: the squared distance is an annotated
expression and the database sorts by it (indexed `grid_x, grid_y`).

`GET /api/planets/distance/?from=tatooine&to=hoth&starship=millennium-falcon`

```json
{
  "origin": {"id": 1, "name": "Tatooine", "slug": "tatooine", "region": "Outer Rim", "grid_square": "R-16"},
  "destination": {"id": 4, "name": "Hoth", "slug": "hoth", "region": "Outer Rim", "grid_square": "K-18"},
  "distance": {"grid_squares": 7.28, "light_years": 43681, "parsecs": 13399},
  "travel": {
    "starship": {"id": 10, "name": "Millennium Falcon", "slug": "millennium-falcon"},
    "hyperdrive_rating": 0.5, "estimated_hours": 21.8, "estimated_days": 0.91
  }
}
```

Errors: `400` if `from`/`to` is missing, `404` if a planet/starship does not exist,
`422` if a planet is uncharted, both are the same planet, or the starship has no hyperdrive.

`GET /api/planets/coruscant/nearest/?limit=3`

```json
[
  {"id": 32, "name": "Chandrila", "slug": "chandrila", "region": "Core Worlds", "grid_square": "L-9", "grid_distance": 0.0, "light_years": 1500},
  {"id": 2, "name": "Alderaan", "slug": "alderaan", "region": "Core Worlds", "grid_square": "M-10", "grid_distance": 1.41, "light_years": 8485},
  {"id": 18, "name": "Cato Neimoidia", "slug": "cato-neimoidia", "region": "Colonies", "grid_square": "M-10", "grid_distance": 1.41, "light_years": 8485}
]
```

---

## Species

| Method | Path | Description |
|---|---|---|
| GET | `/species/` | List (filters: `name`, `classification`, `designation`, `homeworld` slug) |
| POST | `/species/` | Create |
| GET / PUT / PATCH / DELETE | `/species/{id}/` | Get / replace / update / delete |
| GET | `/species/{id}/people/` | Known members of the species |

Fields: `name` (required, unique), `classification`, `designation`, `average_height` (cm),
`average_lifespan` (years), `language`, `skin_colors`, `hair_colors`, `eye_colors`, `homeworld` (planet id).

```http
POST /api/species/
{"name": "Teedo", "classification": "reptilian", "designation": "sentient", "average_height": 120, "homeworld": 1}
```

## People

| Method | Path | Description |
|---|---|---|
| GET | `/people/` | List (filters: `name`, `gender`, `homeworld` slug, `species` slug) |
| POST | `/people/` | Create |
| GET / PUT / PATCH / DELETE | `/people/{id}/` | Get / replace / update / delete |

Fields: `name` (required), `birth_year` (e.g. `19BBY`), `gender`, `height` (cm), `mass` (kg),
`hair_color`, `skin_color`, `eye_color`, `homeworld` (planet id), `species` (ids), `starships` (ids piloted).

```http
POST /api/people/
{"name": "Rey", "birth_year": "15ABY", "gender": "female", "homeworld": 1, "species": [1], "starships": [10]}
```

## Starships

| Method | Path | Description |
|---|---|---|
| GET | `/starships/` | List (filters: `name`, `starship_class`, `max_hyperdrive_rating`; ordering incl. `hyperdrive_rating`) |
| POST | `/starships/` | Create |
| GET / PUT / PATCH / DELETE | `/starships/{id}/` | Get / replace / update / delete |

Fields: `name` (required), `model`, `manufacturer`, `starship_class`, `hyperdrive_rating` (decimal ≥ 0.1, lower is faster),
`mglt`, `max_atmosphering_speed`, `length` (m), `crew`, `passengers`, `cargo_capacity` (kg), `consumables`,
`cost_in_credits`, `pilots` (person ids).

## Films

| Method | Path | Description |
|---|---|---|
| GET | `/films/` | List, ordered by episode (filter: `director`) |
| POST | `/films/` | Create |
| GET / PUT / PATCH / DELETE | `/films/{id}/` | Get / replace / update / delete (lookup by id, slug or title) |

Fields: `title` (required, unique), `episode_id` (required, unique), `director`, `producer`, `release_date`
(`YYYY-MM-DD`), `opening_crawl`, `planets`, `characters`, `species`, `starships` (ids).

## Reference data (read-only)

| Method | Path | Description |
|---|---|---|
| GET | `/regions/` | The 9 galactic regions, core → rim, with planet counts |
| GET | `/regions/{id}/` | One region (id or slug, e.g. `outer-rim`) |
| GET | `/regions/{id}/planets/` | Planets in a region |
| GET | `/climates/`, `/climates/{id}/` | Climates with planet counts (id or name) |
| GET | `/terrains/`, `/terrains/{id}/` | Terrains with planet counts (id or name) |

## Service

| Method | Path | Description |
|---|---|---|
| GET | `/health/` | `{"status": "ok", "database": "up"}` - used by the Docker healthcheck |
| GET | `/stats/` | Counts, total population, most populous planets, fastest starships |
