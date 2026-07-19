# ABOUTME: SYERP accounts-receivable service (SYERP-13) — the sell-side mirror of
# ABOUTME: service/bills.py: INV-#### numbering, the uninvoiced-shipments picker,
# ABOUTME: create/post invoice (Dr 1120 / Cr 4110), and cash receipts (Dr cash /
# ABOUTME: Cr 1120) with FOR-UPDATE locking, validate-before-write, and one commit.
"""SYERP service — AR customer invoices, SO shipment matching, posting, and receipts.

The sell-side mirror of ``service/bills.py`` (Phase 13, SYERP-13). Invoices draw an
uninvoiced *shipped* quantity off a CRUMB sales order line (the sell-side analogue of
a matched PO receipt), post one balanced JE (Dr 1120 Accounts Receivable / Cr 4110
Product Revenue), and are collected by cash receipts (Dr cash / Cr 1120). The pure
helpers, FSM, numbering, FOR-UPDATE locking, validate-all-before-write, and
single-commit atomicity all copy the proven AP shapes — the overpayment predicate is
imported and REUSED from ``bills`` rather than duplicated.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import Invoice, InvoiceLine
    from app.modules.syerp.schemas import (
        InvoiceLineCreate,
        InvoiceRead,
        ReceiptRead,
        UninvoicedShipmentRead,
    )

from app.modules.syerp.service.accounts import _gl_account_id_by_code
from app.modules.syerp.service.bills import _is_overpayment
from app.modules.syerp.service.journal import _require_gl_account, post_journal_entry


# ---------------------------------------------------------------------------
# Accounts-receivable pure helpers (Phase 13, SYERP-13)
# ---------------------------------------------------------------------------
#
# The AR core decisions are pinned in PURE helpers (no DB, no float, no FastAPI) so
# their boundaries are unit-testable in isolation, exactly as the AP bill helpers:
#   - Invoice numbers follow the numeric-safe INV-#### series, mirroring
#     _next_bill_number (numeric-not-lexicographic — D-P9b-1).
#   - Overpayment is the SAME predicate as AP — bills._is_overpayment is imported and
#     reused for the receipt guard (do NOT duplicate).
# INVOICE_TRANSITIONS mirrors BILL_TRANSITIONS' shape (draft -> posted -> paid, paid
# terminal).

_INVOICE_NUMBER_RE = re.compile(r"^INV-[0-9]+$")


def _next_invoice_number(existing_numbers: "Iterable[str]") -> str:
    """
    Compute the next INV-#### number from the set of existing invoice numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric INV-series numbers (matching ``^INV-[0-9]+$``),
    selects the *numerically* highest suffix, and returns that value + 1 zero-padded
    to 4 digits. Returns "INV-0001" when no INV-series numbers exist yet.

    The selection is numeric, never lexicographic: given {"INV-9", "INV-10"} it picks
    10 (not the lexicographically-larger "INV-9") and returns "INV-0011" — mirroring
    _next_bill_number exactly (D-P9b-1).
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _INVOICE_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "INV-0001"
    return f"INV-{max(suffixes) + 1:04d}"


def _uninvoiced_qty(qty_shipped: Decimal, qty_invoiced: Decimal) -> Decimal:
    """
    Pure uninvoiced-quantity helper (no DB — unit-testable).

    Returns the quantity shipped but not yet invoiced (`qty_shipped - qty_invoiced`)
    — the ceiling a new AR invoice line may draw against a sales order line. Decimal
    arithmetic (exact, no float drift — D-11). The sell-side mirror of _unbilled_qty.
    """
    return qty_shipped - qty_invoiced


INVOICE_TRANSITIONS: dict[str, set[str]] = {
    "draft":  {"posted"},
    "posted": {"paid"},
    "paid":   set(),  # terminal — no outgoing transitions
}


def _invoice_transition_allowed(current: str, target: str) -> bool:
    """
    Pure AR-invoice FSM predicate (no DB — unit-testable).

    Returns True when `target` is an allowed successor of `current` per
    INVOICE_TRANSITIONS (draft -> posted -> paid, paid terminal). The service layer
    raises HTTP 422 on top of this; the legality decision is pinned here, mirroring
    BILL_TRANSITIONS. A partial receipt leaves the invoice 'posted' — 'paid' is only
    reached when the open balance hits exactly zero.
    """
    return target in INVOICE_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# AR invoice numbering + uninvoiced-shipments query (Phase 13, SYERP-13)
# ---------------------------------------------------------------------------


async def generate_invoice_number(db: AsyncSession) -> str:
    """
    Generate the next invoice number in the INV-#### series (Phase 13).

    Finds the current highest *numeric* suffix among strictly-numeric INV-series
    numbers (matching ``^INV-[0-9]+$``) by casting the digits after "INV-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_invoice_number helper. Returns "INV-0001" when no INV-series numbers exist.

    Mirrors generate_bill_number: the regex filter MUST precede the cast (a bare cast
    over ``LIKE 'INV-%'`` would throw on any non-numeric number), and
    ``func.substring(invoice_number, 5)`` skips the 4-character "INV-" prefix
    (Postgres substring is 1-indexed, so position 5 is the first digit). The DB unique
    constraint on syerp_invoice.invoice_number is the authoritative guard; this is a
    best-effort generator and the caller retries once on IntegrityError.
    """
    from app.modules.syerp.models import Invoice

    result = await db.execute(
        select(Invoice.invoice_number)
        .where(Invoice.invoice_number.op("~")(r"^INV-[0-9]+$"))
        .order_by(cast(func.substring(Invoice.invoice_number, 5), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_invoice_number([max_number] if max_number is not None else [])


async def list_uninvoiced_shipments(
    db: AsyncSession, customer_id: str
) -> "list[UninvoicedShipmentRead]":
    """
    List a customer's shipped-but-not-fully-invoiced SO lines (the invoice-line picker).

    For every sales order line of `customer_id`'s sales orders, computes
    `uninvoiced_qty = qty_shipped - qty_invoiced` (both stored accumulators on the
    line — no coalesce needed, they default to 0 and are never NULL). Only lines with
    uninvoiced_qty > 0 are returned, carrying the locked unit_price plus the
    sales_order_line_id, so_number, item_id and description (per UninvoicedShipmentRead).
    The sell-side mirror of list_unbilled_receipts. Ordered by so_number, then the
    line's sort_order for a stable presentation.
    """
    from app.modules.crumb.models import SalesOrder, SalesOrderLine
    from app.modules.syerp.models import InventoryItem
    from app.modules.syerp.schemas import UninvoicedShipmentRead

    # LEFT JOIN the stock item so a stock line carries a human "code — name" label
    # (GAP-2 fix) instead of the UI rendering a bare item UUID; non-stock lines
    # (item_id NULL) leave item_code/item_name NULL and fall back to `description`.
    result = await db.execute(
        select(
            SalesOrderLine,
            SalesOrder.so_number,
            InventoryItem.code,
            InventoryItem.name,
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .outerjoin(InventoryItem, InventoryItem.id == SalesOrderLine.item_id)
        .where(
            SalesOrder.partner_id == customer_id,
            SalesOrderLine.qty_shipped - SalesOrderLine.qty_invoiced > 0,
        )
        .order_by(SalesOrder.so_number, SalesOrderLine.sort_order)
    )
    rows = result.all()

    return [
        UninvoicedShipmentRead(
            sales_order_line_id=line.id,
            so_number=so_number,
            item_id=line.item_id,
            item_label=(f"{item_code} — {item_name}" if item_code else None),
            description=line.description,
            uninvoiced_qty=_uninvoiced_qty(line.qty_shipped, line.qty_invoiced),
            unit_price=line.unit_price,
        )
        for line, so_number, item_code, item_name in rows
    ]


# ---------------------------------------------------------------------------
# AR invoice CRUD + shipment match (Phase 13, SYERP-13)
# ---------------------------------------------------------------------------
#
# InvoiceRead nests its lines and carries two DERIVED roll-ups (total, open_balance)
# computed here, not stored — so the service constructs InvoiceRead/InvoiceLineRead
# explicitly rather than serializing the ORM row for those fields. Lines and receipt
# allocations are assembled via ordered/grouped SELECTs (the models declare NO ORM
# relationships, to avoid MissingGreenlet in the async context — RESEARCH.md
# Pitfall 2). Every sum coalesces EACH side independently so a NULL sum on a
# not-yet-invoiced / not-yet-received row degrades to 0, never NULL (D-P8-4).


class _PreparedInvoiceLine(NamedTuple):
    """A validated invoice line ready to persist (pure values — survives rollback)."""

    sales_order_line_id: str
    invoiced_qty: Decimal
    unit_price: Decimal
    amount: Decimal


async def create_invoice(
    db: AsyncSession,
    *,
    customer_id: str,
    sales_order_id: str | None,
    invoice_date: date | None = None,
    lines: "Iterable[InvoiceLineCreate]",
    actor_id: str,
    _attempt: int = 0,
) -> "InvoiceRead":
    """
    Create a draft customer invoice against uninvoiced SO shipments (Phase 13).

    The sell-side mirror of create_bill. Customer gate (mirrors the vendor gate):
    `customer_id` must reference an existing Partner with is_customer==True, else 422.
    Every line is validated BEFORE any write (no partial invoice):
      - the sales order line is loaded (404 if it does not exist) and must belong to a
        sales order whose partner_id == customer_id (422 otherwise — you cannot invoice
        one customer for another's order);
      - a line may be claimed AT MOST ONCE per invoice (dup-line guard, 422);
      - the still-invoiceable quantity is recomputed LIVE as qty_shipped − qty_invoiced
        and the requested invoiced_qty must not exceed it (422 — the negative-open
        guard; you cannot invoice more than has shipped);
      - the line books at the SO line's own LOCKED unit_price, amount = invoiced_qty *
        unit_price.
    On success each SO line's qty_invoiced accumulator is bumped (the sell-side mirror
    of GELATO stamping qty_shipped), the invoice is assigned a server-generated
    INV-#### number (retried once on a unique-constraint collision, mirroring
    create_bill), status 'draft', invoice_date defaulting to today when omitted, and
    its lines are persisted in input order (line_no from 1) in ONE commit. Returned via
    get_invoice.

    The target SO-line rows are locked FOR UPDATE up-front in sorted id order
    (deadlock-safe) BEFORE the read: the uninvoiced-quantity guard is read-then-write,
    so two concurrent create_invoice transactions for the same SO line would each read
    the same qty_invoiced and both pass — over-invoicing the shipment. The lock is held
    until this function's single db.commit() (mirrors create_bill's PO-line lock).
    """
    import sqlalchemy.exc

    from app.modules.crumb.models import SalesOrder, SalesOrderLine
    from app.modules.syerp.models import Invoice, InvoiceLine, Partner

    # Customer gate — the partner must exist AND be a customer (mirror the vendor gate).
    result = await db.execute(select(Partner).where(Partner.id == customer_id))
    customer = result.scalars().first()
    if customer is None or not customer.is_customer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Partner {customer_id} is not a customer (is_customer must be True).",
        )

    # Validate the optional SO-header link UP FRONT. sales_order_id is a client-supplied
    # nullable FK; an invalid one would otherwise surface only as an IntegrityError on the
    # header flush below — indistinguishable there from an invoice-number collision, so the
    # retry path would recurse forever on a bad id. Reject it here with a clean 404.
    if sales_order_id is not None:
        so_header = await db.execute(
            select(SalesOrder.id).where(SalesOrder.id == sales_order_id)
        )
        if so_header.scalar() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sales order {sales_order_id} not found.",
            )

    line_list = list(lines)

    # Serialize concurrent invoices that draw the SAME shipment line: lock each target
    # SO-line row FOR UPDATE up-front, in sorted id order (deadlock-safe), so a second
    # txn blocks until the first commits and then re-reads the true qty_invoiced. The
    # lock is held until this function's single db.commit() (mirrors create_bill).
    target_line_ids = sorted({d.sales_order_line_id for d in line_list})
    for locked_id in target_line_ids:
        await db.execute(
            select(SalesOrderLine.id)
            .where(SalesOrderLine.id == locked_id)
            .with_for_update()
        )

    # Validate every line first, collecting pure values (no partial invoice). A single
    # invoice must claim each shipment line AT MOST ONCE.
    seen_line_ids: set[str] = set()
    prepared: list[_PreparedInvoiceLine] = []
    for data in line_list:
        if data.sales_order_line_id in seen_line_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Sales order line {data.sales_order_line_id} is invoiced more than "
                    f"once on this invoice; an invoice may claim each line at most once."
                ),
            )
        seen_line_ids.add(data.sales_order_line_id)

        so_result = await db.execute(
            select(SalesOrderLine).where(SalesOrderLine.id == data.sales_order_line_id)
        )
        so_line = so_result.scalars().first()
        if so_line is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sales order line {data.sales_order_line_id} not found.",
            )
        # The line must belong to a sales order for THIS customer (422 otherwise).
        parent_result = await db.execute(
            select(SalesOrder.partner_id).where(SalesOrder.id == so_line.sales_order_id)
        )
        parent_partner_id = parent_result.scalar()
        if parent_partner_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Sales order line {so_line.id} belongs to a different customer's "
                    f"order; it cannot be invoiced to customer {customer_id}."
                ),
            )
        # Recompute the still-invoiceable quantity LIVE and reject over-invoicing (the
        # negative-open guard): you cannot invoice more than has shipped uninvoiced.
        uninvoiced = _uninvoiced_qty(so_line.qty_shipped, so_line.qty_invoiced)
        if data.invoiced_qty > uninvoiced:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invoiced quantity {data.invoiced_qty} exceeds the uninvoiced "
                    f"shipped quantity {uninvoiced} for sales order line {so_line.id}."
                ),
            )
        prepared.append(
            _PreparedInvoiceLine(
                sales_order_line_id=so_line.id,
                invoiced_qty=data.invoiced_qty,
                unit_price=so_line.unit_price,
                amount=data.invoiced_qty * so_line.unit_price,
            )
        )
        # Bump the shipped-line's invoiced accumulator (mirrors GELATO stamping
        # qty_shipped) — the ceiling the next invoice may draw against.
        so_line.qty_invoiced = so_line.qty_invoiced + data.invoiced_qty

    # Persist header (retry once on an auto-generated number collision, mirroring
    # create_bill) then its lines, in one commit.
    invoice_number = await generate_invoice_number(db)
    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        invoice_date=invoice_date or date.today(),
        status="draft",
        actor_id=actor_id,
    )
    db.add(invoice)
    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        # sales_order_id was validated up front, so the only expected integrity failure
        # here is an invoice-number collision — retry ONCE (mirrors create_bill's contract).
        # Bound the retry so any unexpected integrity error fails loudly rather than
        # recursing forever.
        if _attempt >= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not assign a unique invoice number; please retry.",
            )
        # The rollback discarded the qty_invoiced bumps too; re-lock, re-validate and
        # re-apply against the now-current state before retrying the header insert.
        return await create_invoice(
            db,
            customer_id=customer_id,
            sales_order_id=sales_order_id,
            invoice_date=invoice_date,
            lines=line_list,
            actor_id=actor_id,
            _attempt=_attempt + 1,
        )

    for line_no, p in enumerate(prepared, start=1):
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                line_no=line_no,
                sales_order_line_id=p.sales_order_line_id,
                invoiced_qty=p.invoiced_qty,
                unit_price=p.unit_price,
                amount=p.amount,
            )
        )

    await db.commit()
    return await get_invoice(db, invoice.id)


async def _get_invoice_row(
    db: AsyncSession, invoice_id: str, *, for_update: bool = False
) -> "Invoice":
    """
    Load an Invoice ORM row by id (internal helper).

    Raises HTTP 404 if no invoice with the given id exists (mirrors _get_bill_row).
    When ``for_update`` is True the row is locked FOR UPDATE for the rest of the
    transaction — record_receipt uses this to serialize concurrent receipts against
    the same invoice so its open-balance read cannot race.
    """
    from app.modules.syerp.models import Invoice

    stmt = select(Invoice).where(Invoice.id == invoice_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    invoice = result.scalars().first()
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    return invoice


async def _load_invoice_lines(db: AsyncSession, invoice_id: str) -> "list[InvoiceLine]":
    """Return an invoice's lines ordered by line_no (no ORM relationship — Pitfall 2)."""
    from app.modules.syerp.models import InvoiceLine

    result = await db.execute(
        select(InvoiceLine)
        .where(InvoiceLine.invoice_id == invoice_id)
        .order_by(InvoiceLine.line_no)
    )
    return list(result.scalars().all())


async def _invoice_received_amount(db: AsyncSession, invoice_id: str) -> Decimal:
    """
    Return the total allocated (collected) against an invoice.

    Sums ReceiptAllocation.amount for `invoice_id`, coalescing to 0 (D-P8-4): an
    invoice with no allocations yet yields Decimal("0"), never NULL. The sell-side
    mirror of _bill_paid_amount.
    """
    from app.modules.syerp.models import ReceiptAllocation

    result = await db.execute(
        select(func.coalesce(func.sum(ReceiptAllocation.amount), 0)).where(
            ReceiptAllocation.invoice_id == invoice_id
        )
    )
    return Decimal(result.scalar() or 0)


def _invoice_to_read(
    invoice: "Invoice", lines: "Iterable[InvoiceLine]", received: Decimal
) -> "InvoiceRead":
    """
    Assemble an InvoiceRead from an Invoice ORM row, its lines, and its collected total.

    total and open_balance are DERIVED, not stored: total = Σ line.amount (an empty
    line set folds to Decimal("0")), open_balance = total − received. Each side is
    coalesced independently (D-P8-4), so the model is CONSTRUCTED explicitly rather
    than validated from_attributes for those two fields (mirrors _bill_to_read).
    """
    from app.modules.syerp.schemas import InvoiceLineRead, InvoiceRead

    lines = list(lines)
    total = sum((line.amount for line in lines), Decimal("0"))
    return InvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        sales_order_id=invoice.sales_order_id,
        invoice_date=invoice.invoice_date,
        status=invoice.status,
        memo=invoice.memo,
        posted_at=invoice.posted_at,
        total=total,
        open_balance=total - received,
        lines=[InvoiceLineRead.model_validate(line) for line in lines],
        created_at=invoice.created_at,
    )


async def get_invoice(db: AsyncSession, invoice_id: str) -> "InvoiceRead":
    """
    Load an invoice (header + nested lines + derived roll-ups) by id.

    Raises HTTP 404 if no invoice with the given id exists (mirrors get_bill).
    """
    invoice = await _get_invoice_row(db, invoice_id)
    lines = await _load_invoice_lines(db, invoice_id)
    received = await _invoice_received_amount(db, invoice_id)
    return _invoice_to_read(invoice, lines, received)


async def list_invoices(
    db: AsyncSession,
    customer_id: str | None = None,
    status: str | None = None,
) -> "list[InvoiceRead]":
    """
    List invoices (newest-first), optionally filtered by customer and/or status.

    Each invoice is returned as an InvoiceRead with its lines nested and its derived
    total/open_balance rolled up. Lines and receipt allocations are fetched in one
    query each over all returned invoice ids and grouped in memory (no per-invoice
    N+1); the allocation sum coalesces to 0 for uncollected invoices (D-P8-4). Ordered
    by created_at DESC, then invoice_number DESC for a stable tie-break (mirrors
    list_bills).
    """
    from app.modules.syerp.models import Invoice, InvoiceLine, ReceiptAllocation

    stmt = select(Invoice)
    if customer_id is not None:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc(), Invoice.invoice_number.desc())

    result = await db.execute(stmt)
    invoices = list(result.scalars().all())
    if not invoices:
        return []

    invoice_ids = [invoice.id for invoice in invoices]

    lines_result = await db.execute(
        select(InvoiceLine)
        .where(InvoiceLine.invoice_id.in_(invoice_ids))
        .order_by(InvoiceLine.line_no)
    )
    lines_by_invoice: dict[str, list[InvoiceLine]] = {iid: [] for iid in invoice_ids}
    for line in lines_result.scalars().all():
        lines_by_invoice[line.invoice_id].append(line)

    received_result = await db.execute(
        select(
            ReceiptAllocation.invoice_id,
            func.coalesce(func.sum(ReceiptAllocation.amount), 0),
        )
        .where(ReceiptAllocation.invoice_id.in_(invoice_ids))
        .group_by(ReceiptAllocation.invoice_id)
    )
    received_by_invoice = {iid: Decimal(amount) for iid, amount in received_result.all()}

    return [
        _invoice_to_read(
            invoice,
            lines_by_invoice[invoice.id],
            received_by_invoice.get(invoice.id, Decimal("0")),
        )
        for invoice in invoices
    ]


# ---------------------------------------------------------------------------
# AR invoice posting (Phase 13, SYERP-13)
# ---------------------------------------------------------------------------


async def post_invoice(db: AsyncSession, invoice_id: str, actor_id: str) -> "InvoiceRead":
    """
    Post a draft AR invoice to the GL, flipping it draft -> posted (Phase 13).

    The sell-side mirror of post_bill. Loads the invoice (404 if missing) and rejects a
    non-draft invoice with 422 via the INVOICE_TRANSITIONS FSM guard (a posted/paid
    invoice cannot be re-posted). Builds ONE balanced journal entry from the invoice's
    lines and posts it through post_journal_entry with commit=False, then stamps
    status='posted' + posted_at and takes the SINGLE commit — the JE, the status flip,
    and the timestamp share one atomic transaction: an invoice can never flip to Posted
    without its balanced GL entry, and if the JE raises nothing persists.

    The journal entry (the revenue-recognition posting):
      - Dr 1120 Accounts Receivable for the whole invoice total (Σ line.amount),
      - Cr 4110 Product Revenue for the same total.

    entry_date = invoice.invoice_date (NOT today) so the 1120 control account's
    entry_date-aged balance ties out to the AR subledger's invoice_date aging — the
    aging tie-out crux (mirrors post_bill's bill_date choice).

    Returns the posted invoice as an InvoiceRead. Audit (invoice.posted) is the
    router's job; this service NEVER writes audit and takes exactly one commit.
    """
    invoice = await _get_invoice_row(db, invoice_id)

    # FSM guard: only a draft invoice may be posted (422 otherwise).
    if not _invoice_transition_allowed(invoice.status, "posted"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot post invoice {invoice.invoice_number}: it is "
                f"'{invoice.status}', only a 'draft' invoice can be posted."
            ),
        )

    lines = await _load_invoice_lines(db, invoice_id)

    ar_account_id = await _gl_account_id_by_code(db, "1120")
    revenue_account_id = await _gl_account_id_by_code(db, "4110")

    invoice_total = sum((line.amount for line in lines), Decimal("0"))

    # One balanced JE: Dr 1120 AR / Cr 4110 Revenue for the whole total. commit=False:
    # the JE rides THIS transaction's single commit alongside the status flip below —
    # no partial post.
    await post_journal_entry(
        db,
        entry_date=invoice.invoice_date,
        memo=f"AR invoice {invoice.invoice_number}",
        lines=[
            {"account_id": ar_account_id, "debit": invoice_total, "credit": 0},
            {"account_id": revenue_account_id, "debit": 0, "credit": invoice_total},
        ],
        actor_id=actor_id,
        source_type="ar_invoice",
        source_id=invoice.id,
        commit=False,
    )

    invoice.status = "posted"
    invoice.posted_at = datetime.now(timezone.utc)

    await db.commit()
    return await get_invoice(db, invoice.id)


# ---------------------------------------------------------------------------
# AR cash receipts (Phase 13, SYERP-13)
# ---------------------------------------------------------------------------


async def advance_invoice_status(
    db: AsyncSession, invoice_id: str, target: str, actor_id: str
) -> "InvoiceRead":
    """
    Advance an AR invoice through the FSM (Phase 13).

    The sell-side mirror of advance_bill_status. Validates the invoice exists (404) and
    that `target` is an allowed successor of the current status per INVOICE_TRANSITIONS
    (draft -> posted -> paid, paid terminal) — 422 if not. Sets invoice.status = target
    and flushes (NOT commits): the caller owns the single commit so the transition can
    ride the same unit of work as its side effects — record_receipt rolls an invoice to
    'paid' inside the receipt's own transaction. Returns the updated invoice as an
    InvoiceRead (header + nested lines).
    """
    invoice = await _get_invoice_row(db, invoice_id)

    if not _invoice_transition_allowed(invoice.status, target):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition invoice from '{invoice.status}' to '{target}'. "
                f"Allowed transitions: "
                f"{sorted(INVOICE_TRANSITIONS.get(invoice.status, set()))}"
            ),
        )

    invoice.status = target
    await db.flush()

    return await get_invoice(db, invoice_id)


async def record_receipt(
    db: AsyncSession,
    *,
    receipt_date: date,
    cash_account_id: int,
    reference: str | None,
    allocations: "Iterable[object]",
    actor_id: str,
) -> "ReceiptRead":
    """
    Record a cash receipt against one or more posted AR invoices (Phase 13).

    The sell-side mirror of record_payment. `allocations` is the ReceiptCreate payload's
    list of (invoice_id, amount) items — each a ReceiptAllocationCreate (or any object
    exposing `.invoice_id` / `.amount`). The whole collection is ONE atomic unit of
    work: a single ``db.commit`` at the very end, so every guard below rejects (422/404)
    with NOTHING persisted, and a successful receipt lands its header, allocations, the
    balanced GL entry, and any auto-Paid transition together — never partially.

    Guard order — each rejection mutates nothing:
      1. `cash_account_id` must resolve to a GL account of type ASSET (422 else) — the
         funds land in a cash/bank asset (default 1110; 1111 is ASSET too).
      2. Σ allocation amounts must be > 0, and every individual amount > 0 (422 else).
      3. For each allocation the invoice must exist (404) and be 'posted' (422 for a
         'draft' or 'paid' invoice). The invoice's LIVE open_balance is total invoiced
         (Σ line.amount, folded from Decimal("0")) minus the coalesced Σ of PRIOR
         ReceiptAllocation.amount (_invoice_received_amount, D-P8-4) — each side
         coalesced independently. Overpayment is rejected via the pure, REUSED
         bills._is_overpayment (receipt > open_balance; the == boundary fully collects).
         When the SAME invoice appears in several allocations of this one receipt they
         must not JOINTLY overpay: the claimed amount is accumulated per invoice_id and
         the running total checked against the live open_balance.

    On success, in that single transaction:
      - persist a Receipt header (amount = Σ allocations) + one ReceiptAllocation row
        per allocation;
      - post ONE balanced JE (commit=False): Dr the cash account / Cr 1120 Accounts
        Receivable, for the receipt total — the funds arrive in cash, the receivable
        drops;
      - for each touched invoice, re-derive open_balance INCLUDING the just-added
        allocations; when it hits EXACTLY zero, advance the invoice 'posted' -> 'paid'
        via advance_invoice_status (auto-Paid). A partial receipt leaves the invoice
        'posted' with a reduced open_balance.

    The target invoice rows are locked FOR UPDATE up-front in sorted id order
    (deadlock-safe) BEFORE the guard read — the overpayment guard is read-then-write, so
    a second concurrent receipt blocks until the first commits and re-reads the true
    received sum (mirrors record_payment). Audit (receipt.recorded) is the router's job;
    this service NEVER writes audit and takes exactly one commit. Returns the receipt as
    a ReceiptRead (constructed explicitly; allocations loaded via an ordered SELECT — no
    ORM relationship).
    """
    from app.modules.syerp.models import Receipt, ReceiptAllocation
    from app.modules.syerp.schemas import ReceiptAllocationRead, ReceiptRead

    alloc_list = list(allocations)

    # Guard 1: the cash side must be an ASSET account (422 otherwise).
    cash_account = await _require_gl_account(db, cash_account_id)  # 404 if unknown.
    if cash_account.account_type != "ASSET":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"GL account {cash_account.code} is {cash_account.account_type}; a "
                f"receipt must land in an ASSET (cash/bank) account."
            ),
        )

    # Guard 2: a receipt is cash IN — the total and every leg must be positive.
    total = Decimal("0")
    for alloc in alloc_list:
        amount = Decimal(str(alloc.amount))
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each receipt allocation amount must be greater than zero.",
            )
        total += amount
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt total (sum of allocations) must be greater than zero.",
        )

    # Serialize concurrent receipts against the same invoice: lock each target invoice
    # row FOR UPDATE up-front, in sorted id order (deadlock-safe), so a second receipt
    # blocks until the first commits and then re-reads the true received sum. Locks are
    # held until this function's single db.commit() (mirrors record_payment).
    for locked_invoice_id in sorted({alloc.invoice_id for alloc in alloc_list}):
        await _get_invoice_row(db, locked_invoice_id, for_update=True)

    # Guard 3: resolve/validate each invoice and reject overpayment BEFORE any write.
    # open_balance = total invoiced - coalesced prior received (each side coalesced).
    # Same-invoice allocations accumulate so they cannot jointly overpay one balance.
    invoice_rows: dict[str, "Invoice"] = {}
    invoice_total_by_id: dict[str, Decimal] = {}
    open_balance_by_id: dict[str, Decimal] = {}
    claimed_by_id: dict[str, Decimal] = {}
    for alloc in alloc_list:
        invoice_id = alloc.invoice_id
        amount = Decimal(str(alloc.amount))
        if invoice_id not in invoice_rows:
            invoice = await _get_invoice_row(db, invoice_id)  # 404 if unknown.
            if invoice.status != "posted":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot collect invoice {invoice.invoice_number}: it is "
                        f"'{invoice.status}', only a 'posted' invoice can be collected."
                    ),
                )
            lines = await _load_invoice_lines(db, invoice_id)
            invoice_total = sum((line.amount for line in lines), Decimal("0"))
            received = await _invoice_received_amount(db, invoice_id)
            invoice_rows[invoice_id] = invoice
            invoice_total_by_id[invoice_id] = invoice_total
            open_balance_by_id[invoice_id] = invoice_total - received
            claimed_by_id[invoice_id] = Decimal("0")
        claimed_by_id[invoice_id] += amount
        if _is_overpayment(open_balance_by_id[invoice_id], claimed_by_id[invoice_id]):
            invoice = invoice_rows[invoice_id]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Receipt of {claimed_by_id[invoice_id]} overpays invoice "
                    f"{invoice.invoice_number} (open balance "
                    f"{open_balance_by_id[invoice_id]})."
                ),
            )

    # Persist the receipt header first so its id is available for the allocations' FK,
    # the JE source link, and the read-back.
    receipt = Receipt(
        receipt_date=receipt_date,
        cash_account_id=cash_account_id,
        amount=total,
        reference=reference,
        actor_id=actor_id,
    )
    db.add(receipt)
    await db.flush()  # materialize receipt.id.

    for alloc in alloc_list:
        db.add(
            ReceiptAllocation(
                receipt_id=receipt.id,
                invoice_id=alloc.invoice_id,
                amount=Decimal(str(alloc.amount)),
            )
        )

    # One balanced JE (commit=False): Dr the cash account / Cr 1120 AR for the total —
    # rides THIS transaction's single commit alongside the allocations and any auto-Paid
    # flip, so a receipt can never persist without its balanced GL entry.
    ar_account_id = await _gl_account_id_by_code(db, "1120")
    await post_journal_entry(
        db,
        entry_date=receipt_date,
        memo=f"AR receipt {receipt.id}",
        lines=[
            {"account_id": cash_account_id, "debit": total, "credit": 0},
            {"account_id": ar_account_id, "debit": 0, "credit": total},
        ],
        actor_id=actor_id,
        source_type="ar_receipt",
        source_id=receipt.id,
        commit=False,
    )

    # Re-derive each touched invoice's open_balance INCLUDING the just-added allocations
    # (autoflushed above); an invoice settled to EXACTLY zero flips 'posted' -> 'paid'
    # (auto-Paid). A partial receipt leaves it 'posted'.
    for invoice_id in invoice_rows:
        received = await _invoice_received_amount(db, invoice_id)
        if invoice_total_by_id[invoice_id] - received == 0:
            await advance_invoice_status(db, invoice_id, "paid", actor_id)

    await db.commit()

    # Read the allocations back in a stable order (no ORM relationship — Pitfall 2).
    alloc_result = await db.execute(
        select(ReceiptAllocation)
        .where(ReceiptAllocation.receipt_id == receipt.id)
        .order_by(ReceiptAllocation.id)
    )
    saved_allocations = list(alloc_result.scalars().all())
    return ReceiptRead(
        id=receipt.id,
        receipt_date=receipt.receipt_date,
        cash_account_id=receipt.cash_account_id,
        amount=receipt.amount,
        reference=receipt.reference,
        allocations=[ReceiptAllocationRead.model_validate(a) for a in saved_allocations],
        created_at=receipt.created_at,
    )


async def get_receipt(db: AsyncSession, receipt_id: str) -> "ReceiptRead":
    """
    Load a single cash receipt (header + nested allocations) by id.

    Raises HTTP 404 if no receipt with the given id exists. Allocations are read in a
    stable order (ReceiptAllocation.id — no ORM relationship, Pitfall 2). The sell-side
    mirror of the AP payment read.
    """
    from app.modules.syerp.models import Receipt, ReceiptAllocation
    from app.modules.syerp.schemas import ReceiptAllocationRead, ReceiptRead

    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalars().first()
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receipt {receipt_id} not found.",
        )

    alloc_result = await db.execute(
        select(ReceiptAllocation)
        .where(ReceiptAllocation.receipt_id == receipt_id)
        .order_by(ReceiptAllocation.id)
    )
    allocations = list(alloc_result.scalars().all())
    return ReceiptRead(
        id=receipt.id,
        receipt_date=receipt.receipt_date,
        cash_account_id=receipt.cash_account_id,
        amount=receipt.amount,
        reference=receipt.reference,
        allocations=[ReceiptAllocationRead.model_validate(a) for a in allocations],
        created_at=receipt.created_at,
    )


async def list_receipts(db: AsyncSession) -> "list[ReceiptRead]":
    """
    List all recorded cash receipts (Phase 13), each with its allocations nested.

    The sell-side mirror of list_payments. Receipts are an append-only ledger; rows are
    returned in creation order (created_at, then id as a stable tie-break). For each
    receipt the allocations are loaded in the SAME stable order record_receipt reads
    them back (ReceiptAllocation.id — no ORM relationship, Pitfall 2) and grouped in
    memory over all receipt ids (no per-receipt N+1). Each ReceiptRead is constructed
    explicitly, money as Decimal (D-11).
    """
    from app.modules.syerp.models import Receipt, ReceiptAllocation
    from app.modules.syerp.schemas import ReceiptAllocationRead, ReceiptRead

    result = await db.execute(select(Receipt).order_by(Receipt.created_at, Receipt.id))
    receipts = list(result.scalars().all())
    if not receipts:
        return []

    receipt_ids = [receipt.id for receipt in receipts]

    alloc_result = await db.execute(
        select(ReceiptAllocation)
        .where(ReceiptAllocation.receipt_id.in_(receipt_ids))
        .order_by(ReceiptAllocation.id)
    )
    allocations_by_receipt: dict[str, list[ReceiptAllocation]] = {
        receipt_id: [] for receipt_id in receipt_ids
    }
    for allocation in alloc_result.scalars().all():
        allocations_by_receipt[allocation.receipt_id].append(allocation)

    return [
        ReceiptRead(
            id=receipt.id,
            receipt_date=receipt.receipt_date,
            cash_account_id=receipt.cash_account_id,
            amount=receipt.amount,
            reference=receipt.reference,
            allocations=[
                ReceiptAllocationRead.model_validate(a)
                for a in allocations_by_receipt[receipt.id]
            ],
            created_at=receipt.created_at,
        )
        for receipt in receipts
    ]
