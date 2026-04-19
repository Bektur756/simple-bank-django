#!/bin/sh
set -eu

until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

python manage.py migrate --noinput
python manage.py runserver 0.0.0.0:8000
