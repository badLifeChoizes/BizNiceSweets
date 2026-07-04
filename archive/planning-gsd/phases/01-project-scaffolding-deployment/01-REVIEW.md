---
phase: 01-project-scaffolding-deployment
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 49
files_reviewed_list:
  - .dockerignore
  - .env.example
  - .gitignore
  - Containerfile
  - backend/alembic.ini
  - backend/alembic/env.py
  - backend/alembic/script.py.mako
  - backend/alembic/versions/0001_initial_baseline.py
  - backend/app/__init__.py
  - backend/app/api/__init__.py
  - backend/app/api/health.py
  - backend/app/core/__init__.py
  - backend/app/core/base.py
  - backend/app/core/config.py
  - backend/app/core/db.py
  - backend/app/core/models.py
  - backend/app/core/registry.py
  - backend/app/core/seed.py
  - backend/app/main.py
  - backend/app/modules/__init__.py
  - backend/app/modules/syerp/__init__.py
  - backend/app/modules/syerp/models.py
  - backend/app/modules/syerp/router.py
  - backend/app/modules/syerp/schemas.py
  - backend/app/modules/syerp/service.py
  - backend/entrypoint.sh
  - backend/pyproject.toml
  - backend/requirements-dev.txt
  - backend/requirements.txt
  - backend/tests/__init__.py
  - backend/tests/conftest.py
  - backend/tests/test_health.py
  - backend/tests/test_migrations.py
  - compose/compose.dev.yml
  - compose/compose.yml
  - docs/deployment/local-dev.md
  - frontend/.eslintrc.cjs
  - frontend/.prettierrc.json
  - frontend/components.json
  - frontend/index.html
  - frontend/package.json
  - frontend/src/App.tsx
  - frontend/src/index.css
  - frontend/src/lib/queryClient.ts
  - frontend/src/lib/utils.ts
  - frontend/src/main.tsx
  - frontend/src/routes/Landing.tsx
  - frontend/src/vite-env.d.ts
  - frontend/tsconfig.app.json
  - frontend/tsconfig.json
  - frontend/tsconfig.node.json
  - frontend/vite.config.ts
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-06-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 49
**Status:** issues_found

## Summary

Phase 1 scaffolding for the FastAPI + React modular monolith. The security posture
declared in the threat model is largely honored: the container runs as a non-root
user, no secrets are baked into the image, the DB has no `ports:` mapping (not
host-exposed), the readiness probe uses a parameterless query and returns a generic
503, and `POSTGRES_PASSWORD` is typed as `SecretStr`. No Critical defects were found —
appropriate for a skeleton with no business logic, no user input handling, and empty
table/router stubs.

The findings are concentrated in two areas: (1) **tooling that will fail at runtime**
— the ESLint setup is internally inconsistent with the pinned ESLint major version, so
`npm run lint` cannot succeed as written; and (2) **runtime/routing behavior gaps**
that are harmless today but will produce confusing results once real API routes exist
(SPA fallback masking API 404s). Several Info items concern pinned dependency versions
that should be verified to actually exist, and minor consistency issues.

## Warnings

### WR-01: ESLint config is incompatible with the pinned ESLint major version (lint is broken)

**File:** `frontend/.eslintrc.cjs:1-15`, `frontend/package.json:10,27`
**Issue:** `package.json` pins `eslint@10.5.0` and the `lint` script is
`eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`. ESLint 9
removed automatic loading of the legacy `.eslintrc.*` (eslintrc) format and made flat
config (`eslint.config.js`) the default; ESLint 10 continues that. The `--ext` flag was
also removed in the flat-config CLI. As written, `npm run lint` will either error out
("could not find config / unknown option --ext") or silently ignore the `.eslintrc.cjs`
file, so linting does not actually run. The legacy `extends: ['eslint:recommended',
'plugin:@typescript-eslint/recommended']` strings are likewise not valid flat-config
entries. This defeats the only automated quality gate in the frontend.
**Fix:** Migrate to flat config. Create `frontend/eslint.config.js`:
```js
import js from '@eslint/js'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
)
```
Then change the script to `"lint": "eslint . --report-unused-disable-directives --max-warnings 0"`
and delete `.eslintrc.cjs`. (`@eslint/js` must be added to devDependencies.)

### WR-02: SPA catch-all returns index.html for unknown /api routes instead of a JSON 404

**File:** `backend/app/main.py:33-42,86-91`
**Issue:** `SPAStaticFiles` is mounted at `/` last and rewrites any 404 to
`index.html`. Because the mount is a catch-all, a request to an unregistered API path
(e.g. a typo'd `/api/v1/syerp/vendorz`, or any future route that 404s) falls through to
this mount and returns the SPA HTML with a 200 status. API clients then receive
`text/html` and a success code for what should be a 404 JSON error. Harmless in Phase 1
(no real routes), but it will silently mask routing bugs and break API error handling
the moment Phase 4 adds endpoints.
**Fix:** Only apply the index.html fallback for non-API paths, and preserve the 404
otherwise:
```python
async def get_response(self, path: str, scope):  # type: ignore[override]
    try:
        return await super().get_response(path, scope)
    except StarletteHTTPException as ex:
        if ex.status_code == 404 and not path.startswith(("api/", "health/")):
            return await super().get_response("index.html", scope)
        raise
```
Alternatively, scope the SPA mount so it never sees `/api` or `/health` traffic.

### WR-03: .env.example ships a usable default password that can reach production

**File:** `.env.example:19`, `docs/deployment/local-dev.md:115,137`
**Issue:** `POSTGRES_PASSWORD=changeme_in_production` is a real, working value, not an
empty placeholder. The deployment doc additionally hardcodes this exact password in two
copy-paste command blocks (the native `podman run` and the backend `.env` snippet). The
threat model says "no baked secrets / operator must supply a strong password," but the
path of least resistance is for an operator to `cp .env.example .env` and run — the
stack will start successfully with the weak password and give no signal that it is
insecure. Nothing forces a change.
**Fix:** Make the default non-functional so a forgotten override fails loudly, e.g.
`POSTGRES_PASSWORD=` (empty) — `Settings.postgres_password` is required and the DB will
refuse an empty password — or add a startup assertion that rejects the literal
`changeme_in_production`. Replace the hardcoded password in `local-dev.md` examples with
`<your-password>` placeholders.

### WR-04: Default postgres image runs as root inside the db container, partially undercutting the non-root posture

**File:** `compose/compose.yml:31-46`
**Issue:** The `api` service is hardened to run as `appuser` (good), but the `db`
service uses `postgres:17-alpine` with no `user:` override, so PostgreSQL's entrypoint
runs initialization as root before dropping to the `postgres` user. The threat model
emphasizes a non-root container posture; the db container is the more sensitive one
(holds all data) and is left at defaults. There is also no `read_only`, `cap_drop`, or
`security_opt: no-new-privileges` on either service.
**Fix:** At minimum add `security_opt: ["no-new-privileges:true"]` to both services and
consider `user:` / `cap_drop: [ALL]` hardening on `api`. Document the residual root in
the db init phase if it is accepted intentionally.

### WR-05: Liveness/readiness queries are unbounded and unauthenticated with no timeout

**File:** `backend/app/api/health.py:26-34`, `backend/app/core/db.py:17`
**Issue:** `/health/ready` opens a DB session and runs `SELECT 1` with no statement or
connection timeout configured on the async engine. If Postgres is reachable but hung
(e.g. connection accepted, query never returns), the readiness handler blocks
indefinitely rather than returning 503, which defeats the purpose of a readiness probe
and can pile up requests. The endpoint is also unauthenticated (acceptable for probes,
but it confirms DB reachability to any caller).
**Fix:** Add a timeout to the readiness check, e.g. wrap the execute in
`asyncio.wait_for(..., timeout=2)` (returning 503 on `TimeoutError`), and/or set
`connect_args={"timeout": 2, "command_timeout": 2}` on `create_async_engine` for asyncpg.

## Info

### IN-01: Pinned dependency versions should be verified to exist

**File:** `backend/requirements.txt:1-9`, `frontend/package.json:12-33`
**Issue:** Several pins are unusually far ahead (e.g. `fastapi==0.138.0`,
`vite@8.1.0`, `typescript@6.0.3`, `eslint@10.5.0`, `react@19.2.7`,
`@types/node@^26.0.0`, `node:22-slim`). If any of these versions does not actually
publish, `pip install` / `npm ci` will fail the build hard. Exact pins are good for
reproducibility but only if resolvable.
**Fix:** Run `npm ci` and `pip install -r requirements.txt` in CI to confirm every pin
resolves; correct any that do not exist.

### IN-02: Inconsistent version-pinning strategy in package.json

**File:** `frontend/package.json:12-33`
**Issue:** Mix of exact pins (`react`, `vite`, `typescript`) and caret ranges
(`clsx ^2.1.1`, `tailwind-merge ^3.6.0`, `@types/node ^26.0.0`). Caret ranges allow
silent minor/patch drift between `npm install` runs, which conflicts with the
reproducible-deploy goal in CLAUDE.md.
**Fix:** Pick one strategy. For a self-hosted reproducible build, pin all exact and rely
on the lockfile, or use ranges uniformly and commit `package-lock.json`.

### IN-03: alembic upgrade head runs on every container start with no advisory lock

**File:** `backend/entrypoint.sh:22-24`, `compose/compose.yml`
**Issue:** The entrypoint runs migrations unconditionally on startup. Single-instance is
fine today, but as soon as more than one `api` replica starts concurrently (or a restart
loop overlaps), two `alembic upgrade head` runs can race. Alembic does not take a lock by
default. Not a Phase 1 bug (one replica), but worth noting before scaling.
**Fix:** When multi-instance becomes possible, gate migrations behind a single
init/migrate job or wrap in a Postgres advisory lock.

### IN-04: vite.config.ts proxy target is container-only; native dev silently misroutes

**File:** `frontend/vite.config.ts:19-26`, `docs/deployment/local-dev.md:155-158`
**Issue:** The proxy hardcodes `http://api:8000`, which only resolves inside the compose
network. For native Path-2 dev, `api` does not resolve and `/api`//`/health` calls fail;
the doc acknowledges this and tells the developer to hand-edit the file. `VITE_API_BASE_URL`
is set in the dev compose env but the config never reads it, so the documented env-var
override does not actually work.
**Fix:** Read the env var: `const apiTarget = process.env.VITE_API_BASE_URL ?? 'http://api:8000'`
and use `apiTarget` for both proxy entries, so native dev works by setting the var.

### IN-05: Landing renders raw error.message to the DOM

**File:** `frontend/src/routes/Landing.tsx:126-128`
**Issue:** On a failed health fetch the component renders `{error.message}` directly.
React escapes it, so this is not an XSS vector, but surfacing raw fetch error strings to
end users is a minor information-exposure / UX smell that tends to leak internals as the
app grows.
**Fix:** Map errors to a friendly message; keep the raw text to console/log only.

### IN-06: `from typing import Sequence, Union` instead of modern syntax in migration scaffolding

**File:** `backend/alembic/versions/0001_initial_baseline.py:14`, `backend/alembic/script.py.mako:8`
**Issue:** Ruff is configured with `UP` (pyupgrade) and `target-version = py313`, which
would flag `typing.Union`/`typing.Sequence` in favor of `X | Y` / `collections.abc`.
These files use the legacy forms (the mako template propagates it to every future
migration). Minor; alembic-generated files are sometimes excluded from lint, but the
template will keep emitting non-conforming code.
**Fix:** Update `script.py.mako` and `0001` to `from collections.abc import Sequence`
and `str | None`, or add an explicit ruff per-file-ignore for `alembic/`.

---

_Reviewed: 2026-06-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
