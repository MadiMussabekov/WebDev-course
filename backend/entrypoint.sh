#!/bin/sh
# Prepare the database, then start the server.
set -e

python manage.py migrate --noinput
python manage.py seed_bounty

exec "$@"
