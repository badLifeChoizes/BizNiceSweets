// ABOUTME: MOUSSE work-order TanStack Query hooks + shared response types. Wraps the
// ABOUTME: /api/v1/mousse/work-orders API (list + detail) through the single axios client.
// ABOUTME: Decimal fields arrive as exact STRINGS (D-11) — render as-is, never float math.

/**
 * MOUSSE work-order hooks — the query seam shared by the WorkOrders list, the
 * detail screen, and the create/issue/complete dialogs (MOUSSE-01, SC7).
 *
 * Query keys (kept in one place so mutations can invalidate consistently):
 *   ['mousse', 'work-orders']       — the list
 *   ['mousse', 'work-orders', id]   — one WO's detail
 *
 * `useWorkOrders()` → GET /api/v1/mousse/work-orders (header rows).
 * `useWorkOrder(id)` → GET /api/v1/mousse/work-orders/{id} (header + component lines
 *   with service-derived on_hand / issued_so_far).
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

// ─── Types (mirror backend/app/modules/mousse/schemas.py) ─────────────────────
// All quantity/money fields are Decimals serialized as exact STRINGS (D-11).

/** Work-order header row (WorkOrderRead) — one row of the list. */
export interface WorkOrderRead {
  id: string
  wo_number: string
  plum_part_id: string
  released_revision_id: string | null
  output_item_id: string | null
  planned_qty: string
  target_location_id: number
  status: string
  wo_date: string
  actor_id: string
  created_at: string
  completed_at: string | null
}

/** One resolved BOM component line (WorkOrderComponentRead). */
export interface WorkOrderComponentRead {
  id: string
  work_order_id: string
  child_part_id: string
  item_id: string | null
  qty_per: string
  qty_required: string
  unit_of_measure: string
  sort_order: number
  // Service-derived figures (not stored columns).
  on_hand: string
  issued_so_far: string
}

/** Work-order detail (WorkOrderDetailRead) — header plus its component lines. */
export interface WorkOrderDetailRead extends WorkOrderRead {
  components: WorkOrderComponentRead[]
}

// ─── Query keys ───────────────────────────────────────────────────────────────

export const workOrdersKey = ['mousse', 'work-orders'] as const
export const workOrderKey = (id: string) => ['mousse', 'work-orders', id] as const

// ─── API helpers ──────────────────────────────────────────────────────────────

function fetchWorkOrders(): Promise<WorkOrderRead[]> {
  return apiClient
    .get<WorkOrderRead[]>('/api/v1/mousse/work-orders')
    .then((r) => r.data)
}

function fetchWorkOrder(id: string): Promise<WorkOrderDetailRead> {
  return apiClient
    .get<WorkOrderDetailRead>(`/api/v1/mousse/work-orders/${id}`)
    .then((r) => r.data)
}

// ─── Hooks ──────────────────────────────────────────────────────────────────--

/** Work-order list (header rows). */
export function useWorkOrders() {
  return useQuery<WorkOrderRead[], Error>({
    queryKey: workOrdersKey,
    queryFn: fetchWorkOrders,
  })
}

/** One work order's detail (header + component lines). */
export function useWorkOrder(id: string) {
  return useQuery<WorkOrderDetailRead, Error>({
    queryKey: workOrderKey(id),
    queryFn: () => fetchWorkOrder(id),
    enabled: !!id,
  })
}
