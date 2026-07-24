# ABOUTME: SERVICE-path port of verify_ar.py scenarios (B)(C)(D) (SC1d) — the AR posting-ties crux.
# ABOUTME: Drives the REAL ship→invoice→post→receipt flow + the aging↔1120 control tie-out on the test DB.
"""
SYERP AR posting-ties SERVICE crux — ported from ``backend/scripts/verify_ar.py``
scenarios (B) end-to-end tie-out, (C) over-invoice rejected, (D) over-receipt
rejected, plus the load-bearing aging↔1120 control tie-out asserted Decimal-exact
at THREE stages (post / partial receipt / final receipt) (SC1d).

WHY THIS EXISTS:
  ``ar.py`` layers the sell-side settlement engine — ``create_invoice`` LOCKING the
  invoice-line price to the shipped SO line's unit_price, ``post_invoice`` posting one
  balanced Dr 1120 / Cr 4110 journal entry, ``record_receipt`` posting Dr cash / Cr
  1120 and auto-advancing a fully-received invoice to 'paid' — on top of the GELATO
  pick→pack→ship path and the Phase-9a GL engine. Its headline cross-module invariant
  is that ``ar_aging_report``'s grand_total ties the 1120 receivable control balance
  Decimal-exact at every settlement stage. That end-to-end path only ever ran against
  the live ``biznice`` DB via the standalone verify script. This test closes that gap
  through the same service functions on the truncate-fresh test database.

D-P2b-5 (hard rule): the shipped SO line is produced by GENUINELY driving the REAL
  GELATO flow — post_receipt → execute_putaway → create_sales_order /
  confirm_sales_order → execute_pick → execute_pack → execute_ship — so qty_shipped is
  stamped and the 12b COGS JE posted by the product code, NOT hand-stamped.

Concurrency mutation-proofs (verify_ar scenarios E/F) stay in the script per
D-P2a-2; only the sequential ties are ported here (D-P2b-2).

All amounts are Decimal — never float (D-11).
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.crumb.models import SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
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
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    Invoice,
    ReceiptAllocation,
    StockLocation,
)
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    InvoiceLineCreate,
    PartnerCreate,
    ReceiptAllocationCreate,
)
from app.modules.syerp.service import (
    create_item,
    create_partner,
    derive_account_balance,
    list_journal_entries,
    post_receipt,
)
from app.modules.syerp.service.ar import (
    create_invoice,
    get_invoice,
    list_uninvoiced_shipments,
    post_invoice,
    record_receipt,
)
from app.modules.syerp.service.reports import ar_aging_report

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


def _line_for_account(entry, account_id: int):
    """Return the nested JournalLineRead for the given account from an entry."""
    return next((ln for ln in entry.lines if ln.account_id == account_id), None)


async def _account_id_by_code(session, code: str) -> int | None:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalars().first()


async def _main_location_id(session) -> int:
    """Resolve the single seeded 'Main' stock location id (seeded_ledger_db)."""
    result = await session.execute(
        select(StockLocation.id).where(StockLocation.name == DEFAULT_LOCATION_NAME)
    )
    return result.scalars().one()


async def _item_moving_avg(session, item_id: str) -> Decimal:
    """Read the item's current moving_avg_cost straight from the master row (oracle)."""
    return (
        await session.execute(
            select(InventoryItem.moving_avg_cost).where(InventoryItem.id == item_id)
        )
    ).scalar()


async def _so_line_invoiced(session, line_id: str) -> Decimal:
    """The live qty_invoiced on one SO line (oracle for over-invoice detection)."""
    return (
        await session.execute(
            select(SalesOrderLine.qty_invoiced).where(SalesOrderLine.id == line_id)
        )
    ).scalar()


def _cust_row(report, cust_id):
    """Return the ArAgingBucketRow for `cust_id` from an aging report, or None."""
    return next((r for r in report.customers if r.customer_id == cust_id), None)


async def _ar_invoice_je(session, invoice_id: str):
    """Find the single JE auto-posted by post_invoice for `invoice_id` (source-linked)."""
    entries = await list_journal_entries(session, source_type="ar_invoice")
    matches = [e for e in entries if e.source_id == invoice_id]
    return matches[0] if len(matches) == 1 else None


async def _seed_shipped_line(
    session,
    location_id: int,
    cust_id: str,
    tag: str,
    *,
    receipts: list[tuple[Decimal, Decimal]],
    into_bin_qty: Decimal,
    order_qty: Decimal,
    ship_qty: Decimal,
    unit_price: Decimal = Decimal("20"),
) -> dict:
    """
    Seed one GENUINELY-shipped SO line by driving the REAL flow end-to-end (D-P2b-5):
    an item with `receipts` (to move moving_avg off 1.0), a pick bin holding
    `into_bin_qty`, a CONFIRMED single-line SO, then pick → pack → SHIP `ship_qty`
    through the REAL GELATO service so qty_shipped is stamped and the 12b COGS JE is
    posted by the product code — NOT hand-stamped. Returns the handles the AR scenarios
    drive create_invoice with. Lifted near-verbatim from verify_ar.py::_seed_shipped_line
    (collapsed onto the single test session).
    """
    item = await create_item(
        session, InventoryItemCreate(name=f"SC1d AR {tag} Widget", unit_of_measure="ea")
    )
    for qty, cost in receipts:
        await post_receipt(session, item.id, location_id, qty, cost, ACTOR_ID)

    pick_bin = await create_bin(session, BinCreate(location_id=location_id, code=f"{tag}-PICK"))
    staging_bin = await create_bin(
        session, BinCreate(location_id=location_id, code=f"{tag}-STAGE")
    )
    await execute_putaway(
        session,
        PutawayRequest(
            item_id=item.id, location_id=location_id, to_bin_id=pick_bin.id,
            qty=into_bin_qty, from_bin_id=None,
        ),
        ACTOR_ID,
    )

    so = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust_id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item.id, qty_ordered=order_qty, unit_price=unit_price
                )
            ],
        ),
        ACTOR_ID,
    )
    confirmed = await confirm_sales_order(session, so.id, ACTOR_ID)
    so_line_id = confirmed.lines[0].id

    picked = await execute_pick(
        session,
        PickRequest(
            sales_order_id=so.id,
            staging_bin_id=staging_bin.id,
            lines=[
                PickLineRequest(
                    sales_order_line_id=so_line_id, from_bin_id=pick_bin.id, qty=ship_qty
                )
            ],
        ),
        ACTOR_ID,
    )
    await execute_pack(session, picked.id, PackRequest(), ACTOR_ID)
    await execute_ship(session, picked.id, ACTOR_ID)

    return {
        "item_id": item.id,
        "so_id": so.id,
        "so_line_id": so_line_id,
        "shipment_id": picked.id,
        "unit_price": unit_price,
        "ship_qty": ship_qty,
        "moving_avg": await _item_moving_avg(session, item.id),
    }


async def test_ar_posting_ties_crux(seeded_ledger_db) -> None:
    """
    Port of verify_ar.py (B)(C)(D) through the SERVICE path, with the aging↔1120
    control tie asserted Decimal-EXACT at three settlement stages (keeper).

    Sequential, state-building, exactly as the standalone verify script runs:
      (B) END-TO-END TIE-OUT — receive 100@6 then 100@9 (moving_avg 7.5), putaway,
          confirm an 8 @ 20 SO, pick → pack → SHIP 8 (all REAL flow, D-P2b-5) →
          create_invoice from the shipped SO line drafts total 160 with the line price
          LOCKED to the SO unit_price 20 and bumps qty_invoiced to 8 → post_invoice
          posts ONE balanced Dr 1120 / Cr 4110 == 160 JE, the open 160 lands in the
          0-30 bucket, and ar_aging_report.grand_total ties derive_account_balance(1120)
          Decimal-exact (STAGE 1). A partial receipt of 60 leaves open 100 and the tie
          holds (STAGE 2); the final 100 auto-advances 'posted' -> 'paid' at open 0, the
          control returns to baseline, and the tie holds (STAGE 3).
      (C) OVER-INVOICE REJECTED — invoicing 6 against an uninvoiced-shipped 5 raises 422
          and persists NOTHING (qty_invoiced still 0, no invoice row for the SO).
      (D) OVER-RECEIPT REJECTED — a receipt of 100 against an 80 open balance raises 422
          and persists NOTHING (invoice still 'posted' with open 80, no allocation rows).

    The aging↔1120 keeper (STAGE 1/2/3): ar_aging_report(...).grand_total.total ==
    derive_account_balance(1120), Decimal-exact. 1120 is DEBIT-normal, so
    derive_account_balance (Σdebit − Σcredit) already yields the positive receivable —
    NO sign negation (unlike AP's credit-normal 2110).

    SC2 red-on-revert: crediting the WRONG account (anything but 1120) in
    ``service/ar.py::record_receipt`` must turn the STAGE 2/3 aging-tie assertions RED —
    the 1120 control would no longer fall in step with the aging subledger.
    """
    session = seeded_ledger_db

    # -- Setup: resolve the seeded accounts + 'Main' location; a shared customer. --
    cash_1110_id = await _account_id_by_code(session, "1110")  # Cash (receipt debit)
    ar_1120_id = await _account_id_by_code(session, "1120")    # Accounts Receivable (control)
    rev_4110_id = await _account_id_by_code(session, "4110")   # Sales revenue (invoice credit)
    assert cash_1110_id is not None and ar_1120_id is not None and rev_4110_id is not None
    main_id = await _main_location_id(session)

    customer = await create_partner(
        session, PartnerCreate(name="SC1d AR Customer", is_customer=True)
    )
    today = date.today()

    # ======================================================================
    # (B) END-TO-END TIE-OUT — ship → invoice → post → receipt → aging tie
    # ======================================================================
    # Receipts 100@6 then 100@9 → moving_avg 7.5 (COGS non-trivial); pick bin holds 50,
    # order/ship 8 @ price 20 → invoice total 160.
    b = await _seed_shipped_line(
        session, main_id, customer.id, "B",
        receipts=[(Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))],
        into_bin_qty=Decimal("50"), order_qty=Decimal("8"), ship_qty=Decimal("8"),
        unit_price=Decimal("20"),
    )
    # The weighted receipts moved moving_avg off 1.0 → 7.500000 (ship COGS non-trivial).
    assert b["moving_avg"] == Decimal("7.500000")

    # The uninvoiced-shipments picker surfaces the shipped line at qty 8, price 20.
    uninvoiced = await list_uninvoiced_shipments(session, customer.id)
    row_b = next((r for r in uninvoiced if r.sales_order_line_id == b["so_line_id"]), None)
    assert row_b is not None
    assert row_b.uninvoiced_qty == Decimal("8")
    assert row_b.unit_price == Decimal("20")
    assert row_b.item_id == b["item_id"]

    # Aging baseline BEFORE the invoice exists (invoice_date basis == today).
    report0 = await ar_aging_report(session, as_of=today)
    control0 = await derive_account_balance(session, ar_1120_id)
    assert report0.grand_total.total == control0 and report0.in_balance

    # create_invoice in the REAL payload shape (InvoiceLineCreate with
    # sales_order_line_id) — the line price must LOCK to the SO line unit_price 20.
    invoice = await create_invoice(
        session,
        customer_id=customer.id,
        sales_order_id=b["so_id"],
        invoice_date=today,
        lines=[InvoiceLineCreate(sales_order_line_id=b["so_line_id"], invoiced_qty=Decimal("8"))],
        actor_id=ACTOR_ID,
    )
    inv_line = invoice.lines[0] if invoice.lines else None
    assert invoice.status == "draft"
    assert invoice.total == Decimal("160")
    assert invoice.open_balance == Decimal("160")
    assert inv_line is not None
    assert inv_line.sales_order_line_id == b["so_line_id"]
    assert inv_line.invoiced_qty == Decimal("8")
    assert inv_line.unit_price == Decimal("20")  # LOCKED to the SO line unit_price
    assert inv_line.amount == Decimal("160")
    # The SO line's qty_invoiced accumulator was bumped by the invoiced qty (fully invoiced).
    assert await _so_line_invoiced(session, b["so_line_id"]) == Decimal("8")

    # post_invoice → ONE balanced Dr 1120 / Cr 4110 for the total; draft -> posted.
    posted = await post_invoice(session, invoice.id, ACTOR_ID)
    assert posted.status == "posted" and posted.posted_at is not None

    je = await _ar_invoice_je(session, invoice.id)
    assert je is not None and je.source_type == "ar_invoice"
    ar_debit = _line_for_account(je, ar_1120_id)
    rev_credit = _line_for_account(je, rev_4110_id)
    # BOTH legs (the per-account keeper): Dr 1120 160, Cr 4110 160.
    assert ar_debit is not None and ar_debit.debit == Decimal("160")
    assert rev_credit is not None and rev_credit.credit == Decimal("160")

    # STAGE 1 — after post the aging grand_total ties the 1120 control Decimal-exact, the
    # control rose by exactly the 160 invoice, and the open 160 lands in the 0-30 bucket.
    report1 = await ar_aging_report(session, as_of=today)
    control1 = await derive_account_balance(session, ar_1120_id)
    row1 = _cust_row(report1, customer.id)
    assert report1.grand_total.total == control1  # aging↔1120 tie (STAGE 1)
    assert report1.in_balance
    assert control1 - control0 == Decimal("160")
    assert row1 is not None and row1.current == Decimal("160") and row1.total == Decimal("160")

    # record_receipt a PARTIAL 60 → invoice stays 'posted', open 100; Dr 1110 / Cr 1120.
    await record_receipt(
        session,
        receipt_date=today,
        cash_account_id=cash_1110_id,
        reference="RCPT-SC1d-partial",
        allocations=[ReceiptAllocationCreate(invoice_id=invoice.id, amount=Decimal("60"))],
        actor_id=ACTOR_ID,
    )
    inv_mid = await get_invoice(session, invoice.id)
    assert inv_mid.status == "posted" and inv_mid.open_balance == Decimal("100")

    # STAGE 2 — the aging still ties the 1120 control Decimal-exact and the open fell to 100.
    report2 = await ar_aging_report(session, as_of=today)
    control2 = await derive_account_balance(session, ar_1120_id)
    row2 = _cust_row(report2, customer.id)
    assert report2.grand_total.total == control2  # aging↔1120 tie (STAGE 2)
    assert report2.in_balance
    assert row2 is not None and row2.total == Decimal("100")

    # record_receipt the FULL remaining 100 → invoice auto-advances 'posted' -> 'paid', open 0.
    await record_receipt(
        session,
        receipt_date=today,
        cash_account_id=cash_1110_id,
        reference="RCPT-SC1d-final",
        allocations=[ReceiptAllocationCreate(invoice_id=invoice.id, amount=Decimal("100"))],
        actor_id=ACTOR_ID,
    )
    inv_done = await get_invoice(session, invoice.id)
    assert inv_done.status == "paid" and inv_done.open_balance == Decimal("0")

    # STAGE 3 — the aging returns to baseline, still ties the 1120 control Decimal-exact,
    # the control returned to baseline, and this customer drops off the aging.
    report3 = await ar_aging_report(session, as_of=today)
    control3 = await derive_account_balance(session, ar_1120_id)
    assert report3.grand_total.total == control3  # aging↔1120 tie (STAGE 3)
    assert report3.in_balance
    assert control3 == control0
    assert _cust_row(report3, customer.id) is None

    # ======================================================================
    # (C) OVER-INVOICE REJECTED — invoice > uninvoiced raises 422, no writes
    # ======================================================================
    # Ship 5; try to invoice 6 (> uninvoiced 5) → 422, qty_invoiced stays 0, no rows.
    c = await _seed_shipped_line(
        session, main_id, customer.id, "C",
        receipts=[(Decimal("20"), Decimal("5"))],
        into_bin_qty=Decimal("10"), order_qty=Decimal("6"), ship_qty=Decimal("5"),
    )
    with pytest.raises(HTTPException) as over_invoice_exc:
        await create_invoice(
            session,
            customer_id=customer.id,
            sales_order_id=c["so_id"],
            invoice_date=today,
            lines=[InvoiceLineCreate(sales_order_line_id=c["so_line_id"], invoiced_qty=Decimal("6"))],
            actor_id=ACTOR_ID,
        )
    assert over_invoice_exc.value.status_code == 422
    c_invoices = (
        await session.execute(
            select(func.count()).select_from(Invoice).where(Invoice.sales_order_id == c["so_id"])
        )
    ).scalar()
    # The refused over-invoice persisted NOTHING: qty_invoiced still 0, no invoice row.
    assert await _so_line_invoiced(session, c["so_line_id"]) == Decimal("0")
    assert c_invoices == 0

    # ======================================================================
    # (D) OVER-RECEIPT REJECTED — allocation > open balance raises 422, no writes
    # ======================================================================
    # Ship 4 @ 20 → invoice total 80; post; try to receipt 100 (> 80) → 422.
    d = await _seed_shipped_line(
        session, main_id, customer.id, "D",
        receipts=[(Decimal("20"), Decimal("5"))],
        into_bin_qty=Decimal("10"), order_qty=Decimal("4"), ship_qty=Decimal("4"),
    )
    d_inv = await create_invoice(
        session,
        customer_id=customer.id,
        sales_order_id=d["so_id"],
        invoice_date=today,
        lines=[InvoiceLineCreate(sales_order_line_id=d["so_line_id"], invoiced_qty=Decimal("4"))],
        actor_id=ACTOR_ID,
    )
    await post_invoice(session, d_inv.id, ACTOR_ID)

    allocs_before = (
        await session.execute(
            select(func.count())
            .select_from(ReceiptAllocation)
            .where(ReceiptAllocation.invoice_id == d_inv.id)
        )
    ).scalar()
    with pytest.raises(HTTPException) as over_receipt_exc:
        await record_receipt(
            session,
            receipt_date=today,
            cash_account_id=cash_1110_id,
            reference="RCPT-SC1d-over",
            allocations=[ReceiptAllocationCreate(invoice_id=d_inv.id, amount=Decimal("100"))],
            actor_id=ACTOR_ID,
        )
    assert over_receipt_exc.value.status_code == 422

    d_inv_after = await get_invoice(session, d_inv.id)
    allocs_after = (
        await session.execute(
            select(func.count())
            .select_from(ReceiptAllocation)
            .where(ReceiptAllocation.invoice_id == d_inv.id)
        )
    ).scalar()
    # The refused over-receipt persisted NOTHING: invoice still 'posted' with open 80,
    # no allocation rows added.
    assert d_inv_after.status == "posted"
    assert d_inv_after.open_balance == Decimal("80")
    assert allocs_after == allocs_before == 0
