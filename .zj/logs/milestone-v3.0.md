# Work Log — Milestone v3.0 "Customer & logistics"

**Closed:** 2026-07-19 · **Tag:** `v3.0` · **Author:** ne1ne
**Audit:** `.zj/MILESTONE-v3.0-AUDIT.md` (goal-backward vs the three-clause DoD; verdict recorded there)

## Scope

v3.0 delivered the **sell-side + fulfilment loop** on top of the v2.0 operations core: two new
suites — **CRUMB** (CRM: leads → opportunities → quotes → sales orders with soft-reservation)
and **GELATO** (WMS: bins, directed putaway, pick → pack → ship) — plus **SYERP-13 accounts
receivable** (invoice-from-shipment, customer receipts, AR aging). It closes the definition of
done's three clauses: *(1) CRM & sales pipeline; (2) warehouse fulfilment; (3) accounts
receivable & sell-side books, with AR aging tying Decimal-exactly to the 1120 control account
and the trial balance still netting zero.*

Delivered across five phases: **11a** (CRUMB CRM & pipeline), **11b** (CRUMB sales orders +
soft-reservation), **12a** (GELATO bins & directed putaway), **12b** (GELATO pick → pack → ship
+ COGS JE), **13** (SYERP-13 AR & sell-side books). Every phase was planned → built → verified
goal-backward → retro'd independently. The build order followed the money: order → ship →
invoice → cash.

## Effort

**130 commits** (67 feat · 8 fix · 39 docs · 14 test · 2 chore), sole author ne1ne, over
**~14.6 hours across 10 inferred work sessions** on 4 active days (2026-07-16 → 2026-07-19).
Pace: 29 commits 07-16, 43 on 07-17, 24 on 07-18, 34 on 07-19 (incl. the close). Densest
sessions were the 11a open (07-16, 3.5h) and the Phase-13 build + verify + retro + close (07-19,
~3.1h). (`/zj:timeline` renders the visual; `.zj/logs/timeline.html`.)

## Shipped work, by phase

### Phase 11a — CRUMB CRM & pipeline (CRUMB-01 AC1/2/3−/5/6/7)
A whole new `crumb` suite, built as a `crumb/service/` package from day one (the D-V3-9 lesson
applied pre-emptively). Leads → opportunities (stage FSM) → quotes (PLUM-derived line pricing +
markup, `QUOTE-####` numeric-safe generator, Draft→Sent→Accepted/Rejected/Expired FSM) + an
append-only customer communication log. Server-enforced FSMs, router-layer audit, `crumb:read`/
`crumb:write` RBAC. Migration 0013. Verify fix-loop closed a reviewer-caught major (a part-less,
description-less priced quote line silently accepted). `verify_crumb` 22/22, `verify_crumb_api`
54/54. Tag `zj/good-11a-crumb-crm-pipeline`.

### Phase 11b — CRUMB sales orders + soft-reservation (CRUMB-01 AC4 + AC3 conversion tail)
Direct SO CRUD + `SO-####` numbering + FSM (Draft→Confirmed→Fulfilling→Closed, +Cancelled);
accepted-quote→SO conversion; and the **soft-reservation crux** — confirm reserves
`min(qty_ordered, available)` where `available = on-hand − Σ open reservations ≥ 0`, with
`InventoryItem` rows `FOR UPDATE`-locked in sorted-id order before the read; cancel releases.
Posts no GL (reservation is a soft quantity; TB still nets zero). Migration 0014. Verify
fix-loop caught a blocker — direct-create lines never resolved `plum_part_id→item_id`, so
UI-created orders reserved 0 — fixed with one shared resolver on every entry point.
`verify_crumb_so` 27/27 (incl. concurrency scenario F), `verify_crumb_so_api` 40. **CRUMB-01
now complete.** Tag `zj/good-11b-crumb-sales-orders`.

### Phase 12a — GELATO bins & directed putaway (GELATO-01 AC1/2 + putaway-side AC7/8)
New `gelato` module. `gelato_bin` + a nullable `bin_id` dimension on the existing
`syerp_inventory_txn` ledger (roll-up to the location total guaranteed by construction,
D-P12a-2; reverse-hub string FK, D-P12a-3). SYERP-owned bin-aware primitives
`post_putaway`/`get_bin_on_hand` (lock the `InventoryItem` master row FOR UPDATE before the
floor read); thin GELATO service validates bins-belong-to-location then delegates. Migration
0015, seeded `gelato:read/write`. The paired HTTP script caught a real audit bug (int-PK `Bin.id`
→ `VARCHAR(36)` `target_id` coercion 500'd the mutation after commit; `str()` fix). Reviewer
MAJOR — bin-blind draws (`post_transfer`/`post_adjustment`/MOUSSE-issue) desync the bin split —
documented as the 12a→12b boundary + pinned by verify scenario E → BACKLOG p2. `verify_gelato`
11/11, `verify_gelato_api` 29/29. Tag `zj/good-12a-gelato-bins-putaway`.

### Phase 12b — GELATO outbound pick → pack → ship + COGS JE (GELATO-01 AC3/4/5 + ship-side AC7/8)
Shipment aggregate + FSM (picking → packed → shipped, +cancelled from picking). Pick = bin-aware
net-zero move to a staging bin; pack = FSM trim; **ship** = a NEW SYERP bin-aware `post_issue`
from staging + ONE atomic **Dr 5100 COGS / Cr 1130 Inventory** JE at moving-avg + reservation
relief + `qty_shipped` stamp. Migration 0016. Verify fix-loop closed a BLOCKER the phase's own
concurrency test had *masked*: two concurrent ships of one packed shipment double-posted COGS
because the FSM gate read an unlocked status — fixed with a shipment-row `FOR UPDATE` lock before
the gate, re-pinned by a corrected scenario (h) where only that lock can reject. Closes the
CRUMB→GELATO outbound loop; TB nets zero WITH the ship COGS JE and 1130 ties to subledger.
`verify_gelato_ship` 21/21, `verify_gelato_ship_api` 23/23. Tag `zj/good-12b-gelato-pick-pack-ship`.

### Phase 13 — SYERP-13 accounts receivable & sell-side books (SYERP-13, 7 ACs)
Extends `syerp`. Invoice-from-shipment (`create_invoice` FOR-UPDATE lock on SO-line rows, price
locked to SO `unit_price`, stamps `qty_invoiced`; `post_invoice` → **Dr 1120 AR / Cr 4110
Revenue**), customer receipts (`record_receipt` + allocations + FOR-UPDATE guard → **Dr cash /
Cr 1120**, auto-Paid at zero), and `ar_aging_report` tying grand-total Decimal-exact to the
**debit-normal** 1120 control (NO sign negation, D-P13-7). The COGS-on-ship JE from 12b is
asserted, not rebuilt (D-P13-3). Migration 0017. Verify fix-loop closed a reviewer MAJOR — an
unvalidated `sales_order_id` FK made `create_invoice` misread an FK error as a number collision
and recurse forever (RecursionError/500) — fixed with up-front 404 validation + a bounded retry.
The Task-13 adjacent-surface regression assertion surfaced a pre-existing 12a cold-boot 500 (lazy
gelato model imports left `bin_id→gelato_bin` unresolvable), fixed by importing `app.core.models`
at boot (D-P13-8). `verify_ar` 17/17 (both concurrency locks mutation-proven), `verify_ar_api`
29/29. **Closes v3.0 DoD clause 3.** Tag `zj/good-13-syerp-ar-invoicing`.

### Milestone close (2026-07-19)
Goal-backward audit of all three DoD clauses against the running stack; records produced
(this log, CHANGELOG v3.0, LEARNINGS roll-up, DECISIONS index regenerated to 130 entries);
`v3.0` tagged; phases 11–13 archived to `.zj/history/v3.0/`.

## Key decisions (with why)

- **D-V3-1** — DoD = *three clauses* (CRM pipeline / warehouse fulfilment / AR & sell-side books).
  The contract is the DoD, not the phase count — Phase 12 sub-split 12a/12b and could have gone
  further; what matters is the loop closes.
- **D-V3-8** — a confirmed sales order *soft-reserves* inventory (`available = on-hand − Σ open
  reservations`), not a hard allocation. Single-shop backorder is an indicator, not a hard block.
- **D-P12a-2** — bins live as a `bin_id` dimension on the *existing* `syerp_inventory_txn` ledger,
  so bin quantities roll up to the location total by construction (one ledger, one truth).
- **D-P12b-7** — the sell-side COGS JE mirrors MOUSSE `issue_components`, swapping Dr 1140→5100:
  **Dr 5100 COGS / Cr 1130** at moving-avg on ship. Two-event real books, no clearing account.
- **D-P13-2** — invoice line price *locks* to the sales-order line's agreed `unit_price` (the
  price the customer accepted), not re-derived from PLUM at invoice time.
- **D-P13-7** — AR aging control-tie has *NO sign negation* — 1120 is debit-normal
  (`control_balance = Σdr − Σcr`), unlike the credit-normal 2110 AP the report was copied from.
  The top correctness risk of the phase; pinned Decimal-exact.
- **D-P13-8** — the running app imports the `app.core.models` aggregator at boot so cross-module
  string FKs resolve on a cold process (GELATO imports its models lazily) — SYERP still never
  imports gelato.

## Verification evidence

- **23/23 live `verify_*.py` scripts exit 0** against the running stack (re-run at milestone
  close): 14 service (gl, ap, reports, inventory, purchasing, e2e_p8, mousse, crumb, crumb_so,
  gelato, gelato_ship, ar, part_numbering, plum_vendor_paths) + 9 HTTP-level `*_api` scripts.
- Whole-DB **trial balance nets 0.000000**; AR/AP/inventory/WIP/GR-IR control accounts flat at
  rest (verify scripts self-clean); AR aging ties Decimal-exact to 1120 within `verify_ar`.
- Frontend **`npm run build` clean**, Vitest green (44 files / 131 tests at Phase 13).
- Alembic head **0017**. `zj doctor` format-clean but for one STATE step-vocab error (resolved at
  close) + the known cosmetic BACKLOG tag-format warnings.

## Carried debt (into the next milestone)

- **BACKLOG p1 infra debt — now three milestones old:** no CI, the live-DB pytest harness still
  broken (D-P7-4), both lint gates non-functional. Correctness rested on `verify_*` + Vitest for
  the whole milestone. Deferred again at close.
- **Human click-through UAT** (D-M2-2) — still a pre-public-release gate; extend the checklist
  with CRUMB/GELATO/AR UI flows before running.
- **Shared cross-path inventory-ledger row-lock** (BACKLOG p2) — now has a third+ writer
  (GELATO ship) plus the inbound bin-blind-desync half; plan the shared FOR-UPDATE lock across
  every floor-guarded path (issue/adjust/receive/transfer/ship) before a multi-writer deploy.
- **Master-merge** — v3.0 tagged on the unmerged `feature-syerp-ar-invoicing` tip; the
  11a+11b+12a+12b+13 stack owes a `/zj:ship` merge to master (the v2.0 debt was cleared via PR #2).
</content>
</invoke>
