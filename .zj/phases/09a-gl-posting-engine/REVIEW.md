# Review: Phase 09a — GL posting engine + receipt auto-post (`master..HEAD`, `feature-syerp-gl-posting-engine`)
Date: 2026-07-11

Scope reviewed: `backend/app/modules/syerp/{models,service,router,schemas,coa_seed}.py`,
`backend/alembic/versions/0009_syerp_gl_journal.py`, `backend/app/core/db.py`,
`backend/app/modules/auth/service.py` (write_audit), plus the diff's frontend files.

## Verdict on the stated high-risk areas

- **Atomicity crux — CLEAN.** In `receive_line` (service.py 1919-1962) both `post_receipt`
  and `post_journal_entry` are invoked with `commit=False`; each only `flush()`es
  (service.py 1015-1018, 2140-2143). The single `await db.commit()` is at service.py 1961.
  No `write_audit` runs inside `receive_line` — both audit writes (which self-commit,
  auth/service.py 342) are in the router *after* `receive_line` returns (router.py 873-896).
  `get_db` uses `async with AsyncSessionLocal()` (db.py 24), so any raise before the commit
  discards the flushed rows. A stock receipt cannot persist without its JE.
- **Balance integrity — CLEAN.** Triple-guarded: schema `JournalLineCreate`
  (schemas.py 593-605), pure `_je_is_balanced` (service.py 885-911), and the service call
  (service.py 2098). Amounts are quantized to scale-6 by the *same* `_je_side` used for
  storage (service.py 2124-2125), so the validated sum and the stored value cannot diverge.
  A sub-micro amount that rounds to 0 fails the XOR check → 422 (never stored as a
  double-NULL line). Unbalanced / single-line / negative / both-sided all rejected.
- **NULL-propagation balance fix — PRESENT.** `derive_account_balance` (service.py 2258-2262)
  and the register opening balance (service.py 2291-2303) both use
  `coalesce(sum(debit),0) - coalesce(sum(credit),0)`. Single-sided and empty accounts
  compute correctly; running balance uses `(debit or 0) - (credit or 0)` (service.py 2335).
- **Immutability — CLEAN.** No PUT/DELETE/edit route or service path touches a posted
  entry/line; reversal posts a new entry and never mutates the original (service.py 2169-2188).
- **RBAC — CLEAN.** Every new GET gated `syerp:read`, every POST gated `syerp:write`
  (router.py 905-1054).
- **Migration 0009 — matches models**, incl. uuid PKs, self-FK `reversal_of_id`,
  account/entry FKs, Numeric(18,6), null/not-null, and the two indexes; downgrade drops in
  FK-safe order. Round-trips cleanly (see Questions for a cosmetic-only note).
- **Account-code coupling — safe.** A missing 1130/2150 raises HTTP 500 (service.py 1829-1833)
  before the commit; the whole receipt rolls back (no partial persist).

## Findings

### 1. [major] Zero-cost PO receipt is impossible — the auto-posted JE is all-zero and self-rejects, rolling back the entire receipt
- **Where:** `service.py:1937-1952` (amount + auto-post) against `_je_is_balanced` `service.py:905-909`; reachable because `POLineCreate.unit_cost` is `Field(..., ge=0)` (`schemas.py:435`) and `post_receipt` permits `unit_cost >= 0` (`service.py:981`).
- **Failure:** Create a PO line with `unit_cost = 0` (samples, consignment, RMA/warranty replacements — all schema-legal and legal for a standalone receipt), approve, then receive it. `amount = qty*0 = Decimal("0.000000")`. `post_journal_entry` gets `[{1130, debit:0}, {2150, credit:0}]`; every line reads debit=0/credit=0, so the XOR guard `(debit != 0) == (credit != 0)` is `True` → `_je_is_balanced` returns `False` → HTTP 422 "Journal entry is not a balanced double-entry". Because this raises inside the single transaction, the *valid* stock receipt, the `qty_received` bump, and the status roll-up all roll back. Net effect: a zero-cost PO line can never be received, and the error message is misleading. This is a **regression** — the same receipt succeeded in Phase 8 before the GL hook existed.
- **Fix:** Skip the GL auto-post when `amount == 0` (a zero-value posting carries no accounting information), or reject zero-cost lines earlier with a clear message. Skipping is preferable and keeps the stock path working.

### 2. [major] No guard against reversing an already-reversed entry (or reversing a reversal) — corrupts derived balances
- **Where:** `service.py:2149-2188` (`reverse_journal_entry`) — only checks the target exists (`service.py:2169`); nothing records or blocks that an entry was already reversed, and `reversal_of_id` has no uniqueness constraint.
- **Failure:** Receipt auto-posts JE-A (Dr 1130 100 / Cr 2150 100). An accountant reverses JE-A → JE-B; account 1130 nets to 0. Later a second accountant, unaware, reverses JE-A again → JE-C (another Dr 2150 100 / Cr 1130 100). Account 1130 now derives to **-100** while the stock is still physically on hand and the moving-average valuation still shows +100 — the GL control account silently diverges from inventory. Reversing a reversal (JE-B) has the same class of effect (re-applies the original). In an audit-first ledger this is a real integrity gap.
- **Fix:** Before posting, reject if an entry with `reversal_of_id == entry_id` already exists, and/or reject reversing an entry that itself has a non-null `reversal_of_id`. Return 409/422 with a clear message.

### 3. [minor] `gl.journal_posted` audit row from the receive path has no `target_id` — the auto-posted JE is not traceable from the audit log
- **Where:** `router.py:887-896` — `write_audit(... action="gl.journal_posted" ...)` omits `target_id` because `receive_line` returns a `PORead`, not the journal entry.
- **Failure:** After a PO receipt, the audit trail records that *a* GL entry was posted but not *which* one (only free-text `source_id=<line_id>` in `detail`). Traceability from the audit log to the specific `syerp_journal_entry.id` — a first-class concern per the medical-device audit posture — is broken for exactly the entries the system posts automatically. (Manual posts at `router.py:960` set `target_id` correctly.)
- **Fix:** Have `receive_line` return (or expose) the posted JE id and pass it as `target_id`, or look it up by `(source_type='po_receipt', source_id=line_id)` before writing the audit row.

## Questions

- **Migration server_default drift (cosmetic):** the model's `created_at` uses a Python-side
  `default=` only, while `0009` adds `server_default=sa.text("now()")` (migration line 88).
  Functionally fine and arguably better, but `alembic revision --autogenerate` will report drift
  against the model on the next run. Intentional? If not, align the two to keep autogenerate clean.
- **`entry_date` uses `date.today()` (server-local) for the auto-post** (`service.py:1942`) while
  the receipt row's `created_at` is UTC. Near midnight these can land on different calendar days,
  putting the receipt and its JE in different register periods. Acceptable? If UTC-consistency is
  desired, use `datetime.now(timezone.utc).date()`.
