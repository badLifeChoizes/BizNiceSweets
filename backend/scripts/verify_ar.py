# ABOUTME: Standalone live-DB verification for the SYERP AR engine (Phase 13, SYERP-13).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL AR service (create_invoice / post_invoice / record_receipt / ar_aging_report)
# ABOUTME: end-to-end through the SAME router payload shapes the UI sends — proving the
# ABOUTME: shipped→invoice match, the locked SO-line price, the aging↔1120 control tie-out, the
# ABOUTME: 12b COGS-on-ship JE, over-invoice/over-receipt rejection, and TWO load-bearing
# ABOUTME: concurrency barriers (receipt overpayment + create_invoice over-invoice); exits
# ABOUTME: non-zero on FAIL and self-cleans.
"""
Standalone live-DB verification script for the SYERP AR engine (Phase 13, SYERP-13).

WHY THIS EXISTS (the AR backend proof, D-P13):
  The AR engine (list_uninvoiced_shipments, create_invoice, post_invoice,
  record_receipt) is the sell-side mirror of the AP engine, layered on the GELATO
  12b outbound path (which stamps qty_shipped and posts the moving-avg COGS JE) and
  the Phase-9a GL posting engine. Its load-bearing invariants — the shipped→invoice
  quantity match with the SO line's LOCKED price, the aging↔1120-control tie-out on
  the invoice_date basis, and the FOR-UPDATE serialization of concurrent receipts /
  invoices — are cross-module properties no pure unit test can prove, and the backend
  live-DB pytest harness is broken (D-P7-4), so DB-dependent tests skip under plain
  ``pytest``. Verifiable truth must therefore come from a STANDALONE run against LIVE
  Postgres. This script stands up its own async engine + sessionmaker from the
  ``POSTGRES_*`` environment variables — it deliberately does NOT import the broken
  test conftest fixtures — and then calls the REAL service functions, proving the
  whole phase's backend behavior end-to-end rather than reimplementing it.

THE KEEPER (11a/11b lesson): this script builds ALL inputs in the REAL router/payload
  shape (customer_id, InvoiceCreate lines carrying sales_order_line_id, ArReceipt
  allocations) — NOT hand-fed internal ids the UI never sends. The shipped SO lines it
  invoices are produced by driving the REAL GELATO pick→pack→ship flow (execute_pick /
  execute_pack / execute_ship through the PickRequest/PackRequest schemas), so the AR
  match runs against genuinely-shipped quantities and a genuinely-posted COGS JE.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_ar.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) PREFLIGHT — 1110/1111/1120/1130/4110/5100 all resolve via _gl_account_id_by_code.
  (B) END-TO-END TIE-OUT — customer + SO; receive stock → pick → pack → SHIP (the 12b
      COGS-on-ship Dr 5100 / Cr 1130 moving-avg JE is asserted to exist, not rebuilt) →
      create_invoice from the shipped SO line (uninvoiced qty match; line price LOCKED to
      the SO line unit_price) → post_invoice → record_receipt partial then full → the
      ar_aging_report grand_total ties to the 1120 control balance Decimal-EXACT on the
      invoice_date basis at each stage, and the invoice auto-advances to 'paid' at zero
      open balance.
  (C) OVER-INVOICE REJECTED — invoicing more than qty_shipped − qty_invoiced raises 422,
      nothing persisted (qty_invoiced unchanged, no invoice row).
  (D) OVER-RECEIPT REJECTED — an allocation driving an invoice open balance negative
      raises 422, nothing persisted (invoice still posted, open unchanged, no rows).
  (E) LOAD-BEARING CONCURRENCY on record_receipt — two barrier-synced receipts against
      ONE posted invoice whose combined amount exceeds the open balance; only the
      over-allocation guard can reject (invoice 'posted', both amounts individually valid
      and > 0, cash account a valid ASSET). Exactly one succeeds, one is 422. Reverting
      record_receipt's invoice-row FOR UPDATE lock yields TWO successes (over-collection).
  (F) SECOND CONCURRENCY on create_invoice — two barrier-synced create_invoice against ONE
      shipped SO line cannot jointly over-invoice (combined invoiced_qty > uninvoiced):
      exactly one succeeds, one 422, and qty_invoiced never exceeds qty_shipped. Reverting
      create_invoice's SO-line FOR UPDATE lock reproduces the joint over-invoice.

LOAD-BEARING PROOF (concurrency, scenarios E and F) — HOW TO REPRODUCE THE FAIL:
  E's serialization point is ``_get_invoice_row(..., for_update=True)`` in
  service/ar.py::record_receipt; F's is the ``select(SalesOrderLine.id)...
  .with_for_update()`` loop in service/ar.py::create_invoice. Revert either lock, rerun
  this script, and the matching scenario FAILS (E: two receipts both settle → the invoice
  over-collects; F: two invoices both post → qty_invoiced exceeds qty_shipped). Restore
  it and the scenario PASSES. Exercised during development; the code is left LOCKED.

The script uses uniquely-suffixed throwaway partners / SYERP items / GELATO bins / sales
orders / shipments / invoices / receipts and CLEANS UP after itself (receipt allocations
→ receipts → invoice lines → invoices → ar_invoice/ar_receipt journal lines/entries →
shipment lines → shipments → gelato_shipment journal lines/entries → SO lines → sales
orders → inventory txns → bins → items → partners) in a finally block, so it is safe to
re-run. The seeded "Main" location and the 1110/1111/1120/1130/4110/5100 GL accounts are
reused and left in place (real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_ar.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (Invoice/InvoiceLine FK crumb_sales_order(_line); ReceiptAllocation FKs syerp_invoice —
# every table must be registered before the FKs resolve; the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.crumb.models import SalesOrder, SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.gelato.models import Bin, Shipment, ShipmentLine
from app.modules.gelato.schemas import (
    BinCreate,
    PackRequest,
    PickLineRequest,
    PickRequest,
    PutawayRequest,
)
from app.modules.gelato.service import (
    create_bin,
    execute_pack,
    execute_pick,
    execute_putaway,
    execute_ship,
)
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Partner,
    Receipt,
    ReceiptAllocation,
    StockLocation,
)
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    InvoiceLineCreate,
    PartnerCreate,
    ReceiptAllocationCreate,
)
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.accounts import _gl_account_id_by_code
from app.modules.syerp.service.ar import (
    create_invoice,
    get_invoice,
    list_uninvoiced_shipments,
    post_invoice,
    record_receipt,
)
from app.modules.syerp.service.partners import create_partner
from app.modules.syerp.service.reports import ar_aging_report

_COST_QUANTUM = Decimal("0.000001")

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


# ---------------------------------------------------------------------------
# Registry for the finally cleanup (populated as fixtures are created)
# ---------------------------------------------------------------------------


class Registry:
    """Throwaway-row id registries swept, in FK-safe order, by _cleanup."""

    def __init__(self) -> None:
        self.partner_ids: set[str] = set()
        self.item_ids: set[str] = set()
        self.bin_ids: set[int] = set()
        self.so_ids: set[str] = set()
        self.shipment_ids: set[int] = set()
        self.invoice_ids: set[str] = set()
        self.receipt_ids: set[str] = set()


# ---------------------------------------------------------------------------
# Fixture builders (drive the REAL services through the router schemas)
# ---------------------------------------------------------------------------


async def _make_customer(session_factory, unique: str, tag: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    async with session_factory() as session:
        partner = await create_partner(
            session, PartnerCreate(name=f"VERIFY-AR {tag} {unique}", is_customer=True)
        )
        return partner.id


async def _make_item(session_factory, unique: str, tag: str) -> str:
    """Create a throwaway SYERP InventoryItem via the REAL service; return its id."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(name=f"VERIFY-AR {tag} {unique}", unit_of_measure="ea"),
        )
        return item.id


async def _make_bin(session_factory, location_id: int, code: str) -> int:
    """Create a throwaway GELATO bin via the REAL create_bin service; return its id."""
    async with session_factory() as session:
        bin_ = await create_bin(session, BinCreate(location_id=location_id, code=code))
        return bin_.id


async def _item_moving_avg(session_factory, item_id: str) -> Decimal:
    """Read the item's current moving_avg_cost straight from the master row (oracle)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(InventoryItem.moving_avg_cost).where(InventoryItem.id == item_id)
            )
        ).scalar()


async def _seed_shipped_line(
    session_factory,
    reg: Registry,
    unique: str,
    tag: str,
    actor_id: str,
    location_id: int,
    cust_id: str,
    *,
    receipts: list[tuple[Decimal, Decimal]],
    into_bin_qty: Decimal,
    order_qty: Decimal,
    ship_qty: Decimal,
    unit_price: Decimal = Decimal("20"),
) -> dict:
    """
    Seed one genuinely-shipped SO line: an item with receipts (moving moving_avg off 1.0),
    a pick bin holding `into_bin_qty`, a CONFIRMED single-line SO, then pick → pack → SHIP
    `ship_qty` through the REAL GELATO flow so qty_shipped is stamped and the 12b COGS JE
    is posted. Returns the handles the AR scenarios drive create_invoice with.
    """
    item_id = await _make_item(session_factory, unique, tag)
    reg.item_ids.add(item_id)
    for qty, cost in receipts:
        async with session_factory() as session:
            await post_receipt(session, item_id, location_id, qty, cost, actor_id)

    pick_bin = await _make_bin(session_factory, location_id, f"{tag}-PICK-{unique}")
    staging_bin = await _make_bin(session_factory, location_id, f"{tag}-STAGE-{unique}")
    reg.bin_ids.update({pick_bin, staging_bin})

    async with session_factory() as session:
        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id, location_id=location_id, to_bin_id=pick_bin,
                qty=into_bin_qty, from_bin_id=None,
            ),
            actor_id,
        )

    async with session_factory() as session:
        so = await create_sales_order(
            session,
            SalesOrderCreate(
                partner_id=cust_id,
                lines=[
                    SalesOrderLineCreate(
                        item_id=item_id, qty_ordered=order_qty, unit_price=unit_price
                    )
                ],
            ),
            actor_id,
        )
    reg.so_ids.add(so.id)
    async with session_factory() as session:
        confirmed = await confirm_sales_order(session, so.id, actor_id)
    so_line_id = confirmed.lines[0].id

    async with session_factory() as session:
        picked = await execute_pick(
            session,
            PickRequest(
                sales_order_id=so.id,
                staging_bin_id=staging_bin,
                lines=[
                    PickLineRequest(
                        sales_order_line_id=so_line_id, from_bin_id=pick_bin, qty=ship_qty
                    )
                ],
            ),
            actor_id,
        )
    shipment_id = picked.id
    reg.shipment_ids.add(shipment_id)
    async with session_factory() as session:
        await execute_pack(session, shipment_id, PackRequest(), actor_id)
    async with session_factory() as session:
        await execute_ship(session, shipment_id, actor_id)

    return {
        "item_id": item_id,
        "so_id": so.id,
        "so_line_id": so_line_id,
        "shipment_id": shipment_id,
        "unit_price": unit_price,
        "ship_qty": ship_qty,
        "moving_avg": await _item_moving_avg(session_factory, item_id),
    }


async def _so_line_invoiced(session_factory, line_id: str) -> Decimal:
    """The live qty_invoiced on one SO line (oracle for over-invoice detection)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(SalesOrderLine.qty_invoiced).where(SalesOrderLine.id == line_id)
            )
        ).scalar()


def _cust_row(report, cust_id):
    """Return the ArAgingBucketRow for `cust_id` from an aging report, or None."""
    return next((r for r in report.customers if r.customer_id == cust_id), None)


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]
    reg = Registry()
    today = date.today()

    try:
        # Seed (idempotent) + reuse the "Main" stock location for on-hand receipts.
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            main_rows = (
                await session.execute(
                    select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
                )
            ).scalars().all()
        check(
            "setup: exactly one seeded 'Main' stock location resolves",
            len(main_rows) == 1,
            f"main={len(main_rows)}",
        )
        main_id = main_rows[0].id

        cust_id = await _make_customer(session_factory, unique, "CUST")
        reg.partner_ids.add(cust_id)

        # ===================================================================
        # (A) PREFLIGHT — every AR-relevant seeded account resolves
        # ===================================================================
        preflight_ok = True
        preflight_detail = ""
        acct_ids: dict[str, int] = {}
        async with session_factory() as session:
            for code in ("1110", "1111", "1120", "1130", "4110", "5100"):
                try:
                    acct_ids[code] = await _gl_account_id_by_code(session, code)
                except HTTPException as exc:
                    preflight_ok = False
                    preflight_detail = f"{code} unresolved ({exc.status_code})"
                    break
        check(
            "(A) preflight: 1110/1111/1120/1130/4110/5100 all resolve via "
            "_gl_account_id_by_code",
            preflight_ok and len(acct_ids) == 6,
            preflight_detail or f"resolved={sorted(acct_ids)}",
        )
        cash_1110_id = acct_ids.get("1110")

        # ===================================================================
        # (B) END-TO-END TIE-OUT — ship → invoice → post → receipt → aging tie
        # ===================================================================
        # Receipts 100@6 then 100@9 → moving_avg 7.5 (COGS non-trivial); pick bin holds
        # 50, order/ship 8 @ price 20 → invoice total 160.
        b = await _seed_shipped_line(
            session_factory, reg, unique, "B", actor_id, main_id, cust_id,
            receipts=[(Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))],
            into_bin_qty=Decimal("50"), order_qty=Decimal("8"), ship_qty=Decimal("8"),
            unit_price=Decimal("20"),
        )
        check(
            "(B/setup) the fixture receipt moved moving_avg_cost off 1.0 "
            "(100@6 then 100@9 → weighted 7.500000) so the ship COGS is non-trivial",
            b["moving_avg"] == Decimal("7.500000"),
            f"moving_avg={b['moving_avg']!r}",
        )

        # The 12b COGS-on-ship JE (asserted to EXIST — NOT rebuilt here): exactly one
        # gelato_shipment JournalEntry, Dr 5100 == Cr 1130 == 8 * 7.5 == 60.000000.
        expected_cogs = (b["ship_qty"] * b["moving_avg"]).quantize(_COST_QUANTUM, ROUND_HALF_UP)
        async with session_factory() as session:
            cogs_entries = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "gelato_shipment",
                        JournalEntry.source_id == str(b["shipment_id"]),
                    )
                )
            ).scalars().all()
            dr_5100 = cr_1130 = Decimal("0")
            if len(cogs_entries) == 1:
                dr_5100 = Decimal(
                    (
                        await session.execute(
                            select(func.coalesce(func.sum(JournalLine.debit), 0))
                            .join(GLAccount, GLAccount.id == JournalLine.account_id)
                            .where(
                                JournalLine.entry_id == cogs_entries[0],
                                GLAccount.code == "5100",
                            )
                        )
                    ).scalar()
                )
                cr_1130 = Decimal(
                    (
                        await session.execute(
                            select(func.coalesce(func.sum(JournalLine.credit), 0))
                            .join(GLAccount, GLAccount.id == JournalLine.account_id)
                            .where(
                                JournalLine.entry_id == cogs_entries[0],
                                GLAccount.code == "1130",
                            )
                        )
                    ).scalar()
                )
        check(
            "(B/12b) the ship posted EXACTLY ONE gelato_shipment COGS JE, Dr 5100 == Cr "
            "1130 == Σ(qty*moving_avg) == 8 * 7.5 == 60.000000 (asserted, not rebuilt)",
            len(cogs_entries) == 1 and dr_5100 == cr_1130 == expected_cogs,
            f"entries={len(cogs_entries)} dr_5100={dr_5100!r} cr_1130={cr_1130!r} "
            f"expected={expected_cogs!r}",
        )

        # The uninvoiced-shipments picker surfaces the shipped line at qty 8, price 20.
        async with session_factory() as session:
            uninvoiced = await list_uninvoiced_shipments(session, cust_id)
        row_b = next(
            (r for r in uninvoiced if r.sales_order_line_id == b["so_line_id"]), None
        )
        check(
            "(B) list_uninvoiced_shipments surfaces the shipped SO line with "
            "uninvoiced_qty == qty_shipped (8) and the SO line's locked unit_price (20)",
            row_b is not None
            and row_b.uninvoiced_qty == Decimal("8")
            and row_b.unit_price == Decimal("20")
            and row_b.item_id == b["item_id"],
            f"row={row_b!r}",
        )

        # Aging baseline BEFORE the invoice exists (invoice_date basis == today).
        async with session_factory() as session:
            report0 = await ar_aging_report(session, as_of=today)
        control0 = report0.control_balance
        check(
            "(B) aging baseline ties out: grand_total == 1120 control balance "
            "Decimal-exact and in_balance is True",
            report0.grand_total.total == report0.control_balance and report0.in_balance,
            f"grand={report0.grand_total.total!r} control={report0.control_balance!r} "
            f"in_balance={report0.in_balance}",
        )

        # create_invoice in the REAL payload shape (InvoiceLineCreate with
        # sales_order_line_id) — the line price must LOCK to the SO line unit_price.
        async with session_factory() as session:
            invoice = await create_invoice(
                session,
                customer_id=cust_id,
                sales_order_id=b["so_id"],
                invoice_date=today,
                lines=[
                    InvoiceLineCreate(
                        sales_order_line_id=b["so_line_id"], invoiced_qty=Decimal("8")
                    )
                ],
                actor_id=actor_id,
            )
        reg.invoice_ids.add(invoice.id)
        inv_line = invoice.lines[0] if invoice.lines else None
        check(
            "(B) create_invoice drafts INV-#### with total 160, and the invoice line "
            "price is LOCKED to the SO line unit_price 20 (amount == 8*20 == 160)",
            invoice.status == "draft"
            and invoice.total == Decimal("160")
            and invoice.open_balance == Decimal("160")
            and inv_line is not None
            and inv_line.sales_order_line_id == b["so_line_id"]
            and inv_line.invoiced_qty == Decimal("8")
            and inv_line.unit_price == Decimal("20")
            and inv_line.amount == Decimal("160"),
            f"status={invoice.status!r} total={invoice.total!r} line={inv_line!r}",
        )
        # The SO line's qty_invoiced accumulator was bumped by the invoiced qty.
        check(
            "(B) create_invoice bumped the SO line qty_invoiced to 8 (fully invoiced)",
            await _so_line_invoiced(session_factory, b["so_line_id"]) == Decimal("8"),
        )

        # post_invoice → Dr 1120 / Cr 4110 for the total; the aging tie-out now carries
        # the open receivable (invoice_date == today → current bucket).
        async with session_factory() as session:
            posted = await post_invoice(session, invoice.id, actor_id)
        check(
            "(B) post_invoice flips draft -> posted and stamps posted_at",
            posted.status == "posted" and posted.posted_at is not None,
            f"status={posted.status!r} posted_at={posted.posted_at!r}",
        )
        async with session_factory() as session:
            report1 = await ar_aging_report(session, as_of=today)
        row1 = _cust_row(report1, cust_id)
        check(
            "(B) after post the aging grand_total ties the 1120 control Decimal-exact "
            "(in_balance), the control rose by exactly the 160 invoice, and this "
            "customer's open 160 lands in the 'current' 0-30 bucket",
            report1.grand_total.total == report1.control_balance
            and report1.in_balance
            and report1.control_balance - control0 == Decimal("160")
            and row1 is not None
            and row1.current == Decimal("160")
            and row1.total == Decimal("160"),
            f"grand={report1.grand_total.total!r} control={report1.control_balance!r} "
            f"Δcontrol={report1.control_balance - control0!r} row={row1!r}",
        )

        # record_receipt a PARTIAL 60 → invoice stays 'posted', open 100; tie holds.
        async with session_factory() as session:
            r_partial = await record_receipt(
                session,
                receipt_date=today,
                cash_account_id=cash_1110_id,
                reference=f"RCPT-{unique}-partial",
                allocations=[ReceiptAllocationCreate(invoice_id=invoice.id, amount=Decimal("60"))],
                actor_id=actor_id,
            )
        reg.receipt_ids.add(r_partial.id)
        async with session_factory() as session:
            inv_mid = await get_invoice(session, invoice.id)
            report2 = await ar_aging_report(session, as_of=today)
        row2 = _cust_row(report2, cust_id)
        check(
            "(B) a partial receipt (60 of 160) leaves the invoice 'posted' with "
            "open_balance 100; the aging still ties the 1120 control Decimal-exact and "
            "this customer's open fell to 100",
            inv_mid.status == "posted"
            and inv_mid.open_balance == Decimal("100")
            and report2.grand_total.total == report2.control_balance
            and report2.in_balance
            and row2 is not None
            and row2.total == Decimal("100"),
            f"status={inv_mid.status!r} open={inv_mid.open_balance!r} "
            f"grand={report2.grand_total.total!r} control={report2.control_balance!r} row={row2!r}",
        )

        # record_receipt the FULL remaining 100 → invoice auto-advances to 'paid', open 0;
        # the aging returns to baseline and still ties the 1120 control Decimal-exact.
        async with session_factory() as session:
            r_final = await record_receipt(
                session,
                receipt_date=today,
                cash_account_id=cash_1110_id,
                reference=f"RCPT-{unique}-final",
                allocations=[ReceiptAllocationCreate(invoice_id=invoice.id, amount=Decimal("100"))],
                actor_id=actor_id,
            )
        reg.receipt_ids.add(r_final.id)
        async with session_factory() as session:
            inv_done = await get_invoice(session, invoice.id)
            report3 = await ar_aging_report(session, as_of=today)
        row3 = _cust_row(report3, cust_id)
        check(
            "(B) the final receipt (remaining 100) auto-advances the invoice 'posted' -> "
            "'paid' at open_balance 0; the aging ties the 1120 control Decimal-exact, the "
            "control returned to baseline, and this customer drops off the aging",
            inv_done.status == "paid"
            and inv_done.open_balance == Decimal("0")
            and report3.grand_total.total == report3.control_balance
            and report3.in_balance
            and report3.control_balance == control0
            and row3 is None,
            f"status={inv_done.status!r} open={inv_done.open_balance!r} "
            f"grand={report3.grand_total.total!r} control={report3.control_balance!r} "
            f"baseline={control0!r} row={row3!r}",
        )

        # ===================================================================
        # (C) OVER-INVOICE REJECTED — invoice > uninvoiced raises 422, no writes
        # ===================================================================
        # Ship 5; try to invoice 6 (> uninvoiced 5) → 422, qty_invoiced stays 0.
        c = await _seed_shipped_line(
            session_factory, reg, unique, "C", actor_id, main_id, cust_id,
            receipts=[(Decimal("20"), Decimal("5"))],
            into_bin_qty=Decimal("10"), order_qty=Decimal("6"), ship_qty=Decimal("5"),
        )
        over_invoice_status = None
        async with session_factory() as session:
            try:
                await create_invoice(
                    session,
                    customer_id=cust_id,
                    sales_order_id=c["so_id"],
                    invoice_date=today,
                    lines=[
                        InvoiceLineCreate(
                            sales_order_line_id=c["so_line_id"], invoiced_qty=Decimal("6")
                        )
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                over_invoice_status = exc.status_code
        async with session_factory() as session:
            c_invoices = (
                await session.execute(
                    select(func.count()).select_from(Invoice).where(
                        Invoice.sales_order_id == c["so_id"]
                    )
                )
            ).scalar()
        check(
            "(C) invoicing 6 against an uninvoiced-shipped 5 raises 422 and persists "
            "NOTHING — qty_invoiced still 0 and no invoice row exists for the SO",
            over_invoice_status == 422
            and await _so_line_invoiced(session_factory, c["so_line_id"]) == Decimal("0")
            and c_invoices == 0,
            f"status={over_invoice_status!r} invoiced="
            f"{await _so_line_invoiced(session_factory, c['so_line_id'])!r} rows={c_invoices!r}",
        )

        # ===================================================================
        # (D) OVER-RECEIPT REJECTED — allocation > open balance raises 422, no writes
        # ===================================================================
        # Ship 4 @ 20 → invoice total 80; post; try to receipt 100 (> 80) → 422.
        d = await _seed_shipped_line(
            session_factory, reg, unique, "D", actor_id, main_id, cust_id,
            receipts=[(Decimal("20"), Decimal("5"))],
            into_bin_qty=Decimal("10"), order_qty=Decimal("4"), ship_qty=Decimal("4"),
        )
        async with session_factory() as session:
            d_inv = await create_invoice(
                session,
                customer_id=cust_id,
                sales_order_id=d["so_id"],
                invoice_date=today,
                lines=[
                    InvoiceLineCreate(
                        sales_order_line_id=d["so_line_id"], invoiced_qty=Decimal("4")
                    )
                ],
                actor_id=actor_id,
            )
        reg.invoice_ids.add(d_inv.id)
        async with session_factory() as session:
            await post_invoice(session, d_inv.id, actor_id)

        async with session_factory() as session:
            receipts_before = (
                await session.execute(
                    select(func.count())
                    .select_from(ReceiptAllocation)
                    .where(ReceiptAllocation.invoice_id == d_inv.id)
                )
            ).scalar()
        over_receipt_status = None
        async with session_factory() as session:
            try:
                await record_receipt(
                    session,
                    receipt_date=today,
                    cash_account_id=cash_1110_id,
                    reference=f"RCPT-{unique}-over",
                    allocations=[
                        ReceiptAllocationCreate(invoice_id=d_inv.id, amount=Decimal("100"))
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                over_receipt_status = exc.status_code
        async with session_factory() as session:
            d_inv_after = await get_invoice(session, d_inv.id)
            receipts_after = (
                await session.execute(
                    select(func.count())
                    .select_from(ReceiptAllocation)
                    .where(ReceiptAllocation.invoice_id == d_inv.id)
                )
            ).scalar()
        check(
            "(D) a receipt of 100 against an 80 open balance raises 422 and persists "
            "NOTHING — invoice still 'posted' with open 80, no allocation rows added",
            over_receipt_status == 422
            and d_inv_after.status == "posted"
            and d_inv_after.open_balance == Decimal("80")
            and receipts_after == receipts_before == 0,
            f"status={over_receipt_status!r} inv_status={d_inv_after.status!r} "
            f"open={d_inv_after.open_balance!r} allocs {receipts_before}->{receipts_after}",
        )

        # ===================================================================
        # (D2) INVALID sales_order_id REJECTED — clean 404, no unbounded retry
        # ===================================================================
        # A client-supplied non-null sales_order_id that does not exist must be rejected
        # 404 UP FRONT. Regression guard: previously the bad FK surfaced only on the header
        # flush, was misread as an invoice-number collision, and recursed forever
        # (RecursionError / HTTP 500). A RecursionError here is UNCAUGHT below and crashes
        # the script — that is the intended loud failure signal. The line is a real one so
        # the rejection is provably the header FK check, not line validation.
        bogus_so_id = "00000000-0000-0000-0000-000000000000"
        bad_so_status = None
        async with session_factory() as session:
            try:
                await create_invoice(
                    session,
                    customer_id=cust_id,
                    sales_order_id=bogus_so_id,
                    invoice_date=today,
                    lines=[
                        InvoiceLineCreate(
                            sales_order_line_id=c["so_line_id"], invoiced_qty=Decimal("1")
                        )
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                bad_so_status = exc.status_code
        async with session_factory() as session:
            bad_so_rows = (
                await session.execute(
                    select(func.count()).select_from(Invoice).where(
                        Invoice.sales_order_id == bogus_so_id
                    )
                )
            ).scalar()
        check(
            "(D2) a non-existent sales_order_id raises a clean 404 (not RecursionError/500) "
            "and persists NOTHING — no invoice row and c's qty_invoiced still 0",
            bad_so_status == 404
            and bad_so_rows == 0
            and await _so_line_invoiced(session_factory, c["so_line_id"]) == Decimal("0"),
            f"status={bad_so_status!r} rows={bad_so_rows!r} "
            f"invoiced={await _so_line_invoiced(session_factory, c['so_line_id'])!r}",
        )

        # ===================================================================
        # (G) PREPAYMENT DATE-SEAM — aging tie-out holds when receipt_date < invoice_date
        # ===================================================================
        # Milestone-audit GAP-1 regression. A receipt dated on/before as_of allocated to an
        # invoice dated AFTER as_of (a customer prepayment / future-dated invoice) used to
        # orphan the receipt's Cr-1120 leg in the control balance — the paying invoice's
        # Dr-1120 leg is not yet recognized and the subledger drops both — so the tie-out
        # falsely tripped with a NEGATIVE 1120 control. ar_aging_report now adds those
        # allocation amounts back (prepayment reclassification), so the tie-out holds for
        # EVERY date ordering. LOAD-BEARING: delete the prepay_adjust block in
        # service/reports.py::ar_aging_report and the as_of=today assertion FAILS
        # (control undershoots grand_total by the receipt amount, in_balance False).
        g = await _seed_shipped_line(
            session_factory, reg, unique, "G", actor_id, main_id, cust_id,
            receipts=[(Decimal("20"), Decimal("5"))],
            into_bin_qty=Decimal("10"), order_qty=Decimal("5"), ship_qty=Decimal("5"),
        )
        # GAP-2 companion (checked here while the line is still uninvoiced): the
        # uninvoiced-shipments picker labels a stock line with a human "code — name",
        # never a bare item UUID.
        async with session_factory() as session:
            g_pick = await list_uninvoiced_shipments(session, cust_id)
        g_pick_row = next((r for r in g_pick if r.item_id == g["item_id"]), None)
        check(
            "(G) list_uninvoiced_shipments labels a stock line with 'code — name' "
            "(item_label set, not a bare UUID)",
            g_pick_row is not None
            and g_pick_row.item_label is not None
            and " — " in g_pick_row.item_label
            and g_pick_row.item_label != g_pick_row.item_id,
            f"row={g_pick_row!r}",
        )
        future = today + timedelta(days=10)
        # Baseline control at as_of=today BEFORE the future invoice exists.
        async with session_factory() as session:
            report_g0 = await ar_aging_report(session, as_of=today)
        base_g = report_g0.control_balance
        async with session_factory() as session:
            g_inv = await create_invoice(
                session,
                customer_id=cust_id,
                sales_order_id=g["so_id"],
                invoice_date=future,
                lines=[
                    InvoiceLineCreate(
                        sales_order_line_id=g["so_line_id"], invoiced_qty=Decimal("5")
                    )
                ],
                actor_id=actor_id,
            )
        reg.invoice_ids.add(g_inv.id)
        async with session_factory() as session:
            await post_invoice(session, g_inv.id, actor_id)
        # Prepayment: receipt dated TODAY (before the invoice_date) — the reachable path.
        async with session_factory() as session:
            g_rcpt = await record_receipt(
                session,
                receipt_date=today,
                cash_account_id=cash_1110_id,
                reference=f"RCPT-{unique}-prepay",
                allocations=[
                    ReceiptAllocationCreate(invoice_id=g_inv.id, amount=Decimal("40"))
                ],
                actor_id=actor_id,
            )
        reg.receipt_ids.add(g_rcpt.id)
        # as_of=today: the future invoice is NOT yet recognized, the prepayment is
        # reclassified out of the control, so the tie-out holds and the control is
        # UNCHANGED from baseline (no false negative receivable).
        async with session_factory() as session:
            report_g_today = await ar_aging_report(session, as_of=today)
        check(
            "(G) with a receipt dated before its invoice_date (prepayment), the aging "
            "as_of=today still ties the 1120 control Decimal-exact, in_balance is True, and "
            "the control is unchanged from baseline (no phantom negative receivable)",
            report_g_today.grand_total.total == report_g_today.control_balance
            and report_g_today.in_balance
            and report_g_today.control_balance == base_g,
            f"grand={report_g_today.grand_total.total!r} "
            f"control={report_g_today.control_balance!r} baseline={base_g!r} "
            f"in_balance={report_g_today.in_balance}",
        )
        # as_of=future: the invoice is now recognized, receipt already counted — the open
        # 60 receivable (100 invoice - 40 prepaid) ties normally. Compared against the
        # as_of=today report (identical DB state, only as_of differs) the control rises by
        # exactly G's open 60 — isolating G's recognition from the other scenarios' shared
        # customer balances.
        async with session_factory() as session:
            report_g_future = await ar_aging_report(session, as_of=future)
        check(
            "(G) as_of the invoice_date the receivable is recognized: aging ties the 1120 "
            "control Decimal-exact (in_balance), and the control rises by exactly the open "
            "60 (100 invoice - 40 prepaid) between as_of=today and as_of=invoice_date",
            report_g_future.grand_total.total == report_g_future.control_balance
            and report_g_future.in_balance
            and report_g_future.control_balance - report_g_today.control_balance
            == Decimal("60"),
            f"grand={report_g_future.grand_total.total!r} "
            f"control={report_g_future.control_balance!r} "
            f"Δ(future-today)={report_g_future.control_balance - report_g_today.control_balance!r}",
        )

        # ===================================================================
        # (E) LOAD-BEARING CONCURRENCY on record_receipt (the overpayment lock)
        # ===================================================================
        await run_receipt_concurrency(
            session_factory, reg, unique, actor_id, main_id, cust_id, cash_1110_id
        )

        # ===================================================================
        # (F) SECOND CONCURRENCY on create_invoice (the over-invoice lock)
        # ===================================================================
        await run_invoice_concurrency(
            session_factory, reg, unique, actor_id, main_id, cust_id
        )

    finally:
        await _cleanup(session_factory, reg)
        await engine.dispose()


# ---------------------------------------------------------------------------
# (E) Receipt concurrency — the invoice-row FOR UPDATE lock is what holds
# ---------------------------------------------------------------------------
#
# record_receipt locks each target invoice row FOR UPDATE up-front, BEFORE the
# read-then-write overpayment guard. Two concurrent receipts each claiming 60 against
# ONE posted invoice with open balance 100 (both amounts individually valid and > 0,
# cash account a valid ASSET, invoice 'posted' — so ONLY the over-allocation guard can
# reject) serialize: the first collects 60 (open → 40, commits, releasing the lock),
# the second blocks, re-reads the true received sum, sees open 40 < 60, and 422s. Revert
# the ``_get_invoice_row(..., for_update=True)`` lock and both read open 100 under READ
# COMMITTED, both pass, and the invoice OVER-COLLECTS (received 120 > 100) — the exact
# defect this lock exists to prevent. A sequential test cannot surface that race; only
# a barrier-synced asyncio.gather on TWO INDEPENDENT sessions can.


async def run_receipt_concurrency(
    session_factory, reg: Registry, unique: str, actor_id: str, main_id: int,
    cust_id: str, cash_account_id: int,
) -> None:
    """A posted invoice of open 100, two barrier-synced receipts of 60 — exactly one
    succeeds, the other 422s, and the invoice collects exactly 60 (never over)."""
    e = await _seed_shipped_line(
        session_factory, reg, unique, "E", actor_id, main_id, cust_id,
        receipts=[(Decimal("20"), Decimal("5"))],
        into_bin_qty=Decimal("10"), order_qty=Decimal("5"), ship_qty=Decimal("5"),
        unit_price=Decimal("20"),  # 5 * 20 == 100 open balance
    )
    async with session_factory() as session:
        e_inv = await create_invoice(
            session,
            customer_id=cust_id,
            sales_order_id=e["so_id"],
            invoice_date=date.today(),
            lines=[InvoiceLineCreate(sales_order_line_id=e["so_line_id"], invoiced_qty=Decimal("5"))],
            actor_id=actor_id,
        )
    reg.invoice_ids.add(e_inv.id)
    async with session_factory() as session:
        await post_invoice(session, e_inv.id, actor_id)

    barrier = asyncio.Barrier(2)

    async def _receipt_once():
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))  # pre-warm the connection
            await barrier.wait()
            return await record_receipt(
                session,
                receipt_date=date.today(),
                cash_account_id=cash_account_id,
                reference=f"RCPT-{unique}-race-{uuid.uuid4().hex[:6]}",
                allocations=[ReceiptAllocationCreate(invoice_id=e_inv.id, amount=Decimal("60"))],
                actor_id=actor_id,
            )

    results = await asyncio.gather(_receipt_once(), _receipt_once(), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    rejects = [r for r in results if isinstance(r, HTTPException) and r.status_code == 422]
    for r in successes:
        reg.receipt_ids.add(r.id)

    async with session_factory() as session:
        collected = Decimal(
            (
                await session.execute(
                    select(func.coalesce(func.sum(ReceiptAllocation.amount), 0)).where(
                        ReceiptAllocation.invoice_id == e_inv.id
                    )
                )
            ).scalar()
        )
        inv_after = await get_invoice(session, e_inv.id)
    check(
        "(E/THE LOCK) two concurrent receipts of 60 against ONE posted invoice (open "
        "100) never over-collect: EXACTLY one succeeds, one is rejected 422, the invoice "
        "collected exactly 60 and stays 'posted' with open 40. Reverting record_receipt's "
        "invoice-row FOR UPDATE lock regresses this to 2 successes / collected 120 / "
        "over-collected.",
        len(successes) == 1
        and len(rejects) == 1
        and collected == Decimal("60")
        and inv_after.status == "posted"
        and inv_after.open_balance == Decimal("40"),
        f"successes={len(successes)} rejects422={len(rejects)} collected={collected!r} "
        f"status={inv_after.status!r} open={inv_after.open_balance!r} "
        f"results={[type(r).__name__ for r in results]}",
    )


# ---------------------------------------------------------------------------
# (F) Invoice concurrency — the SO-line FOR UPDATE lock is what holds
# ---------------------------------------------------------------------------
#
# create_invoice locks each target SO-line row FOR UPDATE up-front, BEFORE the
# read-then-write uninvoiced-quantity guard. Two concurrent create_invoice each drawing
# 6 off ONE shipped SO line with uninvoiced 10 serialize: the first invoices 6
# (qty_invoiced → 6, commits, releasing the lock), the second blocks, re-reads the true
# qty_invoiced, sees uninvoiced 4 < 6, and 422s. Revert the
# ``select(SalesOrderLine.id)...with_for_update()`` loop and both read qty_invoiced 0
# under READ COMMITTED, both pass, and the shipment is OVER-INVOICED (qty_invoiced 12 >
# qty_shipped 10). Barrier-synced asyncio.gather on TWO INDEPENDENT sessions.


async def run_invoice_concurrency(
    session_factory, reg: Registry, unique: str, actor_id: str, main_id: int, cust_id: str
) -> None:
    """One shipped SO line (uninvoiced 10), two barrier-synced create_invoice of 6 —
    exactly one succeeds, the other 422s, and qty_invoiced never exceeds qty_shipped."""
    f = await _seed_shipped_line(
        session_factory, reg, unique, "F", actor_id, main_id, cust_id,
        receipts=[(Decimal("20"), Decimal("5"))],
        into_bin_qty=Decimal("15"), order_qty=Decimal("10"), ship_qty=Decimal("10"),
    )

    barrier = asyncio.Barrier(2)

    async def _invoice_once():
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))  # pre-warm the connection
            await barrier.wait()
            return await create_invoice(
                session,
                customer_id=cust_id,
                sales_order_id=f["so_id"],
                invoice_date=date.today(),
                lines=[
                    InvoiceLineCreate(sales_order_line_id=f["so_line_id"], invoiced_qty=Decimal("6"))
                ],
                actor_id=actor_id,
            )

    results = await asyncio.gather(_invoice_once(), _invoice_once(), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    rejects = [r for r in results if isinstance(r, HTTPException) and r.status_code == 422]
    for r in successes:
        reg.invoice_ids.add(r.id)

    qty_invoiced = await _so_line_invoiced(session_factory, f["so_line_id"])
    invoiced_sum = sum((inv.total for inv in successes), Decimal("0"))
    check(
        "(F/THE LOCK) two concurrent create_invoice of 6 against ONE shipped SO line "
        "(uninvoiced 10) never jointly over-invoice: EXACTLY one succeeds, one is "
        "rejected 422, qty_invoiced == 6 (<= qty_shipped 10, never 12). Reverting "
        "create_invoice's SO-line FOR UPDATE lock regresses this to 2 successes — BOTH "
        "invoices book (jointly 12 units > 10 shipped, the qty_invoiced accumulator "
        "lost-updating to 6), over-invoicing the shipment.",
        len(successes) == 1
        and len(rejects) == 1
        and qty_invoiced == Decimal("6")
        and qty_invoiced <= Decimal("10")
        and invoiced_sum == Decimal("120"),  # one 6*20 invoice booked 120 of revenue
        f"successes={len(successes)} rejects422={len(rejects)} qty_invoiced={qty_invoiced!r} "
        f"results={[type(r).__name__ for r in results]}",
    )


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(session_factory, reg: Registry) -> None:
    """
    Delete the throwaway rows in FK-safe order: receipt allocations -> receipts ->
    invoice lines -> invoices -> ar_invoice/ar_receipt journal lines/entries -> shipment
    lines -> shipments -> gelato_shipment journal lines/entries -> SO lines -> sales
    orders -> inventory txns -> bins -> inventory items -> partners. The seeded "Main"
    location and the 1110/1111/1120/1130/4110/5100 accounts are reused and left in place.
    """
    async with session_factory() as session:
        invoice_list = list(reg.invoice_ids)
        receipt_list = list(reg.receipt_ids)
        shipment_list = list(reg.shipment_ids)
        so_list = list(reg.so_ids)
        item_list = list(reg.item_ids)
        bin_list = list(reg.bin_ids)
        partner_list = list(reg.partner_ids)

        # AR: allocations -> receipts, invoice lines -> invoices.
        if receipt_list:
            await session.execute(
                delete(ReceiptAllocation).where(ReceiptAllocation.receipt_id.in_(receipt_list))
            )
            await session.execute(delete(Receipt).where(Receipt.id.in_(receipt_list)))
        if invoice_list:
            await session.execute(
                delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_list))
            )
            await session.execute(delete(Invoice).where(Invoice.id.in_(invoice_list)))

        # Source-linked auto-posted JEs (ar_invoice, ar_receipt, gelato_shipment).
        entry_ids: list[str] = []
        for source_type, source_ids in (
            ("ar_invoice", invoice_list),
            ("ar_receipt", receipt_list),
            ("gelato_shipment", [str(s) for s in shipment_list]),
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

        # Shipments must go before their gelato_shipment JEs (shipment.journal_entry_id FK).
        if shipment_list:
            await session.execute(
                delete(ShipmentLine).where(ShipmentLine.shipment_id.in_(shipment_list))
            )
            await session.execute(delete(Shipment).where(Shipment.id.in_(shipment_list)))

        if entry_ids:
            await session.execute(delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids)))
            await session.execute(delete(JournalEntry).where(JournalEntry.id.in_(entry_ids)))

        if so_list:
            await session.execute(
                delete(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(so_list))
            )
            await session.execute(delete(SalesOrder).where(SalesOrder.id.in_(so_list)))
        if item_list:
            await session.execute(delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list)))
        if bin_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_list)))
        if item_list:
            await session.execute(delete(InventoryItem).where(InventoryItem.id.in_(item_list)))
        if partner_list:
            await session.execute(delete(Partner).where(Partner.id.in_(partner_list)))

        await session.commit()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
