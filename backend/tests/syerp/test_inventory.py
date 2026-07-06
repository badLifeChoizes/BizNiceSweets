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
