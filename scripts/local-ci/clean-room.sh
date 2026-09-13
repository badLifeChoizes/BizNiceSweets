#!/usr/bin/env bash
# scripts/local-ci/clean-room.sh
# ABOUTME: Builds the API image from the Containerfile uncached and boots it against Postgres.
# ABOUTME: This is the retired container-image job — the artifact a self-hoster actually gets.
#
# Usage: scripts/local-ci/clean-room.sh [--ref <git-ref>]
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
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) shift; REF="${1:?--ref needs a value}" ;;
    -h|--help) sed -n '1,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

need_podman
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
podman run -d --name "$API_NAME" --network "$NET" \
  --env-file .env --env-file .env.db \
  -e POSTGRES_HOST="$PG_NAME" -e POSTGRES_PORT=5432 \
  -p 127.0.0.1:8000:8000 \
  biznicesweets-api:local-ci >/dev/null

for _ in $(seq 1 60); do
  # /health/ready returns 503 while the DB is unreachable, so a passing curl proves migrations
  # ran and the pool connects — not merely that a process started.
  if curl -fsS http://127.0.0.1:8000/health/ready; then
    echo; echo "the built image booted and reports ready"
    exit 0
  fi
  sleep 2
done

echo "the image built but never came up — every static config assertion can still pass while" >&2
echo "entrypoint.sh or the .env/.env.db wiring is broken. Container log follows." >&2
podman logs "$API_NAME" >&2 || true
exit 1
