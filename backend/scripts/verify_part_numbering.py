# ABOUTME: Standalone live-DB verification for PLUM auto part-numbering (Phase 7, SC2).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and
# ABOUTME: drives the REAL generate_part_number() and exits non-zero on any failed assertion.
"""
Standalone live-DB verification script for ``generate_part_number`` (Phase 7, SC2).

WHY THIS EXISTS (the phase's regression gate):
  The backend live-DB pytest harness is broken (D-P7-4), so
  ``tests/plum/test_parts.py::test_generate_part_number_digit_boundary`` silently
  SKIPS under plain ``pytest`` — it has never once executed. Until that harness is
  repaired (BACKLOG p1), verifiable truth for part numbering must come from a
  STANDALONE run against LIVE Postgres. This script stands up its own async engine
  + sessionmaker from the ``POSTGRES_*`` environment variables and calls the REAL
  ``generate_part_number`` rather than reimplementing its query.

  It pins TWO defects that both produced production 500s:

  PLUM-01 (digit boundary) — the original lexicographic ``MAX(part_number)``
    ranked "P99999" above "P100000", so the generator handed back an already-taken
    number once the suffix crossed a digit-width boundary → duplicate-key 500.

  Phase-7 regression (int4 overflow) — the fix for PLUM-01 ordered by
    ``CAST(substring(part_number, 2) AS Integer)``. part_number is String(50) with
    no format constraint, so a legal create of "P9999999999" (suffix > int4 max)
    matched the ``^P[0-9]+$`` filter and overflowed the cast: Postgres raised
    "value out of range for type integer", and EVERY subsequent auto-numbered
    create returned 500 until the row was deleted by hand — a persistent,
    user-triggerable denial of service. The cast target is now Numeric, which
    cannot overflow for any 50-char digit string. Scenario 3 below is the guard.

HOW TO RUN (the compose ``db`` service is not host-published). PYTHONPATH is
required — python puts scripts/ on sys.path, not the /app package root:
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Exec into the running api container (it already has POSTGRES_* + the network):
  API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1)
  podman exec -w /app -e PYTHONPATH=/app "$API" python scripts/verify_part_numbering.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. Non-numeric P-series row ("P-DUPE-<u>") does not throw — the regex filter
     excludes it before the cast (PLUM-01 fix, pitfall 3).
  2. Digit boundary: with two adjacent numeric rows seeded, the generator returns
     the true numeric MAX+1 (computed independently in Python), strictly greater
     than every existing numeric suffix, colliding with no existing part_number.
  3. int4 overflow: with a suffix > 2^31-1 seeded, the generator STILL succeeds and
     still returns numeric MAX+1. Under the Integer cast this raised DataError and
     bricked auto-numbering for every user. THIS IS THE BLOCKER GUARD.

Scope: this script covers the SQL half of generate_part_number (regex filter, cast
target, ordering) — the half that needs real Postgres semantics. The pure-Python
half (the ``max_pn is None`` -> "P00001" branch and the ``f"P{suffix+1:05d}"``
increment) is covered without a database by tests/plum/test_part_number.py, which
runs in the ordinary pytest suite. Same split as Phase 8's _next_item_code.

The script uses uniquely-suffixed throwaway part numbers and CLEANS UP after itself
(deletes only the rows it created) in a finally block, so it is safe to re-run
against the same database and never disturbs real parts.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated.
import app.core.models  # noqa: F401
from app.modules.plum.models import PlumPart
from app.modules.plum.service import generate_part_number

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0

_NUMERIC_PN = re.compile(r"^P[0-9]+$")


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


# ---------------------------------------------------------------------------
# Own async engine from POSTGRES_* env (NOT the broken conftest fixtures)
# ---------------------------------------------------------------------------


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


async def _max_numeric_suffix(session_factory: async_sessionmaker) -> int:
    """True numeric MAX over ^P[0-9]+$ rows, computed in Python (independent oracle)."""
    async with session_factory() as session:
        rows = (await session.execute(select(PlumPart.part_number))).scalars().all()
    suffixes = [int(pn[1:]) for pn in rows if _NUMERIC_PN.match(pn)]
    return max(suffixes) if suffixes else 0


async def _all_part_numbers(session_factory: async_sessionmaker) -> set[str]:
    async with session_factory() as session:
        return set((await session.execute(select(PlumPart.part_number))).scalars().all())


async def _seed(session_factory: async_sessionmaker, part_number: str) -> str:
    """Insert a bare PlumPart header row (no revision needed for numbering)."""
    part_id = str(uuid.uuid4())
    async with session_factory() as session:
        session.add(PlumPart(id=part_id, part_number=part_number, active=True))
        await session.commit()
    return part_id


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    unique = uuid.uuid4().hex[:8]
    seeded_ids: list[str] = []

    # Uniquely-suffixed so concurrent/repeat runs never collide on the unique index.
    # The numeric ones must still be numeric, so uniqueness comes from a high prefix
    # that is far above any real part number yet well inside int4 (scenarios 1-2),
    # and deliberately far OUTSIDE int4 for scenario 3.
    base = 900_000 + int(unique[:4], 16) % 1000  # e.g. P900123 / P900124
    pn_low = f"P{base:05d}"
    pn_high = f"P{base + 1:05d}"
    pn_nonnumeric = f"P-DUPE-{unique}"
    pn_overflow = f"P{2_147_483_647 + base}"  # strictly > int4 max

    try:
        # -------------------------------------------------------------------
        # 1. Non-numeric P-series row must not break the cast (PLUM-01, pitfall 3)
        # -------------------------------------------------------------------
        seeded_ids.append(await _seed(session_factory, pn_nonnumeric))
        try:
            async with session_factory() as session:
                pn = await generate_part_number(session)
            check(
                "non-numeric P-series row does not break generate_part_number",
                bool(_NUMERIC_PN.match(pn)),
                f"returned {pn!r}",
            )
        except Exception as exc:  # noqa: BLE001 - the whole point is to catch a raise
            check(
                "non-numeric P-series row does not break generate_part_number",
                False,
                f"raised {type(exc).__name__}: {exc}",
            )

        # -------------------------------------------------------------------
        # 2. Digit boundary — numeric MAX+1, no collision (PLUM-01 defect)
        # -------------------------------------------------------------------
        seeded_ids.append(await _seed(session_factory, pn_low))
        seeded_ids.append(await _seed(session_factory, pn_high))

        expected_suffix = await _max_numeric_suffix(session_factory)
        existing = await _all_part_numbers(session_factory)
        async with session_factory() as session:
            pn = await generate_part_number(session)

        check("boundary: result matches ^P[0-9]+$", bool(_NUMERIC_PN.match(pn)), f"got {pn!r}")
        check(
            "boundary: result is true numeric MAX+1 (not lexicographic)",
            _NUMERIC_PN.match(pn) is not None and int(pn[1:]) == expected_suffix + 1,
            f"got {pn!r}, expected suffix {expected_suffix + 1}",
        )
        check("boundary: result collides with no existing part_number", pn not in existing)

        # -------------------------------------------------------------------
        # 3. int4 OVERFLOW GUARD — the Phase-7 blocker regression.
        #    Under `cast(..., Integer)` this row makes generate_part_number raise
        #    DataError ("value out of range for type integer") and every
        #    auto-numbered create 500s until the row is deleted by hand.
        # -------------------------------------------------------------------
        seeded_ids.append(await _seed(session_factory, pn_overflow))

        overflow_suffix = int(pn_overflow[1:])
        check(
            "overflow: seeded suffix genuinely exceeds int4 max (test is meaningful)",
            overflow_suffix > 2_147_483_647,
            f"suffix {overflow_suffix} is not > 2147483647 — scenario 3 proves nothing",
        )

        try:
            async with session_factory() as session:
                pn = await generate_part_number(session)
            check("overflow: generate_part_number survives a > int4 suffix (no DataError)", True)
            check(
                "overflow: result is still numeric MAX+1",
                _NUMERIC_PN.match(pn) is not None and int(pn[1:]) == overflow_suffix + 1,
                f"got {pn!r}, expected suffix {overflow_suffix + 1}",
            )
        except Exception as exc:  # noqa: BLE001 - a raise here IS the regression
            check(
                "overflow: generate_part_number survives a > int4 suffix (no DataError)",
                False,
                f"raised {type(exc).__name__}: {exc} — auto-numbering is bricked",
            )
            check("overflow: result is still numeric MAX+1", False, "generator raised")

    finally:
        # -------------------------------------------------------------------
        # Clean up only the rows this script created.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            if seeded_ids:
                await session.execute(delete(PlumPart).where(PlumPart.id.in_(seeded_ids)))
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
