# Verification: Phase 08 — SYERP Extended: inventory & purchasing
Date: 2026-07-08 | Commits: `b5c5c31~1..554c3fe` (`feature-syerp-inventory-purchasing`)
Verdict: PASS (with two owner-accepted deferrals, logged BACKLOG p1)

The phase goal is **functionally delivered and empirically proven** — the full inventory +
purchasing flow was driven against live Postgres and every assertion passed. Initial verdict was
GAPS FOUND; the fix loop below resolved the one code defect and the owner accepted the remaining
regression-protection gaps as owned deferrals (2026-07-08).

## Fix loop (2026-07-08)
- **Resolved [major, code] — `plum_part_id` → HTTP 500** (reviewer finding). `create_item`/
  `update_item` misclassified an FK `IntegrityError` on a bad `plum_part_id` as a code collision
  (retry re-raised → 500). Fixed in `554c3fe`: `_validate_plum_part` rejects a non-existent link
  with a clean 422 up front (D-P8-2 — the PLUM link is advisory and must degrade). Guarded by a new
  `verify_inventory.py` assertion. **Re-verified fully green after the fix** (counts below).
- **Accepted-deferral [major ×3] — no automated regression protection for the crux (11.4),
  audit (10.7/11.7), and RBAC (10.8/11.8)** (verifier gaps 1–3). Root cause is the broken async
  live-DB pytest harness (D-P7-4, already BACKLOG p1). Owner elected 2026-07-08 to close on the
  live-proven behavior (D-P7-5 precedent) and repair the harness + port the verify-script assertions
  into runnable integration tests as its own p1 task. Recorded in `.zj/BACKLOG.md`.

## Re-verification after fix (all green)
- `backend/.venv/bin/python -m pytest tests/syerp/test_inventory.py tests/syerp/test_purchasing.py`
  → **55 passed, 1 skipped**, exit 0 (unchanged — no regression).
- Live DB (`compose_db_1` healthy + `compose_api_1`, `PYTHONPATH=/app`): `verify_inventory.py`
  **15/15** (new bad-link → 4xx assertion), `verify_purchasing.py` **18/18**, `verify_e2e_p8.py`
  **18/18** — all exit 0.

---

## Original report (initial verdict: GAPS FOUND)

The phase goal is **functionally true today** — I empirically drove the full flow against live
Postgres and every assertion passed. The verdict is GAPS FOUND because the phase's crux
integration and the audit/RBAC criteria have **no automated regression protection**: their only
proof is standalone `verify_*.py` scripts that no suite runs, plus (for audit) no test exercises
the router where `write_audit` actually lives. Functionality passes; durability of that pass does
not.

## Commands run (real output)
- `backend/.venv/bin/python -m pytest tests/syerp/test_inventory.py tests/syerp/test_purchasing.py -q`
  → **55 passed, 1 skipped** (0.08s). The 1 skip is a live-DB test (`skip_if_no_db`).
- `frontend: npm run test` → **47 passed (17 files)**, exit 0.
- `frontend: npm run build` (`tsc -b && vite build`) → **built clean, exit 0** (tsc no errors).
- Live DB via running `compose_db_1` (healthy) + `compose_api_1` container, `PYTHONPATH=/app`:
  - `python scripts/verify_inventory.py` → **14/14 PASS, exit 0** (avg exactly 3.000000; on-hand
    value 60.000000; negative-adjustment rejected with no row; transfer nets zero, two legs share
    `transfer_group_id`; `Main` seed idempotent).
  - `python scripts/verify_purchasing.py` → **18/18 PASS, exit 0** (approve stamps approver;
    partial receive → `partially_received`, on-hand +4, avg 5.000000; over-receipt raises 422 with
    no mutation; full receipt → `received`; vendor total 50; exactly two real `receipt` txns
    source-linked to the PO line).
  - `python scripts/verify_e2e_p8.py` → **18/18 PASS, exit 0** (fresh-DB flow: seeded `Main`,
    Draft→Approved→partial→remainder, on-hand 10 @ avg 5.000000 value 50.000000, weighted second
    item 10@2 then 10@4 → 3.000000).
- Note: `ruff` not installed in `.venv`/image and `npm run lint` broken repo-wide (no flat ESLint
  config) — **neither lint gate ran this phase** (PLAN "Noticed" T9). `tsc -b` is the only enforced
  static check and it is clean.

## Source-read confirmations (exists → wired)
- **On-hand is derived, not stored** (10.3): `InventoryItem` (models.py:164-197) has **no quantity
  column** — only by-design `moving_avg_cost` (Decision 4). `get_item_onhand` (service.py:688-698)
  is `SUM(quantity) GROUP BY location` over the ledger. PASS.
- **Moving-average is pure Decimal** (10.5): `compute_new_moving_avg` (service.py:773-801) uses the
  exact formula, `.quantize(Decimal("0.000001"), ROUND_HALF_UP)`, no float. PASS.
- **Ledger immutable/append-only** (10.4): `InventoryTxn` rows only ever inserted; no update/delete
  path in service. PASS.
- **Receiving crux atomic** (11.4): `receive_line` (service.py:1686-1782) guards status → qty>0 →
  over-receipt **before any mutation**, then calls the real `post_receipt(..., commit=False)`,
  increments `qty_received`, rolls up status, single `db.commit()`. PASS.
- **FSM server-enforced** (11.1): `PO_TRANSITIONS` (service.py:1587-1593) + `advance_po_status`
  rejects illegal transitions with 422. PASS.
- **Vendor-only guard** (11.3): `create_po` (service.py:1378-1384) 422s a missing/non-vendor
  partner. PASS.
- **RBAC on every endpoint**: grep of router.py — all 24 syerp endpoints carry
  `Depends(require_permission("syerp:read"|"syerp:write"))`; reads `read`, writes `write`. Wired.
- **Audit on every mutation**: grep of router.py — `write_audit(...)` present after every POST/
  PATCH/DELETE/approve/close/receive. Wired.
- **Seed wired**: `seed_default_location` registered in `app/core/seed.py:53` (`run_seeds`). PASS.

## Criteria
### SYERP-10.1 Item master + numeric-safe code — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| CRUD + archive, unique code | ✓ | ✓ router GET/POST/GET-one/PATCH | ✓ | verify_inventory create/seed; Vitest InventoryItems |
| numeric-safe generator (int cast, not lexicographic) | ✓ | ✓ `create_item` | ✓ | `test_inventory.py` generator boundary 9→10, non-lexicographic |

### SYERP-10.2 Flat locations — PASS
| CRUD + archive, unique name | ✓ | ✓ | ✓ | verify_inventory builds 2 locations; seed idempotent; Vitest StockLocations |

### SYERP-10.3 On-hand by location (derived) — PASS
| On-hand = SUM(quantity), no stored qty col | ✓ | ✓ `/onhand` endpoint | ✓ | model has no qty col; `test_derive_onhand_*` (pure); verify scripts assert per-location sums |

### SYERP-10.4 Immutable ledger — PASS
| append-only txn w/ type/qty/cost/ts/actor/source | ✓ | ✓ | ✓ | `InventoryTxn` model; verify scripts assert rows appended/source-linked |

### SYERP-10.5 Moving-average valuation (Decimal) — PASS
| weighted formula, scale-6, no float | ✓ | ✓ `post_receipt` | ✓ | `test_moving_avg_*` (pure, exact); live 3.000000 / 5.000000 |

### SYERP-10.6 Adjustment + transfer + negative reject — PASS
| negative-stock 4xx; transfer nets zero | ✓ | ✓ | ✓ | `_adjustment_violates_floor`/underflow pure tests; live reject + net-zero |

### SYERP-10.7 Audit — PASS (exists+wired); works UNVERIFIED
| write_audit on all inventory mutations | ✓ | ✓ router | ✗ not exercised | grep confirms calls; **no test/script drives the router to assert an audit row** (scripts call service fns directly, which do not write audit) |

### SYERP-10.8 RBAC — PASS (exists+wired); works UNVERIFIED for syerp
| syerp:read/write on all endpoints | ✓ | ✓ router | ~ | grep confirms `require_permission`; no syerp-specific 403 test (mechanism covered generically by `tests/auth/test_rbac.py`) |

### SYERP-11.1 PO lifecycle FSM — PASS
| illegal transitions refused server-side 4xx | ✓ | ✓ approve/close | ✓ | `test_po_transitions_*` (pure table); verify_purchasing walks legal+illegal |

### SYERP-11.2 Numeric PO numbering — PASS
| int-cast generator | ✓ | ✓ `create_po` | ✓ | `test_generator_*` (pure); live PO-#### |

### SYERP-11.3 Vendor link + history — PASS
| vendor-only guard; vendor-filtered list w/ totals | ✓ | ✓ | ✓ | `create_po` guard; verify_purchasing vendor filter + total 50 |

### SYERP-11.4 Receiving → SYERP-10 receipt @ line cost, over-receipt reject — PASS (works today; unpinned)
| atomic post_receipt at line cost; over-receipt 4xx | ✓ | ✓ `receive_line` | ✓ | live: 2 real receipts, on-hand/avg move, over-receipt 422, no mutation. **Only proof is verify scripts — no automated suite runs them (gap)** |

### SYERP-11.5 Status roll-up (auto-advance) — PASS
| ordered/received/outstanding; auto → received | ✓ | ✓ | ✓ | `test_rollup_*` (pure); live partial→received |

### SYERP-11.6 No AP — PASS
| no invoice/match/payment models | ✓ | n/a | ✓ | no AP tables in 0007/0008; PO cost only values inventory |

### SYERP-11.7 Audit — PASS (exists+wired); works UNVERIFIED
| write_audit on po.created/approved/closed/received/line_* | ✓ | ✓ router | ✗ not exercised | same as 10.7 — router-level, no test asserts rows |

### SYERP-11.8 RBAC — PASS (exists+wired); works UNVERIFIED for syerp
| gated endpoints | ✓ | ✓ router | ~ | same as 10.8 |

## Regression protection
| Criterion | Pinned by |
|---|---|
| 10.1 code generator | `test_inventory.py::test_generator_*` (pure, repeatable) ✓ |
| 10.1 CRUD wiring | `InventoryItems.test.tsx` (Vitest) ✓ |
| 10.2 locations | `StockLocations.test.tsx` ✓ |
| 10.3 on-hand derivation | `test_inventory.py::test_derive_onhand_*` (pure) ✓ — **but endpoint→DB wiring only in verify scripts (not run by any suite)** |
| 10.4 ledger append | MISSING — only verify scripts (standalone) |
| 10.5 moving-average math | `test_inventory.py::test_moving_avg_*` (pure) ✓ |
| 10.6 negative reject / net-zero | `test_inventory.py::test_adjustment_floor_*`, `test_transfer_*` (pure) ✓ (predicate); service+DB path MISSING (verify scripts only) |
| 10.7 audit | **MISSING** — no test drives the router to assert an audit row |
| 10.8 RBAC (syerp) | partial — `tests/auth/test_rbac.py` (mechanism); syerp-endpoint 403 MISSING |
| 11.1 FSM | `test_purchasing.py::test_po_transitions_*` (pure) ✓ |
| 11.2 PO numbering | `test_purchasing.py::test_generator_*` (pure) ✓ |
| 11.3 vendor history | `PurchaseOrders.test.tsx` (UI); service+DB guard MISSING (verify scripts only) |
| 11.4 receive→on-hand→avg integration | **MISSING** — the phase crux; only `verify_purchasing.py`/`verify_e2e_p8.py`, which no suite runs |
| 11.5 roll-up | `test_purchasing.py::test_rollup_*` (pure) ✓ |
| 11.7 audit | **MISSING** — as 10.7 |
| 11.8 RBAC | partial — as 10.8 |

## Test suite
- Backend pure/generator subset: `pytest tests/syerp/test_inventory.py tests/syerp/test_purchasing.py`
  → **55 passed, 1 skipped**. Live-DB pytest harness broken (D-P7-4, BACKLOG p1) — not relied upon.
- Frontend: **47 passed**, build clean.
- Live scripts (manual, one-off): inventory 14/14, purchasing 18/18, e2e 18/18 — all exit 0.

## Gaps (ranked)
1. **[major] The phase-crux receive→on-hand→moving-average integration (SYERP-11.4) has no automated
   regression protection** — its only proof is `backend/scripts/verify_purchasing.py` /
   `verify_e2e_p8.py`, standalone scripts no pytest/CI run invokes. A silent break would pass every
   automated gate. Root cause: the broken async live-DB pytest harness (D-P7-4). Fix: repair the
   harness (BACKLOG p1) and port the verify-script assertions into runnable pytest integration tests.
2. **[major] Audit (SYERP-10.7 / 11.7) "works" level is entirely unverified.** `write_audit` is
   grep-present on every mutation endpoint in `backend/app/modules/syerp/router.py`, but no test or
   verify script exercises the router — the scripts call service functions directly, and audit is
   written only at the router. Fix: a router-level test asserting an audit row per mutation.
3. **[major] RBAC (SYERP-10.8 / 11.8) has no syerp-specific enforcement test.**
   `require_permission` is on all 24 endpoints (static), but no test asserts a 403 for an
   un-permissioned syerp call; only the generic `tests/auth/test_rbac.py` covers the mechanism.
   Fix: a syerp 401/403 test on one read + one write endpoint.
4. **[minor] Neither lint gate ran this phase** — `ruff` absent from `.venv`/image; `npm run lint`
   broken repo-wide (missing flat `eslint.config.js`). CLAUDE.md's zero-warning policy is unenforced.
   Fix: install ruff + add ESLint flat config (chore before merge/CI).
5. **[minor] Starlette deprecation** — `HTTP_422_UNPROCESSABLE_ENTITY` (deprecated) fires from
   `post_receipt`/`post_adjustment`/`post_transfer`/`receive_line` (`backend/app/modules/syerp/
   service.py`). Cosmetic; sweep to `_CONTENT` before it becomes noise.
6. **[minor] Docs are accurate, not overclaiming** — `.zj/SRD.md`, `requirements-progress.md`, and
   `.zj/UAT-v2.0.md` correctly cite the verify-script PASS counts and mark UI-flow UAT pending; they
   explicitly state no status rests on an unrun live pytest. No doc gap, but they enshrine the
   unrepeatable-script evidence that gaps 1-3 flag — the docs should be updated once automated
   integration tests replace the scripts.
