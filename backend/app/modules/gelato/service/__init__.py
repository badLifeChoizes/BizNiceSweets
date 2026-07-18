# ABOUTME: GELATO service layer package — re-exports the public surface (bin CRUD
# ABOUTME: + putaway orchestration) so `from app.modules.gelato.service import X`
# ABOUTME: and `service.X` work unchanged; also re-exports get_bin_on_hand from the
# ABOUTME: SYERP hub so callers read per-bin on-hand through the GELATO surface.
"""GELATO service layer (business logic).

Split into cohesive per-entity submodules like syerp/service and crumb/service
(D-P10-6 — keep new suites' service layers thin; GELATO-01 — the Warehouse
Management suite over the SYERP hub). This package re-exports the full public
surface so `from app.modules.gelato.service import X` and `service.X` work
unchanged.

get_bin_on_hand is re-exported straight from the SYERP hub: per-bin on-hand is a
canonical ledger derivation SYERP owns, surfaced here so GELATO callers read it
through the GELATO service without importing the hub directly.
"""
from __future__ import annotations

from app.modules.gelato.service.bins import (
    archive_bin,
    create_bin,
    get_bin,
    list_bins,
    update_bin,
)
from app.modules.gelato.service.putaway import (
    execute_putaway,
    list_unbinned_stock,
    suggest_target_bin,
)
from app.modules.gelato.service.shipments import (
    SHIPMENT_TRANSITIONS,
    build_pick_list,
    execute_pack,
    execute_pick,
)
from app.modules.syerp.service import get_bin_on_hand

__all__ = [
    # bins
    "archive_bin",
    "create_bin",
    "get_bin",
    "list_bins",
    "update_bin",
    # putaway
    "execute_putaway",
    "list_unbinned_stock",
    "suggest_target_bin",
    # shipments (pick/pack/ship)
    "SHIPMENT_TRANSITIONS",
    "build_pick_list",
    "execute_pack",
    "execute_pick",
    # re-exported from the SYERP hub
    "get_bin_on_hand",
]
