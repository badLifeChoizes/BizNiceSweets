# Milestone v1.0 Audit — Foundation + PLUM
Verdict: GAPS FOUND
Date: 2026-07-09 | Auditor: goal-backward, evidence-only | Stack: live Podman (compose_api_1 / compose_db_1 / compose_frontend_1), dev overlay (DEBUG=true)

**Definition of done (PROJECT.md / ROADMAP.md):** "Can deploy it, log in, manage
vendors/customers, and design parts with multi-level BOMs and cost roll-up."

The four DOD claims are **empirically satisfied at the API/data layer** (login, partner CRUD,
multi-level BOM, exact-Decimal cost roll-up, margin, AVL, JSON round-trip — all driven live and
correct). The verdict is GAPS FOUND for three reasons, none of which breaks the DOD sentence:
a real **where-used UI-label defect** (PLUM-06), a **broken Excel export in the deployed image**
(PLUM-10), and the **entire DB-backed pytest suite silently skipping** (regression protection
rests on 5 verify scripts + frontend vitest only).

---

## DOD results

| DOD | Claim | Result | Evidence |
|-----|-------|--------|----------|
| DOD-1 | Deploy it — one-command Podman, migrations auto-run, app serves | **PASS (caveats)** | Stack up; `/health/ready` → `{"status":"ok","db":"connected"}` 200; `alembic current` = `0008 (head)`, chain 0001→0008 clean & auto-run by `entrypoint.sh`; `/openapi.json` 200. Caveats below. |
| DOD-2 | Log in — JWT, refresh, RBAC | **PASS** | `POST /auth/login` 200 (access token + httpOnly refresh cookie); `/auth/me` → admin, `*` perm; `POST /auth/refresh` 200 rotates; bad password 401; no-token `/auth/me` 401; un-permissioned partner create 401. |
| DOD-3 | Manage vendors/customers — CRUD + search + archive | **PASS** | Live drive of `/syerp/partners`: create vendor (auto `P-0001`) + customer; neither-flag → 422; `?q=` narrows; `?role=vendor/customer` filters; PATCH edit; PATCH `active=false` archives → hidden from default list, shown with `include_archived=true`. |
| DOD-4 | Design parts w/ multi-level BOM + cost roll-up | **PASS at API (1 UI defect)** | See below. |

### DOD-1 caveats
- Running the **dev overlay**: SPA is served by **Vite on :5173** (200). FastAPI root on :8000 returns 404 because `frontend/dist` is absent from the api image (mount is dir-guarded). The **prod** SPA-serving path is code-confirmed (`Containerfile` builds+copies `frontend/dist`; `main.py:106` mounts `SPAStaticFiles`) but **not exercised** in this deployment.
- **openpyxl is not installed in the running api image** → `GET /plum/export/excel` returns **HTTP 500** (`ModuleNotFoundError: openpyxl`). This is image staleness (BACKLOG), not a code regression — `openpyxl 3.1.5` is a declared dependency.
- Migrations run to `0008` (Phase 8 inventory/purchasing) — beyond the v1.0 target of `0006` because the audit ran on branch `feature-syerp-inventory-purchasing`; all apply cleanly.

### DOD-4 detail — driven live, all arithmetic exact Decimal
Built TOP→MID→SUB→LEAF (grandparent→parent→child→leaf), with SUB shared by both TOP and MID:
- **Multi-level tree** (`GET .../bom`): TOP→MID(3)→SUB(2)→LEAF(4) and TOP→SUB(5)→LEAF(4). Structure correct.
- **Flat roll-up** (`GET .../bom/flat`): SUB appears **exactly once**, `total_qty = 11` (direct 5 + via MID 3×2=6); LEAF `total_qty = 44` (11×4); MID = 3. Shared-part dedup + summed qty proven.
- **Where-used** (`GET .../where-used`) of LEAF: API correctly returns SUB `direct=true`; MID `direct=false,indirect=true`; TOP `indirect=true`. **Backend analysis correct.** (UI label defect — see gaps.)
- **Cost roll-up** (`GET .../cost`): TOP `effective_cost = 110.000000` source `roll-up` = 3×(2×(4×2.50)) + 5×(4×2.50). Exact.
- **Margin**: sale 150 → margin `40`, margin_pct `36.36…` (= margin/effective_cost, consistent with prior audit's 30/20=150% convention); sale 50 → margin `-60` (drives `text-destructive` styling, code-confirmed at PartDetail.tsx:1131/1137/1213).
- **AVL**: link LEAF→vendor persists on re-GET (preferred=true, vendor_part_number retained); non-vendor partner → **422**; price-break + `selected_vendor_link_id` → effective_cost `3.000000` source `vendor price`.
- **JSON round-trip** (multipart): export 8 parts → validate/preview/commit all **200** (`inserted 0, updated 8`); parts count 8→8 (**upsert, no delete**); unknown `vendor_code` → reported as validation **error** (not 500); **11 MB upload → HTTP 413** "File exceeds 10 MB limit."

---

## Verify scripts (backend/scripts/verify_*.py) — run in compose_api_1

| Script | Result |
|--------|--------|
| `verify_plum_vendor_paths.py` (SC1, 4 alias sites) | **8/8 PASS**, exit 0 |
| `verify_part_numbering.py` (SC2, incl. int4-overflow guard) | **7/7 PASS**, exit 0 |
| `verify_inventory.py` (SYERP-10) | **15/15 PASS**, exit 0 |
| `verify_purchasing.py` (SYERP-11) | **18/18 PASS**, exit 0 |
| `verify_e2e_p8.py` (fresh-DB e2e) | **18/18 PASS**, exit 0 |
| **Total** | **66/66 live assertions PASS** |

## Test suites

- **Backend pytest** (`python -m pytest`, in compose_api_1): **90 passed, 98 skipped**. **All 98 skips are the same reason: "No live database available — skipping DB-dependent test"** — i.e. the async pytest harness cannot reach Postgres (D-P7-4 / BACKLOG p1). The 98 skips break down: **auth 38, syerp 17, plum 34, core 7, misc 2**. The SRD's phrasing ("PLUM DB tests silently skip") *understates* this — the skip affects the **entire** DB-backed suite across every module, not just PLUM. What actually runs = 90 pure/non-DB tests (schema/FSM/generator/Decimal units).
- **Frontend vitest** (`npx vitest run`, in compose_frontend_1): **49 passed / 17 files**, 0 failures.

## NFR checks

- **NFR-1 (audit trail):** PROVEN live. `audit_log` holds attributable rows for every mutating flow exercised: `auth.login_success` (8), `auth.login_failed` (1), `partner.created/updated/archived`, `part.created` (8), `bom.line_added` (4), `avl.link_added` (7), `avl.price_break_added`, `part.cost_updated` (5), `plum.exported/imported`. Honest.
- **NFR-2 (permissive licenses):** status "implemented (unaudited)" — **honest**; no formal audit performed (backlog). Not verified here.

---

## FR status accuracy

**No FR is more optimistic than reality.** Every `implemented` FR I exercised (CORE-01/02/03/05/09,
SYERP-01..04) holds. Critically, PLUM-06 is marked **`partial (unverified)`** and that caution is
**vindicated** — the UI label is in fact defective (below). The `partial` gate did its job.

**FRs that are more pessimistic than reality (backend fully provable now; only visual residue):**
- **PLUM-04** (BOM tree) — 3-level structure proven live. *(Note: the tree endpoint returns `effective_cost=null` per node; cost is only populated in the flat view. Minor, not a DOD miss.)*
- **PLUM-05** (flat roll-up) — dedup + summed qty + extended cost fully proven; no defect found. Only "renders as one row + footer total" is visual.
- **PLUM-08** (cost roll-up) — all three sources (manual 2.50 / roll-up 110 / vendor-price 3.00) proven exact.
- **PLUM-09** (margin) — margin, margin_pct, and negative-margin→`text-destructive` logic all present/correct; only the red *color* is human-visual.
- **PLUM-07** (AVL) — persist + non-vendor 422 + vendor-price source all proven; only "Preferred badge" visual + vendor-picker UX remain.

These stay `partial` by the deliberate D-P7-5 policy (UI confirmation deferred to milestone UAT),
so the pessimism is by-design — but note the backends are now fully machine-provable.

---

## UAT residue — what a machine CANNOT close (the 10 `todo` checks)

| # | Machine-proven now | Genuine human-only residue |
|---|---|---|
| 2 | Flat data: SUB one row, qty 11, extended cost (API) | Visual: renders as a single row; "Total BOM Cost" footer shows |
| 3 | Backend direct/indirect correct (API) | **UI is BROKEN (see gap G1)** — label always shows "Direct parent"; "Indirect via {part}" never appears. Not just visual: a real defect. |
| 4 | Link persists after refresh; preferred/vendor_part_number retained (API) | Visual: "Preferred" badge renders; vendor-picker dropdown UX |
| 5 | All 3 cost sources exact (API) | Visual: card shows the source label |
| 6 | margin/margin_pct exact; negative→`text-destructive` class logic (code) | Visual only: the actual **red color** rendering |
| 7 | JSON export + re-import 0 errors + upsert-no-delete + >10MB→413 (API) | **Excel export broken in image (G2)**; "No records were deleted" toast text visual |
| 9 | AVL add returns 201, no 500 (API) | Visual: **absence** of an error toast |
| 10 | Import w/ vendor previews+commits 200, no 500; unknown vendor → error not 500 (API) | Visual: absence of an error toast |
| 11 | Cache-invalidation fires — pinned by `ImportExport.test.tsx` (vitest green) | Visual: list visibly updates with no manual refresh |
| 12 | Auto-number P100001..P100004 unique past P100000 boundary, no dup-key (API); `verify_part_numbering` 7/7 | Essentially none — UI "New Part" is a thin wrapper; human confirms the form |

**Checks a machine genuinely cannot close (report to owner):** 6 (red color), 9 & 10 (toast
*absence*), 2 & 4 (badge/one-row/footer visual affordances), 11 (visible no-refresh — though
vitest pins the mechanism). Check 3 is worse than "human-only" — it will **fail** for a human
because of defect G1. Check 7 cannot pass until the image ships `openpyxl` (G2).

---

## Gaps

- **G1 — MAJOR (unprotected UI defect, PLUM-06 / UAT check 3).** `frontend/src/routes/plum/PartDetail.tsx`
  keys the where-used label (line 1274-1276) and sort (line 518-519) **solely** on
  `entry.via_part_number`, a field the backend `WhereUsedRow` schema **never returns** (live API
  confirmed: rows carry `direct`/`indirect` booleans, no `via_part_number`). Result: every
  where-used row — including truly indirect parents (MID, TOP) — renders as **"Direct parent"**,
  and "Indirect via {part}" is **never** shown. The backend analysis is correct; the UI ignores it.
  No test covers the label. **Fix:** either have the API populate `via_part_number` (add the
  intermediate part to `WhereUsedRow` + service), or rewrite the UI to use the `direct`/`indirect`
  booleans; add a vitest asserting an indirect row shows the indirect label.
- **G2 — MAJOR (deployed-image, PLUM-10 / UAT check 7).** `GET /plum/export/excel` → **HTTP 500**,
  `ModuleNotFoundError: No module named 'openpyxl'` in compose_api_1. Code + requirements are
  correct (`openpyxl 3.1.5` declared); the **running image is stale**. **Fix:** rebuild the api
  image so Excel export works before the human runs check 7 (already on BACKLOG p1).
- **G3 — MAJOR (regression protection, D-P7-4 / BACKLOG p1).** The async pytest harness reaches no
  DB, so **98 DB-backed tests across auth/syerp/plum/core silently SKIP** — including every
  partner, part, revision, BOM, AVL, costing, and RBAC integration test. Only 90 pure-unit tests
  run. DB-level regression protection for the DOD currently rests **entirely** on the 5
  `verify_*.py` scripts (66 assertions) + 49 frontend vitest tests. Repairing the harness would
  re-arm ~98 checks. **Fix:** repair the harness and port the verify-script assertions into it.
- **G4 — MINOR (BOM tree cost).** `GET .../bom` tree nodes return `effective_cost=null` /
  `effective_cost_source=null` even where the flat/cost endpoints compute real costs. If the BOM
  card is meant to show per-node cost, it will show blank. Confirm intended, or populate.

## Bottom line
The v1.0 DOD is **empirically true at the API/data layer** — deploy, login, vendors/customers, and
multi-level BOM with exact cost roll-up all work and are proven live. But the **product** ships one
real UI defect (where-used labels, G1), a **broken Excel export in the deployed image** (G2), and
carries its DB regression protection almost entirely outside the pytest suite (G3). These are the
items a milestone-close human UAT would surface; close G1/G2 before declaring v1.0 done.
