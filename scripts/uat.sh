#!/usr/bin/env bash
# ABOUTME: One-command setup + launch of the full BizNiceSweets dev stack for human UAT.
# ABOUTME: Bash port of scripts/uat.ps1, which is pwsh-only and so unusable on a host with
# ABOUTME: no PowerShell installed — same four flags (--fresh/--detach/--down/--no-browser),
# ABOUTME: same behaviour. Resolves a compose runner (podman-compose > podman compose >
# ABOUTME: docker compose > docker-compose), ensures BOTH env files exist (.env and .env.db
# ABOUTME: — D-P5-10, the split that defect U0 came from), optionally resets the DB volume,
# ABOUTME: then brings up db + api + frontend via the dev overlay. Detached mode polls
# ABOUTME: /health/ready for ~2 min before opening the app. Seeding the named UAT fixtures
# ABOUTME: is deliberately NOT done here — it is an explicit step in .zj/UAT-v4.0.md §1.1.
#
# One-command setup + launch of the full BizNiceSweets dev stack for human UAT.
#
# Bash port of scripts/uat.ps1, which is pwsh-only and therefore unusable on a
# host without PowerShell installed. Same flags, same behaviour.
#
# Brings up the whole stack using the dev compose overlay:
#   db        PostgreSQL 17 (internal network only, not published to host)
#   api       FastAPI + uvicorn --reload on http://localhost:8000
#             (entrypoint auto-runs `alembic upgrade head`; app startup runs the
#              idempotent seeds incl. the SYERP chart-of-accounts)
#   frontend  Vite dev server + HMR on http://localhost:5173
#
# Everything runs in containers — no local Python/Node install needed. The only
# prerequisite is Podman (preferred) or Docker.
#
# Usage:
#   ./scripts/uat.sh                  Foreground; logs stream, Ctrl+C stops.
#   ./scripts/uat.sh --fresh --detach Reset the DB volume, start in the
#                                     background, wait for health, open the app.
#   ./scripts/uat.sh --down           Stop and remove the stack.
#   ./scripts/uat.sh --down --fresh   Stop and also delete the DB volume.
#
# Flags:
#   -f, --fresh       Reset the database volume (`down -v`) before starting, so
#                     migrations and the seeds re-apply from a clean database.
#                     Use this for a clean UAT pass.
#   -d, --detach      Start in the background (`up -d`), wait for the API to
#                     become healthy, open the app in a browser, then return.
#       --down        Stop and remove the stack, then exit. Combine with --fresh
#                     to also delete the DB volume.
#   -n, --no-browser  Do not auto-open the browser (only relevant with --detach).
#   -h, --help        Show this help.
#
# NOTE: after a --fresh reset the database holds only the automatic startup
# seeds. The named UAT fixtures are a separate, explicit step — see
# .zj/UAT-v4.0.md §1.1 step 5:
#   podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py

set -euo pipefail

FRESH=0
DETACH=0
DOWN=0
NO_BROWSER=0

usage() {
  cat <<'EOF'
uat.sh — launch the BizNiceSweets dev stack for human UAT.

Usage:
  ./scripts/uat.sh                  Foreground; logs stream, Ctrl+C stops.
  ./scripts/uat.sh --fresh --detach Reset the DB volume, start in the background,
                                    wait for health, open the app.
  ./scripts/uat.sh --down           Stop and remove the stack.
  ./scripts/uat.sh --down --fresh   Stop and also delete the DB volume.

Flags:
  -f, --fresh       Reset the database volume (down -v) before starting, so
                    migrations and the seeds re-apply from a clean database.
                    Use this for a clean UAT pass.
  -d, --detach      Start in the background (up -d), wait for the API to become
                    healthy, open the app in a browser, then return.
      --down        Stop and remove the stack, then exit. Combine with --fresh
                    to also delete the DB volume.
  -n, --no-browser  Do not auto-open the browser (only relevant with --detach).
  -h, --help        Show this help.

After a --fresh reset the database holds only the automatic startup seeds. The
named UAT fixtures are a separate, explicit step — see .zj/UAT-v4.0.md §1.1:
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--fresh)       FRESH=1 ;;
    -d|--detach)      DETACH=1 ;;
    --down)           DOWN=1 ;;
    -n|--no-browser)  NO_BROWSER=1 ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; echo "Try --help." >&2; exit 2 ;;
  esac
  shift
done

# --- Repo root = parent of this script's directory ---------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FRONTEND_URL='http://localhost:5173'
API_DOCS_URL='http://localhost:8000/docs'
API_HEALTH_URL='http://localhost:8000/health/ready'

# --- Colours (suppressed when not a terminal) --------------------------------
if [[ -t 1 ]]; then
  CYAN=$'\033[36m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
  RED=$'\033[31m'; GREY=$'\033[90m'; RESET=$'\033[0m'
else
  CYAN=''; GREEN=''; YELLOW=''; RED=''; GREY=''; RESET=''
fi

say()  { printf '%s%s%s\n' "$1" "$2" "$RESET"; }
warn() { printf '%sWARNING: %s%s\n' "$YELLOW" "$1" "$RESET" >&2; }
die()  { printf '%sERROR: %s%s\n' "$RED" "$1" "$RESET" >&2; exit 1; }

# --- Resolve a container compose runner (podman preferred per compose docs) ---
if   command -v podman-compose >/dev/null 2>&1; then COMPOSER=(podman-compose)
elif command -v podman         >/dev/null 2>&1; then COMPOSER=(podman compose)
elif command -v docker         >/dev/null 2>&1; then COMPOSER=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSER=(docker-compose)
else
  die "No container compose tool found on PATH. Install Podman (recommended) or Docker."
fi

FILE_ARGS=(-f compose/compose.yml -f compose/compose.dev.yml)

compose() {
  say "$GREY" "  > ${COMPOSER[*]} ${FILE_ARGS[*]} $*"
  "${COMPOSER[@]}" "${FILE_ARGS[@]}" "$@"
}

# --- Banner ------------------------------------------------------------------
echo
say "$CYAN" '==================================================='
say "$CYAN" ' BizNiceSweets - UAT Launcher'
say "$CYAN" "  runner: ${COMPOSER[*]}"
say "$CYAN" '==================================================='

# --- Down mode: stop and exit ------------------------------------------------
if (( DOWN )); then
  say "$YELLOW" 'Stopping the stack...'
  if (( FRESH )); then compose down -v; else compose down; fi
  say "$GREEN" 'Stack stopped.'
  exit 0
fi

# --- Ensure BOTH env files exist (D-P5-10) -----------------------------------
# The stack reads two: ../.env for app secrets, ../.env.db for the database
# credentials. A missing .env.db leaves POSTGRES_PASSWORD empty, which an
# already-initialized volume tolerates but a FRESH one refuses outright
# ("Database is uninitialized and superuser password is not specified").
# That was defect U0; --fresh is exactly the path that trips it.
for pair in ".env:.env.example" ".env.db:.env.db.example"; do
  target="${pair%%:*}"
  template="${pair##*:}"
  if [[ ! -f "$target" ]]; then
    [[ -f "$template" ]] || die "$target and $template are both missing - cannot configure the stack."
    cp "$template" "$target"
    warn "$target was missing - created from $template. Set the real secrets in it before any non-local use."
  fi
done

# POSTGRES_PASSWORD lives in .env.db and nowhere else (D-P5-10).
if ! grep -Eq '^POSTGRES_PASSWORD=\S+' .env.db; then
  warn "POSTGRES_PASSWORD looks empty in .env.db - a fresh db volume will refuse to initialize (defect U0). Edit .env.db and set it."
fi

# A leftover POSTGRES_PASSWORD in .env is the PRE-D-P5-10 layout. podman-compose
# emits `--env-file ../.env --env-file ../.env.db` and the LATER file wins, so the
# stale .env value is not the one `api` ends up using - and an already-initialized
# volume still expects it. Two homes for one credential is exactly the drift
# D-P5-10 removed. Warn, never fail: it is the operator's file to fix.
if grep -Eq '^POSTGRES_PASSWORD=' .env; then
  warn ".env still defines POSTGRES_PASSWORD - it now lives ONLY in .env.db (D-P5-10). If your database volume predates the split, MOVE that line's value into .env.db and delete it from .env; see docs/deployment/local-dev.md 1.2."
fi

# --- Fresh: reset DB volume --------------------------------------------------
if (( FRESH )); then
  say "$YELLOW" 'Resetting database volume (down -v)...'
  compose down -v || warn "down -v reported a failure (continuing)"
fi

# --- URLs --------------------------------------------------------------------
echo
say "$GREEN" 'Once started, open:'
say "$GREEN" "  App (Vite) : $FRONTEND_URL"
say "$GREEN" "  API docs   : $API_DOCS_URL"
say "$GREEN" '  Log in with BNS_ADMIN_EMAIL / BNS_ADMIN_PASSWORD from .env.'
echo

# --- Detached mode: up -d, wait for health, open browser ---------------------
if (( DETACH )); then
  say "$YELLOW" 'Starting stack in background...'
  compose up -d

  say "$YELLOW" 'Waiting for the API to become healthy...'
  # Connection-reset errors here mean "not up yet" — the entrypoint is still
  # waiting on Postgres and running migrations. Give up after ~2 min.
  ready=0
  for _ in $(seq 60); do
    if curl -sf -o /dev/null --max-time 3 "$API_HEALTH_URL"; then ready=1; break; fi
    sleep 2
  done

  if (( ready )); then
    say "$GREEN" 'API is healthy.'
    if (( ! NO_BROWSER )); then
      if   command -v xdg-open >/dev/null 2>&1; then xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
      elif command -v open     >/dev/null 2>&1; then open "$FRONTEND_URL" >/dev/null 2>&1 &
      else warn "No xdg-open/open on PATH - browse to $FRONTEND_URL yourself."
      fi
    fi
  else
    warn "API did not report healthy within ~2 min. Check logs: ${COMPOSER[*]} ${FILE_ARGS[*]} logs -f"
  fi

  echo
  say "$GREEN" 'Stack is running in the background.'
  say "$GREEN" "  View logs : ./scripts/uat.sh  (foreground)  or  ${COMPOSER[*]} ${FILE_ARGS[*]} logs -f"
  say "$GREEN" '  Stop      : ./scripts/uat.sh --down'
  exit 0
fi

# --- Foreground mode (default): stream logs, Ctrl+C stops --------------------
say "$YELLOW" 'Starting stack (foreground). Press Ctrl+C to stop.'
echo
compose up
