// ABOUTME: CRUMB Sales Order detail screen (/crumb/sales-orders/:id) — placeholder wired in
// ABOUTME: Phase 11b task 13; the full builder over /api/v1/crumb/sales-orders/{id} lands in task 15.

/**
 * SalesOrderDetail screen — one sales order's header + ordered lines
 * (/crumb/sales-orders/:id).
 *
 * Minimal placeholder registered alongside the SO hooks/routes so the route
 * resolves; task 15 fleshes it out into the line editor + status FSM controls.
 */

import { CrumbNav } from './components/CrumbNav'

export function SalesOrderDetail() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-2xl font-semibold">Sales Order</h1>
    </div>
  )
}
