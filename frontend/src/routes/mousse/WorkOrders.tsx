// ABOUTME: MOUSSE Work Orders list screen (/mousse/work-orders) — WO number, part,
// ABOUTME: planned qty, and status badge over /api/v1/mousse/work-orders. The hub of
// ABOUTME: the materials-only manufacturing-execution slice (MOUSSE-01, SC7).

/**
 * WorkOrders screen — MOUSSE work-order list (/mousse/work-orders).
 *
 * Layout: p-8 space-y-6 (matches the SYERP PurchaseOrders pattern).
 *
 * Table columns: WO Number | Part | Planned Qty | Status
 *
 * Part-name resolution: WorkOrderRead carries only plum_part_id, so PLUM parts are
 * fetched once (GET /api/v1/plum/parts) and mapped id→part_number client-side.
 * Decimal `planned_qty` is a STRING — rendered as-is, never coerced to float (D-11).
 *
 * Row click navigates to /mousse/work-orders/{id} (the detail screen).
 */

import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { MousseNav } from './components/MousseNav'
import { useWorkOrders } from './hooks'
import type { PartRead } from '../plum/components/PartSheet'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchParts(): Promise<PartRead[]> {
  return apiClient.get<PartRead[]>('/api/v1/plum/parts').then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label. Color AND text together (never color alone). */
export function WorkOrderStatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
    draft: { variant: 'secondary', label: 'Draft' },
    released: { variant: 'default', label: 'Released' },
    in_progress: {
      variant: 'outline',
      className: 'border-blue-300 bg-blue-50 text-blue-700',
      label: 'In progress',
    },
    on_hold: {
      variant: 'outline',
      className: 'border-amber-300 bg-amber-50 text-amber-700',
      label: 'On hold',
    },
    completed: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Completed',
    },
    cancelled: { variant: 'outline', className: 'text-muted-foreground', label: 'Cancelled' },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return (
    <Badge variant={cfg.variant} className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function WorkOrders() {
  const navigate = useNavigate()

  const { data: orders = [], isLoading, isError } = useWorkOrders()

  const { data: parts = [] } = useQuery<PartRead[], Error>({
    queryKey: ['plum', 'parts'],
    queryFn: fetchParts,
  })

  // Resolve plum_part_id → part_number client-side (WorkOrderRead carries only the id).
  const partName = (id: string) => parts.find((p) => p.id === id)?.part_number ?? '—'

  return (
    <div className="p-8 space-y-6">
      <MousseNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Work Orders</h1>
        <p className="text-base font-normal text-muted-foreground">
          Create, release, issue components to, and complete work orders that consume
          PLUM BOMs and SYERP inventory.
        </p>
      </div>

      {/* Orders table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load work orders. Check your connection and refresh the page.
          </p>
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No work orders yet</p>
          <p className="text-sm text-muted-foreground">
            Create your first work order to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>WO Number</TableHead>
              <TableHead>Part</TableHead>
              <TableHead className="text-right">Planned Qty</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((wo) => (
              <TableRow
                key={wo.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/mousse/work-orders/${wo.id}`)}
                aria-label={`View work order ${wo.wo_number}`}
              >
                <TableCell className="font-medium">{wo.wo_number}</TableCell>
                <TableCell>{partName(wo.plum_part_id)}</TableCell>
                <TableCell className="text-right font-mono">{wo.planned_qty}</TableCell>
                <TableCell>
                  <WorkOrderStatusBadge status={wo.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
