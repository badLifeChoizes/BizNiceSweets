# Local CI — what replaced GitHub Actions

This repository is public, so its Actions minutes were free. It was retired anyway, because the
owner is moving every project off hosted CI onto podman and real machines. Nothing about the
checks was weakened: every job the workflow ran has a local equivalent below, and the two
properties that made CI worth having — a cold machine and a pinned toolchain — are preserved
by containers rather than by a runner.

## Run it

```bash
scripts/local-ci/gate.sh                      # every retired CI job except the image build
scripts/local-ci/gate.sh --only backend-tests # one job
scripts/local-ci/clean-room.sh                # uncached image build + boot probe
```

The gate runs automatically on `git push` via `.githooks/pre-push`; `ZJ_SKIP_GATE=1` bypasses it.

## What maps to what

| Retired job | Replacement | Runs in |
|---|---|---|
| `backend-lint` | `gate.sh --only backend-lint` | `python:3.13` |
| `backend-tests` | `gate.sh --only backend-tests` | `python:3.13` + `postgres:17` |
| `verify-scripts` (+ UAT seed idempotency) | `gate.sh --only verify-scripts` | `python:3.13` + `postgres:17` |
| `verify-scripts-api` | `gate.sh --only verify-scripts-api` | `python:3.13` + `postgres:17` |
| `frontend` | `gate.sh --only frontend` | `node:22` |
| `container-image` | **`clean-room.sh`** | podman build + `postgres:17` |

## Why the backend runs in a container and not in `backend/.venv`

The archived workflow pinned **Python 3.13**. This machine carries **3.12**. A gate that tests a
different interpreter than the one the project ships against is reporting on something else, so
the backend jobs run in `python:3.13` and reach Postgres by container name on a podman network —
the local analogue of the workflow's `services:` block resolving on localhost.

A named volume caches pip wheels so a repeat run is not a fresh download. It caches wheels only,
never the project, so it cannot mask a dependency change.

## Why the image build is a separate script

Defect U2 — the API image could not be built at all — hid for five phases because nothing ever
cold-built it, and a warm layer cache is what hid it. `clean-room.sh` builds with `--no-cache`
from `git archive HEAD`, so neither a layer cache nor an untracked file can make a clean build a
warm one. It keeps the log assertion too: `podman build` returns a trustworthy status, unlike the
`podman-compose build` that printed `exit code: 1` and returned 0.

Run it before a release and after any change to `Containerfile`, `entrypoint.sh`, `compose.yml`,
or the `.env*` templates.

## Arming the hook on a fresh clone

```bash
git config core.hooksPath .githooks
```
