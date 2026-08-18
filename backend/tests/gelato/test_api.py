# ABOUTME: HTTP client-layer port of verify_gelato_ship_api.py (SC3) — the GELATO shipment RBAC + audit crux.
# ABOUTME: Drives POST /api/v1/gelato/shipments/pick + GET /shipments/{id} through the ASGI client, proving the 401/403/200 triad + an attributable shipment.picked AuditLog row (int-PK→VARCHAR(36) round-trip guard).
"""
GELATO shipment router RBAC + audit crux — ported from
``backend/scripts/verify_gelato_ship_api.py`` to the ``client`` (httpx-ASGI) layer (SC3).

WHY THIS EXISTS (the router proof — the companion to test_shipments.py):
  test_shipments.py drives the gelato SERVICE functions directly and so proves the
  ship-COGS accounting crux (the balanced JE, reservation relief, partial-ship), but
  it can never exercise the two things that live only in the ROUTER: the audit row
  written by ``write_audit`` and the RBAC gate enforced by
  ``require_permission("gelato:read" / "gelato:write")``. This test closes that gap by
  making REAL HTTP calls against the ASGI app and asserting, on the pick mutation + one
  read route:
    - POST /gelato/shipments/pick accepts a gelato:write token (200, shipment in
      'picking'), refuses a token WITHOUT gelato:write (403 — the gelato:read-only
      reader), and refuses an unauthenticated request (401);
    - after the 200, the matching ``shipment.picked`` AuditLog row exists, is
      attributable to the acting writer (actor_id), and targets the created shipment
      (target_type="shipment", target_id == str(shipment.id) — the Shipment PK is an
      autoincrement INTEGER, so the router str()s it into the VARCHAR(36) column; this
      asserts that round-trip, the 12a int-PK regression guard);
    - GET /gelato/shipments/{id} accepts a gelato:read token (200), refuses a
      no-permission token (403), and refuses an unauthenticated request (401).

require_permission reads the user's ROLES from the DB (not the JWT perms claim, D-P2a-4),
so a genuine 403 requires a REAL limited User bound to a Role holding only the read scope.
This mints THREE throwaway identities in a LOCAL per-test fixture (D-P2b-4) on the clean
per-test DB (created AFTER _isolate; the next test's TRUNCATE sweeps them):
  * writer — role holding gelato:read + gelato:write (the 200; the audit row is
             attributable to THIS user);
  * reader — role holding ONLY gelato:read (200 on the read, 403 on the pick);
  * noperm — no roles at all (403 on the read, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.

A pickable shipment needs a CONFIRMED single-line SO whose line is reserved and a pick
bin holding stock, so the setup drives the REAL gelato/crumb/syerp flow (receipts →
create_bin → putaway → create_sales_order → confirm_sales_order) exactly as
verify_gelato_ship_api.py and test_shipments.py::_seed_confirmed_order do — the pick
route will not 200 without it.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.gelato.schemas import BinCreate, PutawayRequest
from app.modules.gelato.service import create_bin, execute_putaway
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the gelato:read/gelato:write Permission
# rows). Mirrors verify_gelato_ship_api.py's throwaway-identity minting near-verbatim;
# no cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these rows.
# ---------------------------------------------------------------------------


@pytest.fixture
async def gelato_identities(test_sessionmaker) -> dict:
    """
    Mint three real Users bound to real Roles and return their ids + Bearer tokens.

    writer → role with gelato:read + gelato:write; reader → role with gelato:read
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
                        Permission.code.in_(["gelato:read", "gelato:write"])
                    )
                )
            ).scalars().all()
        }
        assert "gelato:read" in perms and "gelato:write" in perms, (
            "seeded gelato:read/gelato:write permissions not found"
        )

        writer_role = Role(
            name=f"test-gelato-writer-{unique}",
            description="test throwaway role: gelato:read + gelato:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["gelato:read"], perms["gelato:write"]]
        )

        reader_role = Role(
            name=f"test-gelato-reader-{unique}",
            description="test throwaway role: gelato:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["gelato:read"])

        writer = User(
            email=f"test-gelato-writer-{unique}@example.test",
            hashed_password=hash_password("test-gelato-writer-pw"),
            full_name="TEST gelato:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-gelato-reader-{unique}@example.test",
            hashed_password=hash_password("test-gelato-reader-pw"),
            full_name="TEST gelato:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-gelato-noperm-{unique}@example.test",
            hashed_password=hash_password("test-gelato-noperm-pw"),
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
# Pickable-shipment fixture builder — a customer, an item with two receipts (so
# moving_avg is off 1.0), a pick bin holding stock, a staging bin, and a CONFIRMED
# single-line SO whose line is reserved and pickable. Lifted from
# verify_gelato_ship_api.py's fixture block / test_shipments.py::_seed_confirmed_order
# onto the single test session — the pick route will not 200 without a pickable SO.
# ---------------------------------------------------------------------------


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


async def _seed_pickable_order(session, main_id: int, unique: str) -> dict:
    """
    Seed one shippable order and return the handles the pick payload is built from.

    A customer, an item with two receipts (100@6 then 100@9 → moving_avg 7.5, off
    1.0), a pick bin holding 50, a staging bin, and a CONFIRMED single-line SO
    ordering 8 (its line is reserved and pickable). Driven through the REAL
    gelato/crumb/syerp service flow, exactly as verify_gelato_ship_api.py does.
    """
    customer = await create_partner(
        session,
        PartnerCreate(name=f"SC3 GELATO-API cust {unique}", is_customer=True),
    )
    item = await create_item(
        session,
        InventoryItemCreate(name=f"SC3 GELATO-API item {unique}", unit_of_measure="ea"),
    )
    for qty, cost in ((Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))):
        await post_receipt(session, item.id, main_id, qty, cost, ACTOR_ID)

    pick_bin = await create_bin(
        session, BinCreate(location_id=main_id, code=f"SHIP-PICK-{unique}")
    )
    staging_bin = await create_bin(
        session, BinCreate(location_id=main_id, code=f"SHIP-STAGE-{unique}")
    )
    await execute_putaway(
        session,
        PutawayRequest(
            item_id=item.id, location_id=main_id, to_bin_id=pick_bin.id,
            qty=Decimal("50"), from_bin_id=None,
        ),
        ACTOR_ID,
    )

    so = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=customer.id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item.id, qty_ordered=Decimal("8"), unit_price=Decimal("20")
                )
            ],
        ),
        ACTOR_ID,
    )
    confirmed = await confirm_sales_order(session, so.id, ACTOR_ID)

    return {
        "so_id": so.id,
        "so_line_id": confirmed.lines[0].id,
        "pick_bin_id": pick_bin.id,
        "staging_bin_id": staging_bin.id,
    }


# ---------------------------------------------------------------------------
# The crux: the 401/403/200 triad + an attributable shipment.picked audit row
# whose target_id round-trips as the shipment-id STRING (the int-PK guard).
# ---------------------------------------------------------------------------


async def test_gelato_shipment_pick_rbac_and_audit(
    client: httpx.AsyncClient,
    seeded_ledger_db,
    test_sessionmaker,
    gelato_identities: dict,
) -> None:
    """
    Port of verify_gelato_ship_api.py's pick + read RBAC/audit assertions (SC3).

    POST /api/v1/gelato/shipments/pick:
      - writer token (gelato:read + gelato:write) → 200 with a shipment in 'picking';
      - a shipment.picked AuditLog row then exists, attributable to the writer
        (actor_id == writer.id), targeting the created shipment (target_type="shipment",
        target_id == str(shipment.id) — the int PK coerced into VARCHAR(36), the 12a
        regression guard);
      - the gelato:read-only reader token → 403 (no gelato:write);
      - no token → 401.

    GET /api/v1/gelato/shipments/{id}:
      - reader token (gelato:read) → 200;
      - the no-permission noperm token → 403;
      - no token → 401.
    """
    session = seeded_ledger_db
    unique = uuid.uuid4().hex[:8]
    main_id = await _main_location_id(session)
    order = await _seed_pickable_order(session, main_id, unique)

    writer_token = gelato_identities["writer_token"]
    reader_token = gelato_identities["reader_token"]
    noperm_token = gelato_identities["noperm_token"]
    writer_id = gelato_identities["writer_id"]

    pick_body = {
        "sales_order_id": order["so_id"],
        "staging_bin_id": order["staging_bin_id"],
        "lines": [
            {
                "sales_order_line_id": order["so_line_id"],
                "from_bin_id": order["pick_bin_id"],
                "qty": "8",
            }
        ],
    }

    # --- writer (gelato:write) → 200 with a shipment in 'picking' ---
    resp = await client.post(
        "/api/v1/gelato/shipments/pick",
        json=pick_body,
        headers={"Authorization": f"Bearer {writer_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    shipment_id = body["id"]
    assert body["status"] == "picking"

    # --- attributable shipment.picked audit row (SC3); target_id round-trips as the
    #     shipment-id STRING (int PK → VARCHAR(36), the 12a int-PK regression guard) ---
    target_str = str(shipment_id)
    async with test_sessionmaker() as audit_session:
        audit = (
            await audit_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "shipment.picked",
                    AuditLog.target_id == target_str,
                )
            )
        ).scalars().first()
    assert audit is not None, "no shipment.picked audit row for the picked shipment"
    assert audit.actor_id == writer_id
    assert audit.target_type == "shipment"
    assert audit.target_id == target_str
    assert isinstance(audit.target_id, str)

    # --- gelato:read-only reader → 403 (no gelato:write) ---
    resp = await client.post(
        "/api/v1/gelato/shipments/pick",
        json=pick_body,
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403, resp.text

    # --- unauthenticated → 401 ---
    resp = await client.post("/api/v1/gelato/shipments/pick", json=pick_body)
    assert resp.status_code == 401, resp.text

    # --- READ route GET /gelato/shipments/{id}: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        f"/api/v1/gelato/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == shipment_id

    resp = await client.get(
        f"/api/v1/gelato/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {noperm_token}"},
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"/api/v1/gelato/shipments/{shipment_id}")
    assert resp.status_code == 401, resp.text
