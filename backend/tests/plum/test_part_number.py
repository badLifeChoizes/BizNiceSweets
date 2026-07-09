# ABOUTME: Pure no-DB unit tests for PLUM generate_part_number (Phase 7, SC2).
# ABOUTME: Covers the Python half — the empty-set "P00001" branch and the
# ABOUTME: f"P{suffix+1:05d}" increment, including past the 5-digit boundary.
"""
PLUM part-number generation — pure unit tests (Phase 7, SC2).

``generate_part_number`` has two halves:

  SQL half   — the ``^P[0-9]+$`` regex filter, the ``cast(..., Numeric)`` target,
               and the numeric ``ORDER BY``. These need real Postgres semantics
               and are exercised live by backend/scripts/verify_part_numbering.py
               (which also pins the int4-overflow blocker: an Integer cast made a
               legal "P9999999999" row 500 every auto-numbered create).

  Python half — the ``max_pn is None`` -> "P00001" branch and the
               ``f"P{suffix + 1:05d}"`` increment. That is what these tests cover,
               with NO database, by feeding the function a stub session whose
               ``execute(...).scalar()`` returns the value the query would have.

This is the split Phase 8 used for ``_next_item_code`` (pure) + verify_inventory.py
(live). It matters here because the DB-backed PLUM tests silently skip under plain
pytest while the live harness is broken (D-P7-4, BACKLOG p1) — these tests RUN.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.modules.plum.service import generate_part_number


class _StubResult:
    """Stands in for the SQLAlchemy Result of the part-number SELECT."""

    def __init__(self, value: str | None) -> None:
        self._value = value

    def scalar(self) -> str | None:
        return self._value


class _StubSession:
    """
    Minimal async stand-in for AsyncSession.

    generate_part_number only ever calls ``await db.execute(stmt)`` and then
    ``.scalar()``, so the stub returns whatever part_number the real query would
    have selected. No database, no event loop juggling.
    """

    def __init__(self, max_part_number: str | None) -> None:
        self._max = max_part_number

    async def execute(self, _stmt: Any) -> _StubResult:
        return _StubResult(self._max)


@pytest.mark.asyncio
async def test_returns_p00001_when_no_p_series_rows_exist() -> None:
    """An empty P-series table yields the first part number, P00001."""
    assert await generate_part_number(_StubSession(None)) == "P00001"


@pytest.mark.asyncio
async def test_increments_and_zero_pads_to_five_digits() -> None:
    """P00041 -> P00042: increment, zero-padded to the 5-digit P##### series."""
    assert await generate_part_number(_StubSession("P00041")) == "P00042"


@pytest.mark.asyncio
async def test_crosses_the_five_to_six_digit_boundary() -> None:
    """
    P99999 -> P100000, the PLUM-01 defect boundary.

    The old lexicographic MAX(part_number) ranked "P99999" ABOVE "P100000", so once
    a six-digit number existed the generator kept re-issuing an already-taken value
    and create_part died on the unique constraint. Widening past 5 digits is
    correct and intended — part_number is String(50).
    """
    result = await generate_part_number(_StubSession("P99999"))
    assert result == "P100000"
    assert int(result[1:]) == 100_000


@pytest.mark.asyncio
async def test_suffix_beyond_int4_still_increments() -> None:
    """
    A suffix larger than int4 max increments in Python without overflowing.

    Postgres int4 tops out at 2,147,483,647. Python ints are arbitrary-precision,
    so the increment itself was never the problem — the CAST in the ORDER BY was
    (see verify_part_numbering.py scenario 3). This pins the Python side of that
    story so a future "just cast to Integer, it's simpler" edit fails something.
    """
    result = await generate_part_number(_StubSession("P9999999999"))
    assert result == "P10000000000"
    assert int(result[1:]) == 10_000_000_000
