# Review: v4.0 Phase 5 — Human click-through UAT (NFR-8), `4171605..1954b56`
Date: 2026-08-17

Scope reviewed as code, not prose: `backend/app/modules/syerp/service/inventory.py` (SC8),
`backend/app/modules/auth/service.py` (U1), `compose/compose.yml` + `.env*` (U0),
`Containerfile` (U2), `scripts/uat.sh`, `backend/scripts/seed_uat_fixtures.py`,
`backend/scripts/verify_gelato.py` (G), `frontend/src/components/AppShell.test.tsx`, and the
three new pin tests.

## Tripwires — both clean
- **No Alembic migration.** `git diff --stat 4171605..HEAD -- backend/alembic/` is empty; head
  is still `0017_syerp_ar_invoicing`.
- **No GL/JE posting change.** The only files changed under `backend/app/` are
  `syerp/service/inventory.py` and `auth/service.py`; no amount, account, or posting rule moved.

## Findings

### 1. [major] `seed_uat_fixtures.py` has no target-database guard, and the documented command cannot tell the prod database from the dev one
- **Where:** `backend/scripts/seed_uat_fixtures.py:254-269` (`build_dsn`), `:464` / `:566-579`
  (the fixture user), `:2455-2486` (opening-capital + manual JE), `Containerfile:63`
  (`COPY backend/ .` ships the script inside the runtime image).
- **Failure:** podman-compose derives its project name from the *directory of the first compose
  file* (`podman_compose.py:1509-1516`), which is `compose/` for **both**
  `podman-compose -f compose/compose.yml up -d` (prod, Task 35, `:8000`) and the dev overlay.
  Both therefore produce container `compose_api_1` **and volume `compose_pgdata`** — the same
  database. The runbook line reproduced in `scripts/uat.sh:48`, `:81`,
  `docs/deployment/local-dev.md` and `.zj/UAT-v4.0.md` §1.1 is
  `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py`, which
  silently targets whichever stack happens to be up. Run once against a self-hoster's live
  books and it posts, through the real services and in one shot: an opening-capital JE, a
  manual JE, an approved+received PO, a posted bill, a cash payment, an AR invoice and a
  customer receipt. Journal entries are append-only — none of that can be deleted, only
  reversed, in a product whose stated posture is "audit trail and traceability are
  first-class". It also creates an **active** login `uat-plum-user@example.invalid` with the
  password `uat-plum-user-pw`, which is committed to the repo (`.zj/QA.md:81`,
  `.zj/UAT-v4.0.md:147`, `docs/tasks/_completed/2026-08-17-chore-human-uat.md:203`) and is also
  echoed to stdout by the manifest (`:624`). The script greps clean for any environment gate:
  no `--yes`, no DEBUG check, no "refuse if the ledger already has non-`UAT-` rows".
- **Fix:** gate `run(seed=True)` behind an explicit opt-in that a copy-pasted command cannot
  satisfy by accident — e.g. require `BNS_ALLOW_UAT_SEED=1` in the container env (the dev
  overlay can set it; the prod compose file must not), and additionally refuse when the target
  database already contains journal entries whose memo is not a `UAT-` fixture. Cheapest
  partial mitigation if the gate is deferred: set `name:` in `compose/compose.dev.yml` so the
  dev stack gets a distinct project/volume, and stop shipping `scripts/seed_uat_fixtures.py` in
  the runtime image (`.dockerignore` it, as `backend/tests/` already is).

### 2. [major] SC8's bin probe does not check `active`, so a binned adjustment can book stock into an archived bin that GELATO itself refuses
- **Where:** `backend/app/modules/syerp/service/inventory.py:441-457`; compare
  `backend/app/modules/gelato/service/putaway.py:165-179`.
- **Failure:** `execute_putaway` validates a destination bin three ways — exists, belongs to the
  location, **and `active`** ("Destination bin {id} is archived", 422). The new probe is
  `SELECT 1 FROM gelato_bin WHERE id = :bin_id AND location_id = :location_id`, i.e. two of the
  three. Concrete case: archive bin `A-01` at location `L` (`POST /gelato/bins/{id}/archive` —
  bins are only ever soft-deleted, `bins.py:122-133`), then
  `POST /api/v1/syerp/inventory/adjustments {item, location: L, bin_id: A-01, qty_delta: +10}`.
  It is accepted. `list_bins` hides archived bins by default, so the SC6 bin picker and the
  bin-grain screens never show `A-01`; the location total includes the 10 while the visible
  per-bin split does not — which is precisely the "per-bin split goes wrong while the location
  total hides it" failure SC8's own docstring says it exists to close. Recovery requires
  hand-crafting a negative adjustment against a bin id the UI will not offer.
- **Fix:** add `AND active` to the probe and say so in the 422 detail, matching
  `execute_putaway`'s wording. Extend `verify_gelato.py` scenario (G) with a `(G5)`: archive
  `bin_g_b`, assert a `+5` adjustment naming it is 422 with zero ledger rows.

### 3. [major] The `.env` → `.env` + `.env.db` split breaks every already-deployed stack on upgrade, with no migration note
- **Where:** `compose/compose.yml:85-88` (`api` reads `../.env` then `../.env.db`),
  `.env.example` (POSTGRES_PASSWORD removed), `docs/deployment/local-dev.md:34-63`.
- **Failure:** an existing operator's `.env` still contains `POSTGRES_PASSWORD=<their real
  password>` (this change cannot rewrite an untracked file), and their volume is initialized
  with it. They pull, follow the new §1.2 verbatim — `cp .env.db.example .env.db` — and bring
  the stack up. `db` starts fine (an initialized PGDATA ignores `POSTGRES_PASSWORD`), but for
  `api` podman-compose emits `--env-file ../.env --env-file ../.env.db` in that order
  (`podman_compose.py:886-891`) and the later file wins, so `api` authenticates with the
  template's `changeme_in_production` and dies on
  `password authentication failed for user "app"`. Nothing in the docs, the compose comments,
  or `.env.db.example` tells them to move the value out of `.env` or that the *old* value is
  the one that must go into `.env.db`. Same class as U0 — a config change that only bites
  someone whose state predates it.
- **Fix:** add an upgrade note to `docs/deployment/local-dev.md` §1.2 ("if you already have a
  running stack: move the existing `POSTGRES_PASSWORD` line from `.env` into `.env.db` and
  delete it from `.env`"), and have `scripts/uat.sh` warn when `.env` still defines
  `POSTGRES_PASSWORD` — a second home is exactly the drift D-P5-10 set out to remove.

### 4. [major] `scripts/uat.ps1` was not ported to the env split, and the new docs claim it was
- **Where:** `docs/deployment/local-dev.md:136-140` vs `scripts/uat.ps1:101-113` (untouched in
  this range).
- **Failure:** the new §1.6 states "Both resolve a compose runner automatically … **and create
  `.env` / `.env.db` from their templates if either is missing**." `uat.ps1` does neither for
  `.env.db`: it creates only `.env`, then greps `^POSTGRES_PASSWORD=\S+` **in `.env`**, which
  D-P5-10 emptied — so it now warns on a *correct* setup, and its guard can no longer detect
  the condition it exists to detect. On a fresh Windows checkout `./scripts/uat.ps1 -Fresh`
  destroys the volume and then fails at `podman run --env-file ../.env.db` (no such file). The
  gap itself is logged in `.zj/BACKLOG.md:332-341`; what is *not* flagged is that this phase
  shipped documentation asserting the opposite, aimed at the one platform (pwsh/Windows) where
  it is false — and CLAUDE.md still names `./scripts/uat.ps1` as the full-dev-stack entry point.
- **Fix:** port the `scripts/uat.sh:154-167` block into `uat.ps1` (it is ~10 lines), or, until
  then, correct §1.6 to say the `.ps1` predates the split and requires `.env.db` to be copied
  by hand.

### 5. [minor] `uat.sh --detach` exits 0 when the stack never came up
- **Where:** `scripts/uat.sh:184-213`.
- **Failure:** `compose up -d` inherits the podman-compose trap this phase itself documented
  (`backend/tests/test_containerfile_config.py:35-38`: `podman-compose build` prints
  `exit code: 1` and returns 0). If the image build fails — exactly defect U2 — `up -d`
  returns 0, the health poll runs its full ~2 minutes, prints a `WARNING`, and the script
  `exit 0`s while telling the user "Stack is running in the background." Any wrapper that
  chains `./scripts/uat.sh --detach && <next step>` proceeds over a dead stack, and the
  warning scrolls off in the 60 lines of poll output.
- **Fix:** `exit 1` when `ready` is 0, and grep the `up -d` output for `Error: building at STEP`
  before starting the poll.

### 6. [minor] `--manifest`, documented as read-only and safe on any database, raises on an unseeded or unprofitable one
- **Where:** `backend/scripts/seed_uat_fixtures.py:2783`.
- **Failure:** `_expect("balance sheet reports non-negative total assets", bs.total_assets > 0,
  True)` is the one reporter assertion not gated by an `if … is not None` presence check
  (contrast `:2673-2676`, `:2689-2692`, `:2703-2704`, `:955-956`). On a freshly-migrated volume
  carrying only the startup seeds, `total_assets` is `0`, so
  `python scripts/seed_uat_fixtures.py --manifest` — the command the runbook offers for
  re-reading literals mid click-through — dies with `RuntimeError: oracle mismatch`, directly
  contradicting the module docstring's "an unseeded database honestly reports an empty
  manifest". `bs` is a whole-ledger figure, so the same assertion fires on any real database
  whose assets are legitimately non-positive.
- **Fix:** run the balance-sheet/trial-balance oracles only when the layer's own fixtures were
  found (e.g. guard on `_bill_by_ref(AP_POSTED_BILL_REF) is not None`), or skip them entirely
  in `--manifest` mode.

### 7. [minor] `.dockerignore` does not exclude the newly-introduced `.env.db`
- **Where:** `.dockerignore:19-22` (`.env`, `*.env`) vs the new `.env.db`.
- **Failure:** neither pattern matches `.env.db` (`.env` is an exact match; `*.env` matches
  names *ending* in `.env`). Today no `COPY` picks it up, so nothing leaks into a layer — but
  the file's stated purpose in that block is "Secrets must never be baked into the image
  (T-01-10)", and the newest secret file is the one it does not cover. A future `COPY . .`, or
  any build run with a tool that snapshots context, silently bakes the database password in.
- **Fix:** add `.env.db` (or `.env*` with a `!.env*.example` negation) to `.dockerignore`.

## Questions

- **`legacy-peer-deps=true` as a build-blocking dependency (U2).** The fix is correct and
  minimal — `COPY frontend/package*.json frontend/.npmrc ./` copies exactly one extra tracked,
  secret-free file, and `test_containerfile_config.py` pins both the ordering and the
  non-duplication. But the image now cannot be built at all unless npm ignores *every* peer
  range in the tree, not just `eslint-plugin-react-hooks@5`'s. The next dependency bump that
  introduces a genuinely incompatible peer will install cleanly and fail at `npm run build` or
  at runtime instead. Is pinning `eslint-plugin-react-hooks` to a v6 release (or an
  `overrides.peerDependencies` entry scoped to that one package) on the roadmap, so the escape
  hatch stops covering the whole tree?
- **`POSTGRES_PASSWORD` is interpolated into a DSN without URL-encoding** —
  `backend/app/core/config.py:52-56` and `seed_uat_fixtures.py:269`. Pre-existing, but
  `.env.db.example` now tells a first-time self-hoster "set a strong, unique password" in a
  brand-new file; a password containing `@`, `/`, `:` or `#` yields an opaque asyncpg parse
  failure on first boot. Worth a one-line warning in `.env.db.example`, or `quote_plus()` on
  the password?
- **The commented module-service templates at `compose/compose.yml:111-151` still carry
  `env_file: ../.env` alone.** Whoever uncomments `gelato-worker` gets the app secrets and no
  database credentials — the drift D-P5-10 was written to prevent, pre-seeded into the file.
  Intentional, or should those templates be updated to the two-file form now?

## Verified sound (no finding)

- **SC8 probe mechanics.** No gelato import was added (only `text` from `sqlalchemy`), so
  D-P12a-3 holds. The SQL is fully parameterized (`:bin_id`, `:location_id`) — no injection
  surface. The `bin_id is None` path is untouched, so D-P4-1's unbinned pool and the SC6
  zero-pool fixtures are intact. The probe takes no lock and runs *before* the
  `SELECT … FOR UPDATE` on the item-master row, which cannot change lock ordering (NFR-7) — and
  because `location_id` is immutable on a bin (`BinUpdate` exposes only `description`/`active`;
  `bins.py:103-119`) and bins are never hard-deleted, there is no TOCTOU between the probe and
  the insert.
- **verify_gelato scenario (G) goes RED for the right reason.** In G1 the delta is `+5` at a
  location holding 10, so the location floor passes (`15 >= 0`) and D-P4-6 gives positives no
  pool floor; `bin_g_a` genuinely exists so the FK is satisfied. The membership probe is the
  only guard that can reject it, and `_ledger_rows` before/after is a true row-count oracle.
  The job runs in CI (`.github/workflows/ci.yml:155-163`).
- **U1 narrowing is driver-correct.** `ix_users_email` is the real index name
  (`alembic/versions/0002_add_auth_tables.py:65`); `exc.orig.__cause__.constraint_name` is
  where asyncpg's `UniqueViolationError` puts it under SQLAlchemy's double wrap, with a string
  fallback that still requires the name explicitly. `await db.rollback()` precedes the branch,
  so the session is not left poisoned, and the pre-check's exact-match `User.email == email`
  matches the DB index's case sensitivity — no cased-duplicate behaviour change. The router
  writes its audit row only after `create_user` returns, so no orphan audit entry.
- **U0 compose fix and its pin.** `api` reads both files, so its DSN cannot drift from what
  `db` was initialized with (aside from finding 3's upgrade path); `.env.db` is gitignored and
  `.env.db.example` is tracked and asserted tracked by the test. The `$$POSTGRES_USER`
  healthcheck escape renders correctly under podman-compose 1.0.6 (verified with
  `podman-compose config`: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`).
  `test_compose_config.py` pins behaviour, not text: it strips comments first, then asserts on
  the parsed `env_file` values and the absence of a `POSTGRES_PASSWORD: ${…}` line.
- **`AppShell.test.tsx` is not vacuous.** `'excludes a disabled module even from an admin'`
  fails if the wildcard is hoisted above the `enabled` check;
  `'preserves the input order of the modules it keeps'` pins ordering;
  `'does not treat a write permission as read access'` pins the `:read` key. Types match
  `ModuleRecord`/`AuthUser` exactly.
- **Seed idempotency keys are stable.** POs are keyed on `notes`, and there is no PO-header
  PATCH endpoint, so a human click-through cannot invalidate the key; bills/payments/JEs key on
  `vendor_invoice_ref` / `reference` / `memo`; every builder branch is skip-if-present and the
  archive step runs only on the creating run.
