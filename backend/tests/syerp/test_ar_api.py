# ABOUTME: HTTP client-layer port of verify_ar_api.py (SC3) — the SYERP AR invoice RBAC + audit crux.
# ABOUTME: Drives POST /api/v1/syerp/ar/invoices + GET /ar/aging through the ASGI client, proving the 401/403/201 triad + an attributable invoice.created AuditLog row.
"""
SYERP AR invoice router RBAC + audit crux — ported from
``backend/scripts/verify_ar_api.py`` to the ``client`` (httpx-ASGI) layer (SC3).

WHY THIS EXISTS (the router proof — the companion to test_ar.py):
  test_ar.py drives the AR SERVICE functions directly and so proves the posting-ties
  crux (create_invoice locking the SO line price, post_invoice's balanced JE, the
  aging↔1120 tie), but it can never exercise the two things that live only in the
  ROUTER: the audit row written by ``write_audit`` and the RBAC gate enforced by
  ``require_permission("syerp:read" / "syerp:write")``. This test closes that gap by
  making REAL HTTP calls against the ASGI app and asserting, on the create + one read
  route:
    - POST /syerp/ar/invoices accepts a syerp:write token (201, a draft invoice),
      refuses a token WITHOUT syerp:write (403 — the syerp:read-only reader), and
      refuses an unauthenticated request (401);
    - after the 201, the matching ``invoice.created`` AuditLog row exists, is
      attributable to the acting writer (actor_id), and targets the created invoice
      (target_type="invoice", target_id == the invoice id — string-compared as stored);
    - GET /syerp/ar/aging accepts a syerp:read token (200), refuses a no-permission
      token (403), and refuses an unauthenticated request (401).

require_permission reads the user's ROLES from the DB (not the JWT perms claim, D-P2a-4),
so a genuine 403 requires a REAL limited User bound to a Role holding only the read scope.
This mints THREE throwaway identities in a LOCAL per-test fixture (D-P2b-4) on the clean
per-test DB (created AFTER _isolate; the next test's TRUNCATE sweeps them):
  * writer — role holding syerp:read + syerp:write (the 201; the audit row is
             attributable to THIS user);
  * reader — role holding ONLY syerp:read (200 on the read, 403 on the create);
  * noperm — no roles at all (403 on the read, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.

A genuinely-shipped SO line is a hard precondition: create_invoice draws its invoiced
quantity off a live-recomputed uninvoiced SHIPPED quantity, so the setup drives the REAL
GELATO flow (post_receipt → create_bin → putaway → create_sales_order /
confirm_sales_order → execute_pick → execute_pack → execute_ship) exactly as
verify_ar_api.py and test_ar.py::_seed_shipped_line do — the create route will not 201
without a real shipped-but-uninvoiced line.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
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
from app.modules.syerp.models import StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the syerp:read/syerp:write Permission
# rows). Mirrors verify_ar_api.py's throwaway-identity minting near-verbatim;
# no cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these rows.
# ---------------------------------------------------------------------------


@pytest.fixture
async def ar_identities(test_sessionmaker) -> dict:
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
            name=f"test-ar-writer-{unique}",
            description="test throwaway role: syerp:read + syerp:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["syerp:read"], perms["syerp:write"]]
        )

        reader_role = Role(
            name=f"test-ar-reader-{unique}",
            description="test throwaway role: syerp:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["syerp:read"])

        writer = User(
            email=f"test-ar-writer-{unique}@example.test",
            hashed_password=hash_password("test-ar-writer-pw"),
            full_name="TEST syerp:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-ar-reader-{unique}@example.test",
            hashed_password=hash_password("test-ar-reader-pw"),
            full_name="TEST syerp:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-ar-noperm-{unique}@example.test",
            hashed_password=hash_password("test-ar-noperm-pw"),
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
# Shipped-line fixture builder — a customer's item with stock, a pick bin, and a
# CONFIRMED single-line SO driven pick → pack → SHIP so qty_shipped is stamped and
# the invoice picker surfaces it. Lifted from test_ar.py::_seed_shipped_line /
# verify_ar_api.py::_seed_shipped_line onto the single test session — the create
# route will not 201 without a genuinely shipped-but-uninvoiced line.
# ---------------------------------------------------------------------------


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


async def _seed_shipped_line(
    session, location_id: int, cust_id: str, unique: str
) -> dict:
    """
    Seed one GENUINELY-shipped SO line by driving the REAL flow end-to-end: an item
    with stock, a pick bin holding 50, a CONFIRMED single-line SO for 8 @ price 20,
    then pick → pack → SHIP 8 through the REAL GELATO service so qty_shipped is stamped
    and the invoice picker surfaces it. Returns the handles the AR create body needs.
    """
    item = await create_item(
        session,
        InventoryItemCreate(name=f"SC3 AR-API Widget {unique}", unit_of_measure="ea"),
    )
    await post_receipt(session, item.id, location_id, Decimal("100"), Decimal("10"), ACTOR_ID)

    pick_bin = await create_bin(
        session, BinCreate(location_id=location_id, code=f"AR-API-PICK-{unique}")
    )
    staging_bin = await create_bin(
        session, BinCreate(location_id=location_id, code=f"AR-API-STAGE-{unique}")
    )
    await execute_putaway(
        session,
        PutawayRequest(
            item_id=item.id, location_id=location_id, to_bin_id=pick_bin.id,
            qty=Decimal("50"), from_bin_id=None,
        ),
        ACTOR_ID,
    )

    so = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust_id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item.id, qty_ordered=Decimal("8"), unit_price=Decimal("20")
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
                    sales_order_line_id=so_line_id, from_bin_id=pick_bin.id, qty=Decimal("8")
                )
            ],
        ),
        ACTOR_ID,
    )
    await execute_pack(session, picked.id, PackRequest(), ACTOR_ID)
    await execute_ship(session, picked.id, ACTOR_ID)

    return {"item_id": item.id, "so_id": so.id, "so_line_id": so_line_id}


# ---------------------------------------------------------------------------
# The crux: the 401/403/201 triad + an attributable invoice.created audit row.
# ---------------------------------------------------------------------------


async def test_ar_invoice_create_rbac_and_audit(
    client: httpx.AsyncClient,
    seeded_ledger_db,
    test_sessionmaker,
    ar_identities: dict,
) -> None:
    """
    Port of verify_ar_api.py's create + read RBAC/audit assertions (SC3).

    POST /api/v1/syerp/ar/invoices:
      - writer token (syerp:read + syerp:write) → 201 with a draft invoice id (total 160);
      - an invoice.created AuditLog row then exists, attributable to the writer
        (actor_id == writer.id), targeting the created invoice (target_type="invoice",
        target_id == the invoice id — compared as stored);
      - the syerp:read-only reader token → 403 (no syerp:write);
      - no token → 401.

    GET /api/v1/syerp/ar/aging:
      - reader token (syerp:read) → 200;
      - the no-permission noperm token → 403;
      - no token → 401.
    """
    session = seeded_ledger_db
    unique = uuid.uuid4().hex[:8]
    main_id = await _main_location_id(session)

    customer = await create_partner(
        session, PartnerCreate(name=f"SC3 AR-API Customer {unique}", is_customer=True)
    )
    shipped = await _seed_shipped_line(session, main_id, customer.id, unique)

    writer_token = ar_identities["writer_token"]
    reader_token = ar_identities["reader_token"]
    noperm_token = ar_identities["noperm_token"]
    writer_id = ar_identities["writer_id"]

    invoice_body = {
        "customer_id": customer.id,
        "sales_order_id": shipped["so_id"],
        "invoice_date": date.today().isoformat(),
        "lines": [{"sales_order_line_id": shipped["so_line_id"], "invoiced_qty": "8"}],
    }

    # --- writer (syerp:write) → 201 with a draft invoice id (total 160) ---
    resp = await client.post(
        "/api/v1/syerp/ar/invoices",
        json=invoice_body,
        headers={"Authorization": f"Bearer {writer_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    invoice_id = body["id"]
    assert body["status"] == "draft"
    assert Decimal(str(body["total"])) == Decimal("160")

    # --- attributable invoice.created audit row (SC3) ---
    async with test_sessionmaker() as audit_session:
        audit = (
            await audit_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "invoice.created",
                    AuditLog.target_id == invoice_id,
                )
            )
        ).scalars().first()
    assert audit is not None, "no invoice.created audit row for the created invoice"
    assert audit.actor_id == writer_id
    assert audit.target_type == "invoice"
    assert audit.target_id == invoice_id

    # --- syerp:read-only reader → 403 (no syerp:write) ---
    resp = await client.post(
        "/api/v1/syerp/ar/invoices",
        json=invoice_body,
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403, resp.text

    # --- unauthenticated → 401 ---
    resp = await client.post("/api/v1/syerp/ar/invoices", json=invoice_body)
    assert resp.status_code == 401, resp.text

    # --- READ route GET /syerp/ar/aging: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        "/api/v1/syerp/ar/aging",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        "/api/v1/syerp/ar/aging",
        headers={"Authorization": f"Bearer {noperm_token}"},
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get("/api/v1/syerp/ar/aging")
    assert resp.status_code == 401, resp.text
