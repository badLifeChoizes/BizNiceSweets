#!/usr/bin/env bash
# scripts/local-ci/lib.sh
# ABOUTME: Shared podman helpers for the local CI scripts — the Postgres service the retired
# ABOUTME: GitHub Actions jobs declared under `services:`, started and torn down the same way.
#
# Usage: sourced by gate.sh and clean-room.sh; not run directly.

# The credentials are the ones the archived ci.yml used, and they must keep matching
# .env.db for the container-image boot probe to work. They are throwaway test values.
PG_IMAGE="${PG_IMAGE:-docker.io/library/postgres:17}"
PG_USER=app
PG_PASSWORD=ci_test_pw
# POSTGRES_DB=biznice creates the database the verify_* scripts expect. The maintenance
# `postgres` database still exists either way, which is the one conftest.py connects to
# before it creates biznice_test — so one service satisfies every job.
PG_DB=biznice
PG_PORT="${PG_PORT:-55432}"

NET="${NET:-bns-local-ci}"
PG_NAME="${PG_NAME:-bns-local-ci-pg}"

need_podman() { command -v podman >/dev/null || { echo "podman is not installed" >&2; exit 127; }; }

# The network is created independently of Postgres: jobs that need no database still join it,
# so creating it only inside pg_up left them addressing a network that did not exist.
net_up() { podman network exists "$NET" 2>/dev/null || podman network create "$NET" >/dev/null; }

pg_up() {
  net_up
  podman rm -f "$PG_NAME" >/dev/null 2>&1 || true
  podman run -d --name "$PG_NAME" --network "$NET" \
    -e POSTGRES_USER="$PG_USER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DB" \
    -p "127.0.0.1:${PG_PORT}:5432" \
    "$PG_IMAGE" >/dev/null
  # The same readiness gate the workflow's `--health-cmd pg_isready` gave for free.
  for _ in $(seq 1 60); do
    if podman exec "$PG_NAME" pg_isready -U "$PG_USER" >/dev/null 2>&1; then
      echo "postgres ready on 127.0.0.1:${PG_PORT}"
      return 0
    fi
    sleep 1
  done
  echo "postgres never became ready" >&2
  podman logs "$PG_NAME" >&2 || true
  return 1
}

pg_down() { podman rm -f "$PG_NAME" >/dev/null 2>&1 || true; }
