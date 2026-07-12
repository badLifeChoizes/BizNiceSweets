# Plan: Phase 09a — GL posting engine + receipt auto-post
Goal: A user can post/reverse balanced journal entries and view derived account balances, and every PO receipt atomically posts its GR/IR journal entry alongside the stock ledger.
Status: ready
Branch: `feature-syerp-gl-posting-engine` off `master` (D-P9a-2)

## Success criteria
<!-- From the phase brief; each implements SYERP-12 acceptance criteria noted inline. -->
- **SC1** (AC1): A JE with ≥2 lines posts only when Σdebits == Σcredits (else HTTP 4xx); posted entries cannot be edited or deleted; a posted entry can be reversed, producing a new balancing entry that references the original.
- **SC2** (AC2): Each GL account's balance = signed sum of its posted journal lines (no stored balance column); an account-register endpoint + screen shows posted lines for one account over a date range with a running balance.
- **SC3** (AC3): Receiving a PO line atomically writes BOTH the SYERP-10 stock receipt AND a balanced JE Dr 1130 / Cr 2150 at the line's unit cost in ONE DB transaction; if either fails, neither persists. Phase-8 verify scripts still pass unchanged (regression gate).
- **SC4** (AC1 UI): From the UI a user can key + post a balanced manual JE (rejected if unbalanced) and reverse a posted entry; the new GL screens are reachable from SyerpNav.
- **SC5** (AC8/AC9): JE post and JE reversal each write an attributable audit event; all new endpoints are gated by `syerp:read` (GET) / `syerp:write` (mutations).

## Context
Key files (all paths absolute from repo root `/home/zack/Projects/BizNiceSweets/`):
- `backend/app/modules/syerp/models.py` — add `JournalEntry` + `JournalLine`. Mirror the `InventoryTxn` append-only docstring/immutability style (models.py:235). Money = `Numeric(18,6)` never float (D-11). uuid `String(36)` PK like `Partner`/`InventoryTxn`.
- `backend/app/modules/syerp/coa_seed.py` — `_STANDARD_COA` (models.py list, line 40). GR/IR `2150` inserted beside Accounts Payable `2110`, parent `2100`. Two-pass select-before-insert seed (`seed_gl_accounts`, line 97) already handles it; parent `2100` exists.
- `backend/app/modules/syerp/service.py` — pure helper pattern `compute_new_moving_avg` (line 800, `_COST_QUANTUM`/`ROUND_HALF_UP`), `commit: bool` flush-vs-commit pattern in `post_receipt` (line 828), derived-sum pattern `func.sum(InventoryTxn.quantity)` (line 886), receipt hook point `receive_line` (line 1710; `post_receipt(..., commit=False)` at 1785, single `await db.commit()` at 1803), `list_gl_accounts` (line 408).
- `backend/app/modules/syerp/schemas.py`, `router.py` — router mounts `/api/v1/syerp`; reads `Depends(require_permission("syerp:read"))`, writes `syerp:write`; audit via `from app.modules.auth.service import write_audit` written by the router after service success (receipt example router.py:382-417). **NOTE: `write_audit` itself commits (auth/service.py:342)** — call it AFTER the service call has committed, exactly as the receipt endpoint does.
- `backend/alembic/versions/` — head is `0008_syerp_purchasing.py` (`revision="0008"`, `down_revision="0007"`). Add `0009_syerp_gl_journal.py` (`revision="0009"`, `down_revision="0008"`). Runs at boot via `backend/entrypoint.sh` (`alembic upgrade head`). New models must be reachable from `app.core.models`.
- `backend/scripts/verify_purchasing.py` — the standalone live-Postgres verify pattern (own async engine from `POSTGRES_*`, no conftest, real service calls, PASS/FAIL, self-cleanup). Model for the new `verify_gl.py`. **DB-backed pytest is BROKEN (D-P7-4)** — backend truth comes from `verify_*.py` scripts; only pure-Decimal helpers go in runnable pytest.
- `backend/tests/syerp/test_inventory.py` — pure-helper unit-test pattern for `test_gl_journal.py`.
- Frontend: `frontend/src/routes/syerp/GLAccounts.tsx` (read-only screen + `apiClient` + TanStack Query patterns), `frontend/src/routes/syerp/components/SyerpNav.tsx` (tab strip, line 15 `TABS`), `frontend/src/routes/syerp/components/ReceiveLineDialog.tsx` / `StockAdjustDialog.tsx` (dialog form patterns), `frontend/src/App.tsx` (route table; existing `/syerp/gl` at line 53), `frontend/src/api/client.ts` (single axios client). Colocated `*.test.tsx` Vitest; `tsc -b` must stay clean.

Prior decisions honored: D-11 (Decimal money), D-10 (idempotent startup seeds), D-P8-4 (derived on-hand, mirror for derived balances), D-P7-4 (broken pytest → verify scripts), D-P9-1/2/3 (GL/AP/reporting spec). Cite `D-P9a-*` in new code comments for the 9a decisions below.

## Decisions (resolved at planning, 2026-07-11 → D-P9a-1..5; see `.zj/DECISIONS.md`)
1. **JournalEntry / JournalLine field set** — **D-P9a-1, adopted as recommended:**
   - `JournalEntry` (`syerp_journal_entry`): `id String(36) uuid PK`; `entry_date Date NOT NULL`; `memo String(500) NULL`; `source_type String(50) NULL` + `source_id String(36) NULL` (soft link, e.g. `'po_receipt'` + line id — mirrors `InventoryTxn.source_*`, no FK); `reversal_of_id String(36) FK→syerp_journal_entry.id NULL` (self-link; set on reversal entries); `actor_id String(36) NOT NULL`; `created_at DateTime(tz) NOT NULL`. **No mutable status column** — entries are posted-on-create and immutable (append-only, mirroring `InventoryTxn`); "posted" is the only state a row can be in.
   - `JournalLine` (`syerp_journal_line`): `id String(36) uuid PK`; `entry_id String(36) FK→syerp_journal_entry.id NOT NULL index`; `account_id Integer FK→syerp_gl_account.id NOT NULL index`; `line_no Integer NOT NULL`; `debit Numeric(18,6) NULL`; `credit Numeric(18,6) NULL` (exactly one of debit/credit non-null per line, both ≥ 0).
2. **Branch base** — **D-P9a-2: branch `feature-syerp-gl-posting-engine` off `master`.** The architect's draft assumed master was 263 commits behind (D-P8-11), but that debt was **resolved at the v1.0 ship (2026-07-11)**: PR #1 fast-forward-merged `feature-syerp-inventory-purchasing` → `master`, so master now carries Phases 1–8 (`backend/`, `frontend/`, `.zj/` all tracked on master; verified `git ls-files`). The D-P8-11 "branch off the working tip, not master" trap no longer applies — master **is** the working tip. Cut 9a off current `master` (HEAD `f2466d3`).
3. **Endpoint path spellings** — **D-P9a-3, adopted:** `POST /syerp/gl/journal-entries`, `GET /syerp/gl/journal-entries`, `GET /syerp/gl/journal-entries/{id}`, `POST /syerp/gl/journal-entries/{id}/reverse`, `GET /syerp/gl/accounts/{id}/register?from=YYYY-MM-DD&to=YYYY-MM-DD`. (Existing `GET /syerp/gl/accounts` stays.)
4. **Reversal semantics** — **D-P9a-4, adopted:** reversal takes an optional memo (default `"Reversal of {original_id}"`), swaps debit⇄credit on every line, sets `reversal_of_id`, and is dated **today** (current period), not the original's date. Revisit only if the owner needs same-period reversals later.
5. **Receipt auto-post audit** — **D-P9a-5, adopted:** the receive endpoint writes BOTH `po.received` AND `gl.journal_posted` audit rows after `receive_line` commits, so AC8 covers the auto-posted JE too.

## Tasks

### [x] 1. Add pure Decimal JE-balance helpers + unit tests
- **Files:** `backend/app/modules/syerp/service.py`, `backend/tests/syerp/test_gl_journal.py` (new)
- **Do:** Add pure (no-DB) helpers mirroring `compute_new_moving_avg` (service.py:800): `_je_totals(lines) -> tuple[Decimal, Decimal]` (Σdebits, Σcredits over line dicts/objects) and `_je_is_balanced(lines) -> bool` (equal totals AND ≥2 lines AND each line has exactly one of debit/credit set, both ≥ 0). Quantize to `Numeric(18,6)`. Add a `_reverse_lines(lines)` pure helper that swaps debit⇄credit. Cite D-11, D-P9a. Write `test_gl_journal.py` covering: balanced 2-line, unbalanced rejected, <2 lines rejected, both-sides-set rejected, negative rejected, reverse swaps sides and stays balanced.
- **Done when:** `pytest backend/tests/syerp/test_gl_journal.py` passes with these cases; helpers import cleanly.
- **Verify:** `cd backend && pytest tests/syerp/test_gl_journal.py -q`
- **Parallel-ok:** yes

### [x] 2. Add JournalEntry + JournalLine models (AC1)
- **Files:** `backend/app/modules/syerp/models.py`
- **Do:** Add the two models per Decision 1, appended after `PurchaseOrderLine`. Copy the `InventoryTxn` immutability docstring language (append-only; corrections are reversing entries, never edits/deletes). Update the module header docstring's phase list. Confirm `app.core.models` already imports the syerp models module (it does — Base.metadata population, verified by verify_purchasing.py:63).
- **Done when:** `python -c "import app.core.models; from app.modules.syerp.models import JournalEntry, JournalLine"` succeeds from `backend/`; both tables appear in `Base.metadata.tables`.
- **Verify:** `cd backend && python -c "import app.core.models; from app.core.base import Base; print('syerp_journal_entry' in Base.metadata.tables, 'syerp_journal_line' in Base.metadata.tables)"`
- **Parallel-ok:** no (blocks 3, 5)

### [x] 3. Add migration 0009_syerp_gl_journal (AC1)
- **Files:** `backend/alembic/versions/0009_syerp_gl_journal.py` (new)
- **Do:** Hand-write the migration mirroring `0008_syerp_purchasing.py` structure (`revision="0009"`, `down_revision="0008"`). `create_table("syerp_journal_entry", ...)` and `create_table("syerp_journal_line", ...)` matching the model columns exactly (uuid PKs, FKs `journal_line.entry_id→journal_entry.id`, `journal_line.account_id→syerp_gl_account.id`, self-FK `reversal_of_id`, `Numeric(18,6)` debit/credit, `server_default=sa.text("now()")` for `created_at`, indexes on `entry_id`/`account_id`/`entry_date`). Provide a real `downgrade()` dropping both tables.
- **Done when:** `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` all succeed against the dev DB with no autogenerate drift.
- **Verify:** run inside the compose api container: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` (dev DB per verify_purchasing.py HOW-TO-RUN block).
- **Parallel-ok:** no (depends on 2; blocks the live verify script)

### [x] 4. Seed GR/IR account 2150 in the standard CoA
- **Files:** `backend/app/modules/syerp/coa_seed.py`
- **Do:** Add `{"code": "2150", "name": "Goods Received Not Invoiced (GR/IR)", "account_type": "LIABILITY", "parent_code": "2100"}` to `_STANDARD_COA` in the LIABILITIES block after `2140`. No seed-function change needed (two-pass idempotent select-before-insert already covers it; parent `2100` pre-exists). Cite D-P9a (new GR/IR account).
- **Done when:** After a startup seed run, `GET /api/v1/syerp/gl/accounts` includes code `2150` (LIABILITY, parent = 2100 id); re-running the seed adds no duplicate.
- **Verify:** in the api container `python -c "import app.modules.syerp.coa_seed as c; print(any(a['code']=='2150' for a in c._STANDARD_COA))"`, plus confirmed live by `verify_gl.py` (Task 9).
- **Parallel-ok:** yes

### [x] 5. Add GL posting/reversal/query service functions (AC1, AC2)
- **Files:** `backend/app/modules/syerp/service.py`
- **Do:** Add:
  - `post_journal_entry(db, *, entry_date, memo, lines, actor_id, source_type=None, source_id=None, reversal_of_id=None, commit=True) -> JournalEntryRead` — validate via `_je_is_balanced` (raise `HTTPException(422)` on unbalanced/<2 lines/bad line); create `JournalEntry` + ordered `JournalLine` rows; follow the `commit: bool` flush-vs-commit pattern from `post_receipt` (line 909) so the receipt path (Task 8) can pass `commit=False`. Resolve `account_id`s; 404 if an account code/id is unknown.
  - `reverse_journal_entry(db, entry_id, actor_id, memo=None) -> JournalEntryRead` — load original (404 if missing); build a new entry via `_reverse_lines`, set `reversal_of_id=entry_id`, `entry_date=today`; reuse `post_journal_entry`. Do NOT edit/delete the original (immutability).
  - `list_journal_entries(db, ...) -> list[JournalEntryRead]` and `get_journal_entry(db, id)`.
  - `get_account_register(db, account_id, date_from, date_to) -> AccountRegisterRead` — posted lines for one account over the date range ordered by `entry_date`, with a Python-computed running balance (`Σdebit − Σcredit`, D-P8-4-style derivation); also expose `derive_account_balance(db, account_id)` = `func.sum(debit) − func.sum(credit)` mirroring service.py:886.
  - Cite D-11, D-P8-4, D-P9a.
- **Done when:** functions import; unbalanced input raises 422; reversal returns a new balanced entry referencing the original. (DB behavior proven by Task 9.)
- **Verify:** `cd backend && python -c "from app.modules.syerp.service import post_journal_entry, reverse_journal_entry, get_account_register, derive_account_balance"`; full behavior via `verify_gl.py` (Task 9).
- **Parallel-ok:** no (depends on 1, 2)

### [x] 6. Add GL Pydantic schemas
- **Files:** `backend/app/modules/syerp/schemas.py`
- **Do:** Add `JournalLineCreate` (account_id, debit?, credit?), `JournalEntryCreate` (entry_date, memo?, lines: list[JournalLineCreate]), `JournalLineRead`, `JournalEntryRead` (with lines, reversal_of_id, actor_id, created_at), `ReverseRequest` (memo?), `AccountRegisterRow` (entry_date, entry_id, memo, debit, credit, running_balance) and `AccountRegisterRead` (account meta + rows + opening/closing balance). Money fields `Decimal`. Add a schema-level validator: exactly one of debit/credit per line, both ≥ 0 (defense-in-depth beside the pure helper).
- **Done when:** schemas import; `JournalEntryCreate` rejects a line with both debit and credit set.
- **Verify:** `cd backend && python -c "from app.modules.syerp.schemas import JournalEntryCreate, JournalEntryRead, AccountRegisterRead"`
- **Parallel-ok:** yes (independent of 5 signature-wise; align field names with Task 5)

### [x] 7. Add GL router endpoints with RBAC + audit (AC1, AC8, AC9)
- **Files:** `backend/app/modules/syerp/router.py`
- **Do:** Add endpoints per Decision 3, mirroring the receipt endpoint (router.py:382): POST journal-entries (`syerp:write`, calls `post_journal_entry`, then `write_audit(action="gl.journal_posted", target_type="journal_entry", target_id=entry.id, detail=...)`); POST `{id}/reverse` (`syerp:write`, calls `reverse_journal_entry`, then `write_audit(action="gl.journal_reversed", ...)`); GET list, GET `{id}`, GET `accounts/{id}/register` (all `syerp:read`). No PUT/DELETE on entries (immutability — enforced by absence). Audit written AFTER the service commit (write_audit self-commits).
- **Done when:** OpenAPI shows the 5 new routes; an un-permissioned token gets 403 on each; unbalanced POST returns 422; there is no edit/delete route for entries.
- **Verify:** curl the running dev api: POST an unbalanced JE → 422; POST balanced → 201; POST `{id}/reverse` → 201; GET register → 200; repeat with a token lacking `syerp:write` → 403 (checked in `verify_gl.py`).
- **Parallel-ok:** no (depends on 5, 6)

### [x] 8. Wire receipt auto-post into receive_line, atomically (AC3, SC3 crux)
- **Files:** `backend/app/modules/syerp/service.py` (`receive_line`, line 1710), `backend/app/modules/syerp/router.py` (receive endpoint audit, per Decision 5)
- **Do:** In `receive_line`, AFTER `post_receipt(..., commit=False)` (line 1785) and BEFORE the single `await db.commit()` (line 1803), insert `await post_journal_entry(db, entry_date=today, memo=f"PO receipt {line.id}", lines=[Dr 1130 amount=qty*unit_cost, Cr 2150 amount=qty*unit_cost], actor_id=actor_id, source_type="po_receipt", source_id=line.id, commit=False)`. Resolve account ids for `1130` and `2150` by code lookup (helper `_gl_account_id_by_code(db, code)`; 500/misconfig if absent — they are seeded). Amount = `qty * unit_cost` quantized to scale 6. The JE, the stock txn, the `qty_received` bump, and the status roll-up now share the one commit — if any raises, nothing persists. Update the `receive_line` docstring to state the JE side-effect. In the router receive endpoint, add the `gl.journal_posted` audit (Decision 5).
- **Done when:** receiving a line creates one balanced JE (Dr 1130 = Cr 2150 = qty×cost) linked `source_type='po_receipt'`; forcing the JE to fail (e.g. temporarily missing 2150) rolls back the stock txn too (no partial persist).
- **Verify:** `verify_gl.py` (Task 9) receipt scenario asserts JE existence + balance + atomicity; regression via Task 10.
- **Parallel-ok:** no (depends on 5; must precede regression Task 10)

### [x] 9. Write verify_gl.py live-Postgres verification script (SC1, SC2, SC3, SC5)
- **Files:** `backend/scripts/verify_gl.py` (new)
- **Do:** Mirror `verify_purchasing.py` (own async engine from `POSTGRES_*`, no conftest, PASS/FAIL prints, non-zero exit on FAIL, self-cleanup in `finally`). Scenarios: (a) post a balanced 2-line JE → succeeds; unbalanced → raises 422. (b) attempt to reverse → new entry references original, original untouched, both persist (immutability). (c) `derive_account_balance` / register: sum of posted lines equals expected, register running balance monotonic over date range. (d) drive `receive_line` end-to-end (create vendor/item/location/PO/approve/receive) and assert a JE Dr 1130 / Cr 2150 at qty×cost was posted in the same transaction as the stock receipt; GR/IR (2150) balance moved by the receipt amount. (e) confirm seeded `2150` exists. Include the run instructions header (compose one-off container) like verify_purchasing.py.
- **Done when:** `python scripts/verify_gl.py` prints all PASS and exits 0 against the live dev DB; re-runnable (cleans up).
- **Verify:** run in the api one-off container: `python scripts/verify_gl.py` → exit 0.
- **Parallel-ok:** no (depends on 3, 4, 5, 7, 8)

### [x] 10. Regression: re-run Phase-8 verify scripts unchanged (SC3 gate)
- **Files:** none (validation only) — exercises `backend/scripts/verify_purchasing.py`, `verify_inventory.py`, `verify_e2e_p8.py`
- **Do:** Run all three Phase-8 verify scripts after Task 8. Confirm on-hand + moving-average assertions still pass (the JE side-effect must not alter stock/valuation). If any fails, the receipt-hook change regressed — fix Task 8 before proceeding.
- **Done when:** all three scripts exit 0 with unchanged PASS counts (e.g. verify_purchasing 18/18).
- **Verify:** in the api container: `python scripts/verify_purchasing.py && python scripts/verify_inventory.py && python scripts/verify_e2e_p8.py`
- **Parallel-ok:** no (depends on 8)

### [x] 11. Frontend: manual Journal Entry list + post dialog (SC4, AC1)
- **Files:** `frontend/src/routes/syerp/JournalEntries.tsx` (new), `frontend/src/routes/syerp/components/JournalEntryDialog.tsx` (new), `frontend/src/routes/syerp/JournalEntries.test.tsx` (new)
- **Do:** List screen (TanStack Query GET `/api/v1/syerp/gl/journal-entries`) reusing `GLAccounts.tsx` layout (`p-8 space-y-6`, `SyerpNav`). A "New journal entry" button opens `JournalEntryDialog` (pattern from `ReceiveLineDialog.tsx`): date, memo, a dynamic multi-line grid (account select from GET `/syerp/gl/accounts`, debit/credit inputs), a live "Debits / Credits / Difference" footer that disables Post until balanced and ≥2 lines. POST on submit; toast via sonner; invalidate the list query. Client-side balance guard mirrors the server 422. Vitest: renders, add-line, balance gate disables/enables Post.
- **Done when:** `npm run test -- JournalEntries` passes; keying an unbalanced entry keeps Post disabled; a balanced entry posts and appears in the list.
- **Verify:** `cd frontend && npm run test -- JournalEntries && npx tsc -b`
- **Parallel-ok:** yes (after 7 exists for the contract; UI mockable)

### [x] 12. Frontend: reverse action + Account Register screen (SC4, SC2)
- **Files:** `frontend/src/routes/syerp/JournalEntries.tsx` (reverse action), `frontend/src/routes/syerp/AccountRegister.tsx` (new), `frontend/src/routes/syerp/AccountRegister.test.tsx` (new)
- **Do:** Add a "Reverse" action on each posted entry (confirm dialog → POST `{id}/reverse` → toast + invalidate). Add `AccountRegister.tsx`: pick an account + from/to date range, GET `/syerp/gl/accounts/{id}/register`, render rows with debit/credit/running-balance columns and opening/closing balance. Reuse `GLAccounts.tsx` Card/layout patterns. Vitest for register rendering + running-balance display.
- **Done when:** `npm run test -- AccountRegister` passes; reversing an entry adds the reversal to the list; register shows a running balance over the selected range.
- **Verify:** `cd frontend && npm run test -- AccountRegister && npx tsc -b`
- **Parallel-ok:** no (depends on 11 for the list screen)

### [x] 13. Frontend: register routes in App.tsx + SyerpNav tabs (SC4)
- **Files:** `frontend/src/App.tsx`, `frontend/src/routes/syerp/components/SyerpNav.tsx`
- **Do:** Import + add routes `/syerp/gl/journal` → `JournalEntries` and `/syerp/gl/register` → `AccountRegister` (beside the existing `/syerp/gl` at App.tsx:53). Add `TABS` entries in `SyerpNav.tsx` (line 15): `{ to: '/syerp/gl/journal', label: 'Journal' }` and `{ to: '/syerp/gl/register', label: 'Account Register' }` (keep "Chart of Accounts").
- **Done when:** the new tabs render and navigate; `tsc -b` clean; the full frontend suite passes.
- **Verify:** `cd frontend && npx tsc -b && npm run test`
- **Parallel-ok:** no (depends on 11, 12)

## Risks
- **Atomicity regression (highest):** the Task-8 hook shares `receive_line`'s single commit; a stray `commit=True` or a `write_audit` mid-transaction (write_audit self-commits) would split the unit of work and let a stock receipt persist without its JE. Early warning: Task 10 Phase-8 scripts pass but `verify_gl.py` atomicity case fails, or a receipt exists with no linked JE. Mitigation: JE posted with `commit=False`; all audit writes happen after `receive_line` returns.
- **Broken DB pytest masks failures (D-P7-4):** if backend correctness is asserted only in `tests/syerp` DB-backed tests they silently skip and look green. Mitigation: every backend SC lands in `verify_gl.py` (live) + pure helpers in `test_gl_journal.py`; do not accept a green pytest as proof of DB behavior.
- **Account-code coupling:** the receipt hook resolves `1130`/`2150` by code; if a deploy renamed/deleted them the hook breaks. Mitigation: codes are seeded (Task 4) and idempotent; hook raises a clear misconfig error, and `verify_gl.py` asserts both exist.
- **Migration drift:** hand-written 0009 diverging from the models causes boot-time or autogenerate mismatch. Mitigation: Task 3 round-trips upgrade/downgrade/upgrade and checks for autogenerate drift.

## Deviations
- **T9/T5 — NULL-propagation balance bug caught by the live proof & fixed (`69ab54e`).**
  `derive_account_balance` and the register `opening_balance` computed
  `func.sum(debit) - func.sum(credit)`; for an account posted on only ONE side (all
  debits, or a credit-only control account like GR/IR 2150) the empty side is SQL `NULL`,
  making the whole expression `NULL`→`0` — a $60 debit account reported $0, the receipt's
  GR/IR movement read as 0. Fixed in service.py to coalesce each sum independently
  (`coalesce(sum(debit),0) - coalesce(sum(credit),0)`); empty-account 0−0=0 preserved. This
  is precisely the defect class the broken DB-pytest (D-P7-4) would have masked — the reason
  verify_gl.py is the backend proof. No assertion was weakened to fit buggy output.
- **T3/T2 — `entry_date` index dropped (trivial, accepted).** The plan listed indexes on
  `entry_id`/`account_id`/`entry_date`, but Task 2's `JournalEntry` model did not declare
  `index=True` on `entry_date`, so migration 0009 omits it to avoid autogenerate drift
  (adding it would make `alembic check` want to remove it). Not a correctness/SC concern —
  the register query filters primarily on the indexed `journal_line.account_id`; entry_date
  ordering is over a single account's small row set. Revisit if register perf ever matters.
- **T6 schema fix (post-commit, `89daadc`).** Task 6 typed four UUID id fields as `int`
  (`JournalEntryRead.id`/`reversal_of_id`, `JournalLineRead.id`, `AccountRegisterRow.entry_id`)
  while the models use `String(36)`. Would have raised `ValidationError` serializing live rows
  in Task 9. Manager-fixed to `str` in a follow-up commit before Task 7/9.
- **T3 — `alembic check` never exits 0 in this repo (pre-existing, Noticed).** 7 unnamed
  `unique=True` constraints reflect from Postgres with names the model metadata lacks, so
  `alembic check` reports spurious `remove_constraint` on master at 0008 already. GL pass
  criterion is "no *new* journal operations detected," which 0009 satisfies. Logged for
  backlog (naming convention on `Base.metadata`).

## Noticed
<!-- Minor items logged during /zj:verify 09a (owner chose the "Recommended set"; these were
     deferred rather than fixed in the loop). Majors M1/M2 + mandated tests M3/M4 + m5/docs were
     fixed — see VERIFICATION.md "Fix-loop resolution". -->
- **Reverse-from-UI has no Vitest (G3/m6).** The "Reverse" action in `JournalEntries.tsx` (added
  in `c2bde3d`) is exercised only by hand. Add a Vitest case mirroring the post-flow test: confirm
  dialog → `POST {id}/reverse` → toast + query invalidate. Backend reversal (incl. the new 409
  double-reversal guard) is covered by `verify_gl.py` (h); this is the UI half only.
- **Migration `server_default=now()` autogenerate drift (cosmetic).** `0009` sets
  `server_default=sa.text("now()")` on `created_at` while the model uses a Python-side `default=`
  only, so `alembic revision --autogenerate` will report drift on the next run. Functionally fine
  (arguably better). Align model and migration if/when autogenerate cleanliness is pursued (relates
  to the pre-existing 7-constraint drift already noted in `## Deviations`).
- **Receipt `entry_date` uses server-local `date.today()` while `created_at` is UTC.** Near
  midnight a receipt and its auto-posted JE can land on different calendar days, splitting them
  across register periods. Acceptable for a single-timezone self-host; switch to
  `datetime.now(timezone.utc).date()` if UTC-consistent periods are ever required.
- **`.zj/codebase/MAP.md` is stale since Phase 8** (it predated 0007/0008 too, not just 0009). The
  migration list was corrected in this verify loop; a fuller refresh (GL endpoints, journal tables,
  the syerp service surface) is owed via `/zj:docs`.
- **No DESIGN.md for this frontend-bearing phase (G5).** Accepted — tasks 11–13 carried explicit
  acceptance criteria in this PLAN. Noted for process.

## Out of scope
- All AP work (vendor bills, 3-way match, payments) — Phase 9b.
- AP aging + financial statements (Trial Balance, P&L, Balance Sheet) — Phase 9c.
- Editing/deleting posted entries (immutable by design; corrections are reversals only).
- GL account CRUD (create/edit/archive accounts) — CoA stays seeded/read-only this phase.
- Period close / fiscal-period locking, multi-currency, and any GL-to-reporting rollups.
- Offline/Service-Worker support for the new screens (standing cross-module concern, not this phase).
