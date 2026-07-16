# ABOUTME: Router-level live-HTTP verification for the CRUMB CRM endpoints (Phase 11a,
# ABOUTME: CRUMB-01 SC6). Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in
# ABOUTME: the image) to prove the crumb:read/crumb:write RBAC gate returns 200/401/403 on
# ABOUTME: leads/opportunities/quotes/interactions routes, and that create/convert/stage/
# ABOUTME: quote-create/status/interaction mutations write attributable AuditLog rows; exits
# ABOUTME: non-zero on FAIL and self-cleans (crumb rows, audit rows, throwaway users/roles).
"""
Router-level live-HTTP verification for the CRUMB CRM endpoints (Phase 11a).

WHY THIS EXISTS (the router proof — the companion to verify_crumb.py):
  verify_crumb.py drives the crumb SERVICE functions directly and so proves the
  FSMs, PLUM-derived pricing and numbering, but it can never exercise the two
  things that live only in the ROUTER: the audit rows written by write_audit and
  the RBAC gate enforced by require_permission("crumb:read" / "crumb:write"). This
  script closes that gap (SC6 — the 9a HTTP-verify discipline) by making REAL HTTP
  calls against the running api and asserting, for representative routes of EACH
  entity (leads, opportunities, quotes, interactions):
    - every MUTATION accepts a crumb:write token (2xx), refuses a token WITHOUT
      crumb:write (403 — a crumb:read-only user), and refuses an unauthenticated
      request (401);
    - every READ accepts a crumb:read token (200), refuses a no-permission token
      (403), and refuses an unauthenticated request (401);
    - after a successful create / convert / stage-change / quote-create /
      status-change / interaction driven over HTTP, the matching AuditLog row
      exists, is attributable to the acting user (actor_id), and targets the entity
      (target_type/target_id).

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so this mints THREE throwaway users backed by throwaway roles:
    * writer   — role holding crumb:read + crumb:write (drives the lifecycle over
                 HTTP; the audit rows are attributable to THIS user);
    * reader   — role holding ONLY crumb:read (200 on reads, 403 on every mutation);
    * noperm   — no roles at all (403 on reads, the no-permission case).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_crumb.py which owns its own engine):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_api.py

The script builds its OWN SYERP customer fixtures via the service functions (so it
has real customers to quote/log against), drives the pipeline over HTTP, and CLEANS
UP after itself in a finally block (interactions -> quote lines -> quotes ->
opportunities/leads with the circular FK broken -> partners -> the audit_log rows it
wrote -> the three throwaway users + roles), so it is safe to re-run.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_crumb_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.crumb.models import Interaction, Lead, Opportunity, Quote, QuoteLine
from app.modules.syerp.models import Partner
from app.modules.syerp.schemas import PartnerCreate
from app.modules.syerp.service.partners import create_partner

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/crumb"


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


def build_dsn() -> str:
    """Assemble the asyncpg DSN directly from POSTGRES_* env (self-contained)."""
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def http(method: str, path: str, token: str | None = None, payload: dict | None = None):
    """
    Make one blocking HTTP request against the running api and return (status, body).

    Uses stdlib urllib (httpx is not installed in the runtime image). `path` is
    relative to the /api/v1/crumb base. HTTP error statuses are captured and
    returned rather than raised, so the caller can assert on 401/403/422.
    """
    url = f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


async def _audit_row(session_factory, action: str, target_id: str):
    """Fetch the AuditLog row for (action, target_id), or None."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == action,
                    AuditLog.target_id == target_id,
                )
            )
        ).scalars().first()


async def _make_customer(session_factory, unique: str, tag: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    async with session_factory() as session:
        partner = await create_partner(
            session,
            PartnerCreate(name=f"VERIFY-CRUMB-API {tag} {unique}", is_customer=True),
        )
        return partner.id


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    partner_ids: set[str] = set()
    lead_ids: set[str] = set()
    opp_ids: set[str] = set()
    quote_ids: set[str] = set()
    interaction_ids: set[str] = set()
    user_ids: list[str] = []
    role_ids: list[int] = []

    writer_id: str | None = None
    reader_id: str | None = None
    noperm_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Setup: mint the three throwaway users (writer = read+write,
        # reader = read-only, noperm = no roles) and a customer fixture.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            perms = {
                p.code: p
                for p in (
                    await session.execute(
                        select(Permission).where(
                            Permission.code.in_(["crumb:read", "crumb:write"])
                        )
                    )
                ).scalars().all()
            }
            if "crumb:read" not in perms or "crumb:write" not in perms:
                print("FAIL: seeded crumb:read/crumb:write permissions not found.")
                sys.exit(2)

            writer_role = Role(
                name=f"verify-crumb-writer-{unique}",
                description="VERIFY throwaway role: crumb:read + crumb:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["crumb:read"], perms["crumb:write"]]
            )

            reader_role = Role(
                name=f"verify-crumb-reader-{unique}",
                description="VERIFY throwaway role: crumb:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["crumb:read"])

            writer = User(
                email=f"verify-crumb-writer-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-writer-pw"),
                full_name="VERIFY crumb:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-crumb-reader-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-reader-pw"),
                full_name="VERIFY crumb:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-crumb-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-noperm-pw"),
                full_name="VERIFY no-permission user",
                is_active=True,
            )
            session.add(noperm)
            await session.flush()

            await session.commit()
            writer_id, reader_id, noperm_id = writer.id, reader.id, noperm.id
            role_ids.extend([writer_role.id, reader_role.id])
        user_ids.extend([writer_id, reader_id, noperm_id])

        writer_token = create_access_token(writer_id, [])
        reader_token = create_access_token(reader_id, [])
        noperm_token = create_access_token(noperm_id, [])

        cust_id = await _make_customer(session_factory, unique, "CUST")
        partner_ids.add(cust_id)

        # ===================================================================
        # (A) LEAD create + convert over HTTP (writer) + attributable audit (SC6).
        # ===================================================================
        s, body = http("POST", "/leads", writer_token, {"name": f"API-lead {unique}"})
        lead_id = body.get("id") if isinstance(body, dict) else None
        if lead_id:
            lead_ids.add(lead_id)
        check(
            "(A) POST /crumb/leads with crumb:write → 201 with a new lead id",
            s == 201 and lead_id is not None and body.get("status") == "new",
            f"status={s} body={body!r}",
        )
        lead_created_audit = await _audit_row(session_factory, "lead.created", lead_id)
        check(
            "(A/SC6) a lead.created audit row exists, attributable to the writer, "
            "targeting the created lead",
            lead_created_audit is not None
            and lead_created_audit.actor_id == writer_id
            and lead_created_audit.target_type == "crumb_lead",
            f"audit={lead_created_audit!r}",
        )

        # Link to the customer (prerequisite for convert), then convert.
        s, _ = http(
            "POST", f"/leads/{lead_id}/link-customer", writer_token,
            {"partner_id": cust_id},
        )
        check(
            "(A) POST /crumb/leads/{id}/link-customer with crumb:write → 200",
            s == 200,
            f"status={s}",
        )
        s, body = http(
            "POST", f"/leads/{lead_id}/convert", writer_token,
            {"name": f"API-opp-from-lead {unique}"},
        )
        conv_opp_id = body.get("id") if isinstance(body, dict) else None
        if conv_opp_id:
            opp_ids.add(conv_opp_id)
        check(
            "(A) POST /crumb/leads/{id}/convert with crumb:write → 201 with an "
            "opportunity in stage 'qualify'",
            s == 201 and conv_opp_id is not None and body.get("stage") == "qualify",
            f"status={s} body={body!r}",
        )
        lead_converted_audit = await _audit_row(session_factory, "lead.converted", lead_id)
        check(
            "(A/SC6) a lead.converted audit row exists, attributable to the writer, "
            "targeting the lead",
            lead_converted_audit is not None
            and lead_converted_audit.actor_id == writer_id
            and lead_converted_audit.target_type == "crumb_lead",
            f"audit={lead_converted_audit!r}",
        )

        # ===================================================================
        # (B) OPPORTUNITY create + stage-change over HTTP (writer) + audit (SC6).
        # ===================================================================
        s, body = http(
            "POST", "/opportunities", writer_token,
            {"name": f"API-opp {unique}", "partner_id": cust_id},
        )
        opp_id = body.get("id") if isinstance(body, dict) else None
        if opp_id:
            opp_ids.add(opp_id)
        check(
            "(B) POST /crumb/opportunities with crumb:write → 201 with a new "
            "opportunity in stage 'qualify'",
            s == 201 and opp_id is not None and body.get("stage") == "qualify",
            f"status={s} body={body!r}",
        )
        opp_created_audit = await _audit_row(session_factory, "opportunity.created", opp_id)
        check(
            "(B/SC6) an opportunity.created audit row exists, attributable to the writer",
            opp_created_audit is not None
            and opp_created_audit.actor_id == writer_id
            and opp_created_audit.target_type == "crumb_opportunity",
            f"audit={opp_created_audit!r}",
        )

        s, body = http(
            "POST", f"/opportunities/{opp_id}/stage", writer_token,
            {"target_stage": "proposal"},
        )
        check(
            "(B) POST /crumb/opportunities/{id}/stage with crumb:write → 200, stage "
            "advanced to 'proposal'",
            s == 200 and isinstance(body, dict) and body.get("stage") == "proposal",
            f"status={s} body={body!r}",
        )
        stage_audit = await _audit_row(
            session_factory, "opportunity.stage_changed", opp_id
        )
        check(
            "(B/SC6) an opportunity.stage_changed audit row exists, attributable to the writer",
            stage_audit is not None
            and stage_audit.actor_id == writer_id
            and stage_audit.target_type == "crumb_opportunity",
            f"audit={stage_audit!r}",
        )

        # ===================================================================
        # (C) QUOTE create + status-change over HTTP (writer) + audit (SC6).
        # ===================================================================
        s, body = http(
            "POST", "/quotes", writer_token,
            {"partner_id": cust_id, "lines": []},
        )
        quote_id = body.get("id") if isinstance(body, dict) else None
        if quote_id:
            quote_ids.add(quote_id)
        check(
            "(C) POST /crumb/quotes with crumb:write → 201 with a Draft quote and a "
            "QUOTE-#### number",
            s == 201
            and quote_id is not None
            and body.get("status") == "draft"
            and str(body.get("quote_number", "")).startswith("QUOTE-"),
            f"status={s} body={body!r}",
        )
        quote_created_audit = await _audit_row(session_factory, "quote.created", quote_id)
        check(
            "(C/SC6) a quote.created audit row exists, attributable to the writer",
            quote_created_audit is not None
            and quote_created_audit.actor_id == writer_id
            and quote_created_audit.target_type == "crumb_quote",
            f"audit={quote_created_audit!r}",
        )

        s, body = http(
            "POST", f"/quotes/{quote_id}/status", writer_token,
            {"target_status": "sent"},
        )
        check(
            "(C) POST /crumb/quotes/{id}/status with crumb:write → 200, status → 'sent'",
            s == 200 and isinstance(body, dict) and body.get("status") == "sent",
            f"status={s} body={body!r}",
        )
        status_audit = await _audit_row(session_factory, "quote.status_changed", quote_id)
        check(
            "(C/SC6) a quote.status_changed audit row exists, attributable to the writer",
            status_audit is not None
            and status_audit.actor_id == writer_id
            and status_audit.target_type == "crumb_quote",
            f"audit={status_audit!r}",
        )

        # A bogus opportunity_id on direct quote create must surface as a clean 404,
        # not a DB IntegrityError re-raised as a 500 by the quote-number retry.
        s, _ = http(
            "POST", "/quotes", writer_token,
            {"partner_id": cust_id, "opportunity_id": f"missing-{unique}", "lines": []},
        )
        check(
            "(C) POST /crumb/quotes with a nonexistent opportunity_id → 404 (not 500)",
            s == 404,
            f"status={s}",
        )

        # ===================================================================
        # (C2) SPAWN a quote from a WON opportunity → BOTH audit rows (SC6/D-V3-15).
        #      The section-B opportunity is at 'proposal'; walk it to 'won', spawn,
        #      and assert an opportunity.quote_spawned row (target: the opp) AND a
        #      quote.created row (target: the new quote) — the spawned quote carries
        #      the same attributable creation record as a directly-created one.
        # ===================================================================
        http("POST", f"/opportunities/{opp_id}/stage", writer_token, {"target_stage": "won"})
        s, body = http("POST", f"/opportunities/{opp_id}/quote", writer_token, {})
        spawned_quote_id = body.get("id") if isinstance(body, dict) else None
        if spawned_quote_id:
            quote_ids.add(spawned_quote_id)
        check(
            "(C2) POST /crumb/opportunities/{id}/quote on a WON opportunity → 201 "
            "with a Draft quote",
            s == 201 and spawned_quote_id is not None and body.get("status") == "draft",
            f"status={s} body={body!r}",
        )
        spawn_audit = await _audit_row(session_factory, "opportunity.quote_spawned", opp_id)
        check(
            "(C2/SC6) an opportunity.quote_spawned audit row exists (target: the opportunity)",
            spawn_audit is not None
            and spawn_audit.actor_id == writer_id
            and spawn_audit.target_type == "crumb_opportunity",
            f"audit={spawn_audit!r}",
        )
        spawned_created_audit = await _audit_row(
            session_factory, "quote.created", spawned_quote_id
        )
        check(
            "(C2/SC6) a spawned quote also gets its own quote.created audit row "
            "(target: the new quote) — no audit asymmetry with direct create",
            spawned_created_audit is not None
            and spawned_created_audit.actor_id == writer_id
            and spawned_created_audit.target_type == "crumb_quote",
            f"audit={spawned_created_audit!r}",
        )

        # ===================================================================
        # (D) INTERACTION log over HTTP (writer) + audit (SC6).
        # ===================================================================
        s, body = http(
            "POST", "/interactions", writer_token,
            {"partner_id": cust_id, "interaction_type": "note", "body": f"API note {unique}"},
        )
        interaction_id = body.get("id") if isinstance(body, dict) else None
        if interaction_id:
            interaction_ids.add(interaction_id)
        check(
            "(D) POST /crumb/interactions with crumb:write → 201 with a logged interaction",
            s == 201 and interaction_id is not None and body.get("interaction_type") == "note",
            f"status={s} body={body!r}",
        )
        interaction_audit = await _audit_row(
            session_factory, "interaction.logged", interaction_id
        )
        check(
            "(D/SC6) an interaction.logged audit row exists, attributable to the writer",
            interaction_audit is not None
            and interaction_audit.actor_id == writer_id
            and interaction_audit.target_type == "crumb_interaction",
            f"audit={interaction_audit!r}",
        )

        # ===================================================================
        # (E) RBAC on every MUTATION route: a token WITHOUT crumb:write (the
        #     crumb:read-only reader) → 403; unauthenticated → 401. These auth
        #     failures short-circuit BEFORE the service, so firing them against the
        #     already-driven records cannot mutate state (SC6).
        # ===================================================================
        timeline_q = "?" + urllib.parse.urlencode({"partner_id": cust_id})
        mutation_routes = [
            ("POST", "/leads", {"name": "rbac"}),
            ("POST", f"/leads/{lead_id}/convert", {"name": "rbac"}),
            ("POST", "/opportunities", {"name": "rbac", "partner_id": cust_id}),
            ("POST", f"/opportunities/{opp_id}/stage", {"target_stage": "won"}),
            ("POST", "/quotes", {"partner_id": cust_id, "lines": []}),
            ("POST", f"/quotes/{quote_id}/status", {"target_status": "accepted"}),
            ("POST", "/interactions",
             {"partner_id": cust_id, "interaction_type": "note", "body": "rbac"}),
        ]
        for method, path, payload in mutation_routes:
            s, _ = http(method, path, reader_token, payload)
            check(
                f"(E) crumb:read-only token → 403 on {method} {path} (no crumb:write)",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None, payload)
            check(
                f"(E) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

        # ===================================================================
        # (F) RBAC on every READ route: crumb:read token → 200; no-permission
        #     token → 403; unauthenticated → 401 (SC6).
        # ===================================================================
        read_routes = [
            ("GET", "/leads"),
            ("GET", f"/leads/{lead_id}"),
            ("GET", "/opportunities"),
            ("GET", f"/opportunities/{opp_id}"),
            ("GET", "/quotes"),
            ("GET", f"/quotes/{quote_id}"),
            ("GET", f"/interactions{timeline_q}"),
        ]
        for method, path in read_routes:
            s, _ = http(method, path, reader_token)
            check(
                f"(F) crumb:read token → 200 on {method} {path}",
                s == 200,
                f"status={s}",
            )
            s, _ = http(method, path, noperm_token)
            check(
                f"(F) no-permission token → 403 on {method} {path}",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None)
            check(
                f"(F) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

    finally:
        await _cleanup(
            session_factory,
            partner_ids,
            lead_ids,
            opp_ids,
            quote_ids,
            interaction_ids,
            user_ids,
            role_ids,
        )
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    partner_ids: set[str],
    lead_ids: set[str],
    opp_ids: set[str],
    quote_ids: set[str],
    interaction_ids: set[str],
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: interactions -> quote lines ->
    quotes -> (break the crumb_lead ↔ crumb_opportunity circular FK by nulling
    lead.opportunity_id) -> opportunities -> leads -> partners -> the audit_log
    rows targeting the crumb records -> throwaway users -> throwaway roles.
    """
    async with session_factory() as session:
        i_list = list(interaction_ids)
        q_list = list(quote_ids)
        o_list = list(opp_ids)
        le_list = list(lead_ids)
        pa_list = list(partner_ids)
        audit_targets = i_list + q_list + o_list + le_list

        if i_list:
            await session.execute(delete(Interaction).where(Interaction.id.in_(i_list)))
        if q_list:
            await session.execute(delete(QuoteLine).where(QuoteLine.quote_id.in_(q_list)))
            await session.execute(delete(Quote).where(Quote.id.in_(q_list)))
        if le_list:
            await session.execute(
                update(Lead).where(Lead.id.in_(le_list)).values(opportunity_id=None)
            )
        if o_list:
            await session.execute(delete(Opportunity).where(Opportunity.id.in_(o_list)))
        if le_list:
            await session.execute(delete(Lead).where(Lead.id.in_(le_list)))
        if pa_list:
            await session.execute(delete(Partner).where(Partner.id.in_(pa_list)))
        if audit_targets:
            await session.execute(
                delete(AuditLog).where(AuditLog.target_id.in_(audit_targets))
            )
        if user_ids:
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        if role_ids:
            await session.execute(delete(Role).where(Role.id.in_(role_ids)))

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
