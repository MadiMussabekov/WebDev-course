# Assignment 1 — Dockerized Django "Hello, World"

A minimal Django web app with one page. The page shows a greeting message
(read from the `APP_MESSAGE` environment variable) and re-fetches it from a
small JSON API (`/api/hello/`) every 5 seconds, so the displayed server time
updates live.

## Project structure

- `manage.py`, `config/` — Django project (settings, URLs, WSGI entrypoint)
- `hello/` — Django app (view + template) rendering the greeting page and the `/api/hello/` endpoint
- `requirements.txt` — Python dependencies (Django, gunicorn)
- `Dockerfile` — container build instructions
- `.dockerignore` — files excluded from the build context
- `.env.example` — sample environment variables

## Environment variables

| Variable | Purpose | Default (set in Dockerfile) |
|---|---|---|
| `APP_MESSAGE` | Greeting text shown on the page | `Hello, World!` |
| `DJANGO_SECRET_KEY` | Django secret key | dev fallback (override in real use) |
| `DJANGO_DEBUG` | `True`/`False` debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `*` |

## Run locally without Docker (optional)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

## Build and run with Docker

Build the image:

```
docker build -t assignment1 .
```

Run the container (maps container port 8000 to host port 8000):

```
docker run -p 8000:8000 --env-file .env assignment1
```

Or override the environment variable directly on the command line without a `.env` file:

```
docker run -p 8000:8000 -e APP_MESSAGE="Hello from Docker!" assignment1
```

Then open http://localhost:8000 in a browser. The page fetches `/api/hello/`
every 5 seconds and updates the displayed message and server time.

## Making a live change and rebuilding

1. Edit `APP_MESSAGE` in `.env`, or change the greeting logic in `hello/views.py`.
2. Rebuild: `docker build -t assignment1 .`
3. Re-run: `docker run -p 8000:8000 --env-file .env assignment1`
