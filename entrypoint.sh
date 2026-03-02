#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding integrations..."
python scripts/seed.py

echo "Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
