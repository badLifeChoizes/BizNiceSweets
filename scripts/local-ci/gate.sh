#!/usr/bin/env bash
# scripts/local-ci/gate.sh
# ABOUTME: Every check the retired GitHub Actions CI ran, driven locally through podman.
# ABOUTME: Backend jobs run in python:3.13 because this host carries 3.12 and CI pinned 3.13.
#
# Usage: scripts/local-ci/gate.sh [--only <job>] [--keep-pg]
#   jobs: backend-lint backend-tests verify-scripts verify-scripts-api frontend
#
# WHY containers rather than the host venv: the archived workflow pinned Python 3.13 and Node 22,
# and this machine has Python 3.12. A gate that silently tests a different interpreter than the
# one the project ships against is a gate that reports on something else.
#
# The container-image job is NOT here — it is clean-room.sh, because an uncached image build on
# a cold tree is a different kind of check and wants running deliberately.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
. scripts/local-ci/lib.sh

ONLY=""; KEEP_PG=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) shift; ONLY="${1:?--only needs a job}" ;;
    --keep-pg) KEEP_PG=1 ;;
    -h|--help) sed -n '1,18p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

need_podman
net_up
FAILED=()
PY_IMAGE="${PY_IMAGE:-docker.io/library/python:3.13}"
NODE_IMAGE="${NODE_IMAGE:-docker.io/library/node:22}"
REPO="$PWD"

say()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }
skip() { [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; }
fail() { FAILED+=("$1"); printf '\033[31mFAIL\033[0m %s\n' "$1"; }
ok()   { printf '\033[32mok\033[0m   %s\n' "$1"; }

# A pip cache volume keeps a repeat run from re-downloading the whole requirements tree.
# It caches wheels only — never the project — so it cannot mask a dependency change.
podman volume exists bns-local-ci-pip 2>/dev/null || podman volume create bns-local-ci-pip >/dev/null

# Backend containers join the postgres network and address it by container name, which is the
# local analogue of the workflow's `services:` block resolving on localhost.
py() {
  podman run --rm -i --network "$NET" \
    -v "$REPO":/src:Z -v bns-local-ci-pip:/root/.cache/pip \
    -w /src/backend \
    -e POSTGRES_HOST="$PG_NAME" -e POSTGRES_PORT=5432 \
    -e POSTGRES_USER="$PG_USER" -e POSTGRES_PASSWORD="$PG_PASSWORD" \
    -e JWT_SECRET=ci_test_jwt_secret_at_least_32_chars_long \
    -e BNS_ADMIN_PASSWORD=ci_test_pw \
    -e PYTHONPATH=/src/backend \
    "$@"
}

NEEDS_PG=0
for j in backend-tests verify-scripts verify-scripts-api; do
  { [ -z "$ONLY" ] || [ "$ONLY" = "$j" ]; } && NEEDS_PG=1
done
if [ "$NEEDS_PG" = 1 ]; then
  say "postgres service"
  pg_up || exit 1
  [ "$KEEP_PG" = 1 ] || trap 'pg_down' EXIT
fi

if ! skip backend-lint; then
  say "backend-lint (ruff)"
  if py "$PY_IMAGE" bash -c 'pip install -q -r requirements-dev.txt && ruff check .'; then
    ok "ruff check"; else fail "ruff check"; fi
fi

if ! skip backend-tests; then
  say "backend-tests (pytest)"
  # conftest.py connects to the maintenance database, CREATEs biznice_test and migrates it
  # itself, so nothing here sets POSTGRES_DB.
  if py "$PY_IMAGE" bash -c 'pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q'; then
    ok "pytest"; else fail "pytest"; fi
fi

if ! skip verify-scripts; then
  say "verify-scripts (non-API) + UAT seed idempotency"
  if py -e POSTGRES_DB="$PG_DB" "$PY_IMAGE" bash -c '
    set -e
    pip install -q -r requirements.txt -r requirements-dev.txt
    python -m alembic upgrade head
    python - <<PY
import asyncio
from app.core.db import AsyncSessionLocal
from app.core.seed import run_seeds
async def main():
    async with AsyncSessionLocal() as db:
        await run_seeds(db)
asyncio.run(main())
print("seeds applied")
PY
    for s in scripts/verify_*.py; do
      case "$s" in *_api.py) continue ;; esac
      echo "== $s =="; python "$s"
    done'; then ok "verify_*.py"; else fail "verify_*.py"; fi

  # The seed manifest is the contract .zj/QA.md quotes 275 derived literals from. A second run
  # must change nothing — and the census catches a table the manifest does not count.
  if py -e POSTGRES_DB=uatseed -e BNS_ALLOW_UAT_SEED=1 "$PY_IMAGE" bash -c '
    set -e
    pip install -q -r requirements.txt -r requirements-dev.txt
    python - <<PY
import asyncio, os, asyncpg
async def main():
    c = await asyncpg.connect(host=os.environ["POSTGRES_HOST"], port=5432,
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
        database="postgres")
    await c.execute("DROP DATABASE IF EXISTS uatseed")
    await c.execute("CREATE DATABASE uatseed")
    await c.close()
asyncio.run(main())
print("created database uatseed")
PY
    python -m alembic upgrade head
    cat > /tmp/census.py <<PY
import asyncio, os, asyncpg
TABLES = ("SELECT table_name FROM information_schema.tables WHERE table_schema = %s "
          "AND table_type = %s ORDER BY table_name")
async def main():
    c = await asyncpg.connect(host=os.environ["POSTGRES_HOST"], port=5432,
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"])
    rows = await c.fetch("SELECT table_name FROM information_schema.tables "
                         "WHERE table_schema = \$1 AND table_type = \$2 ORDER BY table_name",
                         "public", "BASE TABLE")
    for r in rows:
        t = r["table_name"]
        print(t, await c.fetchval("SELECT count(*) FROM \"" + t + "\""))
    await c.close()
asyncio.run(main())
PY
    python scripts/seed_uat_fixtures.py > /tmp/manifest-1.txt
    python /tmp/census.py                > /tmp/census-1.txt
    python scripts/seed_uat_fixtures.py > /tmp/manifest-2.txt
    python /tmp/census.py                > /tmp/census-2.txt
    diff -u /tmp/manifest-1.txt /tmp/manifest-2.txt || { echo "seed_uat_fixtures.py is NOT idempotent — the manifest changed"; exit 1; }
    diff -u /tmp/census-1.txt /tmp/census-2.txt || { echo "the second seed run WROTE ROWS in a table the manifest does not count"; exit 1; }
    echo "manifest byte-identical across two runs on a fresh database"'; then
    ok "UAT seed idempotency"; else fail "UAT seed idempotency"; fi
fi

if ! skip verify-scripts-api; then
  say "verify-scripts-api (against a booted api)"
  if py -e POSTGRES_DB="$PG_DB" -e BNS_API_BASE_URL=http://127.0.0.1:8099 "$PY_IMAGE" bash -c '
    set -e
    pip install -q -r requirements.txt -r requirements-dev.txt
    python -m alembic upgrade head
    nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 > /tmp/uvicorn.log 2>&1 &
    for _ in $(seq 1 60); do
      if curl -fsS "$BNS_API_BASE_URL/health/ready"; then echo; echo "api serving on 8099"; break; fi
      sleep 1
    done
    curl -fsS "$BNS_API_BASE_URL/health/ready" >/dev/null || { echo "api never became ready"; cat /tmp/uvicorn.log; exit 1; }
    for s in scripts/verify_*_api.py; do echo "== $s =="; python "$s"; done'; then
    ok "verify_*_api.py"; else fail "verify_*_api.py"; fi
fi

if ! skip frontend; then
  say "frontend (node 22)"
  if podman run --rm -i -v "$REPO":/src:Z -w /src/frontend "$NODE_IMAGE" \
       bash -c 'npm ci && npm run lint && npx tsc -b && npx vitest run && npm run build'; then
    ok "frontend"; else fail "frontend"; fi
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then printf '\033[32mgate passed\033[0m\n'; exit 0; fi
printf '\033[31mgate failed (%d):\033[0m\n' "${#FAILED[@]}"; printf '  - %s\n' "${FAILED[@]}"; exit 1
