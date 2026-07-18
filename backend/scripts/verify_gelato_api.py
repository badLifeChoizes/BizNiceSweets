# ABOUTME: Router-level live-HTTP verification for the GELATO bins & putaway endpoints
# ABOUTME: (Phase 12a, GELATO-01). Drives the RUNNING api over HTTP (stdlib urllib — httpx is
# ABOUTME: not in the image) to prove the gelato:read/gelato:write RBAC gate returns 200/401/403
# ABOUTME: on every bins/putaway route, and that bin create/update/archive + putaway write
# ABOUTME: attributable AuditLog rows; exits non-zero on FAIL and self-cleans (bins, txns, item,
# ABOUTME: location, audit rows, throwaway users/roles).
"""
Router-level live-HTTP verification for the GELATO endpoints (Phase 12a).

WHY THIS EXISTS (the router proof — the companion to verify_gelato.py):
  verify_gelato.py drives the gelato SERVICE functions directly and so proves the
  bin CRUD, the putaway ledger legs and the suggestion heuristic, but it can never
  exercise the two things that live only in the ROUTER: the audit rows written by
  write_audit and the RBAC gate enforced by require_permission("gelato:read" /
  "gelato:write"). This script closes that gap (the 9a/11a HTTP-verify discipline)
  by making REAL HTTP calls against the running api and asserting, for EACH route:
    - every MUTATION (bin create / patch / archive / putaway) accepts a gelato:write
      token (2xx), refuses a token WITHOUT gelato:write (403 — a gelato:read-only
      user), and refuses an unauthenticated request (401);
    - every READ (bins list / unbinned / suggestion) accepts a gelato:read token
      (200), refuses a no-permission token (403), and refuses an unauthenticated
      request (401);
    - after a successful bin create / update / archive and a putaway driven over
      HTTP, the matching AuditLog row (bin.created / bin.updated / bin.archived /
      inventory.putaway) exists, is attributable to the acting user (actor_id), and
      targets the entity (target_type/target_id).

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so this mints THREE throwaway users backed by throwaway roles:
    * writer   — role holding gelato:read + gelato:write (drives the whole lifecycle
                 over HTTP; the audit rows are attributable to THIS user);
    * reader   — role holding ONLY gelato:read (200 on reads, 403 on every mutation);
    * noperm   — no roles at all (403 on reads, the no-permission case).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_gelato.py which owns its own engine):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato_api.py

The script builds its OWN throwaway SYERP fixtures via the service functions (a stock
location + an inventory item + a received-in unbinned pool, so there is real stock to
put away), creates the bins over HTTP, drives a putaway, and CLEANS UP after itself in
a finally block (audit rows -> inventory txns -> bins -> item -> location -> the three
throwaway users + roles), so it is safe to re-run against the same database.
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
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_gelato_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.gelato.models import Bin
from app.modules.syerp.models import InventoryItem, InventoryTxn, StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, StockLocationCreate
from app.modules.syerp.service import create_item, create_location, post_receipt

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
    bin_ids: set[int] = set()
    item_id: str | None = None
    location_id: int | None = None
    audit_targets: set[str] = set()
    user_ids: list[str] = []
    role_ids: list[int] = []

    writer_id: str | None = None
    reader_id: str | None = None
    noperm_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Setup: mint the three throwaway users (writer = read+write,
        # reader = read-only, noperm = no roles); build a throwaway SYERP
        # location + item + received-in unbinned pool to put away.
        # -------------------------------------------------------------------
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
                name=f"verify-gelato-writer-{unique}",
                description="VERIFY throwaway role: gelato:read + gelato:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["gelato:read"], perms["gelato:write"]]
            )

            reader_role = Role(
                name=f"verify-gelato-reader-{unique}",
                description="VERIFY throwaway role: gelato:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["gelato:read"])

            writer = User(
                email=f"verify-gelato-writer-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-writer-pw"),
                full_name="VERIFY gelato:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-gelato-reader-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-reader-pw"),
                full_name="VERIFY gelato:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-gelato-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-gelato-noperm-pw"),
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

        # Throwaway location + item + a received-in unbinned pool (100 @ 5) so the
        # putaway has real stock to draw from the location's unbinned pool.
        async with session_factory() as session:
            location = await create_location(
                session, StockLocationCreate(name=f"VERIFY-GELATO-API loc {unique}")
            )
            location_id = location.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(
                    name=f"VERIFY-GELATO-API item {unique}", unit_of_measure="ea"
                ),
            )
            item_id = item.id
        async with session_factory() as session:
            await post_receipt(
                session, item_id, location_id, Decimal("100"), Decimal("5"), writer_id
            )

        # ===================================================================
        # (A) MUTATION HAPPY PATH over HTTP with the writer (gelato:write) +
        #     attributable AuditLog rows.
        # ===================================================================
        # --- create the putaway target bin (A1, active) ---
        s, body = http(
            "POST", "/bins", writer_token,
            {"location_id": location_id, "code": f"A1-{unique}", "description": "target"},
        )
        bin_id = body.get("id") if isinstance(body, dict) else None
        if bin_id is not None:
            bin_ids.add(bin_id)
            audit_targets.add(str(bin_id))
        check(
            "(A) POST /gelato/bins with gelato:write → 201 with an active bin id",
            s == 201 and bin_id is not None and body.get("active") is True,
            f"status={s} body={body!r}",
        )
        created_audit = await _audit_row(session_factory, "bin.created", str(bin_id))
        check(
            "(A) a bin.created audit row exists, attributable to the writer, targeting the bin",
            created_audit is not None
            and created_audit.actor_id == writer_id
            and created_audit.target_type == "bin",
            f"audit={created_audit!r}",
        )

        # --- patch the bin's description ---
        s, body = http(
            "PATCH", f"/bins/{bin_id}", writer_token, {"description": "verify updated"}
        )
        check(
            "(A) PATCH /gelato/bins/{id} with gelato:write → 200, description applied",
            s == 200 and isinstance(body, dict) and body.get("description") == "verify updated",
            f"status={s} body={body!r}",
        )
        updated_audit = await _audit_row(session_factory, "bin.updated", str(bin_id))
        check(
            "(A) a bin.updated audit row exists, attributable to the writer",
            updated_audit is not None
            and updated_audit.actor_id == writer_id
            and updated_audit.target_type == "bin",
            f"audit={updated_audit!r}",
        )

        # --- create a SECOND bin (A2) and archive it (leaves A1 as the live target) ---
        s, body = http(
            "POST", "/bins", writer_token,
            {"location_id": location_id, "code": f"A2-{unique}"},
        )
        bin2_id = body.get("id") if isinstance(body, dict) else None
        if bin2_id is not None:
            bin_ids.add(bin2_id)
            audit_targets.add(str(bin2_id))
        check(
            "(A) POST /gelato/bins (second bin) with gelato:write → 201",
            s == 201 and bin2_id is not None,
            f"status={s} body={body!r}",
        )
        s, body = http("POST", f"/bins/{bin2_id}/archive", writer_token)
        check(
            "(A) POST /gelato/bins/{id}/archive with gelato:write → 200, active=False",
            s == 200 and isinstance(body, dict) and body.get("active") is False,
            f"status={s} body={body!r}",
        )
        archived_audit = await _audit_row(session_factory, "bin.archived", str(bin2_id))
        check(
            "(A) a bin.archived audit row exists, attributable to the writer",
            archived_audit is not None
            and archived_audit.actor_id == writer_id
            and archived_audit.target_type == "bin",
            f"audit={archived_audit!r}",
        )

        # --- GET reads (admin/writer holds gelato:read too) ---
        s, body = http("GET", f"/locations/{location_id}/bins", writer_token)
        listed_ids = [b["id"] for b in body] if isinstance(body, list) else []
        check(
            "(A) GET /gelato/locations/{id}/bins with gelato:read → 200, lists the live bin "
            "(archived A2 hidden by default)",
            s == 200 and bin_id in listed_ids and bin2_id not in listed_ids,
            f"status={s} body={body!r}",
        )

        s, body = http("GET", f"/locations/{location_id}/unbinned", writer_token)
        unbinned_rows = body if isinstance(body, list) else []
        our_row = next((r for r in unbinned_rows if r.get("item_id") == item_id), None)
        check(
            "(A) GET /gelato/locations/{id}/unbinned with gelato:read → 200, item has 100 "
            "unbinned awaiting putaway",
            s == 200 and our_row is not None
            and Decimal(str(our_row.get("unbinned_qty"))) == Decimal("100"),
            f"status={s} row={our_row!r}",
        )

        suggestion_q = "?" + urllib.parse.urlencode(
            {"item_id": item_id, "location_id": location_id}
        )
        s, body = http("GET", f"/putaway/suggestion{suggestion_q}", writer_token)
        check(
            "(A) GET /gelato/putaway/suggestion with gelato:read → 200, suggests the live bin",
            s == 200 and isinstance(body, dict) and body.get("suggested_bin_id") == bin_id,
            f"status={s} body={body!r}",
        )

        # --- execute the putaway (unbinned pool → A1) ---
        s, body = http(
            "POST", "/putaway", writer_token,
            {"item_id": item_id, "location_id": location_id, "to_bin_id": bin_id, "qty": "10"},
        )
        out_leg_id = (
            body.get("out_leg", {}).get("id") if isinstance(body, dict) else None
        )
        if out_leg_id:
            audit_targets.add(out_leg_id)
        check(
            "(A) POST /gelato/putaway with gelato:write → 200, 10 into the bin (bin_on_hand=10)",
            s == 200 and isinstance(body, dict)
            and Decimal(str(body.get("bin_on_hand"))) == Decimal("10")
            and out_leg_id is not None,
            f"status={s} body={body!r}",
        )
        putaway_audit = await _audit_row(session_factory, "inventory.putaway", out_leg_id)
        check(
            "(A) an inventory.putaway audit row exists, attributable to the writer, targeting "
            "the OUT-leg txn",
            putaway_audit is not None
            and putaway_audit.actor_id == writer_id
            and putaway_audit.target_type == "inventory_txn",
            f"audit={putaway_audit!r}",
        )

        # ===================================================================
        # (B) RBAC on every MUTATION route: a token WITHOUT gelato:write (the
        #     gelato:read-only reader) → 403; unauthenticated → 401. These auth
        #     failures short-circuit BEFORE the service, so firing them cannot
        #     mutate state.
        # ===================================================================
        mutation_routes = [
            ("POST", "/bins", {"location_id": location_id, "code": f"rbac-{unique}"}),
            ("PATCH", f"/bins/{bin_id}", {"description": "rbac"}),
            ("POST", f"/bins/{bin_id}/archive", None),
            ("POST", "/putaway",
             {"item_id": item_id, "location_id": location_id, "to_bin_id": bin_id, "qty": "1"}),
        ]
        for method, path, payload in mutation_routes:
            s, _ = http(method, path, reader_token, payload)
            check(
                f"(B) gelato:read-only token → 403 on {method} {path} (no gelato:write)",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None, payload)
            check(
                f"(B) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

        # ===================================================================
        # (C) RBAC on every READ route: gelato:read token → 200; no-permission
        #     token → 403; unauthenticated → 401.
        # ===================================================================
        read_routes = [
            ("GET", f"/locations/{location_id}/bins"),
            ("GET", f"/locations/{location_id}/unbinned"),
            ("GET", f"/putaway/suggestion{suggestion_q}"),
        ]
        for method, path in read_routes:
            s, _ = http(method, path, reader_token)
            check(
                f"(C) gelato:read token → 200 on {method} {path}",
                s == 200,
                f"status={s}",
            )
            s, _ = http(method, path, noperm_token)
            check(
                f"(C) no-permission token → 403 on {method} {path}",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None)
            check(
                f"(C) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

    finally:
        await _cleanup(
            session_factory,
            bin_ids,
            item_id,
            location_id,
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
    bin_ids: set[int],
    item_id: str | None,
    location_id: int | None,
    audit_targets: set[str],
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: the audit_log rows this run wrote ->
    inventory txns (they FK gelato_bin.bin_id + the item + location) -> bins -> item
    -> location -> throwaway users -> throwaway roles.
    """
    async with session_factory() as session:
        target_list = list(audit_targets)
        bin_id_list = list(bin_ids)

        if target_list:
            await session.execute(
                delete(AuditLog).where(AuditLog.target_id.in_(target_list))
            )
        if item_id is not None:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id == item_id)
            )
        if bin_id_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_id_list)))
        if item_id is not None:
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id == item_id)
            )
        if location_id is not None:
            await session.execute(
                delete(StockLocation).where(StockLocation.id == location_id)
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
