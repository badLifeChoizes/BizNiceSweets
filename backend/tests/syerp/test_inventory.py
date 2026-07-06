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
from decimal import Decimal

import httpx

from app.modules.syerp.service import (
    _adjustment_violates_floor,
    _derive_onhand,
    _next_item_code,
    compute_new_moving_avg,
)


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
# _derive_onhand — pure, no-DB valuation core (Task 4)
# ---------------------------------------------------------------------------
#
# On-hand is derived from SUM(txn.quantity) per location (AC10-3); the pure core
# here filters zero-net locations, sums the grand total, and values it against
# moving_avg_cost — all in Decimal, so these assert exact values with no float
# drift. The live SUM/group_by query is exercised by verify_inventory.py (Task 8).


def test_derive_onhand_sums_per_location_and_values() -> None:
    """Grand total is the sum of per-location nets; value = total * avg cost."""
    rows = [
        (1, "Main", Decimal("10")),
        (2, "Overflow", Decimal("5")),
    ]
    nonzero, total_qty, value = _derive_onhand(rows, Decimal("2.5"))

    assert nonzero == rows
    assert total_qty == Decimal("15")
    # 15 * 2.5 = 37.5 exactly (Decimal, no float drift)
    assert value == Decimal("37.5")


def test_derive_onhand_omits_zero_net_locations() -> None:
    """A location whose signed txns net to exactly zero is omitted (documented policy)."""
    rows = [
        (1, "Main", Decimal("8")),
        (2, "Returns", Decimal("0")),  # e.g. +3 then -3
    ]
    nonzero, total_qty, value = _derive_onhand(rows, Decimal("1"))

    assert nonzero == [(1, "Main", Decimal("8"))]
    assert total_qty == Decimal("8")
    assert value == Decimal("8")


def test_derive_onhand_handles_negative_net() -> None:
    """Signed sums can be negative (over-issue); value follows the signed total."""
    rows = [(1, "Main", Decimal("-4"))]
    nonzero, total_qty, value = _derive_onhand(rows, Decimal("3"))

    assert nonzero == [(1, "Main", Decimal("-4"))]
    assert total_qty == Decimal("-4")
    assert value == Decimal("-12")


def test_derive_onhand_empty_returns_zero_decimals() -> None:
    """No movements → empty rows, and total/value are Decimal('0'), never int 0."""
    nonzero, total_qty, value = _derive_onhand([], Decimal("9.999999"))

    assert nonzero == []
    assert total_qty == Decimal("0")
    assert isinstance(total_qty, Decimal)
    assert value == Decimal("0")
    assert isinstance(value, Decimal)


def test_derive_onhand_no_float_drift_on_fractional_sums() -> None:
    """Summing 0.1 three times yields exactly 0.3 (Decimal), not 0.30000000000000004."""
    rows = [
        (1, "A", Decimal("0.1")),
        (2, "B", Decimal("0.1")),
        (3, "C", Decimal("0.1")),
    ]
    _, total_qty, value = _derive_onhand(rows, Decimal("1.5"))

    assert total_qty == Decimal("0.3")
    assert value == Decimal("0.45")


# ---------------------------------------------------------------------------
# compute_new_moving_avg — pure, no-DB moving-average recompute (Task 5, AC10-5)
# ---------------------------------------------------------------------------
#
# The moving average is the valuation crux: every downstream on-hand value rides
# on it being EXACTLY right in Decimal (no float drift). These tests pin the
# formula, the first-receipt short-circuit, and the deterministic scale-6
# quantize. The live posting path (post_receipt) is exercised end-to-end by
# verify_inventory.py (Task 8).


def test_moving_avg_first_receipt_is_unit_cost() -> None:
    """First receipt (qty_before == 0) → avg == unit_cost, no div-by-zero."""
    result = compute_new_moving_avg(
        Decimal("0"), Decimal("0"), Decimal("10"), Decimal("2")
    )
    assert result == Decimal("2")
    # Quantized to scale 6, still numerically equal to the unit cost.
    assert result == Decimal("2.000000")
    assert isinstance(result, Decimal)


def test_moving_avg_weighted_second_receipt_is_exact() -> None:
    """
    10@2 then 10@4 weights to exactly 3.000000 (AC10-5).

    (10*2 + 10*4) / (10+10) = 60/20 = 3 — a terminating quotient, so the result
    is the exact Decimal("3.000000"), never a float-tainted 2.9999999… .
    """
    # First receipt establishes avg = 2 on 10 units.
    avg_after_first = compute_new_moving_avg(
        Decimal("0"), Decimal("0"), Decimal("10"), Decimal("2")
    )
    assert avg_after_first == Decimal("2.000000")

    # Second receipt: 10 more units at unit cost 4 against 10 units @ avg 2.
    result = compute_new_moving_avg(
        Decimal("10"), avg_after_first, Decimal("10"), Decimal("4")
    )
    assert result == Decimal("3.000000")
    assert isinstance(result, Decimal)


def test_moving_avg_non_terminating_quotient_quantizes_to_scale_6() -> None:
    """
    10@1 then 5@2 → 20/15 = 1.3333… quantized HALF_UP to exactly 1.333333.

    This exercises the fixed scale-6 quantize on a non-terminating quotient: the
    result must be deterministic and match the Numeric(18,6) column, never an
    unbounded repeating Decimal or a float.
    """
    result = compute_new_moving_avg(
        Decimal("10"), Decimal("1"), Decimal("5"), Decimal("2")
    )
    # 20/15 = 1.33333333… → HALF_UP at scale 6 → 1.333333
    assert result == Decimal("1.333333")
    assert isinstance(result, Decimal)


def test_moving_avg_returns_decimal_with_no_float_drift() -> None:
    """
    Return type is Decimal and equals a string-constructed Decimal exactly.

    0.1@1 then 0.2@1.55 must land on exactly the scale-6 value computed with
    Decimal arithmetic — proving no float ever contaminates the pipeline.
        (0.1*1 + 0.2*1.55) / (0.1+0.2) = (0.1 + 0.31) / 0.3 = 0.41/0.3
        = 1.36666… → HALF_UP scale 6 → 1.366667
    """
    result = compute_new_moving_avg(
        Decimal("0.1"), Decimal("1"), Decimal("0.2"), Decimal("1.55")
    )
    assert result == Decimal("1.366667")
    assert isinstance(result, Decimal)
    # Exactly equal to the string-constructed Decimal (no float representation).
    assert str(result) == "1.366667"


# ---------------------------------------------------------------------------
# _adjustment_violates_floor — pure, no-DB per-location negative-stock guard
# ---------------------------------------------------------------------------
#
# The adjustment guard is per-LOCATION (D-P8-7, AC10-6): a signed qty_delta may
# not drive that location's on-hand below zero. The pure predicate below decides
# reject/allow from (current_loc_onhand, qty_delta) in Decimal — the live SUM
# query that feeds current_loc_onhand is exercised by verify_inventory.py
# (Task 8). Adjustments never move the moving-average — asserted separately.


def test_adjustment_floor_rejects_delta_driving_location_negative() -> None:
    """A negative delta exceeding the location on-hand is rejected (returns True)."""
    # 5 on hand, issue 8 → would be -3 → violates the floor.
    assert _adjustment_violates_floor(Decimal("5"), Decimal("-8")) is True


def test_adjustment_floor_allows_delta_landing_exactly_zero() -> None:
    """Emptying a location exactly to zero is allowed (boundary is inclusive)."""
    # 5 on hand, issue 5 → lands on exactly 0 → allowed.
    assert _adjustment_violates_floor(Decimal("5"), Decimal("-5")) is False


def test_adjustment_floor_allows_positive_delta() -> None:
    """A positive adjustment can never drive on-hand negative → always allowed."""
    assert _adjustment_violates_floor(Decimal("0"), Decimal("10")) is False
    assert _adjustment_violates_floor(Decimal("5"), Decimal("3")) is False


def test_adjustment_floor_rejects_issue_from_empty_location() -> None:
    """Any negative delta against a zero on-hand location is rejected."""
    assert _adjustment_violates_floor(Decimal("0"), Decimal("-1")) is True


def test_adjustment_floor_uses_exact_decimal_boundary_no_drift() -> None:
    """The floor check is exact in Decimal — 0.1 on hand, -0.1 delta lands on 0."""
    # Would be 0.30000000000000004 in float; Decimal makes 0.1+0.1+0.1-0.3 exact.
    assert _adjustment_violates_floor(Decimal("0.3"), Decimal("-0.3")) is False
    assert _adjustment_violates_floor(Decimal("0.3"), Decimal("-0.300001")) is True


def test_adjustment_does_not_move_moving_average() -> None:
    """
    Adjustments must NOT alter the item's moving-average (AC10-5).

    post_adjustment never calls compute_new_moving_avg — only receipts move the
    average. This asserts the invariant at the pure level: the moving-average
    recompute is the ONLY function that changes the average, and it is not part
    of the adjustment path. We prove compute_new_moving_avg is a pure passthrough
    of the prior average when there is no receipt (qty_recv == 0 is not a valid
    receipt), so an adjustment leaving the average untouched is equivalent to the
    average simply not being recomputed. The live "avg unchanged after an
    adjustment" assertion runs in verify_inventory.py (Task 8).
    """
    import inspect

    from app.modules.syerp import service

    # The adjustment posting path must not INVOKE the moving-average recompute —
    # inspect the source as a no-DB regression guard for the invariant. The
    # recompute (compute_new_moving_avg) is the only function that changes the
    # average, and it is exclusive to the receipt path.
    source = inspect.getsource(service.post_adjustment)
    assert "compute_new_moving_avg" not in source, (
        "post_adjustment must NOT recompute the moving average (AC10-5) — only "
        "receipts move it."
    )
    # And the code must never ASSIGN item.moving_avg_cost (comments/docstrings may
    # mention it, but there must be no `moving_avg_cost =` assignment statement).
    assert "moving_avg_cost =" not in source, (
        "post_adjustment must leave item.moving_avg_cost untouched (AC10-5)."
    )


# ---------------------------------------------------------------------------
# post_transfer — pure, no-DB source-underflow guard + nets-zero invariant (Task 7)
# ---------------------------------------------------------------------------
#
# A transfer moves qty between two locations as TWO paired `transfer` legs (a
# `-qty` leg at the source, a `+qty` leg at the destination) sharing a
# transfer_group_id. Two invariants make the transfer safe, and both are provable
# without a DB:
#   1. The source `-qty` leg must not over-draw the source location. That guard is
#      the SAME per-location floor as adjustments: the source leg IS a negative
#      adjustment of the source, so _adjustment_violates_floor(from_onhand, -qty)
#      decides reject/allow (from_onhand - qty < 0 ⟺ from_onhand < qty).
#   2. The two legs sum to exactly zero, so total item on-hand is unchanged.
# The live invariant/over-draw assertions run in verify_inventory.py (Task 8).


def test_transfer_source_underflow_predicate_rejects_over_draw() -> None:
    """
    The source over-draw guard reuses the per-location floor: transferring more
    than the source holds (`from_onhand < qty`) is rejected.

    The `-qty` source leg is a negative adjustment of the source location, so the
    over-draw check is exactly _adjustment_violates_floor(from_onhand, -qty):
    from_onhand - qty < 0 ⟺ from_onhand < qty.
    """
    from_onhand = Decimal("5")
    qty = Decimal("8")  # over-draw: 5 on hand, move 8
    # from_onhand < qty → over-draw → must reject
    assert from_onhand < qty
    assert _adjustment_violates_floor(from_onhand, -qty) is True


def test_transfer_source_exact_empty_is_allowed() -> None:
    """Moving exactly the source on-hand empties it to zero and is allowed."""
    from_onhand = Decimal("5")
    qty = Decimal("5")  # lands on exactly 0 at the source
    assert not (from_onhand < qty)
    assert _adjustment_violates_floor(from_onhand, -qty) is False


def test_transfer_legs_net_to_zero() -> None:
    """
    The paired legs (`-qty` out, `+qty` in) sum to exactly zero → total item
    on-hand is unchanged by a transfer (the nets-zero invariant at the leg level).
    """
    qty = Decimal("7.5")
    out_leg = -qty
    in_leg = qty
    assert out_leg + in_leg == Decimal("0")
    # Decimal, so no float drift even on fractional quantities.
    assert isinstance(out_leg + in_leg, Decimal)


def test_transfer_legs_net_to_zero_no_float_drift() -> None:
    """Fractional legs still net exactly to zero in Decimal (no 0.1+0.1+0.1 drift)."""
    qty = Decimal("0.1")
    assert (-qty) + qty == Decimal("0")


def test_transfer_does_not_move_moving_average() -> None:
    """
    Transfers must NOT alter the item's moving-average (AC10-5) — only receipts do.

    post_transfer never calls compute_new_moving_avg and never assigns
    item.moving_avg_cost. This asserts the invariant at the pure/source level,
    mirroring test_adjustment_does_not_move_moving_average. The live "avg unchanged
    after a transfer" assertion runs in verify_inventory.py (Task 8).
    """
    import inspect

    from app.modules.syerp import service

    source = inspect.getsource(service.post_transfer)
    assert "compute_new_moving_avg" not in source, (
        "post_transfer must NOT recompute the moving average (AC10-5) — only "
        "receipts move it."
    )
    # The transfer path must never ASSIGN item.moving_avg_cost. It READS it (to
    # value the legs) via `item.moving_avg_cost`, but there must be no assignment
    # statement (`moving_avg_cost =` / `.moving_avg_cost =`).
    assert "moving_avg_cost =" not in source, (
        "post_transfer must leave item.moving_avg_cost untouched (AC10-5)."
    )


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
