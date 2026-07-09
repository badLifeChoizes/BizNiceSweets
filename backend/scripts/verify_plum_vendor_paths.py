# ABOUTME: Standalone live-DB verification for PLUM's four SYERP-vendor code paths (Phase 7, SC1).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: add_avl_link / build_json_export / validate_import / commit_import to prove no ImportError.
"""
Standalone live-DB verification for PLUM's SYERP-vendor code paths (Phase 7, SC1).

WHY THIS EXISTS (the phase's regression gate):
  PLUM's service layer reaches SYERP through four *function-local* imports of
  ``Partner as SyerpPartner``. Before Phase 7 they each read
  ``from app.modules.syerp.models import SyerpPartner`` — a class that does not
  exist — so every vendor-touching request died with ImportError -> HTTP 500:
  AVL linking (PLUM-07) and vendor import/export (PLUM-10) were both broken in
  production.

  Because the imports are function-LOCAL, they are independent: a broken import
  inside ``commit_import`` stays invisible until commit_import actually runs. Four
  sites therefore need four drives. Nothing else covers them — the DB-backed
  pytest tests (tests/plum/test_avl.py, test_import_export.py) silently SKIP under
  plain pytest while the live harness is broken (D-P7-4, BACKLOG p1), so they have
  never once executed and would not catch a re-break.

  Sites guarded (service.py, at the time of writing):
    1. add_avl_link        (~1644)  — vendor is_vendor=True validation
    2. build_json_export   (~2159)  — vendor_id -> vendor_code resolution
    3. validate_import     (~2617)  — vendor_code cross-reference, side-effect free
    4. commit_import       (~2750)  — vendor_code -> vendor_id upsert

HOW TO RUN (the compose ``db`` service is not host-published). PYTHONPATH is
required — python puts scripts/ on sys.path, not the /app package root:
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1)
  podman exec -w /app -e PYTHONPATH=/app "$API" python scripts/verify_plum_vendor_paths.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. add_avl_link links a real is_vendor=True Partner to a part (no ImportError).
  2. add_avl_link REJECTS a non-vendor Partner with HTTP 422 — proves the is_vendor
     filter still runs and was not lost when the import was aliased.
  3. build_json_export emits our part with the vendor's CODE resolved (the export's
     vendor lookup ran rather than short-circuiting on an empty vendor_ids set).
  4. validate_import accepts a payload whose avl.vendor_code resolves, reporting
     no errors for that row.
  5. validate_import REPORTS an error for an unknown vendor_code — proves the
     lookup executed rather than silently passing everything.
  6. commit_import upserts a PlumAvlLink for a valid vendor_code, and the link is
     readable back with the right vendor_id.

The script uses uniquely-suffixed throwaway parts/vendors and CLEANS UP after
itself (deletes only the rows it created) in a finally block, so it is safe to
re-run against the same database and never disturbs real data.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (PlumAvlLink.vendor_id FKs syerp_partner, whose table must be registered).
import app.core.models  # noqa: F401
from app.modules.plum.models import PlumAvlLink, PlumPart, PlumPartRevision
from app.modules.plum.schemas import AvlLinkCreate, PartCreate
from app.modules.plum.service import (
    add_avl_link,
    build_json_export,
    commit_import,
    create_part,
    validate_import,
)
from app.modules.syerp.models import Partner

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0


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
    """
    Assemble the asyncpg DSN directly from POSTGRES_* environment variables.

    Mirrors app.core.config.Settings.database_url but reads os.environ itself so
    the script is fully self-contained and never touches the test conftest.
    """
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    vendor_code = f"V-VP-{unique}"[:20]
    customer_code = f"C-VP-{unique}"[:20]
    part_number = f"P-VP-{unique}"  # non-numeric on purpose: never disturbs auto-numbering
    import_part_number = f"P-VPI-{unique}"

    vendor_id: str | None = None
    customer_id: str | None = None
    part_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Fixtures: one is_vendor=True Partner, one is_vendor=False Partner, one part.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor = Partner(code=vendor_code, name=f"Vendor {unique}", is_vendor=True)
            customer = Partner(
                code=customer_code, name=f"Customer {unique}", is_vendor=False, is_customer=True
            )
            session.add_all([vendor, customer])
            await session.commit()
            vendor_id, customer_id = vendor.id, customer.id

        async with session_factory() as session:
            part = await create_part(
                session, PartCreate(part_number=part_number, description=f"vendor-path probe {unique}")
            )
            await session.commit()
            part_id = part.id

        # -------------------------------------------------------------------
        # 1. add_avl_link with a real vendor — site 1 must not raise ImportError.
        # -------------------------------------------------------------------
        try:
            async with session_factory() as session:
                link = await add_avl_link(
                    session,
                    part_id,
                    AvlLinkCreate(vendor_id=vendor_id, vendor_part_number="VP-001", preferred=True),
                    actor_id,
                )
                await session.commit()
            check(
                "add_avl_link links an is_vendor=True Partner (no ImportError)",
                str(link.get("vendor_id")) == str(vendor_id),
                f"returned {link!r}",
            )
        except Exception as exc:  # noqa: BLE001 - an ImportError here IS the regression
            check(
                "add_avl_link links an is_vendor=True Partner (no ImportError)",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )

        # -------------------------------------------------------------------
        # 2. add_avl_link must still REJECT a non-vendor Partner (is_vendor filter intact).
        # -------------------------------------------------------------------
        try:
            async with session_factory() as session:
                await add_avl_link(
                    session, part_id, AvlLinkCreate(vendor_id=customer_id), actor_id
                )
                await session.commit()
            check(
                "add_avl_link rejects a non-vendor Partner (is_vendor filter intact)",
                False,
                "a Partner with is_vendor=False was accepted",
            )
        except HTTPException as exc:
            check(
                "add_avl_link rejects a non-vendor Partner (is_vendor filter intact)",
                exc.status_code == 422,
                f"expected 422, got {exc.status_code}",
            )
        except Exception as exc:  # noqa: BLE001
            check(
                "add_avl_link rejects a non-vendor Partner (is_vendor filter intact)",
                False,
                f"raised {type(exc).__name__}: {exc} (expected HTTPException 422)",
            )

        # -------------------------------------------------------------------
        # 3. build_json_export resolves vendor_id -> vendor_code (site 2).
        #    The AVL row seeded above guarantees vendor_ids is non-empty, so the
        #    lookup runs instead of short-circuiting.
        # -------------------------------------------------------------------
        try:
            async with session_factory() as session:
                export = await build_json_export(session)
            exported = [p for p in export.get("parts", []) if p.get("part_number") == part_number]
            codes = [a.get("vendor_code") for p in exported for a in p.get("avl", [])]
            check(
                "build_json_export runs the vendor lookup (no ImportError)",
                len(exported) == 1,
                f"expected our part once in the export, found {len(exported)}",
            )
            check(
                "build_json_export resolves vendor_id -> vendor_code",
                vendor_code in codes,
                f"expected {vendor_code!r} among {codes!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check(
                "build_json_export runs the vendor lookup (no ImportError)", False,
                f"raised {type(exc).__name__}: {exc}",
            )
            check("build_json_export resolves vendor_id -> vendor_code", False, "export raised")

        # -------------------------------------------------------------------
        # 4/5. validate_import — site 3. Known vendor_code passes; unknown one errors.
        # -------------------------------------------------------------------
        def _payload(code: str, pn: str) -> dict:
            return {
                "parts": [
                    {
                        "part_number": pn,
                        "active": True,
                        "revisions": [],
                        "avl": [{"vendor_code": code, "vendor_part_number": "VP-IMP", "preferred": False}],
                    }
                ]
            }

        try:
            async with session_factory() as session:
                preview = await validate_import(session, _payload(vendor_code, import_part_number))
            check(
                "validate_import accepts a resolvable vendor_code (no ImportError)",
                len(preview.errors) == 0,
                f"unexpected errors: {[e.message for e in preview.errors]}",
            )
        except Exception as exc:  # noqa: BLE001
            check(
                "validate_import accepts a resolvable vendor_code (no ImportError)",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )

        try:
            async with session_factory() as session:
                preview = await validate_import(
                    session, _payload(f"V-NOPE-{unique}", import_part_number)
                )
            check(
                "validate_import reports an unknown vendor_code (lookup really ran)",
                len(preview.errors) > 0,
                "an unknown vendor_code produced no error — the lookup did not run",
            )
        except Exception as exc:  # noqa: BLE001
            check(
                "validate_import reports an unknown vendor_code (lookup really ran)",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )

        # -------------------------------------------------------------------
        # 6. commit_import — site 4. Upserts the AVL link against the vendor code.
        # -------------------------------------------------------------------
        try:
            async with session_factory() as session:
                await commit_import(session, _payload(vendor_code, import_part_number), actor_id)
                await session.commit()

            async with session_factory() as session:
                imported = (
                    await session.execute(
                        select(PlumPart).where(PlumPart.part_number == import_part_number)
                    )
                ).scalars().first()
                linked_vendor_ids = []
                if imported is not None:
                    linked_vendor_ids = list(
                        (
                            await session.execute(
                                select(PlumAvlLink.vendor_id).where(
                                    PlumAvlLink.part_id == imported.id
                                )
                            )
                        ).scalars().all()
                    )
            check(
                "commit_import creates the imported part (no ImportError)",
                imported is not None,
                f"{import_part_number} not found after commit",
            )
            check(
                "commit_import upserts the AVL link against the resolved vendor_id",
                str(vendor_id) in {str(v) for v in linked_vendor_ids},
                f"expected vendor_id {vendor_id} among {linked_vendor_ids!r}",
            )
        except Exception as exc:  # noqa: BLE001
            check(
                "commit_import creates the imported part (no ImportError)",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )
            check(
                "commit_import upserts the AVL link against the resolved vendor_id",
                False,
                "commit raised",
            )

    finally:
        # -------------------------------------------------------------------
        # Clean up only the rows this script created (children before parents).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            part_ids = list(
                (
                    await session.execute(
                        select(PlumPart.id).where(
                            PlumPart.part_number.in_([part_number, import_part_number])
                        )
                    )
                ).scalars().all()
            )
            if part_ids:
                await session.execute(delete(PlumAvlLink).where(PlumAvlLink.part_id.in_(part_ids)))
                await session.execute(
                    delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(part_ids))
                )
                await session.execute(delete(PlumPart).where(PlumPart.id.in_(part_ids)))
            partner_ids = [p for p in (vendor_id, customer_id) if p is not None]
            if partner_ids:
                await session.execute(delete(Partner).where(Partner.id.in_(partner_ids)))
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
