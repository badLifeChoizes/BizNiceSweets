# ABOUTME: Unit tests for SYERP accounts-payable pure helpers (Phase 9b).
# ABOUTME: Proves bill numbering, overpayment, three-way match, and the AP-bill
# ABOUTME: FSM decisions in pure Decimal — no DB, no float (D-11, D-P9b).
"""
SYERP accounts-payable tests — Phase 9b (SYERP-12, D-P9b).

The AP core decisions live in PURE helpers (no DB, no float, no FastAPI):

    _next_bill_number(existing)        -> str  BILL-####, numeric-not-lexicographic
    _is_overpayment(open, pay)         -> bool  pay > open (== boundary allowed)
    _unbilled_qty(received, billed)    -> Decimal  received - billed
    _is_exact_match(mq, uc, uq, pc)    -> bool  qty AND cost equal exactly
    _bill_transition_allowed(cur, tgt) -> bool  draft -> posted -> paid FSM

These tests exercise the AP truth decisions without a database. The service
layer (later task) raises HTTP 422 / auto-reconciles on top of these predicates;
the truth is proven here. All amounts are Decimal literals — never float (D-11).
"""
from decimal import Decimal

from app.modules.syerp.service import (
    _bill_transition_allowed,
    _is_exact_match,
    _is_overpayment,
    _next_bill_number,
    _unbilled_qty,
)


# ---------------------------------------------------------------------------
# _next_bill_number — numeric-not-lexicographic BILL-#### series (D-P9b-1)
# ---------------------------------------------------------------------------


def test_next_bill_number_crosses_digit_boundary() -> None:
    """BILL-9 is the numeric max, so the next number is BILL-0010, not BILL-0009."""
    assert _next_bill_number(["BILL-9"]) == "BILL-0010"


def test_next_bill_number_empty_starts_at_one() -> None:
    """An empty series seeds the first bill at BILL-0001."""
    assert _next_bill_number([]) == "BILL-0001"


def test_next_bill_number_picks_numeric_max_not_lexicographic() -> None:
    """{BILL-9, BILL-10} picks 10 (numeric), returning BILL-0011."""
    assert _next_bill_number(["BILL-9", "BILL-10"]) == "BILL-0011"


# ---------------------------------------------------------------------------
# _is_overpayment — pay > open rejected, pay == open allowed (D-P8-7, D-11)
# ---------------------------------------------------------------------------


def test_overpayment_over_open_balance_rejected() -> None:
    """Paying 10.01 against a 10.00 open balance is an overpayment (True)."""
    assert _is_overpayment(Decimal("10.00"), Decimal("10.01")) is True


def test_overpayment_exact_balance_allowed() -> None:
    """Paying 10.00 against a 10.00 open balance fully pays it (False)."""
    assert _is_overpayment(Decimal("10.00"), Decimal("10.00")) is False


# ---------------------------------------------------------------------------
# _unbilled_qty — received minus already-billed
# ---------------------------------------------------------------------------


def test_unbilled_qty_subtracts_already_billed() -> None:
    """Unbilled qty is qty_received minus already_billed, Decimal-exact."""
    assert _unbilled_qty(Decimal("10.000000"), Decimal("4.000000")) == Decimal("6.000000")


# ---------------------------------------------------------------------------
# _is_exact_match — qty AND cost equal exactly (D-P9b-2)
# ---------------------------------------------------------------------------


def test_exact_match_true_on_qty_and_cost_equal() -> None:
    """Matching qty and unit cost exactly auto-reconciles (True)."""
    assert (
        _is_exact_match(
            Decimal("5.000000"),
            Decimal("2.500000"),
            Decimal("5.000000"),
            Decimal("2.500000"),
        )
        is True
    )


def test_exact_match_false_on_qty_mismatch() -> None:
    """A quantity variance drops the line to manual review (False)."""
    assert (
        _is_exact_match(
            Decimal("4.000000"),
            Decimal("2.500000"),
            Decimal("5.000000"),
            Decimal("2.500000"),
        )
        is False
    )


def test_exact_match_false_on_cost_mismatch() -> None:
    """A price variance drops the line to manual review (False)."""
    assert (
        _is_exact_match(
            Decimal("5.000000"),
            Decimal("2.750000"),
            Decimal("5.000000"),
            Decimal("2.500000"),
        )
        is False
    )


# ---------------------------------------------------------------------------
# _bill_transition_allowed — draft -> posted -> paid FSM (D-P9b-5)
# ---------------------------------------------------------------------------


def test_transition_draft_to_posted_allowed() -> None:
    """A draft bill may be posted."""
    assert _bill_transition_allowed("draft", "posted") is True


def test_transition_posted_to_paid_allowed() -> None:
    """A posted bill may be paid."""
    assert _bill_transition_allowed("posted", "paid") is True


def test_transition_draft_to_paid_rejected() -> None:
    """A draft bill cannot skip straight to paid."""
    assert _bill_transition_allowed("draft", "paid") is False


def test_transition_posted_to_draft_rejected() -> None:
    """A posted bill cannot revert to draft."""
    assert _bill_transition_allowed("posted", "draft") is False


def test_transition_from_paid_is_terminal() -> None:
    """paid is terminal — no outgoing transition is allowed."""
    assert _bill_transition_allowed("paid", "posted") is False
    assert _bill_transition_allowed("paid", "draft") is False
    assert _bill_transition_allowed("paid", "paid") is False
