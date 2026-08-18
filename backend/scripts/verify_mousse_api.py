# ABOUTME: Router-level live-HTTP verification for the MOUSSE work-order endpoints (Phase 10,
# ABOUTME: MOUSSE-01 SC6). Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in the
# ABOUTME: image) to prove the mousse:read/mousse:write RBAC gate returns 200/401/403 on every
# ABOUTME: route, and that create/release/issue/complete write attributable AuditLog rows; exits
# ABOUTME: non-zero on FAIL and self-cleans (WO rows, JEs, fixtures, throwaway users/roles).
"""
Router-level live-HTTP verification for the MOUSSE work-order endpoints (Phase 10).

WHY THIS EXISTS (the router proof — the companion to verify_mousse.py):
  verify_mousse.py drives the mousse SERVICE functions directly and so proves the
  costing/FSM numbers, but it can never exercise the two things that live only in
  the ROUTER: the audit rows written by write_audit and the RBAC gate enforced by
  require_permission("mousse:read" / "mousse:write"). This script closes that gap
  (SC6) by making REAL HTTP calls against the running api and asserting, for EACH
  route:
    - every MUTATION (create / release / issue / hold / resume / complete / cancel)
      accepts a mousse:write token (2xx), refuses a token WITHOUT mousse:write
      (403 — a mousse:read-only user), and refuses an unauthenticated request (401);
    - every READ (list / detail) accepts a mousse:read token (200), refuses a
      no-permission token (403), and refuses an unauthenticated request (401);
    - after a successful create / release / issue / complete driven over HTTP, the
      matching AuditLog row (work_order.created / released / issued / completed)
      exists, is attributable to the acting user (actor_id), and targets the WO.

  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so this mints THREE throwaway users backed by throwaway roles:
    * writer   — role holding mousse:read + mousse:write (drives the whole lifecycle
                 over HTTP; the audit rows are attributable to THIS user);
    * reader   — role holding ONLY mousse:read (200 on reads, 403 on every mutation);
    * noperm   — no roles at all (403 on reads, the no-permission case).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_mousse.py which owns its own engine):
  # From inside the running dev api container (api binds 0.0.0.0:8000):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_mousse_api.py
  # Or as a one-off container on the compose network, pointing at the api service:
  podman run --rm --network compose_default --env-file .env \
      -e POSTGRES_HOST=db -e PYTHONPATH=/app -e BNS_API_BASE_URL=http://api:8000 \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_mousse_api.py

The script builds its OWN buildable PLUM parts / SYERP items / stock fixtures via the
service functions (so it has real work orders to drive over HTTP), creates the work
orders and posts the JEs over HTTP, and CLEANS UP after itself in a finally block
(work-order issues -> mousse JEs -> components -> work orders -> inventory txns ->
items -> BOM items -> revisions -> parts -> the audit_log rows it wrote -> the three
throwaway users + roles), so it is safe to re-run against the same database. The
seeded "Main" location and 1130/1140 GL accounts are reused and left in place.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_mousse_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.mousse.models import WorkOrder, WorkOrderComponent, WorkOrderIssue
from app.modules.plum.models import PlumBomItem, PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate
from app.modules.syerp.service import create_item, post_receipt

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/mousse"


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
    relative to the /api/v1/mousse base. HTTP error statuses are captured and
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


# ---------------------------------------------------------------------------
# Fixture builders — a buildable PLUM part (Released rev + 2-child BOM + linked
# stocked SYERP items + a linked FG item), so each WO can be driven end-to-end.
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
        description=f"verify_mousse_api {part_number}",
        unit_of_measure=uom,
        released_at=datetime.now(UTC) if released else None,
    )
    session.add(rev)
    await session.flush()
    return part.id, rev.id


async def _link_item(session_factory, unique: str, tag: str, part_id: str | None) -> str:
    """Create a SYERP InventoryItem (optionally PLUM-linked) and return its id."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-MOUSSE-API {tag} {unique}",
                unit_of_measure="ea",
                plum_part_id=part_id,
            ),
        )
        return item.id


async def _build_buildable_part(
    session_factory,
    unique: str,
    tag: str,
    main_id: int,
    part_ids: set[str],
    item_ids: set[str],
) -> str:
    """
    Build a fully-buildable PLUM part: Released rev + a 2-child direct BOM
    (qty_per 2 and 3), each child linked to a stocked InventoryItem (100 on-hand),
    and a linked FG item for the parent. Returns the FG PLUM part id (the WO build
    target). Registers all created part/item ids for the finally cleanup.
    """
    async with session_factory() as session:
        fg_part_id, fg_rev_id = await _make_part_with_revision(
            session, f"P-MO-API-{unique}-{tag}-fg", released=True
        )
        child_a_id, _ = await _make_part_with_revision(
            session, f"P-MO-API-{unique}-{tag}-ca", released=True
        )
        child_b_id, _ = await _make_part_with_revision(
            session, f"P-MO-API-{unique}-{tag}-cb", released=True
        )
        part_ids.update({fg_part_id, child_a_id, child_b_id})
        session.add(
            PlumBomItem(
                parent_revision_id=fg_rev_id, child_part_id=child_a_id,
                qty=Decimal("2"), sort_order=0,
            )
        )
        session.add(
            PlumBomItem(
                parent_revision_id=fg_rev_id, child_part_id=child_b_id,
                qty=Decimal("3"), sort_order=1,
            )
        )
        await session.commit()

    fg_item_id = await _link_item(session_factory, unique, f"{tag}-FG", fg_part_id)
    item_a_id = await _link_item(session_factory, unique, f"{tag}-CA", child_a_id)
    item_b_id = await _link_item(session_factory, unique, f"{tag}-CB", child_b_id)
    # Register every created item (incl. the FG item, which receives stock on
    # completion) so the finally cleanup removes them and their txns.
    item_ids.update({fg_item_id, item_a_id, item_b_id})
    async with session_factory() as session:
        await post_receipt(session, item_a_id, main_id, Decimal("100"), Decimal("3"), str(uuid.uuid4()))
    async with session_factory() as session:
        await post_receipt(session, item_b_id, main_id, Decimal("100"), Decimal("5"), str(uuid.uuid4()))
    return fg_part_id


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
    part_ids: set[str] = set()
    item_ids: set[str] = set()
    wo_ids: set[str] = set()
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
                            Permission.code.in_(["mousse:read", "mousse:write"])
                        )
                    )
                ).scalars().all()
            }
            if "mousse:read" not in perms or "mousse:write" not in perms:
                print("FAIL: seeded mousse:read/mousse:write permissions not found.")
                sys.exit(2)

            writer_role = Role(
                name=f"verify-mousse-writer-{unique}",
                description="VERIFY throwaway role: mousse:read + mousse:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["mousse:read"], perms["mousse:write"]]
            )

            reader_role = Role(
                name=f"verify-mousse-reader-{unique}",
                description="VERIFY throwaway role: mousse:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["mousse:read"])

            writer = User(
                email=f"verify-mousse-writer-{unique}@example.test",
                hashed_password=hash_password("verify-mousse-writer-pw"),
                full_name="VERIFY mousse:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-mousse-reader-{unique}@example.test",
                hashed_password=hash_password("verify-mousse-reader-pw"),
                full_name="VERIFY mousse:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-mousse-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-mousse-noperm-pw"),
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

        # Buildable fixtures: MAIN drives create->release->issue->complete;
        # HOLD drives create->release->issue->hold->resume; CANCEL is cancelled
        # from Draft. Each has its own PLUM part / BOM / stocked items.
        main_part_id = await _build_buildable_part(
            session_factory, unique, "MAIN", main_id, part_ids, item_ids
        )
        hold_part_id = await _build_buildable_part(
            session_factory, unique, "HOLD", main_id, part_ids, item_ids
        )
        async with session_factory() as session:
            cancel_part_id, _ = await _make_part_with_revision(
                session, f"P-MO-API-{unique}-CANCEL-fg", released=True
            )
            part_ids.add(cancel_part_id)
            await session.commit()

        # ===================================================================
        # (A) MUTATION HAPPY PATH over HTTP with the writer (mousse:write) +
        #     attributable AuditLog rows (SC6).
        # ===================================================================
        # --- create ---
        create_body = {
            "plum_part_id": main_part_id,
            "planned_qty": "10",
            "target_location_id": main_id,
        }
        s, body = http("POST", "/work-orders", writer_token, create_body)
        wo_main_id = body.get("id") if isinstance(body, dict) else None
        if wo_main_id:
            wo_ids.add(wo_main_id)
        check(
            "(A) POST /work-orders with mousse:write → 201 with a Draft WO id",
            s == 201 and wo_main_id is not None and body.get("status") == "draft",
            f"status={s} body={body!r}",
        )
        created_audit = await _audit_row(session_factory, "work_order.created", wo_main_id)
        check(
            "(A/SC6) a work_order.created audit row exists, attributable to the writer, "
            "targeting the created WO",
            created_audit is not None
            and created_audit.actor_id == writer_id
            and created_audit.target_type == "work_order",
            f"audit={created_audit!r}",
        )

        # --- release ---
        s, body = http("POST", f"/work-orders/{wo_main_id}/release", writer_token)
        check(
            "(A) POST /work-orders/{id}/release with mousse:write → 200, status Released",
            s == 200 and isinstance(body, dict) and body.get("status") == "released",
            f"status={s} body={body!r}",
        )
        released_audit = await _audit_row(session_factory, "work_order.released", wo_main_id)
        check(
            "(A/SC6) a work_order.released audit row exists, attributable to the writer",
            released_audit is not None
            and released_audit.actor_id == writer_id
            and released_audit.target_type == "work_order",
            f"audit={released_audit!r}",
        )

        # --- fetch the resolved components (needed to build the issue payload) ---
        s, detail = http("GET", f"/work-orders/{wo_main_id}", writer_token)
        components = detail.get("components", []) if isinstance(detail, dict) else []
        issue_lines = [
            {"component_id": c["id"], "quantity": c["qty_required"]} for c in components
        ]
        check(
            "(A) GET /work-orders/{id} returns the 2 snapshot component lines",
            s == 200 and len(issue_lines) == 2,
            f"status={s} lines={len(issue_lines)}",
        )

        # --- issue all components ---
        s, body = http(
            "POST", f"/work-orders/{wo_main_id}/issue", writer_token, {"lines": issue_lines}
        )
        check(
            "(A) POST /work-orders/{id}/issue with mousse:write → 200, both lines issued "
            "(Σ 20*3 + 30*5 == 210.000000 into WIP)",
            s == 200
            and isinstance(body, dict)
            and body.get("lines_issued") == 2
            and Decimal(str(body.get("total_issued_value"))) == Decimal("210.000000"),
            f"status={s} body={body!r}",
        )
        issued_audit = await _audit_row(session_factory, "work_order.issued", wo_main_id)
        check(
            "(A/SC6) a work_order.issued audit row exists, attributable to the writer",
            issued_audit is not None
            and issued_audit.actor_id == writer_id
            and issued_audit.target_type == "work_order",
            f"audit={issued_audit!r}",
        )

        # --- complete (fully issued → no override needed) ---
        s, body = http(
            "POST", f"/work-orders/{wo_main_id}/complete", writer_token,
            {"override_incomplete": False},
        )
        check(
            "(A) POST /work-orders/{id}/complete with mousse:write → 200, received 10 FG, "
            "cleared 210 from WIP",
            s == 200
            and isinstance(body, dict)
            and Decimal(str(body.get("quantity_received"))) == Decimal("10")
            and Decimal(str(body.get("wip_cleared_value"))) == Decimal("210.000000"),
            f"status={s} body={body!r}",
        )
        completed_audit = await _audit_row(session_factory, "work_order.completed", wo_main_id)
        check(
            "(A/SC6) a work_order.completed audit row exists, attributable to the writer",
            completed_audit is not None
            and completed_audit.actor_id == writer_id
            and completed_audit.target_type == "work_order",
            f"audit={completed_audit!r}",
        )

        # ===================================================================
        # (B) HOLD / RESUME 2xx over HTTP (mousse:write) — SC1b mutations.
        # ===================================================================
        s, body = http("POST", "/work-orders", writer_token,
                       {"plum_part_id": hold_part_id, "planned_qty": "10",
                        "target_location_id": main_id})
        wo_hold_id = body.get("id") if isinstance(body, dict) else None
        if wo_hold_id:
            wo_ids.add(wo_hold_id)
        http("POST", f"/work-orders/{wo_hold_id}/release", writer_token)
        s2, hdetail = http("GET", f"/work-orders/{wo_hold_id}", writer_token)
        hlines = [
            {"component_id": c["id"], "quantity": c["qty_required"]}
            for c in (hdetail.get("components", []) if isinstance(hdetail, dict) else [])
        ]
        http("POST", f"/work-orders/{wo_hold_id}/issue", writer_token, {"lines": hlines})
        s, body = http("POST", f"/work-orders/{wo_hold_id}/hold", writer_token)
        check(
            "(B) POST /work-orders/{id}/hold with mousse:write → 200, status On Hold",
            s == 200 and isinstance(body, dict) and body.get("status") == "on_hold",
            f"status={s} body={body!r}",
        )
        s, body = http("POST", f"/work-orders/{wo_hold_id}/resume", writer_token)
        check(
            "(B) POST /work-orders/{id}/resume with mousse:write → 200, status In Progress",
            s == 200 and isinstance(body, dict) and body.get("status") == "in_progress",
            f"status={s} body={body!r}",
        )

        # ===================================================================
        # (C) CANCEL 2xx over HTTP (mousse:write) — from Draft.
        # ===================================================================
        s, body = http("POST", "/work-orders", writer_token,
                       {"plum_part_id": cancel_part_id, "planned_qty": "1",
                        "target_location_id": main_id})
        wo_cancel_id = body.get("id") if isinstance(body, dict) else None
        if wo_cancel_id:
            wo_ids.add(wo_cancel_id)
        s, body = http("POST", f"/work-orders/{wo_cancel_id}/cancel", writer_token)
        check(
            "(C) POST /work-orders/{id}/cancel with mousse:write → 200, status Cancelled",
            s == 200 and isinstance(body, dict) and body.get("status") == "cancelled",
            f"status={s} body={body!r}",
        )

        # ===================================================================
        # (D) RBAC on every MUTATION route: a token WITHOUT mousse:write (the
        #     mousse:read-only reader) → 403; unauthenticated → 401. These auth
        #     failures short-circuit BEFORE the service, so firing them against
        #     the already-driven WOs cannot mutate state (SC6).
        # ===================================================================
        mutation_routes = [
            ("POST", "/work-orders", create_body),
            ("POST", f"/work-orders/{wo_main_id}/release", None),
            ("POST", f"/work-orders/{wo_main_id}/issue", {"lines": issue_lines}),
            ("POST", f"/work-orders/{wo_hold_id}/hold", None),
            ("POST", f"/work-orders/{wo_hold_id}/resume", None),
            ("POST", f"/work-orders/{wo_main_id}/complete", {"override_incomplete": False}),
            ("POST", f"/work-orders/{wo_main_id}/cancel", None),
        ]
        for method, path, payload in mutation_routes:
            s, _ = http(method, path, reader_token, payload)
            check(
                f"(D) mousse:read-only token → 403 on {method} {path} (no mousse:write)",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None, payload)
            check(
                f"(D) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

        # ===================================================================
        # (E) RBAC on every READ route: mousse:read token → 200; no-permission
        #     token → 403; unauthenticated → 401 (SC6).
        # ===================================================================
        read_routes = [
            ("GET", "/work-orders"),
            ("GET", f"/work-orders/{wo_main_id}"),
        ]
        for method, path in read_routes:
            s, _ = http(method, path, reader_token)
            check(
                f"(E) mousse:read token → 200 on {method} {path}",
                s == 200,
                f"status={s}",
            )
            s, _ = http(method, path, noperm_token)
            check(
                f"(E) no-permission token → 403 on {method} {path}",
                s == 403,
                f"status={s}",
            )
            s, _ = http(method, path, None)
            check(
                f"(E) unauthenticated → 401 on {method} {path}",
                s == 401,
                f"status={s}",
            )

    finally:
        await _cleanup(session_factory, part_ids, item_ids, wo_ids, user_ids, role_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    part_ids: set[str],
    item_ids: set[str],
    wo_ids: set[str],
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: work-order issues -> the WOs'
    source-linked journal lines/entries -> components -> work orders -> the
    audit_log rows targeting the WOs -> inventory txns -> items -> BOM items ->
    revisions -> parts -> throwaway users -> throwaway roles. The seeded "Main"
    location and 1130/1140 GL accounts are reused and left in place.
    """
    async with session_factory() as session:
        # Idempotent: keep the default location present for re-runs on a fresh DB.
        await seed_default_location(session)

        wo_id_list = list(wo_ids)
        item_id_list = list(item_ids)
        part_id_list = list(part_ids)

        if wo_id_list:
            await session.execute(
                delete(WorkOrderIssue).where(WorkOrderIssue.work_order_id.in_(wo_id_list))
            )
            entry_ids = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "mousse_work_order",
                        JournalEntry.source_id.in_(wo_id_list),
                    )
                )
            ).scalars().all()
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )
            await session.execute(
                delete(WorkOrderComponent).where(
                    WorkOrderComponent.work_order_id.in_(wo_id_list)
                )
            )
            await session.execute(delete(WorkOrder).where(WorkOrder.id.in_(wo_id_list)))
            await session.execute(
                delete(AuditLog).where(AuditLog.target_id.in_(wo_id_list))
            )

        if item_id_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_id_list))
            )
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_id_list))
            )

        if part_id_list:
            await session.execute(
                delete(PlumBomItem).where(PlumBomItem.child_part_id.in_(part_id_list))
            )
            await session.execute(
                delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(part_id_list))
            )
            await session.execute(delete(PlumPart).where(PlumPart.id.in_(part_id_list)))

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
