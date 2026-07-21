# ABOUTME: Unit tests for SYERP GL journal-entry balance helpers (Phase 9a).
# ABOUTME: Proves _je_totals / _je_is_balanced / _reverse_lines enforce the
# ABOUTME: double-entry invariant (Σdebits == Σcredits) in pure Decimal, no DB.
"""
SYERP GL journal tests — Phase 9a (SYERP-12, D-P9a).

The double-entry invariant — a journal entry posts only when debits equal
credits — lives in three PURE helpers (no DB, no float, no FastAPI):

    _je_totals(lines)      -> (Σdebits, Σcredits), quantized to scale 6 (D-11)
    _je_is_balanced(lines) -> bool (equal totals AND >=2 lines AND each line
                              sets exactly one non-negative side)
    _reverse_lines(lines)  -> new line dicts with debit/credit swapped

These tests exercise the balance core without a database. The service layer
(later task) raises HTTP 422 on top of `_je_is_balanced`; the truth decision
is proven here. All amounts are Decimal literals — never float (D-11).
"""
from decimal import Decimal

from app.modules.syerp.service import (
    _je_is_balanced,
    _je_totals,
    _reverse_lines,
)

# A balanced 2-line entry: DR 100.00 Cash / CR 100.00 Revenue.
BALANCED_TWO_LINE = [
    {"debit": Decimal("100.000000"), "credit": None},
    {"debit": None, "credit": Decimal("100.000000")},
]


# ---------------------------------------------------------------------------
# _je_totals — pure Decimal column sums
# ---------------------------------------------------------------------------


def test_totals_sums_each_column() -> None:
    """Σdebits and Σcredits are summed independently, quantized to scale 6."""
    total_debit, total_credit = _je_totals(BALANCED_TWO_LINE)
    assert total_debit == Decimal("100.000000")
    assert total_credit == Decimal("100.000000")
    # Quantized to Numeric(18,6) scale.
    assert total_debit.as_tuple().exponent == -6


def test_totals_treats_none_side_as_zero() -> None:
    """A line's unset side contributes zero to its column, not an error."""
    lines = [
        {"debit": Decimal("40.500000"), "credit": None},
        {"debit": Decimal("9.500000"), "credit": None},
        {"debit": None, "credit": Decimal("50.000000")},
    ]
    total_debit, total_credit = _je_totals(lines)
    assert total_debit == Decimal("50.000000")
    assert total_credit == Decimal("50.000000")


# ---------------------------------------------------------------------------
# _je_is_balanced — the double-entry gate
# ---------------------------------------------------------------------------


def test_balanced_two_line_entry_accepted() -> None:
    """A canonical DR/CR pair with equal totals balances."""
    assert _je_is_balanced(BALANCED_TWO_LINE) is True


def test_unbalanced_entry_rejected() -> None:
    """Debits != credits does not balance."""
    lines = [
        {"debit": Decimal("100.000000"), "credit": None},
        {"debit": None, "credit": Decimal("99.000000")},
    ]
    assert _je_is_balanced(lines) is False


def test_single_line_entry_rejected() -> None:
    """Fewer than two lines cannot form a double-entry."""
    lines = [{"debit": Decimal("100.000000"), "credit": None}]
    assert _je_is_balanced(lines) is False


def test_empty_entry_rejected() -> None:
    """Zero lines cannot form a double-entry."""
    assert _je_is_balanced([]) is False


def test_line_with_both_sides_set_rejected() -> None:
    """A line must set exactly one side; setting both is invalid."""
    lines = [
        {"debit": Decimal("100.000000"), "credit": Decimal("100.000000")},
        {"debit": None, "credit": Decimal("100.000000")},
    ]
    assert _je_is_balanced(lines) is False


def test_line_with_neither_side_set_rejected() -> None:
    """A line must set exactly one side; setting neither is invalid."""
    lines = [
        {"debit": Decimal("100.000000"), "credit": None},
        {"debit": None, "credit": None},
        {"debit": None, "credit": Decimal("100.000000")},
    ]
    assert _je_is_balanced(lines) is False


def test_negative_amount_rejected() -> None:
    """A negative side is invalid — a negative debit must be a credit instead."""
    lines = [
        {"debit": Decimal("-100.000000"), "credit": None},
        {"debit": None, "credit": Decimal("-100.000000")},
    ]
    assert _je_is_balanced(lines) is False


def test_balanced_accepts_line_objects_not_only_dicts() -> None:
    """Helpers are duck-typed: objects exposing .debit/.credit also work."""

    class _Line:
        def __init__(self, debit: Decimal | None, credit: Decimal | None) -> None:
            self.debit = debit
            self.credit = credit

    lines = [
        _Line(Decimal("250.000000"), None),
        _Line(None, Decimal("250.000000")),
    ]
    assert _je_is_balanced(lines) is True


# ---------------------------------------------------------------------------
# _reverse_lines — audit-safe reversal
# ---------------------------------------------------------------------------


def test_reverse_swaps_sides() -> None:
    """Reversal swaps each line's debit and credit."""
    reversed_lines = _reverse_lines(BALANCED_TWO_LINE)
    assert reversed_lines == [
        {"debit": Decimal("0"), "credit": Decimal("100.000000")},
        {"debit": Decimal("100.000000"), "credit": Decimal("0")},
    ]


def test_reverse_of_balanced_stays_balanced() -> None:
    """Reversing a balanced entry yields another balanced entry."""
    reversed_lines = _reverse_lines(BALANCED_TWO_LINE)
    assert _je_is_balanced(reversed_lines) is True
    # Column totals merely trade places.
    orig_debit, orig_credit = _je_totals(BALANCED_TWO_LINE)
    rev_debit, rev_credit = _je_totals(reversed_lines)
    assert rev_debit == orig_credit
    assert rev_credit == orig_debit


def test_reverse_does_not_mutate_source() -> None:
    """Reversal returns new dicts; the source lines are untouched."""
    source = [
        {"debit": Decimal("10.000000"), "credit": None},
        {"debit": None, "credit": Decimal("10.000000")},
    ]
    _reverse_lines(source)
    assert source[0]["debit"] == Decimal("10.000000")
    assert source[0]["credit"] is None
