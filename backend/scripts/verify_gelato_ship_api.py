# ABOUTME: Router-level live-HTTP verification for the GELATO outbound pick/pack/ship
# ABOUTME: endpoints (Phase 12b, GELATO-02). Drives the RUNNING api over HTTP (stdlib urllib —
# ABOUTME: httpx is not in the image) to prove the gelato:read/gelato:write RBAC gate returns
# ABOUTME: 401/403/200 on the pick-list/pick/pack/ship routes, drives a FULL pick→pack→ship as
# ABOUTME: admin (final ship carries a non-null journal_entry_id), and that pick/pack/ship write
# ABOUTME: attributable AuditLog rows whose target_id ROUND-TRIPS as the shipment-id STRING (the
# ABOUTME: int-PK→VARCHAR(36) regression guard); exits non-zero on FAIL and self-cleans.
"""
Router-level live-HTTP verification for the GELATO ship endpoints (Phase 12b).

WHY THIS EXISTS (the router proof — the companion to verify_gelato_ship.py):
  verify_gelato_ship.py drives the gelato SERVICE functions directly and so proves
  the pick/pack/ship accounting crux (one balanced COGS JE, reservation relief, the
  concurrency barrier), but it can never exercise the two things that live only in
  the ROUTER: the audit rows written by write_audit and the RBAC gate enforced by
  require_permission("gelato:read" / "gelato:write"). This script closes that gap
  (the 9a/11a HTTP-verify discipline) by making REAL HTTP calls against the running
  api and asserting, for the pick/pack/ship routes:
    - unauthenticated → 401 on the pick-list GET and the pick/pack/ship mutations;
    - a token WITHOUT gelato:write (a gelato:read-only user) → 403 on pick/pack/ship;
    - a token WITHOUT gelato:read (a no-permission user) → 403 on the pick-list GET;
    - an admin-equivalent (gelato:read + gelato:write) drives a FULL pick → pack →
      ship over HTTP, each returning 2xx, and the final ship returns a ShipmentRead
      with a non-null journal_entry_id (the ship really posted its COGS JE);
    - after the successful ship, the AuditLog rows shipment.picked / shipment.packed
      / shipment.shipped exist, are attributable to the acting user (actor_id), and
      their target_id ROUND-TRIPS as the shipment-id STRING.

  THE REGRESSION GUARD (the 12a int-PK bug this script exists to catch): the router
  writes target_id=str(shipment.id) into AuditLog.target_id (a VARCHAR(36) column).
  The Shipment PK is an autoincrement INTEGER; a router that passed the raw int
  would 500 at the audit write AFTER the ship commit (an asyncpg DataError on the
  VARCHAR column) — the mutation would already have moved stock and posted GL, then
  blow up on the audit row. A pure service-level script never reaches that write.
  This script therefore asserts BOTH halves: the ship endpoint returns 2xx (NOT a
  500-after-commit), and the audit target_id comes back as the shipment-id string.

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so this mints THREE throwaway users backed by throwaway roles:
    * writer   — role holding gelato:read + gelato:write (drives the whole pick →
                 pack → ship over HTTP; the audit rows are attributable to THIS user);
    * reader   — role holding ONLY gelato:read (403 on every mutation);
    * noperm   — no roles at all (403 on the pick-list read, the no-permission case).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_gelato_ship.py which owns its own engine):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato_ship_api.py

The script builds its OWN throwaway SYERP fixtures via the service functions (a stock
location reused from the seeded "Main", an item with receipts so moving_avg is off 1.0,
a pick bin holding stock, a staging bin, and a CONFIRMED single-line sales order so its
line is reserved and pickable), drives the shipment over HTTP, and CLEANS UP after
itself in a finally block (shipment lines -> shipments -> gelato_shipment journal
lines/entries -> SO lines -> sales orders -> the audit_log rows it wrote -> inventory
txns -> bins -> item -> partner -> the three throwaway users + roles), so it is safe to
re-run. The seeded "Main" location and the 1130/5100 GL accounts are reused and left in
place (real deploy state).
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

# Make the backend root importable when run as a bare `python scripts/verify_gelato_ship_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.crumb.models import SalesOrder, SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.gelato.models import Bin, Shipment, ShipmentLine
from app.modules.gelato.schemas import BinCreate, PutawayRequest
from app.modules.gelato.service import create_bin, execute_putaway
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/gelato"


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
    relative to the /api/v1/gelato base. HTTP error statuses are captured and
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


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    partner_ids: set[str] = set()
    item_ids: set[str] = set()
    bin_ids: set[int] = set()
    so_ids: set[str] = set()
    shipment_ids: set[int] = set()
    audit_targets: set[str] = set()
    user_ids: list[str] = []
    role_ids: list[int] = []

    writer_id: str | None = None
    reader_id: str | None = None
    noperm_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Setup: seed (idempotent) the "Main" location; mint the three throwaway
        # users (writer = read+write, reader = read-only, noperm = no roles).
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
                            Permission.code.in_(["gelato:read", "gelato:write"])
                        )
                    )
                ).scalars().all()
            }
            if "gelato:read" not in perms or "gelato:write" not in perms:
                print("FAIL: seeded gelato:read/gelato:write permissions not found.")
                sys.exit(2)

            writer_role = Role(
                name=f"verify-gelato-ship-writer-{unique}",
                description="VERIFY throwaway role: gelato:read + gelato:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["gelato:read"], perms["gelato:write"]]
            )

            reader_role = Role(
                name=f"verify-gelato-ship-reader-{unique}",
                description="VERIFY throwaway role: gelato:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["gelato:read"])

            writer = User(
                email=f"verify-gelato-ship-writer-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-ship-writer-pw"),
                full_name="VERIFY gelato:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-gelato-ship-reader-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-ship-reader-pw"),
                full_name="VERIFY gelato:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-gelato-ship-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-ship-noperm-pw"),
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

        # -------------------------------------------------------------------
        # Fixture: a customer, an item with two receipts (100@6 then 100@9 →
        # moving_avg 7.5, off 1.0 so COGS is non-trivial), a pick bin holding 50,
        # a staging bin, and a CONFIRMED single-line SO ordering 8 (its line is
        # reserved and pickable). The writer acts as the seeding actor.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            partner = await create_partner(
                session,
                PartnerCreate(name=f"VERIFY-GELATO-SHIP-API cust {unique}", is_customer=True),
            )
            cust_id = partner.id
        partner_ids.add(cust_id)

        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(
                    name=f"VERIFY-GELATO-SHIP-API item {unique}", unit_of_measure="ea"
                ),
            )
            item_id = item.id
        item_ids.add(item_id)

        for qty, cost in ((Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))):
            async with session_factory() as session:
                await post_receipt(session, item_id, main_id, qty, cost, writer_id)

        async with session_factory() as session:
            pick_bin = await create_bin(
                session, BinCreate(location_id=main_id, code=f"SHIP-PICK-{unique}")
            )
            pick_bin_id = pick_bin.id
        async with session_factory() as session:
            staging_bin = await create_bin(
                session, BinCreate(location_id=main_id, code=f"SHIP-STAGE-{unique}")
            )
            staging_bin_id = staging_bin.id
        bin_ids.update({pick_bin_id, staging_bin_id})

        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_id, location_id=main_id, to_bin_id=pick_bin_id,
                    qty=Decimal("50"), from_bin_id=None,
                ),
                writer_id,
            )

        async with session_factory() as session:
            so = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            item_id=item_id, qty_ordered=Decimal("8"), unit_price=Decimal("20")
                        )
                    ],
                ),
                writer_id,
            )
            so_id = so.id
        so_ids.add(so_id)
        async with session_factory() as session:
            confirmed = await confirm_sales_order(session, so_id, writer_id)
            so_line_id = confirmed.lines[0].id

        pick_payload = {
            "sales_order_id": so_id,
            "staging_bin_id": staging_bin_id,
            "lines": [
                {"sales_order_line_id": so_line_id, "from_bin_id": pick_bin_id, "qty": "8"}
            ],
        }

        # ===================================================================
        # (1) 401 — no token → pick-list / pick / pack / ship all 401. The
        #     pack/ship shipment ids do not yet exist, but auth short-circuits
        #     BEFORE the service so a placeholder id is enough to prove the gate.
        # ===================================================================
        no_token_routes = [
            ("GET", f"/sales-orders/{so_id}/pick-list", None),
            ("POST", "/shipments/pick", pick_payload),
            ("POST", "/shipments/1/pack", {"overrides": []}),
            ("POST", "/shipments/1/ship", {}),
        ]
        for method, path, payload in no_token_routes:
            s, _ = http(method, path, None, payload)
            check(
                f"(1) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

        # ===================================================================
        # (3) 403 read — a token WITHOUT gelato:read (the noperm user) → 403 on
        #     the pick-list GET; the reader (gelato:read) gets 200. Done BEFORE
        #     the happy path so the SO is still 'confirmed' (pick-list gate).
        # ===================================================================
        s, _ = http("GET", f"/sales-orders/{so_id}/pick-list", noperm_token)
        check(
            "(3) no-permission token → 403 on GET /gelato/sales-orders/{id}/pick-list "
            "(no gelato:read)",
            s == 403,
            f"status={s}",
        )
        s, body = http("GET", f"/sales-orders/{so_id}/pick-list", reader_token)
        pl_line = None
        if isinstance(body, dict):
            pl_line = next(
                (ln for ln in body.get("lines", [])
                 if ln.get("sales_order_line_id") == so_line_id),
                None,
            )
        check(
            "(3) gelato:read token → 200 on GET /gelato/sales-orders/{id}/pick-list, "
            "surfacing the ordered line",
            s == 200 and pl_line is not None,
            f"status={s} body={body!r}",
        )

        # ===================================================================
        # (4) 200 HAPPY PATH — the writer (gelato:read+write) drives the FULL
        #     pick → pack → ship over HTTP, each 2xx; the final ship returns a
        #     ShipmentRead with a NON-NULL journal_entry_id (the ship posted its
        #     COGS JE, and did NOT 500 at the post-commit audit write).
        # ===================================================================
        s, body = http("POST", "/shipments/pick", writer_token, pick_payload)
        shipment_id = body.get("id") if isinstance(body, dict) else None
        if shipment_id is not None:
            shipment_ids.add(shipment_id)
            audit_targets.add(str(shipment_id))
        check(
            "(4) POST /gelato/shipments/pick with gelato:write → 200, shipment in 'picking'",
            s == 200 and shipment_id is not None and body.get("status") == "picking",
            f"status={s} body={body!r}",
        )

        s, body = http(
            "POST", f"/shipments/{shipment_id}/pack", writer_token, {"overrides": []}
        )
        check(
            "(4) POST /gelato/shipments/{id}/pack with gelato:write → 200, status 'packed'",
            s == 200 and isinstance(body, dict) and body.get("status") == "packed",
            f"status={s} body={body!r}",
        )

        s, body = http("POST", f"/shipments/{shipment_id}/ship", writer_token, {})
        je_id = body.get("journal_entry_id") if isinstance(body, dict) else None
        check(
            "(4/GUARD) POST /gelato/shipments/{id}/ship with gelato:write → 200 (NOT a "
            "500-after-commit) with status 'shipped' and a NON-NULL journal_entry_id",
            s == 200
            and isinstance(body, dict)
            and body.get("status") == "shipped"
            and je_id is not None,
            f"status={s} body={body!r}",
        )

        # A plain read-back of the shipped shipment (gelato:read).
        s, body = http("GET", f"/shipments/{shipment_id}", writer_token)
        check(
            "(4) GET /gelato/shipments/{id} with gelato:read → 200, the shipped shipment",
            s == 200 and isinstance(body, dict) and body.get("id") == shipment_id,
            f"status={s} body={body!r}",
        )

        # ===================================================================
        # (5) AUDIT — shipment.picked / shipment.packed / shipment.shipped rows
        #     exist, are attributable to the writer (actor_id), and their
        #     target_id ROUND-TRIPS as the shipment-id STRING (the int-PK guard).
        # ===================================================================
        target_str = str(shipment_id)
        for action in ("shipment.picked", "shipment.packed", "shipment.shipped"):
            audit = await _audit_row(session_factory, action, target_str)
            check(
                f"(5) a {action} audit row exists, attributable to the writer "
                "(actor_id), targeting target_type='shipment'",
                audit is not None
                and audit.actor_id == writer_id
                and audit.target_type == "shipment",
                f"audit={audit!r}",
            )
            check(
                f"(5/GUARD) the {action} row's target_id round-trips as the shipment-id "
                f"STRING '{target_str}' (VARCHAR(36), not a raw int)",
                audit is not None
                and audit.target_id == target_str
                and isinstance(audit.target_id, str),
                f"target_id={getattr(audit, 'target_id', None)!r}",
            )

        # ===================================================================
        # (2) 403 write — a token WITHOUT gelato:write (the gelato:read-only
        #     reader) → 403 on pick / pack / ship; unauthenticated → 401. The
        #     auth failure short-circuits BEFORE the service, so firing these
        #     against the already-shipped shipment cannot mutate state.
        # ===================================================================
        write_routes = [
            ("POST", "/shipments/pick", pick_payload),
            ("POST", f"/shipments/{shipment_id}/pack", {"overrides": []}),
            ("POST", f"/shipments/{shipment_id}/ship", {}),
        ]
        for method, path, payload in write_routes:
            s, _ = http(method, path, reader_token, payload)
            check(
                f"(2) gelato:read-only token → 403 on {method} {path} (no gelato:write)",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None, payload)
            check(
                f"(2) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

    finally:
        await _cleanup(
            session_factory,
            partner_ids,
            item_ids,
            bin_ids,
            so_ids,
            shipment_ids,
            audit_targets,
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
    bin_ids: set[int],
    so_ids: set[str],
    shipment_ids: set[int],
    audit_targets: set[str],
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: shipment lines -> shipments -> the
    gelato_shipment journal lines/entries -> the audit_log rows this run wrote -> SO
    lines -> sales orders -> inventory txns -> bins -> inventory items -> partners ->
    throwaway users -> throwaway roles. The seeded "Main" location and 1130/5100 GL
    accounts are reused and left in place.
    """
    async with session_factory() as session:
        shipment_list = list(shipment_ids)
        so_list = list(so_ids)
        item_list = list(item_ids)
        bin_list = list(bin_ids)
        partner_list = list(partner_ids)
        target_list = list(audit_targets)

        if shipment_list:
            await session.execute(
                delete(ShipmentLine).where(ShipmentLine.shipment_id.in_(shipment_list))
            )
            await session.execute(delete(Shipment).where(Shipment.id.in_(shipment_list)))
            entry_ids = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "gelato_shipment",
                        JournalEntry.source_id.in_([str(s) for s in shipment_list]),
                    )
                )
            ).scalars().all()
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(delete(JournalEntry).where(JournalEntry.id.in_(entry_ids)))

        if target_list:
            await session.execute(
                delete(AuditLog).where(AuditLog.target_id.in_(target_list))
            )
        if so_list:
            await session.execute(
                delete(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(so_list))
            )
            await session.execute(delete(SalesOrder).where(SalesOrder.id.in_(so_list)))
        if item_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list))
            )
        if bin_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_list)))
        if item_list:
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_list))
            )
        if partner_list:
            await session.execute(delete(Partner).where(Partner.id.in_(partner_list)))
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
