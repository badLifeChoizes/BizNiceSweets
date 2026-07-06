# ABOUTME: Unit tests for SYERP inventory item-code generation (Phase 8).
# ABOUTME: Proves _next_item_code is numeric-safe across digit-width boundaries
# ABOUTME: (ITEM-9 -> ITEM-0010, never a lexicographic collision) with no DB.
"""
SYERP inventory tests — Phase 8.

The item-code generator (generate_item_code) is numeric-safe: it picks the
NUMERICALLY highest existing suffix and increments it. The DB half of that
(the ``order_by(cast(func.substring(code, 6), Integer))`` query) is exercised
live by backend/scripts/verify_inventory.py (Task 8).

The boundary-correctness guarantee — that "ITEM-9" succeeds to "ITEM-0010" and
never to a smaller/lexicographic value — lives in the pure _next_item_code
helper, which these tests cover without a database.
"""
import httpx

from app.modules.syerp.service import _next_item_code


# ---------------------------------------------------------------------------
# _next_item_code — pure, no-DB digit-boundary guarantee
# ---------------------------------------------------------------------------


def test_generator_first_code_when_empty() -> None:
    """With no existing ITEM-series codes, the first code is ITEM-0001."""
    assert _next_item_code([]) == "ITEM-0001"


def test_generator_digit_boundary_nine_to_ten() -> None:
    """
    ITEM-9 must succeed to suffix 10 (ITEM-0010), never a lexicographic value.

    A lexicographic/string-max generator would keep "ITEM-9" as the max and
    re-issue "ITEM-0010" indefinitely (or produce "ITEM-90"-style garbage). The
    numeric generator parses the suffix as an integer and increments it.
    """
    result = _next_item_code(["ITEM-9"])
    assert result == "ITEM-0010"
    # The suffix is the integer 10 — not 90, not 9.
    assert int(result.split("-", 1)[1]) == 10


def test_generator_picks_numeric_max_not_lexicographic_max() -> None:
    """
    Given {"ITEM-9", "ITEM-10"}, the numeric max is 10 → next is ITEM-0011.

    Lexicographically "ITEM-9" > "ITEM-10" ('9' > '1'), so a MAX(code) generator
    would wrongly pick "ITEM-9" and re-issue the already-taken "ITEM-0010". This
    is exactly the Phase-7 partner defect the numeric generator avoids.
    """
    assert _next_item_code(["ITEM-9", "ITEM-10"]) == "ITEM-0011"


def test_generator_crosses_four_digit_boundary() -> None:
    """ITEM-9999 succeeds to ITEM-10000 (padding never truncates)."""
    assert _next_item_code(["ITEM-9999"]) == "ITEM-10000"


def test_generator_ignores_non_numeric_and_foreign_codes() -> None:
    """
    Only strictly-numeric ITEM- codes are considered.

    Legacy/manual codes like "ITEM-A1" or partner "P-0001" codes are ignored,
    so the cast-to-integer DB ordering can never trip over them.
    """
    assert _next_item_code(["ITEM-A1", "P-0001", "ITEM-5", "WIDGET-7"]) == "ITEM-0006"


def test_generator_ignores_non_numeric_only_returns_first() -> None:
    """When no strictly-numeric ITEM- code exists, generation starts at ITEM-0001."""
    assert _next_item_code(["ITEM-A1", "ITEM-XYZ", "P-0002"]) == "ITEM-0001"


# ---------------------------------------------------------------------------
# Default stock-location seed (D-P8-14) — wiring + idempotency
# ---------------------------------------------------------------------------


def test_default_location_seed_registered_where_coa_seed_runs() -> None:
    """
    seed_default_location must be wired into run_seeds alongside seed_gl_accounts.

    Guards the wiring (Decision 3 = yes): a fresh deploy runs the location seed
    at startup so receiving works out-of-the-box. Inspecting the run_seeds source
    keeps this a no-DB regression guard for the registration itself; the live
    seed-twice-counts-one assertion is exercised by verify_inventory.py (Task 8)
    and by test_default_location_seed_idempotent below when a DB is available.
    """
    import inspect

    from app.core import seed as seed_module

    source = inspect.getsource(seed_module.run_seeds)
    assert "seed_default_location" in source, (
        "seed_default_location is not wired into run_seeds — receiving would not "
        "work out-of-the-box on a fresh deploy (D-P8-14)."
    )
    assert "seed_gl_accounts" in source, "coa_seed regressed out of run_seeds"


def test_default_location_name_is_main() -> None:
    """The single seeded location is named 'Main' (D-P8-14)."""
    from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME

    assert DEFAULT_LOCATION_NAME == "Main"


async def test_default_location_seed_idempotent(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Running seed_default_location twice yields exactly one 'Main' location.

    Mirrors test_gl_seed_idempotent: select-before-insert (upsert-by-name)
    means re-running the seed on every podman-compose up leaves the row count
    for name='Main' at exactly 1. Skips cleanly when no live DB is reachable.
    """
    from sqlalchemy import func, select

    from app.core.db import AsyncSessionLocal
    from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
    from app.modules.syerp.models import StockLocation

    # Ensure the location exists (first seed run may be a no-op if already seeded)
    async with AsyncSessionLocal() as session:
        await seed_default_location(session)

    # Run the seed a second time — must be a no-op
    async with AsyncSessionLocal() as session:
        await seed_default_location(session)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(StockLocation)
            .where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
        count = result.scalar()

    assert count == 1, (
        f"Expected exactly one '{DEFAULT_LOCATION_NAME}' location after re-seeding, "
        f"got {count}. seed_default_location is not idempotent!"
    )
