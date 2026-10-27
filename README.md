# HoloNet Galactic Atlas API

A containerised REST API for the Star Wars galaxy. Browse planets, species, people, starships and films
imported from [SWAPI](https://swapi.dev), ask *"who lives on Tatooine?"* or *"which species are native to Naboo?"*,
measure the hyperspace distance between two worlds and estimate how long the Millennium Falcon would take
to get there.

**Stack:** Python 3.13 · Django 5.2 · Django REST Framework · drf-spectacular (OpenAPI / Swagger) ·
PostgreSQL 17 · Gunicorn · Docker Compose

## Quick start

Requirements: Docker Desktop (or Docker Engine + Compose v2).

```bash
cp .env.example .env      # skip if you received a ready-made .env
docker compose up --build
```

On first start the API container applies the migrations, loads the galaxy data and creates an admin user.
Then open:

| What | URL |
|---|---|
| Swagger UI (API docs) | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| API root | http://localhost:8000/api/ |
| Django admin | http://localhost:8000/admin/ (credentials from `.env`) |
| Adminer (DB browser) | http://localhost:8080 (server `db`, credentials from `.env`) |

Try it:

```bash
curl "http://localhost:8000/api/planets/tatooine/people/"
curl "http://localhost:8000/api/planets/distance/?from=tatooine&to=hoth&starship=millennium-falcon"
```

Stop with `docker compose down` (data is kept in the named volume) or `docker compose down -v` to wipe it.

## Documentation

- **[docs/API.md](docs/API.md)** - endpoint reference with request/response examples
- **[docs/openapi.yaml](docs/openapi.yaml)** - OpenAPI 3 schema (also served live at `/api/schema/`)
- **[postman/](postman/)** - Postman collection (67 requests with tests) and environment

### Postman

Import `postman/HoloNet.postman_collection.json` (and optionally `postman/HoloNet.postman_environment.json`),
then *Run collection*. The `baseUrl` variable defaults to `http://localhost:8000`. Each CRUD folder creates a record,
reads, replaces (`PUT`), patches and deletes it, passing the new id between requests through collection
variables, so the collection can be run repeatedly.

From the command line, with the stack running:

```bash
docker run --rm --network holonet_galaxy_net -v "$(pwd)/postman:/etc/newman" \
  postman/newman:6-alpine run HoloNet.postman_collection.json --env-var baseUrl=http://api:8000
```

## Architecture

```
                 host machine
   :8000 │                       │ :8080
┌────────▼─────────┐     ┌───────▼───────┐
│ api              │     │ adminer       │
│ Django + DRF     │     │ DB web UI     │
│ Gunicorn         │     └───────┬───────┘
└────────┬─────────┘             │
         │  postgres://db:5432   │        network: galaxy_net (bridge)
┌────────▼───────────────────────▼───────┐
│ db  - PostgreSQL 17                    │
│ /var/lib/postgresql/data ──► volume galaxy_data
└────────────────────────────────────────┘
```

| Service | Image | Role |
|---|---|---|
| `api` | built from `backend/Dockerfile` | REST API; waits for `db` to be healthy, then migrates, seeds and starts Gunicorn |
| `db` | `postgres:17-alpine` | relational database; data stored in the named volume `galaxy_data`; not published to the host |
| `adminer` | `adminer:5` | optional web UI to inspect the database |

- **Networking:** all services join the user-defined bridge network `galaxy_net`. Containers reach each other
  by service name through Docker's DNS - the API connects to host `db`, Adminer's default server is `db`.
  Only the API (8000) and Adminer (8080) ports are published to the host.
- **Persistence:** PostgreSQL writes to the named volume `galaxy_data`, so data survives
  `docker compose down` / `up` and image rebuilds.
- **Configuration:** everything environment-specific comes from `.env` (see `.env.example`): Django secret key,
  debug flag, allowed hosts, database name/user/password, admin credentials, published ports, Gunicorn workers,
  and `SEED_ON_STARTUP`. Compose uses the same file both for variable substitution in `docker-compose.yml` and
  as the API container's `env_file`.
- **Health checks:** `db` uses `pg_isready`; the API image has a `HEALTHCHECK` hitting `/api/health/`, which also
  runs `SELECT 1` against the database. `depends_on: condition: service_healthy` makes the API start only once
  PostgreSQL accepts connections.

### Dockerfile highlights (`backend/Dockerfile`)

1. `python:3.13-slim` base image.
2. `requirements.txt` is copied and installed **before** the source code, so the dependency layer is cached
   and rebuilding after a code change takes seconds.
3. Static files (Swagger UI assets, admin) are collected at build time and served by WhiteNoise.
4. The app runs as an unprivileged user (`jedi`), not root.
5. `ENTRYPOINT` runs `entrypoint.sh` (migrate → seed → create superuser), then `exec`s the `CMD` (Gunicorn),
   so Gunicorn becomes PID 1 and receives stop signals directly.

## Data model

```
Region 1───* Planet *───* Climate
                │  *───* Terrain
                │ 1
     ┌──────────┼──────────────┐
     * homeworld│              * homeworld
   Person *────*  Species      │
     │ *  (species)            │
     *  pilots                 │
  Starship                     │
     *           *         *   *
     └────── Film (planets, characters, species, starships)
```

SWAPI stores much of its data as free text (`"temperate, tropical"`, `"1,000"`, `"unknown"`). During import the
data was normalised:

- comma-separated **climates and terrains** became lookup tables with many-to-many relations, so you can filter
  `?climate=arid` and the vocabulary can grow (`POST` a planet with a new climate and it is created);
- numeric strings became real numeric columns (`PositiveBigIntegerField` for populations of a trillion,
  `DecimalField` for mass/hyperdrive), and `"unknown"` became `NULL`;
- SWAPI's placeholder planet called *"unknown"* was dropped; references to it became `homeworld = NULL`;
- SWAPI leaves `species` empty for humans - those people were linked to the *Human* species explicitly;
- every resource has a unique **slug**, so URLs can use names (`/planets/yavin-iv/`).

**Galactic coordinates.** SWAPI has no positions, so `Planet` gets `region` and a galactic grid position
(`grid_x`, `grid_y` ↔ `grid_square` like `"R-16"`), seeded for 36 well-known worlds from the canonical galaxy map.
A check constraint guarantees both coordinates are set or both are `NULL`, and a composite index on
`(grid_x, grid_y)` backs the nearest-neighbour query, which orders by a squared-distance expression computed in SQL.
Uncharted planets return `422` from navigation endpoints until you chart them with `PATCH {"grid_square": "N-12"}`.

## Seeding

The SWAPI data was downloaded once and committed as a Django fixture,
`backend/galaxy/fixtures/galaxy_seed.json` (305 records). The one-off download/convert script was not kept in the
repository: the snapshot makes start-up fast, reproducible and independent of SWAPI being online.

`python manage.py seed_galaxy` loads the fixture only when the database has no planets (use `--force` to reload).
The entrypoint runs it on every start when `SEED_ON_STARTUP=true`, which is safe because it is idempotent.

## Project structure

```
.
├── docker-compose.yml          # db + api + adminer, network, named volume
├── .env.example                # documented configuration template (.env is git-ignored)
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh           # migrate → seed → superuser → exec gunicorn
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/                 # Django project: settings (env-driven), root urls, wsgi
│   └── galaxy/                 # the app
│       ├── models.py           # relational schema
│       ├── serializers.py      # validation + representation
│       ├── views.py            # viewsets and custom endpoints
│       ├── filters.py          # query-string filters
│       ├── urls.py             # router
│       ├── services/navigation.py   # distance / travel-time maths
│       ├── management/commands/seed_galaxy.py
│       ├── fixtures/galaxy_seed.json
│       ├── migrations/
│       └── tests.py
├── docs/                       # API.md + openapi.yaml
└── postman/                    # collection + environment
```

## Development tasks

```bash
docker compose exec api python manage.py test galaxy        # run the test suite (12 tests)
docker compose exec api python manage.py makemigrations     # after changing models
docker compose exec -T api python manage.py spectacular > docs/openapi.yaml  # regenerate the schema
docker compose exec db psql -U galaxy -d galaxy             # SQL shell
docker compose logs -f api                                  # follow API logs
docker volume inspect holonet_galaxy_data                   # where the data lives
```
