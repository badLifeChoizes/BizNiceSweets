# ABOUTME: SERVICE-path port of verify_ap.py scenarios (d)(e)(f) (SC1c) — the AP posting-ties crux.
# ABOUTME: Drives the real AP service (post_bill/record_payment) + the GR/IR-clears-to-zero crux on the test DB.
"""
SYERP AP posting-ties SERVICE crux — ported from ``backend/scripts/verify_ap.py``
scenarios (d) balanced bill post, (e) THE GR/IR-clears-to-zero crux, (f) partial ->
final -> paid payment settlement, plus the AP control-account ↔ bill-subledger
equality and the overpayment-refused-persists-nothing negative path (SC1c).

WHY THIS EXISTS:
  ``bills.py`` carries PURE helpers (``_is_exact_match`` / ``_is_overpayment`` /
  ``_next_bill_number``) that unit-test in isolation. The AP engine a shop actually
  relies on, however, is the SERVICE path — ``post_bill`` posting ONE balanced
  Dr 2150/Dr expense / Cr 2110 journal entry, ``record_payment`` posting Dr 2110 /
  Cr cash and auto-advancing a fully-paid bill, and the load-bearing cross-module
  invariant that posting a matched bill clears the receipt's GR/IR accrual back to
  its pre-receipt value. That end-to-end path only ever ran against the live
  ``biznice`` DB via the standalone verify script. This test closes that gap through
  the same service functions on the truncate-fresh test database.

Concurrency mutation-proofs (verify_ap scenarios j/k) stay in the script per
D-P2a-2; only the sequential ties are ported here (D-P2b-2).

All amounts are Decimal — never float (D-11).
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.syerp.models import GLAccount, Payment, PaymentAllocation
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
    list_bills,
    list_journal_entries,
    post_bill,
    receive_line,
    record_payment,
)

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


def _line_for_account(entry, account_id: int):
    """Return the nested JournalLineRead for the given account from an entry."""
    return next((ln for ln in entry.lines if ln.account_id == account_id), None)


def _debit_sum(entry) -> Decimal:
    """Σ of every debit leg of an entry (coalescing each None to 0, D-P8-4)."""
    return sum((ln.debit or Decimal("0") for ln in entry.lines), Decimal("0"))


async def _account_id_by_code(session, code: str) -> int | None:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalars().first()


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


async def test_ap_posting_ties_crux(seeded_ledger_db) -> None:
    """
    Port of verify_ap.py (d)(e)(f) through the SERVICE path, plus the control ↔
    subledger equality (keeper) and the overpayment negative path.

    Sequential, state-building, exactly as the standalone verify script runs:
      (d) post_bill on a matched 4@5 bill posts ONE balanced JE (source_type=
          'ap_bill'): Σ debits == Cr 2110 == 20, Dr 2150 == 20; the bill flips
          draft -> posted with posted_at stamped; re-posting a posted bill 422s.
      (e) THE CRUX — GR/IR clears to zero: capture derive_account_balance(2150)
          BEFORE the receipt; receive 7@5 (Cr 2150 −35), make a matched bill +
          post_bill (Dr 2150 35) → the 2150 derived balance EQUALS its pre-receipt
          value, Decimal-exact (== grir_pre). This is the headline red-on-revert.
      (f) record_payment: a partial 20 of 50 leaves the bill 'posted' with
          open_balance 30 and posts a balanced Dr 2110 / Cr 1110 == 20 JE; the
          final 30 auto-advances 'posted' -> 'paid' with open_balance 0.
      AP control ↔ subledger EQUALITY (keeper): derive_account_balance(2110)
      (Σdebit − Σcredit) equals the NEGATED sum of open_balance across all
      posted-unpaid bills — the control account ties DIRECTLY to the bill
      subledger, not merely "the trial balance nets to zero".
      Overpayment negative path: paying 30 against a 25 open balance raises 422
      and persists NOTHING (no bill flip, no orphan Payment/allocation rows).

    SC2 red-on-revert: dropping the Dr 2150 GR/IR debit leg in
    ``service/bills.py::post_bill`` (so a matched bill no longer clears the
    receipt accrual) must turn the (e) GR/IR-clears assertion RED.
    """
    session = seeded_ledger_db

    # -- Setup: shared vendor + item + location; resolve the seeded accounts. --
    cash_id = await _account_id_by_code(session, "1110")  # Cash (payment credit)
    ap_id = await _account_id_by_code(session, "2110")    # Accounts Payable (control)
    grir_id = await _account_id_by_code(session, "2150")  # GR/IR (the crux account)
    assert cash_id is not None and ap_id is not None and grir_id is not None

    vendor = await create_partner(
        session, PartnerCreate(name="SC1c AP Vendor", is_vendor=True)
    )
    item = await create_item(
        session, InventoryItemCreate(name="SC1c AP Widget", unit_of_measure="ea")
    )
    location = await create_location(session, StockLocationCreate(name="SC1c-AP"))

    _bill_seq = 0

    async def build_received_line(qty: Decimal, cost: Decimal) -> str:
        """Open a PO for the shared vendor, add one line, approve, receive fully."""
        po = await create_po(session, POCreate(vendor_id=vendor.id))
        line = await add_line(
            session, po.id, POLineCreate(item_id=item.id, qty_ordered=qty, unit_cost=cost)
        )
        await advance_po_status(session, po.id, "approved", ACTOR_ID)
        await receive_line(session, po.id, line.id, location.id, qty, ACTOR_ID)
        return line.id

    async def make_matched_bill(line_id: str, qty: Decimal):
        """Create a draft bill with one exact-matched line against `line_id`."""
        nonlocal _bill_seq
        _bill_seq += 1
        return await create_bill(
            session,
            vendor_id=vendor.id,
            vendor_invoice_ref=f"INV-SC1c-{_bill_seq}",
            lines=[BillLineCreate(line_type="matched", po_line_id=line_id, matched_qty=qty)],
            actor_id=ACTOR_ID,
        )

    # -- (d) post_bill: ONE balanced JE, Σ debits == Cr 2110 == Dr 2150 == 20 --
    line_d = await build_received_line(Decimal("4"), Decimal("5"))
    bill_d = await make_matched_bill(line_d, Decimal("4"))
    assert bill_d.status == "draft" and bill_d.total == Decimal("20")

    posted_d = await post_bill(session, bill_d.id, ACTOR_ID)
    assert posted_d.status == "posted" and posted_d.posted_at is not None

    je_d = await _ap_bill_je(session, bill_d.id)
    assert je_d is not None
    assert je_d.source_type == "ap_bill" and je_d.source_id == bill_d.id
    ap_credit = _line_for_account(je_d, ap_id)
    grir_debit = _line_for_account(je_d, grir_id)
    # Balanced, single JE: every debit sums to the total, one Cr 2110 for the total,
    # and the matched line's Dr 2150 GR/IR carries the whole 20 (per-leg invariant).
    assert _debit_sum(je_d) == Decimal("20")
    assert ap_credit is not None and ap_credit.credit == Decimal("20")
    assert grir_debit is not None and grir_debit.debit == Decimal("20")

    # Re-posting a non-draft (already posted) bill raises 422 (D-P9b-5).
    with pytest.raises(HTTPException) as repost_exc:
        await post_bill(session, bill_d.id, ACTOR_ID)
    assert repost_exc.value.status_code == 422

    # -- (e) THE CRUX — GR/IR clears to zero (Decimal-exact) ------------------
    # Capture 2150 BEFORE the receipt; this block is contiguous so nothing else
    # touches 2150 in the window.
    grir_pre = await derive_account_balance(session, grir_id)

    line_e = await build_received_line(Decimal("7"), Decimal("5"))  # Cr 2150 −35
    grir_after_receipt = await derive_account_balance(session, grir_id)
    assert (grir_after_receipt - grir_pre) == Decimal("-35")

    bill_e = await make_matched_bill(line_e, Decimal("7"))
    await post_bill(session, bill_e.id, ACTOR_ID)  # Dr 2150 35 — clears the accrual

    grir_post = await derive_account_balance(session, grir_id)
    # HEADLINE: after receive + post_bill the 2150 GR/IR derived balance EQUALS its
    # pre-receipt value, Decimal-exact — the accrual cleared to zero (the SC2
    # red-on-revert target: drop the Dr 2150 leg in post_bill and this goes RED).
    assert grir_post == grir_pre

    # -- (f) record_payment: partial -> 'posted' open 30; final -> 'paid' open 0 --
    line_pay = await build_received_line(Decimal("10"), Decimal("5"))  # total 50
    bill_pay = await make_matched_bill(line_pay, Decimal("10"))
    await post_bill(session, bill_pay.id, ACTOR_ID)

    pay_partial = await record_payment(
        session,
        payment_date=date.today(),
        cash_account_id=cash_id,
        reference="CHK-SC1c-partial",
        allocations=[PaymentAllocationCreate(bill_id=bill_pay.id, amount=Decimal("20"))],
        actor_id=ACTOR_ID,
    )
    bill_pay_mid = await get_bill(session, bill_pay.id)
    # A partial 20 of 50 leaves the bill 'posted' with open_balance reduced to 30.
    assert bill_pay_mid.status == "posted" and bill_pay_mid.open_balance == Decimal("30")

    je_partial = await _ap_payment_je(session, pay_partial.id)
    assert je_partial is not None and je_partial.source_type == "ap_payment"
    pay_ap = _line_for_account(je_partial, ap_id)
    pay_cash = _line_for_account(je_partial, cash_id)
    # Balanced Dr 2110 / Cr 1110 cash for 20 (both legs — the per-account keeper).
    assert pay_ap is not None and pay_ap.debit == Decimal("20")
    assert pay_cash is not None and pay_cash.credit == Decimal("20")

    await record_payment(
        session,
        payment_date=date.today(),
        cash_account_id=cash_id,
        reference="CHK-SC1c-final",
        allocations=[PaymentAllocationCreate(bill_id=bill_pay.id, amount=Decimal("30"))],
        actor_id=ACTOR_ID,
    )
    bill_pay_done = await get_bill(session, bill_pay.id)
    # The final 30 auto-advances 'posted' -> 'paid' with open_balance 0 (D-P9b-5).
    assert bill_pay_done.status == "paid" and bill_pay_done.open_balance == Decimal("0")

    # -- AP control ↔ bill subledger EQUALITY (keeper) -----------------------
    # derive_account_balance(2110) is Σdebit − Σcredit: post_bill credits 2110 by
    # each bill total, record_payment debits it by each payment. A posted-unpaid
    # bill therefore leaves −open_balance on the control; a fully-paid bill nets to
    # 0. So the control balance is the NEGATED sum of open_balance across the bill
    # subledger's posted-unpaid rows — asserted DIRECTLY against the subledger, not
    # via "the trial balance nets to zero".
    posted_bills = await list_bills(session, status="posted")
    subledger_open = sum((b.open_balance for b in posted_bills), Decimal("0"))
    ap_control = await derive_account_balance(session, ap_id)
    assert ap_control == -subledger_open
    # Cross-check the live figure: bill_d (20) + bill_e (35) still open, bill_pay paid.
    assert subledger_open == Decimal("55")

    # -- Overpayment negative path: 422 and persists NOTHING -----------------
    line_over = await build_received_line(Decimal("5"), Decimal("5"))  # total 25
    bill_over = await make_matched_bill(line_over, Decimal("5"))
    await post_bill(session, bill_over.id, ACTOR_ID)

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

    with pytest.raises(HTTPException) as overpay_exc:
        await record_payment(
            session,
            payment_date=date.today(),
            cash_account_id=cash_id,
            reference="CHK-SC1c-over",
            allocations=[PaymentAllocationCreate(bill_id=bill_over.id, amount=Decimal("30"))],
            actor_id=ACTOR_ID,
        )
    assert overpay_exc.value.status_code == 422

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
    # The refused overpayment persisted NOTHING: the bill is still 'posted' with its
    # 25 open balance, and no orphan Payment/allocation rows were written.
    assert bill_over_after.status == "posted"
    assert bill_over_after.open_balance == Decimal("25")
    assert payments_after == payments_before
    assert allocs_after == allocs_before == 0
