# ABOUTME: SERVICE-path port of verify_gl.py scenarios (a)(c)(b)(d) (SC1b) — the GL posting-ties crux.
# ABOUTME: Drives the real GL service (post/reverse/derive/register + receive_line auto-post) on the test DB.
"""
SYERP GL posting-ties SERVICE crux — ported from ``backend/scripts/verify_gl.py``
scenarios (a) balanced/unbalanced post, (c) derived balances + register, (b)
reversal immutability, (d) receipt auto-post (SC1b).

WHY THIS EXISTS:
  ``test_gl_journal.py`` covers the PURE balance helpers (``_je_is_balanced`` /
  ``_je_totals`` / ``_reverse_lines``) with no DB. The posting engine a shop
  actually relies on — double-entry enforcement raising 422, derived balances,
  append-only reversal, and the Phase-8 receiving path AUTO-POSTING a balanced
  Dr 1130 / Cr 2150 JE in the SAME transaction as the stock receipt (SYERP-12
  AC3) — only ever ran end-to-end against the live ``biznice`` DB via the
  standalone verify script. This test closes that gap through the same service
  functions on the truncate-fresh test database.

Concurrency/atomicity mutation-proofs (verify_gl scenarios f/g/h) stay in the
script per D-P2a-2; only the sequential ties are ported here (D-P2b-2).

All amounts are Decimal — never float (D-11).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.syerp.models import GLAccount
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    PartnerCreate,
    POCreate,
    POLineCreate,
    StockLocationCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_item,
    create_location,
    create_partner,
    create_po,
    derive_account_balance,
    get_account_register,
    get_journal_entry,
    list_journal_entries,
    post_journal_entry,
    receive_line,
    reverse_journal_entry,
)

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


def _line_for_account(entry, account_id: int):
    """Return the nested JournalLineRead for the given account from an entry."""
    return next((ln for ln in entry.lines if ln.account_id == account_id), None)


async def _account_id_by_code(session, code: str) -> int | None:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalars().first()


async def test_gl_posting_ties_crux(seeded_ledger_db) -> None:
    """
    Port of verify_gl.py (a)(c)(b)(d) through the SERVICE path.

    Sequential, state-building, exactly as the standalone verify script runs:
      (a) post_journal_entry balanced (Dr A 10 / Cr B 10) persists 2 lines; an
          unbalanced entry (Dr 10 / Cr 5) RAISES HTTPException 422 and persists
          NOTHING (no JE, no lines).
      (c) after the 10/20/30 series, derive_account_balance A == 60, B == −60;
          get_account_register over [d1,d3] running == [10, 30, 60], opening 0 /
          closing 60.
      (b) reverse_journal_entry posts a NEW entry that swaps every debit/credit
          and links reversal_of_id; the ORIGINAL is untouched (immutability).
      (d) receive_line 4@5 AUTO-POSTS exactly ONE 'po_receipt' JE source-linked
          to the PO line, balanced Dr 1130 / Cr 2150 == Decimal("20.000000"); the
          2150 derived balance moved −20 and the 1130 moved +20 (BOTH legs, the
          per-account invariant keeper).

    SC2 red-on-revert: commenting out the receipt auto-post in
    ``service/purchasing.py::receive_line`` must turn the (d) receipt-JE
    assertions RED.
    """
    session = seeded_ledger_db

    # Dates for the register series (in the past so the reversal, dated today,
    # falls OUTSIDE the register window and cannot perturb it) — mirrors the script.
    base = date.today() - timedelta(days=30)
    d1, d2, d3 = base, base + timedelta(days=10), base + timedelta(days=20)

    # -- Setup: two throwaway GL accounts (deterministic, isolated) ----------
    acct_a = GLAccount(code="ZA0001", name="SC1b Debit Acct", account_type="ASSET")
    acct_b = GLAccount(code="ZB0001", name="SC1b Credit Acct", account_type="LIABILITY")
    session.add_all([acct_a, acct_b])
    await session.commit()
    acct_a_id, acct_b_id = acct_a.id, acct_b.id

    # -- (a) balanced post SUCCEEDS; unbalanced RAISES 422, persists nothing --
    e1 = await post_journal_entry(
        session,
        entry_date=d1,
        memo="SC1b balanced",
        lines=[
            {"account_id": acct_a_id, "debit": Decimal("10")},
            {"account_id": acct_b_id, "credit": Decimal("10")},
        ],
        actor_id=ACTOR_ID,
    )
    a_line = _line_for_account(e1, acct_a_id)
    b_line = _line_for_account(e1, acct_b_id)
    assert len(e1.lines) == 2
    assert a_line is not None and a_line.debit == Decimal("10") and a_line.credit is None
    assert b_line is not None and b_line.credit == Decimal("10") and b_line.debit is None

    unbalanced_status = None
    with pytest.raises(HTTPException) as exc_info:
        await post_journal_entry(
            session,
            entry_date=d1,
            memo="SC1b unbalanced",
            lines=[
                {"account_id": acct_a_id, "debit": Decimal("10")},
                {"account_id": acct_b_id, "credit": Decimal("5")},
            ],
            actor_id=ACTOR_ID,
        )
    unbalanced_status = exc_info.value.status_code
    assert unbalanced_status == 422
    # The rejected unbalanced entry persisted NOTHING (no JE, no lines).
    after_reject = await list_journal_entries(session, source_type=None)
    assert not any(e.memo == "SC1b unbalanced" for e in after_reject)

    # -- Post the rest of the register series (E2 @ d2, E3 @ d3) -------------
    e2 = await post_journal_entry(
        session,
        entry_date=d2,
        memo="SC1b series-2",
        lines=[
            {"account_id": acct_a_id, "debit": Decimal("20")},
            {"account_id": acct_b_id, "credit": Decimal("20")},
        ],
        actor_id=ACTOR_ID,
    )
    await post_journal_entry(
        session,
        entry_date=d3,
        memo="SC1b series-3",
        lines=[
            {"account_id": acct_a_id, "debit": Decimal("30")},
            {"account_id": acct_b_id, "credit": Decimal("30")},
        ],
        actor_id=ACTOR_ID,
    )

    # -- (c) derived balances == Σdebit − Σcredit; monotonic register --------
    bal_a = await derive_account_balance(session, acct_a_id)
    bal_b = await derive_account_balance(session, acct_b_id)
    assert bal_a == Decimal("60")  # 10 + 20 + 30
    assert bal_b == Decimal("-60")  # credited only

    register = await get_account_register(session, acct_a_id, date_from=d1, date_to=d3)
    running = [row.running_balance for row in register.rows]
    assert len(register.rows) == 3
    assert running == [Decimal("10"), Decimal("30"), Decimal("60")]
    assert all(b > a for a, b in zip(running, running[1:]))  # strictly monotonic
    assert register.opening_balance == Decimal("0")  # no postings before d1
    assert register.closing_balance == Decimal("60")

    # -- (b) reversal: NEW entry swaps legs, links back, original immutable ---
    reversal = await reverse_journal_entry(session, e2.id, ACTOR_ID)
    rev_a = _line_for_account(reversal, acct_a_id)
    rev_b = _line_for_account(reversal, acct_b_id)
    assert reversal.id != e2.id and reversal.reversal_of_id == e2.id
    # Every debit/credit swapped: Cr A 20 / Dr B 20.
    assert rev_a is not None and rev_a.credit == Decimal("20") and rev_a.debit is None
    assert rev_b is not None and rev_b.debit == Decimal("20") and rev_b.credit is None

    original_after = await get_journal_entry(session, e2.id)
    orig_a = _line_for_account(original_after, acct_a_id)
    orig_b = _line_for_account(original_after, acct_b_id)
    # The ORIGINAL is untouched (immutability): still Dr A 20 / Cr B 20, no link.
    assert original_after.reversal_of_id is None
    assert orig_a is not None and orig_a.debit == Decimal("20")
    assert orig_b is not None and orig_b.credit == Decimal("20")

    listed = await list_journal_entries(session)
    listed_ids = {e.id for e in listed}
    assert e2.id in listed_ids and reversal.id in listed_ids  # both queryable
    # The reversal posted a real opposite leg: A's balance moved −20 (60 → 40).
    assert await derive_account_balance(session, acct_a_id) == Decimal("40")

    # -- (d) receipt auto-post: receive_line 4@5 → ONE balanced Dr 1130/Cr 2150 --
    inv_id = await _account_id_by_code(session, "1130")  # Inventory control (debit)
    grir_id = await _account_id_by_code(session, "2150")  # GR/IR control (credit)
    assert inv_id is not None and grir_id is not None

    grir_before = await derive_account_balance(session, grir_id)
    inv_before = await derive_account_balance(session, inv_id)

    vendor = await create_partner(
        session, PartnerCreate(name="SC1b GL Vendor", is_vendor=True)
    )
    item = await create_item(
        session, InventoryItemCreate(name="SC1b GL Widget", unit_of_measure="ea")
    )
    location = await create_location(session, StockLocationCreate(name="SC1b-GL"))
    po = await create_po(session, POCreate(vendor_id=vendor.id))
    line = await add_line(
        session,
        po.id,
        POLineCreate(item_id=item.id, qty_ordered=Decimal("10"), unit_cost=Decimal("5")),
    )
    await advance_po_status(session, po.id, "approved", ACTOR_ID)

    # Receive 4 @ 5 → expect an auto-posted JE for 4 * 5 == 20.
    expected_amount = Decimal("20.000000")
    await receive_line(session, po.id, line.id, location.id, Decimal("4"), ACTOR_ID)

    receipt_entries = await list_journal_entries(session, source_type="po_receipt")
    matches = [e for e in receipt_entries if e.source_id == line.id]
    # Exactly ONE JE source-linked to the PO line (source_type='po_receipt').
    assert len(matches) == 1
    receipt_je = matches[0]
    receipt_inv = _line_for_account(receipt_je, inv_id)
    receipt_grir = _line_for_account(receipt_je, grir_id)
    # BOTH legs: balanced Dr 1130 / Cr 2150 at qty×unit_cost == 20.000000
    # (the per-account invariant keeper — this is the SC2 red-on-revert target).
    assert receipt_inv is not None
    assert receipt_inv.debit == expected_amount and receipt_inv.credit is None
    assert receipt_grir is not None
    assert receipt_grir.credit == expected_amount and receipt_grir.debit is None

    grir_after = await derive_account_balance(session, grir_id)
    inv_after = await derive_account_balance(session, inv_id)
    # GR/IR (2150) moved −20 (credited); Inventory (1130) moved +20 (debited).
    assert (grir_after - grir_before) == Decimal("-20")
    assert (inv_after - inv_before) == Decimal("20")
