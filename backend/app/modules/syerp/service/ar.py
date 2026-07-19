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
    from app.modules.syerp.schemas import UninvoicedShipmentRead

    result = await db.execute(
        select(SalesOrderLine, SalesOrder.so_number)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
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
            description=line.description,
            uninvoiced_qty=_uninvoiced_qty(line.qty_shipped, line.qty_invoiced),
            unit_price=line.unit_price,
        )
        for line, so_number in rows
    ]
