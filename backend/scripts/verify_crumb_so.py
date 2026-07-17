# ABOUTME: Standalone live-DB verification for the CRUMB sales-order + soft-reservation
# ABOUTME: engine (Phase 11b). Builds its OWN async engine from POSTGRES_* env (no conftest
# ABOUTME: fixtures) and drives the REAL crumb sales-order service — direct create, numeric-safe
# ABOUTME: SO-#### numbering, draft-only line edits, the order-status FSM, accepted-quote →
# ABOUTME: sales-order conversion, and THE CRUX — soft-reservation math + concurrent-confirm
# ABOUTME: contention that cannot over-reserve; exits non-zero on FAIL and self-cleans.
"""
Standalone live-DB verification script for the CRUMB sales-order engine (Phase 11b).

WHY THIS EXISTS (CRUMB-01 / soft-reservation crux, D-V3-11 / D-V3-16 / AC3..AC6):
  Phase 11b layers sales orders over the 11a CRM pipeline. A sales order is a
  header (SO-#### number, partner, optional source quote / opportunity, status,
  dates) plus ordered lines; a line orders either a SYERP stock item (`item_id`)
  or a non-stock free-text item (`item_id` NULL, D-V3-16). Line edits are Draft-
  only (409 otherwise); the status walks the controlled
  draft → confirmed → fulfilling → closed FSM, with cancel allowed only from
  draft/confirmed (an illegal move is 422). An accepted quote converts into a
  Draft sales order, copying the priced lines, resolving each line's `item_id`
  from its PLUM part via the advisory InventoryItem link, and stamping both
  source ids for traceability.

  THE LOAD-BEARING CRUX is the soft-reservation: confirming a Draft SO reserves
  `qty_reserved = min(qty_ordered, available)` per line, where
  `available = on_hand − Σ qty_reserved across OTHER open (confirmed/fulfilling)
  SOs for that item`; a shortage (`qty_ordered − qty_reserved`) never blocks and
  a non-stock line reserves 0; cancelling a Confirmed SO releases its reservation
  back into availability. confirm_sales_order locks the contended InventoryItem
  rows FOR UPDATE BEFORE reading availability, so two concurrent confirms
  competing for the same scarce item can never jointly over-reserve. None of that
  can be proven by the pure unit tests, and the backend live-DB pytest harness is
  broken (D-P7-4), so DB-dependent tests skip under plain ``pytest``. Verifiable
  truth must therefore come from a STANDALONE run against LIVE Postgres. This
  script stands up its own async engine + sessionmaker from the ``POSTGRES_*``
  environment variables — it deliberately does NOT import the broken test conftest
  fixtures — and drives the REAL crumb service functions end-to-end.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_so.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) DIRECT CREATE + NUMERIC-SAFE SO-#### (CRUMB-01 / D-P8-6): create_sales_order
      opens a Draft SO carrying an SO-#### number, its ordered lines, and the
      derived total_value; the pure helper crosses the digit boundary
      (SO-0009 → SO-0010); the DB generator returns the true numeric MAX+1
      (independent Python oracle) and SURVIVES a non-SO-[0-9]+ junk row — never
      lexicographic.
  (B) DRAFT-ONLY LINE EDIT (D-V3): add/update/delete a line on a Draft SO succeed;
      once the SO is Confirmed the same three editors are rejected 409.
  (C) STATUS FSM (CRUMB-01): the valid walk draft → confirmed → fulfilling → closed
      succeeds; an invalid target (draft → fulfilling skip, fulfilling → cancelled,
      off the terminal closed) is rejected 422.
  (D) QUOTE → SALES ORDER CONVERSION (AC3/AC6/D-V3-16): converting a NON-accepted
      quote is rejected 422; converting an accepted quote copies each line exactly
      (qty_ordered from the quote line quantity, unit_price verbatim), resolves the
      stock line's item_id from its plum_part_id via the InventoryItem link, leaves
      a part-less line non-stock (item_id NULL), and stamps BOTH source_quote_id
      and source_opportunity_id.
  (E) RESERVATION MATH (D-V3-11, THE CRUX): confirming reserves
      min(qty_ordered, available) with available = on_hand − Σ other-open
      reservations; an over-ordered line still confirms with a positive shortage; a
      non-stock line reserves 0; cancelling a Confirmed SO releases its reservation
      so availability frees back for the next confirm.
  (F) CONCURRENCY (D-V3-11, THE CRUX): two concurrent confirms (each in its OWN
      session) competing for one scarce item, each ordering more than half the
      on-hand, cannot over-reserve — the FOR UPDATE lock serializes them so the
      combined qty_reserved equals the on-hand EXACTLY (never more), neither goes
      negative, and no confirm errors. Repeated over several iterations.

The script uses uniquely-suffixed throwaway partners / PLUM parts / SYERP items /
opportunities / quotes / sales orders and CLEANS UP after itself (SO lines -> sales
orders -> quote lines -> quotes -> opportunities -> inventory txns -> items ->
revisions -> parts -> partners) in a finally block, so it is safe to re-run against
the same database. The seeded "Main" stock location is reused and left in place
(real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_crumb_so.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the crumb_* FKs reference syerp_* and plum_* tables that must be registered
# before the FKs resolve — the Task-8 lesson from MOUSSE).
import app.core.models  # noqa: F401
from app.modules.crumb.models import (
    Opportunity,
    Quote,
    QuoteLine,
    SalesOrder,
    SalesOrderLine,
)
from app.modules.crumb.schemas import (
    OpportunityCreate,
    QuoteCreate,
    QuoteLineCreate,
    QuoteToSalesOrderRequest,
    SalesOrderCreate,
    SalesOrderLineCreate,
)
from app.modules.crumb.service import (
    advance_quote_status,
    advance_sales_order_status,
    cancel_sales_order,
    confirm_sales_order,
    convert_quote_to_sales_order,
    create_opportunity,
    create_quote,
    create_sales_order,
    get_sales_order_detail,
    list_sales_orders,
)
from app.modules.crumb.service.sales_orders import (
    _next_sales_order_number,
    add_line as so_add_line,
    delete_line as so_delete_line,
    generate_sales_order_number,
    update_line as so_update_line,
)
from app.modules.plum.models import PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    InventoryItem,
    InventoryTxn,
    Partner,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0

_NUMERIC_SO = re.compile(r"^SO-[0-9]+$")


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
# Fixture builders — SYERP customer / PLUM part / linked InventoryItem
# ---------------------------------------------------------------------------


async def _make_customer(session_factory, unique: str, tag: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    async with session_factory() as session:
        partner = await create_partner(
            session,
            PartnerCreate(name=f"VERIFY-CRUMB-SO {tag} {unique}", is_customer=True),
        )
        return partner.id


async def _make_part(session_factory, part_number: str) -> str:
    """
    Insert a PLUM part + a Released revision directly via the ORM; return part_id.

    Direct ORM inserts keep the fixture fully controllable rather than driving the
    whole PLUM FSM (mirrors verify_crumb._make_part).
    """
    async with session_factory() as session:
        part = PlumPart(id=str(uuid.uuid4()), part_number=part_number, active=True)
        session.add(part)
        await session.flush()
        rev = PlumPartRevision(
            id=str(uuid.uuid4()),
            part_id=part.id,
            revision_number=1,
            revision_label="A",
            status="released",
            description=f"verify_crumb_so {part_number}",
            unit_of_measure="ea",
            released_at=datetime.now(timezone.utc),
        )
        session.add(rev)
        await session.commit()
        return part.id


async def _link_item(session_factory, unique: str, tag: str, part_id: str | None) -> str:
    """Create a SYERP InventoryItem (optionally linked to a PLUM part); return its id."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-CRUMB-SO {tag} {unique}",
                unit_of_measure="ea",
                plum_part_id=part_id,
            ),
        )
        return item.id


async def _max_so_suffix(session_factory) -> int:
    """True numeric MAX over ^SO-[0-9]+$ rows, computed in Python (oracle)."""
    async with session_factory() as session:
        rows = (await session.execute(select(SalesOrder.so_number))).scalars().all()
    suffixes = [int(n.split("-", 1)[1]) for n in rows if _NUMERIC_SO.match(n)]
    return max(suffixes) if suffixes else 0


async def _item_reserved_total(session_factory, item_id: str) -> Decimal:
    """Σ qty_reserved across OPEN (confirmed/fulfilling) SO lines for an item (oracle)."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(SalesOrderLine.qty_reserved), 0))
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .where(
                SalesOrderLine.item_id == item_id,
                SalesOrder.status.in_(("confirmed", "fulfilling")),
            )
        )
    return Decimal(result.scalar() or 0)


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    partner_ids: set[str] = set()
    part_ids: set[str] = set()
    item_ids: set[str] = set()
    opp_ids: set[str] = set()
    quote_ids: set[str] = set()
    so_ids: set[str] = set()

    def _pn(*parts: object) -> str:
        # Non-numeric part numbers never disturb PLUM auto-numbering (P##### series).
        return f"P-SO-{unique}-" + "-".join(str(p) for p in parts)

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
        partner_ids.add(cust_id)

        # ===================================================================
        # (A) DIRECT CREATE + NUMERIC-SAFE SO-#### (CRUMB-01 / D-P8-6)
        # ===================================================================
        async with session_factory() as session:
            so_a = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            description="Direct non-stock line",
                            qty_ordered=Decimal("3"),
                            unit_price=Decimal("12.5"),
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_a.id)
        check(
            "(A/CRUMB-01) create_sales_order opens a Draft SO with an SO-#### number, "
            "its ordered line, and total_value == qty*price (3 * 12.5 == 37.5)",
            so_a.status == "draft"
            and bool(_NUMERIC_SO.match(so_a.so_number))
            and len(so_a.lines) == 1
            and so_a.lines[0].line_total == Decimal("37.5")
            and so_a.total_value == Decimal("37.5"),
            f"status={so_a.status!r} number={so_a.so_number!r} "
            f"lines={len(so_a.lines)} total={so_a.total_value!r}",
        )

        # list_sales_orders returns our new order.
        async with session_factory() as session:
            listed = await list_sales_orders(session)
        check(
            "(A/CRUMB-01) list_sales_orders includes the freshly-created SO",
            any(s.id == so_a.id for s in listed),
            f"count={len(listed)}",
        )

        # Pure-helper digit boundary — the exact SO-0009 → SO-0010 crossing + seed.
        check(
            "(A/D-P8-6) the pure generator crosses the digit boundary "
            "(_next_sales_order_number(9) == 'SO-0010') and seeds 'SO-0001'",
            _next_sales_order_number(9) == "SO-0010"
            and _next_sales_order_number(None) == "SO-0001",
            f"boundary={_next_sales_order_number(9)!r} seed={_next_sales_order_number(None)!r}",
        )

        # DB generator: seed a non-SO-[0-9]+ junk row + a numeric pair whose suffix is
        # far above any real number, then prove the generator ignores the junk and
        # returns the true numeric MAX+1 (independent Python oracle) — never lexicographic.
        base = 900000 + int(unique[:4], 16) % 1000
        junk_number = f"SO-X{unique}"  # leading letter → never matches ^SO-[0-9]+$
        num_low = f"SO-{base:04d}"
        num_high = f"SO-{base + 1:04d}"
        async with session_factory() as session:
            for n in (junk_number, num_low, num_high):
                so = SalesOrder(
                    so_number=n,
                    partner_id=cust_id,
                    status="draft",
                    order_date=date.today(),
                    actor_id=actor_id,
                )
                session.add(so)
                await session.flush()
                so_ids.add(so.id)
            await session.commit()

        expected_suffix = await _max_so_suffix(session_factory)
        try:
            async with session_factory() as session:
                generated = await generate_sales_order_number(session)
            survived = True
        except Exception as exc:  # noqa: BLE001 - a raise here IS the D-P8-6 regression
            generated = None
            survived = False
            check(
                "(A/D-P8-6) generate_sales_order_number survives a non-SO-[0-9]+ junk row",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )
        if survived:
            check(
                "(A/D-P8-6) generate_sales_order_number survives a non-SO-[0-9]+ junk row "
                "and returns the true numeric MAX+1 (independent oracle), not lexicographic",
                generated is not None
                and bool(_NUMERIC_SO.match(generated))
                and int(generated.split("-", 1)[1]) == expected_suffix + 1,
                f"generated={generated!r} expected_suffix={expected_suffix + 1}",
            )

        # ===================================================================
        # (B) DRAFT-ONLY LINE EDIT + 409 once Confirmed (D-V3)
        # ===================================================================
        async with session_factory() as session:
            so_b = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            description="Editable line",
                            qty_ordered=Decimal("1"),
                            unit_price=Decimal("10"),
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_b.id)

        # add / update / delete a line while Draft — all succeed.
        async with session_factory() as session:
            added = await so_add_line(
                session,
                so_b.id,
                SalesOrderLineCreate(
                    description="Added line", qty_ordered=Decimal("2"), unit_price=Decimal("5")
                ),
                actor_id,
            )
        async with session_factory() as session:
            updated = await so_update_line(
                session,
                so_b.id,
                added.id,
                SalesOrderLineCreate(
                    description="Updated line", qty_ordered=Decimal("4"), unit_price=Decimal("6")
                ),
                actor_id,
            )
        async with session_factory() as session:
            await so_delete_line(session, so_b.id, added.id, actor_id)
        async with session_factory() as session:
            b_detail = await get_sales_order_detail(session, so_b.id)
        check(
            "(B/D-V3) add/update/delete line on a Draft SO succeed "
            "(update applied qty 4, delete left 1 line)",
            updated.qty_ordered == Decimal("4") and len(b_detail.lines) == 1,
            f"updated_qty={updated.qty_ordered!r} remaining_lines={len(b_detail.lines)}",
        )

        # Confirm (non-stock line reserves 0, no inventory needed), then the three
        # editors are rejected 409.
        async with session_factory() as session:
            await confirm_sales_order(session, so_b.id, actor_id)
        b_line_id = b_detail.lines[0].id
        for label, coro_factory in (
            ("add_line", lambda s: so_add_line(
                s, so_b.id,
                SalesOrderLineCreate(description="x", qty_ordered=Decimal("1"), unit_price=Decimal("1")),
                actor_id,
            )),
            ("update_line", lambda s: so_update_line(
                s, so_b.id, b_line_id,
                SalesOrderLineCreate(description="x", qty_ordered=Decimal("1"), unit_price=Decimal("1")),
                actor_id,
            )),
            ("delete_line", lambda s: so_delete_line(s, so_b.id, b_line_id, actor_id)),
        ):
            try:
                async with session_factory() as session:
                    await coro_factory(session)
                check(f"(B/D-V3) {label} on a Confirmed SO is rejected", False,
                      "editor succeeded on a confirmed order")
            except HTTPException as exc:
                check(
                    f"(B/D-V3) {label} on a Confirmed SO is rejected 409",
                    exc.status_code == 409,
                    f"status={exc.status_code}",
                )

        # ===================================================================
        # (C) STATUS FSM (draft → confirmed → fulfilling → closed) + invalid 422
        # ===================================================================
        async with session_factory() as session:
            so_c = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            description="FSM line", qty_ordered=Decimal("1"), unit_price=Decimal("1")
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_c.id)

        # invalid skip: draft → fulfilling (not an allowed successor) → 422.
        try:
            async with session_factory() as session:
                await advance_sales_order_status(session, so_c.id, "fulfilling", actor_id)
            check("(C) a draft → fulfilling skip is rejected", False, "transition succeeded")
        except HTTPException as exc:
            check(
                "(C/CRUMB-01) a draft → fulfilling skip is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        async with session_factory() as session:
            c1 = await advance_sales_order_status(session, so_c.id, "confirmed", actor_id)
        async with session_factory() as session:
            c2 = await advance_sales_order_status(session, so_c.id, "fulfilling", actor_id)
        async with session_factory() as session:
            c3 = await advance_sales_order_status(session, so_c.id, "closed", actor_id)
        check(
            "(C/CRUMB-01) the valid walk draft → confirmed → fulfilling → closed succeeds",
            c1.status == "confirmed" and c2.status == "fulfilling" and c3.status == "closed",
            f"statuses={c1.status!r}/{c2.status!r}/{c3.status!r}",
        )

        # off the terminal closed → 422.
        try:
            async with session_factory() as session:
                await advance_sales_order_status(session, so_c.id, "fulfilling", actor_id)
            check("(C) a transition off the terminal 'closed' is rejected", False,
                  "transition succeeded")
        except HTTPException as exc:
            check(
                "(C/CRUMB-01) a transition off the terminal 'closed' is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # fulfilling → cancelled is forbidden (AC4). Reach fulfilling on a fresh SO.
        async with session_factory() as session:
            so_c2 = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            description="No-cancel line", qty_ordered=Decimal("1"),
                            unit_price=Decimal("1"),
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_c2.id)
        async with session_factory() as session:
            await advance_sales_order_status(session, so_c2.id, "confirmed", actor_id)
        async with session_factory() as session:
            await advance_sales_order_status(session, so_c2.id, "fulfilling", actor_id)
        try:
            async with session_factory() as session:
                await advance_sales_order_status(session, so_c2.id, "cancelled", actor_id)
            check("(C/AC4) fulfilling → cancelled is rejected", False, "cancel succeeded")
        except HTTPException as exc:
            check(
                "(C/AC4) fulfilling → cancelled is rejected 422 "
                "(cancel allowed only from draft/confirmed)",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # ===================================================================
        # (D) QUOTE → SALES ORDER CONVERSION (AC3 / AC6 / D-V3-16)
        # ===================================================================
        # A PLUM part linked to a stock item (item_id resolves) and an opportunity to
        # prove source_opportunity_id is stamped through the quote's opportunity link.
        part_conv = await _make_part(session_factory, _pn("D", "stock"))
        part_ids.add(part_conv)
        item_conv = await _link_item(session_factory, unique, "D-STOCK", part_conv)
        item_ids.add(item_conv)

        async with session_factory() as session:
            opp_d = await create_opportunity(
                session,
                OpportunityCreate(name=f"Opp-conv {unique}", partner_id=cust_id),
                actor_id,
            )
        opp_ids.add(opp_d.id)

        # Non-accepted (draft) quote → convert is rejected 422.
        async with session_factory() as session:
            q_draft = await create_quote(
                session,
                QuoteCreate(
                    partner_id=cust_id,
                    opportunity_id=opp_d.id,
                    lines=[
                        QuoteLineCreate(
                            plum_part_id=part_conv, quantity=Decimal("4"),
                            unit_price=Decimal("25"),
                        )
                    ],
                ),
                actor_id,
            )
        quote_ids.add(q_draft.id)
        try:
            async with session_factory() as session:
                await convert_quote_to_sales_order(
                    session, q_draft.id, QuoteToSalesOrderRequest(), actor_id
                )
            check("(D/AC3) converting a non-accepted quote is rejected", False,
                  "conversion succeeded on a draft quote")
        except HTTPException as exc:
            check(
                "(D/AC3) converting a NON-accepted (draft) quote is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # Build an ACCEPTED quote (draft → sent → accepted) with a stock-part line and
        # a part-less free-text line, linked to the opportunity.
        async with session_factory() as session:
            q_acc = await create_quote(
                session,
                QuoteCreate(
                    partner_id=cust_id,
                    opportunity_id=opp_d.id,
                    lines=[
                        # stock line: part_conv is linked to item_conv → item_id resolves
                        QuoteLineCreate(
                            plum_part_id=part_conv, quantity=Decimal("4"),
                            unit_price=Decimal("25"),
                        ),
                        # part-less free-text line → non-stock (item_id NULL, D-V3-16)
                        QuoteLineCreate(
                            description="Rush handling", quantity=Decimal("2"),
                            unit_price=Decimal("15"),
                        ),
                    ],
                ),
                actor_id,
            )
        quote_ids.add(q_acc.id)
        async with session_factory() as session:
            await advance_quote_status(session, q_acc.id, "sent", actor_id)
        async with session_factory() as session:
            await advance_quote_status(session, q_acc.id, "accepted", actor_id)

        async with session_factory() as session:
            converted = await convert_quote_to_sales_order(
                session, q_acc.id, QuoteToSalesOrderRequest(), actor_id
            )
        so_ids.add(converted.id)
        conv_lines = sorted(converted.lines, key=lambda ln: ln.sort_order)
        stock_line = conv_lines[0]
        freetext_line = conv_lines[1]
        check(
            "(D/AC6) conversion stamps BOTH source_quote_id and source_opportunity_id",
            converted.source_quote_id == q_acc.id
            and converted.source_opportunity_id == opp_d.id,
            f"source_quote={converted.source_quote_id!r} "
            f"source_opp={converted.source_opportunity_id!r}",
        )
        check(
            "(D/AC3) the stock line copies exactly (qty_ordered 4 from the quote "
            "quantity, unit_price 25 verbatim) and resolves item_id from plum_part_id",
            stock_line.qty_ordered == Decimal("4")
            and stock_line.unit_price == Decimal("25")
            and stock_line.plum_part_id == part_conv
            and stock_line.item_id == item_conv,
            f"qty={stock_line.qty_ordered!r} price={stock_line.unit_price!r} "
            f"item_id={stock_line.item_id!r}",
        )
        check(
            "(D/D-V3-16) the part-less line copies exactly (qty 2, price 15) and is "
            "non-stock (item_id NULL)",
            freetext_line.qty_ordered == Decimal("2")
            and freetext_line.unit_price == Decimal("15")
            and freetext_line.item_id is None
            and freetext_line.plum_part_id is None,
            f"qty={freetext_line.qty_ordered!r} price={freetext_line.unit_price!r} "
            f"item_id={freetext_line.item_id!r}",
        )

        # ===================================================================
        # (E) RESERVATION MATH (D-V3-11, THE CRUX)
        # ===================================================================
        # One scarce item, on-hand 10. Three SOs contend for it in sequence.
        part_e = await _make_part(session_factory, _pn("E", "stock"))
        part_ids.add(part_e)
        item_e = await _link_item(session_factory, unique, "E-STOCK", part_e)
        item_ids.add(item_e)
        async with session_factory() as session:
            await post_receipt(session, item_e, main_id, Decimal("10"), Decimal("4"), actor_id)

        # SO_E1: qty 6 → available 10 → reserved 6 (full, no shortage).
        async with session_factory() as session:
            so_e1 = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            item_id=item_e, qty_ordered=Decimal("6"), unit_price=Decimal("20")
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_e1.id)
        async with session_factory() as session:
            e1 = await confirm_sales_order(session, so_e1.id, actor_id)
        check(
            "(E/D-V3-11) confirming SO_E1 (qty 6, available 10) reserves 6 with zero "
            "shortage (min(qty, available), no cap engaged)",
            e1.lines[0].qty_reserved == Decimal("6") and e1.lines[0].shortage == Decimal("0"),
            f"reserved={e1.lines[0].qty_reserved!r} shortage={e1.lines[0].shortage!r}",
        )

        # SO_E2: stock qty 8 + non-stock qty 3 → available now 10-6=4 → stock reserved 4
        # (cap engaged), shortage 4; the non-stock line reserves 0.
        async with session_factory() as session:
            so_e2 = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            item_id=item_e, qty_ordered=Decimal("8"), unit_price=Decimal("20")
                        ),
                        SalesOrderLineCreate(
                            description="Non-stock service", qty_ordered=Decimal("3"),
                            unit_price=Decimal("9"),
                        ),
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_e2.id)
        async with session_factory() as session:
            e2 = await confirm_sales_order(session, so_e2.id, actor_id)
        e2_lines = sorted(e2.lines, key=lambda ln: ln.sort_order)
        check(
            "(E/D-V3-11) confirming SO_E2 caps the stock line at available 4 "
            "(min(8, 4)) with a positive shortage 4 — the over-order still confirms",
            e2.status == "confirmed"
            and e2_lines[0].qty_reserved == Decimal("4")
            and e2_lines[0].shortage == Decimal("4"),
            f"status={e2.status!r} reserved={e2_lines[0].qty_reserved!r} "
            f"shortage={e2_lines[0].shortage!r}",
        )
        check(
            "(E/D-V3-16) the non-stock line reserves 0 (nothing to reserve)",
            e2_lines[1].qty_reserved == Decimal("0"),
            f"reserved={e2_lines[1].qty_reserved!r}",
        )

        # available == on_hand − Σ open reservations: 10 − (6 + 4) == 0 (fully reserved).
        reserved_now = await _item_reserved_total(session_factory, item_e)
        check(
            "(E/D-V3-11) available == on_hand − Σ open reservations "
            "(10 − (6+4) == 0, item fully reserved)",
            reserved_now == Decimal("10") and (Decimal("10") - reserved_now) == Decimal("0"),
            f"reserved_total={reserved_now!r} available={(Decimal('10') - reserved_now)!r}",
        )

        # Cancel SO_E1 → releases its 6 back into availability.
        async with session_factory() as session:
            e1_cancelled = await cancel_sales_order(session, so_e1.id, actor_id)
        reserved_after_cancel = await _item_reserved_total(session_factory, item_e)
        check(
            "(E/D-V3-11) cancelling Confirmed SO_E1 zeroes its reservation and releases "
            "it (Σ open reservations 10 → 4, available frees back to 6)",
            e1_cancelled.status == "cancelled"
            and all(ln.qty_reserved == Decimal("0") for ln in e1_cancelled.lines)
            and reserved_after_cancel == Decimal("4"),
            f"status={e1_cancelled.status!r} reserved_total={reserved_after_cancel!r}",
        )

        # SO_E3: qty 5 → available now 10-4=6 → reserved 5 (proves the release freed
        # capacity; without it available would be 0 and this would reserve 0).
        async with session_factory() as session:
            so_e3 = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            item_id=item_e, qty_ordered=Decimal("5"), unit_price=Decimal("20")
                        )
                    ],
                ),
                actor_id,
            )
        so_ids.add(so_e3.id)
        async with session_factory() as session:
            e3 = await confirm_sales_order(session, so_e3.id, actor_id)
        check(
            "(E/D-V3-11 CRUX) after the release, confirming SO_E3 (qty 5, available "
            "10−4==6) reserves 5 — the freed capacity is genuinely available again",
            e3.lines[0].qty_reserved == Decimal("5"),
            f"reserved={e3.lines[0].qty_reserved!r}",
        )

        # ===================================================================
        # (F) CONCURRENCY (D-V3-11, THE CRUX) — two concurrent confirms, no over-reserve
        # ===================================================================
        await run_concurrency(
            session_factory, unique, actor_id, main_id, cust_id, part_ids, item_ids, so_ids
        )

    finally:
        await _cleanup(
            session_factory, partner_ids, part_ids, item_ids, opp_ids, quote_ids, so_ids
        )
        await engine.dispose()


# ---------------------------------------------------------------------------
# (F) Concurrency scenario (D-V3-11) — the FOR UPDATE lock is what makes this hold
# ---------------------------------------------------------------------------
#
# confirm_sales_order locks the contended InventoryItem row `SELECT ... FOR UPDATE`
# BEFORE reading availability, so two concurrent confirms against the same scarce
# item serialize: the first reserves min(qty, on_hand), commits (releasing the
# lock), and the second then re-reads the now-depleted availability and reserves
# only what remains. Removing that FOR UPDATE lets both read the original on_hand
# under READ COMMITTED and both reserve their full order — driving the combined
# qty_reserved ABOVE on_hand (an over-reservation) — i.e. this scenario FAILS. A
# sequential test cannot surface that race; only firing both with asyncio.gather on
# TWO INDEPENDENT sessions can. Repeated over several iterations for confidence.


async def run_concurrency(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    cust_id: str,
    part_ids: set[str],
    item_ids: set[str],
    so_ids: set[str],
) -> None:
    """
    For each iteration: a fresh scarce item (on-hand 10) and two fresh Draft SOs
    each ordering 7 (> half). Fire both confirms concurrently on INDEPENDENT
    sessions and prove the combined qty_reserved is EXACTLY the on-hand (10) —
    never more (no over-reserve), never negative. Reuses the caller's already-
    registered customer so every throwaway row is swept by the caller's cleanup.
    """
    on_hand = Decimal("10")
    order_qty = Decimal("7")  # > half of on_hand, so two full orders would over-reserve
    iterations = 5

    all_ok = True
    detail = ""
    for i in range(iterations):
        part_f = await _make_part(session_factory, f"P-SO-{unique}-F{i}")
        part_ids.add(part_f)
        item_f = await _link_item(session_factory, unique, f"F{i}", part_f)
        item_ids.add(item_f)
        async with session_factory() as session:
            await post_receipt(session, item_f, main_id, on_hand, Decimal("4"), actor_id)

        so_pair = []
        for _k in range(2):
            async with session_factory() as session:
                so = await create_sales_order(
                    session,
                    SalesOrderCreate(
                        partner_id=cust_id,
                        lines=[
                            SalesOrderLineCreate(
                                item_id=item_f, qty_ordered=order_qty, unit_price=Decimal("20")
                            )
                        ],
                    ),
                    actor_id,
                )
            so_pair.append(so.id)
            so_ids.add(so.id)

        # Barrier makes the race deterministic: each worker owns an INDEPENDENT
        # session, pre-warms its connection, then both enter confirm together.
        barrier = asyncio.Barrier(2)

        async def _confirm_once(so_id: str):
            from sqlalchemy import text

            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await confirm_sales_order(session, so_id, actor_id)

        results = await asyncio.gather(
            _confirm_once(so_pair[0]),
            _confirm_once(so_pair[1]),
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            all_ok = False
            detail = f"iter {i}: confirm raised {[type(e).__name__ for e in errors]}"
            break

        combined = await _item_reserved_total(session_factory, item_f)
        # Each line's own reservation must be within [0, order_qty].
        per_line = [r.lines[0].qty_reserved for r in results]
        if any(q < Decimal("0") or q > order_qty for q in per_line):
            all_ok = False
            detail = f"iter {i}: per-line reservation out of range {per_line}"
            break
        if combined != on_hand:
            all_ok = False
            detail = (
                f"iter {i}: combined qty_reserved {combined} != on_hand {on_hand} "
                f"(per-line {per_line})"
            )
            break

    check(
        "(F/D-V3-11 CRUX) two concurrent confirms (each own session) for one scarce "
        f"item (on-hand 10, each ordering 7) never over-reserve — combined qty_reserved "
        f"== 10 EXACTLY across {iterations} iterations, never negative, no confirm errors",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    partner_ids: set[str],
    part_ids: set[str],
    item_ids: set[str],
    opp_ids: set[str],
    quote_ids: set[str],
    so_ids: set[str],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: SO lines -> sales orders (they FK
    into quotes/opportunities via source_*) -> quote lines -> quotes (FK into
    opportunities) -> opportunities -> inventory txns -> inventory items (FK into
    plum parts) -> revisions -> parts -> partners. The seeded "Main" location is
    reused and left in place (real deploy state).
    """
    async with session_factory() as session:
        so_list = list(so_ids)
        q_list = list(quote_ids)
        o_list = list(opp_ids)
        item_list = list(item_ids)
        part_list = list(part_ids)
        pa_list = list(partner_ids)

        if so_list:
            await session.execute(
                delete(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(so_list))
            )
            await session.execute(delete(SalesOrder).where(SalesOrder.id.in_(so_list)))
        if q_list:
            await session.execute(delete(QuoteLine).where(QuoteLine.quote_id.in_(q_list)))
            await session.execute(delete(Quote).where(Quote.id.in_(q_list)))
        if o_list:
            await session.execute(delete(Opportunity).where(Opportunity.id.in_(o_list)))
        if item_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list))
            )
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_list))
            )
        if part_list:
            await session.execute(
                delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(part_list))
            )
            await session.execute(delete(PlumPart).where(PlumPart.id.in_(part_list)))
        if pa_list:
            await session.execute(delete(Partner).where(Partner.id.in_(pa_list)))

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
