# ABOUTME: Standalone live-DB verification for the SYERP GL posting engine (Phase 9a, SYERP-12).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives the
# ABOUTME: REAL GL service functions end-to-end, proving balanced posting, reversal immutability,
# ABOUTME: derived balances/register, and the receipt auto-post; exits non-zero on FAIL.
"""
Standalone live-DB verification script for the SYERP GL posting engine (Phase 9a).

WHY THIS EXISTS (the GL backend proof, D-P9a):
  The GL posting engine (post_journal_entry, reverse_journal_entry,
  derive_account_balance, get_account_register) enforces double-entry balance,
  append-only immutability (corrections are reversing entries, never edits), and
  DERIVED balances — and the Phase-8 receiving path now AUTO-POSTS a balanced
  Dr 1130 / Cr 2150 journal entry in the SAME atomic transaction as the stock
  receipt (SYERP-12 AC3). None of that can be proven by the pure unit tests
  (which only pin the helper predicates), and the backend live-DB pytest harness
  is broken (D-P7-4), so DB-dependent tests skip under plain ``pytest``.
  Verifiable truth must therefore come from a STANDALONE run against LIVE
  Postgres. This script stands up its own async engine + sessionmaker from the
  ``POSTGRES_*`` environment variables — it deliberately does NOT import the
  broken test conftest fixtures — and then calls the REAL service functions,
  proving the whole phase's backend behavior end-to-end rather than
  reimplementing it.

HOW TO RUN (the compose ``db`` service is not host-published):
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Run this script in a one-off container on the compose network so it can
  #    resolve host `db`:
  podman run --rm --network compose_default --env-file .env -e POSTGRES_HOST=db \
      -e PYTHONPATH=/app -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_gl.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (a) post_journal_entry on a balanced 2-line entry SUCCEEDS; an unbalanced entry
      RAISES HTTPException 422 and persists nothing.
  (b) reverse_journal_entry posts a NEW entry that swaps every debit/credit and
      links back via reversal_of_id; the ORIGINAL is untouched (immutability) and
      BOTH remain queryable via list_journal_entries.
  (c) derive_account_balance == Σdebit − Σcredit of the posted lines; the register
      over a date range carries a MONOTONIC running balance and the expected
      opening/closing.
  (d) receive_line (create vendor/item/location/PO/approve/receive) AUTO-POSTS a
      balanced JE Dr 1130 / Cr 2150 at qty×unit_cost, source-linked to the PO line,
      in the same transaction as the stock receipt; the GR/IR (2150) derived
      balance moved by exactly the receipt amount.
  (e) the seeded GR/IR control account (code 2150, LIABILITY) exists.
  (f) ATOMICITY (verify M3): forcing the GL auto-post to fail mid-receive rolls
      BOTH the stock txn AND the JE back — nothing persists, qty_received unchanged.
  (g) ZERO-COST receipt (verify M1): a unit_cost==0 line receives successfully,
      records the physical stock txn, and posts NO GL entry (all-zero JE skipped).
  (h) DOUBLE-REVERSAL guard (verify M2): reversing an already-reversed entry, or a
      reversal itself, is refused with 409; the derived balance stays intact.

Router-level concerns — the gl.journal_posted / gl.journal_reversed audit rows and
the syerp:read/write RBAC 403 path — are proven over live HTTP by the companion
scripts/verify_gl_api.py (this script drives the service layer directly and so
cannot exercise the router where write_audit and require_permission live).

The script uses uniquely-named throwaway data — two throwaway GL accounts, a
vendor, an item, a location, a PO — and CLEANS UP after itself (deletes its
journal lines/entries, PO lines, PO, inventory txns, item, location, vendor, and
throwaway accounts, respecting FK order) in a finally block, so it is safe to
re-run against the same database. The seeded 1130/2150 accounts and the "Main"
location are reused and left in place (real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (JournalLine.account_id FKs syerp_gl_account, PurchaseOrderLine.item_id FKs
# syerp_inventory_item — every table must be registered before the FKs resolve;
# the Task-8 lesson).
import app.core.models  # noqa: F401
import app.modules.syerp.service as gl_service
from app.modules.syerp.inventory_seed import seed_default_location
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLocation,
)
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


async def _account_id_by_code(session, code: str) -> int | None:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalars().first()


def _line_for_account(entry, account_id: int):
    """Return the nested JournalLineRead for the given account from an entry."""
    return next((ln for ln in entry.lines if ln.account_id == account_id), None)


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway GL accounts for the isolated posting/balance/register scenarios so
    # those assertions are deterministic (the seeded 1130/2150 carry other traffic).
    acct_a_id: int | None = None  # ASSET — debited by the series
    acct_b_id: int | None = None  # LIABILITY — credited by the series
    created_entry_ids: list[str] = []

    vendor_id: str | None = None
    item_id: str | None = None
    loc_id: int | None = None
    po_id: str | None = None
    line_id: str | None = None

    # Zero-cost receipt scenario (M1) uses its own item + PO so it does not perturb
    # the scenario-(d) moving-average/balance assertions.
    item0_id: str | None = None
    po0_id: str | None = None
    line0_id: str | None = None

    # Dates for the register series (in the past so the reversal, dated today,
    # falls OUTSIDE the register window and cannot perturb it).
    base = date.today() - timedelta(days=30)
    d1, d2, d3 = base, base + timedelta(days=10), base + timedelta(days=20)

    try:
        # -------------------------------------------------------------------
        # Setup: create two throwaway GL accounts (deterministic, isolated).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            acct_a = GLAccount(
                code=f"ZA{unique[:6]}",
                name=f"VERIFY Debit Acct {unique}",
                account_type="ASSET",
            )
            acct_b = GLAccount(
                code=f"ZB{unique[:6]}",
                name=f"VERIFY Credit Acct {unique}",
                account_type="LIABILITY",
            )
            session.add_all([acct_a, acct_b])
            await session.commit()
            acct_a_id, acct_b_id = acct_a.id, acct_b.id

        # -------------------------------------------------------------------
        # (a) Balanced post SUCCEEDS; unbalanced post RAISES 422 (no persist).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            e1 = await post_journal_entry(
                session,
                entry_date=d1,
                memo=f"VERIFY balanced {unique}",
                lines=[
                    {"account_id": acct_a_id, "debit": Decimal("10")},
                    {"account_id": acct_b_id, "credit": Decimal("10")},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e1.id)
        a_line = _line_for_account(e1, acct_a_id)
        b_line = _line_for_account(e1, acct_b_id)
        check(
            "post_journal_entry persisted a balanced 2-line entry (Dr A 10 / Cr B 10)",
            len(e1.lines) == 2
            and a_line is not None
            and a_line.debit == Decimal("10")
            and a_line.credit is None
            and b_line is not None
            and b_line.credit == Decimal("10")
            and b_line.debit is None,
            f"lines={[(ln.account_id, ln.debit, ln.credit) for ln in e1.lines]}",
        )

        unbalanced_rejected = False
        unbalanced_status = None
        async with session_factory() as session:
            try:
                await post_journal_entry(
                    session,
                    entry_date=d1,
                    memo=f"VERIFY unbalanced {unique}",
                    lines=[
                        {"account_id": acct_a_id, "debit": Decimal("10")},
                        {"account_id": acct_b_id, "credit": Decimal("5")},
                    ],
                    actor_id=actor_id,
                )
            except HTTPException as exc:
                unbalanced_rejected = True
                unbalanced_status = exc.status_code
        check(
            "unbalanced entry (Dr 10 / Cr 5) RAISES HTTPException 422",
            unbalanced_rejected and unbalanced_status == 422,
            f"rejected={unbalanced_rejected} status={unbalanced_status}",
        )
        async with session_factory() as session:
            after_reject = await list_journal_entries(session, source_type=None)
        reject_persisted = any(
            e.memo == f"VERIFY unbalanced {unique}" for e in after_reject
        )
        check(
            "the rejected unbalanced entry persisted NOTHING",
            not reject_persisted,
            "an unbalanced entry was written",
        )

        # -------------------------------------------------------------------
        # Post the rest of the register series (E2 @ d2, E3 @ d3).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            e2 = await post_journal_entry(
                session,
                entry_date=d2,
                memo=f"VERIFY series-2 {unique}",
                lines=[
                    {"account_id": acct_a_id, "debit": Decimal("20")},
                    {"account_id": acct_b_id, "credit": Decimal("20")},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e2.id)
        async with session_factory() as session:
            e3 = await post_journal_entry(
                session,
                entry_date=d3,
                memo=f"VERIFY series-3 {unique}",
                lines=[
                    {"account_id": acct_a_id, "debit": Decimal("30")},
                    {"account_id": acct_b_id, "credit": Decimal("30")},
                ],
                actor_id=actor_id,
            )
            created_entry_ids.append(e3.id)

        # -------------------------------------------------------------------
        # (c) Derived balance == Σdebit − Σcredit; register running balance is
        #     monotonic over the date range, with the expected opening/closing.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            bal_a = await derive_account_balance(session, acct_a_id)
            bal_b = await derive_account_balance(session, acct_b_id)
        check(
            "derive_account_balance(A) == Σdebit − Σcredit == 10+20+30 == 60",
            bal_a == Decimal("60"),
            f"got {bal_a!r}",
        )
        check(
            "derive_account_balance(B) == Σdebit − Σcredit == −60 (credited only)",
            bal_b == Decimal("-60"),
            f"got {bal_b!r}",
        )

        async with session_factory() as session:
            register = await get_account_register(
                session, acct_a_id, date_from=d1, date_to=d3
            )
        running = [row.running_balance for row in register.rows]
        monotonic = all(b > a for a, b in zip(running, running[1:]))
        check(
            "register over [d1,d3] has 3 rows with a strictly MONOTONIC running "
            "balance [10, 30, 60]",
            len(register.rows) == 3
            and running == [Decimal("10"), Decimal("30"), Decimal("60")]
            and monotonic,
            f"running={running!r}",
        )
        check(
            "register opening_balance == 0 (no postings before d1) and "
            "closing_balance == 60",
            register.opening_balance == Decimal("0")
            and register.closing_balance == Decimal("60"),
            f"opening={register.opening_balance!r} closing={register.closing_balance!r}",
        )

        # -------------------------------------------------------------------
        # (b) Reversal: NEW entry swaps every debit/credit and links back via
        #     reversal_of_id; the ORIGINAL is untouched; BOTH stay queryable.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            reversal = await reverse_journal_entry(session, e2.id, actor_id)
            created_entry_ids.append(reversal.id)
        rev_a = _line_for_account(reversal, acct_a_id)
        rev_b = _line_for_account(reversal, acct_b_id)
        check(
            "reverse_journal_entry posts a new entry with reversal_of_id == original.id",
            reversal.id != e2.id and reversal.reversal_of_id == e2.id,
            f"reversal_of_id={reversal.reversal_of_id!r} original={e2.id!r}",
        )
        check(
            "the reversing entry SWAPS every debit/credit (Cr A 20 / Dr B 20)",
            rev_a is not None
            and rev_a.credit == Decimal("20")
            and rev_a.debit is None
            and rev_b is not None
            and rev_b.debit == Decimal("20")
            and rev_b.credit is None,
            f"lines={[(ln.account_id, ln.debit, ln.credit) for ln in reversal.lines]}",
        )

        async with session_factory() as session:
            original_after = await get_journal_entry(session, e2.id)
        orig_a = _line_for_account(original_after, acct_a_id)
        orig_b = _line_for_account(original_after, acct_b_id)
        check(
            "the ORIGINAL entry is untouched after reversal (immutability): still "
            "Dr A 20 / Cr B 20, reversal_of_id is None",
            original_after.reversal_of_id is None
            and orig_a is not None
            and orig_a.debit == Decimal("20")
            and orig_b is not None
            and orig_b.credit == Decimal("20"),
            f"reversal_of_id={original_after.reversal_of_id!r} "
            f"lines={[(ln.account_id, ln.debit, ln.credit) for ln in original_after.lines]}",
        )

        async with session_factory() as session:
            listed = await list_journal_entries(session)
        listed_ids = {e.id for e in listed}
        check(
            "BOTH the original and its reversal remain queryable via list_journal_entries",
            e2.id in listed_ids and reversal.id in listed_ids,
            f"original_present={e2.id in listed_ids} reversal_present={reversal.id in listed_ids}",
        )

        async with session_factory() as session:
            bal_a_after_rev = await derive_account_balance(session, acct_a_id)
        check(
            "the reversal moved account A's derived balance by −20 (60 → 40), proving "
            "the reversing entry posts a real opposite leg",
            bal_a_after_rev == Decimal("40"),
            f"got {bal_a_after_rev!r}",
        )

        # -------------------------------------------------------------------
        # (e) The seeded GR/IR control account (2150, LIABILITY) exists.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            grir = (
                await session.execute(select(GLAccount).where(GLAccount.code == "2150"))
            ).scalars().first()
            inv_acct = (
                await session.execute(select(GLAccount).where(GLAccount.code == "1130"))
            ).scalars().first()
        check(
            "seeded GR/IR control account 2150 exists and is a LIABILITY",
            grir is not None and grir.account_type == "LIABILITY",
            f"grir={grir!r}",
        )
        check(
            "seeded Inventory control account 1130 exists (auto-post debit target)",
            inv_acct is not None,
            f"inv_acct={inv_acct!r}",
        )
        grir_id = grir.id if grir else None
        inv_id = inv_acct.id if inv_acct else None

        # -------------------------------------------------------------------
        # (d) receive_line AUTO-POSTS a balanced JE Dr 1130 / Cr 2150 at
        #     qty×unit_cost, source-linked to the PO line, in the SAME
        #     transaction as the stock receipt; the 2150 balance moved by the
        #     receipt amount.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            grir_before = await derive_account_balance(session, grir_id)
            inv_before = await derive_account_balance(session, inv_id)

        async with session_factory() as session:
            vendor = await create_partner(
                session, PartnerCreate(name=f"VERIFY GL Vendor {unique}", is_vendor=True)
            )
            vendor_id = vendor.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY GL Widget {unique}", unit_of_measure="ea"),
            )
            item_id = item.id
        async with session_factory() as session:
            location = await create_location(
                session, StockLocationCreate(name=f"VERIFY-GL-{unique}")
            )
            loc_id = location.id
        async with session_factory() as session:
            po = await create_po(session, POCreate(vendor_id=vendor_id))
            po_id = po.id
        async with session_factory() as session:
            line = await add_line(
                session,
                po_id,
                POLineCreate(
                    item_id=item_id, qty_ordered=Decimal("10"), unit_cost=Decimal("5")
                ),
            )
            line_id = line.id
        async with session_factory() as session:
            await advance_po_status(session, po_id, "approved", actor_id)

        # Receive 4 @ 5 → expect an auto-posted JE for 4 * 5 == 20.
        expected_amount = Decimal("20.000000")
        async with session_factory() as session:
            await receive_line(session, po_id, line_id, loc_id, Decimal("4"), actor_id)

        async with session_factory() as session:
            receipt_entries = await list_journal_entries(session, source_type="po_receipt")
        receipt_je = next((e for e in receipt_entries if e.source_id == line_id), None)
        receipt_inv = _line_for_account(receipt_je, inv_id) if receipt_je else None
        receipt_grir = _line_for_account(receipt_je, grir_id) if receipt_je else None
        check(
            "receiving auto-posted exactly ONE JE source-linked to the PO line "
            "(source_type='po_receipt', source_id=line.id)",
            receipt_je is not None
            and sum(1 for e in receipt_entries if e.source_id == line_id) == 1,
            f"matches={sum(1 for e in receipt_entries if e.source_id == line_id)}",
        )
        check(
            "the receipt JE is a balanced Dr 1130 / Cr 2150 at qty×unit_cost == 20",
            receipt_inv is not None
            and receipt_inv.debit == expected_amount
            and receipt_inv.credit is None
            and receipt_grir is not None
            and receipt_grir.credit == expected_amount
            and receipt_grir.debit is None,
            f"inv={(receipt_inv.debit if receipt_inv else None)} "
            f"grir={(receipt_grir.credit if receipt_grir else None)}",
        )

        async with session_factory() as session:
            grir_after = await derive_account_balance(session, grir_id)
            inv_after = await derive_account_balance(session, inv_id)
        check(
            "GR/IR (2150) derived balance moved by −20 (credited by the receipt)",
            (grir_after - grir_before) == Decimal("-20"),
            f"before={grir_before!r} after={grir_after!r} delta={grir_after - grir_before!r}",
        )
        check(
            "Inventory (1130) derived balance moved by +20 (debited by the receipt)",
            (inv_after - inv_before) == Decimal("20"),
            f"before={inv_before!r} after={inv_after!r} delta={inv_after - inv_before!r}",
        )

        # -------------------------------------------------------------------
        # (f) ATOMICITY ROLLBACK (M2/verify M3): force the GL auto-post to FAIL
        #     mid-receive and assert that NEITHER the stock receipt NOR the JE
        #     persists — the negative half of scenario (d), the phase's highest
        #     risk (a split unit of work leaving a receipt with no JE). We
        #     monkeypatch _gl_account_id_by_code (a module global receive_line
        #     resolves at call time) to raise when resolving 2150 — AFTER
        #     post_receipt has already flushed the stock txn — so the raise must
        #     roll the whole transaction back.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            txns_before = (
                await session.execute(
                    select(InventoryTxn.id).where(InventoryTxn.item_id == item_id)
                )
            ).scalars().all()
            jes_before = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "po_receipt",
                        JournalEntry.source_id == line_id,
                    )
                )
            ).scalars().all()

        # receive_line resolves _gl_account_id_by_code from the purchasing submodule's
        # globals (post-service-split, chore-syerp-service-split), so patch it there —
        # patching the package attribute would not affect the name receive_line calls.
        _po_mod = gl_service.purchasing
        _real_lookup = _po_mod._gl_account_id_by_code

        async def _boom_on_grir(db, code):
            if code == "2150":
                raise HTTPException(status_code=500, detail="forced GR/IR failure (verify M3)")
            return await _real_lookup(db, code)

        _po_mod._gl_account_id_by_code = _boom_on_grir
        rollback_raised = False
        try:
            async with session_factory() as session:
                # line still has 6 of 10 outstanding (received 4 in (d)); receive 3.
                await receive_line(session, po_id, line_id, loc_id, Decimal("3"), actor_id)
        except HTTPException:
            rollback_raised = True
        finally:
            _po_mod._gl_account_id_by_code = _real_lookup

        async with session_factory() as session:
            txns_after = (
                await session.execute(
                    select(InventoryTxn.id).where(InventoryTxn.item_id == item_id)
                )
            ).scalars().all()
            jes_after = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "po_receipt",
                        JournalEntry.source_id == line_id,
                    )
                )
            ).scalars().all()
            line_after = (
                await session.execute(
                    select(PurchaseOrderLine).where(PurchaseOrderLine.id == line_id)
                )
            ).scalars().first()

        check(
            "forcing the GL auto-post to fail RAISES out of receive_line (no swallow)",
            rollback_raised,
            "receive_line did not raise when the JE post failed",
        )
        check(
            "atomic rollback: NO new inventory txn persisted for the failed receipt "
            "(the flushed stock receipt was rolled back with the failed JE)",
            len(txns_after) == len(txns_before),
            f"before={len(txns_before)} after={len(txns_after)}",
        )
        check(
            "atomic rollback: NO new journal entry persisted for the failed receipt",
            len(jes_after) == len(jes_before),
            f"before={len(jes_before)} after={len(jes_after)}",
        )
        check(
            "atomic rollback: the PO line's qty_received is UNCHANGED (still 4)",
            line_after is not None and line_after.qty_received == Decimal("4"),
            f"qty_received={line_after.qty_received if line_after else None!r}",
        )

        # -------------------------------------------------------------------
        # (g) ZERO-COST RECEIPT (verify M1): a unit_cost==0 line (samples,
        #     warranty/RMA replacements) is schema-legal and must still receive —
        #     the GL post is SKIPPED (an all-zero JE cannot balance) while the
        #     physical stock receipt is still recorded. Before the M1 fix this
        #     422'd and rolled back the whole receipt.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            item0 = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY GL Sample {unique}", unit_of_measure="ea"),
            )
            item0_id = item0.id
        async with session_factory() as session:
            po0 = await create_po(session, POCreate(vendor_id=vendor_id))
            po0_id = po0.id
        async with session_factory() as session:
            line0 = await add_line(
                session,
                po0_id,
                POLineCreate(
                    item_id=item0_id, qty_ordered=Decimal("5"), unit_cost=Decimal("0")
                ),
            )
            line0_id = line0.id
        async with session_factory() as session:
            await advance_po_status(session, po0_id, "approved", actor_id)

        zero_cost_ok = True
        zero_cost_err = ""
        try:
            async with session_factory() as session:
                await receive_line(session, po0_id, line0_id, loc_id, Decimal("2"), actor_id)
        except HTTPException as exc:
            zero_cost_ok = False
            zero_cost_err = f"{exc.status_code}: {exc.detail}"

        async with session_factory() as session:
            zero_txns = (
                await session.execute(
                    select(InventoryTxn).where(InventoryTxn.item_id == item0_id)
                )
            ).scalars().all()
            zero_jes = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "po_receipt",
                        JournalEntry.source_id == line0_id,
                    )
                )
            ).scalars().all()
        check(
            "a zero-cost PO line RECEIVES successfully (M1 regression — no 422)",
            zero_cost_ok,
            f"receive raised {zero_cost_err}",
        )
        check(
            "the zero-cost receipt still recorded the physical stock txn (qty 2)",
            len(zero_txns) == 1 and zero_txns[0].quantity == Decimal("2"),
            f"txns={[(t.quantity) for t in zero_txns]}",
        )
        check(
            "the zero-cost receipt posted NO GL journal entry (all-zero JE skipped)",
            len(zero_jes) == 0,
            f"unexpected JEs={zero_jes!r}",
        )

        # -------------------------------------------------------------------
        # (h) DOUBLE-REVERSAL GUARD (verify M2): an entry may be reversed at most
        #     once, and a reversal is not itself reversible — else the opposite
        #     swing applies twice and the derived control-account balance diverges
        #     from the inventory valuation it mirrors. e2 was already reversed in
        #     (b) by `reversal`; both re-reversal paths must 409.
        # -------------------------------------------------------------------
        rereverse_status = None
        async with session_factory() as session:
            try:
                await reverse_journal_entry(session, e2.id, actor_id)
            except HTTPException as exc:
                rereverse_status = exc.status_code
        check(
            "reversing an ALREADY-reversed entry is refused with 409",
            rereverse_status == 409,
            f"status={rereverse_status!r}",
        )

        reverse_of_reversal_status = None
        async with session_factory() as session:
            try:
                await reverse_journal_entry(session, reversal.id, actor_id)
            except HTTPException as exc:
                reverse_of_reversal_status = exc.status_code
        check(
            "reversing a REVERSAL entry is refused with 409",
            reverse_of_reversal_status == 409,
            f"status={reverse_of_reversal_status!r}",
        )
        async with session_factory() as session:
            bal_a_final = await derive_account_balance(session, acct_a_id)
        check(
            "the refused double-reversals left account A's balance intact at 40 "
            "(no phantom swing persisted)",
            bal_a_final == Decimal("40"),
            f"got {bal_a_final!r}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows in FK-safe order: journal lines → journal
        # entries (both my direct entries and the receipt auto-post) → PO lines →
        # PO → inventory txns → item → location → vendor → throwaway accounts.
        # The seeded 1130/2150 accounts and the "Main" location are left in place.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            # Idempotent: seed the default location too so re-runs against a fresh
            # DB still work (mirrors verify_purchasing.py).
            await seed_default_location(session)

            entry_ids = list(created_entry_ids)
            # The receipt auto-post JE is source-linked to the PO line, not tracked
            # in created_entry_ids — collect it (and any reversal chain) for both the
            # scenario-(d) line and the zero-cost line (which posts none, but stay
            # symmetric) to delete.
            source_line_ids = [lid for lid in (line_id, line0_id) if lid is not None]
            if source_line_ids:
                receipt_ids = (
                    await session.execute(
                        select(JournalEntry.id).where(
                            JournalEntry.source_type == "po_receipt",
                            JournalEntry.source_id.in_(source_line_ids),
                        )
                    )
                ).scalars().all()
                entry_ids.extend(receipt_ids)

            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )

            po_ids = [pid for pid in (po_id, po0_id) if pid is not None]
            if po_ids:
                await session.execute(
                    delete(PurchaseOrderLine).where(PurchaseOrderLine.po_id.in_(po_ids))
                )
                await session.execute(
                    delete(PurchaseOrder).where(PurchaseOrder.id.in_(po_ids))
                )
            item_ids = [iid for iid in (item_id, item0_id) if iid is not None]
            if item_ids:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_ids))
                )
                await session.execute(
                    delete(InventoryItem).where(InventoryItem.id.in_(item_ids))
                )
            if loc_id is not None:
                await session.execute(
                    delete(StockLocation).where(StockLocation.id == loc_id)
                )
            if vendor_id is not None:
                await session.execute(delete(Partner).where(Partner.id == vendor_id))

            # Throwaway GL accounts last (their lines are already deleted above).
            acct_ids = [aid for aid in (acct_a_id, acct_b_id) if aid is not None]
            if acct_ids:
                await session.execute(
                    delete(GLAccount).where(GLAccount.id.in_(acct_ids))
                )
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
