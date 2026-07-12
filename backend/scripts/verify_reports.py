# ABOUTME: Standalone live-DB verification for the SYERP financial-reports engine (Phase 9c).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives the
# ABOUTME: REAL report + AP + GL service functions end-to-end, proving the AP-aging buckets, the
# ABOUTME: 2110 subledger↔GL tie-out crux, and the trial balance / P&L / balance-sheet identities;
# ABOUTME: exits non-zero on FAIL and self-cleans so it is safe to re-run.
"""
Standalone live-DB verification script for the SYERP financial reports (Phase 9c).

WHY THIS EXISTS (the reporting proof, D-P9c):
  The reporting engine (ap_aging_report, trial_balance, profit_loss, balance_sheet)
  reads the whole ledger the Phase-9a GL engine and Phase-9b AP engine post into.
  Its load-bearing invariant is the AP subledger ↔ GL tie-out: the aging grand total
  MUST equal the date-filtered 2110 Accounts-Payable control balance to the cent
  (D-P9c-1), and a DRAFT bill — which is NOT posted to 2110 — must appear in NEITHER
  side (the divergence guard). Alongside it stand the three statement identities:
  trial-balance debits == credits, P&L net_income == revenue − expense with
  out-of-period entries excluded, and the balance-sheet accounting identity
  assets == liabilities + equity with a COMPUTED current-year-net-income equity line.
  None of that can be proven by the pure unit tests, and the backend live-DB pytest
  harness is broken (D-P7-4), so DB-dependent tests skip under plain ``pytest``.
  Verifiable truth must therefore come from a STANDALONE run against LIVE Postgres.
  This script stands up its own async engine + sessionmaker from the ``POSTGRES_*``
  environment variables — it deliberately does NOT import the broken test conftest
  fixtures — and drives the REAL service functions (create_bill / post_bill /
  record_payment / post_journal_entry build the state; the report functions are the
  subjects under test), proving the whole phase's behavior end-to-end rather than
  reimplementing it.

HOW TO RUN (the compose ``db`` service is not host-published):
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Run this script INSIDE the running dev api container, which already carries
  #    the app's POSTGRES_* env and can resolve the compose `db` host:
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_reports.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (a) AP AGING BUCKETS (SC1): a FRESH unique vendor gets four posted bills with
      distinct bill_dates straddling the 30/60/90-day boundaries relative to a FIXED
      as_of — each open balance lands in the correct bucket (current / d31_60 / d61_90
      / d90_plus), the vendor row's five fields sum to `total`, and the vendor row's
      contribution shows up in the grand total (delta-checked, so it is robust to any
      pre-existing AP data).
  (b) TIE-OUT (SC2, THE CRUX): grand_total.total == the negated 2110 control balance,
      Decimal-EXACT, with in_balance True — a GLOBAL invariant (every posted bill Cr
      2110 by its total, every payment Dr 2110 by its allocation, aging open ==
      total − paid), so absolute equality is correct and robust. A PARTIALLY-paid bill
      (partial payment dated <= as_of drops BOTH the aging open balance AND the 2110
      debit leg) keeps the equality; a DRAFT bill (created, NOT posted) appears in
      NEITHER the aging total NOR the 2110 control (the divergence guard).
  (c) TRIAL BALANCE (SC3): total_debit == total_credit, Decimal-EXACT, in_balance True
      (a global invariant over a balanced double-entry ledger); rollup-parent accounts
      that carry children but no direct postings (2100, 1000, 3100) never appear.
  (d) P&L (SC4): over a historical [date_from, date_to] window, in-period manual
      revenue/expense JEs move total_revenue / total_expense by exactly their amounts
      (delta-checked), net_income == total_revenue − total_expense (report identity),
      and out-of-period entries (dated OUTSIDE the window) are EXCLUDED from the totals.
  (e) BALANCE SHEET (SC5): total_assets == total_liabilities + total_equity,
      Decimal-EXACT, in_balance True (the accounting identity); the COMPUTED 3130
      "Current Year Net Income" equity line equals Σrevenue − Σexpense through as_of
      (cross-checked against profit_loss(beginning-of-time, as_of).net_income) while
      ledger 3130 itself carries ZERO posted lines (the computed line is appended by
      the service, never posted).

ROBUSTNESS NOTES: the report functions aggregate over the WHOLE ledger, so an
absolute figure that could be polluted by pre-existing rows is checked as a DELTA
(bucket contribution in (a); period activity in (d)) or against a FRESH unique vendor
(the vendor row in (a)). The tie-out equality (b) and the trial-balance /
balance-sheet identities (c)/(e) are GLOBAL invariants that hold for the entire
ledger regardless of other data, so those are asserted absolutely — that global truth
IS the property under test. The 3130 cross-check (e) compares two computations over
the same ledger, so it holds regardless of pre-existing data.

The script uses uniquely-named throwaway data — a fresh vendor plus a family of bills,
payments, and a few manual journal entries dated far in the past (year 2001/2002, so
they cannot collide with real data) — and CLEANS UP after itself (deletes its payment
allocations, payments, journal lines/entries, bill lines, bills, and vendor, in FK
order) in a finally block, so it is safe to re-run. The AP bills debit an ASSET account
(1150 Prepaid Expenses) rather than an EXPENSE account so the AP scenario stays out of
the P&L, keeping the (d)/(e) accounts cleanly separated; the seeded accounts are reused
and left in place (real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_reports.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (every table must be registered before the FKs resolve; the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.syerp.models import (
    Bill,
    BillLine,
    GLAccount,
    JournalEntry,
    JournalLine,
    Partner,
    Payment,
    PaymentAllocation,
)
from app.modules.syerp.schemas import BillLineCreate, PartnerCreate, PaymentAllocationCreate
from app.modules.syerp.service import (
    ap_aging_report,
    balance_sheet,
    create_bill,
    create_partner,
    post_bill,
    post_journal_entry,
    profit_loss,
    record_payment,
    trial_balance,
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


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # A FIXED as_of anchors every aging-bucket / balance-sheet assertion. Anchoring on
    # today keeps the 30/60/90-day offsets meaningful against real calendar dates.
    as_of = date.today()

    vendor_id: str | None = None
    created_bill_ids: list[str] = []
    created_payment_ids: list[str] = []
    created_entry_ids: list[str] = []  # manual P&L journal entries

    async def make_expense_bill(amount: Decimal, bill_date: date, asset_account_id: int):
        """
        Create a draft AP bill for the fresh vendor with ONE expense line coded to an
        ASSET account (1150). post_bill will book Dr 1150 / Cr 2110 — a real 2110
        posting (so the tie-out is meaningful) that stays OUT of the P&L (so the (d)/(e)
        revenue/expense accounts remain cleanly isolated). `bill_date` places the bill
        in an aging bucket; post_bill posts the JE at entry_date == bill_date.
        """
        async with session_factory() as s:
            bill = await create_bill(
                s,
                vendor_id=vendor_id,
                vendor_invoice_ref=f"INV-{unique}-{len(created_bill_ids) + 1}",
                bill_date=bill_date,
                lines=[
                    BillLineCreate(
                        line_type="expense", account_id=asset_account_id, amount=amount
                    )
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
        # Setup: fresh vendor; resolve the seeded accounts used below.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor = await create_partner(
                session, PartnerCreate(name=f"VERIFY Reports Vendor {unique}", is_vendor=True)
            )
            vendor_id = vendor.id

        async with session_factory() as session:
            ap_2110 = await _account_by_code(session, "2110")
            prepaid_1150 = await _account_by_code(session, "1150")
            cash_1110 = await _account_by_code(session, "1110")
            revenue_4110 = await _account_by_code(session, "4110")
            expense_5110 = await _account_by_code(session, "5110")
            net_income_3130 = await _account_by_code(session, "3130")
        check(
            "seeded accounts resolve: 2110 (LIABILITY), 1150/1110 (ASSET), "
            "4110 (REVENUE), 5110 (EXPENSE), 3130 (EQUITY)",
            all(
                a is not None
                for a in (ap_2110, prepaid_1150, cash_1110, revenue_4110, expense_5110,
                          net_income_3130)
            )
            and ap_2110.account_type == "LIABILITY"
            and prepaid_1150.account_type == "ASSET"
            and cash_1110.account_type == "ASSET"
            and revenue_4110.account_type == "REVENUE"
            and expense_5110.account_type == "EXPENSE"
            and net_income_3130.account_type == "EQUITY",
        )
        prepaid_id = prepaid_1150.id
        cash_id = cash_1110.id
        revenue_id = revenue_4110.id
        expense_id = expense_5110.id
        net_income_3130_id = net_income_3130.id

        # -------------------------------------------------------------------
        # (a) AP AGING BUCKETS (SC1). Four posted bills for the FRESH vendor at
        #     as_of−10 / −45 / −75 / −120 days land in current / d31_60 / d61_90 /
        #     d90_plus respectively. The vendor row is exact (fresh vendor); the grand
        #     total is delta-checked so pre-existing AP data cannot pollute it.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            grand_before = (await ap_aging_report(session, as_of)).grand_total

        amt_cur = Decimal("100")     # age 10  -> current (0–30)
        amt_31 = Decimal("200")      # age 45  -> d31_60
        amt_61 = Decimal("300")      # age 75  -> d61_90
        amt_90 = Decimal("400")      # age 120 -> d90_plus
        for amount, offset in (
            (amt_cur, 10),
            (amt_31, 45),
            (amt_61, 75),
            (amt_90, 120),
        ):
            bill = await make_expense_bill(amount, as_of - timedelta(days=offset), prepaid_id)
            await post(bill.id)

        async with session_factory() as session:
            report_a = await ap_aging_report(session, as_of)
        vrow = next((v for v in report_a.vendors if v.vendor_id == vendor_id), None)
        check(
            "the fresh vendor's aging row buckets each bill by age: current==100, "
            "d31_60==200, d61_90==300, d90_plus==400 (SC1)",
            vrow is not None
            and vrow.current == amt_cur
            and vrow.d31_60 == amt_31
            and vrow.d61_90 == amt_61
            and vrow.d90_plus == amt_90,
            f"row={vrow!r}",
        )
        check(
            "the vendor row's five fields sum to `total` "
            "(current+d31_60+d61_90+d90_plus == total == 1000)",
            vrow is not None
            and vrow.current + vrow.d31_60 + vrow.d61_90 + vrow.d90_plus == vrow.total
            and vrow.total == Decimal("1000"),
            f"total={vrow.total if vrow else None!r}",
        )
        # Delta-check the grand total: robust to any pre-existing AP data (the vendor's
        # contribution is exactly its four bills — it sums INTO the grand total).
        gt = report_a.grand_total
        check(
            "the vendor row sums INTO the grand total — each bucket's grand-total delta "
            "equals this vendor's contribution (current+100, d31_60+200, d61_90+300, "
            "d90_plus+400, total+1000)",
            gt.current - grand_before.current == amt_cur
            and gt.d31_60 - grand_before.d31_60 == amt_31
            and gt.d61_90 - grand_before.d61_90 == amt_61
            and gt.d90_plus - grand_before.d90_plus == amt_90
            and gt.total - grand_before.total == Decimal("1000"),
            f"delta_total={gt.total - grand_before.total!r}",
        )
        check(
            "the grand total's five fields sum to `total` "
            "(current+d31_60+d61_90+d90_plus == total)",
            gt.current + gt.d31_60 + gt.d61_90 + gt.d90_plus == gt.total,
            f"grand_total={gt!r}",
        )

        # -------------------------------------------------------------------
        # (b) TIE-OUT (SC2, THE CRUX). grand_total.total == the negated 2110 control
        #     balance, Decimal-EXACT — a GLOBAL invariant, so absolute equality is
        #     correct. Then a PARTIALLY-paid bill keeps it; then a DRAFT bill appears
        #     in NEITHER side (the divergence guard).
        # -------------------------------------------------------------------
        check(
            "CRUX: aging grand_total.total EXACTLY equals the negated 2110 control "
            "balance and in_balance is True — the AP subledger ties to the GL (SC2)",
            report_a.grand_total.total == report_a.control_balance
            and report_a.in_balance is True,
            f"grand_total={report_a.grand_total.total!r} control={report_a.control_balance!r} "
            f"in_balance={report_a.in_balance!r}",
        )
        print(
            f"      (crux detail) grand_total={report_a.grand_total.total} "
            f"control_balance={report_a.control_balance}"
        )

        # A partially-paid bill: 500 in the current bucket, then a 200 partial payment
        # dated == as_of (so it counts on BOTH sides: aging open drops 200, and the
        # payment JE Dr 2110 200 drops the control by 200). Equality must survive.
        bill_pay = await make_expense_bill(Decimal("500"), as_of - timedelta(days=5), prepaid_id)
        await post(bill_pay.id)
        async with session_factory() as session:
            pay = await record_payment(
                session,
                payment_date=as_of,
                cash_account_id=cash_id,
                reference=f"CHK-{unique}-partial",
                allocations=[PaymentAllocationCreate(bill_id=bill_pay.id, amount=Decimal("200"))],
                actor_id=actor_id,
            )
        created_payment_ids.append(pay.id)

        async with session_factory() as session:
            report_paid = await ap_aging_report(session, as_of)
        # The partially-paid bill contributes 500−200 == 300 to the current bucket; find
        # the vendor row and confirm the still-open 300 rides in `current` (100 from the
        # (a) current bill + 300 == 400) — delta-checked against the (a) snapshot.
        vrow_paid = next((v for v in report_paid.vendors if v.vendor_id == vendor_id), None)
        check(
            "a partial payment (200 of 500) leaves the still-open 300 in the aging and "
            "the tie-out STILL holds EXACTLY (grand_total.total == control, in_balance)",
            report_paid.grand_total.total == report_paid.control_balance
            and report_paid.in_balance is True
            and vrow_paid is not None
            and vrow_paid.current == amt_cur + Decimal("300"),
            f"grand_total={report_paid.grand_total.total!r} control={report_paid.control_balance!r} "
            f"vendor_current={vrow_paid.current if vrow_paid else None!r}",
        )

        # A DRAFT bill (created, NOT posted): 999. It is NOT posted to 2110, so it must
        # appear in NEITHER the aging total NOR the 2110 control — both must be UNCHANGED
        # from the pre-draft (report_paid) snapshot, and in_balance still True.
        draft_bill = await make_expense_bill(Decimal("999"), as_of - timedelta(days=5), prepaid_id)
        async with session_factory() as session:
            report_draft = await ap_aging_report(session, as_of)
        check(
            "a DRAFT bill (999, not posted) appears in NEITHER the aging total NOR the "
            "2110 control — both unchanged from pre-draft, in_balance still True "
            "(the divergence guard)",
            report_draft.grand_total.total == report_paid.grand_total.total
            and report_draft.control_balance == report_paid.control_balance
            and report_draft.grand_total.total == report_draft.control_balance
            and report_draft.in_balance is True,
            f"aging {report_paid.grand_total.total!r}->{report_draft.grand_total.total!r} "
            f"control {report_paid.control_balance!r}->{report_draft.control_balance!r}",
        )

        # -------------------------------------------------------------------
        # (c) TRIAL BALANCE (SC3). total_debit == total_credit (a global invariant over
        #     the balanced double-entry ledger), in_balance True; rollup-parent accounts
        #     (children but no direct postings) never appear.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            tb = await trial_balance(session, as_of)
        check(
            "trial_balance total_debit EXACTLY equals total_credit and in_balance is "
            "True — the whole ledger balances (SC3)",
            tb.total_debit == tb.total_credit and tb.in_balance is True,
            f"total_debit={tb.total_debit!r} total_credit={tb.total_credit!r} "
            f"in_balance={tb.in_balance!r}",
        )
        tb_codes = {row.code for row in tb.rows}
        parents_absent = {"2100", "1000", "3100"}
        check(
            "rollup-parent accounts that carry children but no direct postings "
            "(2100, 1000, 3100) do NOT appear in the trial-balance rows",
            parents_absent.isdisjoint(tb_codes),
            f"unexpected parents present={parents_absent & tb_codes!r}",
        )

        # -------------------------------------------------------------------
        # (d) P&L (SC4). Over a HISTORICAL window [pl_from, pl_to] (year 2001, so no
        #     real data collides), in-period manual revenue/expense JEs move the totals
        #     by exactly their amounts (delta-checked), net_income is the report identity,
        #     and out-of-period entries are EXCLUDED.
        # -------------------------------------------------------------------
        pl_from = date(2001, 1, 1)
        pl_to = date(2001, 12, 31)
        rev_amt = Decimal("100")
        exp_amt = Decimal("40")

        async with session_factory() as session:
            pl0 = await profit_loss(session, pl_from, pl_to)

        # In-period: Dr 1110 / Cr 4110 revenue 100 @ 2001-06-01; Dr 5110 / Cr 1110
        # expense 40 @ 2001-06-15. Both balanced 2-line entries.
        async with session_factory() as session:
            e_rev = await post_journal_entry(
                session,
                entry_date=date(2001, 6, 1),
                memo=f"VERIFY P&L revenue {unique}",
                lines=[
                    {"account_id": cash_id, "debit": rev_amt},
                    {"account_id": revenue_id, "credit": rev_amt},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e_rev.id)
        async with session_factory() as session:
            e_exp = await post_journal_entry(
                session,
                entry_date=date(2001, 6, 15),
                memo=f"VERIFY P&L expense {unique}",
                lines=[
                    {"account_id": expense_id, "debit": exp_amt},
                    {"account_id": cash_id, "credit": exp_amt},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e_exp.id)

        async with session_factory() as session:
            pl1 = await profit_loss(session, pl_from, pl_to)
        check(
            "in-period revenue/expense move the P&L totals by exactly their amounts "
            "(Δtotal_revenue==100, Δtotal_expense==40) (SC4)",
            pl1.total_revenue - pl0.total_revenue == rev_amt
            and pl1.total_expense - pl0.total_expense == exp_amt,
            f"Δrevenue={pl1.total_revenue - pl0.total_revenue!r} "
            f"Δexpense={pl1.total_expense - pl0.total_expense!r}",
        )
        check(
            "P&L net_income EXACTLY equals total_revenue − total_expense (report identity)",
            pl1.net_income == pl1.total_revenue - pl1.total_expense,
            f"net_income={pl1.net_income!r} revenue={pl1.total_revenue!r} "
            f"expense={pl1.total_expense!r}",
        )

        # Out-of-period: revenue 500 @ 2002-01-01 (AFTER pl_to) and expense 200 @
        # 2000-12-31 (BEFORE pl_from). Neither may enter the [pl_from, pl_to] totals.
        async with session_factory() as session:
            e_rev_out = await post_journal_entry(
                session,
                entry_date=date(2002, 1, 1),
                memo=f"VERIFY P&L revenue OOP {unique}",
                lines=[
                    {"account_id": cash_id, "debit": Decimal("500")},
                    {"account_id": revenue_id, "credit": Decimal("500")},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e_rev_out.id)
        async with session_factory() as session:
            e_exp_out = await post_journal_entry(
                session,
                entry_date=date(2000, 12, 31),
                memo=f"VERIFY P&L expense OOP {unique}",
                lines=[
                    {"account_id": expense_id, "debit": Decimal("200")},
                    {"account_id": cash_id, "credit": Decimal("200")},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e_exp_out.id)

        async with session_factory() as session:
            pl2 = await profit_loss(session, pl_from, pl_to)
        check(
            "out-of-period entries (revenue @ 2002-01-01, expense @ 2000-12-31) are "
            "EXCLUDED — the window totals are UNCHANGED from before they were posted",
            pl2.total_revenue == pl1.total_revenue
            and pl2.total_expense == pl1.total_expense
            and pl2.net_income == pl1.net_income,
            f"revenue {pl1.total_revenue!r}->{pl2.total_revenue!r} "
            f"expense {pl1.total_expense!r}->{pl2.total_expense!r}",
        )

        # -------------------------------------------------------------------
        # (e) BALANCE SHEET (SC5). total_assets == total_liabilities + total_equity
        #     (the accounting identity), in_balance True; the COMPUTED 3130 equity line
        #     equals Σrevenue − Σexpense through as_of (cross-checked against
        #     profit_loss(beginning-of-time, as_of).net_income) while ledger 3130 is empty.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            bs = await balance_sheet(session, as_of)
        check(
            "balance_sheet total_assets EXACTLY equals total_liabilities + total_equity "
            "and in_balance is True — the accounting identity (SC5)",
            bs.total_assets == bs.total_liabilities + bs.total_equity
            and bs.in_balance is True,
            f"assets={bs.total_assets!r} liab={bs.total_liabilities!r} "
            f"equity={bs.total_equity!r} in_balance={bs.in_balance!r}",
        )

        # The computed 3130 line: exactly one, and it equals net income through as_of.
        bs_3130 = [line for line in bs.equity if line.code == "3130"]
        async with session_factory() as session:
            pl_all = await profit_loss(session, date(1900, 1, 1), as_of)
        check(
            "the COMPUTED 3130 'Current Year Net Income' equity line (exactly one, "
            "appended by the service) equals Σrevenue − Σexpense through as_of "
            "(profit_loss(beginning-of-time, as_of).net_income)",
            len(bs_3130) == 1
            and bs_3130[0].name == "Current Year Net Income"
            and bs_3130[0].amount == pl_all.net_income,
            f"lines={[(l.code, l.amount) for l in bs_3130]!r} pnl_net={pl_all.net_income!r}",
        )

        # Ledger 3130 itself must carry ZERO posted journal lines (no closing entries).
        async with session_factory() as session:
            posted_3130 = (
                await session.execute(
                    select(func.count())
                    .select_from(JournalLine)
                    .where(JournalLine.account_id == net_income_3130_id)
                )
            ).scalar()
        check(
            "ledger 3130 stays EMPTY — zero posted journal lines (the equity net-income "
            "line is computed and appended, never posted)",
            posted_3130 == 0,
            f"posted 3130 lines={posted_3130!r}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows in FK-safe order: payment allocations →
        # payments → journal lines → journal entries (ap_bill / ap_payment,
        # source-linked, plus the manual P&L entries) → bill lines → bills → vendor.
        # The seeded accounts are reused and left in place (real deploy state).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            if created_payment_ids:
                await session.execute(
                    delete(PaymentAllocation).where(
                        PaymentAllocation.payment_id.in_(created_payment_ids)
                    )
                )
                await session.execute(
                    delete(Payment).where(Payment.id.in_(created_payment_ids))
                )

            # Source-linked auto-posted JEs (bill posts + payment posts) plus the manual
            # P&L entries tracked directly.
            entry_ids: list[str] = list(created_entry_ids)
            for source_type, source_ids in (
                ("ap_bill", created_bill_ids),
                ("ap_payment", created_payment_ids),
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
