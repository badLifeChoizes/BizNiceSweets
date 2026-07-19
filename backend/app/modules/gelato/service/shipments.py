# ABOUTME: GELATO shipment service (GELATO-02) — the outbound pick/pack/ship
# ABOUTME: FSM table, the pick-list read (per-line candidate bins + suggestion),
# ABOUTME: and execute_pick: a bin-aware, net-zero move of picked stock from the
# ABOUTME: pick bins into the shipment's staging bin via SYERP post_putaway.
"""GELATO shipments service (business logic).

Outbound fulfilment of a CRUMB sales order: pick → pack → ship. This module owns
the pick half (GELATO-02, SC2):

  * SHIPMENT_TRANSITIONS — the shipment-status FSM (D-P12b-11), mirroring the
    shape of CRUMB's SO_TRANSITIONS: picking → packed | cancelled, packed →
    shipped, with shipped / cancelled terminal.
  * build_pick_list — the pick suggestion screen: per STOCK order line, the
    ordered/reserved/picked/shipped quantities plus the fulfilling location's
    active bins holding on-hand of the item (candidate sources) and a suggested
    source bin.
  * execute_pick — pick a sales order into its staging bin. Each pick line moves
    stock from a pick bin into the shipment's staging bin as a bin-aware NET-ZERO
    putaway (both legs at the same location — the location total is unchanged,
    only the per-bin split shifts, and the stock stays in the warehouse until
    ship). The physical move is delegated to SYERP post_putaway (commit=False),
    so all of a pick's putaway legs, the qty_picked stamps, and the SO's
    confirmed → fulfilling advance (D-P12b-10) land in ONE atomic commit.

GELATO stays THIN (D-P10-6): it NEVER writes InventoryTxn itself — the ledger
legs are always SYERP's post_putaway. SYERP model/service imports are lazy
(inside functions) so importing this module never pulls in the hub at module
import time (mirrors bins.py / putaway.py). post_putaway's own per-bin floor
guard (over-pick), self-move guard, and item/location 404s propagate unchanged.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gelato.service.bins import get_bin, list_bins

if TYPE_CHECKING:
    from app.modules.gelato.models import Shipment
    from app.modules.gelato.schemas import (
        PackRequest,
        PickListRead,
        PickRequest,
        ShipmentRead,
    )


# ---------------------------------------------------------------------------
# Shipment-status FSM (D-P12b-11)
# ---------------------------------------------------------------------------
#
# A shipment walks a controlled lifecycle; a move is permitted only if the target
# is in the current state's allowed set. Terminal states map to the empty set (no
# further transitions). Mirrors the shape of CRUMB's SO_TRANSITIONS.

# Shipment status: picking → packed | cancelled → shipped (shipped/cancelled terminal).
SHIPMENT_TRANSITIONS: dict[str, set[str]] = {
    "picking": {"packed", "cancelled"},
    "packed": {"shipped"},
    "shipped": set(),
    "cancelled": set(),
}


# ---------------------------------------------------------------------------
# Pick-list read — pick suggestion screen (GELATO-02, SC2)
# ---------------------------------------------------------------------------


async def _resolve_fulfilling_location(
    db: AsyncSession, sales_order_id: str, item_ids: list[str]
) -> int | None:
    """
    Resolve the single stock location a sales order is fulfilled from.

    The CRUMB sales order carries no location (its soft-reservation is item-level,
    D-V3-11) and GELATO fulfils a shipment from ONE location (multi-location picks
    are out of scope — D-V3-7). So the fulfilling location is resolved as:

      (a) if a pick is already in progress — an OPEN (status "picking") Shipment
          exists for the SO — its committed location_id (the operator has already
          chosen it by starting the pick);
      (b) otherwise the location holding the most on-hand across the SO's stock
          items (get_item_onhand only reports locations with nonzero on-hand), so
          the suggestion points where the reserved stock actually is; ties break to
          the lowest location_id for determinism;
      (c) otherwise None — no stock anywhere yet, so there are no bins to suggest.

    Read-only: reading SYERP on-hand is fine; only WRITES are forbidden to GELATO
    (D-P12a-3, D-P10-6). SYERP imports are lazy to avoid pulling in the hub at
    module import time.
    """
    from app.modules.gelato.models import Shipment
    from app.modules.syerp.service import get_item_onhand

    # (a) An in-progress pick has already committed the SO to one location.
    open_shipment = await _get_open_shipment(db, sales_order_id)
    if open_shipment is not None:
        return open_shipment.location_id

    # (b) Else the location holding the most on-hand across the SO's stock items.
    per_location: dict[int, Decimal] = {}
    for item_id in item_ids:
        onhand = await get_item_onhand(db, item_id)
        for loc in onhand.locations:
            per_location[loc.location_id] = (
                per_location.get(loc.location_id, Decimal("0")) + loc.quantity
            )

    if not per_location:
        return None

    # Greatest total on-hand, lowest location_id as the deterministic tie-break.
    best_location_id, _ = max(per_location.items(), key=lambda kv: (kv[1], -kv[0]))
    return best_location_id


async def build_pick_list(db: AsyncSession, sales_order_id: str) -> "PickListRead":
    """
    Build the pick list for a sales order — the pick suggestion screen (SC2).

    Raises 404 if the sales order does not exist, and 422 if its status is not one
    of {confirmed, fulfilling} — a pick may only be built for an order that is
    confirmed (reserved) or already being fulfilled.

    Per STOCK line (item_id not null; non-stock/free-text lines cannot be bin
    picked and are omitted), surfaces the ordered/reserved/picked/shipped
    quantities plus the fulfilling location's ACTIVE bins holding on-hand of the
    item (candidate sources, reusing list_bins + get_bin_on_hand) and a suggested
    source bin:

      * available_bins — every active bin in the fulfilling location whose on-hand
        of the item is > 0, ordered by bin code (list_bins order).
      * suggested_from_bin_id — the first bin whose on-hand covers the
        remaining-to-pick (qty_ordered − qty_picked), else the bin holding the
        most on-hand, else None (no candidate bins).
    """
    from app.modules.crumb.models import SalesOrder, SalesOrderLine
    from app.modules.gelato.schemas import (
        PickListBinRead,
        PickListLineRead,
        PickListRead,
    )
    from app.modules.syerp.service import get_bin_on_hand

    so = await db.get(SalesOrder, sales_order_id)
    if so is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sales order '{sales_order_id}' not found",
        )
    if so.status not in ("confirmed", "fulfilling"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Sales order '{sales_order_id}' is '{so.status}'; a pick list can "
                "only be built for a confirmed or fulfilling order."
            ),
        )

    result = await db.execute(
        select(SalesOrderLine)
        .where(SalesOrderLine.sales_order_id == sales_order_id)
        .order_by(SalesOrderLine.sort_order)
    )
    lines = list(result.scalars().all())

    # Resolve the single fulfilling location from the SO's distinct stock items.
    stock_item_ids = sorted({ln.item_id for ln in lines if ln.item_id is not None})
    location_id = await _resolve_fulfilling_location(db, sales_order_id, stock_item_ids)

    # Cache the location's active bins once (shared across every stock line).
    location_bins = await list_bins(db, location_id) if location_id is not None else []

    pick_lines: list[PickListLineRead] = []
    for line in lines:
        # Non-stock / free-text lines cannot be bin-picked (SC2) — omit them.
        if line.item_id is None:
            continue

        available_bins: list[PickListBinRead] = []
        for bin_ in location_bins:
            on_hand = await get_bin_on_hand(db, line.item_id, location_id, bin_.id)
            if on_hand > 0:
                available_bins.append(
                    PickListBinRead(bin_id=bin_.id, code=bin_.code, on_hand=on_hand)
                )

        remaining = line.qty_ordered - line.qty_picked
        suggested = _suggest_pick_bin(available_bins, remaining)

        pick_lines.append(
            PickListLineRead(
                sales_order_line_id=line.id,
                item_id=line.item_id,
                description=line.description or "",
                qty_ordered=line.qty_ordered,
                qty_reserved=line.qty_reserved,
                qty_picked=line.qty_picked,
                qty_shipped=line.qty_shipped,
                suggested_from_bin_id=suggested,
                available_bins=available_bins,
            )
        )

    return PickListRead(sales_order_id=sales_order_id, lines=pick_lines)


def _suggest_pick_bin(
    available_bins: "list", remaining_to_pick: Decimal
) -> int | None:
    """
    Choose a suggested source bin from a line's candidate bins (pure, no DB).

    Prefers the first bin whose on-hand covers the remaining-to-pick (single-bin
    pick), else the bin holding the most on-hand (start with the fullest), else
    None when there are no candidate bins. available_bins arrive in bin-code order
    (list_bins order), so "first" is the lowest-code covering bin.
    """
    if not available_bins:
        return None

    for candidate in available_bins:
        if candidate.on_hand >= remaining_to_pick:
            return candidate.bin_id

    return max(available_bins, key=lambda b: b.on_hand).bin_id


# ---------------------------------------------------------------------------
# Execute pick — bin-aware net-zero move into staging (GELATO-02, SC2)
# ---------------------------------------------------------------------------


async def _get_open_shipment(
    db: AsyncSession, sales_order_id: str
) -> "Shipment | None":
    """
    Return the SO's OPEN (status "picking") shipment, or None if there is none.

    An open picking shipment is the in-progress pick a further pick appends to; a
    packed / shipped / cancelled shipment is not open. Returns the earliest such
    shipment (by id) for determinism — a well-behaved SO has at most one.
    """
    from app.modules.gelato.models import Shipment

    result = await db.execute(
        select(Shipment)
        .where(Shipment.sales_order_id == sales_order_id, Shipment.status == "picking")
        .order_by(Shipment.id)
        .limit(1)
    )
    return result.scalars().first()


async def execute_pick(
    db: AsyncSession, req: "PickRequest", actor_id: str
) -> "ShipmentRead":
    """
    Pick a sales order into its staging bin — bin-aware, net-zero (SC2).

    In ONE atomic transaction (all post_putaway legs commit=False; a single
    db.commit() at the end):

      (a) Load the SO (404); assert status in {confirmed, fulfilling} (422).
      (b) Resolve the fulfilling location from the staging bin: the staging bin
          must exist (404) and be ACTIVE (422); its location_id is the fulfilling
          location. Every pick line's from_bin must belong to that SAME location
          (422 if any diverges) — the SO carries no explicit location, so the
          staging bin + pick bins define it (all must share one location).
      (c) Get-or-create the SO's OPEN "picking" shipment for this staging bin. If
          an open picking shipment already exists it is reused; a different
          staging bin than the one it opened with is rejected (422).
      (d) Per pick line: resolve the SO line (404 if not a line of THIS SO);
          reject 422 if the line is non-stock (item_id None — a free-text line
          cannot be bin-picked, SC2); guard qty > 0 (422); delegate the physical
          move to SYERP post_putaway (from the pick bin into the staging bin, same
          location — a net-zero move whose per-bin floor guard rejects over-pick
          4xx); append a ShipmentLine; increment the SO line's qty_picked.
      (e) The FIRST pick advances the SO confirmed → fulfilling (D-P12b-10) — a
          plain status write validated against SO_TRANSITIONS.
      (f) Single db.commit().
      (g) Return the shipment (with its lines) as a ShipmentRead.

    GELATO never writes InventoryTxn — the ledger legs are SYERP's post_putaway.
    """
    from app.modules.crumb.models import SalesOrder, SalesOrderLine
    from app.modules.crumb.service._common import SO_TRANSITIONS
    from app.modules.gelato.models import Shipment, ShipmentLine
    from app.modules.syerp.service import post_putaway

    # (a) Load the SO and gate on its status.
    so = await db.get(SalesOrder, req.sales_order_id)
    if so is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sales order '{req.sales_order_id}' not found",
        )
    if so.status not in ("confirmed", "fulfilling"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Sales order '{req.sales_order_id}' is '{so.status}'; only a "
                "confirmed or fulfilling order can be picked."
            ),
        )

    # (b) Resolve the fulfilling location from the staging bin (404 missing, 422
    #     archived). The SO carries no location — the staging bin defines it, and
    #     every pick bin must live in that same location (checked per line below).
    staging_bin = await get_bin(db, req.staging_bin_id)
    if not staging_bin.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Staging bin {req.staging_bin_id} is archived.",
        )
    location_id = staging_bin.location_id

    # (c) Get-or-create the SO's OPEN picking shipment for this staging bin.
    shipment = await _get_open_shipment(db, req.sales_order_id)
    if shipment is None:
        shipment = Shipment(
            sales_order_id=req.sales_order_id,
            location_id=location_id,
            staging_bin_id=req.staging_bin_id,
            status="picking",
            actor_id=actor_id,
        )
        db.add(shipment)
        await db.flush()
    elif shipment.staging_bin_id != req.staging_bin_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Sales order '{req.sales_order_id}' already has an open pick into "
                f"staging bin {shipment.staging_bin_id}; a different staging bin "
                f"({req.staging_bin_id}) cannot be used until it is packed."
            ),
        )

    # (d) Per pick line: validate, delegate the net-zero move, accumulate.
    for req_line in req.lines:
        # Pick bin must belong to the fulfilling location (the staging bin's).
        from_bin = await get_bin(db, req_line.from_bin_id)
        if from_bin.location_id != location_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Pick bin {req_line.from_bin_id} does not belong to the "
                    f"fulfilling location {location_id} (the staging bin's location)."
                ),
            )

        # Resolve the SO line and assert it belongs to THIS order.
        line = await db.get(SalesOrderLine, req_line.sales_order_line_id)
        if line is None or line.sales_order_id != req.sales_order_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Sales order line '{req_line.sales_order_line_id}' not found "
                    f"on order '{req.sales_order_id}'"
                ),
            )
        # A non-stock / free-text line (item_id NULL) cannot be bin-picked (SC2).
        if line.item_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Sales order line '{line.id}' is a non-stock line and cannot "
                    "be bin-picked."
                ),
            )
        if req_line.qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Pick quantity must be greater than zero.",
            )

        # Delegate the physical move to SYERP: a bin-aware net-zero putaway from
        # the pick bin into the staging bin (both at location_id). Its per-bin
        # floor guard rejects over-pick (4xx); commit=False folds it into this
        # unit of work so the whole pick is atomic.
        await post_putaway(
            db,
            item_id=line.item_id,
            location_id=location_id,
            from_bin_id=req_line.from_bin_id,
            to_bin_id=req.staging_bin_id,
            qty=req_line.qty,
            actor_id=actor_id,
            commit=False,
        )

        db.add(
            ShipmentLine(
                shipment_id=shipment.id,
                sales_order_line_id=line.id,
                item_id=line.item_id,
                from_bin_id=req_line.from_bin_id,
                qty=req_line.qty,
            )
        )
        line.qty_picked = line.qty_picked + req_line.qty

    # (e) FIRST pick advances the SO confirmed → fulfilling (D-P12b-10) — a plain
    #     status write validated against the SO FSM (the reservation is untouched).
    if so.status == "confirmed" and "fulfilling" in SO_TRANSITIONS.get(so.status, set()):
        so.status = "fulfilling"

    # (f) Single atomic commit (every post_putaway used commit=False).
    await db.commit()

    # (g) Return the shipment with its lines.
    return await _load_shipment_read(db, shipment.id)


# ---------------------------------------------------------------------------
# Execute pack — FSM picking → packed, staged-qty record only (GELATO-02, SC3)
# ---------------------------------------------------------------------------


async def execute_pack(
    db: AsyncSession, shipment_id: int, req: "PackRequest", actor_id: str
) -> "ShipmentRead":
    """
    Pack a picked shipment — advance picking → packed and record the staged qty.

    A pure state + staged-qty record: packing books NO ledger/GL movement (that is
    ship's job) and does NOT touch the SO's qty_picked / qty_reserved — a partial
    pack does not return stock to the pick bin (that reconciliation is out of scope
    for this phase; ship relieves the reservation for the shipped qty only). The
    packed/staged qty is what ship later issues, stored on ShipmentLine.qty (the
    picked qty stamped at pick), so trimming it DOWN here is what a partial pack
    means (SC3).

      (a) Load the shipment (404).
      (b) Gate on the shipment FSM: only a "picking" shipment can be packed —
          "packed" must be in the current state's allowed set (409 otherwise),
          mirroring SHIPMENT_TRANSITIONS.
      (c) Apply any per-line staged-qty overrides (req.overrides): each must target
          a ShipmentLine of THIS shipment (422 if foreign/nonexistent) and trim the
          staged qty DOWN within (0, picked qty] — an override exceeding the picked
          qty is rejected (422); qty > 0 is guaranteed at the boundary
          (PackLineOverride.qty Field(gt=0)). With no overrides every line packs at
          its picked qty as-is.
      (d) Set status "packed"; single db.commit(); return the ShipmentRead.
    """
    from app.modules.gelato.models import Shipment, ShipmentLine

    # (a) Load the shipment.
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    # (b) FSM gate: only a shipment being picked can be packed. A non-picking
    #     shipment (packed / shipped / cancelled) has no "packed" successor — 409.
    if "packed" not in SHIPMENT_TRANSITIONS[shipment.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Shipment {shipment_id} is '{shipment.status}'; only a shipment "
                "being picked can be packed."
            ),
        )

    # (c) Apply per-line staged-qty overrides. Index THIS shipment's lines by id so
    #     an override targeting a foreign / nonexistent line is rejected (422).
    result = await db.execute(
        select(ShipmentLine).where(ShipmentLine.shipment_id == shipment_id)
    )
    lines_by_id = {line.id: line for line in result.scalars().all()}

    for override in req.overrides:
        line = lines_by_id.get(override.shipment_line_id)
        if line is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Shipment line {override.shipment_line_id} does not belong to "
                    f"shipment {shipment_id}."
                ),
            )
        # A pack override may only trim the staged qty DOWN — it cannot pack more
        # than was picked (line.qty is the picked qty). qty > 0 is enforced at the
        # boundary (PackLineOverride.qty Field(gt=0)).
        if override.qty > line.qty:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Pack qty {override.qty} for shipment line "
                    f"{override.shipment_line_id} exceeds the picked qty {line.qty}; "
                    "packing can only trim the staged qty down."
                ),
            )
        line.qty = override.qty

    # (d) Advance to packed and commit once. No ledger/GL movement here.
    shipment.status = "packed"
    await db.commit()

    return await _load_shipment_read(db, shipment.id)


# ---------------------------------------------------------------------------
# Execute ship — issue out of staging + COGS JE + reservation relief (SC4)
# ---------------------------------------------------------------------------


async def execute_ship(
    db: AsyncSession, shipment_id: int, actor_id: str
) -> "ShipmentRead":
    """
    Ship a packed shipment — the accounting crux (GELATO-02, SC4; SYERP-13 AC1).

    The whole ship is ONE atomic unit of work (a single db.commit at the end),
    mirroring MOUSSE issue_components: every guard rejects (404/409/422) with
    NOTHING persisted, and a successful ship lands its issue ledger legs, ONE
    balanced COGS JE, the SO's qty_shipped / qty_reserved stamps, and the
    shipment's shipped status together — never partially.

    Flow:
      1. Load the shipment (404). Gate on the shipment FSM: only a 'packed'
         shipment can ship — 'shipped' must be in the current state's allowed set
         (409 otherwise). This blocks double-ship / double reservation relief.
      2. Load its ShipmentLines (422 if none — an empty shipment has nothing to
         issue and no balanced JE to post).
      3. **Lock the DISTINCT contended InventoryItem rows FOR UPDATE in sorted-id
         order BEFORE any on-hand read** (copies the issue_components template): a
         concurrent ship / issue against the same item blocks until this
         transaction commits and then re-reads the true on-hand, so two ships can
         never drive the staging bin negative or double-consume.
      4. Per line: delegate the physical draw to SYERP post_issue (from the
         shipment's staging bin at its location, commit=False). post_issue flushes
         each leg, so its per-bin floor guard is CUMULATIVE across lines — two
         lines of the same item from the staging bin cannot jointly overdraw the
         staging on-hand (a staging over-issue is rejected 4xx). Then, on the SAME
         SalesOrderLine:
           * over-ship guard — reject 422 if qty_shipped + line.qty > qty_ordered
             (never ship beyond ordered);
           * qty_shipped += line.qty;
           * relieve the reservation: qty_reserved = max(0, qty_reserved - line.qty)
             (D-P12b-5 — keeps _reserved_by_other_open_sos accurate);
           * soft-link the ShipmentLine to its issue leg (inventory_txn_id);
           * accumulate the issue's extended cost into total_value.
      5. 422 if total_value <= 0 (a zero-value ship cannot post a balanced Dr/Cr
         and has no COGS meaning) — mirrors the issue_components zero-value guard.
      6. ONE balanced JE Dr 5100 COGS / Cr 1130 Inventory for the total shipped
         value, source-linked to the shipment (post_journal_entry(commit=False)).
      7. Set status 'shipped'; single db.commit(); return the ShipmentRead.

    GELATO never writes InventoryTxn itself — the ledger legs are SYERP's
    post_issue and the JE is SYERP's post_journal_entry; both ride this
    transaction's single commit (commit=False) so the whole ship is atomic
    (SYERP-13 AC1). Because each post_issue flushes its leg, the SO line objects
    loaded per line share the session identity map, so repeated draws of the same
    SO line accumulate qty_shipped / relieve qty_reserved without lost updates.
    """
    from app.modules.crumb.models import SalesOrder, SalesOrderLine
    from app.modules.gelato.models import Shipment, ShipmentLine
    from app.modules.syerp.models import InventoryItem
    from app.modules.syerp.service import (
        _gl_account_id_by_code,
        post_issue,
        post_journal_entry,
    )

    # (1) Load the shipment FOR UPDATE and gate on the shipment FSM. Locking the
    #     shipment row first (before the item locks below — one row, sorted-single,
    #     deadlock-free) serializes two concurrent ships of the SAME shipment: the
    #     loser blocks here, and Postgres re-reads the row after the lock is granted,
    #     so it sees the winner's 'shipped' status and 409s at the gate instead of
    #     double-issuing + double-posting COGS. Only 'packed' has 'shipped' in its
    #     allowed set, so this gate alone enforces the packed guard.
    shipment = (
        await db.execute(
            select(Shipment).where(Shipment.id == shipment_id).with_for_update()
        )
    ).scalar_one_or_none()
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )
    if "shipped" not in SHIPMENT_TRANSITIONS[shipment.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Shipment {shipment_id} is '{shipment.status}'; only a packed "
                "shipment can be shipped."
            ),
        )

    # (2) Load the shipment's lines (422 if none — nothing to issue, no JE).
    result = await db.execute(
        select(ShipmentLine)
        .where(ShipmentLine.shipment_id == shipment_id)
        .order_by(ShipmentLine.id)
    )
    lines = list(result.scalars().all())
    if not lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Shipment {shipment_id} has no lines to ship.",
        )

    # (3) Lock the DISTINCT contended InventoryItem rows FOR UPDATE in sorted-id
    #     order BEFORE any on-hand read (issue_components template). post_issue
    #     re-locks each item, but taking the locks up front in a stable order is
    #     the deadlock-free serialization point for a concurrent ship.
    for locked_id in sorted({line.item_id for line in lines}):
        await db.execute(
            select(InventoryItem.id).where(InventoryItem.id == locked_id).with_for_update()
        )

    # The COGS memo names the SO the shipment fulfils (FK guarantees it exists).
    so = await db.get(SalesOrder, shipment.sales_order_id)

    # (4) Per line: delegate the staging-bin draw to post_issue (commit=False, so
    #     each leg flushes and its per-bin floor guard is CUMULATIVE across lines),
    #     then stamp qty_shipped / relieve the reservation on the SAME SO line.
    total_value = Decimal("0")
    for line in lines:
        txn, line_value = await post_issue(
            db,
            item_id=line.item_id,
            location_id=shipment.location_id,
            bin_id=shipment.staging_bin_id,
            qty=line.qty,
            actor_id=actor_id,
            source_type="gelato_shipment",
            source_id=str(shipment.id),
            commit=False,
        )

        so_line = await db.get(SalesOrderLine, line.sales_order_line_id)
        # Over-ship guard: never ship beyond the ordered qty (422). Checked on the
        # live (identity-mapped) SO line, so accumulated qty_shipped is respected.
        if so_line.qty_shipped + line.qty > so_line.qty_ordered:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Shipping {line.qty} of sales order line {so_line.id} would "
                    f"exceed its ordered qty {so_line.qty_ordered} (already shipped "
                    f"{so_line.qty_shipped})."
                ),
            )
        so_line.qty_shipped = so_line.qty_shipped + line.qty
        # Relieve the reservation for the shipped qty (D-P12b-5) — never below zero.
        so_line.qty_reserved = max(Decimal("0"), so_line.qty_reserved - line.qty)
        # Soft-link the ShipmentLine to its issue ledger leg.
        line.inventory_txn_id = txn.id
        total_value += line_value

    # (5) Zero-value guard: a balanced COGS JE needs a strictly positive total
    #     (mirrors the issue_components zero-value guard).
    if total_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Shipment has no material value (items have zero moving-average "
                "cost); nothing to post to COGS."
            ),
        )

    # post_issue already flushed each issue leg (materializing the txn.id soft-links
    # above); a defensive flush keeps the shape identical to issue_components.
    await db.flush()

    # (6) ONE balanced JE: Dr 5100 COGS / Cr 1130 Inventory for the shipped value,
    #     source-linked to the shipment. Rides this transaction's single commit.
    cogs_account_id = await _gl_account_id_by_code(db, "5100")
    inventory_account_id = await _gl_account_id_by_code(db, "1130")
    je = await post_journal_entry(
        db,
        entry_date=date.today(),
        memo=f"Shipment {shipment.id} — SO {so.so_number} COGS",
        lines=[
            {"account_id": cogs_account_id, "debit": total_value, "credit": 0},
            {"account_id": inventory_account_id, "debit": 0, "credit": total_value},
        ],
        actor_id=actor_id,
        source_type="gelato_shipment",
        source_id=str(shipment.id),
        commit=False,
    )
    shipment.journal_entry_id = je.id

    # (7) Advance to shipped and take the single atomic commit (every post_issue
    #     and the JE used commit=False, so they land together — SYERP-13 AC1).
    shipment.status = "shipped"
    await db.commit()

    return await _load_shipment_read(db, shipment.id)


async def get_shipment(db: AsyncSession, shipment_id: int) -> "ShipmentRead":
    """
    Read one shipment with its lines as a ShipmentRead (404 if it does not exist).

    A thin public wrapper over _load_shipment_read for the GET detail route — the
    router stays thin and returns the identical shape the pick/pack/ship entry
    points return. Read-only: no ledger movement, no audit row.
    """
    return await _load_shipment_read(db, shipment_id)


async def _load_shipment_read(db: AsyncSession, shipment_id: int) -> "ShipmentRead":
    """
    Load a shipment with its lines and serialize it as a ShipmentRead.

    Raises 404 if the shipment does not exist. Its lines are ordered by id (insert
    order). Shared by the pick/pack/ship entry points so they return an identical
    shape.
    """
    from app.modules.gelato.models import Shipment, ShipmentLine
    from app.modules.gelato.schemas import ShipmentLineRead, ShipmentRead

    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )

    result = await db.execute(
        select(ShipmentLine)
        .where(ShipmentLine.shipment_id == shipment_id)
        .order_by(ShipmentLine.id)
    )
    lines = list(result.scalars().all())

    return ShipmentRead(
        id=shipment.id,
        sales_order_id=shipment.sales_order_id,
        location_id=shipment.location_id,
        staging_bin_id=shipment.staging_bin_id,
        status=shipment.status,
        journal_entry_id=shipment.journal_entry_id,
        lines=[ShipmentLineRead.model_validate(line) for line in lines],
        created_at=shipment.created_at,
    )
