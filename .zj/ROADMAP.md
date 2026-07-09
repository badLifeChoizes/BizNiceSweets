# ROADMAP — BizNiceSweets
Updated: 2026-07-04 (history reconstructed at ZJ adoption from git + GSD artifacts archived at `archive/planning-gsd/`)

## Milestone v1.0 — Foundation + PLUM
**Definition of done:** "Can deploy it, log in, manage vendors/customers, and design parts
with multi-level BOMs and cost roll-up." Status: **one phase from closing** — Phases 1–6
shipped; Phase 7 closes the audited gaps.

### Phase 0: Prototypes & program planning  [done — adopted 2026-07-04]
- **Goal:** Prove the domain logic and plan the re-platform.
- **Delivers:** PLUM v54 prototype (`plum/app/plm_v54.html`, ~31k lines) and FLAN v24
  prototype (`flan/app/prj-mgmt-v24.html`, ~11.5k lines) — both now frozen reference; the
  7-suite architecture decisions, program roadmap, and per-suite docs (`docs/features/`).
- **Evidence:** git era 2025-12 (16 commits: analysis report, suite restructure, decisions,
  roadmap, PLUM/FLAN doc sets); archived `docs/ROADMAP.md` + `docs/decisions.md`.
- **Notes:** reconstructed from git history at adoption.

### Phase 1: Project Scaffolding & Deployment  [done — verified]
- **Goal:** Target stack scaffolded and deployable in one command.
- **Delivers:** CORE-01, CORE-09 — FastAPI + SQLAlchemy async + Alembic backend, React 19 +
  Vite + Tailwind 4 frontend, module registry, Podman Compose (prod + dev overlay),
  auto-migrating entrypoint.
- **Evidence:** `compose/compose.yml`, `backend/entrypoint.sh`, `backend/app/core/registry.py`;
  operator-live checkpoint 23/23 (archived 01-VERIFICATION.md).

### Phase 2: Authentication & Users  [done — verified]
- **Goal:** Real multi-user access control.
- **Delivers:** CORE-02..05 — JWT two-token auth (PyJWT + Argon2), refresh rotation with
  httpOnly cookie + single-flight axios interceptor, admin user management, RBAC
  (User↔Role↔Permission, `module:action` codes), login audit events.
- **Evidence:** `backend/app/modules/auth/`, `backend/tests/auth/` (8 test files),
  `frontend/src/auth/`; human-verified 2026-06-25.

### Phase 3: App Shell & Settings  [done — verified]
- **Goal:** The modular-suite chrome: navigation, settings, module toggles.
- **Delivers:** CORE-06..08 — AppShell (nav = enabled modules ∩ permissions), admin
  Settings + Modules screens, live toggle propagation, always-on SYERP guard, sonner toasts.
- **Evidence:** `frontend/src/components/AppShell.tsx`, `frontend/src/routes/admin/`,
  `backend/app/core/{modules_router,settings_router}.py`; human-verify approved.

### Phase 4: SYERP Core Hub  [done — verified]
- **Goal:** The hub every module FKs into: partners + GL skeleton.
- **Delivers:** SYERP-01..05 — Partner model (vendor/customer flags), Vendors/Customers
  screens with search + archive-via-PATCH, seeded chart of accounts with read-only screen,
  SYERP sub-nav; 4 UAT fixes (Tailwind v4 tokens, country validation, catch-all route, tab strip).
- **Evidence:** `backend/app/modules/syerp/`, `frontend/src/routes/syerp/`,
  `backend/tests/syerp/test_gl.py`; human-verify approved after UAT.

### Phase 5: PLUM Parts & Revisions  [done — verified]
- **Goal:** First real PLUM capability: parts with revision workflow.
- **Delivers:** PLUM-01..03 — parts CRUD/search, revision FSM with DB-level one-Released
  invariant, SemVer/ASME labels, tag join table, audit events, PartsList/PartDetail UI.
- **Evidence:** `backend/app/modules/plum/`, migration 0005, `backend/tests/plum/test_parts.py`
  + `test_revisions.py`, `frontend/src/routes/plum/`; human UAT 10/10.

### Phase 6: PLUM BOM, Costing & Integration  [done — code-complete, verification pending]
- **Goal:** Multi-level product structures, cost analysis, vendor links, import/export.
- **Delivers:** PLUM-04..10 (all partial pending Phase 7) — BOM tree/flat/where-used with
  cycle detection, AVL + price breaks, Decimal effective-cost chain + margin + release
  snapshot, JSON/Excel import-export with preview/commit, PartDetail four cards + ImportExport page.
- **Evidence:** migration 0006, `service.py`/`router.py` (~4k lines combined),
  `backend/tests/plum/{test_bom,test_avl,test_costing,test_import_export}.py`,
  `frontend/src/routes/plum/components/`.
- **Notes:** the only unverified phase — human-verify checkpoint never ran; milestone audit
  (2026-07-01) found the `SyerpPartner` blocker and the part-number bug → Phase 7.

### Phase 7: Close v1.0 gaps  [verified]
- **Goal:** PLUM AVL and vendor import/export work end-to-end without runtime errors,
  auto part-numbering is numerically correct, the Parts List refreshes after import, and
  Phase 6's flows are human-verified with traceability reconciled.
- **Delivers:** PLUM-07, PLUM-10 (fix); PLUM-01 defect (fix); PLUM-04..06, 08, 09 (verify → implemented).
- **Verified 2026-07-09** (`/zj:verify 07`, tip `8975eeb`, tag `zj/good-07-close-v1-0-gaps`):
  SC1/SC2/SC3/SC5/SC6 proven empirically; SC4 met as amended by D-P7-4 (standalone live-Postgres
  proof substitutes for the broken pytest harness) and D-P7-5 (human-UAT owned by `/zj:milestone`).
  Artifacts: `VERIFICATION.md`, `REVIEW.md`.
  - **One blocker found and fixed in the verify fix loop** (`7562a02`): the phase's own SC2 fix cast
    the part-number suffix to int4, so a legal `P9999999999` row made **every** auto-numbered
    `create_part` return 500 permanently — a user-triggerable, persistent DoS. Cast is now `Numeric`.
  - **Criteria became executable tests** (each proven red/green): `scripts/verify_plum_vendor_paths.py`
    (SC1, 8 live assertions across all four alias sites), `scripts/verify_part_numbering.py` (SC2 SQL
    half, 7 live assertions incl. the overflow guard), `tests/plum/test_part_number.py` (SC2 pure
    half, runs in the ordinary pytest suite), `ImportExport.test.tsx` (SC3, positive + negative path).
  - **Still owed:** the 12-check human-UAT (`.zj/UAT-v1.0.md`, 2/12 done) at `/zj:milestone`, and the
    PLUM pytest-harness repair (BACKLOG p1) — the latter no longer leaves any criterion unprotected.
- **Scope (adopted as-is from GSD Phase 7, owner decision 2026-07-04):**
  1. Backend `service.py`: alias/rename `SyerpPartner` → `Partner` at 4 sites + numeric-safe
     `generate_part_number` + live-DB regression coverage.
  2. Frontend: invalidate `['plum','parts']` on import-commit success.
  3. Consolidated human-verify: 7 PLUM flows + 4 regression checks.
  4. Reconcile SRD statuses + `docs/features/requirements-progress.md` (currently falsely
     marks PLUM-07/10 Complete).
  Source plans archived at `archive/planning-gsd/phases/07-*/` (provenance; `/zj:plan 7`
  produces the ZJ PLAN.md).
- **Closes milestone v1.0** (run `/zj:milestone` after verification).

---

## Milestone v2.0 — Operations (SYERP extended + MOUSSE)
Owner decision 2026-07-04: dependency-first order confirmed — operations before FLAN port /
CRM. **Definition of done (draft):** "Can track inventory, raise purchase orders, and execute
work orders that consume PLUM BOMs and inventory." Refine via `/zj:spec` at milestone start.

### Phase 8: SYERP Extended — inventory & purchasing  [done]
- **Goal:** Inventory items (optional PLUM link) with per-location on-hand, immutable
  transaction history, and moving-average valuation; a Draft→Approve→Receive purchase-order
  workflow whose receipts feed inventory. No AP (SYERP-12), no warehouse bins (GELATO-01).
- **Delivers:** SYERP-10, SYERP-11 — built + verified live (Phase 8, branch
  `feature-syerp-inventory-purchasing`, `b5c5c31~1..554c3fe`). All 16 ACs proven against live
  Postgres (`verify_inventory` 15/15, `verify_purchasing` 18/18, `verify_e2e_p8` 18/18 fresh-DB);
  FK-degradation defect fixed in verify (`554c3fe`). Deferred (BACKLOG p1, D-P7-4): port the
  verify-script assertions into runnable integration tests once the async pytest harness is
  repaired; UI-flow human UAT at the v2.0 milestone (`.zj/UAT-v2.0.md`, D-P7-5).
- **Depends on:** SYERP hub (Partner, done) + PLUM parts (done). MOUSSE (Phase 10) and
  GELATO both build on this inventory ledger.
- **Evidence:** `.zj/phases/08-syerp-inventory-purchasing/{PLAN,VERIFICATION,REVIEW}.md`;
  tag `zj/good-08-syerp-inventory-purchasing`.

### Phase 9: SYERP Extended — AP/AR & reporting  [pending]
- **Goal:** Invoice basics and financial reporting on the GL.
- **Delivers:** SYERP-12.

### Phase 10: MOUSSE — manufacturing execution core  [pending]
- **Goal:** Work orders with routing consume PLUM BOMs and SYERP inventory; costs flow back
  to SYERP.
- **Delivers:** MOUSSE-01.
- **Notes:** consider splitting when planned; also the trigger to split `plum/service.py`
  (~3k lines) before the pattern is copied (see BACKLOG).

---

## Later milestones (unordered candidates — sequence at v2.0 close)

- **FLAN port** (FLAN-01) — retire the second frozen prototype.
- **PLUM advanced** (PLUM-11..16) — documents, ECO workflow, labor costing, cost ranges,
  distributor pricing.
- **Customer & logistics** (CRUMB-01, GELATO-01).
- **Quality & release** (CRISP-01, NFR-3 offline, license audit, public open-source release
  prep).
