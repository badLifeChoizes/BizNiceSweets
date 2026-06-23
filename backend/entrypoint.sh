#!/usr/bin/env sh
# backend/entrypoint.sh
#
# Container startup sequence (D-09):
#   1. Wait for PostgreSQL to accept connections (belt-and-suspenders alongside
#      compose service_healthy healthcheck — Pitfall 2 in RESEARCH.md).
#   2. Run Alembic migrations (idempotent; safe to run on every startup).
#   3. Launch uvicorn.  Appends --reload when UVICORN_RELOAD is set to a
#      truthy value (dev compose overlay, D-11).
#
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until pg_isready \
        -h "${POSTGRES_HOST:-db}" \
        -p "${POSTGRES_PORT:-5432}" \
        -U "${POSTGRES_USER:-app}"; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running Alembic migrations..."
alembic upgrade head
echo "Migrations complete."

echo "Starting API server..."
if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
