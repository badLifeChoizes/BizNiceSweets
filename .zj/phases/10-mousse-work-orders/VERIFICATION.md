# Verification: Phase 10 — MOUSSE manufacturing execution core (materials-only)
Date: 2026-07-14 | Commits: d9da607..c263d90 (HEAD c263d90, branch feature-mousse-work-orders)
Verdict: **PASS** (after fix loop — see "Fix loop" section at the bottom). Every functional success criterion (SC1–SC7) PASSES empirically; the phase GOAL is met: a shop can create → release → issue → complete a WO, WIP (1140) clears to zero Decimal-exactly. The initial pass found **GAPS FOUND** — one correctness major surfaced by the reviewer (1130↔subledger drift) plus documentation/source-of-truth staleness (SRD, MAP, requirements-progress); **all were closed in the fix loop** (code fix `5cffeeb` + doc updates), the full regression was re-run 13/13 green, and the verdict is now PASS.

Original-pass verdict (pre-fix, for the record): **GAPS FOUND** — SC1–SC7 all passed empirically; gaps were the reviewer's 1130↔subledger finding and doc staleness.

## Environment confirmation
- `alembic current` = **0012 (head)** in `compose_api_1` — migration applied.
- Live app OpenAPI exposes **8 mousse paths** under `/api/v1/mousse/work-orders*` (9 route registrations); module registered and mounted.
- Fix `3d59068` verified directly: `from app.modules.syerp.service import PO_TRANSITIONS, BILL_TRANSITIONS` imports (5 / 3 entries) — the D-P10-4 split re-export defect is closed.
- Source reviewed: `backend/app/modules/mousse/service.py` + `router.py` (not just script green output).

## Criteria

### SC1 — WO create + single-level BOM snapshot at release + server-enforced FSM — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Create Draft WO, sequential WO-###### | yes | yes | yes | verify_mousse "(A) create_work_order opens a Draft WO with a WO-###### number" |
| Release snapshots DIRECT BOM only (D-P10-5), qty_required = qty_per×planned | yes | yes | yes | "release snapshots exactly the direct-BOM children (2 lines)"; "qty_required == qty_per*planned_qty (A: 2*10==20, B: 3*10==30)"; service.py:441 selects `PlumBomItem` at `parent_revision_id` (not load_flat_bom) |
| No Released revision → 4xx | yes | yes | yes | "(B1) releasing a WO whose part has no Released revision is rejected 4xx" + "persisted NOTHING" |
| Component with no linked InventoryItem → reject whole release 4xx (D-P10-7) | yes | yes | yes | "(B2/D-P10-7) release with an unlinked BOM child is rejected 4xx" + "NO partial snapshot" (service.py:451-460) |
| Illegal FSM transitions → 4xx, server-side | yes | yes | yes | pure `_WO_TRANSITIONS` table (service.py:328) → 409; "(C) completing a Released WO rejected 4xx" |

### SC1b — Pause/resume — PASS
| Truth | Works | Evidence |
|---|---|---|
| In-Progress → hold → On Hold; resume → In Progress | yes | verify_mousse "(A/SC1b) In Progress -> hold -> On Hold" / "resume -> In Progress" |
| Issue blocked while On Hold | yes | "(A/SC1b) issuing while On Hold is rejected 4xx" (service.py:636) |
| Illegal hold/resume → 4xx | yes | "(C/SC1) holding a Released WO rejected 4xx"; "resuming a WO not On Hold rejected 4xx" |

### SC2 — Component issue: signed txns + one balanced Dr1140/Cr1130 JE, atomic, floor-guarded — PASS
| Truth | Works | Evidence |
|---|---|---|
| Signed `issue` InventoryTxn (−qty, source_type="mousse_work_order", source_id=wo.id) at moving_avg | yes | service.py:715-724; "issue decremented each component's on-hand (100-20==80, 100-30==70)" |
| ONE balanced JE **Dr 1140 / Cr 1130** = Σ(qty×moving_avg) | yes | service.py:748-760 (wip debit / inventory credit); "posted ONE balanced JE Dr 1140 210 / Cr 1130 210 (1140==+210, 1130==-210)" |
| Floor-guarded, nothing persists on overdraw | yes | `_adjustment_violates_floor` reused (service.py:700); "(C/SC2) issuing beyond on-hand rejected 4xx … persisted NOTHING" |
| First issue → In Progress; WorkOrderIssue + audit row | yes | service.py:781; "wrote a WorkOrderIssue row per component (2) and flipped to In Progress"; verify_mousse_api "work_order.issued audit row exists" |

### SC3 — Completion clears WIP to zero Decimal-exactly — PASS
| Truth | Works | Evidence |
|---|---|---|
| Receives planned_qty FG at accumulated-WIP unit cost via post_receipt(commit=False) | yes | service.py:904-914; "received planned_qty (10) of FG at 210/10 == 21.000000 and updated FG moving average" |
| ONE JE **Dr 1130 / Cr 1140** for EXACTLY accumulated_wip | yes | service.py:920-933 (credits `accumulated_wip`, not qty×unit_cost — by construction) |
| WO's 1140-attributable balance returns to pre-WO value Decimal-EXACTLY | yes | **CRUX**: "1140 pre_issue=0 after_issue=210.000000 post_complete=0" |
| Under-issue → 4xx unless override_incomplete (audited); override still clears WIP exactly | yes | service.py:881; "(D) completing under-issued WO WITHOUT override rejected 4xx"; "override_incomplete=True COMPLETES"; "override path clears 1140 EXACTLY even though 100/3 leaves a per-unit residual"; router.py:276-293 records short components |

### SC4 — Regression + trial balance nets zero — PASS
| Script | Exit | Evidence |
|---|---|---|
| verify_inventory | 0 | All assertions PASSED |
| verify_purchasing | 0 | All assertions PASSED |
| verify_e2e_p8 | 0 | All assertions PASSED |
| verify_gl | 0 | atomic rollback asserts PASS |
| verify_ap | 0 | All assertions PASSED |
| verify_reports | 0 | "trial_balance total_debit EXACTLY equals total_credit … in_balance True" |
| verify_mousse (own) | 0 | "(E/SC4) after all WO activity the trial balance still nets zero" |

### SC5 — Concurrency: two issues cannot double-consume — PASS
| Truth | Works | Evidence |
|---|---|---|
| Contended InventoryItem rows locked SELECT…FOR UPDATE in sorted-id order before the read | yes | service.py:679-685 (`sorted({item_id})` … `.with_for_update()`) |
| Scenario genuinely forces interleaving (not two sequential requests) | yes | verify_mousse `run_concurrency` uses `asyncio.Barrier(2)` + independent sessions + pre-warmed connections so both enter the read-check-write window together (script comment + code, lines ~955-990) |
| Exactly one wins, on-hand never negative, no double-consume, WIP=only the winner | yes | "EXACTLY ONE succeeds and one fails"; loser "fails with a 4xx"; "final on-hand == 0, exactly one WorkOrderIssue row"; "1140 == 5*4 == 20.000000, not 40" |

### SC6 — Every mutation audited + mousse:write enforced at HTTP — PASS
| Truth | Works | Evidence |
|---|---|---|
| write_audit AFTER service commit on all 7 mutations | yes | router.py:134/161/191/219/243/294/319 (write_audit self-commits, post-mutation) |
| created/released/issued/completed audit rows attributable to actor | yes | verify_mousse_api "work_order.{created,released,issued,completed} audit row exists, attributable to the writer" |
| mousse:write→2xx, read-only→403, unauth→401 on every mutation; reads gated mousse:read | yes | verify_mousse_api sections D & E — 403/401 asserted on create/release/issue/hold/resume/complete/cancel; 200/403/401 on both GETs |

### SC7 — Frontend WO list/create/detail/issue/complete + nav gating + invalidation — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| WO list + hooks + route | yes | yes | yes | WorkOrders.tsx, hooks.ts, App.tsx:80 |
| Create dialog + invalidate | yes | yes | yes | WorkOrderCreateDialog.tsx:148 invalidates workOrdersKey |
| Detail (snapshot lines + on-hand + issued-so-far) + Issue + hold/resume | yes | yes | yes | WorkOrderDetail.tsx, IssueComponentsDialog.tsx; invalidates detail+list (:129-130) |
| Complete action + override checkbox | yes | yes | yes | CompleteWorkOrderDialog.tsx |
| Nav gated on MOUSSE enabled ∩ mousse:read | yes | yes | yes | AppShell.tsx:39-43 (`!enabled`→hide; standard user needs `mousse:read`); Sidebar renders per visible module |
| Vitest + build | — | — | yes | `vitest run src/routes/mousse` → 4 files / 9 tests passed; `npm run build` → built clean |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 (create/release/snapshot/FSM/reject) | `backend/scripts/verify_mousse.py` (sections A, B1, B2, C) |
| SC1b (hold/resume) | `backend/scripts/verify_mousse.py` (A/SC1b, C/SC1) |
| SC2 (issue JE Dr1140/Cr1130, floor) | `backend/scripts/verify_mousse.py` (A, C/SC2) |
| SC3 (WIP clears exact + override) | `backend/scripts/verify_mousse.py` (A CRUX, D/D-P10-9 CRUX) |
| SC4 (regression + trial balance) | `verify_inventory/purchasing/e2e_p8/gl/ap/reports.py` + verify_mousse E/SC4 |
| SC5 (concurrency lock) | `backend/scripts/verify_mousse.py::run_concurrency` (F/SC5) |
| SC6 (RBAC + audit at HTTP) | `backend/scripts/verify_mousse_api.py` |
| SC7 (UI flows) | `frontend/src/routes/mousse/{WorkOrders,WorkOrderDetail}.test.tsx`, `components/{WorkOrderCreateDialog,IssueComponentsDialog}.test.tsx` (9 tests) |

Caveat: all backend regression protection lives in `scripts/verify_*.py` (manually invoked), NOT in pytest — MOUSSE ships zero pytest tests. The plan's own "Noticed/deferred" acknowledges these are not wired into any CI/aggregate runner. This matches the standing D-P7-4 posture (the live-DB pytest harness skips DB-backed tests project-wide), so it is accepted debt, not a new phase-10 regression — but the criteria are protected only when someone runs the scripts.

## Test suite
- Backend verify scripts (in `compose_api_1`, PYTHONPATH=/app): verify_mousse **exit 0** (34 PASS), verify_mousse_api **exit 0** (34 PASS), 6 regression scripts **all exit 0**.
- Backend pytest: **UNVERIFIED in this environment** — `python -m pytest` = "No module named pytest" (system python lacks it); the dev-overlay-mounted `/app/.venv` interpreter path does not resolve in the container; `pip install` blocked. Could not independently reproduce the build-time 117 passed / 100 skipped claim. Not a phase-10 regression (mousse has no pytest tests; the crux is the verify_* scripts, which all pass). The specific import that pytest *collection* needed (`PO_TRANSITIONS`/`BILL_TRANSITIONS`, fix 3d59068) was verified directly to import.
- Frontend: `vitest run src/routes/mousse` → **9 passed / 4 files**; `npm run build` → **built clean** (only a bundle-size advisory, pre-existing).

## Gaps
1. **MAJOR (doc) — `.zj/SRD.md` MOUSSE-01 not updated.** Still `**Status: planned**` and "MOUSSE-01 still coarse (expand at Phase-10 planning)" (lines 453, 495), with no acceptance criteria and no Verification method — despite the materials-only slice now being built and live-verified. The requirement's source-of-truth entry does not reflect the delivered state; a future reader would think MOUSSE is unstarted. Suggested fix: flip to `partial` (materials-only slice implemented; routing/labor/overhead deferred per D-P10-1), add the SC1–SC7 ACs and cite `verify_mousse.py`/`verify_mousse_api.py` as the verification method.
2. **MAJOR (doc) — `docs/features/requirements-progress.md` has no MOUSSE entry.** CLAUDE.md mandates updating this file when a requirement is completed; there is zero mention of mousse/MOUSSE-01. Suggested fix: add a MOUSSE-01 row citing the phase-10 evidence.
3. **MINOR (doc) — `.zj/codebase/MAP.md` stale.** Line 39 still reads "Head is **0011**" with "MOUSSE adds 0012" in future tense; the map does not list `backend/app/modules/mousse/` as a real (non-placeholder) module or `mousse` among registered modules. Actual head is 0012 and the module is live. Suggested fix: bump the migration/head line to 0012 and add the mousse module to the backend structure section.
4. **MINOR (doc) — `CLAUDE.md` suite-status table.** Line 96 "MOUSSE (MES) | — | Planned" is stale; the module now has backend (`backend/app/modules/mousse/`) + frontend (`frontend/src/routes/mousse/`) code. Suggested fix: update the row to Building with live locations.
5. **MINOR (process) — no automated/CI runner invokes the verify_* scripts or a mousse pytest suite.** Regression protection is real but manual-invocation only (see Regression-protection caveat). Not new to this phase; flagged so a future phase closing D-P7-4 also folds MOUSSE in.

No blockers. No functional gap: SC1–SC7 all proven empirically against the live stack.

---

## Fix loop (manager, /zj:verify 10, 2026-07-16)

The triage merged this report with `REVIEW.md`. Resolutions:

- **MAJOR (correctness, from REVIEW #1) — 1130 control vs inventory subledger drift on completion.**
  The reviewer found (and I confirmed against source) that `complete_work_order` debited 1130 by
  `accumulated_wip` while `post_receipt` capitalises only `planned_qty × fg_unit_cost` into the
  subledger — a permanent sub-quantum divergence on non-divisible WIP (100/3). The verify suite
  missed it (it only asserted 1140-clears + TB-nets-zero). **Fixed `5cffeeb`:** completion now posts
  a 3-line JE (Cr 1140 = accumulated_wip, Dr 1130 = FG receipt value, balancing Dr/Cr to a new seeded
  **5190 Inventory Rounding** account). D-P10-2 amended (owner chose the rounding-sink remedy).
  **Criterion-becomes-test:** `verify_mousse.py` scenario D now asserts the 1130 debit == FG receipt
  value AND 5190 == residual AND receipt_value + 5190 == accumulated_wip. Re-ran the FULL suite after
  the source change: **13/13 verify_* exit 0**, `verify_mousse.py` 34/34, TB still nets zero.
- **MAJOR (doc) — SRD MOUSSE-01 stale + no requirements-progress entry.** Fixed: SRD MOUSSE-01
  rewritten with the delivered materials-only ACs (AC1–AC7), a verification method, and a
  `- **Verified:** 5cffeeb` stamp; PRD-7 traceability row updated; a MOUSSE Module section added to
  `docs/features/requirements-progress.md`.
- **MINOR (doc) — MAP.md + CLAUDE.md.** Fixed: MAP.md head → 0012, mousse listed among registered
  modules; CLAUDE.md suite table MOUSSE row → Building with live locations.
- **MINOR (process) — no CI runner for verify_*.** Unchanged; not new to this phase — folded into the
  standing D-P7-4 harness item (BACKLOG p1).
- **Reviewer question (zero-cost lone component)** logged to PLAN `## Noticed` as a deferred minor.

**Post-fix verdict: PASS.** Phase tagged `zj/good-10-mousse-work-orders`.
