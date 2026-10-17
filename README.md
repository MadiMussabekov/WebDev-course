# Assignment 2 - Time Capsule

Django app with PostgreSQL, running with Docker Compose.

You can write a message and choose when it unlocks. Before that date the message
can't be read (the API returns 423). After it unlocks anyone can open it, and the
app counts how many times it was opened.

## How to run

```
cp .env.example .env
docker compose up --build
```

Then open http://localhost:8000

## Services

- `backend` - Django + gunicorn, built from the Dockerfile. Runs migrations on start.
- `db` - PostgreSQL 16. Data is stored in the `pgdata` volume.

The backend connects to the database using the service name `db`. It starts only
after the database healthcheck passes.

## API

- `GET /api/health/` - checks database connection
- `GET /api/capsules/` - list of capsules (can filter with `?status=locked` or `?status=unlocked`)
- `POST /api/capsules/` - create a capsule
- `GET /api/capsules/<id>/` - open a capsule
- `GET /api/stats/` - some stats

Example:

```
curl -X POST http://localhost:8000/api/capsules/ -H "Content-Type: application/json" -d '{"author":"Madi","title":"Test","message":"Hello","unlock_in_seconds":60}'
```

## Environment variables

All settings are in `.env` (see `.env.example`). `.env` is not committed to git.

## Checking that data is saved

```
docker compose down
docker compose up -d
```

The capsules are still there after this. `docker compose down -v` deletes the data.
