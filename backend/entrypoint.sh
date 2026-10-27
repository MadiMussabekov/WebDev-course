#!/bin/sh
# Container start-up: prepare the database, then hand over to the CMD (gunicorn).
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

if [ "${SEED_ON_STARTUP:-true}" = "true" ]; then
    python manage.py seed_galaxy
fi

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null \
        && echo "Superuser '$DJANGO_SUPERUSER_USERNAME' created." \
        || echo "Superuser '$DJANGO_SUPERUSER_USERNAME' already exists."
fi

exec "$@"
