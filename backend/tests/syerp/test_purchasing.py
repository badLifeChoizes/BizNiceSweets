# ABOUTME: Unit tests for SYERP purchase-order number generation (Phase 8, Task 15).
# ABOUTME: Proves _next_po_number is numeric-safe across digit-width boundaries
# ABOUTME: (PO-9 -> PO-0010, never a lexicographic collision) with no DB.
"""
SYERP purchasing tests — Phase 8, Task 15.

The PO-number generator (generate_po_number) is numeric-safe: it picks the
NUMERICALLY highest existing suffix and increments it. The DB half of that (the
``order_by(cast(func.substring(po_number, 4), Integer))`` query) is exercised
live by backend/scripts/verify_purchasing.py (Task 19).

The boundary-correctness guarantee — that "PO-9" succeeds to "PO-0010" and never
to a smaller/lexicographic value — lives in the pure _next_po_number helper,
which these tests cover without a database.
"""
from app.modules.syerp.service import _next_po_number


# ---------------------------------------------------------------------------
# _next_po_number — pure, no-DB digit-boundary guarantee
# ---------------------------------------------------------------------------


def test_generator_first_number_when_empty() -> None:
    """With no existing PO-series numbers, the first number is PO-0001."""
    assert _next_po_number([]) == "PO-0001"


def test_generator_digit_boundary_nine_to_ten() -> None:
    """
    PO-9 must succeed to suffix 10 (PO-0010), never a lexicographic value.

    A lexicographic/string-max generator would keep "PO-9" as the max and
    re-issue "PO-0010" indefinitely (or produce "PO-90"-style garbage). The
    numeric generator parses the suffix as an integer and increments it.
    """
    result = _next_po_number(["PO-9"])
    assert result == "PO-0010"
    # The suffix is the integer 10 — not 90, not 9.
    assert int(result.split("-", 1)[1]) == 10


def test_generator_picks_numeric_max_not_lexicographic_max() -> None:
    """
    Given {"PO-9", "PO-10"}, the numeric max is 10 → next is PO-0011.

    Lexicographically "PO-9" > "PO-10" ('9' > '1'), so a MAX(po_number) generator
    would wrongly pick "PO-9" and re-issue the already-taken "PO-0010". This is
    exactly the Phase-7 partner defect the numeric generator avoids.
    """
    assert _next_po_number(["PO-9", "PO-10"]) == "PO-0011"


def test_generator_crosses_four_digit_boundary() -> None:
    """PO-9999 succeeds to PO-10000 (padding never truncates)."""
    assert _next_po_number(["PO-9999"]) == "PO-10000"


def test_generator_ignores_non_numeric_and_foreign_numbers() -> None:
    """
    Only strictly-numeric PO- numbers are considered.

    Legacy/manual numbers like "PO-A1" or item "ITEM-0001" codes are ignored, so
    the cast-to-integer DB ordering can never trip over them.
    """
    assert _next_po_number(["PO-A1", "ITEM-0001", "PO-5", "WIDGET-7"]) == "PO-0006"


def test_generator_ignores_non_numeric_only_returns_first() -> None:
    """When no strictly-numeric PO- number exists, generation starts at PO-0001."""
    assert _next_po_number(["PO-A1", "PO-XYZ", "ITEM-0002"]) == "PO-0001"
