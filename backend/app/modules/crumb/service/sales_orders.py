# ABOUTME: CRUMB sales-orders service — SO-#### number generation, direct create
# ABOUTME: (header+lines), read/list, draft-only line edits, and the order-status FSM.
"""CRUMB sales-orders service (business logic).

A sales order is a header (SO-#### number, partner, optional source quote /
opportunity, status, dates) plus ordered lines. A line orders either a SYERP
stock item (`item_id`) or a non-stock free-text item (`item_id` NULL, D-V3-16);
`plum_part_id` is an optional display link to a PLUM catalog part. Each line
carries `qty_reserved`, the reservation accumulator (D-V3-11), which starts at
zero and is moved only by the confirm/cancel reservation side-effects.

Line edits are permitted only while the order is in Draft (409 otherwise). The
status walks the controlled draft → confirmed → fulfilling → closed FSM, with
cancel allowed only from draft/confirmed (SO_TRANSITIONS); an illegal move is
rejected with 422. The reservation-bearing transitions (draft → confirmed and
any → cancelled) are delegated to confirm_sales_order / cancel_sales_order;
the plain status writes (confirmed → fulfilling, fulfilling → closed) are done
here.

Per D-V3-9 this module mirrors quotes.py / syerp/service — small entity module,
lazy imports inside functions to avoid import cycles, one commit per operation.
Audit events are written at the router layer, not here.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crumb.service._common import (
    SO_TRANSITIONS,
    _resolve_customer,
)

if TYPE_CHECKING:
    from app.modules.crumb.models import QuoteLine, SalesOrder, SalesOrderLine
    from app.modules.crumb.schemas import (
        QuoteToSalesOrderRequest,
        SalesOrderCreate,
        SalesOrderLineCreate,
    )


# ---------------------------------------------------------------------------
# SO-number generation (SO-####, D-P8-6 numeric-safe series)
# ---------------------------------------------------------------------------
#
# SO numbers follow the numeric-safe SO-#### series, mirroring
# generate_quote_number / generate_item_code: the highest strictly-NUMERIC
# suffix + 1, zero-padded — never a lexicographic MAX (which re-issues a number
# once the suffix crosses a digit-width boundary, D-P8-6). The DB unique
# constraint on crumb_sales_order.so_number is the authoritative backstop;
# create_sales_order retries once on an IntegrityError collision.


def _next_sales_order_number(existing_max: int | None) -> str:
    """
    Compute the next SO-#### number from the current highest numeric suffix.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Returns "SO-0001" when no SO-series numbers exist yet, otherwise the given
    suffix + 1 zero-padded to 4 digits.
    """
    if existing_max is None:
        return "SO-0001"
    return f"SO-{existing_max + 1:04d}"


async def generate_sales_order_number(db: AsyncSession) -> str:
    """
    Generate the next sales-order number in the SO-#### series (CRUMB-01).

    Finds the current highest *numeric* suffix among strictly-numeric SO-series
    numbers by casting the digits after "SO-" to an integer and ordering
    numerically, then delegates the increment to the pure _next_sales_order_number
    helper. The regex filter MUST precede the cast (a bare cast over
    ``LIKE 'SO-%'`` would throw on a non-numeric number);
    ``func.substring(so_number, 4)`` skips the 3-character "SO-" prefix (Postgres
    substring is 1-indexed, so position 4 is the first digit).
    """
    from app.modules.crumb.models import SalesOrder

    result = await db.execute(
        select(SalesOrder.so_number)
        .where(SalesOrder.so_number.op("~")(r"^SO-[0-9]+$"))
        .order_by(cast(func.substring(SalesOrder.so_number, 4), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()
    existing_max = int(max_number.split("-", 1)[1]) if max_number is not None else None
    return _next_sales_order_number(existing_max)


# ---------------------------------------------------------------------------
# Line construction / item validation (D-V3-16)
# ---------------------------------------------------------------------------


async def _validate_line(db: AsyncSession, line: "SalesOrderLineCreate") -> None:
    """
    Validate one sales-order line before it is persisted.

    A line that supplies an `item_id` must reference an existing SYERP stock item
    (404 via get_item). A NULL `item_id` line is a non-stock / free-text line
    (D-V3-16) and needs no item lookup. Pricing is caller-supplied verbatim
    (unlike quotes, sales-order lines carry an already-agreed unit_price).
    """
    if line.item_id is not None:
        from app.modules.syerp.service import get_item

        await get_item(db, line.item_id)


def _build_line_kwargs(
    sales_order_id: str,
    line: "SalesOrderLineCreate",
    sort_order: int,
) -> dict:
    """Build the SalesOrderLine constructor kwargs from a create line."""
    return {
        "sales_order_id": sales_order_id,
        "item_id": line.item_id,
        "plum_part_id": line.plum_part_id,
        "description": line.description,
        "qty_ordered": line.qty_ordered,
        "unit_price": line.unit_price,
        "qty_reserved": Decimal("0"),
        "sort_order": sort_order,
    }


# ---------------------------------------------------------------------------
# Create / read (CRUMB-01)
# ---------------------------------------------------------------------------


async def create_sales_order(
    db: AsyncSession, data: "SalesOrderCreate", actor_id: str
) -> "SalesOrder":
    """
    Create a draft sales order header and its ordered lines (CRUMB-01).

    Resolves the SYERP customer (404 if not a customer), generates an SO-####
    number, and creates the header in Draft (order_date defaults to today when
    omitted). Each supplied `item_id` line is validated against SYERP stock
    (404); a NULL `item_id` line is a non-stock line (D-V3-16). Lines start with
    qty_reserved = 0 and sort_order = line index. Retries once on an so_number
    IntegrityError (mirrors create_quote). Commits and returns the detail view.
    """
    import sqlalchemy.exc

    from app.modules.crumb.models import SalesOrder, SalesOrderLine

    await _resolve_customer(db, data.partner_id)

    # Validate stock-item references up front (404) so a bad item_id surfaces as a
    # clean 4xx rather than a DB FK IntegrityError that the so_number retry below
    # would misread and re-raise as a 500.
    for line in data.lines:
        await _validate_line(db, line)

    order_date = data.order_date if data.order_date is not None else date.today()

    number = await generate_sales_order_number(db)
    so = SalesOrder(
        so_number=number,
        partner_id=data.partner_id,
        status="draft",
        order_date=order_date,
        required_date=data.required_date,
        actor_id=actor_id,
    )
    db.add(so)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        # Auto-generated SO number collided (race) — retry once with a fresh one.
        await db.rollback()
        number = await generate_sales_order_number(db)
        so = SalesOrder(
            so_number=number,
            partner_id=data.partner_id,
            status="draft",
            order_date=order_date,
            required_date=data.required_date,
            actor_id=actor_id,
        )
        db.add(so)
        await db.flush()

    for index, line in enumerate(data.lines):
        db.add(SalesOrderLine(**_build_line_kwargs(so.id, line, index)))

    await db.commit()
    return await get_sales_order_detail(db, so.id)


# ---------------------------------------------------------------------------
# Conversion — accepted quote → sales order (AC3, AC6, D-V3-16)
# ---------------------------------------------------------------------------


async def _resolve_item_id_for_part(db: AsyncSession, plum_part_id: str | None) -> str | None:
    """
    Resolve a SYERP stock item_id from a quote line's PLUM part link.

    A quote line prices a PLUM catalog part (`plum_part_id`); a sales-order line
    orders a SYERP stock item (`item_id`). The bridge is the advisory
    InventoryItem.plum_part_id link (nullable, no cascade — D-V3-16). Returns the
    first matching InventoryItem.id ordered by id (deterministic — the link is
    not unique, so pick stably), or None when the line carries no part or no
    InventoryItem links that part (a non-stock line — item_id NULL, D-V3-16).
    """
    if plum_part_id is None:
        return None

    from app.modules.syerp.models import InventoryItem

    result = await db.execute(
        select(InventoryItem.id)
        .where(InventoryItem.plum_part_id == plum_part_id)
        .order_by(InventoryItem.id)
        .limit(1)
    )
    return result.scalar()


async def convert_quote_to_sales_order(
    db: AsyncSession,
    quote_id: str,
    data: "QuoteToSalesOrderRequest",
    actor_id: str,
) -> "SalesOrder":
    """
    Convert an accepted quote into a draft sales order (AC3, AC6).

    Loads the quote (404) and requires status == "accepted" (422 otherwise —
    only an accepted quote may be ordered, AC3). Creates a Draft SO for the
    quote's partner, stamping source_quote_id / source_opportunity_id for two-way
    traceability (AC6). Each quote line is copied to an SO line: qty_ordered from
    the quote line's `quantity`, unit_price verbatim, plum_part_id/description
    carried for display, qty_reserved = 0. The line's item_id is resolved from
    the PLUM part via the advisory InventoryItem link (first match, or NULL for a
    part-less / unlinked free-text line — a non-stock line, D-V3-16). Reuses
    generate_sales_order_number and the retry-once idiom (mirrors
    create_sales_order). Commits and returns the detail view.
    """
    import sqlalchemy.exc

    from app.modules.crumb.models import Quote, SalesOrder, SalesOrderLine

    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote '{quote_id}' not found")
    if quote.status != "accepted":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Quote '{quote_id}' is '{quote.status}'; "
                "only an accepted quote can be converted to a sales order."
            ),
        )

    order_date = data.order_date if data.order_date is not None else date.today()

    number = await generate_sales_order_number(db)
    so = SalesOrder(
        so_number=number,
        partner_id=quote.partner_id,
        source_quote_id=quote.id,
        source_opportunity_id=quote.opportunity_id,
        status="draft",
        order_date=order_date,
        required_date=data.required_date,
        actor_id=actor_id,
    )
    db.add(so)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        # Auto-generated SO number collided (race) — retry once with a fresh one.
        await db.rollback()
        number = await generate_sales_order_number(db)
        so = SalesOrder(
            so_number=number,
            partner_id=quote.partner_id,
            source_quote_id=quote.id,
            source_opportunity_id=quote.opportunity_id,
            status="draft",
            order_date=order_date,
            required_date=data.required_date,
            actor_id=actor_id,
        )
        db.add(so)
        await db.flush()

    quote_lines = await _get_quote_lines_for_conversion(db, quote_id)
    for index, ql in enumerate(quote_lines):
        item_id = await _resolve_item_id_for_part(db, ql.plum_part_id)
        db.add(
            SalesOrderLine(
                sales_order_id=so.id,
                item_id=item_id,
                plum_part_id=ql.plum_part_id,
                description=ql.description,
                qty_ordered=ql.quantity,
                unit_price=ql.unit_price,
                qty_reserved=Decimal("0"),
                sort_order=index,
            )
        )

    await db.commit()
    return await get_sales_order_detail(db, so.id)


async def _get_quote_lines_for_conversion(
    db: AsyncSession, quote_id: str
) -> list["QuoteLine"]:
    """Load a quote's lines ordered by sort_order (for line-copy conversion)."""
    from app.modules.crumb.models import QuoteLine

    result = await db.execute(
        select(QuoteLine)
        .where(QuoteLine.quote_id == quote_id)
        .order_by(QuoteLine.sort_order)
    )
    return list(result.scalars().all())


async def _get_sales_order_lines(
    db: AsyncSession, sales_order_id: str
) -> list["SalesOrderLine"]:
    """Load a sales order's lines ordered by sort_order."""
    from app.modules.crumb.models import SalesOrderLine

    result = await db.execute(
        select(SalesOrderLine)
        .where(SalesOrderLine.sales_order_id == sales_order_id)
        .order_by(SalesOrderLine.sort_order)
    )
    return list(result.scalars().all())


async def get_sales_order_detail(db: AsyncSession, so_id: str) -> "SalesOrder":
    """
    Load a sales order with its lines and derived line/total figures (CRUMB-01).

    Raises 404 if the order does not exist. Attaches the service-derived figures
    the schema serializes as transient attributes on the ORM instances (chosen
    over building SalesOrderDetailRead here so the router owns Pydantic
    construction): each line gets `line_total = qty_ordered * unit_price` and
    `shortage = qty_ordered − qty_reserved`, and the header gets `lines` and
    `total_value = Σ line_total`. SalesOrderDetailRead.model_validate(so) then
    reads them straight through from_attributes.
    """
    from app.modules.crumb.models import SalesOrder

    so = await db.get(SalesOrder, so_id)
    if so is None:
        raise HTTPException(status_code=404, detail=f"Sales order '{so_id}' not found")

    lines = await _get_sales_order_lines(db, so_id)
    total = Decimal("0")
    for line in lines:
        line.line_total = line.qty_ordered * line.unit_price
        line.shortage = line.qty_ordered - line.qty_reserved
        total += line.line_total

    so.lines = lines
    so.total_value = total
    return so


async def list_sales_orders(db: AsyncSession) -> list["SalesOrder"]:
    """Return all sales orders ordered by so_number."""
    from app.modules.crumb.models import SalesOrder

    result = await db.execute(select(SalesOrder).order_by(SalesOrder.so_number))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Line editing — Draft only (409 otherwise)
# ---------------------------------------------------------------------------


async def _get_draft_sales_order(db: AsyncSession, so_id: str) -> "SalesOrder":
    """Load a sales order (404) and assert it is editable, i.e. status == draft (409)."""
    from app.modules.crumb.models import SalesOrder

    so = await db.get(SalesOrder, so_id)
    if so is None:
        raise HTTPException(status_code=404, detail=f"Sales order '{so_id}' not found")
    if so.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Sales order '{so_id}' is '{so.status}'; "
                "lines are editable only in draft."
            ),
        )
    return so


async def add_line(
    db: AsyncSession, so_id: str, line: "SalesOrderLineCreate", actor_id: str
) -> "SalesOrderLine":
    """Add an ordered line to a draft sales order (409 if not draft). Returns the line."""
    from app.modules.crumb.models import SalesOrderLine

    await _get_draft_sales_order(db, so_id)
    await _validate_line(db, line)

    existing = await _get_sales_order_lines(db, so_id)
    sort_order = max((ln.sort_order for ln in existing), default=-1) + 1

    row = SalesOrderLine(**_build_line_kwargs(so_id, line, sort_order))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _get_line(db: AsyncSession, so_id: str, line_id: str) -> "SalesOrderLine":
    """Load a sales-order line belonging to the given order (404 if not found)."""
    from app.modules.crumb.models import SalesOrderLine

    line = await db.get(SalesOrderLine, line_id)
    if line is None or line.sales_order_id != so_id:
        raise HTTPException(
            status_code=404,
            detail=f"Sales order line '{line_id}' not found on order '{so_id}'",
        )
    return line


async def update_line(
    db: AsyncSession,
    so_id: str,
    line_id: str,
    patch: "SalesOrderLineCreate",
    actor_id: str,
) -> "SalesOrderLine":
    """
    Replace a draft sales-order line's ordered fields (409 if not draft).

    The patch is a full SalesOrderLineCreate re-validated (item existence) and
    applied. qty_reserved and sort_order are preserved — reservation is never
    moved by a line edit.
    """
    await _get_draft_sales_order(db, so_id)
    line = await _get_line(db, so_id, line_id)
    await _validate_line(db, patch)

    line.item_id = patch.item_id
    line.plum_part_id = patch.plum_part_id
    line.description = patch.description
    line.qty_ordered = patch.qty_ordered
    line.unit_price = patch.unit_price

    await db.commit()
    await db.refresh(line)
    return line


async def delete_line(db: AsyncSession, so_id: str, line_id: str, actor_id: str) -> None:
    """Delete a line from a draft sales order (409 if not draft)."""
    await _get_draft_sales_order(db, so_id)
    line = await _get_line(db, so_id, line_id)
    await db.delete(line)
    await db.commit()


# ---------------------------------------------------------------------------
# Status FSM (draft → confirmed → fulfilling → closed | cancelled)
# ---------------------------------------------------------------------------


async def advance_sales_order_status(
    db: AsyncSession, so_id: str, target_status: str, actor_id: str
) -> "SalesOrder":
    """
    Advance a sales order through the status FSM (CRUMB-01).

    Validates the order exists (404) and that target_status is an allowed
    successor of the current status per SO_TRANSITIONS (422 otherwise). The
    reservation-bearing moves — draft → confirmed and any → cancelled — are
    delegated to confirm_sales_order / cancel_sales_order (they carry the
    soft-reservation side-effects). The remaining plain moves
    (confirmed → fulfilling, fulfilling → closed) are a status write here,
    committed and returned as the detail view.
    """
    from app.modules.crumb.models import SalesOrder

    so = await db.get(SalesOrder, so_id)
    if so is None:
        raise HTTPException(status_code=404, detail=f"Sales order '{so_id}' not found")

    allowed = SO_TRANSITIONS.get(so.status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition sales order from '{so.status}' to "
                f"'{target_status}'. Allowed transitions: {sorted(allowed)}"
            ),
        )

    # Reservation-bearing transitions carry soft-reservation side-effects and are
    # owned by the dedicated functions below (draft → confirmed reserves stock;
    # → cancelled releases it).
    if target_status == "cancelled":
        return await cancel_sales_order(db, so_id, actor_id)
    if so.status == "draft" and target_status == "confirmed":
        return await confirm_sales_order(db, so_id, actor_id)

    # Plain status writes: confirmed → fulfilling, fulfilling → closed.
    so.status = target_status
    await db.commit()
    return await get_sales_order_detail(db, so_id)


# ---------------------------------------------------------------------------
# Reservation-bearing transitions (soft-reservation — wired in Task 8)
# ---------------------------------------------------------------------------


async def confirm_sales_order(
    db: AsyncSession, so_id: str, actor_id: str
) -> "SalesOrder":
    """Confirm a draft sales order, soft-reserving stock (draft → confirmed).

    TODO(Task 8): implement the soft-reservation side-effects (per-line
    qty_reserved against SYERP on-hand) and the status write. Left as an explicit
    seam so advance_sales_order_status can dispatch here without carrying
    reservation logic in the FSM router.
    """
    raise NotImplementedError(
        "confirm_sales_order (soft-reservation) is wired in Task 8"
    )


async def cancel_sales_order(
    db: AsyncSession, so_id: str, actor_id: str
) -> "SalesOrder":
    """Cancel a sales order, releasing any soft-reservations (→ cancelled).

    TODO(Task 8): implement the reservation release (zero each line's
    qty_reserved) and the status write. Left as an explicit seam so
    advance_sales_order_status can dispatch here without carrying reservation
    logic in the FSM router.
    """
    raise NotImplementedError(
        "cancel_sales_order (reservation release) is wired in Task 8"
    )
