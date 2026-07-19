"""SYERP service — AP aging and financial statements (trial balance, P&L, balance sheet)."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        Bill,
        BillLine,
        GLAccount,
        InventoryItem,
        JournalEntry,
        JournalLine,
        Partner,
        PurchaseOrder,
        PurchaseOrderLine,
        StockLocation,
    )
    from app.modules.syerp.schemas import (
        AccountRegisterRead,
        ApAgingReport,
        ArAgingReport,
        BalanceSheetReport,
        BillLineCreate,
        BillRead,
        InventoryItemCreate,
        InventoryItemUpdate,
        ItemOnHandRead,
        JournalEntryRead,
        PartnerCreate,
        PartnerUpdate,
        POCreate,
        POLineCreate,
        POLineRead,
        POLineUpdate,
        PORead,
        ProfitLossReport,
        StockLocationCreate,
        StockLocationUpdate,
        TransactionRead,
        TrialBalanceReport,
        UnbilledReceiptRead,
    )

from app.modules.syerp.service.accounts import _gl_account_id_by_code


# ===== Phase 9c reports =====
#
# Read-only derived reporting layer (SYERP-13): the AP aging schedule plus the
# three financial statements (trial balance, P&L, balance sheet). Every figure is
# derived on demand from the append-only journal / AP subledger — nothing is stored.
#
# Two rules recur across all four (get them right — they are the flagged risks):
#   1. DATE-FILTERED balances. Unlike derive_account_balance (whole-ledger, no date),
#      a report balance is bounded by JournalEntry.entry_date over the report window.
#      Each side is COALESCEd to 0 INDEPENDENTLY (func.coalesce(func.sum(debit), 0)
#      and the same for credit) — Σdr − NULL is NULL in SQL, the recurring 09a
#      NULL-propagation bug (D-P8-4). The join is JournalLine ⋈ JournalEntry on
#      JournalLine.entry_id == JournalEntry.id (the same pattern as
#      get_account_register).
#   2. SIGN normalisation so every magnitude presents positive: debit-normal types
#      (ASSET, EXPENSE) as Σdr − Σcr; credit-normal types (LIABILITY, EQUITY,
#      REVENUE) as Σcr − Σdr.
# Money is exact Decimal throughout (never float — D-11).


async def ap_aging_report(db: AsyncSession, as_of: date | None = None) -> "ApAgingReport":
    """
    Accounts-payable aging schedule as of a date, tied out to the 2110 control (AC6).

    For every bill that is POSTED to 2110 (status in ('posted','paid') and
    bill_date <= as_of) the still-open balance is bill-line total −
    Σ PaymentAllocation.amount for payments dated on/before as_of, each side coalesced
    independently (D-P8-4). DRAFT bills are excluded — a draft is not posted to 2110,
    so including it would break the tie-out (the divergence guard, D-P9c-1). Bills
    with a non-positive open balance are dropped. Each remaining balance is bucketed
    by age = (as_of − bill_date).days — current 0–30, d31_60 31–60, d61_90 61–90,
    d90_plus 90+ — and rolled up per vendor and into a grand total.

    control_balance is the date-filtered 2110 derived balance (Σdebit − Σcredit over
    JournalLine ⋈ JournalEntry where entry_date <= as_of), NEGATED: 2110 is
    credit-normal so the raw figure is negative, and negating presents the positive
    outstanding payable. in_balance is True when the aging grand total equals that
    control to the cent — the AP subledger vs. GL tie-out (D-P9c-1). Exact Decimal.
    """
    from app.modules.syerp.models import (
        Bill,
        BillLine,
        JournalEntry,
        JournalLine,
        Partner,
        Payment,
        PaymentAllocation,
    )
    from app.modules.syerp.schemas import ApAgingBucketRow, ApAgingReport, ApAgingTotals

    if as_of is None:
        as_of = date.today()

    # Bills posted to 2110 and dated on/before as_of — DRAFT bills are NOT posted
    # to 2110 and MUST be excluded (D-P9c-1 divergence guard).
    bills_result = await db.execute(
        select(Bill.id, Bill.vendor_id, Bill.bill_date).where(
            Bill.status.in_(("posted", "paid")),
            Bill.bill_date <= as_of,
        )
    )
    bills = list(bills_result.all())
    if not bills:
        bill_meta: dict[str, tuple[str, date]] = {}
        bill_ids: list[str] = []
    else:
        bill_meta = {bid: (vid, bdate) for bid, vid, bdate in bills}
        bill_ids = list(bill_meta.keys())

    # Bill-line totals per bill (Σ line.amount), coalesced to 0 (D-P8-4).
    totals_by_bill: dict[str, Decimal] = {bid: Decimal("0") for bid in bill_ids}
    if bill_ids:
        totals_result = await db.execute(
            select(BillLine.bill_id, func.coalesce(func.sum(BillLine.amount), 0))
            .where(BillLine.bill_id.in_(bill_ids))
            .group_by(BillLine.bill_id)
        )
        for bid, amount in totals_result.all():
            totals_by_bill[bid] = Decimal(amount)

    # Allocated (paid) per bill, filtered to payments dated on/before as_of — join
    # PaymentAllocation → Payment for the payment_date bound (each side coalesced).
    paid_by_bill: dict[str, Decimal] = {bid: Decimal("0") for bid in bill_ids}
    if bill_ids:
        paid_result = await db.execute(
            select(
                PaymentAllocation.bill_id,
                func.coalesce(func.sum(PaymentAllocation.amount), 0),
            )
            .select_from(PaymentAllocation)
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(
                PaymentAllocation.bill_id.in_(bill_ids),
                Payment.payment_date <= as_of,
            )
            .group_by(PaymentAllocation.bill_id)
        )
        for bid, amount in paid_result.all():
            paid_by_bill[bid] = Decimal(amount)

    # Bucket each open balance per vendor. buckets[vendor_id] = [cur, 31, 61, 90+].
    buckets: dict[str, list[Decimal]] = {}
    for bid in bill_ids:
        vendor_id, bill_date_ = bill_meta[bid]
        open_balance = totals_by_bill[bid] - paid_by_bill[bid]
        if open_balance <= 0:
            continue
        age = (as_of - bill_date_).days
        if age <= 30:
            idx = 0
        elif age <= 60:
            idx = 1
        elif age <= 90:
            idx = 2
        else:
            idx = 3
        row = buckets.setdefault(vendor_id, [Decimal("0")] * 4)
        row[idx] += open_balance

    # Resolve vendor names for the vendors that have an open payable.
    names_by_vendor: dict[str, str] = {}
    if buckets:
        names_result = await db.execute(
            select(Partner.id, Partner.name).where(Partner.id.in_(list(buckets.keys())))
        )
        names_by_vendor = {vid: name for vid, name in names_result.all()}

    vendors: list[ApAgingBucketRow] = []
    grand = [Decimal("0")] * 4
    for vendor_id, row in buckets.items():
        vendor_total = row[0] + row[1] + row[2] + row[3]
        vendors.append(
            ApAgingBucketRow(
                vendor_id=vendor_id,
                vendor_name=names_by_vendor.get(vendor_id, ""),
                current=row[0],
                d31_60=row[1],
                d61_90=row[2],
                d90_plus=row[3],
                total=vendor_total,
            )
        )
        for i in range(4):
            grand[i] += row[i]
    vendors.sort(key=lambda v: v.vendor_name)

    grand_total_amt = grand[0] + grand[1] + grand[2] + grand[3]
    grand_total = ApAgingTotals(
        current=grand[0],
        d31_60=grand[1],
        d61_90=grand[2],
        d90_plus=grand[3],
        total=grand_total_amt,
    )

    # control_balance = date-filtered 2110 derived balance, NEGATED (2110 is
    # credit-normal → raw Σdr−Σcr is negative → negate to the positive payable).
    ap_account_id = await _gl_account_id_by_code(db, "2110")
    control_raw = (
        await db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == ap_account_id,
                JournalEntry.entry_date <= as_of,
            )
        )
    ).scalar() or Decimal("0")
    control_balance = -Decimal(control_raw)

    return ApAgingReport(
        as_of=as_of,
        vendors=vendors,
        grand_total=grand_total,
        control_balance=control_balance,
        in_balance=(grand_total_amt == control_balance),
    )


async def ar_aging_report(db: AsyncSession, as_of: date | None = None) -> "ArAgingReport":
    """
    Accounts-receivable aging schedule as of a date, tied out to the 1120 control.

    The sell-side mirror of ap_aging_report. For every invoice that is POSTED to 1120
    (status in ('posted','paid') and invoice_date <= as_of) the still-open balance is
    invoice-line total − Σ ReceiptAllocation.amount for receipts dated on/before as_of,
    each side coalesced independently (D-P8-4). DRAFT invoices are excluded — a draft is
    not posted to 1120, so including it would break the tie-out. Invoices with a
    non-positive open balance are dropped. Each remaining balance is bucketed by age =
    (as_of − invoice_date).days — current 0–30, d31_60 31–60, d61_90 61–90, d90_plus
    90+ — and rolled up per customer and into a grand total.

    control_balance is the date-filtered 1120 derived balance (Σdebit − Σcredit over
    JournalLine ⋈ JournalEntry where entry_date <= as_of), taken WITHOUT negation: 1120
    is debit-normal (an asset), so the raw Σdr − Σcr is already the positive outstanding
    receivable (the AP version negates because 2110 is credit-normal — that negation is
    removed here). in_balance is True when the aging grand total equals that control to
    the cent — the AR subledger vs. GL tie-out. Exact Decimal.
    """
    from app.modules.syerp.models import (
        Invoice,
        InvoiceLine,
        JournalEntry,
        JournalLine,
        Partner,
        Receipt,
        ReceiptAllocation,
    )
    from app.modules.syerp.schemas import ArAgingBucketRow, ArAgingReport, ArAgingTotals

    if as_of is None:
        as_of = date.today()

    # Invoices posted to 1120 and dated on/before as_of — DRAFT invoices are NOT posted
    # to 1120 and MUST be excluded (the divergence guard).
    invoices_result = await db.execute(
        select(Invoice.id, Invoice.customer_id, Invoice.invoice_date).where(
            Invoice.status.in_(("posted", "paid")),
            Invoice.invoice_date <= as_of,
        )
    )
    invoices = list(invoices_result.all())
    if not invoices:
        invoice_meta: dict[str, tuple[str, date]] = {}
        invoice_ids: list[str] = []
    else:
        invoice_meta = {iid: (cid, idate) for iid, cid, idate in invoices}
        invoice_ids = list(invoice_meta.keys())

    # Invoice-line totals per invoice (Σ line.amount), coalesced to 0 (D-P8-4).
    totals_by_invoice: dict[str, Decimal] = {iid: Decimal("0") for iid in invoice_ids}
    if invoice_ids:
        totals_result = await db.execute(
            select(InvoiceLine.invoice_id, func.coalesce(func.sum(InvoiceLine.amount), 0))
            .where(InvoiceLine.invoice_id.in_(invoice_ids))
            .group_by(InvoiceLine.invoice_id)
        )
        for iid, amount in totals_result.all():
            totals_by_invoice[iid] = Decimal(amount)

    # Collected (received) per invoice, filtered to receipts dated on/before as_of — join
    # ReceiptAllocation → Receipt for the receipt_date bound (each side coalesced).
    received_by_invoice: dict[str, Decimal] = {iid: Decimal("0") for iid in invoice_ids}
    if invoice_ids:
        received_result = await db.execute(
            select(
                ReceiptAllocation.invoice_id,
                func.coalesce(func.sum(ReceiptAllocation.amount), 0),
            )
            .select_from(ReceiptAllocation)
            .join(Receipt, ReceiptAllocation.receipt_id == Receipt.id)
            .where(
                ReceiptAllocation.invoice_id.in_(invoice_ids),
                Receipt.receipt_date <= as_of,
            )
            .group_by(ReceiptAllocation.invoice_id)
        )
        for iid, amount in received_result.all():
            received_by_invoice[iid] = Decimal(amount)

    # Bucket each open balance per customer. buckets[customer_id] = [cur, 31, 61, 90+].
    buckets: dict[str, list[Decimal]] = {}
    for iid in invoice_ids:
        customer_id, invoice_date_ = invoice_meta[iid]
        open_balance = totals_by_invoice[iid] - received_by_invoice[iid]
        if open_balance <= 0:
            continue
        age = (as_of - invoice_date_).days
        if age <= 30:
            idx = 0
        elif age <= 60:
            idx = 1
        elif age <= 90:
            idx = 2
        else:
            idx = 3
        row = buckets.setdefault(customer_id, [Decimal("0")] * 4)
        row[idx] += open_balance

    # Resolve customer names for the customers that have an open receivable.
    names_by_customer: dict[str, str] = {}
    if buckets:
        names_result = await db.execute(
            select(Partner.id, Partner.name).where(Partner.id.in_(list(buckets.keys())))
        )
        names_by_customer = {cid: name for cid, name in names_result.all()}

    customers: list[ArAgingBucketRow] = []
    grand = [Decimal("0")] * 4
    for customer_id, row in buckets.items():
        customer_total = row[0] + row[1] + row[2] + row[3]
        customers.append(
            ArAgingBucketRow(
                customer_id=customer_id,
                customer_name=names_by_customer.get(customer_id, ""),
                current=row[0],
                d31_60=row[1],
                d61_90=row[2],
                d90_plus=row[3],
                total=customer_total,
            )
        )
        for i in range(4):
            grand[i] += row[i]
    customers.sort(key=lambda c: c.customer_name)

    grand_total_amt = grand[0] + grand[1] + grand[2] + grand[3]
    grand_total = ArAgingTotals(
        current=grand[0],
        d31_60=grand[1],
        d61_90=grand[2],
        d90_plus=grand[3],
        total=grand_total_amt,
    )

    # control_balance = date-filtered 1120 derived balance, taken WITHOUT negation (1120
    # is debit-normal → raw Σdr−Σcr is already the positive outstanding receivable; the
    # AP version's negation for credit-normal 2110 is deliberately removed here).
    ar_account_id = await _gl_account_id_by_code(db, "1120")
    control_raw = (
        await db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == ar_account_id,
                JournalEntry.entry_date <= as_of,
            )
        )
    ).scalar() or Decimal("0")
    control_balance = Decimal(control_raw)

    # Prepayment reclassification (GAP-1 fix): control_raw sums every 1120 leg by its own
    # entry_date, but a receipt dated on/before as_of that is allocated to an invoice dated
    # AFTER as_of leaves its Cr-1120 leg orphaned — the paying invoice's Dr-1120 leg is not
    # yet recognized (invoice_date > as_of), and the subledger drops both. Left uncorrected
    # the control reads a nonsensical NEGATIVE receivable and the tie-out badge falsely trips
    # (a customer prepayment / future-dated invoice is really an unearned deposit, not a
    # negative AR). Add those allocation amounts back so the control counts only receipts
    # against invoices recognized as of this date — the tie-out then holds for every date
    # ordering while control_balance stays GL-sourced. Exact Decimal.
    prepay_adjust = (
        await db.execute(
            select(func.coalesce(func.sum(ReceiptAllocation.amount), 0))
            .select_from(ReceiptAllocation)
            .join(Receipt, ReceiptAllocation.receipt_id == Receipt.id)
            .join(Invoice, ReceiptAllocation.invoice_id == Invoice.id)
            .where(
                Receipt.receipt_date <= as_of,
                Invoice.invoice_date > as_of,
                Invoice.status.in_(("posted", "paid")),
            )
        )
    ).scalar() or Decimal("0")
    control_balance = control_balance + Decimal(prepay_adjust)

    return ArAgingReport(
        as_of=as_of,
        customers=customers,
        grand_total=grand_total,
        control_balance=control_balance,
        in_balance=(grand_total_amt == control_balance),
    )


async def trial_balance(db: AsyncSession, as_of: date | None = None) -> "TrialBalanceReport":
    """
    Trial balance as of a date — every posting account's net debit/credit (AC7).

    ONE grouped aggregate sums debit and credit per account over JournalLine ⋈
    JournalEntry where entry_date <= as_of, each side coalesced independently
    (D-P8-4), joined to GLAccount for code/name/account_type. The inner join over
    JournalLine naturally includes ONLY accounts that carry a posting (rollup parents
    carry none, so they never appear). Each account is netted into a single column:
    if Σdr − Σcr >= 0 the magnitude sits in `debit` (credit 0), else in `credit`
    (debit 0). total_debit/total_credit are the column sums; in_balance is True when
    they are equal. Rows are ordered by code; all arithmetic is exact Decimal (D-11).
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import TrialBalanceReport, TrialBalanceRow

    if as_of is None:
        as_of = date.today()

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(JournalEntry.entry_date <= as_of)
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    rows: list[TrialBalanceRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        net = Decimal(sum_debit) - Decimal(sum_credit)
        if net >= 0:
            debit, credit = net, Decimal("0")
        else:
            debit, credit = Decimal("0"), -net
        total_debit += debit
        total_credit += credit
        rows.append(
            TrialBalanceRow(
                account_id=account_id,
                code=code,
                name=name,
                account_type=account_type,
                debit=debit,
                credit=credit,
            )
        )

    return TrialBalanceReport(
        as_of=as_of,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        in_balance=(total_debit == total_credit),
    )


async def profit_loss(
    db: AsyncSession, date_from: date, date_to: date
) -> "ProfitLossReport":
    """
    Profit & loss over an inclusive [date_from, date_to] window (AC7).

    ONE grouped aggregate sums debit/credit per posting account over JournalLine ⋈
    JournalEntry where date_from <= entry_date <= date_to (BOTH bounds inclusive),
    joined to GLAccount and filtered to account_type in ('REVENUE','EXPENSE'); each
    side is coalesced independently (D-P8-4). REVENUE is credit-normal so its period
    activity is Σcr − Σdr (positive revenue); EXPENSE is debit-normal so Σdr − Σcr
    (positive expense). Each account becomes a ProfitLossLine (ordered by code);
    total_revenue / total_expense are the section sums and net_income is their
    difference. A period with no activity folds to zeros (never NULL). Exact Decimal.
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import ProfitLossLine, ProfitLossReport

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= date_to,
            GLAccount.account_type.in_(("REVENUE", "EXPENSE")),
        )
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    revenue: list[ProfitLossLine] = []
    expense: list[ProfitLossLine] = []
    total_revenue = Decimal("0")
    total_expense = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "REVENUE":
            amount = sum_credit - sum_debit  # credit-normal → positive revenue
            total_revenue += amount
            revenue.append(
                ProfitLossLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        else:  # EXPENSE
            amount = sum_debit - sum_credit  # debit-normal → positive expense
            total_expense += amount
            expense.append(
                ProfitLossLine(account_id=account_id, code=code, name=name, amount=amount)
            )

    return ProfitLossReport(
        date_from=date_from,
        date_to=date_to,
        revenue=revenue,
        total_revenue=total_revenue,
        expense=expense,
        total_expense=total_expense,
        net_income=total_revenue - total_expense,
    )


async def balance_sheet(db: AsyncSession, as_of: date | None = None) -> "BalanceSheetReport":
    """
    Balance sheet as of a date — assets vs. liabilities + equity (AC7).

    ONE grouped aggregate sums debit/credit per posting account over JournalLine ⋈
    JournalEntry where entry_date <= as_of, each side coalesced independently
    (D-P8-4), joined to GLAccount and filtered to ASSET/LIABILITY/EQUITY. ASSET is
    debit-normal → presented Σdr − Σcr; LIABILITY and EQUITY are credit-normal →
    Σcr − Σdr, so every magnitude is positive. total_assets / total_liabilities /
    posted total_equity are the section sums.

    Because NO closing entries are posted, ledger 3130 (Current Year Net Income) is
    empty, so a COMPUTED equity line is appended: revenue less expense through as_of
    (Σcr − Σdr over REVENUE minus Σdr − Σcr over EXPENSE), reusing the P&L period
    logic from beginning-of-time through as_of. Its amount is added into total_equity.
    in_balance is True when total_assets == total_liabilities + total_equity (the
    accounting identity). Each section is ordered by code; arithmetic is exact Decimal.
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import BalanceSheetLine, BalanceSheetReport

    if as_of is None:
        as_of = date.today()

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date <= as_of,
            GLAccount.account_type.in_(("ASSET", "LIABILITY", "EQUITY")),
        )
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    assets: list[BalanceSheetLine] = []
    liabilities: list[BalanceSheetLine] = []
    equity: list[BalanceSheetLine] = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "ASSET":
            amount = sum_debit - sum_credit  # debit-normal → positive asset
            total_assets += amount
            assets.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        elif account_type == "LIABILITY":
            amount = sum_credit - sum_debit  # credit-normal → positive liability
            total_liabilities += amount
            liabilities.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        else:  # EQUITY
            amount = sum_credit - sum_debit  # credit-normal → positive equity
            total_equity += amount
            equity.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )

    # Computed current-year net income (3130) — no closing entries are posted, so
    # ledger 3130 is empty; surface it as revenue less expense through as_of (the
    # P&L period logic from beginning-of-time through as_of, D-P9c-1).
    pnl_result = await db.execute(
        select(
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date <= as_of,
            GLAccount.account_type.in_(("REVENUE", "EXPENSE")),
        )
        .group_by(GLAccount.account_type)
    )
    net_income = Decimal("0")
    for account_type, sum_debit, sum_credit in pnl_result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "REVENUE":
            net_income += sum_credit - sum_debit
        else:  # EXPENSE
            net_income -= sum_debit - sum_credit

    net_income_account_id = await _gl_account_id_by_code(db, "3130")
    equity.append(
        BalanceSheetLine(
            account_id=net_income_account_id,
            code="3130",
            name="Current Year Net Income",
            amount=net_income,
        )
    )
    total_equity += net_income
    equity.sort(key=lambda line: line.code)

    return BalanceSheetReport(
        as_of=as_of,
        assets=assets,
        total_assets=total_assets,
        liabilities=liabilities,
        total_liabilities=total_liabilities,
        equity=equity,
        total_equity=total_equity,
        in_balance=(total_assets == total_liabilities + total_equity),
    )
