# UAT — v2.0 milestone (SYERP inventory & purchasing)

> **Superseded for execution by [`.zj/QA.md`](QA.md)** (D-P5-11; previously by
> `.zj/UAT-v4.0.md` per D-P5-6, itself now history). Retained as **history**. **All 14**
> checks here were still open and were carried into v4.0's SYERP block and from there into
> `.zj/QA.md` under **SYERP-01..13**; do not run this file.

Per **D-P7-5**, human click-through UAT is a milestone-close activity, run once at
`/zj:milestone` against the Vite dev server (**http://localhost:5173**, D-P7-1) with the
Podman stack up (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
API container `compose_api_1`, `alembic current` must == `0008`). Log in as admin.

Phase 8 backend behavior is already **proven live** by three standalone Postgres scripts
(`backend/scripts/verify_inventory.py` 14/14, `verify_purchasing.py` 18/18, and a
freshly-migrated `verify_e2e_p8.py` 18/18) — this checklist confirms the **UI flow** only.
A fresh deploy seeds one idempotent **`Main`** stock location (D-P8-14), so receiving works
out-of-the-box. Have a **vendor** (SYERP `Partner.is_vendor`) available for the PO checks.

## SYERP-10 — Inventory management

| # | Flow (AC) | Status | Notes |
|---|---|---|---|
| 1 | Inventory Items — create an item WITH a PLUM part link and one WITHOUT → both get auto `ITEM-####` codes; Show-archived off hides an archived item (10.1) | ⬜ todo | PLUM part Select stays usable when PLUM has no parts |
| 2 | Stock Locations — `Main` is present out-of-the-box; create "Receiving", archive it → drops from default list (10.2, D-P8-14) | ⬜ todo | |
| 3 | Item detail — after a receipt, on-hand shows qty PER location + total qty, moving-average cost, and on-hand value (10.3, 10.5) | ⬜ todo | value = total qty × moving-avg cost |
| 4 | Item detail — transaction ledger lists each txn (type / qty / unit_cost / location / timestamp / reason); rows are read-only (10.4) | ⬜ todo | ledger is append-only, never edited |
| 5 | Adjust Stock dialog — a valid adjustment updates on-hand; an adjustment driving a location negative shows the rejection `toast.error` and changes nothing (10.6) | ⬜ todo | reason is required |
| 6 | Transfer Stock dialog — transfer moves qty between two locations, total on-hand unchanged; an over-draw from source shows the rejection toast (10.6) | ⬜ todo | from==to blocked client-side |
| 7 | Audit — item create/edit/archive, location changes, and each txn appear as attributable audit events (10.7) | ⬜ todo | spot-check via audit log |

## SYERP-11 — Purchase orders

| # | Flow (AC) | Status | Notes |
|---|---|---|---|
| 8 | Create PO — vendor picker lists ONLY vendors; add lines (item, qty, unit cost, optional need-by); PO gets auto `PO-####` (11.1, 11.2, 11.3) | ⬜ todo | lines editable only while Draft |
| 9 | Approve — "Approve" (Draft only) → status `Approved`; line qty/cost no longer editable; illegal actions hidden in UI and rejected by server if forced (11.1) | ⬜ todo | approver captured via audit (D-P8-10) |
| 10 | Receive partial — receive part of a line into a chosen location → PO shows `Partially Received`; the item's on-hand rises by the received qty and moving-average reflects the PO line unit cost (11.4, 11.5) | ⬜ todo | proves receipt → SYERP-10 integration |
| 11 | Receive remainder — receive the rest → PO auto-advances to `Received` when every line is fully received (11.5) | ⬜ todo | |
| 12 | Over-receipt — attempt to receive more than outstanding → rejection `toast.error`, nothing posted (11.4) | ⬜ todo | |
| 13 | Vendor history — PO list `vendor_id` filter narrows to that vendor's POs with status + total value + received roll-up (11.3) | ⬜ todo | |
| 14 | Close — "Close" from an allowed state moves the PO to `Closed` (11.1) | ⬜ todo | |

## If a check fails
Bisect against the atomic Phase-8 commits (`git log --oneline` on
`feature-syerp-inventory-purchasing`) — each behavior is one commit — and re-run the relevant
standalone verify script (`backend/scripts/verify_inventory.py` / `verify_purchasing.py` /
`verify_e2e_p8.py`) to isolate UI-vs-backend. Record the failing flow + observations here and
open a gap-closure task rather than blocking the milestone on unrelated flows.
