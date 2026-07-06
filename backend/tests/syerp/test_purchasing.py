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
from decimal import Decimal

import pytest

from app.modules.syerp.service import (
    PO_TRANSITIONS,
    _is_over_receipt,
    _next_po_number,
    _po_aggregates,
    _po_rollup_status,
)


# ---------------------------------------------------------------------------
# _next_po_number — pure, no-DB digit-boundary guarantee
# ---------------------------------------------------------------------------


@pytest.mark.po_number
def test_generator_first_number_when_empty() -> None:
    """With no existing PO-series numbers, the first number is PO-0001."""
    assert _next_po_number([]) == "PO-0001"


@pytest.mark.po_number
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


@pytest.mark.po_number
def test_generator_picks_numeric_max_not_lexicographic_max() -> None:
    """
    Given {"PO-9", "PO-10"}, the numeric max is 10 → next is PO-0011.

    Lexicographically "PO-9" > "PO-10" ('9' > '1'), so a MAX(po_number) generator
    would wrongly pick "PO-9" and re-issue the already-taken "PO-0010". This is
    exactly the Phase-7 partner defect the numeric generator avoids.
    """
    assert _next_po_number(["PO-9", "PO-10"]) == "PO-0011"


@pytest.mark.po_number
def test_generator_crosses_four_digit_boundary() -> None:
    """PO-9999 succeeds to PO-10000 (padding never truncates)."""
    assert _next_po_number(["PO-9999"]) == "PO-10000"


@pytest.mark.po_number
def test_generator_ignores_non_numeric_and_foreign_numbers() -> None:
    """
    Only strictly-numeric PO- numbers are considered.

    Legacy/manual numbers like "PO-A1" or item "ITEM-0001" codes are ignored, so
    the cast-to-integer DB ordering can never trip over them.
    """
    assert _next_po_number(["PO-A1", "ITEM-0001", "PO-5", "WIDGET-7"]) == "PO-0006"


@pytest.mark.po_number
def test_generator_ignores_non_numeric_only_returns_first() -> None:
    """When no strictly-numeric PO- number exists, generation starts at PO-0001."""
    assert _next_po_number(["PO-A1", "PO-XYZ", "ITEM-0002"]) == "PO-0001"


# ---------------------------------------------------------------------------
# PO_TRANSITIONS — pure, no-DB FSM validity (Phase 8, Task 16)
# ---------------------------------------------------------------------------
#
# advance_po_status accepts a transition iff target in PO_TRANSITIONS[current].
# These tests pin the table itself (the predicate the service applies): every
# legal transition is present, every illegal one is absent. The live HTTP walk
# (approve → close, illegal transitions → 4xx) is Task 19's verify script.


@pytest.mark.fsm
def test_po_transitions_table_exact_shape() -> None:
    """The transition table matches the D-P8 FSM spec exactly (sets per status)."""
    assert PO_TRANSITIONS == {
        "draft": {"approved"},
        "approved": {"partially_received", "received", "closed"},
        "partially_received": {"received", "closed"},
        "received": {"closed"},
        "closed": set(),
    }


@pytest.mark.fsm
def test_draft_only_advances_to_approved() -> None:
    """A draft PO can only be approved — no jumping straight to received/closed."""
    assert "approved" in PO_TRANSITIONS["draft"]
    assert "received" not in PO_TRANSITIONS["draft"]
    assert "closed" not in PO_TRANSITIONS["draft"]
    assert PO_TRANSITIONS["draft"] == {"approved"}


@pytest.mark.fsm
def test_approving_twice_is_illegal() -> None:
    """approved → approved is not a legal transition (re-approval is rejected)."""
    assert "approved" not in PO_TRANSITIONS["approved"]


@pytest.mark.fsm
def test_approved_can_receive_or_close() -> None:
    """From approved the PO may roll to receiving states or close directly."""
    assert PO_TRANSITIONS["approved"] == {"partially_received", "received", "closed"}


@pytest.mark.fsm
def test_partially_received_can_complete_or_close() -> None:
    """partially_received advances to received or closed, never back to approved."""
    assert PO_TRANSITIONS["partially_received"] == {"received", "closed"}
    assert "approved" not in PO_TRANSITIONS["partially_received"]


@pytest.mark.fsm
def test_received_only_closes() -> None:
    """A fully-received PO can only be closed."""
    assert PO_TRANSITIONS["received"] == {"closed"}


@pytest.mark.fsm
def test_closed_is_terminal() -> None:
    """closed has no outgoing transitions — it is a terminal state."""
    assert PO_TRANSITIONS["closed"] == set()


@pytest.mark.fsm
def test_closing_a_draft_is_illegal() -> None:
    """A draft cannot be closed directly (must be approved first)."""
    assert "closed" not in PO_TRANSITIONS["draft"]


# ---------------------------------------------------------------------------
# _is_over_receipt — pure, no-DB over-receipt guard (Phase 8, Task 17, AC11-4)
# ---------------------------------------------------------------------------
#
# receive_line rejects a receipt iff qty_received + qty > qty_ordered. The exact
# boundary (== qty_ordered) is ALLOWED (a line may be fully received in one shot).
# These tests pin that predicate in Decimal (no float drift); the live HTTP walk
# (a real receipt bumps on-hand + moving-avg, over-receipt → 422) is Task 19/20.


def test_over_receipt_rejects_when_sum_exceeds_ordered() -> None:
    """qty_received + qty > qty_ordered is an over-receipt → reject (True)."""
    assert _is_over_receipt(Decimal("6"), Decimal("5"), Decimal("10")) is True


def test_over_receipt_allows_exact_boundary() -> None:
    """qty_received + qty == qty_ordered fully receives the line → allowed (False)."""
    assert _is_over_receipt(Decimal("6"), Decimal("4"), Decimal("10")) is False


def test_over_receipt_allows_partial_under_ordered() -> None:
    """A partial receipt well under the ordered quantity is allowed (False)."""
    assert _is_over_receipt(Decimal("0"), Decimal("3"), Decimal("10")) is False


def test_over_receipt_first_receipt_over_ordered_rejects() -> None:
    """A first receipt larger than qty_ordered is an over-receipt → reject (True)."""
    assert _is_over_receipt(Decimal("0"), Decimal("11"), Decimal("10")) is True


def test_over_receipt_is_exact_in_decimal() -> None:
    """The boundary is exact in Decimal — 0.1 + 0.2 == 0.3 has no float drift."""
    assert _is_over_receipt(Decimal("0.1"), Decimal("0.2"), Decimal("0.3")) is False
    assert _is_over_receipt(Decimal("0.1"), Decimal("0.2001"), Decimal("0.3")) is True


# ---------------------------------------------------------------------------
# _po_rollup_status — pure, no-DB header roll-up (Phase 8, Task 17, AC11-5)
# ---------------------------------------------------------------------------
#
# After a successful receipt the header is `received` iff EVERY line is fully
# received (qty_received >= qty_ordered), otherwise `partially_received`. The list
# is (qty_ordered, qty_received) pairs. Called only post-receipt, so it never has
# to return `approved`.


def test_rollup_received_when_all_lines_full() -> None:
    """Every line fully received → the PO rolls up to `received`."""
    pairs = [(Decimal("10"), Decimal("10")), (Decimal("5"), Decimal("5"))]
    assert _po_rollup_status(pairs) == "received"


def test_rollup_partial_when_one_line_short() -> None:
    """One line still short → the PO stays `partially_received`."""
    pairs = [(Decimal("10"), Decimal("10")), (Decimal("5"), Decimal("2"))]
    assert _po_rollup_status(pairs) == "partially_received"


def test_rollup_partial_when_single_line_partly_received() -> None:
    """A single partly-received line rolls up to `partially_received`."""
    assert _po_rollup_status([(Decimal("10"), Decimal("3"))]) == "partially_received"


def test_rollup_received_on_single_fully_received_line() -> None:
    """A single fully-received line rolls up to `received`."""
    assert _po_rollup_status([(Decimal("10"), Decimal("10"))]) == "received"


def test_rollup_received_treats_over_as_full() -> None:
    """qty_received >= qty_ordered counts as full (>= not ==), so it is `received`."""
    assert _po_rollup_status([(Decimal("10"), Decimal("12"))]) == "received"


# ---------------------------------------------------------------------------
# _po_aggregates — pure, no-DB per-PO roll-ups (Phase 8, Task 18, AC11-3/5)
# ---------------------------------------------------------------------------
#
# Given (qty_ordered, unit_cost, qty_received) for every line, returns the PO's
# total value = SUM(qty_ordered * unit_cost) plus ordered/received/outstanding
# quantities. All arithmetic is Decimal so the sums are exact — no float drift.


def test_aggregates_multi_line_totals() -> None:
    """total = SUM(qty*cost); quantities sum; outstanding = ordered − received."""
    lines = [
        (Decimal("10"), Decimal("2.50"), Decimal("4")),
        (Decimal("5"), Decimal("3.00"), Decimal("5")),
    ]
    agg = _po_aggregates(lines)
    assert agg.total == Decimal("40.00")  # 10*2.50 + 5*3.00
    assert agg.total_ordered_qty == Decimal("15")
    assert agg.total_received_qty == Decimal("9")
    assert agg.outstanding_qty == Decimal("6")


def test_aggregates_empty_po_is_all_zero() -> None:
    """A PO with no lines rolls up to zero across every field."""
    agg = _po_aggregates([])
    assert agg.total == Decimal("0")
    assert agg.total_ordered_qty == Decimal("0")
    assert agg.total_received_qty == Decimal("0")
    assert agg.outstanding_qty == Decimal("0")


def test_aggregates_are_exact_in_decimal() -> None:
    """Fractional qty/cost sum exactly in Decimal (0.1 + 0.2 has no float drift)."""
    lines = [
        (Decimal("0.1"), Decimal("1"), Decimal("0.1")),
        (Decimal("0.2"), Decimal("1"), Decimal("0")),
    ]
    agg = _po_aggregates(lines)
    assert agg.total == Decimal("0.3")
    assert agg.total_ordered_qty == Decimal("0.3")
    assert agg.outstanding_qty == Decimal("0.2")
