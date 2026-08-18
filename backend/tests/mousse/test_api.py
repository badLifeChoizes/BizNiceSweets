# ABOUTME: HTTP client-layer port of verify_mousse_api.py (SC3) — the MOUSSE RBAC + audit crux.
# ABOUTME: Drives POST/GET /api/v1/mousse/work-orders through the ASGI client, proving the 401/403/201 triad + an attributable work_order.created AuditLog row.
"""
MOUSSE router RBAC + audit crux — ported from ``backend/scripts/verify_mousse_api.py``
to the ``client`` (httpx-ASGI) layer (SC3).

WHY THIS EXISTS (the router proof — the companion to test_work_orders.py):
  test_work_orders.py drives the mousse SERVICE functions directly and so proves the
  costing/FSM numbers, but it can never exercise the two things that live only in the
  ROUTER: the audit row written by ``write_audit`` and the RBAC gate enforced by
  ``require_permission("mousse:read" / "mousse:write")``. This test closes that gap by
  making REAL HTTP calls against the ASGI app and asserting, on the create + one read
  route:
    - POST /mousse/work-orders accepts a mousse:write token (201, Draft WO), refuses a
      token WITHOUT mousse:write (403 — the mousse:read-only reader), and refuses an
      unauthenticated request (401);
    - after the 201, the matching ``work_order.created`` AuditLog row exists, is
      attributable to the acting writer (actor_id), and targets the created WO
      (target_type="work_order", target_id == the WO id);
    - GET /mousse/work-orders accepts a mousse:read token (200), refuses a
      no-permission token (403), and refuses an unauthenticated request (401).

require_permission reads the user's ROLES from the DB (not the JWT perms claim, D-P2a-4),
so a genuine 403 requires a REAL limited User bound to a Role holding only the read scope.
This mints THREE throwaway identities in a LOCAL per-test fixture (D-P2b-4) on the clean
per-test DB (created AFTER _isolate; the next test's TRUNCATE sweeps them):
  * writer — role holding mousse:read + mousse:write (the 201; the audit row is
             attributable to THIS user);
  * reader — role holding ONLY mousse:read (200 on the read, 403 on the create);
  * noperm — no roles at all (403 on the read, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.plum.models import PlumBomItem, PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import StockLocation
from app.modules.syerp.schemas import InventoryItemCreate
from app.modules.syerp.service import create_item, post_receipt

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the mousse:read/mousse:write Permission
# rows). Mirrors verify_mousse_api.py's throwaway-identity minting near-verbatim;
# no cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these rows.
# ---------------------------------------------------------------------------


@pytest.fixture
async def mousse_identities(test_sessionmaker) -> dict:
    """
    Mint three real Users bound to real Roles and return their ids + Bearer tokens.

    writer → role with mousse:read + mousse:write; reader → role with mousse:read
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
                        Permission.code.in_(["mousse:read", "mousse:write"])
                    )
                )
            ).scalars().all()
        }
        assert "mousse:read" in perms and "mousse:write" in perms, (
            "seeded mousse:read/mousse:write permissions not found"
        )

        writer_role = Role(
            name=f"test-mousse-writer-{unique}",
            description="test throwaway role: mousse:read + mousse:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["mousse:read"], perms["mousse:write"]]
        )

        reader_role = Role(
            name=f"test-mousse-reader-{unique}",
            description="test throwaway role: mousse:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["mousse:read"])

        writer = User(
            email=f"test-mousse-writer-{unique}@example.test",
            hashed_password=hash_password("test-mousse-writer-pw"),
            full_name="TEST mousse:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-mousse-reader-{unique}@example.test",
            hashed_password=hash_password("test-mousse-reader-pw"),
            full_name="TEST mousse:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-mousse-noperm-{unique}@example.test",
            hashed_password=hash_password("test-mousse-noperm-pw"),
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
# Buildable-part fixture builders — a PLUM part with a Released rev + 2-child BOM
# whose children are linked to stocked SYERP items, so the WO create targets a
# genuinely buildable part (lifted from verify_mousse_api.py::_build_buildable_part).
# ---------------------------------------------------------------------------


async def _make_part_with_revision(
    session, part_number: str, *, released: bool, uom: str = "ea"
) -> tuple[str, str]:
    """Insert a PLUM part + its revision 1 via the ORM; return (part_id, revision_id)."""
    part = PlumPart(id=str(uuid.uuid4()), part_number=part_number, active=True)
    session.add(part)
    await session.flush()
    rev = PlumPartRevision(
        id=str(uuid.uuid4()),
        part_id=part.id,
        revision_number=1,
        revision_label="A",
        status="released" if released else "draft",
        description=f"SC3 {part_number}",
        unit_of_measure=uom,
        released_at=datetime.now(UTC) if released else None,
    )
    session.add(rev)
    await session.flush()
    return part.id, rev.id


async def _link_item(session, tag: str, part_id: str | None) -> str:
    """Create a SYERP InventoryItem linked to a PLUM part and return its id."""
    item = await create_item(
        session,
        InventoryItemCreate(
            name=f"SC3 MOUSSE-API {tag} {uuid.uuid4().hex[:8]}",
            unit_of_measure="ea",
            plum_part_id=part_id,
        ),
    )
    return item.id


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


async def _build_buildable_part(session, main_id: int) -> str:
    """
    Build a fully-buildable PLUM part: Released rev + a 2-child direct BOM (qty_per
    2 & 3), each child linked to a stocked InventoryItem (100 on-hand), and a linked
    FG item for the parent. Returns the FG PLUM part id (the WO build target).
    """
    fg_part_id, fg_rev_id = await _make_part_with_revision(session, "MO-API-fg", released=True)
    child_a_id, _ = await _make_part_with_revision(session, "MO-API-ca", released=True)
    child_b_id, _ = await _make_part_with_revision(session, "MO-API-cb", released=True)
    session.add(
        PlumBomItem(
            parent_revision_id=fg_rev_id, child_part_id=child_a_id, qty=Decimal("2"), sort_order=0
        )
    )
    session.add(
        PlumBomItem(
            parent_revision_id=fg_rev_id, child_part_id=child_b_id, qty=Decimal("3"), sort_order=1
        )
    )
    await session.flush()

    await _link_item(session, "FG", fg_part_id)
    item_a_id = await _link_item(session, "CA", child_a_id)
    item_b_id = await _link_item(session, "CB", child_b_id)
    await post_receipt(session, item_a_id, main_id, Decimal("100"), Decimal("3"), ACTOR_ID)
    await post_receipt(session, item_b_id, main_id, Decimal("100"), Decimal("5"), ACTOR_ID)
    return fg_part_id


# ---------------------------------------------------------------------------
# The crux: the 401/403/201 triad + an attributable work_order.created audit row.
# ---------------------------------------------------------------------------


async def test_mousse_work_order_create_rbac_and_audit(
    client: httpx.AsyncClient,
    seeded_ledger_db,
    test_sessionmaker,
    mousse_identities: dict,
) -> None:
    """
    Port of verify_mousse_api.py's create + read RBAC/audit assertions (SC3).

    POST /api/v1/mousse/work-orders:
      - writer token (mousse:read + mousse:write) → 201 with a Draft WO id;
      - a work_order.created AuditLog row then exists, attributable to the writer
        (actor_id == writer.id), targeting the created WO (target_type="work_order",
        target_id == the WO id — string-compared as stored);
      - the mousse:read-only reader token → 403 (no mousse:write);
      - no token → 401.

    GET /api/v1/mousse/work-orders:
      - reader token (mousse:read) → 200;
      - the no-permission noperm token → 403;
      - no token → 401.
    """
    session = seeded_ledger_db
    main_id = await _main_location_id(session)
    fg_part_id = await _build_buildable_part(session, main_id)

    writer_token = mousse_identities["writer_token"]
    reader_token = mousse_identities["reader_token"]
    noperm_token = mousse_identities["noperm_token"]
    writer_id = mousse_identities["writer_id"]

    create_body = {
        "plum_part_id": fg_part_id,
        "planned_qty": "10",
        "target_location_id": main_id,
    }

    # --- writer (mousse:write) → 201 with a Draft WO id ---
    resp = await client.post(
        "/api/v1/mousse/work-orders",
        json=create_body,
        headers={"Authorization": f"Bearer {writer_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    wo_id = body["id"]
    assert body["status"] == "draft"

    # --- attributable work_order.created audit row (SC3) ---
    async with test_sessionmaker() as audit_session:
        audit = (
            await audit_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "work_order.created",
                    AuditLog.target_id == wo_id,
                )
            )
        ).scalars().first()
    assert audit is not None, "no work_order.created audit row for the created WO"
    assert audit.actor_id == writer_id
    assert audit.target_type == "work_order"
    assert audit.target_id == wo_id

    # --- mousse:read-only reader → 403 (no mousse:write) ---
    resp = await client.post(
        "/api/v1/mousse/work-orders",
        json=create_body,
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 403, resp.text

    # --- unauthenticated → 401 ---
    resp = await client.post("/api/v1/mousse/work-orders", json=create_body)
    assert resp.status_code == 401, resp.text

    # --- READ route GET /mousse/work-orders: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        "/api/v1/mousse/work-orders",
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        "/api/v1/mousse/work-orders",
        headers={"Authorization": f"Bearer {noperm_token}"},
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get("/api/v1/mousse/work-orders")
    assert resp.status_code == 401, resp.text
