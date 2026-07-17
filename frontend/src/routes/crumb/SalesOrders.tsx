// ABOUTME: CRUMB Sales Orders list screen (/crumb/sales-orders) — placeholder wired in
// ABOUTME: Phase 11b task 13; the full table over /api/v1/crumb/sales-orders lands in task 14.

/**
 * SalesOrders screen — the CRUMB sales-order header list (/crumb/sales-orders).
 *
 * Minimal placeholder registered alongside the SO hooks/routes so the route
 * resolves; task 14 fleshes it out into the header table (SO # | Customer | Status).
 */

import { CrumbNav } from './components/CrumbNav'

export function SalesOrders() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-2xl font-semibold">Sales Orders</h1>
    </div>
  )
}
