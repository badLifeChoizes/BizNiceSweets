# ABOUTME: Router-level live-HTTP verification for the CRUMB sales-order endpoints (Phase 11b,
# ABOUTME: CRUMB-01 SC5). Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in the
# ABOUTME: image) to prove the crumb:read/crumb:write RBAC gate returns 200/401/403 on every SO
# ABOUTME: route (+ the quote→SO convert), and that create/confirm/cancel/convert write
# ABOUTME: attributable AuditLog rows targeting the SO; exits non-zero on FAIL and self-cleans
# ABOUTME: (SO rows, quotes, fixtures, audit rows, throwaway users/roles).
"""
Router-level live-HTTP verification for the CRUMB sales-order endpoints (Phase 11b).

WHY THIS EXISTS (the router proof — the SO companion to verify_crumb_so.py):
  verify_crumb_so.py drives the sales-order SERVICE functions directly and so
  proves the SO-#### numbering, the draft→confirmed→fulfilling→closed FSM and the
  soft-reservation math, but it can never exercise the two things that live only
  in the ROUTER: the audit rows written by write_audit and the RBAC gate enforced
  by require_permission("crumb:read" / "crumb:write"). This script closes that gap
  (SC5 — the 9a HTTP-verify discipline; the service-level Task 10 CANNOT prove
  router audit/RBAC) by making REAL HTTP calls against the running api and
  asserting, for every sales-order route (+ the quote→SO convert):
    - every MUTATION accepts a crumb:write token (2xx), refuses a token WITHOUT
      crumb:write (403 — a crumb:read-only user), and refuses an unauthenticated
      request (401);
    - every READ accepts a crumb:read token (200), refuses a no-permission token
      (403), and refuses an unauthenticated request (401);
    - after a successful SO create, a confirm, a cancel, and a quote→SO conversion
      driven over HTTP, the matching AuditLog row (sales_order.created / .confirmed
      / .cancelled / quote.converted_to_sales_order) exists, is attributable to the
      acting user (actor_id), and targets the SO (target_type == "sales_order").

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so this mints THREE throwaway users backed by throwaway roles:
    * writer   — role holding crumb:read + crumb:write (drives the lifecycle over
                 HTTP; the audit rows are attributable to THIS user);
    * reader   — role holding ONLY crumb:read (200 on reads, 403 on every mutation);
    * noperm   — no roles at all (403 on reads, the no-permission case).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_crumb_so.py which owns its engine):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_so_api.py

The script builds its OWN SYERP customer + a stocked InventoryItem (on-hand via a
receipt) so a confirm can actually soft-reserve, drives the SO lifecycle over HTTP,
and CLEANS UP after itself in a finally block (SO lines -> sales orders -> quote
lines -> quotes -> inventory txns -> inventory items -> partners -> the audit_log
rows it wrote -> the three throwaway users + roles), so it is safe to re-run. The
seeded "Main" location is reused and left in place.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_crumb_so_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.crumb.models import (
    Quote,
    QuoteLine,
    SalesOrder,
    SalesOrderLine,
)
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import InventoryItem, InventoryTxn, Partner, StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
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
            PartnerCreate(name=f"VERIFY-CRUMB-SO-API {tag} {unique}", is_customer=True),
        )
        return partner.id


async def _make_stocked_item(session_factory, unique: str, main_id: int) -> str:
    """Create a SYERP InventoryItem and receipt 100 on-hand (so a confirm can reserve)."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-CRUMB-SO-API ITEM {unique}",
                unit_of_measure="ea",
            ),
        )
        item_id = item.id
    async with session_factory() as session:
        await post_receipt(
            session, item_id, main_id, Decimal("100"), Decimal("5"), str(uuid.uuid4())
        )
    return item_id


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    partner_ids: set[str] = set()
    item_ids: set[str] = set()
    so_ids: set[str] = set()
    quote_ids: set[str] = set()
    user_ids: list[str] = []
    role_ids: list[int] = []

    writer_id: str | None = None
    reader_id: str | None = None
    noperm_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Setup: seed (idempotent) the "Main" location; mint the three throwaway
        # users (writer = read+write, reader = read-only, noperm = no roles) and a
        # customer + stocked item so a confirm can actually soft-reserve.
        # -------------------------------------------------------------------
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
                name=f"verify-crumb-so-writer-{unique}",
                description="VERIFY throwaway role: crumb:read + crumb:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["crumb:read"], perms["crumb:write"]]
            )

            reader_role = Role(
                name=f"verify-crumb-so-reader-{unique}",
                description="VERIFY throwaway role: crumb:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["crumb:read"])

            writer = User(
                email=f"verify-crumb-so-writer-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-so-writer-pw"),
                full_name="VERIFY crumb:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-crumb-so-reader-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-so-reader-pw"),
                full_name="VERIFY crumb:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-crumb-so-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-crumb-so-noperm-pw"),
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
        item_id = await _make_stocked_item(session_factory, unique, main_id)
        item_ids.add(item_id)

        # ===================================================================
        # (A) SALES ORDER create over HTTP (writer) + attributable audit (SC5).
        #     A single stock-item line (qty 10) on a 100-on-hand item, so the
        #     confirm below can soft-reserve the full quantity.
        # ===================================================================
        create_body = {
            "partner_id": cust_id,
            "lines": [{"item_id": item_id, "qty_ordered": "10", "unit_price": "5"}],
        }
        s, body = http("POST", "/sales-orders", writer_token, create_body)
        so1_id = body.get("id") if isinstance(body, dict) else None
        if so1_id:
            so_ids.add(so1_id)
        so1_line_id = (
            body["lines"][0]["id"]
            if isinstance(body, dict) and body.get("lines")
            else None
        )
        check(
            "(A) POST /crumb/sales-orders with crumb:write → 201 with a Draft SO and a "
            "SO-#### number",
            s == 201
            and so1_id is not None
            and body.get("status") == "draft"
            and str(body.get("so_number", "")).startswith("SO-"),
            f"status={s} body={body!r}",
        )
        created_audit = await _audit_row(session_factory, "sales_order.created", so1_id)
        check(
            "(A/SC5) a sales_order.created audit row exists, attributable to the writer, "
            "targeting the created SO",
            created_audit is not None
            and created_audit.actor_id == writer_id
            and created_audit.target_type == "sales_order",
            f"audit={created_audit!r}",
        )

        # ===================================================================
        # (B) DRAFT-only line editors over HTTP (writer) — add / update / delete a
        #     SECOND line (the section-A line survives for the confirm) + their audit.
        # ===================================================================
        s, body = http(
            "POST", f"/sales-orders/{so1_id}/lines", writer_token,
            {"item_id": item_id, "qty_ordered": "2", "unit_price": "5"},
        )
        so1_line2_id = body.get("id") if isinstance(body, dict) else None
        check(
            "(B) POST /crumb/sales-orders/{id}/lines with crumb:write → 201 with a new line",
            s == 201 and so1_line2_id is not None,
            f"status={s} body={body!r}",
        )
        line_added_audit = await _audit_row(session_factory, "sales_order.line_added", so1_id)
        check(
            "(B/SC5) a sales_order.line_added audit row exists, attributable to the writer",
            line_added_audit is not None
            and line_added_audit.actor_id == writer_id
            and line_added_audit.target_type == "sales_order",
            f"audit={line_added_audit!r}",
        )

        s, body = http(
            "PATCH", f"/sales-orders/{so1_id}/lines/{so1_line2_id}", writer_token,
            {"item_id": item_id, "qty_ordered": "3", "unit_price": "5"},
        )
        check(
            "(B) PATCH /crumb/sales-orders/{id}/lines/{line} with crumb:write → 200, qty 3",
            s == 200 and isinstance(body, dict) and Decimal(str(body.get("qty_ordered"))) == Decimal("3"),
            f"status={s} body={body!r}",
        )
        line_updated_audit = await _audit_row(
            session_factory, "sales_order.line_updated", so1_id
        )
        check(
            "(B/SC5) a sales_order.line_updated audit row exists, attributable to the writer",
            line_updated_audit is not None
            and line_updated_audit.actor_id == writer_id
            and line_updated_audit.target_type == "sales_order",
            f"audit={line_updated_audit!r}",
        )

        s, _ = http(
            "DELETE", f"/sales-orders/{so1_id}/lines/{so1_line2_id}", writer_token
        )
        check(
            "(B) DELETE /crumb/sales-orders/{id}/lines/{line} with crumb:write → 204",
            s == 204,
            f"status={s}",
        )
        line_deleted_audit = await _audit_row(
            session_factory, "sales_order.line_deleted", so1_id
        )
        check(
            "(B/SC5) a sales_order.line_deleted audit row exists, attributable to the writer",
            line_deleted_audit is not None
            and line_deleted_audit.actor_id == writer_id
            and line_deleted_audit.target_type == "sales_order",
            f"audit={line_deleted_audit!r}",
        )

        # ===================================================================
        # (C) CONFIRM over HTTP (writer) — soft-reserves the full 10 (100 on-hand) +
        #     attributable sales_order.confirmed audit (SC5).
        # ===================================================================
        s, body = http(
            "POST", f"/sales-orders/{so1_id}/status", writer_token,
            {"target_status": "confirmed"},
        )
        confirmed_line = (
            body["lines"][0] if isinstance(body, dict) and body.get("lines") else {}
        )
        check(
            "(C) POST /crumb/sales-orders/{id}/status target=confirmed → 200, status "
            "'confirmed', line soft-reserved 10 of 10",
            s == 200
            and isinstance(body, dict)
            and body.get("status") == "confirmed"
            and Decimal(str(confirmed_line.get("qty_reserved"))) == Decimal("10")
            and Decimal(str(confirmed_line.get("shortage"))) == Decimal("0"),
            f"status={s} body={body!r}",
        )
        confirmed_audit = await _audit_row(session_factory, "sales_order.confirmed", so1_id)
        check(
            "(C/SC5) a sales_order.confirmed audit row exists, attributable to the writer, "
            "targeting the SO",
            confirmed_audit is not None
            and confirmed_audit.actor_id == writer_id
            and confirmed_audit.target_type == "sales_order",
            f"audit={confirmed_audit!r}",
        )

        # ===================================================================
        # (D) CANCEL over HTTP (writer) — a SEPARATE SO created + confirmed, then
        #     cancelled (releasing the reservation) + sales_order.cancelled audit (SC5).
        # ===================================================================
        s, body = http(
            "POST", "/sales-orders", writer_token,
            {
                "partner_id": cust_id,
                "lines": [{"item_id": item_id, "qty_ordered": "4", "unit_price": "5"}],
            },
        )
        so2_id = body.get("id") if isinstance(body, dict) else None
        if so2_id:
            so_ids.add(so2_id)
        check(
            "(D) POST /crumb/sales-orders (cancel fixture) with crumb:write → 201 Draft",
            s == 201 and so2_id is not None and body.get("status") == "draft",
            f"status={s} body={body!r}",
        )
        s, _ = http(
            "POST", f"/sales-orders/{so2_id}/status", writer_token,
            {"target_status": "confirmed"},
        )
        check(
            "(D) POST /crumb/sales-orders/{id}/status target=confirmed → 200 (pre-cancel)",
            s == 200,
            f"status={s}",
        )
        s, body = http(
            "POST", f"/sales-orders/{so2_id}/status", writer_token,
            {"target_status": "cancelled"},
        )
        cancelled_line = (
            body["lines"][0] if isinstance(body, dict) and body.get("lines") else {}
        )
        check(
            "(D) POST /crumb/sales-orders/{id}/status target=cancelled → 200, status "
            "'cancelled', reservation released to 0",
            s == 200
            and isinstance(body, dict)
            and body.get("status") == "cancelled"
            and Decimal(str(cancelled_line.get("qty_reserved"))) == Decimal("0"),
            f"status={s} body={body!r}",
        )
        cancelled_audit = await _audit_row(session_factory, "sales_order.cancelled", so2_id)
        check(
            "(D/SC5) a sales_order.cancelled audit row exists, attributable to the writer, "
            "targeting the SO",
            cancelled_audit is not None
            and cancelled_audit.actor_id == writer_id
            and cancelled_audit.target_type == "sales_order",
            f"audit={cancelled_audit!r}",
        )

        # ===================================================================
        # (E) QUOTE → SALES ORDER conversion over HTTP (writer): build an ACCEPTED
        #     quote (draft → sent → accepted), convert it, and assert the new SO
        #     carries a quote.converted_to_sales_order audit (target: the SO) (SC5).
        # ===================================================================
        s, body = http(
            "POST", "/quotes", writer_token,
            {
                "partner_id": cust_id,
                "lines": [{"description": f"conv-line {unique}", "quantity": "6",
                           "unit_price": "9"}],
            },
        )
        conv_quote_id = body.get("id") if isinstance(body, dict) else None
        if conv_quote_id:
            quote_ids.add(conv_quote_id)
        check(
            "(E) POST /crumb/quotes with crumb:write → 201 Draft quote (convert fixture)",
            s == 201 and conv_quote_id is not None and body.get("status") == "draft",
            f"status={s} body={body!r}",
        )
        http("POST", f"/quotes/{conv_quote_id}/status", writer_token,
             {"target_status": "sent"})
        s, body = http("POST", f"/quotes/{conv_quote_id}/status", writer_token,
                       {"target_status": "accepted"})
        check(
            "(E) quote walked draft→sent→accepted (only an accepted quote can convert)",
            s == 200 and isinstance(body, dict) and body.get("status") == "accepted",
            f"status={s} body={body!r}",
        )
        s, body = http("POST", f"/quotes/{conv_quote_id}/convert", writer_token, {})
        conv_so_id = body.get("id") if isinstance(body, dict) else None
        if conv_so_id:
            so_ids.add(conv_so_id)
        check(
            "(E) POST /crumb/quotes/{id}/convert with crumb:write → 201 with a Draft SO "
            "sourced from the quote",
            s == 201
            and conv_so_id is not None
            and body.get("status") == "draft"
            and body.get("source_quote_id") == conv_quote_id,
            f"status={s} body={body!r}",
        )
        convert_audit = await _audit_row(
            session_factory, "quote.converted_to_sales_order", conv_so_id
        )
        check(
            "(E/SC5) a quote.converted_to_sales_order audit row exists, attributable to the "
            "writer, targeting the new SO",
            convert_audit is not None
            and convert_audit.actor_id == writer_id
            and convert_audit.target_type == "sales_order",
            f"audit={convert_audit!r}",
        )

        # ===================================================================
        # (F) RBAC on every MUTATION route: a token WITHOUT crumb:write (the
        #     crumb:read-only reader) → 403; unauthenticated → 401. These auth
        #     failures short-circuit BEFORE the service, so firing them against the
        #     already-driven records cannot mutate state (SC5).
        # ===================================================================
        mutation_routes = [
            ("POST", "/sales-orders", create_body),
            ("POST", f"/sales-orders/{so1_id}/lines",
             {"item_id": item_id, "qty_ordered": "1", "unit_price": "5"}),
            ("PATCH", f"/sales-orders/{so1_id}/lines/{so1_line_id}",
             {"item_id": item_id, "qty_ordered": "1", "unit_price": "5"}),
            ("DELETE", f"/sales-orders/{so1_id}/lines/{so1_line_id}", None),
            ("POST", f"/sales-orders/{so1_id}/status", {"target_status": "fulfilling"}),
            ("POST", f"/quotes/{conv_quote_id}/convert", {}),
        ]
        for method, path, payload in mutation_routes:
            s, _ = http(method, path, reader_token, payload)
            check(
                f"(F) crumb:read-only token → 403 on {method} {path} (no crumb:write)",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None, payload)
            check(
                f"(F) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

        # ===================================================================
        # (G) RBAC on every READ route: crumb:read token → 200; no-permission
        #     token → 403; unauthenticated → 401 (SC5).
        # ===================================================================
        read_routes = [
            ("GET", "/sales-orders"),
            ("GET", f"/sales-orders/{so1_id}"),
        ]
        for method, path in read_routes:
            s, _ = http(method, path, reader_token)
            check(
                f"(G) crumb:read token → 200 on {method} {path}",
                s == 200,
                f"status={s}",
            )
            s, _ = http(method, path, noperm_token)
            check(
                f"(G) no-permission token → 403 on {method} {path}",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None)
            check(
                f"(G) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

    finally:
        await _cleanup(
            session_factory,
            partner_ids,
            item_ids,
            so_ids,
            quote_ids,
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
    item_ids: set[str],
    so_ids: set[str],
    quote_ids: set[str],
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: SO lines -> sales orders -> quote
    lines -> quotes -> inventory txns -> inventory items -> partners -> the
    audit_log rows targeting the SO / quote records -> throwaway users -> throwaway
    roles. The seeded "Main" location is reused and left in place.
    """
    async with session_factory() as session:
        so_list = list(so_ids)
        q_list = list(quote_ids)
        item_list = list(item_ids)
        pa_list = list(partner_ids)
        # sales_order.* + quote.converted_to_sales_order target the SO; quote.*
        # (created/status_changed) target the quote — clear both id sets.
        audit_targets = so_list + q_list

        if so_list:
            await session.execute(
                delete(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(so_list))
            )
            await session.execute(delete(SalesOrder).where(SalesOrder.id.in_(so_list)))
        if q_list:
            await session.execute(delete(QuoteLine).where(QuoteLine.quote_id.in_(q_list)))
            await session.execute(delete(Quote).where(Quote.id.in_(q_list)))
        if item_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list))
            )
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_list))
            )
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
