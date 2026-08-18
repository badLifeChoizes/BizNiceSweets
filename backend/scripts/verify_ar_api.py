# ABOUTME: Router-level live-HTTP verification for the SYERP AR endpoints (Phase 13, SYERP-13).
# ABOUTME: Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in the image) to prove
# ABOUTME: the invoice.created / invoice.posted / receipt.recorded AUDIT rows are written and
# ABOUTME: attributable, that the syerp:read/write RBAC gate returns 403/401/200 across all 8 AR
# ABOUTME: routes, and that the ReceiptCreate→ArReceiptCreate rename left the inventory costed-
# ABOUTME: receipt endpoint intact; exits non-zero on FAIL and self-cleans.
"""
Router-level live-HTTP verification for the SYERP AR endpoints (Phase 13).

WHY THIS EXISTS (the router proof — the companion to verify_ar.py):
  verify_ar.py drives the AR SERVICE functions directly and so can never exercise
  the two things that live only in the ROUTER: the audit rows written by
  write_audit and the RBAC gate enforced by require_permission. This script closes
  that gap by making REAL HTTP calls against the running api and asserting, for
  EVERY one of the 8 AR routes, the 401/403/200 triad:
    - POST /ar/invoices writes an attributable invoice.created audit row targeting
      the exact invoice id;
    - POST /ar/invoices/{id}/post writes invoice.posted targeting the same invoice;
    - POST /ar/receipts writes receipt.recorded targeting the receipt id;
    - every AR MUTATION endpoint refuses a syerp:read-only token with 403 and an
      unauthenticated request with 401;
    - every AR GET endpoint accepts a syerp:read token with 200 and refuses an
      anonymous request with 401.
  It ALSO locks the Wave-B ReceiptCreate collision fix: the inventory costed-receipt
  endpoint (POST /inventory/items/{id}/receipts) still accepts its costed body
  {location_id, qty, unit_cost} with 201, and an AR-shaped receipt body is NOT
  silently accepted there (422) — proving the AR schema rename (ReceiptCreate →
  ArReceiptCreate) did not shadow the inventory schema.

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so the read-only case mints a token for a throwaway user carrying a throwaway
  role that holds ONLY the seeded syerp:read permission (200 on GET, 403 on any
  write); the authorized/write case mints a token for the seeded admin (whose
  'admin' role is a wildcard). Tokens are minted with create_access_token — no
  password round-trip needed.

  To reach a postable invoice + receipt this script must first produce a
  shipped-but-uninvoiced SO line: it drives the REAL GELATO pick→pack→ship flow
  (execute_putaway / execute_pick / execute_pack / execute_ship) exactly the way
  verify_ar.py does, so the AR match runs against a genuinely-shipped quantity.

HOW TO RUN (needs the api SERVING, unlike verify_ar.py which owns its own engine):
  # From inside the running api container (api binds 0.0.0.0:8000):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_ar_api.py
  # Or as a one-off container on the compose network, pointing at the api service:
  podman run --rm --network compose_default --env-file .env \
      -e POSTGRES_HOST=db -e PYTHONPATH=/app -e BNS_API_BASE_URL=http://api:8000 \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_ar_api.py

The script creates throwaway rows (a customer + item + bins + shipped SO line, one
read-only role + user) plus the invoice and receipt it drives over HTTP, and CLEANS
UP after itself in a finally block (deletes the receipt allocations/receipts, invoice
lines/invoices, ar_invoice/ar_receipt/gelato_shipment journal lines/entries, shipment
lines/shipments, SO lines/sales orders, inventory txns/bins/item/customer, the
audit_log rows it created, and the throwaway user + role), so it is safe to re-run
against the same database.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_ar_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.core.config import settings
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.crumb.models import SalesOrder, SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.gelato.models import Bin, Shipment, ShipmentLine
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
from app.modules.syerp.inventory_seed import (
    DEFAULT_LOCATION_NAME,
    seed_default_location,
)
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Partner,
    Receipt,
    ReceiptAllocation,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/syerp"


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
    relative to the /api/v1/syerp base. HTTP error statuses are captured and
    returned rather than raised, so the caller can assert on 403/401/422.
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


async def _seed_shipped_line(
    session_factory,
    reg: Registry,
    unique: str,
    actor_id: str,
    location_id: int,
    cust_id: str,
) -> dict:
    """
    Seed one genuinely-shipped SO line via the REAL GELATO flow: an item with stock,
    a pick bin holding 50, a CONFIRMED single-line SO for 8 @ price 20, then pick →
    pack → SHIP 8 so qty_shipped is stamped and the invoice picker surfaces it.
    Returns the handles the AR HTTP scenarios drive against.
    """
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(name=f"VERIFY-AR-API Widget {unique}", unit_of_measure="ea"),
        )
        item_id = item.id
    reg.item_ids.add(item_id)

    async with session_factory() as session:
        await post_receipt(session, item_id, location_id, Decimal("100"), Decimal("10"), actor_id)

    async with session_factory() as session:
        pick_bin = await create_bin(
            session, BinCreate(location_id=location_id, code=f"AR-API-PICK-{unique}")
        )
        pick_bin_id = pick_bin.id
    async with session_factory() as session:
        staging_bin = await create_bin(
            session, BinCreate(location_id=location_id, code=f"AR-API-STAGE-{unique}")
        )
        staging_bin_id = staging_bin.id
    reg.bin_ids.update({pick_bin_id, staging_bin_id})

    async with session_factory() as session:
        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id, location_id=location_id, to_bin_id=pick_bin_id,
                qty=Decimal("50"), from_bin_id=None,
            ),
            actor_id,
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
            actor_id,
        )
    reg.so_ids.add(so.id)
    async with session_factory() as session:
        confirmed = await confirm_sales_order(session, so.id, actor_id)
    so_line_id = confirmed.lines[0].id

    async with session_factory() as session:
        picked = await execute_pick(
            session,
            PickRequest(
                sales_order_id=so.id,
                staging_bin_id=staging_bin_id,
                lines=[
                    PickLineRequest(
                        sales_order_line_id=so_line_id, from_bin_id=pick_bin_id, qty=Decimal("8")
                    )
                ],
            ),
            actor_id,
        )
    shipment_id = picked.id
    reg.shipment_ids.add(shipment_id)
    async with session_factory() as session:
        await execute_pack(session, shipment_id, PackRequest(), actor_id)
    async with session_factory() as session:
        await execute_ship(session, shipment_id, actor_id)

    return {"item_id": item_id, "so_id": so.id, "so_line_id": so_line_id}


class Registry:
    """Throwaway-row id registries swept, in FK-safe order, by the finally block."""

    def __init__(self) -> None:
        self.item_ids: set[str] = set()
        self.bin_ids: set[int] = set()
        self.so_ids: set[str] = set()
        self.shipment_ids: set[int] = set()
        self.invoice_ids: set[str] = set()
        self.receipt_ids: set[str] = set()


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]
    reg = Registry()
    today = date.today()

    admin_id: str | None = None
    reader_id: str | None = None
    reader_role_id: int | None = None
    cust_id: str | None = None
    invoice_id: str | None = None
    receipt_id: str | None = None
    audit_target_ids: list[str] = []

    try:
        # -------------------------------------------------------------------
        # Setup: resolve the seeded admin (wildcard = write-capable), mint a
        # read-only role + user holding ONLY the seeded syerp:read permission,
        # resolve the 1110 Cash account + the "Main" location, and build a
        # shipped-but-uninvoiced SO line via the REAL GELATO ship flow.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            admin = (
                await session.execute(
                    select(User).where(User.email == settings.bns_admin_email)
                )
            ).scalars().first()
            if admin is None:
                print(f"FAIL: seeded admin {settings.bns_admin_email} not found.")
                sys.exit(2)
            admin_id = admin.id

            read_perm = (
                await session.execute(
                    select(Permission).where(Permission.code == "syerp:read")
                )
            ).scalars().first()
            if read_perm is None:
                print("FAIL: seeded syerp:read permission not found.")
                sys.exit(2)

            reader_role = Role(
                name=f"verify-ar-readonly-{unique}",
                description="VERIFY throwaway role: syerp:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(read_perm)

            reader = User(
                email=f"verify-ar-reader-{unique}@example.test",
                hashed_password=hash_password("verify-ar-reader-pw"),
                full_name="VERIFY syerp:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)
            await session.commit()
            reader_id = reader.id
            reader_role_id = reader_role.id

        admin_token = create_access_token(admin_id, [])
        reader_token = create_access_token(reader_id, [])

        # Seed (idempotent) + reuse the "Main" stock location; resolve 1110 Cash.
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            main = (
                await session.execute(
                    select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
                )
            ).scalars().first()
            if main is None:
                print("FAIL: seeded 'Main' stock location not found.")
                sys.exit(2)
            main_id = main.id
            cash = (
                await session.execute(select(GLAccount).where(GLAccount.code == "1110"))
            ).scalars().first()
            if cash is None:
                print("FAIL: seeded 1110 Cash account not found.")
                sys.exit(2)
            cash_id = cash.id

        async with session_factory() as session:
            customer = await create_partner(
                session, PartnerCreate(name=f"VERIFY AR-API Customer {unique}", is_customer=True)
            )
            cust_id = customer.id

        shipped = await _seed_shipped_line(
            session_factory, reg, unique, admin_id, main_id, cust_id
        )
        so_line_id = shipped["so_line_id"]
        so_id = shipped["so_id"]
        item_id = shipped["item_id"]

        invoice_body = {
            "customer_id": cust_id,
            "sales_order_id": so_id,
            "invoice_date": today.isoformat(),
            "lines": [{"sales_order_line_id": so_line_id, "invoiced_qty": "8"}],
        }

        # -------------------------------------------------------------------
        # (a) GET /ar/uninvoiced-shipments surfaces the shipped line as admin.
        # -------------------------------------------------------------------
        status_code, body = http(
            "GET", f"/ar/uninvoiced-shipments?customer_id={cust_id}", admin_token
        )
        found = isinstance(body, list) and any(
            r.get("sales_order_line_id") == so_line_id
            and Decimal(str(r.get("uninvoiced_qty"))) == Decimal("8")
            for r in body
        )
        check(
            "GET /ar/uninvoiced-shipments as admin returns 200 with the shipped line "
            "(uninvoiced_qty 8)",
            status_code == 200 and found,
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (b) POST /ar/invoices as admin → 201, and an invoice.created audit
        #     row is written, attributable to the admin, targeting the invoice.
        # -------------------------------------------------------------------
        status_code, body = http("POST", "/ar/invoices", admin_token, invoice_body)
        invoice_id = body.get("id") if isinstance(body, dict) else None
        if invoice_id:
            reg.invoice_ids.add(invoice_id)
            audit_target_ids.append(invoice_id)
        check(
            "POST /ar/invoices as admin returns 201 with a draft invoice id (total 160)",
            status_code == 201
            and invoice_id is not None
            and body.get("status") == "draft"
            and Decimal(str(body.get("total"))) == Decimal("160"),
            f"status={status_code} body={body!r}",
        )

        async with session_factory() as session:
            created_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "invoice.created",
                        AuditLog.target_id == invoice_id,
                    )
                )
            ).scalars().first()
        check(
            "an invoice.created audit row was written, attributable to the admin, "
            "targeting the created invoice",
            created_audit is not None
            and created_audit.actor_id == admin_id
            and created_audit.target_type == "invoice",
            f"audit={created_audit!r}",
        )

        # -------------------------------------------------------------------
        # (c) GET /ar/invoices and GET /ar/invoices/{id} as admin → 200.
        # -------------------------------------------------------------------
        status_code, body = http("GET", "/ar/invoices", admin_token)
        check(
            "GET /ar/invoices as admin returns 200 with a list",
            status_code == 200 and isinstance(body, list),
            f"status={status_code} body={body!r}",
        )
        status_code, body = http("GET", f"/ar/invoices/{invoice_id}", admin_token)
        check(
            "GET /ar/invoices/{id} as admin returns 200 for the created invoice",
            status_code == 200 and isinstance(body, dict) and body.get("id") == invoice_id,
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (d) POST /ar/invoices/{id}/post as admin → 200, and an invoice.posted
        #     audit row is written targeting the same invoice.
        # -------------------------------------------------------------------
        status_code, body = http("POST", f"/ar/invoices/{invoice_id}/post", admin_token)
        check(
            "POST /ar/invoices/{id}/post as admin returns 200 with status 'posted'",
            status_code == 200 and isinstance(body, dict) and body.get("status") == "posted",
            f"status={status_code} body={body!r}",
        )
        async with session_factory() as session:
            posted_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "invoice.posted",
                        AuditLog.target_id == invoice_id,
                    )
                )
            ).scalars().first()
        check(
            "an invoice.posted audit row was written, attributable to the admin, "
            "targeting the posted invoice",
            posted_audit is not None
            and posted_audit.actor_id == admin_id
            and posted_audit.target_type == "invoice",
            f"audit={posted_audit!r}",
        )

        # -------------------------------------------------------------------
        # (e) POST /ar/receipts as admin → 201, and a receipt.recorded audit
        #     row is written targeting the receipt.
        # -------------------------------------------------------------------
        receipt_body = {
            "receipt_date": today.isoformat(),
            "cash_account_id": cash_id,
            "reference": f"RCPT-{unique}",
            "allocations": [{"invoice_id": invoice_id, "amount": "60"}],
        }
        status_code, body = http("POST", "/ar/receipts", admin_token, receipt_body)
        receipt_id = body.get("id") if isinstance(body, dict) else None
        if receipt_id:
            reg.receipt_ids.add(receipt_id)
            audit_target_ids.append(receipt_id)
        check(
            "POST /ar/receipts as admin returns 201 with a receipt id (amount 60)",
            status_code == 201
            and receipt_id is not None
            and Decimal(str(body.get("amount"))) == Decimal("60"),
            f"status={status_code} body={body!r}",
        )
        async with session_factory() as session:
            receipt_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "receipt.recorded",
                        AuditLog.target_id == receipt_id,
                    )
                )
            ).scalars().first()
        check(
            "a receipt.recorded audit row was written, attributable to the admin, "
            "targeting the receipt",
            receipt_audit is not None
            and receipt_audit.actor_id == admin_id
            and receipt_audit.target_type == "receipt",
            f"audit={receipt_audit!r}",
        )

        # -------------------------------------------------------------------
        # (f) GET /ar/receipts and GET /ar/aging as admin → 200.
        # -------------------------------------------------------------------
        status_code, body = http("GET", "/ar/receipts", admin_token)
        check(
            "GET /ar/receipts as admin returns 200 with a list",
            status_code == 200 and isinstance(body, list),
            f"status={status_code} body={body!r}",
        )
        status_code, body = http("GET", "/ar/aging", admin_token)
        check(
            "GET /ar/aging as admin returns 200 with an aging report",
            status_code == 200 and isinstance(body, dict),
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (g) REGRESSION LOCK — the ReceiptCreate → ArReceiptCreate rename did
        #     not shadow the inventory costed-receipt schema. POST /inventory/
        #     items/{id}/receipts still accepts its {location_id, qty, unit_cost}
        #     body (201), and an AR-shaped receipt body is NOT accepted (422).
        # -------------------------------------------------------------------
        costed_body = {"location_id": main_id, "qty": "3", "unit_cost": "12"}
        status_code, body = http(
            "POST", f"/inventory/items/{item_id}/receipts", admin_token, costed_body
        )
        txn_id = body.get("id") if isinstance(body, dict) else None
        if txn_id:
            audit_target_ids.append(txn_id)
        check(
            "REGRESSION: POST /inventory/items/{id}/receipts still accepts the costed "
            "body {location_id, qty, unit_cost} with 201 (ReceiptCreate not shadowed)",
            status_code == 201
            and isinstance(body, dict)
            and Decimal(str(body.get("quantity"))) == Decimal("3"),
            f"status={status_code} body={body!r}",
        )
        ar_shaped_body = {
            "receipt_date": today.isoformat(),
            "cash_account_id": cash_id,
            "reference": f"WRONG-{unique}",
            "allocations": [{"invoice_id": invoice_id, "amount": "1"}],
        }
        status_code, body = http(
            "POST", f"/inventory/items/{item_id}/receipts", admin_token, ar_shaped_body
        )
        check(
            "REGRESSION: POST /inventory/items/{id}/receipts REJECTS an AR-shaped receipt "
            "body with 422 (the inventory endpoint still binds ReceiptCreate, not "
            "ArReceiptCreate)",
            status_code == 422,
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (h) RBAC — the syerp:read-only token is refused 403 on every AR
        #     MUTATION endpoint and accepted 200 on every AR GET.
        # -------------------------------------------------------------------
        s, _ = http("POST", "/ar/invoices", reader_token, invoice_body)
        check("syerp:read token → 403 on POST /ar/invoices", s == 403, f"status={s}")
        s, _ = http("POST", f"/ar/invoices/{invoice_id}/post", reader_token)
        check("syerp:read token → 403 on POST /ar/invoices/{id}/post", s == 403, f"status={s}")
        s, _ = http("POST", "/ar/receipts", reader_token, receipt_body)
        check("syerp:read token → 403 on POST /ar/receipts", s == 403, f"status={s}")

        s, _ = http("GET", f"/ar/uninvoiced-shipments?customer_id={cust_id}", reader_token)
        check("syerp:read token → 200 on GET /ar/uninvoiced-shipments", s == 200, f"status={s}")
        s, _ = http("GET", "/ar/invoices", reader_token)
        check("syerp:read token → 200 on GET /ar/invoices", s == 200, f"status={s}")
        s, _ = http("GET", f"/ar/invoices/{invoice_id}", reader_token)
        check("syerp:read token → 200 on GET /ar/invoices/{id}", s == 200, f"status={s}")
        s, _ = http("GET", "/ar/receipts", reader_token)
        check("syerp:read token → 200 on GET /ar/receipts", s == 200, f"status={s}")
        s, _ = http("GET", "/ar/aging", reader_token)
        check("syerp:read token → 200 on GET /ar/aging", s == 200, f"status={s}")

        # -------------------------------------------------------------------
        # (i) RBAC — an unauthenticated request is refused 401 on every AR
        #     endpoint, mutation AND read.
        # -------------------------------------------------------------------
        s, _ = http("POST", "/ar/invoices", None, invoice_body)
        check("unauthenticated → 401 on POST /ar/invoices", s == 401, f"status={s}")
        s, _ = http("POST", f"/ar/invoices/{invoice_id}/post", None)
        check("unauthenticated → 401 on POST /ar/invoices/{id}/post", s == 401, f"status={s}")
        s, _ = http("POST", "/ar/receipts", None, receipt_body)
        check("unauthenticated → 401 on POST /ar/receipts", s == 401, f"status={s}")

        s, _ = http("GET", f"/ar/uninvoiced-shipments?customer_id={cust_id}", None)
        check("unauthenticated → 401 on GET /ar/uninvoiced-shipments", s == 401, f"status={s}")
        s, _ = http("GET", "/ar/invoices", None)
        check("unauthenticated → 401 on GET /ar/invoices", s == 401, f"status={s}")
        s, _ = http("GET", f"/ar/invoices/{invoice_id}", None)
        check("unauthenticated → 401 on GET /ar/invoices/{id}", s == 401, f"status={s}")
        s, _ = http("GET", "/ar/receipts", None)
        check("unauthenticated → 401 on GET /ar/receipts", s == 401, f"status={s}")
        s, _ = http("GET", "/ar/aging", None)
        check("unauthenticated → 401 on GET /ar/aging", s == 401, f"status={s}")

    finally:
        # Clean up in FK-safe order: receipt allocations → receipts → invoice lines →
        # invoices → ar_invoice/ar_receipt/gelato_shipment journal lines/entries →
        # shipment lines → shipments → SO lines → sales orders → inventory txns → bins
        # → item → customer → audit rows → throwaway user → throwaway role. The seeded
        # admin, accounts, and "Main" location are left in place (real deploy state).
        async with session_factory() as session:
            await seed_default_location(session)  # keep default present for re-runs

            invoice_list = list(reg.invoice_ids)
            receipt_list = list(reg.receipt_ids)
            shipment_list = list(reg.shipment_ids)
            so_list = list(reg.so_ids)
            item_list = list(reg.item_ids)
            bin_list = list(reg.bin_ids)

            if receipt_list:
                await session.execute(
                    delete(ReceiptAllocation).where(
                        ReceiptAllocation.receipt_id.in_(receipt_list)
                    )
                )
                await session.execute(delete(Receipt).where(Receipt.id.in_(receipt_list)))
            if invoice_list:
                await session.execute(
                    delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_list))
                )
                await session.execute(delete(Invoice).where(Invoice.id.in_(invoice_list)))

            entry_ids: list[str] = []
            for source_type, source_ids in (
                ("ar_invoice", invoice_list),
                ("ar_receipt", receipt_list),
                ("gelato_shipment", [str(s) for s in shipment_list]),
            ):
                if source_ids:
                    ids = (
                        await session.execute(
                            select(JournalEntry.id).where(
                                JournalEntry.source_type == source_type,
                                JournalEntry.source_id.in_(source_ids),
                            )
                        )
                    ).scalars().all()
                    entry_ids.extend(ids)

            # Shipments go before their gelato_shipment JEs (shipment.journal_entry_id FK).
            if shipment_list:
                await session.execute(
                    delete(ShipmentLine).where(ShipmentLine.shipment_id.in_(shipment_list))
                )
                await session.execute(delete(Shipment).where(Shipment.id.in_(shipment_list)))
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
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
                await session.execute(delete(InventoryItem).where(InventoryItem.id.in_(item_list)))
            if cust_id is not None:
                await session.execute(delete(Partner).where(Partner.id == cust_id))

            if audit_target_ids:
                await session.execute(
                    delete(AuditLog).where(AuditLog.target_id.in_(audit_target_ids))
                )
            if reader_id is not None:
                await session.execute(delete(User).where(User.id == reader_id))
            if reader_role_id is not None:
                await session.execute(delete(Role).where(Role.id == reader_role_id))

            await session.commit()
        await engine.dispose()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
