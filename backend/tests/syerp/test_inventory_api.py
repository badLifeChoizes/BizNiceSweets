# ABOUTME: HTTP client-layer port of the SYERP inventory receipt RBAC + audit crux (SC3).
# ABOUTME: Drives POST /api/v1/syerp/inventory/items/{id}/receipts + the onhand read through the ASGI client, proving the 401/403/201 triad + an attributable inventory.receipt AuditLog row.
"""
SYERP inventory router RBAC + audit crux — the HTTP-layer companion to the
service-level ``test_inventory_service.py`` / ``verify_inventory.py`` (SC3).

WHY THIS EXISTS (the router proof):
  test_inventory_service.py drives the inventory SERVICE functions directly
  (post_receipt / post_adjustment / post_transfer) and so proves the moving-average
  and floor-guard cruxes, but it can never exercise the two things that live only in
  the ROUTER: the audit row written by ``write_audit`` and the RBAC gate enforced by
  ``require_permission("syerp:read" / "syerp:write")``. This test closes that gap by
  making REAL HTTP calls against the ASGI app and asserting, on the receipt mutation
  route plus one read route:
    - POST /syerp/inventory/items/{id}/receipts accepts a syerp:write token (201, a
      receipt ledger row), refuses a token WITHOUT syerp:write (403 — the
      syerp:read-only reader), and refuses an unauthenticated request (401);
    - after the 201, the matching ``inventory.receipt`` AuditLog row exists, is
      attributable to the acting writer (actor_id), and targets the created ledger
      row (target_type="inventory_txn", target_id == the txn id — compared as stored);
    - GET /syerp/inventory/items/{id}/onhand accepts a syerp:read token (200), refuses
      a no-permission token (403), and refuses an unauthenticated request (401).

require_permission reads the user's ROLES from the DB (not the JWT perms claim, D-P2a-4),
so a genuine 403 requires a REAL limited User bound to a Role holding only the read scope.
This mints THREE throwaway identities in a LOCAL per-test fixture (D-P2b-4) on the clean
per-test DB (created AFTER _isolate; the next test's TRUNCATE sweeps them):
  * writer — role holding syerp:read + syerp:write (the 201; the audit row is
             attributable to THIS user);
  * reader — role holding ONLY syerp:read (200 on the read, 403 on the receipt);
  * noperm — no roles at all (403 on the read, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.

The receipt route needs a real inventory item and a stock location: the item is created
via the service on seeded_ledger_db, and the seeded "Main" location (provisioned by
seeded_ledger_db) is the receipt target.
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
from app.modules.syerp.schemas import InventoryItemCreate
from app.modules.syerp.service import create_item

# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the syerp:read/syerp:write Permission
# rows). Mirrors test_ar_api.py's throwaway-identity minting near-verbatim; no
# cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these rows.
# ---------------------------------------------------------------------------


@pytest.fixture
async def inventory_identities(test_sessionmaker) -> dict:
    """
    Mint three real Users bound to real Roles and return their ids + Bearer tokens.

    writer → role with syerp:read + syerp:write; reader → role with syerp:read
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
                        Permission.code.in_(["syerp:read", "syerp:write"])
                    )
                )
            ).scalars().all()
        }
        assert "syerp:read" in perms and "syerp:write" in perms, (
            "seeded syerp:read/syerp:write permissions not found"
        )

        writer_role = Role(
            name=f"test-inv-writer-{unique}",
            description="test throwaway role: syerp:read + syerp:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["syerp:read"], perms["syerp:write"]]
        )

        reader_role = Role(
            name=f"test-inv-reader-{unique}",
            description="test throwaway role: syerp:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["syerp:read"])

        writer = User(
            email=f"test-inv-writer-{unique}@example.test",
            hashed_password=hash_password("test-inv-writer-pw"),
            full_name="TEST syerp:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-inv-reader-{unique}@example.test",
            hashed_password=hash_password("test-inv-reader-pw"),
            full_name="TEST syerp:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-inv-noperm-{unique}@example.test",
            hashed_password=hash_password("test-inv-noperm-pw"),
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


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


# ---------------------------------------------------------------------------
# The crux: the 401/403/201 triad + an attributable inventory.receipt audit row.
# ---------------------------------------------------------------------------


async def test_inventory_receipt_rbac_and_audit(
    client: httpx.AsyncClient,
    seeded_ledger_db,
    test_sessionmaker,
    inventory_identities: dict,
) -> None:
    """
    HTTP-layer RBAC/audit proof for the inventory receipt mutation route (SC3).

    POST /api/v1/syerp/inventory/items/{id}/receipts:
      - writer token (syerp:read + syerp:write) → 201 with a receipt ledger row
        (txn_type "receipt", quantity 10);
      - an inventory.receipt AuditLog row then exists, attributable to the writer
        (actor_id == writer.id), targeting the created txn (target_type="inventory_txn",
        target_id == the txn id — compared as stored);
      - the syerp:read-only reader token → 403 (no syerp:write);
      - no token → 401.

    GET /api/v1/syerp/inventory/items/{id}/onhand:
      - reader token (syerp:read) → 200;
      - the no-permission noperm token → 403;
      - no token → 401.
    """
    session = seeded_ledger_db
    unique = uuid.uuid4().hex[:8]
    main_id = await _main_location_id(session)

    item = await create_item(
        session,
        InventoryItemCreate(name=f"SC3 Inv-API Widget {unique}", unit_of_measure="ea"),
    )
    item_id = item.id

    writer_token = inventory_identities["writer_token"]
    reader_token = inventory_identities["reader_token"]
    noperm_token = inventory_identities["noperm_token"]
    writer_id = inventory_identities["writer_id"]

    receipt_body = {
        "location_id": main_id,
        "qty": "10",
        "unit_cost": "2",
    }

    # --- writer (syerp:write) → 201 with a receipt ledger row ---
    resp = await client.post(
        f"/api/v1/syerp/inventory/items/{item_id}/receipts",
        json=receipt_body,
        headers={"Authorization": f"Bearer {writer_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    txn_id = body["id"]
    assert body["txn_type"] == "receipt"
    assert Decimal(str(body["quantity"])) == Decimal("10")

    # --- attributable inventory.receipt audit row (SC3) ---
    async with test_sessionmaker() as audit_session:
        audit = (
            await audit_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "inventory.receipt",
                    AuditLog.target_id == txn_id,
                )
            )
        ).scalars().first()
    assert audit is not None, "no inventory.receipt audit row for the posted receipt"
    assert audit.actor_id == writer_id
    assert audit.target_type == "inventory_txn"
    assert audit.target_id == txn_id

    # --- syerp:read-only reader → 403 (no syerp:write) ---
    resp = await client.post(
        f"/api/v1/syerp/inventory/items/{item_id}/receipts",
        json=receipt_body,
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403, resp.text

    # --- unauthenticated → 401 ---
    resp = await client.post(
        f"/api/v1/syerp/inventory/items/{item_id}/receipts", json=receipt_body
    )
    assert resp.status_code == 401, resp.text

    # --- READ route GET onhand: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        f"/api/v1/syerp/inventory/items/{item_id}/onhand",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        f"/api/v1/syerp/inventory/items/{item_id}/onhand",
        headers={"Authorization": f"Bearer {noperm_token}"},
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"/api/v1/syerp/inventory/items/{item_id}/onhand")
    assert resp.status_code == 401, resp.text
