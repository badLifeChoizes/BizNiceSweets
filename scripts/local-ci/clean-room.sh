#!/usr/bin/env bash
# scripts/local-ci/clean-room.sh
# ABOUTME: Builds the API image from the Containerfile uncached and boots it against Postgres.
# ABOUTME: This is the retired container-image job — the artifact a self-hoster actually gets.
#
# Usage: scripts/local-ci/clean-room.sh [--ref <git-ref>] [--port <host-port>]
#
# WHY uncached, and WHY it is not folded into gate.sh: defect U2 — the API image could not be
# built AT ALL — hid for five phases precisely because no automated process ever cold-built it,
# and a warm layer cache is exactly what hid it. `--no-cache` is the check, not an optimisation
# left switched off.
#
# WHY `podman build` directly rather than `podman-compose build`: the compose wrapper printed
# `exit code: 1` and still RETURNED 0, which is how U2 walked past a `build && next-step` chain.
# A direct build returns a status worth reading, and the log assertion below is the belt to it.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
. scripts/local-ci/lib.sh

REF="HEAD"
# Not 8000: that is where ./scripts/uat.sh's dev stack lives, and a busy port used to turn this
# check green against the wrong container.
API_PORT="${API_PORT:-8097}"
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) shift; REF="${1:?--ref needs a value}" ;;
    --port) shift; API_PORT="${1:?--port needs a value}" ;;
    -h|--help) sed -n '1,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

need_podman

# WHY the port is asserted free, and not 8000: a dev stack from ./scripts/uat.sh publishes
# compose_api_1 on 8000 for weeks at a time. Publishing onto an occupied port makes `podman run`
# fail with `rootlessport listen tcp: bind: address already in use` — and then a probe of that
# port is answered by the OTHER container, so this script reported a green boot for an image it
# had never started. Same silent-failure class as U2, in U2's own replacement.
if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE "[:.]${API_PORT}[[:space:]]"; then
  echo "port ${API_PORT} is already in use — refusing to probe a port somebody else may answer." >&2
  echo "Stop what holds it (podman ps) or re-run with --port <free-port>." >&2
  exit 1
fi

SHA="$(git rev-parse --short "$REF")"
WORK="$(mktemp -d)"
API_NAME=bns-local-ci-api
cleanup() { podman rm -f "$API_NAME" >/dev/null 2>&1 || true; pg_down; rm -rf "$WORK"; }
trap cleanup EXIT

# The tree that gets built is what is committed at the ref — never the working directory, whose
# untracked files and build output would make a "clean" build a warm one wearing a container.
echo "clean room: $REF ($SHA)"
git archive --format=tar "$REF" | tar -x -C "$WORK"
cd "$WORK"

echo "--- building the API image from Containerfile (uncached)"
set -o pipefail
podman build --no-cache -f Containerfile -t biznicesweets-api:local-ci . 2>&1 | tee "$WORK/image-build.log"
BUILD_RC=${PIPESTATUS[0]}

# buildah/podman prints `Error: building at STEP`; BuildKit prints `failed to solve`. Neither
# may appear in a log that a `build && next-step` chain would walk straight over.
if grep -nE "Error: building at STEP|failed to solve" "$WORK/image-build.log"; then
  echo "the image build log records a failed step — never trust a build wrapper's exit status alone" >&2
  exit 1
fi
[ "$BUILD_RC" -eq 0 ] || { echo "podman build exited $BUILD_RC" >&2; exit 1; }
podman image inspect biznicesweets-api:local-ci >/dev/null || { echo "the image tag does not exist after a clean build" >&2; exit 1; }
echo "image built from Containerfile, log clean"

# Config the way a real deploy gets it (D-P5-10): app secrets from .env, database credentials
# from .env.db, both built from the tracked templates — so a template that stops carrying a key
# the app needs fails here, on the runbook's own first two commands.
sed -e 's|^JWT_SECRET=.*|JWT_SECRET=ci_test_jwt_secret_at_least_32_chars_long|' \
    -e 's|^BNS_ADMIN_PASSWORD=.*|BNS_ADMIN_PASSWORD=ci_test_pw|' .env.example > .env
sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASSWORD}|" .env.db.example > .env.db
grep -q "^POSTGRES_PASSWORD=${PG_PASSWORD}$" .env.db || { echo "the sed did not hit .env.db" >&2; exit 1; }

echo "--- booting the image we just built"
pg_up || exit 1

# POSTGRES_HOST is overridden because .env ships the compose service name `db`, which is not
# this network's name for it — the same override compose.yml makes in its `environment:` block.
if ! podman run -d --name "$API_NAME" --network "$NET" \
  --env-file .env --env-file .env.db \
  -e POSTGRES_HOST="$PG_NAME" -e POSTGRES_PORT=5432 \
  -p "127.0.0.1:${API_PORT}:8000" \
  biznicesweets-api:local-ci >/dev/null; then
  echo "podman run failed — the image built but could not be started at all" >&2
  exit 1
fi

for _ in $(seq 1 60); do
  # A probe is only evidence if OUR container is the thing that could answer it. If it has
  # exited, stop now and print why rather than polling a port for two minutes.
  if [ "$(podman inspect -f '{{.State.Running}}' "$API_NAME" 2>/dev/null)" != "true" ]; then
    echo "the container exited while coming up. Log follows." >&2
    podman logs "$API_NAME" >&2 || true
    exit 1
  fi
  # /health/ready returns 503 while the DB is unreachable, so a passing curl proves migrations
  # ran and the pool connects — not merely that a process started.
  if curl -fsS "http://127.0.0.1:${API_PORT}/health/ready"; then
    echo; echo "the built image booted and reports ready on ${API_PORT}"
    exit 0
  fi
  sleep 2
done

echo "the image built but never came up — every static config assertion can still pass while" >&2
echo "entrypoint.sh or the .env/.env.db wiring is broken. Container log follows." >&2
podman logs "$API_NAME" >&2 || true
exit 1
