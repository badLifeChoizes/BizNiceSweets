// ABOUTME: CRUMB Sales Orders list screen (/crumb/sales-orders) — a table of sales orders
// ABOUTME: (SO #, customer, status, order date) over /api/v1/crumb/sales-orders with a
// ABOUTME: "New sales order" create dialog. Rows navigate to the SO detail screen (CRUMB-01).

/**
 * SalesOrders screen — the CRUMB sales-order header list (/crumb/sales-orders).
 *
 * Layout: p-8 space-y-6 (matches the other module list screens).
 *
 * Table columns: SO # | Customer | Status | Order date
 *
 * SalesOrderRead carries only partner_id, so customers are fetched once and mapped
 * id→name client-side. Row click navigates to /crumb/sales-orders/{id} (the detail).
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CrumbNav } from './components/CrumbNav'
import { SalesOrderCreateDialog } from './components/SalesOrderCreateDialog'
import { useCustomers } from './components/lookups'
import { useSalesOrders } from './hooks'

// ─── Sub-components ──────────────────────────────────────────────────────────

/** SO status → Badge variant + label. Color AND text together (never color alone). */
export function SalesOrderStatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
    draft: { variant: 'secondary', label: 'Draft' },
    confirmed: {
      variant: 'outline',
      className: 'border-blue-300 bg-blue-50 text-blue-700',
      label: 'Confirmed',
    },
    fulfilling: {
      variant: 'outline',
      className: 'border-amber-300 bg-amber-50 text-amber-700',
      label: 'Fulfilling',
    },
    closed: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Closed',
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

export function SalesOrders() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const { data: salesOrders = [], isLoading, isError } = useSalesOrders()
  const { data: customers = [] } = useCustomers()

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? '—'

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Sales Orders</h1>
        <p className="text-base font-normal text-muted-foreground">
          Turn accepted quotes into ordered lines, then move them through the Draft →
          Confirmed → Fulfilling → Closed lifecycle.
        </p>
      </div>

      {/* Toolbar: create */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Sales Order
        </Button>
      </div>

      {/* Sales orders table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load sales orders. Check your connection and refresh the page.
          </p>
        </div>
      ) : salesOrders.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No sales orders yet</p>
          <p className="text-sm text-muted-foreground">
            Create your first sales order to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SO #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Order date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {salesOrders.map((so) => (
              <TableRow
                key={so.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/crumb/sales-orders/${so.id}`)}
                aria-label={`View sales order ${so.so_number}`}
              >
                <TableCell className="font-medium">{so.so_number}</TableCell>
                <TableCell>{customerName(so.partner_id)}</TableCell>
                <TableCell>
                  <SalesOrderStatusBadge status={so.status} />
                </TableCell>
                <TableCell>{so.order_date}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create dialog */}
      <SalesOrderCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
