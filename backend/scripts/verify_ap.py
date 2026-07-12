# ABOUTME: Standalone live-DB verification for the SYERP AP engine (Phase 9b, SYERP-12 AC4/5).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives the
# ABOUTME: REAL AP service functions end-to-end, proving three-way match, balanced posting, the
# ABOUTME: GR/IR-clears-to-zero crux, and payment settlement; exits non-zero on FAIL.
"""
Standalone live-DB verification script for the SYERP AP engine (Phase 9b).

WHY THIS EXISTS (the AP backend proof, D-P9b):
  The AP engine (list_unbilled_receipts, create_bill, post_bill, record_payment)
  layers vendor bills + cash payments on top of the Phase-8 receiving path and the
  Phase-9a GL posting engine. Its load-bearing invariant is the GR/IR clear-to-zero:
  receive_line accrues Cr 2150 GR/IR for a receipt, and posting the matching bill
  Dr 2150 GR/IR must net that accrual back to zero (leaving the liability on 2110
  Accounts Payable) — a cross-module property no pure unit test can prove, and the
  backend live-DB pytest harness is broken (D-P7-4), so DB-dependent tests skip
  under plain ``pytest``. Verifiable truth must therefore come from a STANDALONE run
  against LIVE Postgres. This script stands up its own async engine + sessionmaker
  from the ``POSTGRES_*`` environment variables — it deliberately does NOT import the
  broken test conftest fixtures — and then calls the REAL service functions, proving
  the whole phase's backend behavior end-to-end rather than reimplementing it.

HOW TO RUN (the compose ``db`` service is not host-published):
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Run this script INSIDE the running dev api container, which already carries
  #    the app's POSTGRES_* env and can resolve the compose `db` host:
  podman exec compose_api_1 sh -c "cd /app && python scripts/verify_ap.py"

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (a) receiving a PO line surfaces it via list_unbilled_receipts(vendor) with
      unbilled_qty == qty_received and unit_cost == the PO line cost (SC1).
  (b) create_bill accepts an EXACT matched line, and rejects a quantity-variance
      matched line with 422 (D-P9b-2); a matched line always books at the PO unit
      cost, so cost cannot vary via the payload (exact by construction) (SC2).
  (c) a non-PO EXPENSE line bills against an EXPENSE account (success), against a
      REVENUE account is refused 422 (D-P9b-3), and amount <= 0 is rejected (SC2).
  (d) post_bill posts ONE balanced JE (Σ debits == Cr 2110 == bill total,
      source_type='ap_bill'), flips the bill draft -> posted, and refuses a
      non-draft bill with 422 (SC3, D-P9b-5).
  (e) THE CRUX — GR/IR clears to zero: the 2150 derived balance AFTER receive +
      post_bill on a fully-received line EQUALS its pre-receipt value, Decimal-exact.
  (f) record_payment: a partial payment leaves the bill 'posted' with a reduced
      open_balance; a final payment auto-advances it to 'paid'; the payment JE is a
      balanced Dr 2110 / Cr <cash>, source_type='ap_payment' (SC4).
  (g) an overpayment (allocation > open_balance) is refused 422 and persists NOTHING
      (bill status + open_balance unchanged; no orphan Payment/allocation rows).
  (h) the seeded 1111 Bank - Checking account exists and is ASSET (D-P9b-4).
  (i) paying one bill via 1110 and another via 1111 posts each credit to the chosen
      cash account (the JE credit line hits the selected account id).

The script uses uniquely-named throwaway data (a vendor, an item, a location, a
family of POs, bills, and payments) and reuses the seeded GL accounts (1110, 1111,
2110, 2150, plus a seeded EXPENSE 5110 and REVENUE 4110). It CLEANS UP after itself
(deletes its allocations, payments, journal lines/entries, bill lines, bills, PO
lines, POs, inventory txns, item, location, and vendor, respecting FK order) in a
finally block, so it is safe to re-run against the same database. The seeded
accounts and the "Main" location are reused and left in place (real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_ap.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (BillLine.po_line_id FKs syerp_purchase_order_line, PaymentAllocation.bill_id FKs
# syerp_bill — every table must be registered before the FKs resolve; the Task-8
# lesson).
import app.core.models  # noqa: F401
from app.modules.syerp.inventory_seed import seed_default_location
from app.modules.syerp.models import (
    Bill,
    BillLine,
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    Payment,
    PaymentAllocation,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLocation,
)
from app.modules.syerp.schemas import (
    BillLineCreate,
    InventoryItemCreate,
    PartnerCreate,
    PaymentAllocationCreate,
    POCreate,
    POLineCreate,
    StockLocationCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_bill,
    create_item,
    create_location,
    create_partner,
    create_po,
    derive_account_balance,
    get_bill,
    list_journal_entries,
    list_unbilled_receipts,
    post_bill,
    receive_line,
    record_payment,
)

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


# ---------------------------------------------------------------------------
# Own async engine from POSTGRES_* env (NOT the broken conftest fixtures)
# ---------------------------------------------------------------------------


def build_dsn() -> str:
    """
    Assemble the asyncpg DSN directly from POSTGRES_* environment variables.

    Mirrors app.core.config.Settings.database_url but reads os.environ itself so
    the script is fully self-contained and never touches the test conftest.
    """
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def _account_by_code(session, code: str) -> "GLAccount | None":
    """Resolve a seeded GL account (full row) by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount).where(GLAccount.code == code))
    return result.scalars().first()


def _line_for_account(entry, account_id: int):
    """Return the nested JournalLineRead for the given account from an entry."""
    return next((ln for ln in entry.lines if ln.account_id == account_id), None)


def _debit_sum(entry) -> Decimal:
    """Σ of every debit leg of an entry (coalescing each None to 0, D-P8-4)."""
    return sum((ln.debit or Decimal("0") for ln in entry.lines), Decimal("0"))


async def _ap_bill_je(session, bill_id: str):
    """Find the single JE auto-posted by post_bill for `bill_id` (source-linked)."""
    entries = await list_journal_entries(session, source_type="ap_bill")
    matches = [e for e in entries if e.source_id == bill_id]
    return matches[0] if len(matches) == 1 else None


async def _ap_payment_je(session, payment_id: str):
    """Find the single JE auto-posted by record_payment for `payment_id`."""
    entries = await list_journal_entries(session, source_type="ap_payment")
    matches = [e for e in entries if e.source_id == payment_id]
    return matches[0] if len(matches) == 1 else None


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    vendor_id: str | None = None
    item_id: str | None = None
    loc_id: int | None = None

    # Everything this script creates, for FK-safe cleanup in the finally block.
    created_po_ids: list[str] = []
    created_line_ids: list[str] = []
    created_bill_ids: list[str] = []
    created_payment_ids: list[str] = []

    # ------------------------------------------------------------------
    # Local fixture builders (capture the shared vendor/item/location).
    # ------------------------------------------------------------------
    async def build_received_line(qty: Decimal, cost: Decimal) -> tuple[str, str]:
        """Open a PO for the vendor, add one line, approve, receive `qty` fully."""
        async with session_factory() as s:
            po = await create_po(s, POCreate(vendor_id=vendor_id))
        created_po_ids.append(po.id)
        async with session_factory() as s:
            line = await add_line(
                s, po.id, POLineCreate(item_id=item_id, qty_ordered=qty, unit_cost=cost)
            )
        created_line_ids.append(line.id)
        async with session_factory() as s:
            await advance_po_status(s, po.id, "approved", actor_id)
        async with session_factory() as s:
            await receive_line(s, po.id, line.id, loc_id, qty, actor_id)
        return po.id, line.id

    async def make_matched_bill(line_id: str, qty: Decimal):
        """Create a draft bill with one exact-matched line against `line_id`."""
        async with session_factory() as s:
            bill = await create_bill(
                s,
                vendor_id=vendor_id,
                vendor_invoice_ref=f"INV-{unique}-{len(created_bill_ids) + 1}",
                lines=[
                    BillLineCreate(line_type="matched", po_line_id=line_id, matched_qty=qty)
                ],
                actor_id=actor_id,
            )
        created_bill_ids.append(bill.id)
        return bill

    async def post(bill_id: str):
        async with session_factory() as s:
            return await post_bill(s, bill_id, actor_id)

    try:
        # -------------------------------------------------------------------
        # Setup: shared vendor + item + location; resolve the seeded accounts.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor = await create_partner(
                session, PartnerCreate(name=f"VERIFY AP Vendor {unique}", is_vendor=True)
            )
            vendor_id = vendor.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY AP Widget {unique}", unit_of_measure="ea"),
            )
            item_id = item.id
        async with session_factory() as session:
            location = await create_location(
                session, StockLocationCreate(name=f"VERIFY-AP-{unique}")
            )
            loc_id = location.id

        async with session_factory() as session:
            cash_1110 = await _account_by_code(session, "1110")
            bank_1111 = await _account_by_code(session, "1111")
            ap_2110 = await _account_by_code(session, "2110")
            grir_2150 = await _account_by_code(session, "2150")
            expense_5110 = await _account_by_code(session, "5110")
            revenue_4110 = await _account_by_code(session, "4110")
        check(
            "seeded GL accounts resolve: 1110/1111 (ASSET), 2110/2150 (LIABILITY), "
            "5110 (EXPENSE), 4110 (REVENUE)",
            all(
                a is not None
                for a in (cash_1110, bank_1111, ap_2110, grir_2150, expense_5110, revenue_4110)
            )
            and cash_1110.account_type == "ASSET"
            and ap_2110.account_type == "LIABILITY"
            and grir_2150.account_type == "LIABILITY"
            and expense_5110.account_type == "EXPENSE"
            and revenue_4110.account_type == "REVENUE",
        )
        cash_id = cash_1110.id
        bank_id = bank_1111.id
        ap_id = ap_2110.id
        grir_id = grir_2150.id
        expense_id = expense_5110.id
        revenue_id = revenue_4110.id

        # -------------------------------------------------------------------
        # (h) The seeded 1111 Bank - Checking account exists and is ASSET.
        # -------------------------------------------------------------------
        check(
            "seeded '1111 Bank - Checking' account exists and is ASSET (D-P9b-4)",
            bank_1111 is not None
            and bank_1111.name.startswith("Bank")
            and bank_1111.account_type == "ASSET",
            f"acct={bank_1111!r}",
        )

        # -------------------------------------------------------------------
        # (a) list_unbilled_receipts surfaces a received line at its unbilled
        #     qty and PO unit cost (SC1).
        # -------------------------------------------------------------------
        po_a, line_a = await build_received_line(Decimal("6"), Decimal("5"))
        async with session_factory() as session:
            unbilled = await list_unbilled_receipts(session, vendor_id)
        row_a = next((r for r in unbilled if r.po_line_id == line_a), None)
        check(
            "list_unbilled_receipts surfaces the received line with "
            "unbilled_qty == qty_received (6) and unit_cost == PO cost (5) (SC1)",
            row_a is not None
            and row_a.unbilled_qty == Decimal("6")
            and row_a.unit_cost == Decimal("5")
            and row_a.item_id == item_id,
            f"row={row_a!r}",
        )

        # -------------------------------------------------------------------
        # (b) EXACT matched line succeeds (cost booked from PO — exact by
        #     construction); a quantity-variance matched line raises 422 (SC2).
        # -------------------------------------------------------------------
        po_b, line_b = await build_received_line(Decimal("4"), Decimal("5"))
        bill_b = await make_matched_bill(line_b, Decimal("4"))
        b_line = bill_b.lines[0] if bill_b.lines else None
        check(
            "create_bill accepts an EXACT matched line — draft bill, total == 20, "
            "matched line books at the PO unit_cost 5 (cost exact by construction) (SC2)",
            bill_b.status == "draft"
            and bill_b.total == Decimal("20")
            and b_line is not None
            and b_line.line_type == "matched"
            and b_line.matched_qty == Decimal("4")
            and b_line.unit_cost == Decimal("5")
            and b_line.amount == Decimal("20"),
            f"status={bill_b.status!r} total={bill_b.total!r} line={b_line!r}",
        )

        po_bv, line_bv = await build_received_line(Decimal("4"), Decimal("5"))
        wrong_qty_status = None
        async with session_factory() as session:
            try:
                await create_bill(
                    session,
                    vendor_id=vendor_id,
                    vendor_invoice_ref=f"INV-{unique}-badqty",
                    lines=[
                        BillLineCreate(
                            line_type="matched", po_line_id=line_bv, matched_qty=Decimal("3")
                        )
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                wrong_qty_status = exc.status_code
        check(
            "a quantity-variance matched line (bill 3 of 4 unbilled) raises 422 (D-P9b-2)",
            wrong_qty_status == 422,
            f"status={wrong_qty_status!r}",
        )
        async with session_factory() as session:
            still_unbilled = await list_unbilled_receipts(session, vendor_id)
        check(
            "the rejected variance bill persisted NOTHING — the line is still fully "
            "unbilled (qty 4)",
            any(
                r.po_line_id == line_bv and r.unbilled_qty == Decimal("4")
                for r in still_unbilled
            ),
            f"unbilled={[(r.po_line_id, r.unbilled_qty) for r in still_unbilled]}",
        )

        # -------------------------------------------------------------------
        # (c) EXPENSE line bills against an EXPENSE account (success); a REVENUE
        #     account raises 422; amount <= 0 is rejected (SC2, D-P9b-3).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            bill_c = await create_bill(
                session,
                vendor_id=vendor_id,
                vendor_invoice_ref=f"INV-{unique}-exp",
                lines=[
                    BillLineCreate(
                        line_type="expense", account_id=expense_id, amount=Decimal("50")
                    )
                ],
                actor_id=actor_id,
            )
        created_bill_ids.append(bill_c.id)
        c_line = bill_c.lines[0] if bill_c.lines else None
        check(
            "an EXPENSE-account expense line bills successfully (total == 50) (SC2)",
            bill_c.status == "draft"
            and bill_c.total == Decimal("50")
            and c_line is not None
            and c_line.line_type == "expense"
            and c_line.account_id == expense_id
            and c_line.amount == Decimal("50"),
            f"status={bill_c.status!r} total={bill_c.total!r} line={c_line!r}",
        )

        revenue_status = None
        async with session_factory() as session:
            try:
                await create_bill(
                    session,
                    vendor_id=vendor_id,
                    vendor_invoice_ref=f"INV-{unique}-rev",
                    lines=[
                        BillLineCreate(
                            line_type="expense", account_id=revenue_id, amount=Decimal("50")
                        )
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                revenue_status = exc.status_code
        check(
            "an expense line coded to a REVENUE account raises 422 (D-P9b-3)",
            revenue_status == 422,
            f"status={revenue_status!r}",
        )

        # amount <= 0 is rejected at the API contract (the BillLineCreate validator
        # raises before the payload ever reaches create_bill — that IS the 422 the
        # client receives; the service carries a redundant amount>0 guard behind it).
        amount_rejected = False
        try:
            BillLineCreate(line_type="expense", account_id=expense_id, amount=Decimal("0"))
        except ValidationError:
            amount_rejected = True
        check(
            "an expense line with amount <= 0 is rejected (schema 422 — pydantic "
            "ValidationError, the API contract the client sees)",
            amount_rejected,
            "BillLineCreate accepted amount == 0",
        )

        # -------------------------------------------------------------------
        # (d) post_bill posts ONE balanced JE (Σ debits == Cr 2110 == total),
        #     source_type='ap_bill', flips draft -> posted; re-post raises 422.
        # -------------------------------------------------------------------
        posted_b = await post(bill_b.id)
        check(
            "post_bill flips the bill draft -> posted and stamps posted_at (SC3)",
            posted_b.status == "posted" and posted_b.posted_at is not None,
            f"status={posted_b.status!r} posted_at={posted_b.posted_at!r}",
        )
        async with session_factory() as session:
            je_b = await _ap_bill_je(session, bill_b.id)
        ap_credit = _line_for_account(je_b, ap_id) if je_b else None
        grir_debit = _line_for_account(je_b, grir_id) if je_b else None
        check(
            "post_bill posted exactly ONE balanced JE (source_type='ap_bill', "
            "source_id=bill.id) — Σ debits == Cr 2110 == bill total 20 (SC3)",
            je_b is not None
            and je_b.source_type == "ap_bill"
            and je_b.source_id == bill_b.id
            and _debit_sum(je_b) == Decimal("20")
            and ap_credit is not None
            and ap_credit.credit == Decimal("20")
            and grir_debit is not None
            and grir_debit.debit == Decimal("20"),
            f"je={je_b is not None} debits={_debit_sum(je_b) if je_b else None!r} "
            f"ap_credit={(ap_credit.credit if ap_credit else None)!r}",
        )
        repost_status = None
        async with session_factory() as session:
            try:
                await post_bill(session, bill_b.id, actor_id)
            except HTTPException as exc:
                repost_status = exc.status_code
        check(
            "re-posting a non-draft (already posted) bill raises 422 (D-P9b-5)",
            repost_status == 422,
            f"status={repost_status!r}",
        )

        # -------------------------------------------------------------------
        # (e) THE CRUX — GR/IR CLEARS TO ZERO. Capture the 2150 derived balance
        #     BEFORE the receipt; after receive + post_bill on the same fully-
        #     received line, it must EQUAL its pre-receipt value (Decimal-exact).
        #     This block is contiguous so nothing else touches 2150 in the window.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            grir_pre = await derive_account_balance(session, grir_id)

        po_e, line_e = await build_received_line(Decimal("7"), Decimal("5"))  # Cr 2150 += 35
        async with session_factory() as session:
            grir_after_receipt = await derive_account_balance(session, grir_id)
        check(
            "receiving a 7 @ 5 line accrued Cr 2150 GR/IR by 35 (balance moved −35)",
            (grir_after_receipt - grir_pre) == Decimal("-35"),
            f"pre={grir_pre!r} after_receipt={grir_after_receipt!r}",
        )

        bill_e = await make_matched_bill(line_e, Decimal("7"))
        await post(bill_e.id)  # Dr 2150 GR/IR 35 — must clear the accrual
        async with session_factory() as session:
            grir_post = await derive_account_balance(session, grir_id)
        check(
            "CRUX: after receive + post_bill the 2150 GR/IR derived balance EQUALS "
            "its pre-receipt value (Decimal-exact) — the accrual cleared to zero",
            grir_post == grir_pre,
            f"pre={grir_pre!r} post={grir_post!r} delta={grir_post - grir_pre!r}",
        )
        print(f"      (crux detail) 2150 pre-receipt={grir_pre} post-bill={grir_post}")

        # -------------------------------------------------------------------
        # (f) record_payment: partial leaves 'posted' with reduced open_balance;
        #     final payment auto-advances to 'paid'; JE is Dr 2110 / Cr <cash>.
        # -------------------------------------------------------------------
        po_pay, line_pay = await build_received_line(Decimal("10"), Decimal("5"))  # total 50
        bill_pay = await make_matched_bill(line_pay, Decimal("10"))
        await post(bill_pay.id)

        async with session_factory() as session:
            pay_partial = await record_payment(
                session,
                payment_date=date.today(),
                cash_account_id=cash_id,
                reference=f"CHK-{unique}-partial",
                allocations=[PaymentAllocationCreate(bill_id=bill_pay.id, amount=Decimal("20"))],
                actor_id=actor_id,
            )
        created_payment_ids.append(pay_partial.id)
        async with session_factory() as session:
            bill_pay_mid = await get_bill(session, bill_pay.id)
        check(
            "a partial payment (20 of 50) leaves the bill 'posted' with open_balance "
            "reduced to 30 (SC4)",
            bill_pay_mid.status == "posted" and bill_pay_mid.open_balance == Decimal("30"),
            f"status={bill_pay_mid.status!r} open_balance={bill_pay_mid.open_balance!r}",
        )
        async with session_factory() as session:
            je_partial = await _ap_payment_je(session, pay_partial.id)
        pay_ap = _line_for_account(je_partial, ap_id) if je_partial else None
        pay_cash = _line_for_account(je_partial, cash_id) if je_partial else None
        check(
            "the payment JE is a balanced Dr 2110 / Cr 1110 cash for 20 "
            "(source_type='ap_payment')",
            je_partial is not None
            and je_partial.source_type == "ap_payment"
            and pay_ap is not None
            and pay_ap.debit == Decimal("20")
            and pay_cash is not None
            and pay_cash.credit == Decimal("20"),
            f"ap_debit={(pay_ap.debit if pay_ap else None)!r} "
            f"cash_credit={(pay_cash.credit if pay_cash else None)!r}",
        )

        async with session_factory() as session:
            pay_final = await record_payment(
                session,
                payment_date=date.today(),
                cash_account_id=cash_id,
                reference=f"CHK-{unique}-final",
                allocations=[PaymentAllocationCreate(bill_id=bill_pay.id, amount=Decimal("30"))],
                actor_id=actor_id,
            )
        created_payment_ids.append(pay_final.id)
        async with session_factory() as session:
            bill_pay_done = await get_bill(session, bill_pay.id)
        check(
            "the final payment (remaining 30) auto-advances the bill 'posted' -> "
            "'paid' with open_balance 0 (SC4, D-P9b-5)",
            bill_pay_done.status == "paid" and bill_pay_done.open_balance == Decimal("0"),
            f"status={bill_pay_done.status!r} open_balance={bill_pay_done.open_balance!r}",
        )

        # -------------------------------------------------------------------
        # (g) an overpayment is refused 422 and persists NOTHING.
        # -------------------------------------------------------------------
        po_over, line_over = await build_received_line(Decimal("5"), Decimal("5"))  # total 25
        bill_over = await make_matched_bill(line_over, Decimal("5"))
        await post(bill_over.id)

        async with session_factory() as session:
            payments_before = (
                await session.execute(select(func.count()).select_from(Payment))
            ).scalar()
            allocs_before = (
                await session.execute(
                    select(func.count())
                    .select_from(PaymentAllocation)
                    .where(PaymentAllocation.bill_id == bill_over.id)
                )
            ).scalar()

        overpay_status = None
        async with session_factory() as session:
            try:
                await record_payment(
                    session,
                    payment_date=date.today(),
                    cash_account_id=cash_id,
                    reference=f"CHK-{unique}-over",
                    allocations=[
                        PaymentAllocationCreate(bill_id=bill_over.id, amount=Decimal("30"))
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                overpay_status = exc.status_code
        check(
            "an overpayment (pay 30 against a 25 open balance) raises 422 (D-P8-7)",
            overpay_status == 422,
            f"status={overpay_status!r}",
        )
        async with session_factory() as session:
            bill_over_after = await get_bill(session, bill_over.id)
            payments_after = (
                await session.execute(select(func.count()).select_from(Payment))
            ).scalar()
            allocs_after = (
                await session.execute(
                    select(func.count())
                    .select_from(PaymentAllocation)
                    .where(PaymentAllocation.bill_id == bill_over.id)
                )
            ).scalar()
        check(
            "the refused overpayment persisted NOTHING — bill still 'posted', "
            "open_balance still 25, no orphan Payment/allocation rows",
            bill_over_after.status == "posted"
            and bill_over_after.open_balance == Decimal("25")
            and payments_after == payments_before
            and allocs_after == allocs_before == 0,
            f"status={bill_over_after.status!r} open={bill_over_after.open_balance!r} "
            f"payments {payments_before}->{payments_after} allocs {allocs_before}->{allocs_after}",
        )

        # -------------------------------------------------------------------
        # (i) paying one bill via 1110 and another via 1111 posts each credit to
        #     the chosen cash account.
        # -------------------------------------------------------------------
        po_i1, line_i1 = await build_received_line(Decimal("3"), Decimal("5"))  # total 15
        bill_i1 = await make_matched_bill(line_i1, Decimal("3"))
        await post(bill_i1.id)
        po_i2, line_i2 = await build_received_line(Decimal("3"), Decimal("5"))  # total 15
        bill_i2 = await make_matched_bill(line_i2, Decimal("3"))
        await post(bill_i2.id)

        async with session_factory() as session:
            pay_i1 = await record_payment(
                session,
                payment_date=date.today(),
                cash_account_id=cash_id,
                reference=f"CHK-{unique}-i1",
                allocations=[PaymentAllocationCreate(bill_id=bill_i1.id, amount=Decimal("15"))],
                actor_id=actor_id,
            )
        created_payment_ids.append(pay_i1.id)
        async with session_factory() as session:
            pay_i2 = await record_payment(
                session,
                payment_date=date.today(),
                cash_account_id=bank_id,
                reference=f"CHK-{unique}-i2",
                allocations=[PaymentAllocationCreate(bill_id=bill_i2.id, amount=Decimal("15"))],
                actor_id=actor_id,
            )
        created_payment_ids.append(pay_i2.id)
        async with session_factory() as session:
            je_i1 = await _ap_payment_je(session, pay_i1.id)
            je_i2 = await _ap_payment_je(session, pay_i2.id)
        i1_cash = _line_for_account(je_i1, cash_id) if je_i1 else None
        i2_bank = _line_for_account(je_i2, bank_id) if je_i2 else None
        check(
            "paying via 1110 credits the 1110 Cash account (JE credit line hits the "
            "selected account id)",
            i1_cash is not None and i1_cash.credit == Decimal("15"),
            f"i1_cash={(i1_cash.credit if i1_cash else None)!r}",
        )
        check(
            "paying via 1111 credits the 1111 Bank account (JE credit line hits the "
            "selected account id)",
            i2_bank is not None and i2_bank.credit == Decimal("15"),
            f"i2_bank={(i2_bank.credit if i2_bank else None)!r}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows in FK-safe order: payment allocations →
        # payments → journal lines → journal entries (ap_bill / ap_payment /
        # po_receipt, source-linked) → bill lines → bills → PO lines → POs →
        # inventory txns → item → location → vendor. Seeded accounts and "Main"
        # location are left in place (real deploy state).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            # Idempotent: seed the default location so re-runs on a fresh DB work.
            await seed_default_location(session)

            if created_payment_ids:
                await session.execute(
                    delete(PaymentAllocation).where(
                        PaymentAllocation.payment_id.in_(created_payment_ids)
                    )
                )
                await session.execute(
                    delete(Payment).where(Payment.id.in_(created_payment_ids))
                )

            # Collect every source-linked auto-posted JE (bill posts, payment posts,
            # and receipt accruals) for deletion.
            entry_ids: list[str] = []
            for source_type, source_ids in (
                ("ap_bill", created_bill_ids),
                ("ap_payment", created_payment_ids),
                ("po_receipt", created_line_ids),
            ):
                if source_ids:
                    ids = (
                        await session.execute(
                            select(JournalEntry.id).where(
                                JournalEntry.source_type == source_type,
                                JournalEntry.source_id.in_(source_ids),
                            )
                        )
                    ).scalars().all()
                    entry_ids.extend(ids)
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )

            if created_bill_ids:
                await session.execute(
                    delete(BillLine).where(BillLine.bill_id.in_(created_bill_ids))
                )
                await session.execute(delete(Bill).where(Bill.id.in_(created_bill_ids)))

            if created_po_ids:
                await session.execute(
                    delete(PurchaseOrderLine).where(
                        PurchaseOrderLine.po_id.in_(created_po_ids)
                    )
                )
                await session.execute(
                    delete(PurchaseOrder).where(PurchaseOrder.id.in_(created_po_ids))
                )
            if item_id is not None:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id == item_id)
                )
                await session.execute(
                    delete(InventoryItem).where(InventoryItem.id == item_id)
                )
            if loc_id is not None:
                await session.execute(
                    delete(StockLocation).where(StockLocation.id == loc_id)
                )
            if vendor_id is not None:
                await session.execute(delete(Partner).where(Partner.id == vendor_id))

            await session.commit()
        await engine.dispose()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
