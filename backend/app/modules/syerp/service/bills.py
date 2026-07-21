"""SYERP service — AP bills, PO matching, posting, and payments."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        Bill,
        BillLine,
    )
    from app.modules.syerp.schemas import (
        BillLineCreate,
        BillRead,
        UnbilledReceiptRead,
    )

from app.modules.syerp.service.accounts import _gl_account_id_by_code
from app.modules.syerp.service.journal import _require_gl_account, post_journal_entry

# ---------------------------------------------------------------------------
# Accounts-payable pure helpers (Phase 9b, SYERP-12)
# ---------------------------------------------------------------------------
#
# The AP core decisions are pinned in PURE helpers (no DB, no float, no
# FastAPI) so their boundaries are unit-testable in isolation, exactly as the
# PO number/receipt/FSM helpers above:
#   - Bill numbers follow the numeric-safe BILL-#### series, mirroring
#     _next_po_number (numeric-not-lexicographic — D-P9b-1).
#   - Overpayment is rejected when pay_amount > open_balance; the exact
#     boundary pay_amount == open_balance is ALLOWED (it fully pays). Decimal
#     comparison — exact, no float drift (D-11, D-P8-7).
#   - Three-way match is EXACT: a matched line auto-reconciles only when its
#     quantity AND unit cost equal the unbilled/PO figures to the cent — any
#     variance drops to manual review (D-P9b-2).
# BILL_TRANSITIONS mirrors PO_TRANSITIONS' shape (draft -> posted -> paid,
# paid terminal — D-P9b-5).

_BILL_NUMBER_RE = re.compile(r"^BILL-[0-9]+$")


def _next_bill_number(existing_numbers: Iterable[str]) -> str:
    """
    Compute the next BILL-#### number from the set of existing bill numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric BILL-series numbers (matching
    ``^BILL-[0-9]+$``), selects the *numerically* highest suffix, and returns
    that value + 1 zero-padded to 4 digits. Returns "BILL-0001" when no
    BILL-series numbers exist yet.

    The selection is numeric, never lexicographic: given {"BILL-9", "BILL-10"}
    it picks 10 (not the lexicographically-larger "BILL-9") and returns
    "BILL-0011". A lexicographic MAX would re-issue "BILL-0010" once the suffix
    crosses a digit-width boundary — mirroring _next_po_number exactly (D-P9b-1).
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _BILL_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "BILL-0001"
    return f"BILL-{max(suffixes) + 1:04d}"


def _is_overpayment(open_balance: Decimal, pay_amount: Decimal) -> bool:
    """
    Pure overpayment predicate (no DB — unit-testable).

    Returns True when `pay_amount` exceeds the bill's `open_balance`
    (`pay_amount > open_balance`), i.e. the payment must be REJECTED. The exact
    boundary — `pay_amount == open_balance` — is ALLOWED (it fully pays the
    bill) and returns False. All arithmetic is Decimal so the boundary is exact
    with no float drift (D-11, D-P8-7).
    """
    return pay_amount > open_balance


def _unbilled_qty(qty_received: Decimal, already_billed: Decimal) -> Decimal:
    """
    Pure unbilled-quantity helper (no DB — unit-testable).

    Returns the quantity received but not yet billed
    (`qty_received - already_billed`) — the ceiling a new AP bill line may draw
    against a PO receipt. Decimal arithmetic (exact, no float drift — D-11).
    """
    return qty_received - already_billed


def _is_exact_match(
    matched_qty: Decimal,
    unit_cost: Decimal,
    unbilled_qty: Decimal,
    po_unit_cost: Decimal,
) -> bool:
    """
    Pure three-way-match predicate (no DB — unit-testable).

    Returns True only when a bill line matches its PO receipt EXACTLY — the
    matched quantity equals the unbilled quantity AND the unit cost equals the
    PO unit cost (both Decimal-exact). Any quantity or price variance returns
    False and drops the line to manual review (D-P9b-2).
    """
    return matched_qty == unbilled_qty and unit_cost == po_unit_cost


BILL_TRANSITIONS: dict[str, set[str]] = {
    "draft":  {"posted"},
    "posted": {"paid"},
    "paid":   set(),  # terminal — no outgoing transitions
}


def _bill_transition_allowed(current: str, target: str) -> bool:
    """
    Pure AP-bill FSM predicate (no DB — unit-testable).

    Returns True when `target` is an allowed successor of `current` per
    BILL_TRANSITIONS (draft -> posted -> paid, paid terminal). The service layer
    (later task) raises HTTP 422 on top of this; the legality decision is pinned
    here (D-P9b-5), mirroring PO_TRANSITIONS.
    """
    return target in BILL_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# Accounts-payable bill CRUD + three-way match (Phase 9b, SYERP-12 AC4/5)
# ---------------------------------------------------------------------------
#
# BillRead nests its lines and carries two DERIVED roll-ups (total, open_balance)
# that are computed here, not stored — so the service constructs BillRead/
# BillLineRead explicitly rather than serializing the ORM row for those fields.
# Lines and payment allocations are assembled via ordered/grouped SELECTs (the
# models declare NO ORM relationships, to avoid MissingGreenlet in the async
# context — RESEARCH.md Pitfall 2). Every sum coalesces EACH side independently
# (func.coalesce(func.sum(...), 0)) so a NULL sum on a not-yet-billed / not-yet-
# paid row degrades to 0, never NULL — the Phase-9a NULL-propagation defect
# (D-P8-4).


async def generate_bill_number(db: AsyncSession) -> str:
    """
    Generate the next bill number in the BILL-#### series (Phase 9b, D-P9b-1).

    Finds the current highest *numeric* suffix among strictly-numeric BILL-series
    numbers (matching ``^BILL-[0-9]+$``) by casting the digits after "BILL-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_bill_number helper. Returns "BILL-0001" when no BILL-series numbers exist.

    Mirrors generate_po_number: the regex filter MUST precede the cast (a bare cast
    over ``LIKE 'BILL-%'`` would throw on any non-numeric number), and
    ``func.substring(bill_number, 6)`` skips the 5-character "BILL-" prefix
    (Postgres substring is 1-indexed, so position 6 is the first digit). The DB
    unique constraint on syerp_bill.bill_number is the authoritative guard; this is
    a best-effort generator and the caller retries once on IntegrityError.
    """
    from app.modules.syerp.models import Bill

    result = await db.execute(
        select(Bill.bill_number)
        .where(Bill.bill_number.op("~")(r"^BILL-[0-9]+$"))
        .order_by(cast(func.substring(Bill.bill_number, 6), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_bill_number([max_number] if max_number is not None else [])


async def _already_billed_qty(db: AsyncSession, po_line_id: str) -> Decimal:
    """
    Return the quantity of a PO line already drawn onto (non-cancelled) bills.

    Sums BillLine.matched_qty across EVERY matched line for `po_line_id` on any
    bill that is not cancelled — draft AND posted both count, so two open drafts
    cannot double-bill the same receipt. The sum coalesces to 0 (D-P8-4): a PO
    line with no bill lines yet yields Decimal("0"), never NULL.
    """
    from app.modules.syerp.models import Bill, BillLine

    result = await db.execute(
        select(func.coalesce(func.sum(BillLine.matched_qty), 0))
        .select_from(BillLine)
        .join(Bill, Bill.id == BillLine.bill_id)
        .where(BillLine.po_line_id == po_line_id, Bill.status != "cancelled")
    )
    return Decimal(result.scalar() or 0)


async def list_unbilled_receipts(
    db: AsyncSession, vendor_id: str
) -> list[UnbilledReceiptRead]:
    """
    List a vendor's received-but-not-fully-billed PO lines (SC1 — matched picker).

    For every PO line of `vendor_id`'s purchase orders with qty_received > 0,
    computes `unbilled_qty = qty_received - Σ BillLine.matched_qty` where the sum
    spans ALL non-cancelled bills (draft + posted) so an open draft already
    consumes the receipt. Each side of the subtraction is coalesced independently
    — the grouped SUM uses func.coalesce(..., 0) and a PO line with no bill lines
    at all falls back to Decimal("0") — so a not-yet-billed line never yields a
    NULL unbilled quantity (D-P8-4). Only lines with unbilled_qty > 0 are returned,
    carrying po_line_id, po_number, item_id, unbilled_qty, and the PO line unit_cost.
    """
    from app.modules.syerp.models import Bill, BillLine, PurchaseOrder, PurchaseOrderLine
    from app.modules.syerp.schemas import UnbilledReceiptRead

    result = await db.execute(
        select(PurchaseOrderLine, PurchaseOrder.po_number)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
        .where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrderLine.qty_received > 0,
        )
        .order_by(PurchaseOrder.po_number, PurchaseOrderLine.line_no)
    )
    rows = result.all()
    if not rows:
        return []

    line_ids = [line.id for line, _ in rows]
    billed_result = await db.execute(
        select(
            BillLine.po_line_id,
            func.coalesce(func.sum(BillLine.matched_qty), 0),
        )
        .join(Bill, Bill.id == BillLine.bill_id)
        .where(BillLine.po_line_id.in_(line_ids), Bill.status != "cancelled")
        .group_by(BillLine.po_line_id)
    )
    billed_by_line = {po_line_id: Decimal(qty) for po_line_id, qty in billed_result.all()}

    unbilled: list[UnbilledReceiptRead] = []
    for line, po_number in rows:
        already = billed_by_line.get(line.id, Decimal("0"))
        remaining = _unbilled_qty(line.qty_received, already)
        if remaining > 0:
            unbilled.append(
                UnbilledReceiptRead(
                    po_line_id=line.id,
                    po_number=po_number,
                    item_id=line.item_id,
                    unbilled_qty=remaining,
                    unit_cost=line.unit_cost,
                )
            )
    return unbilled


class _PreparedBillLine(NamedTuple):
    """A validated bill line ready to persist (pure values — survives rollback)."""

    line_type: str
    po_line_id: str | None
    matched_qty: Decimal | None
    account_id: int | None
    unit_cost: Decimal | None
    amount: Decimal


async def create_bill(
    db: AsyncSession,
    *,
    vendor_id: str,
    vendor_invoice_ref: str | None,
    bill_date: date | None = None,
    lines: Iterable[BillLineCreate],
    actor_id: str,
) -> BillRead:
    """
    Create a draft vendor bill with three-way PO match validation (SC2, D-P9b-1/2/3).

    Vendor gate (mirrors create_po): `vendor_id` must reference an existing Partner
    with is_vendor==True, else 422. Every line is validated BEFORE any write (no
    partial bill):
      - matched (line_type == 'matched'): the PO line is loaded (404 if it does not
        exist), its unbilled quantity is recomputed LIVE against all non-cancelled
        bills, and the line is accepted only on an EXACT three-way match —
        _is_exact_match(matched_qty, po unit_cost, unbilled_qty, po unit_cost); any
        quantity variance is rejected with 422 (D-P9b-2). The matched line always
        books at the PO line's own unit_cost, amount = matched_qty * unit_cost.
      - expense (line_type == 'expense'): the account is resolved (404 if unknown)
        and must be an EXPENSE or ASSET account (else 422, D-P9b-3) with amount > 0
        (else 422); it books at the supplied amount.
    The bill is then assigned a server-generated BILL-#### number (retried once on a
    unique-constraint collision, mirroring create_po), status 'draft', and its lines
    are persisted in input order (line_no from 1) in ONE commit. Returned via get_bill.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Bill, BillLine, GLAccount, Partner, PurchaseOrderLine

    # Vendor gate (D-P9b-1) — the partner must exist AND be a vendor (mirror create_po).
    result = await db.execute(select(Partner).where(Partner.id == vendor_id))
    vendor = result.scalars().first()
    if vendor is None or not vendor.is_vendor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Partner {vendor_id} is not a vendor (is_vendor must be True).",
        )

    line_list = list(lines)

    # Serialize concurrent bills that match the SAME receipt line (REVIEW P9b-#1).
    # The exact-match guard below is read-then-write: under READ COMMITTED two
    # simultaneous create_bill transactions for one po_line_id would each read
    # already_billed == 0, both pass _is_exact_match, and both commit — billing the
    # receipt twice so Dr GR/IR overshoots the receipt's Cr and 2150 never clears
    # (the exact defect this phase exists to prevent). Lock each matched PO-line row
    # FOR UPDATE up-front, in sorted id order (deadlock-safe), so the second txn
    # blocks until the first commits and then re-reads the true billed sum. The
    # lock is held until this function's single db.commit().
    matched_po_line_ids = sorted(
        {d.po_line_id for d in line_list if d.line_type == "matched"}
    )
    for locked_id in matched_po_line_ids:
        await db.execute(
            select(PurchaseOrderLine.id)
            .where(PurchaseOrderLine.id == locked_id)
            .with_for_update()
        )

    # Validate every line first, collecting pure values (no partial posting).
    # A single bill must claim each unbilled receipt line AT MOST ONCE: two matched
    # lines against the same po_line_id would each pass the DB-live exact-match check
    # independently and jointly over-bill the receipt, breaking the exact three-way
    # match / GR-IR-clears-to-zero invariant (D-P9b-1/2). Reject on the first dup.
    seen_po_line_ids: set[str] = set()
    prepared: list[_PreparedBillLine] = []
    for data in line_list:
        if data.line_type == "matched":
            if data.po_line_id in seen_po_line_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"PO line {data.po_line_id} is matched more than once on this "
                        f"bill; a bill may claim each receipt line at most once."
                    ),
                )
            seen_po_line_ids.add(data.po_line_id)
            po_result = await db.execute(
                select(PurchaseOrderLine).where(PurchaseOrderLine.id == data.po_line_id)
            )
            po_line = po_result.scalars().first()
            if po_line is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order line {data.po_line_id} not found.",
                )
            # Recompute the still-billable quantity LIVE, then require an EXACT
            # three-way match — the matched line books at the PO unit_cost, so the
            # cost leg is exact by construction and the quantity must match to the
            # cent; any variance drops to manual review (D-P9b-2).
            unbilled = _unbilled_qty(
                po_line.qty_received, await _already_billed_qty(db, po_line.id)
            )
            if not _is_exact_match(
                data.matched_qty, po_line.unit_cost, unbilled, po_line.unit_cost
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Matched quantity {data.matched_qty} does not exactly match "
                        f"the unbilled quantity {unbilled} for PO line {po_line.id}."
                    ),
                )
            prepared.append(
                _PreparedBillLine(
                    line_type="matched",
                    po_line_id=po_line.id,
                    matched_qty=data.matched_qty,
                    account_id=None,
                    unit_cost=po_line.unit_cost,
                    amount=data.matched_qty * po_line.unit_cost,
                )
            )
        else:  # expense — schema guarantees line_type == 'expense' here
            acct_result = await db.execute(
                select(GLAccount).where(GLAccount.id == data.account_id)
            )
            account = acct_result.scalars().first()
            if account is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"GL account {data.account_id} not found.",
                )
            # Expense lines may only be coded to an EXPENSE or ASSET account
            # (a bill records a cost or a capitalised asset — never a revenue,
            # liability, or equity leg from the vendor side, D-P9b-3).
            if account.account_type not in {"EXPENSE", "ASSET"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"GL account {account.code} is {account.account_type}; expense "
                        f"bill lines must code to an EXPENSE or ASSET account."
                    ),
                )
            if data.amount is None or data.amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="An expense bill line must have amount > 0.",
                )
            prepared.append(
                _PreparedBillLine(
                    line_type="expense",
                    po_line_id=None,
                    matched_qty=None,
                    account_id=account.id,
                    unit_cost=None,
                    amount=data.amount,
                )
            )

    # Persist header (retry once on an auto-generated number collision, mirroring
    # create_po) then its lines, in one commit.
    bill_number = await generate_bill_number(db)
    bill = Bill(
        bill_number=bill_number,
        vendor_id=vendor_id,
        vendor_invoice_ref=vendor_invoice_ref,
        # bill_date defaults to today when the caller omits it, keeping existing
        # 09b callers/tests working (D-P9c-1).
        bill_date=bill_date or date.today(),
        status="draft",
        actor_id=actor_id,
    )
    db.add(bill)
    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        bill_number = await generate_bill_number(db)
        bill = Bill(
            bill_number=bill_number,
            vendor_id=vendor_id,
            vendor_invoice_ref=vendor_invoice_ref,
            status="draft",
            actor_id=actor_id,
        )
        db.add(bill)
        await db.flush()

    for line_no, p in enumerate(prepared, start=1):
        db.add(
            BillLine(
                bill_id=bill.id,
                line_no=line_no,
                line_type=p.line_type,
                po_line_id=p.po_line_id,
                matched_qty=p.matched_qty,
                account_id=p.account_id,
                unit_cost=p.unit_cost,
                amount=p.amount,
            )
        )

    await db.commit()
    return await get_bill(db, bill.id)


async def _get_bill_row(
    db: AsyncSession, bill_id: str, *, for_update: bool = False
) -> Bill:
    """
    Load a Bill ORM row by id (internal helper).

    Raises HTTP 404 if no bill with the given id exists (mirrors _get_po_row).
    When ``for_update`` is True the row is locked FOR UPDATE for the rest of the
    transaction — record_payment uses this to serialize concurrent payments against
    the same bill so its open-balance read cannot race (REVIEW P9b-#1).
    """
    from app.modules.syerp.models import Bill

    stmt = select(Bill).where(Bill.id == bill_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    bill = result.scalars().first()
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill {bill_id} not found.",
        )
    return bill


async def _load_bill_lines(db: AsyncSession, bill_id: str) -> list[BillLine]:
    """Return a bill's lines ordered by line_no (no ORM relationship — Pitfall 2)."""
    from app.modules.syerp.models import BillLine

    result = await db.execute(
        select(BillLine).where(BillLine.bill_id == bill_id).order_by(BillLine.line_no)
    )
    return list(result.scalars().all())


async def _bill_paid_amount(db: AsyncSession, bill_id: str) -> Decimal:
    """
    Return the total allocated (paid) against a bill.

    Sums PaymentAllocation.amount for `bill_id`, coalescing to 0 (D-P8-4): a bill
    with no allocations yet yields Decimal("0"), never NULL.
    """
    from app.modules.syerp.models import PaymentAllocation

    result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.bill_id == bill_id
        )
    )
    return Decimal(result.scalar() or 0)


def _bill_to_read(
    bill: Bill, lines: Iterable[BillLine], paid: Decimal
) -> BillRead:
    """
    Assemble a BillRead from a Bill ORM row, its lines, and its allocated total.

    total and open_balance are DERIVED, not stored: total = Σ line.amount (an empty
    line set folds to Decimal("0")), open_balance = total - paid. Each side is
    coalesced independently (D-P8-4), so the model is CONSTRUCTED explicitly rather
    than validated from_attributes for those two fields.
    """
    from app.modules.syerp.schemas import BillLineRead, BillRead

    lines = list(lines)
    total = sum((line.amount for line in lines), Decimal("0"))
    return BillRead(
        id=bill.id,
        bill_number=bill.bill_number,
        vendor_id=bill.vendor_id,
        vendor_invoice_ref=bill.vendor_invoice_ref,
        bill_date=bill.bill_date,
        status=bill.status,
        memo=bill.memo,
        posted_at=bill.posted_at,
        total=total,
        open_balance=total - paid,
        lines=[BillLineRead.model_validate(line) for line in lines],
        created_at=bill.created_at,
    )


async def get_bill(db: AsyncSession, bill_id: str) -> BillRead:
    """
    Load a bill (header + nested lines + derived roll-ups) by id.

    Raises HTTP 404 if no bill with the given id exists (mirrors get_po).
    """
    bill = await _get_bill_row(db, bill_id)
    lines = await _load_bill_lines(db, bill_id)
    paid = await _bill_paid_amount(db, bill_id)
    return _bill_to_read(bill, lines, paid)


async def list_bills(
    db: AsyncSession,
    vendor_id: str | None = None,
    status: str | None = None,
) -> list[BillRead]:
    """
    List bills (newest-first), optionally filtered by vendor and/or status.

    Each bill is returned as a BillRead with its lines nested and its derived
    total/open_balance rolled up. Lines and payment allocations are fetched in one
    query each over all returned bill ids and grouped in memory (no per-bill N+1);
    the allocation sum coalesces to 0 for unpaid bills (D-P8-4). Ordered by
    created_at DESC, then bill_number DESC for a stable tie-break (mirrors list_pos).
    """
    from app.modules.syerp.models import Bill, BillLine, PaymentAllocation

    stmt = select(Bill)
    if vendor_id is not None:
        stmt = stmt.where(Bill.vendor_id == vendor_id)
    if status is not None:
        stmt = stmt.where(Bill.status == status)
    stmt = stmt.order_by(Bill.created_at.desc(), Bill.bill_number.desc())

    result = await db.execute(stmt)
    bills = list(result.scalars().all())
    if not bills:
        return []

    bill_ids = [bill.id for bill in bills]

    lines_result = await db.execute(
        select(BillLine).where(BillLine.bill_id.in_(bill_ids)).order_by(BillLine.line_no)
    )
    lines_by_bill: dict[str, list[BillLine]] = {bill_id: [] for bill_id in bill_ids}
    for line in lines_result.scalars().all():
        lines_by_bill[line.bill_id].append(line)

    paid_result = await db.execute(
        select(
            PaymentAllocation.bill_id,
            func.coalesce(func.sum(PaymentAllocation.amount), 0),
        )
        .where(PaymentAllocation.bill_id.in_(bill_ids))
        .group_by(PaymentAllocation.bill_id)
    )
    paid_by_bill = {bill_id: Decimal(amount) for bill_id, amount in paid_result.all()}

    return [
        _bill_to_read(bill, lines_by_bill[bill.id], paid_by_bill.get(bill.id, Decimal("0")))
        for bill in bills
    ]


async def advance_bill_status(
    db: AsyncSession, bill_id: str, target: str, actor_id: str
) -> BillRead:
    """
    Advance an AP bill through the FSM (Phase 9b, SYERP-12 AC4/5).

    Validates:
      - Bill exists (404 if not).
      - target is an allowed successor of the current status per BILL_TRANSITIONS
        (draft -> posted -> paid, paid terminal) — 422 if not (D-P9b-5).

    Sets bill.status = target and flushes (NOT commits): the caller owns the single
    commit so the transition can ride the same unit of work as its side effects —
    post_bill stamps posted_at + posts the JE around it, and the payment path (Task 7)
    rolls a bill to 'paid' inside the payment's own transaction. Mirrors
    advance_po_status' structure but flushes rather than committing. Returns the
    updated bill as a BillRead (header + nested lines).
    """
    bill = await _get_bill_row(db, bill_id)

    if not _bill_transition_allowed(bill.status, target):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition bill from '{bill.status}' to '{target}'. "
                f"Allowed transitions: {sorted(BILL_TRANSITIONS.get(bill.status, set()))}"
            ),
        )

    bill.status = target
    await db.flush()

    return await get_bill(db, bill_id)


async def post_bill(db: AsyncSession, bill_id: str, actor_id: str) -> BillRead:
    """
    Post a draft AP bill to the GL, flipping it draft -> posted (SYERP-12 AC4, SC3).

    Loads the bill (404 if missing) and rejects a non-draft bill with 422 via the
    BILL_TRANSITIONS FSM guard (a posted/paid bill cannot be re-posted, D-P9b-5).
    Builds ONE balanced journal entry from the bill's lines and posts it through
    post_journal_entry with commit=False, then stamps status='posted' + posted_at
    and takes the SINGLE commit — the JE, the status flip, and the timestamp share
    one atomic transaction (Risk #3): a bill can never flip to Posted without its
    balanced GL entry, and if the JE raises nothing persists.

    The journal entry (all debits, one credit — the vendor payable):
      - each MATCHED line: Dr 2150 GR/IR (clears the receipt's GR/IR accrual),
      - each EXPENSE line: Dr the line's own EXPENSE/ASSET account,
      - ONE Cr 2110 Accounts Payable for the whole bill total (Σ line.amount).

    GR/IR INVARIANT (D-P9b-2/5): a matched line only exists on an EXACT three-way
    match (matched_qty == unbilled_qty AND unit_cost == PO unit_cost — create_bill),
    so its Dr to GR/IR (matched_qty × unit_cost) exactly equals the original Cr to
    GR/IR that receive_line posted for that receipt (qty × unit_cost). Posting the
    bill therefore clears GR/IR (2150) back to its pre-receipt balance, leaving the
    liability on AP (2110) — the accrual is neither stranded nor double-counted.

    Returns the posted bill as a BillRead. Audit (bill.posted) is the router's job;
    this service NEVER writes audit and takes exactly one commit (atomicity).
    """
    bill = await _get_bill_row(db, bill_id)

    # FSM guard: only a draft bill may be posted (422 otherwise, D-P9b-5).
    if not _bill_transition_allowed(bill.status, "posted"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot post bill {bill.bill_number}: it is '{bill.status}', "
                f"only a 'draft' bill can be posted."
            ),
        )

    lines = await _load_bill_lines(db, bill_id)

    grir_account_id = await _gl_account_id_by_code(db, "2150")
    ap_account_id = await _gl_account_id_by_code(db, "2110")

    bill_total = sum((line.amount for line in lines), Decimal("0"))

    # One balanced JE: every bill line debits (GR/IR for matched, its own account for
    # expense), one credit lands the whole total on Accounts Payable.
    je_lines: list[dict[str, object]] = []
    for line in lines:
        debit_account_id = grir_account_id if line.line_type == "matched" else line.account_id
        je_lines.append({"account_id": debit_account_id, "debit": line.amount, "credit": 0})
    je_lines.append({"account_id": ap_account_id, "debit": 0, "credit": bill_total})

    # commit=False: the JE rides THIS transaction's single commit alongside the status
    # flip below — no partial post (Risk #3).
    # Age the JE by the bill's invoice date, not today's, so the 2110 control
    # account's entry_date-aged balance ties out to the AP subledger's bill_date
    # aging (the SC2 tie-out crux, D-P9c-1).
    await post_journal_entry(
        db,
        entry_date=bill.bill_date,
        memo=f"AP bill {bill.bill_number}",
        lines=je_lines,
        actor_id=actor_id,
        source_type="ap_bill",
        source_id=bill.id,
        commit=False,
    )

    bill.status = "posted"
    bill.posted_at = datetime.now(UTC)

    await db.commit()
    return await get_bill(db, bill.id)


async def record_payment(
    db: AsyncSession,
    *,
    payment_date: date,
    cash_account_id: int,
    reference: str | None,
    allocations: Iterable[object],
    actor_id: str,
) -> PaymentRead:
    """
    Record a cash payment against one or more posted AP bills (SYERP-12 AC5, SC4).

    `allocations` is the PaymentCreate payload's list of (bill_id, amount) items —
    each a PaymentAllocationCreate (or any object exposing `.bill_id` / `.amount`).
    The whole disbursement is ONE atomic unit of work: a single ``db.commit`` at the
    very end, so every guard below rejects (422/404) with NOTHING persisted, and a
    successful payment lands its header, allocations, the balanced GL entry, and any
    auto-Paid transition together — never partially (Risk #3).

    Guard order — each rejection mutates nothing:
      1. `cash_account_id` must resolve to a GL account of type ASSET (422 else) —
         the funds leave a cash/bank asset (default 1110; 1111 is ASSET too).
      2. Σ allocation amounts must be > 0, and every individual amount > 0 (422 else).
      3. For each allocation the bill must exist (404) and be 'posted' (422 for a
         'draft' or 'paid' bill). The bill's LIVE open_balance is derived exactly as
         Task 5 does — total billed (Σ line.amount, folded from Decimal("0")) minus
         the coalesced Σ of PRIOR PaymentAllocation.amount (_bill_paid_amount, D-P8-4)
         — each side coalesced independently so a NULL never propagates. Overpayment
         is rejected via the pure _is_overpayment (pay > open_balance; the == boundary
         fully pays, D-P8-7). When the SAME bill appears in several allocations of this
         one payment they must not JOINTLY overpay: the claimed amount is accumulated
         per bill_id and the running total checked against the live open_balance.

    On success, in that single transaction:
      - persist a Payment header (amount = Σ allocations) + one PaymentAllocation row
        per allocation;
      - post ONE balanced JE (commit=False): Dr 2110 Accounts Payable / Cr the cash
        account, for the payment total — the funds leave cash, the liability drops;
      - for each touched bill, re-derive open_balance INCLUDING the just-added
        allocations; when it hits EXACTLY zero, advance the bill 'posted' -> 'paid'
        via advance_bill_status (auto-Paid, D-P9b-5). A partial payment leaves the
        bill 'posted' with a reduced open_balance.

    Audit (payment.recorded) is the ROUTER's job — this service NEVER writes audit and
    takes exactly one commit. Returns the payment as a PaymentRead (constructed
    explicitly; allocations loaded via an ordered SELECT — no ORM relationship).
    """
    from app.modules.syerp.models import Payment, PaymentAllocation
    from app.modules.syerp.schemas import PaymentAllocationRead, PaymentRead

    alloc_list = list(allocations)

    # Guard 1: the cash side must be an ASSET account (422 otherwise).
    cash_account = await _require_gl_account(db, cash_account_id)  # 404 if unknown.
    if cash_account.account_type != "ASSET":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"GL account {cash_account.code} is {cash_account.account_type}; a "
                f"payment must draw on an ASSET (cash/bank) account."
            ),
        )

    # Guard 2: a payment is cash OUT — the total and every leg must be positive.
    total = Decimal("0")
    for alloc in alloc_list:
        amount = Decimal(str(alloc.amount))
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each payment allocation amount must be greater than zero.",
            )
        total += amount
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment total (sum of allocations) must be greater than zero.",
        )

    # Serialize concurrent payments against the same bill (REVIEW P9b-#1). The
    # overpayment guard below is read-then-write: under READ COMMITTED two
    # simultaneous payments would each read the full open_balance, each allocate it,
    # and both commit — paying the bill twice and driving AP negative. Lock each
    # target bill row FOR UPDATE up-front, in sorted id order (deadlock-safe), so a
    # second payment blocks until the first commits and then re-reads the true paid
    # sum. Locks are held until this function's single db.commit().
    for locked_bill_id in sorted({alloc.bill_id for alloc in alloc_list}):
        await _get_bill_row(db, locked_bill_id, for_update=True)

    # Guard 3: resolve/validate each bill and reject overpayment BEFORE any write.
    # open_balance is derived exactly as Task 5: total billed - coalesced prior paid
    # (each side coalesced). Same-bill allocations accumulate so they cannot jointly
    # overpay a single open balance.
    bill_rows: dict[str, Bill] = {}
    bill_total_by_id: dict[str, Decimal] = {}
    open_balance_by_id: dict[str, Decimal] = {}
    claimed_by_id: dict[str, Decimal] = {}
    for alloc in alloc_list:
        bill_id = alloc.bill_id
        amount = Decimal(str(alloc.amount))
        if bill_id not in bill_rows:
            bill = await _get_bill_row(db, bill_id)  # 404 if the bill is unknown.
            if bill.status != "posted":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot pay bill {bill.bill_number}: it is '{bill.status}', "
                        f"only a 'posted' bill can be paid."
                    ),
                )
            lines = await _load_bill_lines(db, bill_id)
            bill_total = sum((line.amount for line in lines), Decimal("0"))
            paid = await _bill_paid_amount(db, bill_id)
            bill_rows[bill_id] = bill
            bill_total_by_id[bill_id] = bill_total
            open_balance_by_id[bill_id] = bill_total - paid
            claimed_by_id[bill_id] = Decimal("0")
        claimed_by_id[bill_id] += amount
        if _is_overpayment(open_balance_by_id[bill_id], claimed_by_id[bill_id]):
            bill = bill_rows[bill_id]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Payment of {claimed_by_id[bill_id]} overpays bill "
                    f"{bill.bill_number} (open balance {open_balance_by_id[bill_id]})."
                ),
            )

    # Persist the payment header first so its id is available for the allocations'
    # FK, the JE source link, and the read-back.
    payment = Payment(
        payment_date=payment_date,
        cash_account_id=cash_account_id,
        amount=total,
        reference=reference,
        actor_id=actor_id,
    )
    db.add(payment)
    await db.flush()  # materialize payment.id.

    for alloc in alloc_list:
        db.add(
            PaymentAllocation(
                payment_id=payment.id,
                bill_id=alloc.bill_id,
                amount=Decimal(str(alloc.amount)),
            )
        )

    # One balanced JE (commit=False): Dr 2110 AP / Cr the cash account for the total —
    # rides THIS transaction's single commit alongside the allocations and any auto-Paid
    # flip, so a payment can never persist without its balanced GL entry (Risk #3).
    ap_account_id = await _gl_account_id_by_code(db, "2110")
    await post_journal_entry(
        db,
        entry_date=payment_date,
        memo=f"AP payment {payment.id}",
        lines=[
            {"account_id": ap_account_id, "debit": total, "credit": 0},
            {"account_id": cash_account_id, "debit": 0, "credit": total},
        ],
        actor_id=actor_id,
        source_type="ap_payment",
        source_id=payment.id,
        commit=False,
    )

    # Re-derive each touched bill's open_balance INCLUDING the just-added allocations
    # (autoflushed above); a bill settled to EXACTLY zero flips 'posted' -> 'paid'
    # (auto-Paid, D-P9b-5). A partial payment leaves it 'posted'.
    for bill_id in bill_rows:
        paid = await _bill_paid_amount(db, bill_id)
        if bill_total_by_id[bill_id] - paid == 0:
            await advance_bill_status(db, bill_id, "paid", actor_id)

    await db.commit()

    # Read the allocations back in a stable order (no ORM relationship — Pitfall 2).
    alloc_result = await db.execute(
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id == payment.id)
        .order_by(PaymentAllocation.id)
    )
    saved_allocations = list(alloc_result.scalars().all())
    return PaymentRead(
        id=payment.id,
        payment_date=payment.payment_date,
        cash_account_id=payment.cash_account_id,
        amount=payment.amount,
        reference=payment.reference,
        allocations=[PaymentAllocationRead.model_validate(a) for a in saved_allocations],
        created_at=payment.created_at,
    )


async def list_payments(db: AsyncSession) -> list[PaymentRead]:
    """
    List all recorded cash payments (SYERP-12 AC5), each with its allocations nested.

    Payments are an append-only ledger (D-P9b-5); rows are returned in creation order
    (created_at, then id as a stable tie-break). For each payment the allocations are
    loaded in the SAME stable order record_payment reads them back (PaymentAllocation.id,
    no ORM relationship — Pitfall 2) and grouped in memory over all payment ids (no
    per-payment N+1). Each PaymentRead is constructed explicitly, money as Decimal (D-11).
    """
    from app.modules.syerp.models import Payment, PaymentAllocation
    from app.modules.syerp.schemas import PaymentAllocationRead, PaymentRead

    result = await db.execute(select(Payment).order_by(Payment.created_at, Payment.id))
    payments = list(result.scalars().all())
    if not payments:
        return []

    payment_ids = [payment.id for payment in payments]

    alloc_result = await db.execute(
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id.in_(payment_ids))
        .order_by(PaymentAllocation.id)
    )
    allocations_by_payment: dict[str, list[PaymentAllocation]] = {
        payment_id: [] for payment_id in payment_ids
    }
    for allocation in alloc_result.scalars().all():
        allocations_by_payment[allocation.payment_id].append(allocation)

    return [
        PaymentRead(
            id=payment.id,
            payment_date=payment.payment_date,
            cash_account_id=payment.cash_account_id,
            amount=payment.amount,
            reference=payment.reference,
            allocations=[
                PaymentAllocationRead.model_validate(a)
                for a in allocations_by_payment[payment.id]
            ],
            created_at=payment.created_at,
        )
        for payment in payments
    ]
