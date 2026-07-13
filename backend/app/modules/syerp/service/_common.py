"""Shared SYERP service constants."""
from __future__ import annotations

from decimal import Decimal

# ---------------------------------------------------------------------------
# Shared money quantum
# ---------------------------------------------------------------------------
#
# All money/cost arithmetic across the SYERP service is Decimal (fixed-point),
# never float. Non-terminating quotients are quantized to scale 6 with
# ROUND_HALF_UP so results are deterministic and match the Numeric(18,6)
# columns (moving_avg_cost / unit_cost / journal amounts) exactly. Shared here
# because inventory (moving average), journal (JE balancing), and purchasing
# (receipt costing) all quantize to the same quantum.

# Scale-6 quantum matching moving_avg_cost / unit_cost Numeric(18,6).
_COST_QUANTUM = Decimal("0.000001")
