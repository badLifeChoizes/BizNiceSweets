# ABOUTME: Router-level live-HTTP verification for the SYERP AP endpoints (Phase 9b, SYERP-12
# ABOUTME: SC6/AC8/AC9). Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in the
# ABOUTME: image) to prove the bill.created / bill.posted / payment.recorded AUDIT rows are written
# ABOUTME: and attributable, and that the syerp:read/write RBAC gate returns 403/401/200; exits non-zero on FAIL.
"""
Router-level live-HTTP verification for the SYERP AP endpoints (Phase 9b).

WHY THIS EXISTS (the router proof — the companion to verify_ap.py):
  verify_ap.py drives the AP SERVICE functions directly and so can never exercise
  the two things that live only in the ROUTER: the audit rows written by
  write_audit (AC8) and the RBAC gate enforced by require_permission (AC9). This
  script closes that gap by making REAL HTTP calls against the running api and
  asserting:
    - POST /ap/bills writes an attributable bill.created audit row targeting the
      exact bill id;
    - POST /ap/bills/{id}/post writes bill.posted targeting the same bill;
    - POST /ap/payments writes payment.recorded targeting the payment id;
    - every AP MUTATION endpoint refuses a syerp:read-only token with 403 and an
      unauthenticated request with 401;
    - every AP GET endpoint (including GET /ap/payments, the list_payments read)
      accepts a syerp:read token with 200 and refuses an anonymous request with 401.
  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so the read-only case mints a token for a throwaway user carrying a throwaway
  role that holds ONLY the seeded syerp:read permission (200 on GET, 403 on any
  write); the authorized/write case mints a token for the seeded admin (whose
  'admin' role is a wildcard). Tokens are minted with create_access_token — no
  password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_ap.py which owns its own engine):
  # From inside the running api container (api binds 0.0.0.0:8000):
  podman exec compose_api_1 sh -c "cd /app && python scripts/verify_ap_api.py"
  # Or as a one-off container on the compose network, pointing at the api service:
  podman run --rm --network compose_default --env-file .env \
      -e POSTGRES_HOST=db -e PYTHONPATH=/app -e BNS_API_BASE_URL=http://api:8000 \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_ap_api.py

The script creates throwaway rows (a vendor + item + location + PO + received line
to have an exact-match receipt to bill, one read-only role + user) plus the bill and
payment it drives over HTTP, and CLEANS UP after itself in a finally block (deletes
the payment allocations/payments, journal lines/entries, bill lines/bills, PO
lines/POs, inventory txns/item/location/vendor, the audit_log rows it created, and
the throwaway user + role), so it is safe to re-run against the same database.
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

# Make the backend root importable when run as a bare `python scripts/verify_ap_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.core.config import settings
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.syerp.inventory_seed import seed_default_location
from app.modules.syerp.models import (
    Bill,
    BillLine,
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    Payment,
    PaymentAllocation,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLocation,
)
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    PartnerCreate,
    POCreate,
    POLineCreate,
    StockLocationCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_item,
    create_location,
    create_partner,
    create_po,
    receive_line,
)

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


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    admin_id: str | None = None
    reader_id: str | None = None
    reader_role_id: int | None = None
    vendor_id: str | None = None
    item_id: str | None = None
    loc_id: int | None = None
    po_id: str | None = None
    line_id: str | None = None
    bill_id: str | None = None
    payment_id: str | None = None
    audit_target_ids: list[str] = []

    try:
        # -------------------------------------------------------------------
        # Setup: resolve the seeded admin (wildcard = write-capable), mint a
        # read-only role + user holding ONLY the seeded syerp:read permission,
        # and build a billable fixture (vendor + item + location + received PO
        # line) via the AP service functions.
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
                name=f"verify-ap-readonly-{unique}",
                description="VERIFY throwaway role: syerp:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(read_perm)

            reader = User(
                email=f"verify-ap-reader-{unique}@example.test",
                hashed_password=hash_password("verify-ap-reader-pw"),
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

        # Resolve the seeded 1110 Cash account for the payment.
        async with session_factory() as session:
            cash = (
                await session.execute(select(GLAccount).where(GLAccount.code == "1110"))
            ).scalars().first()
            if cash is None:
                print("FAIL: seeded 1110 Cash account not found.")
                sys.exit(2)
            cash_id = cash.id

        # Billable fixture: PO with one line, approved, fully received (6 @ 5 = 30).
        actor_id = admin_id
        async with session_factory() as session:
            vendor = await create_partner(
                session, PartnerCreate(name=f"VERIFY AP-API Vendor {unique}", is_vendor=True)
            )
            vendor_id = vendor.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY AP-API Widget {unique}", unit_of_measure="ea"),
            )
            item_id = item.id
        async with session_factory() as session:
            location = await create_location(
                session, StockLocationCreate(name=f"VERIFY-AP-API-{unique}")
            )
            loc_id = location.id
        async with session_factory() as session:
            po = await create_po(session, POCreate(vendor_id=vendor_id))
        po_id = po.id
        async with session_factory() as session:
            line = await add_line(
                session,
                po_id,
                POLineCreate(item_id=item_id, qty_ordered=Decimal("6"), unit_cost=Decimal("5")),
            )
        line_id = line.id
        async with session_factory() as session:
            await advance_po_status(session, po_id, "approved", actor_id)
        async with session_factory() as session:
            await receive_line(session, po_id, line_id, loc_id, Decimal("6"), actor_id)

        matched_bill_body = {
            "vendor_id": vendor_id,
            "vendor_invoice_ref": f"INV-{unique}",
            "lines": [
                {"line_type": "matched", "po_line_id": line_id, "matched_qty": "6"}
            ],
        }

        # -------------------------------------------------------------------
        # (a) GET /ap/unbilled-receipts surfaces the received line as admin.
        # -------------------------------------------------------------------
        status_code, body = http(
            "GET", f"/ap/unbilled-receipts?vendor_id={vendor_id}", admin_token
        )
        found = isinstance(body, list) and any(
            r.get("po_line_id") == line_id for r in body
        )
        check(
            "GET /ap/unbilled-receipts as admin returns 200 with the received line",
            status_code == 200 and found,
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (b) POST /ap/bills as admin → 201, and a bill.created audit row is
        #     written, attributable to the admin, targeting the bill (AC8).
        # -------------------------------------------------------------------
        status_code, body = http("POST", "/ap/bills", admin_token, matched_bill_body)
        bill_id = body.get("id") if isinstance(body, dict) else None
        if bill_id:
            audit_target_ids.append(bill_id)
        check(
            "POST /ap/bills as admin returns 201 with a draft bill id (total 30)",
            status_code == 201
            and bill_id is not None
            and body.get("status") == "draft"
            and Decimal(str(body.get("total"))) == Decimal("30"),
            f"status={status_code} body={body!r}",
        )

        async with session_factory() as session:
            created_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "bill.created",
                        AuditLog.target_id == bill_id,
                    )
                )
            ).scalars().first()
        check(
            "a bill.created audit row was written, attributable to the admin, "
            "targeting the created bill (AC8)",
            created_audit is not None
            and created_audit.actor_id == admin_id
            and created_audit.target_type == "bill",
            f"audit={created_audit!r}",
        )

        # -------------------------------------------------------------------
        # (c) GET /ap/bills and GET /ap/bills/{id} as admin → 200.
        # -------------------------------------------------------------------
        status_code, body = http("GET", "/ap/bills", admin_token)
        check(
            "GET /ap/bills as admin returns 200 with a list",
            status_code == 200 and isinstance(body, list),
            f"status={status_code} body={body!r}",
        )
        status_code, body = http("GET", f"/ap/bills/{bill_id}", admin_token)
        check(
            "GET /ap/bills/{id} as admin returns 200 for the created bill",
            status_code == 200 and isinstance(body, dict) and body.get("id") == bill_id,
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (d) POST /ap/bills/{id}/post as admin → 200, and a bill.posted audit
        #     row is written targeting the same bill (AC8).
        # -------------------------------------------------------------------
        status_code, body = http("POST", f"/ap/bills/{bill_id}/post", admin_token)
        check(
            "POST /ap/bills/{id}/post as admin returns 200 with status 'posted'",
            status_code == 200 and isinstance(body, dict) and body.get("status") == "posted",
            f"status={status_code} body={body!r}",
        )
        async with session_factory() as session:
            posted_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "bill.posted",
                        AuditLog.target_id == bill_id,
                    )
                )
            ).scalars().first()
        check(
            "a bill.posted audit row was written, attributable to the admin, "
            "targeting the posted bill (AC8)",
            posted_audit is not None
            and posted_audit.actor_id == admin_id
            and posted_audit.target_type == "bill",
            f"audit={posted_audit!r}",
        )

        # -------------------------------------------------------------------
        # (e) POST /ap/payments as admin → 201, and a payment.recorded audit
        #     row is written targeting the payment (AC8).
        # -------------------------------------------------------------------
        payment_body = {
            "payment_date": date.today().isoformat(),
            "cash_account_id": cash_id,
            "reference": f"CHK-{unique}",
            "allocations": [{"bill_id": bill_id, "amount": "30"}],
        }
        status_code, body = http("POST", "/ap/payments", admin_token, payment_body)
        payment_id = body.get("id") if isinstance(body, dict) else None
        if payment_id:
            audit_target_ids.append(payment_id)
        check(
            "POST /ap/payments as admin returns 201 with a payment id (amount 30)",
            status_code == 201
            and payment_id is not None
            and Decimal(str(body.get("amount"))) == Decimal("30"),
            f"status={status_code} body={body!r}",
        )
        async with session_factory() as session:
            payment_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "payment.recorded",
                        AuditLog.target_id == payment_id,
                    )
                )
            ).scalars().first()
        check(
            "a payment.recorded audit row was written, attributable to the admin, "
            "targeting the payment (AC8)",
            payment_audit is not None
            and payment_audit.actor_id == admin_id
            and payment_audit.target_type == "payment",
            f"audit={payment_audit!r}",
        )

        # -------------------------------------------------------------------
        # (f) GET /ap/payments as admin → 200 (exercises the list_payments read,
        #     fix 99ef164).
        # -------------------------------------------------------------------
        status_code, body = http("GET", "/ap/payments", admin_token)
        check(
            "GET /ap/payments as admin returns 200 with a list (list_payments read)",
            status_code == 200 and isinstance(body, list),
            f"status={status_code} body={body!r}",
        )

        # -------------------------------------------------------------------
        # (g) RBAC — the syerp:read-only token is refused 403 on every MUTATION
        #     endpoint and accepted 200 on every GET (AC9).
        # -------------------------------------------------------------------
        s, _ = http("POST", "/ap/bills", reader_token, matched_bill_body)
        check("syerp:read token → 403 on POST /ap/bills (AC9)", s == 403, f"status={s}")
        s, _ = http("POST", f"/ap/bills/{bill_id}/post", reader_token)
        check("syerp:read token → 403 on POST /ap/bills/{id}/post (AC9)", s == 403, f"status={s}")
        s, _ = http("POST", "/ap/payments", reader_token, payment_body)
        check("syerp:read token → 403 on POST /ap/payments (AC9)", s == 403, f"status={s}")

        s, _ = http("GET", f"/ap/unbilled-receipts?vendor_id={vendor_id}", reader_token)
        check("syerp:read token → 200 on GET /ap/unbilled-receipts (AC9)", s == 200, f"status={s}")
        s, _ = http("GET", "/ap/bills", reader_token)
        check("syerp:read token → 200 on GET /ap/bills (AC9)", s == 200, f"status={s}")
        s, _ = http("GET", f"/ap/bills/{bill_id}", reader_token)
        check("syerp:read token → 200 on GET /ap/bills/{id} (AC9)", s == 200, f"status={s}")
        s, _ = http("GET", "/ap/payments", reader_token)
        check("syerp:read token → 200 on GET /ap/payments (AC9)", s == 200, f"status={s}")

        # -------------------------------------------------------------------
        # (h) RBAC — an unauthenticated request is refused 401 on every AP
        #     endpoint, mutation AND read (AC9).
        # -------------------------------------------------------------------
        s, _ = http("POST", "/ap/bills", None, matched_bill_body)
        check("unauthenticated → 401 on POST /ap/bills (AC9)", s == 401, f"status={s}")
        s, _ = http("POST", f"/ap/bills/{bill_id}/post", None)
        check("unauthenticated → 401 on POST /ap/bills/{id}/post (AC9)", s == 401, f"status={s}")
        s, _ = http("POST", "/ap/payments", None, payment_body)
        check("unauthenticated → 401 on POST /ap/payments (AC9)", s == 401, f"status={s}")

        s, _ = http("GET", f"/ap/unbilled-receipts?vendor_id={vendor_id}", None)
        check("unauthenticated → 401 on GET /ap/unbilled-receipts (AC9)", s == 401, f"status={s}")
        s, _ = http("GET", "/ap/bills", None)
        check("unauthenticated → 401 on GET /ap/bills (AC9)", s == 401, f"status={s}")
        s, _ = http("GET", f"/ap/bills/{bill_id}", None)
        check("unauthenticated → 401 on GET /ap/bills/{id} (AC9)", s == 401, f"status={s}")
        s, _ = http("GET", "/ap/payments", None)
        check("unauthenticated → 401 on GET /ap/payments (AC9)", s == 401, f"status={s}")

    finally:
        # Clean up in FK-safe order: payment allocations → payments → journal
        # lines → journal entries (ap_payment / ap_bill / po_receipt, source-linked)
        # → bill lines → bills → PO lines → POs → inventory txns → item → location
        # → vendor → audit rows → throwaway user → throwaway role. The seeded admin,
        # accounts, and "Main" location are left in place (real deploy state).
        async with session_factory() as session:
            # Idempotent: keep the default location present for re-runs on a fresh DB.
            await seed_default_location(session)

            if payment_id is not None:
                await session.execute(
                    delete(PaymentAllocation).where(
                        PaymentAllocation.payment_id == payment_id
                    )
                )
                await session.execute(delete(Payment).where(Payment.id == payment_id))

            entry_ids: list[str] = []
            for source_type, source_id in (
                ("ap_payment", payment_id),
                ("ap_bill", bill_id),
                ("po_receipt", line_id),
            ):
                if source_id is not None:
                    ids = (
                        await session.execute(
                            select(JournalEntry.id).where(
                                JournalEntry.source_type == source_type,
                                JournalEntry.source_id == source_id,
                            )
                        )
                    ).scalars().all()
                    entry_ids.extend(ids)
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )

            if bill_id is not None:
                await session.execute(delete(BillLine).where(BillLine.bill_id == bill_id))
                await session.execute(delete(Bill).where(Bill.id == bill_id))
            if po_id is not None:
                await session.execute(
                    delete(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
                )
                await session.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
            if item_id is not None:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id == item_id)
                )
                await session.execute(delete(InventoryItem).where(InventoryItem.id == item_id))
            if loc_id is not None:
                await session.execute(delete(StockLocation).where(StockLocation.id == loc_id))
            if vendor_id is not None:
                await session.execute(delete(Partner).where(Partner.id == vendor_id))

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
