"""SYERP service — purchase orders, lines, status, and costed receiving."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        PurchaseOrder,
        PurchaseOrderLine,
    )
    from app.modules.syerp.schemas import (
        POCreate,
        POLineCreate,
        POLineRead,
        POLineUpdate,
        PORead,
    )

from app.modules.syerp.service._common import _COST_QUANTUM
from app.modules.syerp.service.accounts import _gl_account_id_by_code
from app.modules.syerp.service.inventory import post_receipt
from app.modules.syerp.service.items import get_item
from app.modules.syerp.service.journal import post_journal_entry

# ---------------------------------------------------------------------------
# Purchase-order number generation (Phase 8, Task 15)
# ---------------------------------------------------------------------------
#
# PO numbers follow the numeric-safe PO-#### series, exactly mirroring the ITEM-
# generator above (Decision 2): the pure _next_po_number helper is unit-testable
# with NO DB so the digit-boundary guarantee (PO-9 -> PO-0010, numeric-not-
# lexicographic) is pinned in isolation, and generate_po_number is the DB half
# that casts the digits after "PO-" to an integer and orders numerically.

_PO_NUMBER_RE = re.compile(r"^PO-[0-9]+$")


def _next_po_number(existing_numbers: Iterable[str]) -> str:
    """
    Compute the next PO-#### number from the set of existing PO numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric PO-series numbers (matching ``^PO-[0-9]+$``),
    selects the *numerically* highest suffix, and returns that value + 1 zero-padded
    to 4 digits. Returns "PO-0001" when no PO-series numbers exist yet.

    The selection is numeric, never lexicographic: given {"PO-9", "PO-10"} it picks
    10 (not the lexicographically-larger "PO-9") and returns "PO-0011". A
    lexicographic MAX would return "PO-9" as the max and re-issue "PO-0010",
    colliding once the suffix crosses a digit-width boundary — the same Phase-7
    partner defect the numeric generator exists to avoid.
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _PO_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "PO-0001"
    return f"PO-{max(suffixes) + 1:04d}"


async def generate_po_number(db: AsyncSession) -> str:
    """
    Generate the next purchase-order number in the PO-#### series (Task 15).

    Finds the current highest *numeric* suffix among strictly-numeric PO-series
    numbers (matching ``^PO-[0-9]+$``) by casting the digits after "PO-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_po_number helper. Returns "PO-0001" when no PO-series numbers exist.

    The regex filter MUST precede the cast: a bare cast over ``LIKE 'PO-%'`` would
    throw on any non-numeric number. ``func.substring(po_number, 4)`` skips the
    3-character "PO-" prefix (Postgres substring is 1-indexed, so position 4 is
    the first digit).

    The DB unique constraint on syerp_purchase_order.po_number is the authoritative
    guard; this function is a best-effort generator. The caller must handle
    IntegrityError on collision (RESEARCH.md Pattern 3).
    """
    from app.modules.syerp.models import PurchaseOrder

    result = await db.execute(
        select(PurchaseOrder.po_number)
        .where(PurchaseOrder.po_number.op("~")(r"^PO-[0-9]+$"))
        .order_by(cast(func.substring(PurchaseOrder.po_number, 4), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_po_number([max_number] if max_number is not None else [])


# ---------------------------------------------------------------------------
# Purchase-order CRUD (Phase 8, Task 15)
# ---------------------------------------------------------------------------
#
# PORead nests its lines (assembled here, not via a lazy ORM relationship, to
# avoid MissingGreenlet in the async context — RESEARCH.md Pitfall 2). Line
# mutations (add/edit/remove) are permitted ONLY while status == 'draft'
# (AC11-1); the _require_draft guard rejects otherwise with 422 (matching the
# inventory guards). create_po requires a vendor_id whose Partner has
# is_vendor==True (AC11-3).


class _POAggregates(NamedTuple):
    """Per-PO Decimal roll-ups derived from its lines (AC11-3 / AC11-5)."""

    total: Decimal
    total_ordered_qty: Decimal
    total_received_qty: Decimal
    outstanding_qty: Decimal


def _po_aggregates(
    lines: Iterable[tuple[Decimal, Decimal, Decimal]],
) -> _POAggregates:
    """
    Pure per-PO aggregate helper (no DB — unit-testable).

    Given (qty_ordered, unit_cost, qty_received) for EVERY line of a PO, returns:
      - `total` = SUM(qty_ordered * unit_cost) — the PO's ordered value (AC11-3);
      - `total_ordered_qty` / `total_received_qty` = SUM of each quantity;
      - `outstanding_qty` = ordered − received.
    All arithmetic is Decimal so the sums are exact (no float drift, no rounding);
    these numbers feed the vendor status table (AC11-5).
    """
    total = Decimal("0")
    total_ordered = Decimal("0")
    total_received = Decimal("0")
    for qty_ordered, unit_cost, qty_received in lines:
        total += qty_ordered * unit_cost
        total_ordered += qty_ordered
        total_received += qty_received
    return _POAggregates(
        total=total,
        total_ordered_qty=total_ordered,
        total_received_qty=total_received,
        outstanding_qty=total_ordered - total_received,
    )


def _po_to_read(po: PurchaseOrder, lines: Iterable[PurchaseOrderLine]) -> PORead:
    """Assemble a PORead schema from a PurchaseOrder ORM row and its lines."""
    from app.modules.syerp.schemas import POLineRead, PORead

    lines = list(lines)
    agg = _po_aggregates(
        (line.qty_ordered, line.unit_cost, line.qty_received) for line in lines
    )
    return PORead(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        status=po.status,
        notes=po.notes,
        approved_at=po.approved_at,
        approved_by=po.approved_by,
        created_at=po.created_at,
        updated_at=po.updated_at,
        total=agg.total,
        total_ordered_qty=agg.total_ordered_qty,
        total_received_qty=agg.total_received_qty,
        outstanding_qty=agg.outstanding_qty,
        lines=[POLineRead.model_validate(line) for line in lines],
    )


async def _load_po_lines(db: AsyncSession, po_id: str) -> list[PurchaseOrderLine]:
    """Return a PO's lines ordered by line_no (helper for PORead assembly)."""
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.po_id == po_id)
        .order_by(PurchaseOrderLine.line_no)
    )
    return list(result.scalars().all())


async def _get_po_row(
    db: AsyncSession, po_id: str, *, for_update: bool = False
) -> PurchaseOrder:
    """
    Load a PurchaseOrder ORM row by id (internal helper).

    Raises HTTP 404 if no PO with the given id exists (mirrors get_item).
    When ``for_update`` is True the row is locked FOR UPDATE for the rest of the
    transaction — receive_line uses this to serialize concurrent receives against
    the same PO so its qty_received accumulator and status roll-up reads cannot
    race (NFR-7; mirrors _get_bill_row / record_payment).
    """
    from app.modules.syerp.models import PurchaseOrder

    stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    po = result.scalars().first()

    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order {po_id} not found",
        )

    return po


def _require_draft(po: PurchaseOrder) -> None:
    """
    Guard: reject a line mutation when the PO is not in Draft (AC11-1).

    Raises 422 (matching the inventory guards) if po.status != 'draft'. Line
    add/edit/remove are only valid while the order is still a draft; once it is
    approved or receiving has begun the lines are frozen.
    """
    if po.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Purchase order lines can only be modified while the PO is in "
                f"Draft (current status: {po.status})."
            ),
        )


async def create_po(db: AsyncSession, data: POCreate) -> PORead:
    """
    Insert a new purchase-order header (Draft, empty of lines).

    Requires data.vendor_id to reference an existing Partner with is_vendor==True;
    a missing partner or a non-vendor partner is rejected with 422 (AC11-3),
    matching the inventory guards. Auto-generates a numeric-safe PO-#### number
    (generate_po_number). On a unique-constraint IntegrityError (auto-generated
    number race) retries ONCE with a fresh number (RESEARCH.md Pattern 3) — the
    number is always server-generated, so there is no user-supplied 409 branch.

    Returns the created order as a PORead (with an empty lines list). The router
    writes the po.created audit row.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Partner, PurchaseOrder

    # Vendor gate (AC11-3): the partner must exist AND be a vendor.
    result = await db.execute(select(Partner).where(Partner.id == data.vendor_id))
    vendor = result.scalars().first()
    if vendor is None or not vendor.is_vendor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Partner {data.vendor_id} is not a vendor (is_vendor must be True).",
        )

    po_number = await generate_po_number(db)
    po = PurchaseOrder(po_number=po_number, vendor_id=data.vendor_id, notes=data.notes)
    db.add(po)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        # Auto-generated number collision — retry once with a fresh number.
        po_number = await generate_po_number(db)
        po = PurchaseOrder(po_number=po_number, vendor_id=data.vendor_id, notes=data.notes)
        db.add(po)
        await db.flush()

    await db.commit()
    await db.refresh(po)
    return _po_to_read(po, [])


async def list_pos(db: AsyncSession, vendor_id: str | None = None) -> list[PORead]:
    """
    Return purchase orders (newest-first), optionally filtered by vendor.

    Args:
        vendor_id: when supplied, restricts the list to POs for that vendor.

    Each PO is returned as a PORead with its lines nested. Lines are fetched in a
    single query over all returned PO ids and grouped in memory (no per-PO N+1).
    Ordered by created_at DESC, then po_number DESC for a stable tie-break.
    """
    from app.modules.syerp.models import PurchaseOrder, PurchaseOrderLine

    stmt = select(PurchaseOrder)
    if vendor_id is not None:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    stmt = stmt.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.po_number.desc())

    result = await db.execute(stmt)
    pos = list(result.scalars().all())

    if not pos:
        return []

    po_ids = [po.id for po in pos]
    lines_result = await db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.po_id.in_(po_ids))
        .order_by(PurchaseOrderLine.line_no)
    )
    lines_by_po: dict[str, list[PurchaseOrderLine]] = {po_id: [] for po_id in po_ids}
    for line in lines_result.scalars().all():
        lines_by_po[line.po_id].append(line)

    return [_po_to_read(po, lines_by_po[po.id]) for po in pos]


async def get_po(db: AsyncSession, po_id: str) -> PORead:
    """
    Load a purchase order (header + nested lines) by id.

    Raises HTTP 404 if no PO with the given id exists (mirrors get_item).
    """
    po = await _get_po_row(db, po_id)
    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)


async def _next_line_no(db: AsyncSession, po_id: str) -> int:
    """Return the next sequential line_no for a PO (max(line_no)+1, else 1)."""
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(func.max(PurchaseOrderLine.line_no)).where(PurchaseOrderLine.po_id == po_id)
    )
    current_max: int | None = result.scalar()
    return (current_max or 0) + 1


async def add_line(db: AsyncSession, po_id: str, data: POLineCreate) -> POLineRead:
    """
    Append a line to a purchase order (Draft-only, AC11-1).

    Rejects with 404 if the PO or the referenced item does not exist, and with
    422 if the PO is not in Draft (line mutations are frozen after Draft). The
    new line's line_no is auto-assigned sequentially (max(line_no)+1). qty_received
    starts at 0 (only receiving moves it, Decision 5).

    Returns the created line as a POLineRead. The router writes the po.line_added
    audit row.
    """
    from app.modules.syerp.models import PurchaseOrderLine
    from app.modules.syerp.schemas import POLineRead

    po = await _get_po_row(db, po_id)
    _require_draft(po)
    # 404 if the item does not exist (mirrors the receipt/adjustment guards).
    await get_item(db, data.item_id)

    line = PurchaseOrderLine(
        po_id=po_id,
        item_id=data.item_id,
        line_no=await _next_line_no(db, po_id),
        qty_ordered=data.qty_ordered,
        unit_cost=data.unit_cost,
        need_by_date=data.need_by_date,
    )
    db.add(line)

    await db.commit()
    await db.refresh(line)
    return POLineRead.model_validate(line)


async def _get_line_row(
    db: AsyncSession, po_id: str, line_id: str
) -> PurchaseOrderLine:
    """
    Load a PO line by id, scoped to its parent PO (internal helper).

    Raises HTTP 404 if no line with the given id exists on that PO.
    """
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.po_id == po_id,
        )
    )
    line = result.scalars().first()

    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order line {line_id} not found on PO {po_id}",
        )

    return line


async def update_line(
    db: AsyncSession, po_id: str, line_id: str, data: POLineUpdate
) -> POLineRead:
    """
    Apply a partial update to a PO line (PATCH semantics, Draft-only, AC11-1).

    Only provided (non-None) fields are written. Rejects with 404 if the PO or the
    line does not exist, and with 422 if the PO is not in Draft. If item_id is
    changed, the new item must exist (404 otherwise). qty_received / line_no are
    not editable here.

    Returns the updated line as a POLineRead. The router writes the po.line_updated
    audit row.
    """
    from app.modules.syerp.schemas import POLineRead

    po = await _get_po_row(db, po_id)
    _require_draft(po)
    line = await _get_line_row(db, po_id, line_id)

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("item_id") is not None:
        # 404 if the reassigned item does not exist.
        await get_item(db, update_data["item_id"])

    for field, value in update_data.items():
        setattr(line, field, value)

    await db.commit()
    await db.refresh(line)
    return POLineRead.model_validate(line)


async def remove_line(db: AsyncSession, po_id: str, line_id: str) -> None:
    """
    Remove a line from a purchase order (Draft-only, AC11-1).

    Rejects with 404 if the PO or the line does not exist, and with 422 if the PO
    is not in Draft. The router writes the po.line_removed audit row (with the
    line_id from the path).
    """
    po = await _get_po_row(db, po_id)
    _require_draft(po)
    line = await _get_line_row(db, po_id, line_id)

    await db.delete(line)
    await db.commit()


# ---------------------------------------------------------------------------
# Purchase-order FSM transitions (Phase 8, Task 16)
# ---------------------------------------------------------------------------
#
# PO_TRANSITIONS mirrors PLUM's VALID_TRANSITIONS shape (a mapping from each
# status to the set of allowed successor states). advance_po_status validates a
# requested transition against this table and rejects an illegal one with 422
# (AC11-1). The approve/close endpoints call it directly; receiving (Task 17)
# reuses it (or sets status directly) to roll the header forward to
# partially_received / received. Approving additionally stamps approved_at /
# approved_by (D-P8-10).

PO_TRANSITIONS: dict[str, set[str]] = {
    "draft":              {"approved"},
    "approved":           {"partially_received", "received", "closed"},
    "partially_received": {"received", "closed"},
    "received":           {"closed"},
    "closed":             set(),  # terminal — no outgoing transitions
}


async def advance_po_status(
    db: AsyncSession, po_id: str, target: str, actor_id: str
) -> PORead:
    """
    Advance a purchase order through the FSM (Phase 8, Task 16).

    Validates:
      - PO exists (404 if not).
      - target is an allowed successor of the current status per PO_TRANSITIONS
        (422 if not — AC11-1).

    On target == "approved", additionally stamps approved_at (tz-aware UTC now)
    and approved_by = actor_id (D-P8-10). Commits in one transaction and returns
    the updated order as a PORead (header + nested lines).

    Reusable by receiving (Task 17): any transition present in PO_TRANSITIONS is
    accepted, so the approved → partially_received / received roll-up can call
    this helper. The approve/close endpoints wire only the "approved" and
    "closed" targets. The router writes the target-specific audit event
    (po.approved / po.closed).
    """
    po = await _get_po_row(db, po_id)

    allowed = PO_TRANSITIONS.get(po.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition purchase order from '{po.status}' to '{target}'. "
                f"Allowed transitions: {sorted(allowed)}"
            ),
        )

    po.status = target
    if target == "approved":
        po.approved_at = datetime.now(UTC)
        po.approved_by = actor_id

    await db.commit()
    await db.refresh(po)

    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)


# ---------------------------------------------------------------------------
# PO receiving → inventory receipt (Phase 8, Task 17, AC11-4/5, D-P8-7)
# ---------------------------------------------------------------------------
#
# Receiving is the phase crux: it posts a REAL costed inventory receipt through
# the Task-5 post_receipt (the single source of truth for on-hand + moving-avg),
# accumulates against the line's qty_received (Decision 5), rolls the header
# status forward, and rejects over-receipt — all in ONE atomic transaction.
#
# The two decisions the pure helpers pin (no DB, unit-testable):
#   - over-receipt: qty_received + qty > qty_ordered is REJECTED; the boundary
#     qty_received + qty == qty_ordered is ALLOWED (a line may be fully received
#     in one shot). Decimal comparison — exact, no float drift (D-11).
#   - status roll-up: the PO is `received` iff EVERY line is fully received
#     (qty_received >= qty_ordered), otherwise `partially_received` (AC11-5).


def _is_over_receipt(qty_received: Decimal, qty: Decimal, qty_ordered: Decimal) -> bool:
    """
    Pure over-receipt predicate (no DB — unit-testable).

    Returns True when receiving `qty` more would push the line's cumulative
    received quantity PAST what was ordered (`qty_received + qty > qty_ordered`),
    i.e. the receipt must be REJECTED (AC11-4, D-P8-7). The exact boundary —
    `qty_received + qty == qty_ordered` — is ALLOWED (it fully receives the line).
    All arithmetic is Decimal so the boundary is exact with no float drift.
    """
    return qty_received + qty > qty_ordered


def _po_rollup_status(line_qtys: Iterable[tuple[Decimal, Decimal]]) -> str:
    """
    Pure PO status roll-up predicate (no DB — unit-testable).

    Given (qty_ordered, qty_received) pairs for EVERY line of a PO, returns the
    receiving-driven header status: `received` when every line is fully received
    (qty_received >= qty_ordered), otherwise `partially_received` (AC11-5). All
    comparisons are Decimal (exact). Called only after a successful receipt, so at
    least one line has moved — the result is never `approved`.
    """
    if all(received >= ordered for ordered, received in line_qtys):
        return "received"
    return "partially_received"


async def receive_line(
    db: AsyncSession,
    po_id: str,
    line_id: str,
    location_id: int,
    qty: Decimal,
    actor_id: str,
) -> PORead:
    """
    Receive `qty` of a PO line into stock (Phase 8, Task 17, AC11-4/5).

    Guard order — every rejection is 422 with NO mutation. The PO header row is
    locked FOR UPDATE at load (_get_po_row for_update=True), BEFORE the status
    guard and the over-receipt guard read (NFR-7): one PO row serializes ALL
    concurrent receives on that PO, covering the line.qty_received accumulator
    (invariant qty_received <= qty_ordered — two racing receives can no longer
    both read the same qty_received and jointly over-receive) AND the header
    status roll-up read across all lines below. Then:
      1. The PO must be `approved` or `partially_received` (receiving is illegal on
         a draft, a fully-received, or a closed order).
      2. `qty` must be > 0.
      3. Over-receipt is rejected: `qty_received + qty > qty_ordered`
         (_is_over_receipt); the exact boundary (== qty_ordered) is allowed.
    The line is loaded scoped to `po_id` (404 if it does not exist on that PO).

    Lock ORDER is PO → item: post_receipt takes the item-master FOR UPDATE lock
    (NFR-7 Task 1) INSIDE this transaction, after the PO-header lock. No other
    writer takes item → PO, so the ordering is acyclic — no deadlock. Both locks
    are held until this function's single commit.

    On success, in ONE atomic transaction (the phase crux):
      - Post a REAL costed inventory receipt via the Task-5 post_receipt at the
        line's unit_cost, source-linked to this line (source_type='po_receipt',
        source_id=line.id) — feeding SYERP-10 on-hand + moving-average (AC11-4).
        post_receipt is the single source of truth for the ledger + valuation; it
        is NOT reimplemented here. It runs with commit=False so the receipt row,
        the qty_received increment, and the status roll-up share one commit —
        a receipt can never be persisted without its accumulator bump.
      - Increment line.qty_received by qty (Decision 5 accumulator).
      - Recompute the header status across ALL lines (_po_rollup_status): `received`
        when every line is fully received, else `partially_received` (AC11-5).
      - Auto-post a balanced GL journal entry at receipt cost (Phase 9a, SYERP-12
        AC3): Dr 1130 Inventory / Cr 2150 GR/IR for qty×unit_cost, source-linked
        (source_type='po_receipt', source_id=line.id) via post_journal_entry with
        commit=False. The JE rides THIS transaction's single commit alongside the
        stock txn, the qty_received bump, and the status roll-up — a non-zero-cost
        receipt can never persist without its balanced GL entry, and if the JE
        raises nothing persists. A ZERO-cost receipt (amount == 0) skips the GL
        post entirely (an all-zero entry cannot balance) but still records the
        physical stock receipt (Phase 9a verify M1).

    Status roll-up sets po.status DIRECTLY rather than routing through
    advance_po_status. This is deliberate: a second partial receipt while the PO is
    already `partially_received` is a legitimate re-affirmation, but
    partially_received → partially_received is NOT in PO_TRANSITIONS (the FSM guard
    would 422 it). Receiving owns this roll-up, so it bypasses the transition guard
    for the computed value; the FSM guard still governs the operator-driven
    approve/close endpoints (Task 16).

    Returns the updated order as a PORead (header + nested lines). The router
    writes the po.received audit row (with qty + location detail).
    """
    # Lock the PO header FOR UPDATE at load, BEFORE the status guard and the
    # over-receipt guard read: one PO row serializes ALL concurrent receives on
    # this PO (qty_received accumulator + status roll-up). Lock order is
    # PO → item (post_receipt's item-master lock) — acyclic, no deadlock.
    po = await _get_po_row(db, po_id, for_update=True)

    # Guard 1: receiving is only valid on an open, approved order.
    if po.status not in ("approved", "partially_received"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Purchase order lines can only be received while the PO is "
                f"'approved' or 'partially_received' (current status: {po.status})."
            ),
        )

    line = await _get_line_row(db, po_id, line_id)

    # Guard 2: a receipt is stock IN — zero/negative is not a receipt.
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receive quantity must be greater than zero.",
        )

    # Guard 3: over-receipt (== boundary allowed). Reject BEFORE any mutation.
    if _is_over_receipt(line.qty_received, qty, line.qty_ordered):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot receive {qty}: line already received {line.qty_received} "
                f"of {line.qty_ordered} ordered (over-receipt)."
            ),
        )

    # Post the REAL costed receipt through the single source of truth, commit=False
    # so the receipt + accumulator bump + status roll-up commit atomically together.
    await post_receipt(
        db,
        item_id=line.item_id,
        location_id=location_id,
        qty=qty,
        unit_cost=line.unit_cost,
        actor_id=actor_id,
        source_type="po_receipt",
        source_id=line.id,
        commit=False,
    )

    # Auto-post the balanced GL journal entry for this receipt in the SAME unit of
    # work (D-P9a-5): Dr 1130 Inventory / Cr 2150 GR/IR at receipt cost. The amount
    # is qty×unit_cost quantized to scale 6 so the GL entry matches post_receipt's
    # stock valuation exactly. commit=False so the entry + its lines ride the single
    # commit below — if the JE raises (e.g. a control account is missing) the stock
    # txn and accumulator bump roll back too (no partial persist, SYERP-12 AC3).
    #
    # A ZERO-cost receipt (unit_cost == 0 → amount == 0: samples, warranty/RMA
    # replacements, consignment) carries no accounting value: an all-zero JE cannot
    # satisfy _je_is_balanced (every line would set neither a positive debit nor a
    # positive credit) and would 422 the whole receipt, regressing a flow that
    # worked before the GL hook (Phase 9a verify M1). Skip the GL post when the
    # amount rounds to zero — the stock ledger still records the physical receipt.
    amount = (qty * line.unit_cost).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)
    if amount != 0:
        inventory_account_id = await _gl_account_id_by_code(db, "1130")
        grir_account_id = await _gl_account_id_by_code(db, "2150")
        await post_journal_entry(
            db,
            entry_date=date.today(),
            memo=f"PO receipt {line.id}",
            lines=[
                {"account_id": inventory_account_id, "debit": amount},
                {"account_id": grir_account_id, "credit": amount},
            ],
            actor_id=actor_id,
            source_type="po_receipt",
            source_id=line.id,
            commit=False,
        )

    line.qty_received += qty

    # Roll the header status forward across ALL lines (autoflush surfaces the
    # qty_received increment above to this query).
    lines = await _load_po_lines(db, po_id)
    po.status = _po_rollup_status([(ln.qty_ordered, ln.qty_received) for ln in lines])

    await db.commit()
    await db.refresh(po)

    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)
