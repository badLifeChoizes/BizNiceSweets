# Plan: Phase 05 — Human click-through UAT (NFR-8)
Goal: Every shipped UI flow — CORE, PLUM, SYERP (inventory/purchasing/GL/AP/AR/reports), MOUSSE, CRUMB, GELATO — has passed a documented human click-through against the hardened v4.0 stack, with every defect fixed (blocker/major, pinned by an automated test) or homed to BACKLOG with an ID.
Status: draft — owner decisions D-P5-1..8 settled at `/zj:plan 5` (2026-07-26); next `/zj:build 5`
Closes: SRD **NFR-8** (§800) and the final clause of the v4.0 DoD. **Final phase of milestone v4.0.**

## Success criteria  (ROADMAP v4.0 Phase 5 row incl. the Phase-4-retro amendment; SRD NFR-8 lines 800–809)

- **SC1 (one consolidated checklist):** `.zj/UAT-v4.0.md` exists as the single checklist. Every shipped UI flow across CORE / PLUM / SYERP / MOUSSE / CRUMB / GELATO has a numbered check carrying (a) the named fixture it uses, (b) what the machine already proved **with the citation**, (c) the **human-only residue**, (d) a status cell. `.zj/UAT-v1.0.md` and `.zj/UAT-v2.0.md` each gain a pointer line to it and stay as history.
- **SC2 (fixtures, fresh volume):** `backend/scripts/seed_uat_fixtures.py` idempotently builds the whole named dataset on a **genuinely fresh volume**; a second run changes nothing (proven — stable row counts / codes). Every expected value quoted anywhere in the checklist is derived from it and stated as a **literal**.
- **SC3 (machine pre-flight):** a record maps each check to the existing `verify_*`/pytest/vitest assertion that proves its backend (or a new probe), so **no check asks the human to confirm something a machine could have confirmed**. Uncovered surfaces get a probe or an explicit `machine-unproven` mark.
- **SC4 (no todo rows):** every check in `.zj/UAT-v4.0.md` has a recorded result — pass or a defect ID. **Zero `todo` rows at close.**
- **SC5 (defects homed):** every defect is either fixed in-phase **with a pinning automated test that fails on revert** (blocker/major) or has a BACKLOG entry with a defect ID (minor); the checklist links each defect to its fix commit or backlog entry.
- **SC6 (Phase-4 bin pickers, incl. GELATO-off):** the three Phase-4 pickers — `StockAdjustDialog`, `StockTransferDialog` from-bin, `IssueComponentsDialog` per-line — are human-driven, **including the GELATO-off degraded path**. v4.0's only new UI surface; unit-tested, never human-driven (ROADMAP Phase-5 amendment, 2026-07-25).
- **SC7 (prod-stack deploy smoke, fresh volume):** `podman-compose -f compose/compose.yml up -d` with a **rebuilt image** and rebuilt `frontend/dist`, served at **:8000** on a fresh volume — login + one write per enabled suite succeeds. Closes BACKLOG p1 "Rebuild `frontend/dist` + the API container image".
- **SC8 (positive-adjust bin membership):** `post_adjustment` rejects a non-null `bin_id` that does not exist or does not belong to `location_id` — a cheap **raw-SQL** existence+membership check against `gelato_bin(id, location_id)`, **no gelato model import** (D-P12a-3's no-imports rule holds), 422 on mismatch, pinned by a new `verify_gelato.py` scenario. The p2 BACKLOG item is checked off.
- **SC9 (bookkeeping):** SRD NFR-8 → done/verified with an evidence stamp; `docs/features/requirements-progress.md` NFR-8 row added; ROADMAP Phase 5 row updated; the p1 BACKLOG UAT item checked off.

## Context

### The surface to be covered (measured, not assumed)

`frontend/src/App.tsx` declares **47 `path=` routes** = **41 addressable screens** (5 suite-index redirects + 1 catch-all are not screens). Dialog/sheet/editor components under `frontend/src/routes/*/components/`: **36** non-test files (`ls frontend/src/routes/*/components/*{Dialog,Sheet,Editor,Form}.tsx | grep -v '\.test\.'`).

| Group | Screens | Notes |
|---|---|---|
| CORE | Login, Home, Settings, Settings→Modules, Users | D-P5-8 — in scope, ~6 checks |
| PLUM | PartsList, PartDetail, ImportExport | PartDetail (1,345 lines) hosts BOM tree/flat, Where-Used, AVL, Cost & Margin, revisions |
| SYERP inventory | InventoryItems, InventoryItemDetail, StockLocations | + StockAdjustDialog, StockTransferDialog (SC6) |
| SYERP purchasing | PurchaseOrders, PurchaseOrderCreate, PurchaseOrderDetail | + ReceiveLineDialog |
| SYERP GL | GLAccounts, JournalEntries, AccountRegister | |
| SYERP AP | Bills, BillDetail, ApAging | + BillCreateDialog, PayBillDialog |
| SYERP AR | Invoices, InvoiceDetail, Receipts, ArAging | + InvoiceCreateDialog, RecordReceiptDialog |
| SYERP reports | FinancialReports | TB / BS / IS |
| SYERP partners | Vendors, Customers | + PartnerSheet, PartnerArchiveDialog |
| MOUSSE | WorkOrders, WorkOrderDetail | + WorkOrderCreateDialog, IssueComponentsDialog (SC6), CompleteWorkOrderDialog |
| CRUMB | Leads, LeadDetail, Pipeline, OpportunityDetail, Quotes, QuoteDetail, SalesOrders, SalesOrderDetail, Communications | 9 screens |
| GELATO | Bins, Putaway, Fulfillment | pick → pack → ship |

### What the machine already proves (the pre-flight's raw material — prefer citation over new code)

- **24 `backend/scripts/verify_*.py`** — 15 non-API + 9 `*_api.py`. The non-API 15 auto-run in CI (`.github/workflows/ci.yml:155-164`, glob `scripts/verify_*.py` minus `*_api.py`).
- **`backend/tests/`** — 51 files, **232 passed / 0 skipped**, incl. `tests/core/test_modules.py`, `tests/core/test_settings.py`, `tests/auth/test_login.py|test_refresh.py|test_refresh_rotation.py|test_rbac.py|test_user_admin.py` — **CORE's API layer is already covered**; the human residue there is FE wiring, not behavior.
- **`frontend/src/**/*.test.tsx`** — **44 files / 139 tests**.

**Measured FE coverage holes (weight the human checks here):** seven route screens have **no colocated vitest** — `routes/Home.tsx`, `routes/admin/Settings.tsx`, `routes/admin/Modules.tsx`, `routes/syerp/GLAccounts.tsx`, `routes/crumb/LeadDetail.tsx`, `routes/crumb/OpportunityDetail.tsx`, `routes/crumb/Quotes.tsx` — plus `getVisibleModules` in `frontend/src/components/AppShell.tsx:37-46` (the RBAC/enabled nav filter). These are the genuinely `machine-unproven` surfaces.

### Environment facts (verified against the tree — do not re-derive)

- Dev overlay (`compose/compose.dev.yml`) bind-mounts `../backend:/app`, which **shadows** the image's `/app/frontend/dist`; `backend/app/main.py:118-124` only mounts the SPA when the dir exists — so under the dev overlay **:8000 serves no SPA**. That is why the click-through runs on **:5173** (D-P5-2 / D-P7-1) and why SC7's smoke must use `compose/compose.yml` **alone**.
- The prod image builds the SPA itself (`Containerfile` stage `frontend-builder` runs `npm run build`), so SC7 needs `podman-compose -f compose/compose.yml build api`, not just a host `npm run build`. The host `frontend/dist` is rebuilt too (the other half of the backlog item, and `npm run build` is part of the FE gate anyway).
- The backend bind mount means **edits to `backend/scripts/*.py` are live in the container with no rebuild** — the seed script can be iterated in seconds.
- Verified commands: dev `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`; fresh volume `podman-compose -f compose/compose.yml down -v` first; in-container script `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`; in-container pytest — **THIS COMMAND DOES NOT WORK, corrected at Task 8a.** `pytest` is absent from the
api image (`Containerfile:52-53` installs `requirements.txt` only, never `requirements-dev.txt`), so
`python -m pytest` gives `No module named pytest`; the dev overlay's bind-mounted
`/app/.venv/bin/pytest` exists but its shebang and `python` symlink point at host paths absent in the
container. **Run pytest from the host venv against a reachable Postgres instead** (the compose `db` is
deliberately not port-mapped, so use a throwaway `postgres:17-alpine` on a spare port — the same shape
as CI's `postgres` service). Third firing of the Phase-3 keeper: a recipe derived by reading is not a
runnable recipe; `backend/.venv/bin/ruff check .` from `backend/`; `npm run lint` / `npm run test` / `npm run build` from `frontend/`. Confirm the container name with `podman ps` before the first `exec`.
- `seed_uat_fixtures.py` is deliberately **not** named `verify_*`, so the CI glob will not pick it up.

### Baselines to hold (regression gate)

pytest **232 passed / 0 skipped**; **15/15** non-API + **9/9** API `verify_*` exit 0; FE **139 tests / 44 files**; `npm run lint`, `backend/.venv/bin/ruff check .`, `tsc -b && vite build` exit 0; all **four** CI jobs green (`frontend`, `backend-lint`, `backend-tests`, `verify-scripts`).

### Prior art to copy

`.zj/UAT-v1.0.md` is the proven shape: fixture preamble → "What the machine already proved" table → per-check runbook with `✅` bullets → ordering rule (read-only first, mutating last). Its round-1/round-2 defects tell you where to aim: a **dead file picker** (no drag-drop handler, "Choose File" opened nothing), a **500 on re-adding an already-linked vendor**, a **footer that triple-counted material cost**. Weight checks toward file pickers, duplicate/re-entry paths, footers and totals, empty states, and **error-toast absence**.

### Standing traps to counter explicitly

- **Dead-through-UI** (caught in-build in Phases 11a/11b/12b/13, four running): a field/flow wired in the backend but unreachable through the UI. This UAT is the standing counter-measure — every check must confirm **end-to-end reachability**, not just that something rendered.
- **"Self-provisions from a bare server" is unproven until run against a genuinely EMPTY environment** (Phase 03) → SC2's seed and SC7's prod smoke run on a **fresh volume**, never a persisted dev DB.
- **A recipe derived by READING code is not a runnable recipe** (Phase 03) → **every command in the UAT runbook is executed once at build time (Task 16)** before the owner is asked to trust it.
- **Hand-checked ≠ pinned** (Phase 04) → every blocker/major fix ships a **CI-visible** assertion. New non-API `verify_*` scenarios are auto-globbed by the Phase-3 `verify-scripts` job, so the pin is nearly free.
- **A mutation's RED must fail for the *intended* reason** (Phase 04) → when pinning a fix, record what actually failed in the RED run and confirm it is the defect, not another guard hijacking red.

## Decisions  (owner-made; append to `.zj/DECISIONS.md` at build close)

- **D-P5-1 — UAT breadth = residue-only, full coverage.** Every shipped flow gets a check; each names only what a machine cannot confirm (labels, badges, colours, toast *absence*, auto-refresh without F5, empty states, sort order, read-only-ness). An agent pre-flight proves each flow's backend first. Target **~40–50 checks**, est. **2–3 h** of owner time. Copy `.zj/UAT-v1.0.md`'s "machine already proved" / "residue only a human can confirm" split.
- **D-P5-2 — Environment = dev overlay for the click-through + one prod-stack smoke.** Click-through on the Vite dev server **:5173** (D-P7-1 precedent; HMR means a defect is fixed and re-checked in seconds). Separately, one task brings the **prod** stack up on a fresh volume at **:8000** and smokes login + one write per suite (SC7).
- **D-P5-3 — Fixtures = idempotent seed script on a fresh DB** (SC2). The v1.0 UAT was burned by exactly this ("the previously-listed fixtures no longer exist — the dev volume was recreated"). The script is reusable for every future milestone UAT.
- **D-P5-4 — Defect policy = fix blocker/major in-phase with a pinning test; home minor to BACKLOG with a defect ID.** Matches the v1.0 D1/D2/D3 handling and every prior milestone.
- **D-P5-5 — Positive-adjust bin membership: ADD the check** (SC8), not accept-and-document. Resolves the p2 BACKLOG item's owner call.
- **D-P5-6 — One consolidated `.zj/UAT-v4.0.md`**, not three per-milestone docs. This **amends NFR-8's literal wording** ("`UAT-v1.0.md` round-2 + `UAT-v2.0.md` extended") — same coverage, one runbook. The SRD sentence is trued up at Task 33.
- **D-P5-7 — Run mechanics = interactive, suite by suite.** The build brings the stack up and pre-flights a suite, the **owner** clicks through it and reports results; the engineer records them and fixes defects live, then moves to the next suite. **The status table in `.zj/UAT-v4.0.md` is the resumable state** — the run must survive being paused across sessions.
- **D-P5-8 — CORE platform surfaces are IN scope** (~6 checks): login + token refresh, Users admin CRUD, RBAC nav filtering, module-toggle propagation, Settings. The module-toggle check is needed anyway for SC6's GELATO-off path, and it makes "every shipped UI flow" literally true.
- **D-P5-9 — Branch:** cut a fresh `chore-human-uat` off the current tip **`c02d80b`** on `chore-inventory-race-safety` (the unmerged v4.0 stack), same pattern as D-P4-4. `.vscode/settings.json` is unstaged-dirty (owner's) — **leave it**.

- **D-P5-10 — `U0` fix shape = a dedicated db env file** (owner, AskUserQuestion at Task 8, 2026-07-26).
  Split into `.env` (app secrets, unchanged) + **`.env.db`** (`POSTGRES_*` only); `db` gets
  `env_file: ../.env.db` and loses the `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}` line from
  `environment:` (which takes precedence and would keep overriding it to empty). Rejected alternatives:
  `env_file: ../.env` on `db` (one line, but spreads `JWT_SECRET` — the auth system's master key — and
  `BNS_ADMIN_PASSWORD` into a container that needs neither, visible in `podman inspect`);
  `--env-file .env` on every documented command (no restructure, but a forgotten flag silently
  reproduces the bug); deferring to BACKLOG (SC7 would then prove the artifact only under a workaround,
  contradicting its own wording). Rationale: the db container never sees a secret it does not need, and
  the **documented deploy command stays unchanged** — which is the thing U0 broke.

## Decisions needed

None. D-P5-1..10 are settled. If the run surfaces a defect whose fix requires an **Alembic migration** or a **GL/JE posting change**, that is a tripwire (below), not an architect decision — stop and surface it.

## Two STOP-and-flag tripwires

v4.0 ships **no new end-user capability**. The only product-code changes this phase authorizes are (a) UAT defect fixes and (b) the SC8 validation check. Therefore:

1. **Any need for an Alembic migration → STOP and flag the owner.** Head is `0017`; this phase adds none.
2. **Any change to GL/JE posting → STOP and flag the owner.** No amount, account, or posting rule moves in this phase.

Anything else that looks like new capability stops and surfaces too. Record the stop in `## Deviations`.

## Defect-handling protocol (a task pattern, referenced by every `[OWNER]` task — do not re-invent per suite)

When an owner check fails, the engineer runs this loop. **The phase's total size is bounded by SC4/SC5 and is unknown until the checks run** — that is expected and is not a planning defect.

1. **Assign an ID** — `U1`, `U2`, … (UAT defect; `U#` avoids colliding with `D-*` decisions and the v1.0 `D1/G1` series). Record it in the `.zj/UAT-v4.0.md` **Defects** table immediately, before any fixing: ID, check #, one-line symptom, severity, status.
2. **Call severity:**
   - **blocker** — the flow cannot be completed at all, or it produces wrong data / a wrong number.
   - **major** — the flow completes but a load-bearing affordance is wrong (mislabelled, missing badge, silent failure, stale list, a 500 on a legitimate re-entry).
   - **minor** — cosmetic, or an edge case the owner would not hit in normal operation.
3. **blocker/major → fix in-phase, with a pinning automated test:**
   - Backend fix → a new scenario in the relevant `backend/scripts/verify_*.py` (non-API, so CI auto-globs it) **or** a `backend/tests/` test.
   - Frontend fix → a colocated vitest asserting the real payload/render.
   - **Prove RED-on-revert and record what actually failed** — confirm the RED signature is the defect, not a different guard hijacking red (Phase-4 keeper).
   - Commit as `fix(<scope>): <symptom>` + `test(<scope>): pin U#`, referencing the defect ID.
   - Re-hand the check to the owner (HMR makes this seconds) and only then record the pass.
4. **minor → BACKLOG:** append an item under the appropriate priority naming `U#`, the check, and the observed behavior. Link it from the checklist row.
5. **Either way:** the checklist row's status becomes `pass`, `pass (U# fixed <commit>)`, or `U# → BACKLOG` — never `todo`.
6. **Tripwire check:** if the fix needs a migration or touches GL/JE posting, STOP (above).

**Early-warning rule:** if the first two owner suites yield **more than two blockers**, stop and re-scope with the owner before continuing — that signals the hardened stack is less healthy than Phases 1–4 implied.

## Owner hand-back protocol (applies to every `[OWNER]` task)

- The engineer hands over: the check numbers in scope, the URL to start at, the fixture names each check uses, and the literal expected values.
- The owner reports back, per check: **check number** + **PASS** or **FAIL** + for a FAIL, *what they actually saw* (the verbatim label / number / colour / absent element). A screenshot is welcome but the verbatim observation is what is required.
- The engineer records exactly what was reported into the status table and nothing more.
- **An engineer must never tick an owner check on the owner's behalf, and never infer a pass** from a passing machine assertion, from an adjacent check, or from silence. Unreported checks stay `todo` and the task stays open.
- A paused run is normal: the status table is the resumable state (D-P5-7).

## Tasks

Engineer tasks are unmarked. Owner tasks are marked **[OWNER]** and their "Verify" is the recorded result in the status table.

### [x] 0. Cut the branch and open the checklist file
- **Files:** `docs/tasks/chore-human-uat.md` (new)
- **Do:** `git checkout c02d80b -b chore-human-uat` (D-P5-9). Create the checklist file listing Tasks 1–38 per project convention. Leave `.vscode/settings.json` untouched. Conventional commits, no attribution lines, never edit `CHANGELOG.md`.
- **Done when:** `git rev-parse chore-human-uat~0` resolves and `git merge-base --is-ancestor c02d80b HEAD` is true; checklist committed.
- **Verify:** `git log --oneline -1 && git status --short` (only `.vscode/settings.json` and the new checklist appear).
- **Parallel-ok:** no (gates everything).

---

### Fixtures (SC2) — Tasks 1–8

### [x] 1. Create the seed-script skeleton with an idempotency contract and a manifest
- **Files:** `backend/scripts/seed_uat_fixtures.py` (new)
- **Do:** Model the header/DSN/engine bootstrap on `backend/scripts/verify_ar.py:158-214` (`build_dsn()`, own async engine from `POSTGRES_*`, no conftest import). Establish the contract in the module docstring: **every fixture is get-or-create keyed on a stable natural key** (code / number / name / email) and every builder returns the existing row unchanged when found. Add `main()` with two modes: default = seed then print the manifest; `--manifest` = print only, write nothing. The manifest is a deterministic, sorted table of `table → row count` plus the literal key codes of every named fixture. Register the fixture prefix `UAT-` on every code the script mints so its rows are identifiable.
- **Done when:** `python scripts/seed_uat_fixtures.py --manifest` runs against the live dev DB and prints an empty-ish manifest without writing; exit 0.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py --manifest`
- **Parallel-ok:** no (Tasks 2–7 extend this file).

### [x] 2. Seed the CORE + partners fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Get-or-create: two vendors and two customers via the real `syerp.service.partners` functions (`UAT-VEND-1`, `UAT-VEND-2`, `UAT-CUST-1`, `UAT-CUST-2`), one already-archived vendor (so the show-archived toggle has something to hide), and one **non-admin user** with a single-module role (for the RBAC nav-filter check) via `auth` service functions. Drive real services, never hand-INSERT — the dead-through-UI lesson applies to fixtures too.
- **Done when:** a run prints the five partner codes + the non-admin user's email in the manifest; a second run prints identical counts.
- **Verify:** run the script twice; `diff <(run1) <(run2)` is empty for the partner/user lines.
- **Parallel-ok:** no.

### [x] 3. Seed the PLUM fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Build, via the real PLUM service: the **cost / shared-sub-assembly tree** and the **where-used chain** in the shapes `.zj/UAT-v1.0.md:19-30` specifies (a 3-level BOM where one sub-assembly is shared, so the flat view must dedupe; a 3-level chain so Where-Used has one direct and one indirect parent), with explicit material costs and a below-cost sale price; one **Released** revision (v1.0 had none — check 8's read-only assertions need one); one Draft part with **no** AVL link (the happy-path Add-Vendor target) and one **with** a link plus a price break (so the vendor-price cost source is reachable). Use `UAT-P…` part numbers so auto-numbering checks are not perturbed. Compute and record the exact rolled-up cost / margin / margin-% Decimals in the manifest.
- **Done when:** the manifest prints the tree's part numbers with their rolled-up cost, the flat-BOM dedupe quantity, the sale price, the margin and margin-%, and the Released part number.
- **Verify:** two consecutive runs produce identical manifests for the PLUM block.
- **Parallel-ok:** no.

### [x] 4. Seed the SYERP inventory + purchasing fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Get-or-create: two stock locations besides the seeded `Main` (one to archive), three inventory items (`UAT-ITEM-…`) — one PLUM-linked, one standalone, one archived — and costed receipts giving each item known per-location on-hand and a known moving-average cost. One **Draft** PO with two lines and one **Approved** PO with outstanding quantity (so approve/receive/over-receipt checks each have their own PO and don't contend). Record every on-hand, moving-average, on-hand-value, PO number, and outstanding quantity as literals.
- **Done when:** manifest prints item codes, per-location on-hand, moving averages, on-hand values, and both PO numbers with line quantities.
- **Verify:** two consecutive runs → identical manifest block; `verify_inventory.py` still exits 0 afterwards.
- **Parallel-ok:** no.

### [x] 5. Seed the GELATO bins fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Get-or-create bins via the real GELATO service: at least two active bins plus one archived bin in one location, and **fully put away** one item's stock at that location so its unbinned pool is exactly zero — the fixture that makes the "must name a bin" pool floor (D-P4-1) observable in the pickers. Leave a second location with **no** bins at all, so the pickers' hide-when-no-bins branch is exercisable. Record bin codes, per-bin on-hand, and the zero unbinned pool as literals.
- **Done when:** manifest prints bin codes with per-bin on-hand and the exactly-zero unbinned pool for the fully-binned item.
- **Verify:** two consecutive runs → identical block; `verify_gelato.py` exits 0.
- **Parallel-ok:** no.

### [x] 6. Seed the MOUSSE + CRUMB fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Get-or-create via real services: one **Draft** and one **Released** work order over a PLUM BOM with components in stock (so issue and complete are each reachable without perturbing the other); one lead, one opportunity mid-stage, one quote with PLUM-derived lines in a state that can still be accepted, one **accepted** quote (so quote→SO conversion is reachable), one **confirmed** sales order carrying a soft reservation, and two communication-log entries. Record WO numbers, quote numbers, SO number, reserved quantity, and quote line totals as literals.
- **Done when:** manifest prints all of the above codes and quantities.
- **Verify:** two consecutive runs → identical block; `verify_mousse.py` and `verify_crumb_so.py` exit 0.
- **Parallel-ok:** no.

### [x] 7. Seed the SYERP GL / AP / AR fixture layer
- **Files:** `backend/scripts/seed_uat_fixtures.py`
- **Do:** Get-or-create via real services: one posted manual journal entry (so the register and JE list are non-empty and reversal is reachable), one **Draft** and one **Posted** AP bill (one PO-matched), one partial payment, one **posted** invoice from a shipment plus one partially-allocated receipt. Aim so that AP aging, AR aging, TB, BS, and IS all render non-trivially and the TB nets zero. Record every bill/invoice/receipt number, aging bucket total, control-account balance, and the TB net as literals.
- **Done when:** manifest prints those literals; the TB net is exactly zero.
- **Verify:** two consecutive runs → identical block; `verify_gl.py`, `verify_ap.py`, `verify_ar.py`, `verify_reports.py` all exit 0.
- **Parallel-ok:** no.

### [x] 8. Prove the seed idempotent on a genuinely fresh volume
- **Files:** `docs/tasks/chore-human-uat.md` (record the two manifests)
- **Do:** `podman-compose -f compose/compose.yml down -v`, then `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`, wait for `alembic current` == head (`0017`), then run the seed **twice**, capturing both manifests. Diff them. Fix any non-idempotent builder (Phase-03 keeper: this is the first run against a genuinely empty environment — expect it to find something). Paste both manifests into the checklist file as the authoritative literals source.
- **Done when:** `diff manifest1 manifest2` is empty, on a volume created minutes earlier; the manifests are recorded.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && alembic current'` prints `0017 (head)`; the two-run diff is empty.
- **Parallel-ok:** no (blocks Tasks 11–14 and every owner task).

### [x] 8a. Fix `U0` — the fresh-volume deploy blocker (ADDED mid-build, D-P5-10)
- **Files:** `compose/compose.yml`, `.env.db.example` (new), `.env.example`, `.gitignore`,
  `compose/compose.dev.yml` (only if it overrides db env), `README.md` / deploy docs, plus a pinning test
- **Do:** Implement D-P5-10. Give `db` `env_file: ../.env.db` and **remove** the
  `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}` line from its `environment:`. Create `.env.db.example`
  carrying only `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`; strip `POSTGRES_PASSWORD` from
  `.env.example` (or cross-reference it) so there is exactly one home for it. Add `.env.db` to
  `.gitignore`. Correct the misleading header comment at `compose/compose.yml:19`. Update every place
  that documents the bring-up so a first-time self-hoster copies **both** example files.
- **Done when:** on a genuinely fresh volume, the **documented** command sequence alone brings the stack
  up — no `set -a; . ./.env` shell workaround — and `podman inspect` shows a non-empty
  `POSTGRES_PASSWORD` on `db` and **no** `JWT_SECRET` / `BNS_ADMIN_PASSWORD` on `db`.
- **Verify:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v`, then the
  documented bring-up from a clean shell; `/health/ready` 200; `alembic current` == `0017 (head)`;
  the pinning test fails on revert.
- **Parallel-ok:** no (must precede Task 35; land it before the owner run so product config is stable).

---

### Pre-flight (SC3) — Tasks 9–10

### [x] 9. Write the check → machine-assertion map
- **Files:** `.zj/phases/05-human-uat/PREFLIGHT.md` (new)
- **Do:** One row per planned check: check #, flow, the **existing** assertion that proves its backend (`backend/scripts/verify_*.py` scenario letter, `backend/tests/...::test_name`, or `frontend/src/.../*.test.tsx`), and the residue left for the human. Prefer citation over new code — the 24 verify scripts plus 232 pytest tests plus 139 vitests already cover most backends. Mark every row with **no** covering assertion as `machine-unproven`. Seed the map from the measured FE holes in `## Context` (Home, Settings, Modules, GLAccounts, LeadDetail, OpportunityDetail, Quotes, `getVisibleModules`).
- **Done when:** every planned check has either a citation (file + test/scenario name) or an explicit `machine-unproven` mark; no row is blank.
- **Verify:** every cited file path exists and every cited test/scenario name is greppable — `grep -c` each citation; zero misses.
- **Parallel-ok:** yes (independent of Tasks 1–8).

### [x] 10. Add probes for the machine-unproven surfaces worth probing
- **Files:** `frontend/src/components/AppShell.test.tsx` (new), plus any additional `frontend/src/routes/**/**.test.tsx` the map calls for
- **Do:** For each `machine-unproven` row from Task 9, either add a cheap probe or leave the mark and say why in `PREFLIGHT.md`. Minimum: a vitest on `getVisibleModules` (`AppShell.tsx:37-46`) covering enabled∩permitted, admin-wildcard, and disabled-module exclusion — the nav filter behind CORE-07 and SC6's GELATO-off check, which nothing tests today. Do **not** write probes for pure appearance (colour, badge presence, toast absence); those are the human residue by definition.
- **Done when:** `PREFLIGHT.md` has no unexplained `machine-unproven` row; new tests pass.
- **Verify:** `cd frontend && npm run test` — file/test count is above the 44/139 baseline and 0 failures.
- **Parallel-ok:** no (depends on Task 9).

### [x] 10a. Fix `U1` — HTTP 500 on duplicate-email user creation (ADDED mid-build)
- **Files:** `backend/app/modules/auth/service.py` (and/or `router.py`), plus a pinning test
- **Do:** Found by the Task-9 pre-flight, not by a human: `POST` a second user with an existing email
  returns **500** (`IntegrityError` → `UniqueViolationError` on `ix_users_email`) because nothing guards
  it — `grep -n "IntegrityError\|409\|already exists"` over the auth service and router returns **no
  matches**. Severity **major** per the plan's rubric ("a 500 on a legitimate re-entry"), and it is the
  v1.0 **D2** pattern the plan explicitly told this UAT to weight toward. Return a clean **409**
  (or 422 if that matches the codebase's house convention for this class — check the neighbours and
  match them) with an actionable message, and persist nothing.
- **Done when:** a duplicate-email create returns a clean, non-5xx, actionable error; the first create
  still succeeds; no partial user row is written.
- **Verify:** a pinning test in `backend/tests/auth/` proven RED-on-revert with the **actual RED
  signature recorded**, confirming the red is the missing guard and not another assertion hijacking it.
- **Parallel-ok:** no (land before the owner run so `C-CORE-04` can pass rather than be a known failure).

---

### The checklist (SC1) — Tasks 11–15

### [x] 11. Author `.zj/UAT-v4.0.md`: preamble, fixture table, ordering rule, defect ledger
- **Files:** `.zj/UAT-v4.0.md` (new)
- **Do:** Copy `.zj/UAT-v1.0.md`'s shape. Sections: (1) how to run — the exact fresh-volume bring-up + seed commands, `:5173`, admin login from `.env` (`BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD`); (2) the **named fixture table** with every literal from Task 8's manifests; (3) the ordering rule — *read-only checks first, mutating checks last; a check must never poison a later check's fixture*; (4) the master **status table** (check #, flow + requirement ID, suite, status, notes) — this is the phase's resumable state (D-P5-7); (5) an empty **Defects** table (ID, check, symptom, severity, status, fix commit / backlog link); (6) a note that this doc consolidates and supersedes the v1.0/v2.0 runbooks per **D-P5-6**.
- **Done when:** the doc exists with all six sections; every literal in the fixture table traces to a Task-8 manifest line.
- **Verify:** `grep -c '^| ' .zj/UAT-v4.0.md` > 0 and every fixture code in the table appears in the recorded manifest (`grep -F` each).
- **Parallel-ok:** no (depends on Task 8).

### [x] 12. Author the CORE + PLUM checks
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** ~6 CORE checks (D-P5-8): login + session survives access-token expiry (CORE-02/03), Users admin CRUD incl. a duplicate-email re-entry (CORE-04), RBAC nav filtering as the non-admin fixture user (CORE-05), Settings save + persist (CORE-06), module-toggle propagation to the sidebar (CORE-07), Home/nav shell + unknown-path fallback (CORE-08). ~11–13 PLUM checks covering PLUM-01..10: parts list search/filter + empty state, part detail, BOM tree expand/collapse, **flat BOM dedupe + the Total-BOM-Cost footer** (the v1.0 D1 triple-count), Where-Used direct/indirect labels and their sort order, Cost & Margin across all three sources, below-cost margin **rendered red**, revision FSM + Released read-only-ness, AVL add + Preferred badge + **the duplicate re-add path** (the v1.0 D2 500), import/export incl. **"Choose File" opens a dialog AND drag-drop highlights and selects** (the v1.0 D3 dead picker), and the list refreshing **without F5** after a commit. Each check names its fixture, cites its machine proof from `PREFLIGHT.md`, and states residue only.
- **Done when:** every CORE/PLUM row has fixture + citation + residue + a `todo` status; each requirement ID CORE-01..09 and PLUM-01..10 appears in at least one row.
- **Verify:** `for id in CORE-0{1..9} PLUM-0{1..9} PLUM-10; do grep -qF "$id" .zj/UAT-v4.0.md || echo "MISSING $id"; done` prints nothing.
- **Parallel-ok:** yes (with Tasks 13, 14).

### [x] 13. Author the SYERP checks
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** ~18–20 checks over SYERP-01..05 and SYERP-10..13: partners CRUD + search + archive-toggle; inventory items (auto `ITEM-####`, PLUM link, show-archived), item detail per-location on-hand + total + moving average + on-hand value, the **read-only** append-only ledger, stock locations incl. archive; adjust and transfer happy paths plus their rejection **toasts**; PO create (vendor picker lists **only** vendors), approve (illegal actions **hidden**), partial receive → `Partially Received`, remainder → `Received`, over-receipt rejection, vendor filter, close; GL accounts, journal entry post + reverse, account register; AP bill from a PO receipt, pay bill, AP aging tie-out **footer**; AR invoice from a shipment, record receipt, AR aging; financial reports TB/BS/IS with the **TB netting zero on screen**. Reuse `.zj/UAT-v2.0.md`'s 14 checks verbatim where they still apply, upgraded with fixture names, citations, and residue.
- **Done when:** every row has fixture + citation + residue + `todo`; SYERP-01..05 and SYERP-10..13 each appear.
- **Verify:** `for id in SYERP-0{1..5} SYERP-1{0..3}; do grep -qF "$id" .zj/UAT-v4.0.md || echo "MISSING $id"; done` prints nothing.
- **Parallel-ok:** yes.

### [x] 14. Author the MOUSSE, CRUMB and GELATO checks
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** ~4 MOUSSE (MOUSSE-01): WO list + create from a BOM, release, issue components, complete with **WIP visibly clearing to zero**. ~8 CRUMB (CRUMB-01): leads list + create + convert-to-opportunity, lead detail, pipeline stage move, opportunity detail, quote create with PLUM-derived line pricing + line editor totals, quote status FSM + accept, sales orders list, SO detail confirm showing the **soft reservation**, communication log **append-only-ness**. ~4 GELATO (GELATO-01): bins CRUD + archive, putaway incl. the suggestion, fulfilment pick → pack → ship, and the post-ship state. Give the CRUMB→GELATO→AR money-loop checks an explicit ordering note so they run in dependency order and do not poison the AR fixtures Task 13's read-only checks consume.
- **Done when:** every row has fixture + citation + residue + `todo`; MOUSSE-01, CRUMB-01, GELATO-01 each appear.
- **Verify:** `for id in MOUSSE-01 CRUMB-01 GELATO-01; do grep -qF "$id" .zj/UAT-v4.0.md || echo "MISSING $id"; done` prints nothing.
- **Parallel-ok:** yes.

### [x] 15. Author the SC6 bin-picker checks, including the GELATO-off degraded path
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Four checks. (a) `StockAdjustDialog` bin picker: it appears only once a location with active bins is chosen, defaults to **"Unbinned pool"**, resets when the location changes, and a negative adjustment against the **fully-binned** fixture item (zero unbinned pool) is rejected with the pool-floor toast unless a bin is named (D-P4-1). (b) `StockTransferDialog` **from-bin** picker: same shape; confirm the destination leg lands **unbinned** (D-P4-5) and total on-hand is unchanged. (c) `IssueComponentsDialog` **per-line** bin picker: the column appears per line and each line's bin is independently selectable. (d) **GELATO-off degraded path:** toggle GELATO off in Settings→Modules, then re-open all three dialogs and record what actually happens. Write this check as *record the observed behavior*, not as *confirm the picker hides* — see `## Noticed` #1: there is **no server-side module gate**, so the API still serves `/api/v1/gelato/*` and the dialogs' own docstrings ("hidden when the bins query errors (GELATO off)") may be wrong. If the pickers still list bins, that is a defect → protocol (expected severity: minor). The check must end by toggling GELATO **back on** and confirming the sidebar restores.
- **Done when:** four rows exist, each naming its dialog file and its fixture, with the GELATO-off row written as an observation with an explicit restore step.
- **Verify:** `grep -c 'StockAdjustDialog\|StockTransferDialog\|IssueComponentsDialog' .zj/UAT-v4.0.md` ≥ 3 and the GELATO-off row names the restore step.
- **Parallel-ok:** yes.

### [x] 16. Execute every command in the runbook once, at build time
- **Files:** `.zj/UAT-v4.0.md` (corrections), `docs/tasks/chore-human-uat.md` (log)
- **Do:** The Phase-03 keeper, applied literally: run **every** command the runbook asks the owner to run — the fresh-volume `down -v`, the dev-overlay bring-up, `alembic current`, the seed invocation, the `:5173` load, and the admin login — in order, from a clean shell, and correct the doc wherever reality differs (missing `PYTHONPATH`, container name, wait-for-ready, a needed seed step). Leave the stack **up and seeded** so Task 18 can start immediately.
- **Done when:** every runbook command has been executed once with the observed output logged; the doc matches reality; `:5173` serves the login page and admin login succeeds.
- **Verify:** `curl -sSf -o /dev/null -w '%{http_code}\n' http://localhost:5173` → `200`; `curl -sSf http://localhost:8000/health/ready` → 200.
- **Parallel-ok:** no (depends on Tasks 11–15).

### [x] 17. Add pointer lines to the v1.0 and v2.0 UAT docs
- **Files:** `.zj/UAT-v1.0.md`, `.zj/UAT-v2.0.md`
- **Do:** Add one pointer line at the top of each: superseded for *execution* by `.zj/UAT-v4.0.md` (D-P5-6), retained as history — with the count of checks each carried forward (10 of 12 open in v1.0; all 14 open in v2.0). Change nothing else in either file.
- **Done when:** both files carry the pointer; `git diff --stat` shows only added lines.
- **Verify:** `grep -c 'UAT-v4.0.md' .zj/UAT-v1.0.md .zj/UAT-v2.0.md` → 1 each; `git diff --numstat .zj/UAT-v1.0.md .zj/UAT-v2.0.md` shows 0 deletions.
- **Parallel-ok:** yes.

---

### The SC8 validation check — Tasks 18–19 (land before the owner run so product code is stable)

### [x] 18. Add the positive-adjust bin existence + membership check
- **Files:** `backend/app/modules/syerp/service/inventory.py` (`post_adjustment`, ~line 361)
- **Do:** After the `get_location` 404 load and before the ledger write, when `bin_id is not None`, run **one raw-SQL** `SELECT 1 FROM gelato_bin WHERE id = :bin_id AND location_id = :location_id` via `db.execute(text(...))` and raise **422** when it returns nothing. **No gelato model import** — D-P12a-3's no-imports rule must hold (assert it: `grep -n 'gelato' backend/app/modules/syerp/service/inventory.py` shows only comments and the raw table name). Update the docstring's trust-boundary paragraph (lines ~403-406) — it currently states the bin is *not* validated. Before writing, `grep` the existing 422 detail strings in `backend/scripts/verify_gelato.py`, `verify_mousse.py`, and `backend/tests/syerp/` to confirm no existing assertion depends on the negative-mismatch path's current message.
- **Done when:** a `post_adjustment` with a `bin_id` belonging to a different location raises 422 and writes no ledger row; a matching `(location, bin)` pair still succeeds; no gelato model is imported.
- **Verify:** `cd backend && .venv/bin/ruff check .` exit 0; `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest -q tests/syerp'` → 0 failures.
- **Parallel-ok:** no (Task 19 pins it).

### [x] 19. Pin the membership check with a new `verify_gelato.py` scenario
- **Files:** `backend/scripts/verify_gelato.py`
- **Do:** Add scenario **(G)** following the existing (E)/(F) style: build two locations each with a bin, then `post_adjustment(+qty, location_id=B, bin_id=<bin of A>)` → assert **422** and assert the item's ledger row count is unchanged; then the matching pair → assert success and that the bin's on-hand rises by exactly `qty`. Extend the docstring scenario list and the `_cleanup` registry. Prove the mutation: comment out the new check → scenario G goes RED; restore → GREEN. **Record what actually failed in the RED run** and confirm it is the missing membership check, not another guard (Phase-4 keeper).
- **Done when:** `verify_gelato.py` exits 0 with scenario G present; the RED→GREEN mutation is executed and its RED signature recorded in the checklist file.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato.py` → "All assertions PASSED", exit 0. (Non-API, so the Phase-3 `verify-scripts` CI job auto-globs it — the pin is free.)
- **Parallel-ok:** no.

---

### The owner run (SC4/SC6) — Tasks 20–31, ordered read-only before mutating

Each task: the engineer confirms the stack is up and seeded, restates the checks in scope with their literals, hands over per the **hand-back protocol**, then records results and applies the **defect-handling protocol**. Suites are ordered so no check poisons a later check's fixture.

### [ ] 20. **[OWNER]** CORE platform click-through
- **Files:** `.zj/UAT-v4.0.md` (status + defects)
- **Do:** Owner runs the ~6 CORE checks from Task 12 (login + session-survives-expiry, Users CRUD + duplicate-email re-entry, RBAC nav as the non-admin fixture user, Settings save/persist, Home + unknown-path fallback). **The module-toggle check is deferred to Task 26** so the toggle's blast radius stays contained there. Engineer records results verbatim.
- **Done when:** every CORE row has `pass` or a defect ID; zero `todo`.
- **Verify:** the recorded results in the CORE block of the status table; `grep -c 'todo' ` over the CORE rows → 0.
- **Parallel-ok:** no (first sitting; also validates login for every later task).

### [ ] 21. **[OWNER]** PLUM read-only click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the read-only PLUM checks: parts list search/filter + empty state, part detail, BOM tree, **flat BOM dedupe + footer total**, Where-Used labels + sort order, Cost & Margin sources, **below-cost margin red**, Released revision read-only-ness. Nothing here mutates, so it can be re-run freely after any fix.
- **Done when:** every read-only PLUM row has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 22. **[OWNER]** PLUM mutating click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs: new revision + FSM advance, BOM add/remove on a Draft, AVL add + Preferred badge + **duplicate re-add** (v1.0 D2), archive part, and Import/Export — export JSON, export Excel, **"Choose File" opens a dialog**, **drag-drop highlights and selects** (v1.0 D3), re-import → 0 errors → Confirm → "No records deleted", >10 MB rejected, and the parts list refreshing **without F5**. Runs after Task 21 because imports and part creation shift the fixtures Task 21 reads.
- **Done when:** every mutating PLUM row has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 23. **[OWNER]** SYERP financial read-only click-through (GL, AP, AR, reports)
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the read-only financial checks **before any new posting moves the numbers**: GL accounts list, journal-entry list, account register, bills list + bill detail, AP aging footer tie-out, invoices list + invoice detail, receipts list, AR aging, and financial reports TB/BS/IS with the **TB netting zero on screen** — each against the Task-7 literals. `GLAccounts.tsx` has no vitest, so weight it accordingly.
- **Done when:** every row in this block has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no (must precede Tasks 27–30, which post).

### [ ] 24. **[OWNER]** SYERP inventory read-only click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs: partners lists + search + show-archived, inventory items list (auto codes, PLUM link, show-archived), item detail (per-location on-hand, total, moving average, on-hand value), the **read-only append-only ledger**, and stock locations incl. `Main` present out-of-the-box.
- **Done when:** every row in this block has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 25. **[OWNER]** SYERP inventory mutating click-through + the adjust/transfer bin pickers
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the adjust and transfer checks together with SC6 checks (a) and (b) from Task 15 — the `StockAdjustDialog` bin picker and the `StockTransferDialog` from-bin picker — since they live in exactly these dialogs. Includes both rejection toasts (per-location floor and pool floor) and the destination-leg-lands-unbinned assertion (D-P4-5).
- **Done when:** every adjust/transfer row and SC6 rows (a) and (b) have `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 26. **[OWNER]** Module-toggle propagation and the GELATO-off degraded path
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the CORE-07 module-toggle check and SC6 check (d): toggle GELATO **off** in Settings→Modules, confirm the sidebar drops it, then re-open all three Phase-4 dialogs and **record what actually happens to the bin pickers** (see Task 15 and `## Noticed` #1 — do not assume they hide). Also try navigating directly to `/gelato/bins`. Then toggle GELATO **back on** and confirm the sidebar restores. Engineer applies the defect protocol to whatever is observed.
- **Done when:** the toggle row and SC6 row (d) have `pass` or a defect ID, **and** GELATO is confirmed back on (later tasks depend on it).
- **Verify:** recorded results in the status table; **and** GELATO is confirmed re-enabled straight from the DB, no token needed (table `modules`, natural key `key`, per `backend/app/core/modules_model.py:21-27`):
  `podman exec compose_db_1 psql -U app -d biznice -tAc "select key, enabled from modules where key='gelato'"` → prints `gelato|t`.
  (Confirm the db container name with `podman ps`; `POSTGRES_USER` defaults to `app`, `POSTGRES_DB` to `biznice` — `compose/compose.yml:34-35`.)
- **Parallel-ok:** no (must precede Task 30).

### [ ] 27. **[OWNER]** SYERP purchasing click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the seven purchasing checks: create (vendor picker lists **only** vendors, auto `PO-####`), approve (lines become non-editable, illegal actions hidden), receive partial → `Partially Received` with on-hand and moving-average moving as expected, receive remainder → `Received`, over-receipt rejection toast with nothing posted, vendor filter, close. Runs after Tasks 23/24 because receipts move on-hand and post to the GL.
- **Done when:** every purchasing row has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 28. **[OWNER]** MOUSSE click-through + the per-line issue bin picker
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs WO list/create/release/issue/complete with **WIP visibly clearing to zero**, together with SC6 check (c) — the `IssueComponentsDialog` per-line bin picker.
- **Done when:** every MOUSSE row and SC6 row (c) have `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 29. **[OWNER]** CRUMB click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the ~8 CRUMB checks: leads list/create/convert, lead detail, pipeline stage move, opportunity detail, quote create + line pricing + totals, quote FSM + accept, sales orders list, SO confirm showing the soft reservation, communication log append-only-ness. `LeadDetail.tsx`, `OpportunityDetail.tsx`, and `Quotes.tsx` have **no vitest** — weight those heaviest.
- **Done when:** every CRUMB row has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no (must precede Task 30 — GELATO fulfils a confirmed SO).

### [ ] 30. **[OWNER]** GELATO click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs bins CRUD + archive, putaway incl. the suggested bin, and fulfilment **pick → pack → ship** against the SO from Task 29, plus the post-ship state. Requires GELATO enabled (Task 26 restored it).
- **Done when:** every GELATO row has `pass` or a defect ID.
- **Verify:** recorded results in the status table.
- **Parallel-ok:** no.

### [ ] 31. **[OWNER]** SYERP money-loop tail click-through
- **Files:** `.zj/UAT-v4.0.md`
- **Do:** Owner runs the write side of the books, in dependency order and last: create a bill from the Task-27 PO receipt, pay it, **invoice from the Task-30 shipment**, record a receipt against that invoice, then re-open Financial Reports and confirm the **TB still nets zero on screen** and AP/AR aging still tie to their control accounts. This is the whole money loop driven through the UI in one sitting.
- **Done when:** every row in this block has `pass` or a defect ID; the on-screen TB net is zero.
- **Verify:** recorded results in the status table; `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_reports.py` still exits 0.
- **Parallel-ok:** no (last owner suite on the dev stack).

---

### Close-out — Tasks 32–36

### [ ] 32. Reconcile the checklist: zero `todo`, every defect homed
- **Files:** `.zj/UAT-v4.0.md`, `.zj/BACKLOG.md`
- **Do:** Sweep the status table for any `todo` row and either get it run (back to the owner) or, if the owner explicitly declines a check, record that decision verbatim as a `## Deviations` entry — never as a pass. Reconcile the Defects table: every blocker/major has a fix commit **and** a named pinning test; every minor has a BACKLOG item quoting its `U#`.
- **Done when:** `grep -c 'todo' .zj/UAT-v4.0.md` → 0; every Defects row carries a commit SHA or a backlog link.
- **Verify:** `grep -n 'todo\|⬜' .zj/UAT-v4.0.md` prints nothing; each fix SHA resolves via `git cat-file -e <sha>^{commit}`.
- **Parallel-ok:** no.

### [ ] 33. Run the full regression gate
- **Files:** `docs/tasks/chore-human-uat.md` (record results)
- **Do:** Hold the baselines: in-container `pytest -q` (**232 passed / 0 skipped**, plus any new tests), the 15 non-API + 9 API `verify_*` scripts, `backend/.venv/bin/ruff check .`, `npm run lint`, `npm run test`, `npm run build`, and all four CI jobs green on `chore-human-uat`. Record the CI run ID.
- **Done when:** every command exits 0, counts at or above baseline, CI 4/4 green with the run ID recorded.
- **Verify:** `gh run list --branch chore-human-uat --limit 1` shows all four jobs `success`.
- **Parallel-ok:** no.

### [ ] 34. Rebuild `frontend/dist` and the API container image
- **Files:** `frontend/dist/` (rebuilt artifact), no source change
- **Do:** `cd frontend && npm run build` (host bundle), then `podman-compose -f compose/compose.yml build api` (the image builds its own SPA in the `frontend-builder` stage — see `## Context`). Must run **after** Task 32, so no defect fix lands after the image is built; if a fix lands later, re-run this task. Closes the p1 BACKLOG "Rebuild `frontend/dist` + the API container image" item, including the stale-`openpyxl` half.
- **Done when:** both artifacts are newer than the last source commit; the image contains `openpyxl` (the old image did not).
- **Verify:** `podman run --rm --entrypoint python <image> -c 'import openpyxl, sys; print(openpyxl.__version__)'` prints `3.1.5`; `ls -l frontend/dist/index.html` is newer than `git log -1 --format=%cd -- frontend/src`.
- **Parallel-ok:** no.

### [ ] 35. Bring the prod stack up on a fresh volume at :8000
- **Files:** `docs/tasks/chore-human-uat.md` (log)
- **Do:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v` (drop the dev stack **and** its volume), then `podman-compose -f compose/compose.yml up -d` with `compose.yml` **alone** — no dev overlay, so the image's `/app/frontend/dist` is not shadowed. Wait for the entrypoint's `alembic upgrade head` + lifespan seeds, then run `seed_uat_fixtures.py` in the prod container. This is the fresh-volume, genuinely-empty environment the Phase-03 keeper demands.
- **Done when:** `/health/ready` is 200, `alembic current` is `0017 (head)`, and `:8000` serves the SPA (not a 404) with the seeded fixtures present.
- **Verify:** `curl -sSf -o /dev/null -w '%{http_code}\n' http://localhost:8000/` → `200`; `curl -sSf http://localhost:8000/health/ready`; `podman exec -e PYTHONPATH=/app <prod api container> sh -c 'cd /app && alembic current'` → `0017 (head)`.
- **Parallel-ok:** no.

### [ ] 36. **[OWNER]** Prod-stack deploy smoke at :8000
- **Files:** `.zj/UAT-v4.0.md` (a short "prod smoke" section with its own status rows)
- **Do:** Owner logs in at **http://localhost:8000** (not :5173) and performs **one write per enabled suite** — e.g. edit a partner (SYERP), edit a part (PLUM), create a WO (MOUSSE), log an interaction (CRUMB), create a bin (GELATO) — confirming each succeeds and no error toast appears. This proves the *shipped artifact*, not the dev server: the exact thing the stale-image backlog item was about.
- **Done when:** login succeeds and one write per enabled suite is recorded as `pass`, or a defect ID exists per the protocol.
- **Verify:** the recorded results in the prod-smoke section of `.zj/UAT-v4.0.md`.
- **Parallel-ok:** no.

### [ ] 37. Bookkeeping: SRD NFR-8 and requirements-progress
- **Files:** `.zj/SRD.md` (NFR-8, §800), `docs/features/requirements-progress.md`
- **Do:** Stamp NFR-8 → `done (pending /zj:verify 5)` with evidence: the check count and pass tally, the defect ledger summary (blockers/majors fixed with pin names, minors homed), the SC7 prod-smoke result, and the SC8 commit. **True up NFR-8's Verification sentence** to name the single consolidated `.zj/UAT-v4.0.md` per **D-P5-6** (it currently says "`UAT-v1.0.md` round-2 + `UAT-v2.0.md` extended"). Add the NFR-8 row to `requirements-progress.md` in the house format. Also promote the module SRD rows whose only remaining caveat was "UI-flow UAT-pending" (PLUM-04..10, SYERP-10/11, MOUSSE-01) where their checks now passed — cite the check numbers.
- **Done when:** NFR-8 carries a status + evidence stamp naming `.zj/UAT-v4.0.md`; the progress row exists; every promoted module row cites its check number.
- **Verify:** `grep -A4 'NFR-8' .zj/SRD.md` shows the new status and the UAT-v4.0 citation; `grep -c 'NFR-8' docs/features/requirements-progress.md` ≥ 1.
- **Parallel-ok:** no.

### [ ] 38. Bookkeeping: ROADMAP, BACKLOG, DECISIONS, and archive the checklist
- **Files:** `.zj/ROADMAP.md` (v4.0 Phase 5 row), `.zj/BACKLOG.md`, `.zj/DECISIONS.md`, `docs/tasks/_completed/2026-07-XX-chore-human-uat.md`
- **Do:** Update the ROADMAP Phase 5 row with the outcome and evidence. Check off the p1 "Human click-through UAT for v2.0 operations" item and the p1 "Rebuild `frontend/dist` + the API container image" item; check off the p2 "Positive adjustment accepts an unvalidated `bin_id`" item citing the SC8 commit and scenario G; add any new minor defects as items quoting their `U#`. Append **D-P5-1..9** to `.zj/DECISIONS.md`. Archive `docs/tasks/chore-human-uat.md` to `docs/tasks/_completed/{date}-chore-human-uat.md`.
- **Done when:** all four files updated; the three backlog items are `[x]`; D-P5-1..9 present; the checklist is archived.
- **Verify:** `grep -c 'D-P5-' .zj/DECISIONS.md` ≥ 9; `grep -n 'Human click-through UAT\|Rebuild `frontend/dist`\|unvalidated `bin_id`' .zj/BACKLOG.md` all show `[x]`; the archived file exists.
- **Parallel-ok:** no (last task).

## Risks

- **The defect tail is unbounded by construction.** SC4/SC5 bound the phase's size, and it is unknowable until the checks run — this is inherent to a UAT phase, not a planning gap. *Early warning:* more than two blockers in the first two owner suites → stop and re-scope with the owner (see the protocol).
- **A defect fix wants a migration or a GL/JE change.** *Early warning:* the fix hypothesis mentions a new column or a posting rule. → tripwire, STOP and flag.
- **A late fix invalidates the prod artifacts.** Tasks 34–36 must follow Task 32; a fix landing after Task 34 leaves a stale image again — exactly the v1.0 G2 failure. *Early warning:* any commit touching `backend/app/` or `frontend/src/` after Task 34 → re-run 34–36.
- **Fixture poisoning across checks.** A mutating check consumes stock/reservations a later read-only check quotes as a literal. Mitigated by the read-only-first ordering and the per-task ordering notes; *early warning:* a check fails on a *number* rather than an affordance — re-seed and re-run before treating it as a defect.
- **The seed script's own idempotency is the single point of failure for every literal in the checklist.** Task 8 proves it on a fresh volume before anything downstream depends on it. *Early warning:* the two-run manifest diff is non-empty.
- **Owner time is the scarce resource and the run will be paused.** Mitigated by D-P5-7 (the status table is the resumable state) and by grouping owner tasks one-sitting-per-suite. *Early warning:* an owner task's checks span more than ~20 minutes → split it.
- **Interpreting a machine pass as a human pass.** The single most likely way this phase produces a false PASS. Countered by the hand-back protocol's explicit prohibition, and by the fact that the v1.0 Where-Used defect (G1) was exactly this failure — "live-confirmed by audit" meant the *API* was confirmed.

## Noticed

1. **There is no server-side module gate.** `backend/app/core/modules_router.py` only stores the `enabled` flag; no router carries a module-enabled dependency (`grep -rn 'require_module\|module_enabled' backend/app/` → nothing), and `frontend/src/App.tsx` has no per-module route guard. Disabling GELATO therefore only filters the sidebar via `getVisibleModules` (`AppShell.tsx:37-46`) — `/api/v1/gelato/*` still serves an authorized user and `/gelato/bins` stays directly reachable. Consequently the three Phase-4 dialogs' docstring claim — "Hidden … when the bins query errors (GELATO off)" (`StockAdjustDialog.tsx:20-21`, mirrored in `StockTransferDialog.tsx:20`, `IssueComponentsDialog.tsx:149-151`) — is **probably wrong about the cause**: the real `isError` trigger is an RBAC 403 or a network failure, not a module toggle. Task 15/26 record the truth; the docstrings likely need correcting either way.
2. **Seven route screens have no colocated vitest** — `Home.tsx`, `admin/Settings.tsx`, `admin/Modules.tsx`, `syerp/GLAccounts.tsx`, `crumb/LeadDetail.tsx`, `crumb/OpportunityDetail.tsx`, `crumb/Quotes.tsx` — plus `getVisibleModules`. Task 10 adds the `getVisibleModules` probe; the rest are the genuinely machine-unproven surfaces and get the heaviest human weight.
3. **Under the dev overlay, `:8000` serves no SPA at all** (the `../backend:/app` bind mount shadows the image's `/app/frontend/dist`; `main.py:118` mounts only if the dir exists). This is the mechanical reason D-P7-1 chose `:5173`, and the reason SC7's smoke must use `compose.yml` alone.
4. **Build-time observations from the fixture layers** (candidate UAT checks / minor defects, not acted on):
   (a) `update_cost` rejects a Released revision with *"BOM lines can only be edited on Draft revisions."*
   (`plum/service.py:2029`) — copy-pasted from `add_bom_line`; correct behavior, wrong noun. If it ever
   reaches a toast the owner is told about BOM lines while editing a cost. Candidate minor.
   (b) Flat-BOM rows come back over HTTP with raw column scale (`qty = 33.000000000000000000`) — the
   PLUM read-only check must confirm the **screen** shows `33`, not the raw scale.
   (c) `POST /api/v1/auth/login` takes **OAuth2 form-encoded** `username`/`password`, not JSON (a JSON
   body 422s naming a missing `username`) — bake into the Task-11 runbook and Task 16.
   (d) The seeded `user` role grants all ten business read/write permissions, so it is unusable as an
   RBAC nav-filter subject; that is why T2 mints its own single-permission `UAT-PLUM-ONLY` role.
   (e) `get_item_onhand` **omits zero-net locations by documented policy** (`inventory.py:60`), so the
   archived zero-stock item shows an *empty* location table. The item-detail check must read that as
   correct, not as a defect.
   (f) On-hand quantities also come over HTTP at raw column scale (`"7.000000"`) — same screen-vs-payload
   eye as (b).
   (g) **The pool-floor rejection names the location by numeric id** — *"exceeds the unbinned pool at
   location 374"*, not `UAT-LOC-A`. If that string reaches a toast verbatim the owner sees `374`.
   Strong candidate minor defect for Task 25; flagged now so it is recognised as known, not new.
   (h) `UAT-BIN-A3` is archived and holds 0. The pickers call `list_bins(include_archived=False)`, so
   it must be **absent** from the picker while still visible on the Bins screen with the toggle on —
   the manifest records it so "correctly hidden" is distinguishable from "missing".
   (i) **A Draft WO genuinely reports `component_count 0`** — components snapshot at *release*. Task 14's
   WO check needs a sentence saying so, or an empty component table reads as a broken fixture.
   (j) Quote line `sort_order` is **0-based** while PO lines are **1-based**. Harmless, but if the UI
   surfaces raw sort order the two screens number their lines differently.
   (k) **Receipts and payments have no human document number.** `ReceiptRead`/`PaymentRead` expose only
   `id`, date, amount and a free-text `reference` — unlike `BILL-####` / `INV-####`. The Receipts and
   Payments screens have nothing else to identify a row by, and nothing enforces reference uniqueness.
   Task 23's receipts-list check should look deliberately: "the list shows a UUID" would be a real
   finding.
   (l) **`2150 GR/IR` carries 4950.00 of pre-existing dev data** (receipts never billed) — the dominant
   TB line, and not the fixture's. On Task 8's fresh volume it will be only the fixture's 94.25, so the
   very different fresh-volume totals must not be read as a regression.
   (m) `SO-0002` shows `qty_reserved 0` after shipping — the reservation is consumed by the pick.
   Correct, but a checklist quoting "reserved" for a shipped SO would be quoting a zero.
   (n) Number formats/widths differ across suites (`QUOTE-####`, `SO-####`, `WO-######`, `PO-####`,
   `ITEM-####`) — quote them exactly in the checklist so an owner doesn't flag a "wrong" width.

5. **`U0` (blocker, deploy config) — the compose stack cannot start on a fresh volume.** Found at Task 8,
   verified independently by the manager. `db` receives `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}` by
   **interpolation only** (`compose/compose.yml:36`); only `api` carries `env_file: ../.env` (line 62);
   `compose/.env` does not exist (the real `.env` is at the repo root), so podman-compose interpolates
   it to **empty** and Postgres refuses to initialize: *"Database is uninitialized and superuser
   password is not specified."* Confirmed by `podman inspect compose_db_1` showing `POSTGRES_PASSWORD=`
   empty while `compose_api_1` has it. The header comment at line 19 documents an intent
   ("POSTGRES_PASSWORD comes from ../.env (env_file)") that is never implemented for `db`.
   **Invisible for the life of a volume** — an initialized `PGDATA` doesn't need the password at
   start-up — which is why five phases never hit it. The Phase-03 keeper firing on the deploy layer.
   **Blocks Task 35 / SC7**, and blocks any first-ever self-hosted deploy following `.env.example`'s
   documented `cp .env.example .env` + `podman-compose -f compose/compose.yml up -d`. Task 8 unblocked
   itself user-side (`set -a; . ./.env; set +a`) without touching product config, so the fresh-volume
   proof stands. Fix approach is an owner decision (secret-spread trade-off) — see `## Deviations`.

6. **`verify_purchasing.py` leaks `po_receipt` journal entries** — its `_cleanup` removes the PO, lines
   and inventory txns but not the auto-posted JE, so every run permanently adds to 1130/2150. This is
   the source of the phantom 4950.00. Already BACKLOG p3 from Phase 4; Task 8 measured it at exactly
   50.00 per twelve-script sweep and it makes any "TB on a shared dev DB" literal untrustworthy.

7. **Three follow-ups from the `U0` fix** (Task 8a): (a) the commented-out module stubs at
   `compose/compose.yml:111-157` all carry `env_file: ../.env` — whoever uncomments `plum-worker` etc.
   will reintroduce U0 in a new service; the pin covers only `db` and `api`, so extending it to any
   uncommented service is a cheap follow-up. (b) **`.env.example` no longer defines
   `POSTGRES_PASSWORD`, so anyone with an existing `.env` and no `.env.db` gets a broken stack after
   pulling `4ace2c4`** — the api starts and fails to authenticate. A troubleshooting row covers the db
   symptom; an upgrade note belongs in the release path (`CHANGELOG.md` is generated, so not edited
   here). (c) **`pytest` is absent from the api image** — see the corrected verified-commands entry in
   `## Context`; Task 33's regression gate must use the host venv, not `podman exec`.

8. **Seeding takes ~40 s on an empty database** (all create paths) — state it in the Task-11 runbook so
   the owner does not assume it has hung.

9. **Three follow-ups from the pre-flight** (Tasks 9/10): (a) `verify_ap.py`, `verify_reports.py`,
   `verify_purchasing.py`, `verify_inventory.py`, `verify_gl.py` (mostly) and `verify_gelato_ship.py`
   use **no scenario letters**, so their citations are `check()`-label substrings — greppable today, but
   they break silently if anyone reformats a label. Cheap hardening: give those scripts scenario letters
   like their siblings. (b) `routes/admin/Modules.tsx` has no vitest and no check row of its own — it is
   exercised only *through* `C-SC6-d`; if the Modules screen itself should be checked it needs a row.
   (c) **The plan's own Task 12–14 verify greps are now trivially satisfiable** — `grep -qF "CORE-05"`
   matches the check ID `C-CORE-05` as well as the requirement, so requirement coverage would prove
   nothing. Tasks 12–14 must use a delimited pattern (e.g. `grep -qF "(CORE-05)"`) instead.

10. **Two follow-ups from the `U1` fix** (Task 10a): (a) **`PREFLIGHT.md`'s `C-CORE-04` row is now stale**
    — it tells the owner to expect a **500** and marks the row known-failing. Task 12 must true it up to
    "expect a clean 409 naming the address", or the two documents contradict each other in front of the
    owner. (b) **`create_user` silently ignores an unknown `role_name`** (`if role:` with no else): an
    admin who typos a role gets a 201 and a user with *no* role, which via `getVisibleModules` means an
    **empty sidebar**. Not U1 and not in scope there, but the same "ordinary operator mistake handled
    badly" family — `C-CORE-03` may surface it.

11. **Three follow-ups from authoring the runbook** (Tasks 11–15): (a) **`C-CORE-02` needs a ~15-minute
    idle wait** (access-token expiry). Written as "start it, go do other checks, come back", but it is the
    one check that cannot be done in sequence — if sittings run shorter than 15 minutes it may never get
    exercised. Watch for it at Task 32's reconciliation. (b) **`C-SYERP-11`'s expected moving average
    `10.125` is a forward prediction, not a manifest literal** — `(4×12.25 + 4×8) / 8`, derivable from
    manifested inputs and labelled as an expected outcome. It is the runbook's only forward-computed
    number; if the owner sees something else, re-check the inputs first. (c) **A markdown formatter
    rewrote `.zj/UAT-v4.0.md` mid-authoring.** Content survived and all checks pass, but if that
    formatter sits in a pre-commit hook it may reflow the tables on future edits.

12. **Three follow-ups from executing the runbook** (Task 16): (a) the `until curl` readiness loop added
    at T16 **has no timeout** — if the stack genuinely cannot start (a repeat of `U0`) the owner gets a
    silent infinite spin instead of an error; bounding it with a "give up and check
    `podman logs compose_api_1`" hint is kinder and is being done. (b) **`:5173` returns 200 for
    `/no-such-page`** — correct for a SPA (the shell loads, the router decides), but it means
    `C-CORE-07`'s unknown-path check can never be verified by status code; it is purely about what the
    rendered page says. (c) `docs/tasks/chore-human-uat.md` is now ~370 lines and is doing two jobs
    (checklist + evidence archive); if it keeps growing the manifests belong in a linked artifact.

13. **SC8's hole is now asymmetric — `post_transfer` and MOUSSE `issue_components` still trust their bins**
    (Task 18/19 finding). Their docstrings (`inventory.py:826-827`, `:998-999`) claim bin membership "is
    GELATO's domain and is checked by the caller" — exactly what `post_adjustment`'s said until Task 18.
    `post_transfer`'s `from_bin_id` and each issue line's `bin_id` are reachable from the API with a
    mismatched pair. SC8 scoped only the positive-adjust path so they were deliberately not touched, but
    the hole is the same shape. **→ p2 BACKLOG item at Task 38.** Also: SC8's 422 names the location by
    numeric id (`"Bin 5 does not exist at location 6"`), matching the existing house style rather than
    diverging — if the `C-SC6-a` pool-floor toast wording gets fixed, fix this with it. And
    `verify_gelato.py` is now the slowest non-API script — the one to watch if `verify-scripts` ever
    starts timing out.

14. **`.zj/codebase/MAP.md` is materially stale** (generated 2026-07-04 at `2329803`): Concern 1 (the `SyerpPartner` blocker) and Concern 5 ("No CI") are resolved; the registry list omits `gelato` (registered at `main.py:82`); the FE lint entry still cites `.eslintrc.cjs`, deleted in Phase 1. A fuller refresh is already BACKLOG p3 — worth pulling forward at the v4.0 milestone close, not in this phase.

## Deviations

- **T0 (trivial) — branch cut off the plan-carrying tip, not `c02d80b`.** D-P5-9 named `c02d80b`,
  but that commit predates the plan commit `4171605`, so the branch dropped `PLAN.md` entirely.
  Fast-forwarded to `4171605`, which is **docs-only** (`git diff --stat c02d80b 4171605` = `.zj/STATE.md`
  + `.zj/phases/05-human-uat/PLAN.md`, zero product code) and therefore code-identical to the named
  base. `c02d80b` remains an ancestor. Same trivial deviation logged in Phases 3, 4, and 13.
- **T2 (trivial) — the fixture role is built with the ORM upsert `auth/seed.py` uses, not a service
  function.** `auth.service` exposes no `create_role`; roles are seed data (D-09) and no router or UI
  path creates one. `create_user(role_name=…)`/`update_user(role_name=…)` only *attach* an existing
  role. The drive-real-services rule is not weakened: the fixture **user** is created through
  `auth.service.create_user` and the role is consumed through it. The `plum:read` permission row is
  never minted — the builder raises loudly if the startup seed has not created it.
- **T2 (trivial) — archiving drives `update_partner(PartnerUpdate(active=False))`, not the
  `archive_partner()` alias.** `PATCH /syerp/partners/{id}` (`router.py:299`) routes archiving through
  `update_partner`; nothing calls `archive_partner`. The fixture takes the path the UI takes.
- **T3 (trivial) — the PLUM cost tree departs from `.zj/UAT-v1.0.md`'s literals on purpose.** A fifth
  part (`UAT-P105`, a **second costed leaf**) was added, moving the rolled-up total from v1.0's
  `110.00` to **`99.15`**. Reason is the Phase-2b keeper: with a single costed leaf the roll-up total
  is structurally identical to that leaf's extended cost, so a footer printing one flat row would look
  correct. With two costed leaves no single flat row equals `99.15`, and the v1.0 D1 triple-count bug
  now yields `239.40` — unmistakably distinct. Other wrong formulas land on 57.90 / 90.75 / 27.95.
- **T3 (trivial) — a second, non-preferred AVL link** (`UAT-VEND-2` on `UAT-P402`) beyond the one the
  task asked for: a Preferred-badge check with a single row cannot fail.
- **T3 (trivial) — lossless Decimal formatting in `Manifest.value()`.** `Numeric(_,6)` roll-ups return
  `99.150000000000000000000000`; the manifest strips trailing zeros with no rounding or quantize, so a
  genuine `99.154` still prints in full and Task 8's diff still catches drift. The single rounded
  literal is the separately-labelled `margin_pct_2dp` (the exact percentage is 28 non-terminating
  digits; the UI paints `-59.66`).
- **T3 (trivial) — `_ensure_cost` skips the write when values already match.** An unconditional PATCH
  appends a `part.cost_updated` audit row every run — manifest-identical but not actually idempotent.
- **T4 (trivial) — PO natural key is the header `notes` marker** (`UAT-PO-DRAFT` / `UAT-PO-APPROVED`),
  not `po_number`: the number is server-generated and cannot key a get-or-create. The generated
  `PO-####` is recorded via `Manifest.value()`.
- **T4 (trivial) — the Approved PO draws on `UAT-ITEM-2`, not the two-receipt `UAT-ITEM-1`.** Pointing
  it at ITEM-1 would mean Task 27's receiving moves the exact moving-average literals Task 24's
  read-only checks quote. Fixture-poisoning avoided by construction, not only by ordering.
- **T4 (trivial) — archived `UAT-ITEM-3` carries zero stock** (the task said "each item"): an archived
  item holding stock is a contradictory state that would muddy valuation checks; its only job is to
  give the show-archived toggle something to hide. Zeros recorded as literals.
- **T4 (trivial) — receipt idempotency keyed on the value tuple** `(item, location, qty, unit_cost)`,
  since an append-only ledger row has no natural key.
- **T4 (note, not a deviation) — this layer contributes exactly zero to the trial balance.** Standalone
  `post_receipt` writes an `InventoryTxn` and moves the moving average but posts **no** JE; only PO
  `receive_line` does (Dr 1130 / Cr 2150), and neither PO has been received. Proven, not assumed
  (`JEs from UAT PO lines: 0`; TB `4950.00 = 4950.00`, all pre-existing dev data). Task 7 inherits a
  clean slate.
- **T5 (trivial) — a third location (`UAT-LOC-NOBIN`) and a fourth item (`UAT-ITEM-4`) added.** The
  zero-pool crux and the no-bins branch both need stock that cannot disturb Task 4's literals, so this
  layer uses its own item rather than fully binning a Task-4 one (ITEM-1/2 stay 7/6 and 4). Bonus: at
  `UAT-LOC-A`, `UAT-ITEM-4` is fully binned (pool 0 → must name a bin) while `UAT-ITEM-1`'s 6 sit
  entirely unbinned (pool 6 → drawable with none named) — **the same dialog must behave differently for
  two items one row apart**. Bin-free location is a dedicated `UAT-LOC-NOBIN`, not `Main` (the
  `verify_*` scripts create/clean bins there, so its bin-free-ness isn't guaranteeable) and not
  `UAT-LOC-ARCH` (an archived location may not be offered at all, testing nothing). Consequence: the
  inventory reporter describes the whole DB, so the Task-4 manifest block grew to 4 items / 3 locations.
- **T5 (trivial) — putaway idempotency keyed on the resulting ledger leg**, not the bin's current
  on-hand, so an owner moving that stock mid-UAT doesn't make a re-seed 422 against an empty pool.
- **T5 (crux proven, not assumed) — the zero unbinned pool genuinely rejects.** A NULL-bin `-1`
  adjustment against `UAT-ITEM-4 @ UAT-LOC-A` returns `HTTP 422: Adjustment of -1 exceeds the unbinned
  pool at location 374 (current 0).` — the **D-P4-1 pool floor**, not the per-location floor (which
  could not have fired: the location holds 15). Red for the intended reason, per the Phase-4 keeper;
  the rejection wrote no ledger row (6 before, 6 after). Roll-up invariant asserted every run:
  `Σ(bins) 15 + unbinned 0 == location total 15`; putaway legs sum to exactly 0 at location grain.
- **T6 (trivial) — a dedicated Released build target (`UAT-P501` + children), not Task 3's `UAT-P301`.**
  Release snapshots only the Released revision's *direct* children and `UAT-P301` has exactly one; SC6
  check (c) is about **per-line** independence, which a one-line dialog cannot demonstrate. Side
  benefit: MOUSSE churn never touches the part whose read-only-ness Task 21 checks.
- **T6 (trivial) — four new inventory items (`UAT-ITEM-5..8`).** Components must resolve to linked stock
  items or `release_work_order` 422s the snapshot; the FG must too or completion cannot receive it; the
  SO needs pickable stock that doesn't disturb `UAT-ITEM-4`'s Task-5 literals.
- **T6 (trivial) — two opportunities, and the SO/quote natural keys are markers.** A quote number is
  server-generated, so the opportunity link is a quote's only stable key → two quotes need two
  opportunities (`UAT-OPP-1` at `proposal`, `UAT-OPP-2` at `qualify`, which also populates two pipeline
  columns). `SalesOrder` has neither a client-settable number nor a notes column, so its key is a
  marker in the line description (`UAT-SO-1`), which doubles as an on-screen label.
- **T6 (trivial, good judgment) — the reservation clamp is NOT re-proved by the fixture.** The SO
  reserves 11 of an available 25; over-ordering to force a shortage would complicate Tasks 30/31, and
  `verify_crumb_so.py` scenarios E/F already pin the `min(ordered, available)` clamp and the
  concurrent-confirm race. SC3's prefer-citation-over-new-code rule, applied to fixtures. The fixture
  still discriminates: wrong `reserved = on_hand` reads 25, a missing reservation reads 0.
- **T6 (trivial) — no dates in the manifest** (`wo_date`/`order_date` default to today and would make it
  run-varying); interactions use fixed `occurred_at` constants so newest-first ordering is deterministic
  rather than a microsecond race.
- **T6 (SC6 (c) made observable) — one `IssueComponentsDialog` shows two lines with opposite bin
  requirements.** At `UAT-LOC-A` the Released WO's comp A (`UAT-ITEM-5`, 20) is **fully binned → pool 0
  → the line MUST name a bin**, while comp B (`UAT-ITEM-6`, 30) is **entirely unbinned → issues with no
  bin**. Both pool states are asserted by `_expect` every run, so fixture drift that would quietly void
  the check fails the seed instead. Money-loop head proven reachable, not just seeded: GELATO's own
  pick-list builder resolves `SO-0001` to `UAT-BIN-A2` holding 25 against a reserved 11. Soft
  reservation posts **no** JE (tripwire clear).
- **T7 (trivial) — the manual JE posts to 5290/1110, not to a control account.** Both aging reports tie
  their subledger total to the GL control (1120 / 2110); a manual JE on a control would move it without
  a matching subledger document, breaking `in_balance` and **manufacturing a false defect** for the
  owner to report at Task 23. Fixture-design choice, not a posting-rule change.
- **T7 (trivial) — AR/AP run on their own documents, keeping the money loop pristine.** AR uses its own
  `SO-0002` / `UAT-ITEM-10` / shipment; AP uses its own third PO (`UAT-PO-BILLED`) / `UAT-ITEM-9`.
  Proven, not asserted: `SO-0001` still `confirmed, picked 0, shipped 0, invoiced 0` with its
  `UAT-BIN-A2` stock of 25 unconsumed, and `PO-0002` still `approved, received 0`. Task 27's receive
  subject and Task 30/31's ship→invoice subject are untouched while Task 23 gets fully posted books.
- **T7 (trivial) — a fourth bin `UAT-BIN-STAGE`** (`execute_pick` requires a staging bin), so the Task-5
  literal `gelato.bins_at.UAT-LOC-A` becomes **4, not 3**. Convenient: Task 30's owner pick needs one.
- **T7 (trivial) — the P&L uses a rolling 365-day window**, not YTD (a YTD window would silently drop
  the 70-day-old invoice if the seed ran in early January). Window length recorded as a literal.
  Aging ages are **relative offsets**, never fixed dates, so buckets don't drift as the calendar moves.
- **T7 (trivial) — three read-schema gaps worked around in the script, no product change:** `BillRead`
  has no `paid_amount` (derived `total − open_balance`), `JournalEntryRead` has no
  `total_debit`/`total_credit` (summed from lines), `profit_loss()` needs an explicit window.
- **T7 (TB proven either side)** — before `4950.00 = 4950.00` (2 rows), after **`5541.25 = 5541.25`
  (8 rows)** spanning assets/liabilities/revenue/expense, net exactly zero. `_expect` asserts the zero
  net, `in_balance`, and **both** aging tie-outs every run, so a later layer that unbalances the books
  fails the seed rather than surfacing as a phantom defect at Task 23.
- **T8 (MATERIAL → owner) — `U0`: the stack cannot start on a fresh volume at all.** See
  `## Noticed` #6. Escalated to the owner rather than fixed in a fixtures task; blocks Task 35 / SC7.
- **T8 (trivial) — the fixture needed an opening capital contribution.** On a fresh volume the books
  balanced but the Balance Sheet reported **negative total assets** (−258.25): the fixture pays a bill
  (36.50) and a professional-services expense (412.75) out of a 1110 Cash account that was never
  funded, collecting only 55.25. No assertion caught it because the books *were* in balance, and dev
  data's 4950.00 of GR/IR inventory had masked it. An owner reading that at Task 23 would reasonably
  report "total assets is negative" — a **false** defect, same class as T7's manual-JE-on-a-control
  problem. Fixed by posting `Dr 1110 / Cr 3110 Capital Contributions 8,250.00` through the real
  service: touches neither the 1120/2110 controls (both aging tie-outs still 84.25 / 57.75,
  `in_balance`) nor revenue/expense (net income still −316). `report()` now asserts
  `total_assets > 0` so the state cannot return silently. The volume was destroyed and the whole cycle
  redone post-fix, so the recorded diff proves the *shipped* fixture.
- **T8 (finding) — the dev DB's 4950.00 GR/IR was litter, not data.** `verify_purchasing.py`'s cleanup
  drops the PO, its lines and its stock txns but **not** the auto-posted `po_receipt` journal entry.
  Measured: running the twelve verify scripts against the fresh seeded volume added exactly 50.00 to
  total debit, total credit and total liabilities and left an orphaned JE with no PO. Repeated over
  many phases, that is the whole 4950.00. Consequence: **aggregate** TB/BS figures are whole-ledger and
  drift if any `verify_*` runs against the same DB; the fixture-specific literals (document numbers,
  aging buckets, 1120/2110 controls) do not move. The volume was reset a third time and seeded once so
  the live stack matches the recorded manifest byte-for-byte.
- **T8a — `U0` fixed per D-P5-10** (`4ace2c4` fix + `d870233` pin). Three forced deviations beyond the
  task block, all necessary rather than scope creep: (1) the db `environment:` block was removed
  **entirely**, not just the password line — an `environment:` entry takes precedence over `env_file`, so
  leaving `POSTGRES_DB`/`POSTGRES_USER` would have kept overriding `.env.db` with their *defaults*;
  (2) the **healthcheck** interpolated `${POSTGRES_USER:-app}`/`${POSTGRES_DB:-biznice}`, which resolved
  only because those values were shell-visible in `.env` — once they live solely in `.env.db` it would
  silently fall back to defaults, so a non-default user/db would make `db` never go healthy and `api`
  (`depends_on: service_healthy`) never start; rewritten to `$$POSTGRES_USER`/`$$POSTGRES_DB` (verified
  unescaped correctly by podman-compose 1.0.6); (3) the three DB keys were stripped from the real `.env`,
  because leaving duplicates there would have let `api` work even if `.env.db` were not wired to it,
  making the `podman inspect` verification prove nothing. `api` reads **both** env files (it must
  authenticate to Postgres). `compose/compose.dev.yml` was checked first and has **no `db` service**.
  **Proof:** clean shell (`env | grep POSTGRES` → 0 matches), documented command alone on a fresh volume
  → `/health/ready` ok, `alembic current` `0017 (head)`, no `set -a` workaround; `podman inspect` shows
  `POSTGRES_PASSWORD` non-empty on `db` and **zero** `JWT_SECRET`/`BNS_ADMIN_*` on `db`; re-seeded
  manifest **byte-identical** to the Task-8 record. **Pin** `backend/tests/test_compose_config.py` (4
  tests, structural-textual not PyYAML — PyYAML is in the local venv but declared in neither
  requirements file, so `import yaml` would `ImportError` in CI, a RED for the wrong reason). The test
  **strips comments before matching**, which is load-bearing: the pre-fix file carried the comment
  *"POSTGRES_PASSWORD comes from ../.env (env_file)"*, so a naive substring search would have **passed
  against the broken config**. RED-on-revert executed with the corrected header comment left in place so
  the RED cannot come from prose; RED is an `AssertionError` on the empty `env_files` list, and the
  secret-spread guard on the line above **passed**, confirming it did not hijack red. Full suite
  **236 passed** (232 + 4).
- **T9/T10 — 48 checks mapped, 309 citations, zero misses.** Check-ID scheme is `C-`-prefixed and
  **suite-local** (`C-CORE-01`, `C-PLUM-04`, `C-SC6-a`) so a check can never be confused with an SRD
  requirement (`CORE-05` vs `C-CORE-05`) and Tasks 11–15 can insert checks without renumbering anything
  the owner has already reported against. 41 rows carry a citation, 7 are `machine-unproven` (1 probed,
  6 deliberately not, each with a per-row reason). The citation checker caught a **real miscitation**
  before commit (a Putaway test title copied from StockTransferDialog, missing "as a toast"); its own
  first version cried wolf with 38 false misses and was rewritten rather than trusted. Module-toggle
  propagation is `C-SC6-d`, not a CORE check, keeping the toggle's blast radius inside Task 26.
  `getVisibleModules` probe **mutation-exercised**: swapping the `enabled` check and the admin wildcard
  turns 2 named tests RED for the intended reason (order-sensitive cases, not a compile error), product
  code restored byte-identical. That ordering is load-bearing — wildcard-first would mean toggling
  GELATO off changes nothing for the admin who just toggled it, so `C-SC6-d` would silently pass while
  the feature was broken. FE suite 44/139 → **45/148**, lint exit 0.
- **T9 (transient product-code touch, disclosed) —** `AppShell.tsx` was mutated and reverted for the
  mutation proof. Nothing ships (`git diff --stat` empty); recorded so it cannot surface as a surprise.
- **T10a — `U1` fixed** (`f508554` fix + `f67f085` pin), **409** matching the house convention: every
  sibling rejecting a caller-supplied unique key uses `409 "<Thing> '<value>' already exists."`
  (`partners.py:112`, `items.py:154`, `locations.py:49`, `plum/service.py:334`); the lone 422 outlier
  (`bins.py:59`) is a composite-key pre-check. Mechanism is a **pre-check plus a narrowed
  `IntegrityError` backstop** for the read-then-write race — explicitly *not* a broad except, because
  `users` carries **two** unique indexes (`users_pkey`, `ix_users_email`, confirmed against the live
  schema), so a broad handler would report a PK collision or role-FK failure as "that email already
  exists" and send the operator to debug the wrong thing — the Phase-13 `create_invoice` failure in
  miniature. The constraint name's location was **measured, not guessed**: the outer `IntegrityError`
  does not carry it, `exc.orig.__cause__.constraint_name` does. `update_user` was checked and does
  **not** share the hole (`UserUpdate` has no email field; no route can move one user's address onto
  another's) — pinned anyway by `test_update_user_cannot_change_an_email` so the guard travels if anyone
  adds email editing. **No-partial-row proven** rather than inferred: users 2→3 across a 201 then a 409,
  exactly one row for the address carrying the **first** request's `full_name`, exactly one
  `user.created` audit row. **RED signature is U1 itself** — an unhandled `UniqueViolationError` on
  `ix_users_email` propagating out of the `INSERT`, with the two non-DB tests staying green under the
  revert, which is the discriminator that the failure is localised to the missing guard. Full suite
  **240 passed** (236 + 4).
- **T11–15 — `.zj/UAT-v4.0.md` authored, 1,574 lines, 59 checks.** Status rows 59 ↔ check sections 59,
  perfect 1:1, all `todo`. **63 distinct quoted literals traced to the Task-8 manifest, 0 misses.**
  The tracer caught two literals quoted from a **live query rather than the manifest** — `PO-0003` and
  `UAT-PO-BILLED` (the GL/AP/AR reporter records `po_number` for only the two POs it reports, so the
  third PO's number is genuinely not in the manifest); the fixture table now describes that PO by its
  *manifested* attributes instead and says why no number is given.
- **T12–14 (trivial) — the plan's requirement-coverage greps were replaced with delimited ones.** Bounded
  on **both** sides (`[(,] ?ID[,)]`) so they match mid-list occurrences like `(SYERP-01, SYERP-02, …)`;
  a first attempt anchoring only the left side missed those. Demonstrated non-pedantic: a file containing
  only `C-SYERP-02` **passes** `grep -qF "SYERP-02"` and correctly **fails** the delimited form.
- **T12/13 (trivial) — four SYERP requirements were covered but unlabelled**, and were labelled rather
  than padded with new checks: `SYERP-02/03/04/05` (vendor search, customer CRUD, customer search, GL
  skeleton). `C-SYERP-01` now exercises both screens' searches incl. a no-match case; `C-SYERP-02` now
  creates/edits/archives a **customer as well as** a vendor (both screens share `PartnerSheet.tsx`, so a
  regression in one may not show in the other). `CORE-01/07/09` have **no click of their own** and the
  doc says so out loud instead of inventing checks — they are exercised by the fresh-volume bring-up
  (which is what caught `U0`), by `C-SC6-d`'s toggle, and by the audit assertions cited throughout.
- **T11–15 (trivial, self-caught) — two arithmetic errors in the engineer's own prior work, disclosed:**
  (1) `PREFLIGHT.md`'s headline said "48 planned checks" while its rows enumerate **58** — D-P5-1's
  "~40–50" target had been copied into the summary instead of counting the rows; per-row content was
  always correct. Corrected in place with a dated note; derived figures re-derived to **49** cited and
  **9** machine-unproven checks across **7** register rows (`C-CRUMB-02/04/05` share a row — the source
  of the 7-vs-9 discrepancy). (2) `C-SYERP-20` is a 59th check, **appended** so no existing ID moved.
- **T15 — `C-SC6-d` is written as an observation, not an assertion**, per `## Noticed` #1: the doc states
  there is no server-side module gate and that the dialogs' own comments are probably wrong about the
  cause, with eight "record what you saw" steps and a mandatory re-enable plus a `psql` verification.
  `C-PLUM-07` (below-cost red) has **no** machine citation and cannot have one — written as pure residue
  with an explicit contrast (`UAT-P104` red vs `UAT-P301` not), because "is it red" alone is
  unfalsifiable if everything is red.
- **T11–15 — ordering made explicit on the checks themselves**, not merely implied by task order: the
  `C-CRUMB-07 → C-GELATO-03 → C-SYERP-20` chain carries a dependency banner on each check, `C-CRUMB-07`
  tells the owner **not to cancel `SO-0001`** (create your own draft SO to exercise confirm), and the
  GL/AP/AR read-only checks are scheduled before any receiving that posts to the ledger.
- **D-P5-1 amended (owner, AskUserQuestion, 2026-07-26) — keep all 59 checks.** The runbook came out at
  59 against D-P5-1's "~40–50, est. 2–3 h". The overage is structural, not padding: 59 is the **exact sum
  of the plan's own per-suite maxima** (6+13+20+4+8+4+4), so the per-suite instructions and the aggregate
  estimate never agreed. Owner chose full coverage over the estimate — D-P5-1's binding words were
  "residue-only, **full coverage**"; the count was an estimate, not a cap, and D-P5-7's resumable status
  table means the extra hour need not be one sitting. Rejected: trimming ~9–12 thinnest-residue checks
  (either owner- or engineer-selected) and reordering to front-load the machine-unproven surfaces.
  Runbook estimate raised to **~3 h** across eleven suggested sittings.
- **T16 — three runbook bugs found by executing it, all doc bugs (no `U#` assigned).** (1) **The health
  check as written failed**: the doc said *"Wait for ready (a few seconds)"* as **prose** and then printed
  a bare `curl`, which returns `curl: (56) Recv failure: Connection reset by peer`. A prose wait is not a
  command; an owner pasting the block concludes the stack is broken. Replaced with a real
  `until curl -sf …; do sleep 2; done` and the error documented so it reads "not yet", not "broken". The
  few-second window is what makes it insidious — it bites some owners and not others. (2) **The seed is
  ~5 s, not ~40 s** — the engineer's own Task-8 claim (which this plan had recorded) was wrong; measured
  on a genuinely fresh volume exercising every create path. Corrected in both places. Whole bring-up is
  **~30 s**, not the several minutes the old wording implied. (3) `alembic current` emits two `INFO` lines
  first; the doc now shows all three and says so. **Corrected block re-run verbatim** on a
  freshly-destroyed volume rather than trusted by reading, and the resulting manifest is **identical** to
  the Task-8 record — nothing to reconcile. Admin login confirmed both directly and **through the Vite
  `/api` proxy** (`:5173` returning 200 does not prove login works from the browser; nothing had tested
  the proxy), and the admin keys confirmed still in `.env` after Task 8a moved the DB keys to `.env.db`.
- **T17 — pointer lines added, `git diff --numstat` shows 5/0 and 4/0: zero deletions on both.** The
  plan's carried-forward counts were verified against the files rather than trusted: v1.0 is 10 todo +
  2 pass = 12, v2.0 is 14 of 14.
- **T18/T19 — SC8 landed** (`e57c1ff` check + `0a7a89f` pin). One raw-SQL probe, **no gelato import**
  (`grep -n 'gelato'` shows comments and the raw table name only — D-P12a-3 holds). Pre-flight found a
  collateral risk the task block did not name: `tests/syerp/test_inventory.py::test_adjustment_does_not_move_moving_average`
  does `inspect.getsource(post_adjustment)` and asserts `"compute_new_moving_avg"` / `"moving_avg_cost ="`
  are absent **from the source including the docstring**, so the docstring rewrite had to avoid both
  strings; it does, and the test passes. **NULL path confirmed untouched** — a NULL negative draw is still
  rejected by the *original* pool floor with its *original* message, which is what keeps the SC6 fixture
  design valid (`UAT-ITEM-4`'s zero-pool rejection still comes from the pool floor, not from SC8).
  Matching pair still succeeds per D-P4-6 (bin on-hand rose by exactly the delta).
  **Scenario (G) RED is unambiguous:** G1 reported `status=None rows 1->2` — *no exception at all* and a
  ledger row written, i.e. stock booked into a bin at the wrong location. The reasoning that it can only
  be the missing probe: G1 uses a **positive** delta, and D-P4-6 gives positive deltas **no floor guard**,
  so neither floor exists on that path to steal the red; the FK is **satisfied** because location A's bin
  genuinely exists (it fires only on G2, which crashed the script with an unhandled
  `ForeignKeyViolationError` — a 500 to a client); both 404 guards pass. G2's crash independently confirms
  the docstring's claim that the FK "catches only a bin that does not exist at all; it cannot see the
  membership half". Restored → GREEN, all four G assertions pass. Gates: 5 `verify_*` + `pytest
  tests/syerp` 105 + full suite **240 passed** + ruff exit 0.
- **T19 (trivial) — the pin commit carries three files.** The runbook wait-loop bound (a manager
  instruction folded into this task) and the RED-signature log (Task 19's own Done-when) ride with it;
  splitting would have produced a commit whose message described work not in it. Both paths of the
  bounded loop were tested verbatim — happy (`0.05 s`) and dead-port (`"STILL NOT UP after 2 min. Check:
  podman logs compose_api_1"`, 6 s) — not just the happy one.

## Out of scope

- **Any new end-user capability.** v4.0 ships none; the only product-code changes authorized are UAT defect fixes and the SC8 check (tripwires above).
- **The other p2/p3 findings from Phase 4** — `pick_for_shipment` unsorted item locks, the pick-path shipment-header races (Q1/Q2), `TransactionRead` omitting `bin_id`, pre-lock `moving_avg_cost` staleness. They stay in BACKLOG.
- **FLAN** (prototype only, never re-platformed) and **CRISP** (planned, no code) — nothing to click through.
- **PLUM-11..16** (advanced PLM) and **NFR-3** (offline) — not built.
- **A full `.zj/codebase/MAP.md` refresh** (`## Noticed` #4) — BACKLOG p3, better done at the milestone close.
- **Master-merge / tagging / the milestone audit** — `/zj:verify 5`, `/zj:retro 5`, then `/zj:milestone` handle those; this phase closes NFR-8 only.
- **Performance, load, accessibility, and cross-browser testing** — NFR-8 is a functional click-through.
