# ABOUTME: HTTP client-layer port of verify_crumb_so_api.py (SC3) — the CRUMB sales-order RBAC + audit crux.
# ABOUTME: Drives POST/GET /api/v1/crumb/sales-orders through the ASGI client, proving the 401/403/201 triad + an attributable sales_order.created AuditLog row.
"""
CRUMB sales-order router RBAC + audit crux — ported from
``backend/scripts/verify_crumb_so_api.py`` to the ``client`` (httpx-ASGI) layer (SC3).

WHY THIS EXISTS (the router proof — the companion to test_sales_orders.py):
  test_sales_orders.py drives the crumb sales-order SERVICE functions directly and so
  proves the SO-#### numbering / FSM / soft-reservation math, but it can never exercise
  the two things that live only in the ROUTER: the audit row written by ``write_audit``
  and the RBAC gate enforced by ``require_permission("crumb:read" / "crumb:write")``.
  This test closes that gap by making REAL HTTP calls against the ASGI app and asserting,
  on the create + one read route:
    - POST /crumb/sales-orders accepts a crumb:write token (201, Draft SO with a SO-####
      number), refuses a token WITHOUT crumb:write (403 — the crumb:read-only reader),
      and refuses an unauthenticated request (401);
    - after the 201, the matching ``sales_order.created`` AuditLog row exists, is
      attributable to the acting writer (actor_id), and targets the created SO
      (target_type="sales_order", target_id == the SO id);
    - GET /crumb/sales-orders accepts a crumb:read token (200), refuses a
      no-permission token (403), and refuses an unauthenticated request (401).

require_permission reads the user's ROLES from the DB (not the JWT perms claim, D-P2a-4),
so a genuine 403 requires a REAL limited User bound to a Role holding only the read scope.
This mints THREE throwaway identities in a LOCAL per-test fixture (D-P2b-4) on the clean
per-test DB (created AFTER _isolate; the next test's TRUNCATE sweeps them):
  * writer — role holding crumb:read + crumb:write (the 201; the audit row is
             attributable to THIS user);
  * reader — role holding ONLY crumb:read (200 on the read, 403 on the create);
  * noperm — no roles at all (403 on the read, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.

The sales order is built DIRECTLY over the create route with an inline SYERP customer +
stocked InventoryItem line (as verify_crumb_so_api.py does), NOT via a lead→opportunity→
quote funnel, so no crumb_lead/crumb_opportunity rows are created.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the crumb:read/crumb:write Permission
# rows). Mirrors verify_crumb_so_api.py's throwaway-identity minting near-verbatim;
# no cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these rows.
# ---------------------------------------------------------------------------


@pytest.fixture
async def crumb_identities(test_sessionmaker) -> dict:
    """
    Mint three real Users bound to real Roles and return their ids + Bearer tokens.

    writer → role with crumb:read + crumb:write; reader → role with crumb:read
    only; noperm → no roles. Tokens are minted with create_access_token (the perms
    claim is ignored by RBAC, which authorizes from the DB roles — D-P2a-4).
    """
    unique = uuid.uuid4().hex[:8]
    async with test_sessionmaker() as session:
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
        assert "crumb:read" in perms and "crumb:write" in perms, (
            "seeded crumb:read/crumb:write permissions not found"
        )

        writer_role = Role(
            name=f"test-crumb-writer-{unique}",
            description="test throwaway role: crumb:read + crumb:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["crumb:read"], perms["crumb:write"]]
        )

        reader_role = Role(
            name=f"test-crumb-reader-{unique}",
            description="test throwaway role: crumb:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["crumb:read"])

        writer = User(
            email=f"test-crumb-writer-{unique}@example.test",
            hashed_password=hash_password("test-crumb-writer-pw"),
            full_name="TEST crumb:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-crumb-reader-{unique}@example.test",
            hashed_password=hash_password("test-crumb-reader-pw"),
            full_name="TEST crumb:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-crumb-noperm-{unique}@example.test",
            hashed_password=hash_password("test-crumb-noperm-pw"),
            full_name="TEST no-permission user",
            is_active=True,
        )
        session.add(noperm)
        await session.flush()

        await session.commit()
        writer_id, reader_id, noperm_id = writer.id, reader.id, noperm.id

    return {
        "writer_id": writer_id,
        "reader_id": reader_id,
        "noperm_id": noperm_id,
        "writer_token": create_access_token(writer_id, []),
        "reader_token": create_access_token(reader_id, []),
        "noperm_token": create_access_token(noperm_id, []),
    }


# ---------------------------------------------------------------------------
# Buildable-order fixture builders — a SYERP customer + a stocked InventoryItem,
# so the SO create targets a genuine customer with a genuine sellable line (lifted
# from verify_crumb_so_api.py::_make_customer / _make_stocked_item). Built DIRECTLY,
# NOT via a lead→opportunity→quote funnel, so no crumb_lead/crumb_opportunity rows
# leak (those tables do not truncate cleanly under the current _isolate sort).
# ---------------------------------------------------------------------------


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


async def _make_customer(session, unique: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    partner = await create_partner(
        session,
        PartnerCreate(name=f"SC3 CRUMB-API CUST {unique}", is_customer=True),
    )
    return partner.id


async def _make_stocked_item(session, unique: str, main_id: int) -> str:
    """Create a SYERP InventoryItem and receipt 100 on-hand; return its id."""
    item = await create_item(
        session,
        InventoryItemCreate(
            name=f"SC3 CRUMB-API ITEM {unique}",
            unit_of_measure="ea",
        ),
    )
    await post_receipt(
        session, item.id, main_id, Decimal("100"), Decimal("5"), str(uuid.uuid4())
    )
    return item.id


# ---------------------------------------------------------------------------
# The crux: the 401/403/201 triad + an attributable sales_order.created audit row.
# ---------------------------------------------------------------------------


async def test_crumb_sales_order_create_rbac_and_audit(
    client: httpx.AsyncClient,
    seeded_ledger_db,
    test_sessionmaker,
    crumb_identities: dict,
) -> None:
    """
    Port of verify_crumb_so_api.py's create + read RBAC/audit assertions (SC3).

    POST /api/v1/crumb/sales-orders:
      - writer token (crumb:read + crumb:write) → 201 with a Draft SO and a SO-#### number;
      - a sales_order.created AuditLog row then exists, attributable to the writer
        (actor_id == writer.id), targeting the created SO (target_type="sales_order",
        target_id == the SO id — string-compared as stored);
      - the crumb:read-only reader token → 403 (no crumb:write);
      - no token → 401.

    GET /api/v1/crumb/sales-orders:
      - reader token (crumb:read) → 200;
      - the no-permission noperm token → 403;
      - no token → 401.
    """
    session = seeded_ledger_db
    unique = uuid.uuid4().hex[:8]
    main_id = await _main_location_id(session)
    cust_id = await _make_customer(session, unique)
    item_id = await _make_stocked_item(session, unique, main_id)

    writer_token = crumb_identities["writer_token"]
    reader_token = crumb_identities["reader_token"]
    noperm_token = crumb_identities["noperm_token"]
    writer_id = crumb_identities["writer_id"]

    create_body = {
        "partner_id": cust_id,
        "lines": [{"item_id": item_id, "qty_ordered": "10", "unit_price": "5"}],
    }

    # --- writer (crumb:write) → 201 with a Draft SO and a SO-#### number ---
    resp = await client.post(
        "/api/v1/crumb/sales-orders",
        json=create_body,
        headers={"Authorization": f"Bearer {writer_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    so_id = body["id"]
    assert body["status"] == "draft"
    assert str(body["so_number"]).startswith("SO-")

    # --- attributable sales_order.created audit row (SC3) ---
    async with test_sessionmaker() as audit_session:
        audit = (
            await audit_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "sales_order.created",
                    AuditLog.target_id == so_id,
                )
            )
        ).scalars().first()
    assert audit is not None, "no sales_order.created audit row for the created SO"
    assert audit.actor_id == writer_id
    assert audit.target_type == "sales_order"
    assert audit.target_id == so_id

    # --- crumb:read-only reader → 403 (no crumb:write) ---
    resp = await client.post(
        "/api/v1/crumb/sales-orders",
        json=create_body,
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403, resp.text

    # --- unauthenticated → 401 ---
    resp = await client.post("/api/v1/crumb/sales-orders", json=create_body)
    assert resp.status_code == 401, resp.text

    # --- READ route GET /crumb/sales-orders: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        "/api/v1/crumb/sales-orders",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        "/api/v1/crumb/sales-orders",
        headers={"Authorization": f"Bearer {noperm_token}"},
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get("/api/v1/crumb/sales-orders")
    assert resp.status_code == 401, resp.text
