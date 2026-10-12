#!/bin/sh
set -e

echo "[DevTask] Checking database connectivity and applying migrations..."
python manage.py migrate --noinput

echo "[DevTask] Starting application server..."
exec "$@"
