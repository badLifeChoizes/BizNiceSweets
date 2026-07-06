// ABOUTME: SYERP Purchase Orders list screen (/syerp/purchasing/orders) — PO
// ABOUTME: number, vendor, status badge, total, and created date, with a vendor
// ABOUTME: filter Select over /api/v1/syerp/purchasing/orders. Sibling of Vendors.tsx.

/**
 * PurchaseOrders screen — SYERP purchase-order list (/syerp/purchasing/orders).
 *
 * Layout: p-8 space-y-6 (matches Vendors/InventoryItems pattern).
 *
 * Toolbar:
 *   - Vendor filter Select (?vendor_id= — narrows to one vendor's history, AC11-3)
 *   - Create PO Button (variant="default" — only accent element; → Task 21 route)
 *
 * Table columns: PO Number | Vendor | Status | Total | Created
 *
 * Vendor name resolution: PORead carries only vendor_id, so vendors are fetched
 * once (GET /api/v1/syerp/partners?role=vendor) and mapped id→name client-side;
 * the same list backs the filter Select. Decimal `total` is a STRING — rendered
 * as-is, never coerced to float (D-11).
 *
 * Orders: GET /api/v1/syerp/purchasing/orders[?vendor_id={id}]
 * Query key: ['syerp', 'purchasing', 'orders', { vendorId }]
 *
 * Accessibility: row aria-label, color+text status badge via Badge variants.
 */

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'
import type { PartnerRead } from './components/PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

/** Purchase-order header row as returned by GET /syerp/purchasing/orders. */
export interface PORead {
  id: string
  po_number: string
  vendor_id: string
  status: string
  notes: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
  // Decimal roll-ups arrive as exact strings — render as-is, never float math.
  total: string
  total_ordered_qty: string
  total_received_qty: string
  outstanding_qty: string
}

// Sentinel for the "All vendors" option — Radix Select forbids empty-string
// values, so an unfilterable placeholder value stands in for "no filter".
const ALL_VENDORS = '__all__'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchOrders(vendorId: string): Promise<PORead[]> {
  const params = new URLSearchParams()
  if (vendorId) params.set('vendor_id', vendorId)
  const qs = params.toString()
  return apiClient
    .get<PORead[]>(`/api/v1/syerp/purchasing/orders${qs ? `?${qs}` : ''}`)
    .then((r) => r.data)
}

function fetchVendors(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=vendor')
    .then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label. Color AND text together (never color alone). */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    approved: { variant: 'default', label: 'Approved' },
    partially_received: {
      variant: 'outline',
      className: 'border-amber-300 bg-amber-50 text-amber-700',
      label: 'Partially received',
    },
    received: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Received',
    },
    closed: { variant: 'outline', className: 'text-muted-foreground', label: 'Closed' },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return (
    <Badge variant={cfg.variant} className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Helper: format ISO date (date-only for the list) ────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PurchaseOrders() {
  const navigate = useNavigate()

  // ── Vendor filter ──
  const [vendorFilter, setVendorFilter] = useState<string>(ALL_VENDORS)
  const vendorId = vendorFilter === ALL_VENDORS ? '' : vendorFilter

  // ── Data ──
  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
  })

  const {
    data: orders = [],
    isLoading,
    isError,
  } = useQuery<PORead[], Error>({
    queryKey: ['syerp', 'purchasing', 'orders', { vendorId }],
    queryFn: () => fetchOrders(vendorId),
  })

  // Resolve vendor_id → name client-side (PORead carries only the id).
  const vendorName = (id: string) => vendors.find((v) => v.id === id)?.name ?? '—'

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Purchase Orders</h1>
        <p className="text-base font-normal text-muted-foreground">
          Track purchase orders and their receiving status against vendors.
        </p>
      </div>

      {/* Toolbar: Vendor filter + Create PO */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Label htmlFor="po-vendor-filter">Vendor</Label>
          <Select value={vendorFilter} onValueChange={setVendorFilter}>
            <SelectTrigger id="po-vendor-filter" className="w-64" aria-label="Filter by vendor">
              <SelectValue placeholder="All vendors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VENDORS}>All vendors</SelectItem>
              {vendors.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {/* "Create PO" is the ONLY accent/default button on this screen */}
        <Button variant="default" asChild className="ml-auto">
          <Link to="/syerp/purchasing/orders/new">Create PO</Link>
        </Button>
      </div>

      {/* Orders table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load purchase orders. Check your connection and refresh the page.
          </p>
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          {vendorId ? (
            <>
              <p className="text-base font-semibold text-foreground">No purchase orders found</p>
              <p className="text-sm text-muted-foreground">
                This vendor has no purchase orders yet. Clear the filter or create one.
              </p>
            </>
          ) : (
            <>
              <p className="text-base font-semibold text-foreground">No purchase orders yet</p>
              <p className="text-sm text-muted-foreground">
                Create your first purchase order to get started.
              </p>
            </>
          )}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>PO Number</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((po) => (
              <TableRow
                key={po.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/syerp/purchasing/orders/${po.id}`)}
                aria-label={`View purchase order ${po.po_number}`}
              >
                <TableCell className="font-medium">{po.po_number}</TableCell>
                <TableCell>{vendorName(po.vendor_id)}</TableCell>
                <TableCell>
                  <StatusBadge status={po.status} />
                </TableCell>
                <TableCell>{po.total}</TableCell>
                <TableCell>{formatDate(po.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
