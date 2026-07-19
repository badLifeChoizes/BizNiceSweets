# Review: Phase 12b — GELATO outbound pick → pack → ship (bde5b77..4552d1a)
Date: 2026-07-18

## Findings

### 1. [blocker] Concurrent double-ship: the packed→shipped FSM gate is read from a stale row before the item lock, so two simultaneous ships can both post COGS
- **Where:** `backend/app/modules/gelato/service/shipments.py:577-612` (`execute_ship`)
- **Failure:** `execute_ship` loads the shipment with `db.get(Shipment, ...)` (no lock) at line 577 and gates on `shipment.status` at 583, but the only rows it locks FOR UPDATE are the `InventoryItem` rows (609-612). The shipment row is never locked and its status is never re-checked after the locks are taken. Two concurrent `POST /gelato/shipments/{id}/ship` on the same *packed* shipment:
  - Request A: reads status `packed`, passes the gate, acquires the item lock, issues out of staging, stamps `qty_shipped`, relieves `qty_reserved`, posts COGS JE #1, sets `shipped`, commits (releasing the lock).
  - Request B: read status `packed` *before* A committed, passed the gate, then blocked on the item lock at 609-612. When A commits, B unblocks with `shipment.status` still `packed` in its identity map — it never re-reads — and proceeds to issue a **second** time, stamp `qty_shipped` again, relieve `qty_reserved` again, and post **COGS JE #2**.
  The only thing stopping B is `post_issue`'s per-bin floor guard, which holds *only* when the staging bin's on-hand equals the shipment's qty exactly. With a shared/reused outbound-staging bin (normal WMS practice) or a partial pack that left residual staged stock, the staging bin has enough on-hand for B's draw to pass — so B double-issues inventory, double-books COGS, double-relieves the SO reservation, and double-counts `qty_shipped`, with two JEs against one physical shipment. This is exactly the double-post the FSM gate is meant to prevent. (Contrast MOUSSE `issue_components`, whose identical "status-before-lock" shape is safe only because issuing is intentionally repeatable, not a one-shot terminal transition.)
- **Fix:** Serialize on the shipment itself: load it with `select(Shipment).where(Shipment.id == shipment_id).with_for_update()` (taken first, before the item locks — one row, deadlock-free), OR re-read and re-assert `shipment.status == "packed"` *after* acquiring the item locks and before the first `post_issue`. The FSM gate must run against a locked/fresh row.

## Questions

- **Concurrent first-pick creates two open shipments.** `execute_pick` (shipments.py:325-335) get-or-creates via `_get_open_shipment` with no lock on the SO/shipment. Two simultaneous first picks for one SO both see "no open shipment" and each create one, leaving the SO with two `picking` shipments. The per-item `post_putaway` lock keeps `qty_picked` correct and inventory non-negative, so it is not corrupting, but it violates the "at most one open pick per SO" assumption `_get_open_shipment`/`_resolve_fulfilling_location` rely on. Intended?

- **Pick can append to a shipment being packed.** `execute_pick` reads the open shipment (status `picking`) and then adds `ShipmentLine`s + putaway legs without re-checking status; a concurrent `execute_pack` (which takes no locks) can flip it to `packed` in between. The extra line then rides to ship without having been through pack's staged-qty review. Narrow interleaving, no ledger corruption — flagging for awareness, not as a confirmed defect.

## Cleared (verified, not findings)
- Ship JE is balanced (2 lines, Dr 5100 / Cr 1130 = `total_value`), single `db.commit`, all inner calls `commit=False` — atomic; `_je_is_balanced` accepts the `credit:0`/`debit:0` dict shape.
- `post_issue` locks the item-master row before the floor read; per-bin floor guard is cumulative across lines via `db.flush`; sign is `-qty`; valuation `qty*moving_avg` quantized scale-6.
- Over-ship guard on the identity-mapped `so_line`; `qty_reserved` relief floored at 0; multiple shipment lines for one SO line accumulate correctly.
- Migration 0016: parent-before-child create, reverse-order downgrade, `server_default="0"` on the new NOT NULL columns, FK types match models.
- RBAC: every endpoint gated `gelato:read`/`gelato:write`; audit written after service commit with `target_id=str(shipment.id)`.
- Frontend invalidation keys (`soDetailKey`) match CRUMB's `salesOrderKey`; `SalesOrderLineRead` only ever built via `model_validate`, so the new required `qty_picked`/`qty_shipped` fields resolve from the ORM.
