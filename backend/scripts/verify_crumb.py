# ABOUTME: Standalone live-DB verification for the CRUMB CRM pipeline (Phase 11a).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and
# ABOUTME: drives the REAL crumb service — lead→customer link/create, lead→opportunity
# ABOUTME: conversion, the opportunity-stage and quote-status FSMs, PLUM-derived line
# ABOUTME: pricing, numeric-safe QUOTE-#### numbering, quote-line/total integrity, and the
# ABOUTME: append-only interaction timeline; exits non-zero on FAIL and self-cleans.
"""
Standalone live-DB verification script for the CRUMB CRM pipeline (Phase 11a).

WHY THIS EXISTS (CRUMB-01 / SC2..SC5):
  CRUMB layers a CRM pipeline over the SYERP hub: a lead links-or-creates a SYERP
  customer and converts into an opportunity; an opportunity walks a controlled
  stage FSM (qualify → proposal → won | lost) and, once WON, spawns a draft quote;
  a quote prices PLUM-part or free-text lines (the PLUM released cost + a per-line
  editable markup) and walks its own status FSM (draft → sent → accepted | rejected
  | expired); interactions are an append-only per-customer timeline. None of the
  server-enforced invariants below can be proven by the pure unit tests, and the
  backend live-DB pytest harness is broken (D-P7-4), so DB-dependent tests skip
  under plain ``pytest``. Verifiable truth must therefore come from a STANDALONE
  run against LIVE Postgres. This script stands up its own async engine +
  sessionmaker from the ``POSTGRES_*`` environment variables — it deliberately does
  NOT import the broken test conftest fixtures — and drives the REAL crumb service
  functions end-to-end. The router-only concerns (audit rows + crumb:read/write
  RBAC) are proven separately over HTTP by verify_crumb_api.py (SC6).

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) LEAD → CUSTOMER (SC2): a lead links an EXISTING SYERP customer, AND a lead
      creates a NEW SYERP customer; both paths stamp partner_id and set the lead
      status to "qualified".
  (B) LEAD → OPPORTUNITY (SC2): converting a qualified lead stamps both sides
      (lead.opportunity_id set, lead.status "converted"; opp.lead_id set, stage
      "qualify"); converting a lead with NO linked customer is rejected 422.
  (C) OPPORTUNITY STAGE FSM (SC3): the valid walk qualify → proposal → won
      succeeds; an invalid transition (off the terminal "won", and a disallowed
      skip) is rejected 422; spawn_quote on a NON-won opportunity is rejected 422
      (D-V3-15) while on a won one it returns a Draft quote.
  (D) QUOTE STATUS FSM (SC4): the valid walk draft → sent → accepted succeeds; an
      illegal reject (sent → draft) is rejected 422.
  (E) PLUM-DERIVED PRICE DEFAULT (SC4/D-V3-6/D-V3-14): a line for a PLUM part with
      a released cost snapshot defaults to cost × 1.30; an explicit unit_price
      override persists verbatim; a part with a NULL snapshot (or no released
      revision) defaults to 0 (price entered manually).
  (F) NUMERIC-SAFE QUOTE-#### (SC4/D-P8-6): the pure helper crosses the digit
      boundary (QUOTE-0009 → QUOTE-0010); the DB generator returns the true numeric
      MAX+1 (independent Python oracle) and SURVIVES a non-QUOTE-[0-9]+ junk row in
      the table (the regex filter excludes it before the cast) — never lexicographic.
  (G) QUOTE-LINE INTEGRITY (SC4): Σ(line quantity × unit_price) equals the header
      total_value Decimal-exactly, and each line_total equals quantity × unit_price.
  (H) INTERACTION TIMELINE (SC5): appended interactions carry the acting user and a
      UTC timestamp; the per-customer timeline returns them newest occurred_at first.

The script uses uniquely-suffixed throwaway partners / PLUM parts / leads /
opportunities / quotes / interactions and CLEANS UP after itself (interactions ->
quote lines -> quotes -> opportunities/leads with the circular FK broken first ->
partners -> PLUM revisions/parts) in a finally block, so it is safe to re-run
against the same database.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_crumb.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the crumb_* FKs reference syerp_* and plum_* tables that must be registered
# before the FKs resolve — the Task-8 lesson from MOUSSE).
import app.core.models  # noqa: F401
from app.modules.crumb.models import (
    Interaction,
    Lead,
    Opportunity,
    Quote,
    QuoteLine,
)
from app.modules.crumb.schemas import (
    InteractionCreate,
    LeadCreate,
    LeadLinkCustomerRequest,
    LeadToOpportunityRequest,
    OpportunityCreate,
    OpportunityToQuoteRequest,
    QuoteCreate,
    QuoteLineCreate,
)
from app.modules.crumb.service import (
    advance_quote_status,
    advance_stage,
    convert_to_opportunity,
    create_interaction,
    create_lead,
    create_opportunity,
    create_quote,
    generate_quote_number,
    get_quote_detail,
    link_or_create_customer,
    list_customer_timeline,
    spawn_quote,
)
from app.modules.crumb.service.quotes import _next_quote_number
from app.modules.plum.models import PlumPart, PlumPartRevision
from app.modules.syerp.models import Partner
from app.modules.syerp.schemas import PartnerCreate
from app.modules.syerp.service.partners import create_partner

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0

_NUMERIC_QUOTE = re.compile(r"^QUOTE-[0-9]+$")


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
# Fixture builders — SYERP customer partner + PLUM part with a released revision
# ---------------------------------------------------------------------------


async def _make_customer(session_factory, unique: str, tag: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    async with session_factory() as session:
        partner = await create_partner(
            session,
            PartnerCreate(name=f"VERIFY-CRUMB {tag} {unique}", is_customer=True),
        )
        return partner.id


async def _make_part(
    session_factory,
    part_number: str,
    *,
    released: bool,
    snapshot: Decimal | None,
) -> str:
    """
    Insert a PLUM part + its revision 1 directly via the ORM; return part_id.

    `released=True` writes a Released revision (the quote-line pricing looks up the
    released revision's `released_cost_snapshot`); `released=False` leaves it Draft
    (used to prove the no-released-cost path defaults to 0). Direct ORM inserts keep
    the fixture fully controllable rather than driving the whole PLUM FSM.
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
            status="released" if released else "draft",
            description=f"verify_crumb {part_number}",
            unit_of_measure="ea",
            released_at=datetime.now(UTC) if released else None,
            released_cost_snapshot=snapshot,
        )
        session.add(rev)
        await session.commit()
        return part.id


async def _max_quote_suffix(session_factory) -> int:
    """True numeric MAX over ^QUOTE-[0-9]+$ rows, computed in Python (oracle)."""
    async with session_factory() as session:
        rows = (await session.execute(select(Quote.quote_number))).scalars().all()
    suffixes = [int(qn.split("-", 1)[1]) for qn in rows if _NUMERIC_QUOTE.match(qn)]
    return max(suffixes) if suffixes else 0


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    partner_ids: set[str] = set()
    part_ids: set[str] = set()
    lead_ids: set[str] = set()
    opp_ids: set[str] = set()
    quote_ids: set[str] = set()
    interaction_ids: set[str] = set()

    def _pn(*parts: object) -> str:
        # Non-numeric part numbers never disturb PLUM auto-numbering (P##### series).
        return f"P-CR-{unique}-" + "-".join(str(p) for p in parts)

    try:
        # A reusable existing customer for the linked-lead / opportunity paths.
        cust_id = await _make_customer(session_factory, unique, "CUST")
        partner_ids.add(cust_id)

        # ===================================================================
        # (A) LEAD → CUSTOMER: link existing AND create new (SC2)
        # ===================================================================
        async with session_factory() as session:
            lead_link = await create_lead(
                session, LeadCreate(name=f"Lead-link {unique}"), actor_id
            )
        lead_ids.add(lead_link.id)
        async with session_factory() as session:
            linked = await link_or_create_customer(
                session,
                lead_link.id,
                LeadLinkCustomerRequest(partner_id=cust_id),
                actor_id,
            )
        check(
            "(A/SC2) linking a lead to an EXISTING customer stamps partner_id and "
            "sets status 'qualified'",
            linked.partner_id == cust_id and linked.status == "qualified",
            f"partner_id={linked.partner_id!r} status={linked.status!r}",
        )

        async with session_factory() as session:
            lead_new = await create_lead(
                session, LeadCreate(name=f"Lead-new {unique}"), actor_id
            )
        lead_ids.add(lead_new.id)
        async with session_factory() as session:
            created = await link_or_create_customer(
                session,
                lead_new.id,
                LeadLinkCustomerRequest(new_customer_name=f"VERIFY-CRUMB NEWCUST {unique}"),
                actor_id,
            )
        if created.partner_id:
            partner_ids.add(created.partner_id)
        # Verify the freshly created partner is actually a SYERP customer.
        async with session_factory() as session:
            new_partner = await session.get(Partner, created.partner_id) if created.partner_id else None
        check(
            "(A/SC2) linking a lead by new_customer_name CREATES a SYERP customer, "
            "stamps partner_id and sets status 'qualified'",
            created.partner_id is not None
            and created.partner_id != cust_id
            and created.status == "qualified"
            and new_partner is not None
            and new_partner.is_customer is True,
            f"partner_id={created.partner_id!r} status={created.status!r} "
            f"is_customer={getattr(new_partner, 'is_customer', None)!r}",
        )

        # ===================================================================
        # (B) LEAD → OPPORTUNITY conversion (SC2)
        # ===================================================================
        async with session_factory() as session:
            opp_from_lead = await convert_to_opportunity(
                session,
                lead_link.id,
                LeadToOpportunityRequest(
                    name=f"Opp-from-lead {unique}", estimated_value=Decimal("1000")
                ),
                actor_id,
            )
        opp_ids.add(opp_from_lead.id)
        async with session_factory() as session:
            lead_after = await session.get(Lead, lead_link.id)
        check(
            "(B/SC2) converting a qualified lead stamps both sides (lead.opportunity_id "
            "+ status 'converted'; opp.lead_id + stage 'qualify')",
            lead_after.opportunity_id == opp_from_lead.id
            and lead_after.status == "converted"
            and opp_from_lead.lead_id == lead_link.id
            and opp_from_lead.stage == "qualify"
            and opp_from_lead.partner_id == cust_id,
            f"lead.opportunity_id={lead_after.opportunity_id!r} lead.status={lead_after.status!r} "
            f"opp.lead_id={opp_from_lead.lead_id!r} opp.stage={opp_from_lead.stage!r}",
        )

        # convert-WITHOUT-customer → 422
        async with session_factory() as session:
            lead_nolink = await create_lead(
                session, LeadCreate(name=f"Lead-nolink {unique}"), actor_id
            )
        lead_ids.add(lead_nolink.id)
        try:
            async with session_factory() as session:
                await convert_to_opportunity(
                    session,
                    lead_nolink.id,
                    LeadToOpportunityRequest(name=f"Opp-should-fail {unique}"),
                    actor_id,
                )
            check("(B/SC2) converting a lead with NO linked customer is rejected", False,
                  "conversion succeeded")
        except HTTPException as exc:
            check(
                "(B/SC2) converting a lead with NO linked customer is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # ===================================================================
        # (C) OPPORTUNITY STAGE FSM + won-only spawn_quote (SC3 / D-V3-15)
        # ===================================================================
        async with session_factory() as session:
            opp_fsm = await create_opportunity(
                session,
                OpportunityCreate(name=f"Opp-fsm {unique}", partner_id=cust_id),
                actor_id,
            )
        opp_ids.add(opp_fsm.id)
        async with session_factory() as session:
            await advance_stage(session, opp_fsm.id, "proposal", actor_id)
        async with session_factory() as session:
            won = await advance_stage(session, opp_fsm.id, "won", actor_id)
        check(
            "(C/SC3) valid stage walk qualify → proposal → won succeeds",
            won.stage == "won",
            f"stage={won.stage!r}",
        )

        # invalid transition OFF the terminal "won"
        try:
            async with session_factory() as session:
                await advance_stage(session, opp_fsm.id, "proposal", actor_id)
            check("(C/SC3) a transition off the terminal 'won' is rejected", False,
                  "transition succeeded")
        except HTTPException as exc:
            check(
                "(C/SC3) a transition off the terminal 'won' (won → proposal) is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # a disallowed skip: qualify → 'accepted' (not a stage / not an allowed target)
        async with session_factory() as session:
            opp_skip = await create_opportunity(
                session,
                OpportunityCreate(name=f"Opp-skip {unique}", partner_id=cust_id),
                actor_id,
            )
        opp_ids.add(opp_skip.id)
        try:
            async with session_factory() as session:
                await advance_stage(session, opp_skip.id, "accepted", actor_id)
            check("(C/SC3) a disallowed stage target is rejected", False,
                  "transition succeeded")
        except HTTPException as exc:
            check(
                "(C/SC3) a disallowed stage target (qualify → 'accepted') is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # spawn_quote on a NON-won opportunity → 422 (D-V3-15)
        async with session_factory() as session:
            opp_nonwon = await create_opportunity(
                session,
                OpportunityCreate(name=f"Opp-nonwon {unique}", partner_id=cust_id),
                actor_id,
            )
        opp_ids.add(opp_nonwon.id)
        try:
            async with session_factory() as session:
                await spawn_quote(
                    session, opp_nonwon.id, OpportunityToQuoteRequest(), actor_id
                )
            check("(C/D-V3-15) spawn_quote on a non-won opportunity is rejected", False,
                  "spawn succeeded")
        except HTTPException as exc:
            check(
                "(C/D-V3-15) spawn_quote on a non-won opportunity is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # spawn_quote on the WON opportunity → a Draft quote carrying the opp + partner
        async with session_factory() as session:
            spawned = await spawn_quote(
                session, opp_fsm.id, OpportunityToQuoteRequest(), actor_id
            )
        quote_ids.add(spawned.id)
        check(
            "(C/D-V3-15) spawn_quote on a WON opportunity returns a Draft quote linked "
            "to the opportunity and its customer",
            spawned.status == "draft"
            and spawned.opportunity_id == opp_fsm.id
            and spawned.partner_id == cust_id
            and spawned.quote_number.startswith("QUOTE-"),
            f"status={spawned.status!r} opp={spawned.opportunity_id!r} "
            f"partner={spawned.partner_id!r} number={spawned.quote_number!r}",
        )

        # ===================================================================
        # (D) QUOTE STATUS FSM (SC4)
        # ===================================================================
        async with session_factory() as session:
            q_fsm = await create_quote(
                session, QuoteCreate(partner_id=cust_id, lines=[]), actor_id
            )
        quote_ids.add(q_fsm.id)
        async with session_factory() as session:
            await advance_quote_status(session, q_fsm.id, "sent", actor_id)
        async with session_factory() as session:
            accepted = await advance_quote_status(session, q_fsm.id, "accepted", actor_id)
        check(
            "(D/SC4) valid status walk draft → sent → accepted succeeds",
            accepted.status == "accepted",
            f"status={accepted.status!r}",
        )

        async with session_factory() as session:
            q_reject = await create_quote(
                session, QuoteCreate(partner_id=cust_id, lines=[]), actor_id
            )
        quote_ids.add(q_reject.id)
        async with session_factory() as session:
            await advance_quote_status(session, q_reject.id, "sent", actor_id)
        try:
            async with session_factory() as session:
                await advance_quote_status(session, q_reject.id, "draft", actor_id)
            check("(D/SC4) an illegal reject (sent → draft) is rejected", False,
                  "transition succeeded")
        except HTTPException as exc:
            check(
                "(D/SC4) an illegal reject (sent → draft) is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # ===================================================================
        # (E) PLUM-DERIVED PRICE DEFAULT + (G) QUOTE-LINE INTEGRITY (SC4)
        # ===================================================================
        # PA: released revision, snapshot 100 → default price 100 * 1.30 == 130.
        # PB: released revision, NULL snapshot → default 0.
        # PC: NO released revision (draft only) → default 0.
        part_a = await _make_part(session_factory, _pn("PA"), released=True, snapshot=Decimal("100"))
        part_b = await _make_part(session_factory, _pn("PB"), released=True, snapshot=None)
        part_c = await _make_part(session_factory, _pn("PC"), released=False, snapshot=Decimal("55"))
        part_ids.update({part_a, part_b, part_c})

        async with session_factory() as session:
            q_price = await create_quote(
                session,
                QuoteCreate(
                    partner_id=cust_id,
                    lines=[
                        # PLUM default: 100 * 1.30 == 130, markup 30, qty 2 → 260
                        QuoteLineCreate(plum_part_id=part_a, quantity=Decimal("2")),
                        # explicit override persists verbatim, qty 3 → 127.5
                        QuoteLineCreate(
                            plum_part_id=part_a, quantity=Decimal("3"),
                            unit_price=Decimal("42.5"),
                        ),
                        # released rev but NULL snapshot → 0, qty 1 → 0
                        QuoteLineCreate(plum_part_id=part_b, quantity=Decimal("1")),
                        # no released rev → 0, qty 1 → 0
                        QuoteLineCreate(plum_part_id=part_c, quantity=Decimal("1")),
                    ],
                ),
                actor_id,
            )
        quote_ids.add(q_price.id)
        async with session_factory() as session:
            detail = await get_quote_detail(session, q_price.id)
        lines = detail.lines
        check(
            "(E/SC4) a PLUM-part line with a released snapshot defaults to cost × 1.30 "
            "(100 → 130.000000) with the 30% markup recorded",
            len(lines) == 4
            and lines[0].unit_price == Decimal("130")
            and lines[0].markup_pct == Decimal("30"),
            f"unit_price={lines[0].unit_price!r} markup={lines[0].markup_pct!r}",
        )
        check(
            "(E/SC4) an explicit unit_price override persists verbatim (42.5)",
            lines[1].unit_price == Decimal("42.5"),
            f"unit_price={lines[1].unit_price!r}",
        )
        check(
            "(E/SC4) a released part with a NULL snapshot defaults unit_price to 0 "
            "(price entered manually)",
            lines[2].unit_price == Decimal("0"),
            f"unit_price={lines[2].unit_price!r}",
        )
        check(
            "(E/SC4) a part with NO released revision defaults unit_price to 0",
            lines[3].unit_price == Decimal("0"),
            f"unit_price={lines[3].unit_price!r}",
        )

        # (E2/SC4/D-V3-14) Identity rule: a part-less line MUST carry a description,
        # even when a price is supplied — otherwise an unlabeled line lands on a
        # customer-facing quote. A supplied price must not bypass this guard.
        try:
            async with session_factory() as session:
                await create_quote(
                    session,
                    QuoteCreate(
                        partner_id=cust_id,
                        lines=[QuoteLineCreate(quantity=Decimal("2"), unit_price=Decimal("50"))],
                    ),
                    actor_id,
                )
            check(
                "(E2/SC4) a part-less line with a price but NO description is rejected",
                False,
                "create_quote accepted an unlabeled free-text line",
            )
        except HTTPException as exc:
            check(
                "(E2/SC4) a part-less line with a price but NO description is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # (E3/SC4) A legitimate free-text line (description + explicit price, no part)
        # is accepted and persists verbatim — the guard rejects only unlabeled lines.
        async with session_factory() as session:
            q_freetext = await create_quote(
                session,
                QuoteCreate(
                    partner_id=cust_id,
                    lines=[
                        QuoteLineCreate(
                            description="Custom tooling charge",
                            quantity=Decimal("1"),
                            unit_price=Decimal("75"),
                        )
                    ],
                ),
                actor_id,
            )
        quote_ids.add(q_freetext.id)
        async with session_factory() as session:
            ft_detail = await get_quote_detail(session, q_freetext.id)
        check(
            "(E3/SC4) a free-text line with a description + explicit price is accepted "
            "and persists (description + unit_price 75)",
            len(ft_detail.lines) == 1
            and ft_detail.lines[0].description == "Custom tooling charge"
            and ft_detail.lines[0].unit_price == Decimal("75")
            and ft_detail.lines[0].plum_part_id is None,
            f"lines={[(line.description, line.unit_price) for line in ft_detail.lines]!r}",
        )

        # (G) line integrity: Σ(qty × unit_price) == total_value, Decimal-exact.
        expected_total = (
            Decimal("2") * Decimal("130")
            + Decimal("3") * Decimal("42.5")
            + Decimal("1") * Decimal("0")
            + Decimal("1") * Decimal("0")
        )  # 260 + 127.5 == 387.5
        per_line_ok = all(
            ln.line_total == ln.quantity * ln.unit_price for ln in lines
        )
        check(
            "(G/SC4) each line_total == quantity × unit_price and Σ line_total equals the "
            "header total_value Decimal-exactly (387.5)",
            per_line_ok
            and detail.total_value == expected_total
            and detail.total_value == Decimal("387.5"),
            f"total_value={detail.total_value!r} expected={expected_total!r} "
            f"per_line_ok={per_line_ok}",
        )

        # ===================================================================
        # (F) NUMERIC-SAFE QUOTE-#### (SC4 / D-P8-6)
        # ===================================================================
        # Pure-helper digit boundary — the exact QUOTE-0009 → QUOTE-0010 crossing
        # and the empty-series seed. Pure (no DB) so it is deterministic.
        check(
            "(F/D-P8-6) the pure generator crosses the digit boundary "
            "(_next_quote_number(9) == 'QUOTE-0010') and seeds 'QUOTE-0001'",
            _next_quote_number(9) == "QUOTE-0010"
            and _next_quote_number(None) == "QUOTE-0001",
            f"boundary={_next_quote_number(9)!r} seed={_next_quote_number(None)!r}",
        )

        # DB generator: seed a non-QUOTE-[0-9]+ junk row + a numeric pair whose suffix
        # is far above any real number, then prove the generator ignores the junk and
        # returns the true numeric MAX+1 (independent Python oracle) — never lexicographic.
        base = 900000 + int(unique[:4], 16) % 1000
        junk_number = f"QUOTE-X{unique}"  # leading letter → never matches ^QUOTE-[0-9]+$
        num_low = f"QUOTE-{base:04d}"
        num_high = f"QUOTE-{base + 1:04d}"
        async with session_factory() as session:
            for qn in (junk_number, num_low, num_high):
                q = Quote(
                    quote_number=qn, partner_id=cust_id, status="draft", actor_id=actor_id
                )
                session.add(q)
                await session.flush()
                quote_ids.add(q.id)
            await session.commit()

        expected_suffix = await _max_quote_suffix(session_factory)
        try:
            async with session_factory() as session:
                generated = await generate_quote_number(session)
            survived = True
        except Exception as exc:  # noqa: BLE001 - a raise here IS the D-P8-6 regression
            generated = None
            survived = False
            check(
                "(F/D-P8-6) generate_quote_number survives a non-QUOTE-[0-9]+ junk row",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )
        if survived:
            check(
                "(F/D-P8-6) generate_quote_number survives a non-QUOTE-[0-9]+ junk row and "
                "returns the true numeric MAX+1 (independent oracle), not lexicographic",
                generated is not None
                and bool(_NUMERIC_QUOTE.match(generated))
                and int(generated.split("-", 1)[1]) == expected_suffix + 1,
                f"generated={generated!r} expected_suffix={expected_suffix + 1}",
            )

        # ===================================================================
        # (H) INTERACTION TIMELINE — append + newest-first ordering (SC5)
        # ===================================================================
        now = datetime.now(UTC)
        # Insert out of chronological order to prove ordering is by occurred_at, not
        # by insert order: middle, oldest, newest.
        touches = [
            ("note", "second", now - timedelta(hours=1)),
            ("call", "oldest", now - timedelta(hours=2)),
            ("email", "newest", now),
        ]
        for itype, body, occurred in touches:
            async with session_factory() as session:
                inter = await create_interaction(
                    session,
                    InteractionCreate(
                        partner_id=cust_id,
                        interaction_type=itype,
                        body=body,
                        occurred_at=occurred,
                    ),
                    actor_id,
                )
            interaction_ids.add(inter.id)
        check(
            "(H/SC5) an appended interaction carries the acting user and its UTC timestamp",
            inter.actor_id == actor_id and inter.occurred_at is not None,
            f"actor_id={inter.actor_id!r} occurred_at={inter.occurred_at!r}",
        )
        async with session_factory() as session:
            timeline = await list_customer_timeline(session, cust_id)
        bodies = [t.body for t in timeline]
        check(
            "(H/SC5) the per-customer timeline returns interactions newest occurred_at "
            "first (newest, second, oldest)",
            bodies == ["newest", "second", "oldest"],
            f"order={bodies!r}",
        )

    finally:
        await _cleanup(
            session_factory,
            partner_ids,
            part_ids,
            lead_ids,
            opp_ids,
            quote_ids,
            interaction_ids,
        )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    partner_ids: set[str],
    part_ids: set[str],
    lead_ids: set[str],
    opp_ids: set[str],
    quote_ids: set[str],
    interaction_ids: set[str],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: interactions -> quote lines ->
    quotes -> (break the crumb_lead ↔ crumb_opportunity circular FK by nulling
    lead.opportunity_id) -> opportunities -> leads -> partners -> PLUM revisions ->
    PLUM parts. Nothing seeded is touched.
    """
    async with session_factory() as session:
        i_list = list(interaction_ids)
        q_list = list(quote_ids)
        o_list = list(opp_ids)
        le_list = list(lead_ids)
        pa_list = list(partner_ids)
        pt_list = list(part_ids)

        if i_list:
            await session.execute(delete(Interaction).where(Interaction.id.in_(i_list)))
        if q_list:
            await session.execute(delete(QuoteLine).where(QuoteLine.quote_id.in_(q_list)))
            await session.execute(delete(Quote).where(Quote.id.in_(q_list)))
        if le_list:
            # Break the crumb_lead ↔ crumb_opportunity circular FK before deleting.
            await session.execute(
                update(Lead).where(Lead.id.in_(le_list)).values(opportunity_id=None)
            )
        if o_list:
            await session.execute(delete(Opportunity).where(Opportunity.id.in_(o_list)))
        if le_list:
            await session.execute(delete(Lead).where(Lead.id.in_(le_list)))
        if pa_list:
            await session.execute(delete(Partner).where(Partner.id.in_(pa_list)))
        if pt_list:
            await session.execute(
                delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(pt_list))
            )
            await session.execute(delete(PlumPart).where(PlumPart.id.in_(pt_list)))

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
