# Verification: Phase 09a — GL posting engine + receipt auto-post
Date: 2026-07-11 | Commits: 8b97fc2..6a44692 (initial) + verify-loop fixes
Verdict: PASS (post fix-loop — see "Fix-loop resolution" below)

> **Original verdict was GAPS FOUND** (phase goal empirically TRUE; two major
> regression-protection gaps + two major review bugs). The manager fix-loop resolved
> every blocker/major and the mandated criteria-become-tests items; the remaining
> items are minors, logged under PLAN.md `## Noticed`. Re-verification after the fixes
> is green (see below). The body of this report is the original empirical evidence.

All five success criteria were verified empirically (exists → wired → works) against the
live Podman stack (`compose_api_1` / `compose_db_1`). The phase behavior is real.

Note: the standalone verify scripts require `PYTHONPATH=/app` inside `compose_api_1` (the
brief's bare `python scripts/verify_gl.py` fails with `ModuleNotFoundError: app`). Correct
invocation used below. Pure pytest ran in `backend/.venv` (the runtime container has no pytest).

## Criteria

### SC1 (AC1) — balanced-only post, immutable, reversible — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| JE ≥2 lines posts only when Σdebit==Σcredit, else 4xx | yes | yes | yes | verify_gl.py: "post_journal_entry persisted a balanced 2-line entry"; "unbalanced (Dr 10/Cr 5) RAISES HTTPException 422"; "rejected entry persisted NOTHING". Live API POST unbalanced → 422 |
| Posted entries cannot be edited/deleted | yes (by absence) | yes | yes | OpenAPI shows only get+post on `/gl/journal-entries`, get on `{id}`, post on `{id}/reverse`; PUT `{id}` → 405, DELETE `{id}` → 405 (proven live) |
| Reversal produces new balancing entry referencing original via `reversal_of_id` | yes | yes | yes | verify_gl.py: "new entry with reversal_of_id == original.id"; "SWAPS every debit/credit"; "ORIGINAL untouched (immutability), reversal_of_id is None"; "BOTH remain queryable"; "reversal moved account A balance by −20" |

### SC2 (AC2) — derived balances + account register — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Balance = signed sum of posted lines; NO stored balance column | yes | yes | yes | `\d syerp_journal_entry`/`syerp_journal_line` have no balance column; `derive_account_balance` = `coalesce(sum(debit),0)-coalesce(sum(credit),0)` (service.py:2260) |
| Single-sided (credit-only) account reports correct non-zero balance (NULL-coalesce fix) | yes | yes | yes | verify_gl.py: "derive_account_balance(B) == −60 (credited only)"; "GR/IR (2150) derived balance moved by −20" — the exact defect the deviation fixed |
| Register endpoint + screen: posted lines for one account over date range with running balance | yes | yes | yes | verify_gl.py: "register over [d1,d3] has 3 rows with strictly MONOTONIC running balance [10,30,60]"; "opening_balance==0 and closing_balance==60". `GET /gl/accounts/{id}/register` in OpenAPI; `AccountRegister.tsx` + test render running balance |

### SC3 (AC3) — atomic receipt → GR/IR journal — PASS (positive proven; rollback unguarded)
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Receiving a PO line posts JE Dr 1130 / Cr 2150 at qty×unit_cost | yes | yes | yes | verify_gl.py: "receiving auto-posted exactly ONE JE source-linked (source_type='po_receipt')"; "balanced Dr 1130 / Cr 2150 at qty×unit_cost == 20"; Inventory +20 / GR-IR −20 |
| Both stock receipt AND JE in ONE transaction; if either fails, neither persists | yes | yes | partial | Architecture sound: `receive_line` calls `post_receipt(commit=False)` (service.py:1919) and `post_journal_entry(commit=False)` (1940), then a single `db.commit()` (1961). **The negative path (force JE fail → stock rolls back) is NOT asserted by any test** — see Gap G1 |
| Phase-8 verify scripts still pass unchanged (regression gate) | yes | yes | yes | verify_purchasing 18/18, verify_inventory 15/15, verify_e2e_p8 18/18 — all exit 0. `git diff master..HEAD` on all three scripts = empty (not weakened) |

### SC4 (AC1 UI) — key/post/reverse JE + reachable screens — PASS (reverse UI untested)
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Key + post a balanced JE, rejected if unbalanced | yes | yes | yes | `JournalEntries.test.tsx` "gates Post on a balanced ≥2-line entry": Post disabled unkeyed → disabled one-sided → enabled balanced → disabled when broken → posts payload. 5 tests pass |
| Reverse a posted entry from UI | yes | yes | partial | Reverse action in `JournalEntries.tsx` (commit c2bde3d); **no frontend test exercises it** — see Gap G3 |
| New GL screens reachable from SyerpNav | yes | yes | yes | `App.tsx:56-57` routes `/syerp/gl/journal`, `/syerp/gl/register`; `SyerpNav.tsx:22-23` tabs "Journal"/"Account Register". `tsc -b` clean; full FE suite 64/64 pass |

### SC5 (AC8/AC9) — audit events + RBAC 403 — PASS (both proven by hand, unguarded)
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| JE post writes attributable `gl.journal_posted` | yes | yes | yes | Live API POST as admin → audit_log row: 1 `gl.journal_posted` for entry, `actor_id == admin.id` (proven this run) |
| JE reversal writes `gl.journal_reversed` | yes | yes | yes | router.py:1029 identical `write_audit` call, unconditional after service commit; POST reverse → 201 (write_audit did not raise); keyed to new entry id, detail cross-references original |
| Receipt path writes `gl.journal_posted` (D-P9a-5) | yes | yes | yes | router.py:884-895 writes it after `receive_line` commits (same `write_audit` mechanism proven above) |
| GET gated by `syerp:read`, mutations by `syerp:write`; no-perm token → 403 | yes | yes | yes | All 5 endpoints `Depends(require_permission(...))`. No-perm token: POST journal-entries → 403, GET register → 403, POST reverse → 403, no token → 401 (proven this run) |
| No PUT/DELETE route on entries | yes | yes | yes | PUT/DELETE `{id}` → 405 (proven live) |

## Regression protection
| Criterion | Pinned by |
|-----------|-----------|
| SC1 balanced-post/reject/reverse | `backend/scripts/verify_gl.py` (live) + `backend/tests/syerp/test_gl_journal.py` (13 pure tests, run in .venv) |
| SC1 immutability (no edit/delete) | verify_gl.py "ORIGINAL untouched" + absence of routes (no negative HTTP test in repo; proven by hand → 405) |
| SC2 derived balance + coalesce fix | verify_gl.py (derive_account_balance B=−60, GR/IR movement) |
| SC2 register/running balance | verify_gl.py + `frontend/src/routes/syerp/AccountRegister.test.tsx` |
| SC3 receipt auto-post (positive) | verify_gl.py scenario (d) |
| SC3 atomicity rollback (negative) | **MISSING (Gap G1)** — no test forces a JE failure to prove the stock txn rolls back |
| SC3 phase-8 non-regression | verify_purchasing.py / verify_inventory.py / verify_e2e_p8.py (unchanged, all green) |
| SC4 post/balance-gate UI | `frontend/src/routes/syerp/JournalEntries.test.tsx` |
| SC4 reverse-from-UI | **MISSING (Gap G3)** — no FE test exercises the reverse action |
| SC5 audit events (posted/reversed/receipt) | **MISSING (Gap G2)** — no test/script asserts any audit_log row; verify_gl drives services directly, bypassing the router where audit is written |
| SC5 403 RBAC path | **MISSING (Gap G2)** — verify_gl.py contains no 403 assertion; proven only by hand this run |

## Test suite
- `PYTHONPATH=/app python scripts/verify_gl.py` (in compose_api_1) → **19/19 PASS, exit 0**
- `verify_purchasing.py` → 18/18 PASS; `verify_inventory.py` → 15/15 PASS; `verify_e2e_p8.py` → 18/18 PASS; all exit 0
- `backend/.venv/bin/python -m pytest tests/syerp/test_gl_journal.py -q` → **13 passed**
- `frontend: npm run test --run` → **20 files, 64 tests passed**; `npx tsc -b` → clean (exit 0)
- Migration: `alembic current` == `0009 (head)`; `syerp_journal_entry` + `syerp_journal_line` exist with columns/FKs/indexes matching models (Numeric(18,6) debit/credit, self-FK `reversal_of_id`, indexes on entry_id/account_id)
- Hand-run this session (not in repo): 403/401/405 RBAC matrix (all as expected); audit_log `gl.journal_posted` row written + attributable to actor

## Deviations corroborated (all 4 real, not papered over)
1. **NULL-propagation coalesce fix** — CONFIRMED. service.py:2260-2261/2293-2294 use `coalesce(sum(),0)` per side; verify_gl proves credit-only B=−60 and GR/IR 2150 movement (the exact defect). No assertion weakened.
2. **entry_date index dropped** — CONFIRMED. `\d syerp_journal_entry` shows no index on `entry_date` (only PK + line indexes on entry_id/account_id). Accepted, non-correctness.
3. **T6 uuid-str schema fix (89daadc)** — CONFIRMED. `JournalEntryRead.id`/`reversal_of_id`, `JournalLineRead.id`, `AccountRegisterRow.entry_id` all typed `str`; live serialization in verify_gl succeeds (would ValidationError if still int).
4. **alembic check spurious drift** — CONFIRMED. `alembic check` reports drift on exactly 7 pre-existing unnamed unique constraints (plum_part.part_number, uq_plum_part_one_released, syerp_gl_account/inventory_item/partner.code, purchase_order.po_number, stock_location.name). **Zero** journal_entry/journal_line operations → 0009 introduces no new drift; GL tables match models.

## Gaps
- **G1 (major) — SC3 atomicity rollback is unguarded.** The highest-risk behavior (Plan Risk #1: a stray commit splits the unit of work, letting a stock receipt persist without its JE) is proven only in the positive direction. Fix: add a scenario to `backend/scripts/verify_gl.py` that forces `post_journal_entry` to fail inside `receive_line` (e.g. monkeypatch `_gl_account_id_by_code("2150")` to raise, or a deliberately unbalanced injected line) and assert BOTH the JE and the stock `InventoryTxn` are absent afterward — the negative half of scenario (d).
- **G2 (major) — SC5 audit events + 403 RBAC path have no automated guard.** `verify_gl.py` drives service functions directly, bypassing the router where `write_audit` and `require_permission` live, so no durable check asserts either; both were provable only by the hand-run in this verification. Fix: add a router-level check (a `verify_gl_api.py` or extend verify_gl) that POSTs a JE + reversal + receipt through the live API and asserts the `audit_log` rows (`gl.journal_posted`/`gl.journal_reversed`) exist and are attributable, plus a no-permission token → 403 on each mutation/read endpoint.
- **G3 (minor) — reverse-from-UI (SC4) has no frontend test.** The reverse action in `JournalEntries.tsx` is untested; add a Vitest case (confirm dialog → POST `{id}/reverse` → invalidate) mirroring the post-flow test.
- **G4 (minor, docs) — SYERP-12 work is undocumented.** `docs/features/requirements-progress.md` has SYERP-10/11 rows but **no SYERP-12 row** (project rule mandates updating it on requirement work); `.zj/SRD.md` SYERP-12 is still "Status: planned" with no Phase-9a evidence line; `.zj/codebase/MAP.md` has no mention of the journal tables / GL endpoints / migration 0009. The only doc touched by the phase was the task checklist.
- **G5 (minor, process) — no DESIGN.md** for the frontend-bearing phase. Acceptable here because tasks 11–13 carry explicit acceptance criteria in PLAN.md, but noted.

## Fix-loop resolution (2026-07-11, manager)

Merged with REVIEW.md (2 major + 1 minor). Owner chose the "Recommended set." Re-verified
live after the fixes — **all green**.

| Item | Source | Disposition |
|------|--------|-------------|
| **M1** zero-cost PO receipt self-rejects (422) → whole receipt rolls back | reviewer (major) | **Fixed** — `receive_line` skips the GL post when `amount == 0`; stock receipt still records. Guard: `verify_gl.py` scenario (g). |
| **M2** no double-reversal guard → derived control account diverges | reviewer (major) | **Fixed** — `reverse_journal_entry` refuses (409) reversing an already-reversed entry or a reversal itself. Guard: `verify_gl.py` scenario (h). |
| **G1** SC3 atomicity rollback unguarded | verifier (major, mandated) | **Fixed** — `verify_gl.py` scenario (f) forces the JE to fail mid-receive and asserts the stock txn + JE both roll back and qty_received is unchanged. |
| **G2** SC5 audit + 403 RBAC unguarded | verifier (major, mandated) | **Fixed** — new `backend/scripts/verify_gl_api.py` (9/9) posts/reverses over live HTTP and asserts the gl.journal_posted/gl.journal_reversed audit rows + 403/401 on every GL endpoint. |
| **m5** receipt `gl.journal_posted` audit row had no `target_id` | reviewer (minor) | **Fixed** — router resolves the just-posted JE by source (`latest_journal_entry_id_for_source`) and targets it; a zero-cost receipt (no JE) writes no phantom row. |
| **G4** docs (requirements-progress / SRD / MAP) | verifier (minor) | **Fixed** — SYERP-12 row added to `requirements-progress.md`; SRD SYERP-12 status + Phase-9a evidence; MAP migration list corrected through 0009. |
| **G3 / m6** reverse-from-UI has no Vitest | verifier (minor) | **Logged** → PLAN.md `## Noticed`. |
| Migration `server_default=now()` autogenerate drift | reviewer (question) | **Logged** → PLAN.md `## Noticed`. |
| Receipt `entry_date` server-local vs UTC (near-midnight period split) | reviewer (question) | **Logged** → PLAN.md `## Noticed`. |
| **G5** no DESIGN.md; MAP fuller refresh owed | verifier (minor/process) | **Logged** → PLAN.md `## Noticed`. |

**Re-verification after fixes (all green):**
- `verify_gl.py` → **28/28 PASS** (was 19; +9 for atomicity-rollback, zero-cost, double-reversal)
- `verify_gl_api.py` (new) → **9/9 PASS** (audit rows + 403/401 RBAC over live HTTP)
- Phase-8 regression (receive_line + receive endpoint changed): `verify_purchasing.py`, `verify_inventory.py`, `verify_e2e_p8.py` → all exit 0, unchanged PASS counts
- `tests/syerp/test_gl_journal.py` → **13 passed**
- Frontend untouched by the fixes → 64/64 + `tsc -b` clean stands from the original run

**Final verdict: PASS.**
