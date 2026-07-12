# Review: Phase 09b — AP bills, PO match & payments (`c1b431b..f7b51ba`)
Date: 2026-07-12

Scope reviewed: `syerp` backend (models, schemas, service, router, coa_seed),
migration 0010, and the four new frontend AP screens. The three trailing 09a-doc
commits were ignored per the brief.

## Findings

### 1. [major] No row-level lock — concurrent requests defeat the double-bill and overpayment guards  — ✅ FIXED (verify fix-loop 2026-07-12)
> **Resolution:** `create_bill` now `SELECT … FOR UPDATE`-locks each matched PO-line row, and `record_payment` locks each target bill row, both acquired up-front in sorted id order (deadlock-safe), before the guard read. The second transaction blocks until the first commits and then re-reads the true billed/paid sum, so the exact-match / overpayment guards hold under concurrency. Pinned by new `verify_ap.py` scenarios (j) + (k) (`asyncio.gather` two concurrent requests → exactly one succeeds, the other 422s, billed/paid exactly once). Re-verified: verify_ap.py 24/24, regression suite unchanged.

- **Where:** `service.py` `create_bill` (`_already_billed_qty` at :3116 → insert at :3170)
  and `record_payment` (`_bill_paid_amount` at :3204 → allocation insert at :3232).
- **Failure:** Both guards read-then-write with no `SELECT … FOR UPDATE` and no
  unique/exclusion constraint. Two concurrent `POST /ap/bills` for the *same*
  `po_line_id` (received qty 10): each transaction runs `_already_billed_qty` under
  READ COMMITTED, both see `0`, both pass `_is_exact_match(10 == 10)`, both insert a
  matched line, both commit → the receipt is billed **twice**, `Dr GR/IR 2150` is
  posted for 20 against a receipt `Cr` of 10, and **account 2150 never clears** (the
  exact defect the phase exists to prevent). The identical race on `record_payment`:
  two concurrent payments each read `open_balance = 100`, each allocate 100, both
  commit → the bill is paid 200, `Cr cash` / `Dr AP` overshoot, AP goes negative.
  The in-payload dup guard and the draft-reservation logic only close the *sequential*
  window; simultaneous transactions slip through.
- **Fix:** Lock the contended rows inside the transaction before the guard read —
  `select(PurchaseOrderLine).where(id == …).with_for_update()` in `create_bill`, and
  `select(Bill).with_for_update()` per allocated bill in `record_payment` — so the
  second transaction blocks until the first commits and then re-reads the true
  billed/paid sum. (A partial unique index cannot express "Σ matched_qty ≤ qty_received".)

### 2. [minor] GR/IR can leave a sub-micro residue on multi-lot fractional receipts
- **Where:** matched-line amount `data.matched_qty * po_line.unit_cost` (`service.py`
  :3163) vs the per-receipt `(qty * unit_cost).quantize(_COST_QUANTUM, ROUND_HALF_UP)`
  in `receive_line` (:1951, quantum `0.000001`).
- **Failure:** The bill books the matched leg as ONE combined product; each receipt
  booked its `Cr GR/IR` as a separately-rounded product. With a fractional quantity
  received across multiple lots the two need not agree at the 6th decimal. Example:
  `unit_cost = 0.000001`, two receipts of qty `0.5` → each rounds `0.0000005` up to
  `0.000001`, receipt `Cr` total `0.000002`; a single bill of `matched_qty = 1.0`
  books `Dr = 0.000001`. GR/IR is left holding `0.000001`, not exactly zero — the
  invariant the phase asserts. Magnitude is bounded by ~`n_lots × 0.5e-6`, so it is
  financially trivial, but it is a real divergence from "nets to zero exactly" and
  `verify_ap.py` scenario (e) — a single fully-received line — cannot surface it.
- **Fix:** Derive the matched line's amount from the sum of the *booked* receipt
  amounts for that `po_line_id` (or quantize identically per receipt), rather than
  recomputing one combined product, so the Dr equals the Σ of the original Crs.

### 3. [minor] A zero-quantity matched line creates a permanently unpostable draft
- **Where:** `create_bill` exact-match (`service.py` :3152) + `_je_is_balanced` XOR
  rule (:913).
- **Failure:** For a fully-billed (or never-received) PO line `unbilled_qty == 0`, so
  a hand-crafted `{line_type:'matched', po_line_id, matched_qty:0}` passes
  `_is_exact_match(0 == 0)` and persists a `amount = 0` line. `post_bill` then emits a
  JE line with `debit == 0 and credit == 0`, which `_je_is_balanced` rejects
  (`(debit!=0)==(credit!=0)` → both False → False), so the bill 422s forever and is
  stuck in `draft`. Not a money bug (nothing posts) and the UI never generates it
  (the picker filters `unbilled_qty > 0`), but the API accepts it.
- **Fix:** Reject `matched_qty <= 0` in `BillLineCreate` / `create_bill`.

## Questions
- `Bills.tsx` `BillLineRead` still declares `quantity` (no such backend field) and
  omits `matched_qty`/`line_no`. Confirmed harmless today — the list renders no line
  rows and `BillDetail.tsx` defines a correct local type — matching the PLAN "Noticed"
  note. Latent trap if the list type is ever reused; not a defect now.

## Assessment
The subledger is well-built and the four highest-risk axes are clean under sequential
use:
- **Atomicity** — `post_bill` and `record_payment` both post the JE with `commit=False`
  and take a single `db.commit()`; every `write_audit` fires in the router *after* the
  service returns. No stray `commit=True`, no mid-service audit. Verified.
- **GR/IR crux (sequential)** — matched lines always book at the PO `unit_cost` (the
  user's `unit_cost` is ignored) and `matched_qty` must equal the full live `unbilled_qty`,
  so a single bill's Dr GR/IR equals the receipt's Cr GR/IR exactly.
- **Overpayment / open balance** — `coalesce(sum,·),0)` on each side independently
  (`_bill_paid_amount`, `_already_billed_qty`); same-bill allocations accumulate before
  the `_is_overpayment` check; `==` fully pays; rejection persists nothing (single
  commit at the end).
- **FSM / account resolution / RBAC** — `BILL_TRANSITIONS` enforced server-side (422 on
  re-post / paying a draft or paid bill); 2110/2150 by code, expense legs gated to
  EXPENSE|ASSET, cash gated to ASSET; every GET `syerp:read`, every mutation
  `syerp:write`, no PUT/DELETE on a posted bill.
- **Migration 0010** matches the four models exactly (uuid PKs, all FKs, `Numeric(18,6)`,
  unique `bill_number`, index-mirroring, Python-side timestamps) with an FK-safe
  downgrade (allocation → payment, line → header).
- **Frontend** paths, list invalidation, Post-gated-to-draft / Pay-gated-to-posted,
  and the client `amount ≤ open_balance` guard are all correct.

Finding 1 is the one that would bite in production (a multi-user shop billing/paying
the same document from two sessions); 2 and 3 are edge-case correctness nits. None
block the sequential happy path the verify scripts exercise.
