// ABOUTME: SYERP Purchase Order detail (/syerp/purchasing/orders/:id) — header
// ABOUTME: (PO#, vendor, status, dates), the ordered/received/outstanding line
// ABOUTME: roll-up (AC11-5), and approve/close FSM actions + a per-line receive seam.

/**
 * PurchaseOrderDetail — single purchase-order view (/syerp/purchasing/orders/:id).
 *
 * Layout: p-8 space-y-6 (matches PurchaseOrders/InventoryItemDetail), Back link →
 * /syerp/purchasing/orders.
 *
 * Data:
 *   - PO + lines: GET /api/v1/syerp/purchasing/orders/{id}  → key
 *                 ['syerp','purchasing','orders', id]
 *   - Vendors:    GET /syerp/partners?role=vendor  (resolve vendor_id → name)
 *   - Items:      GET /syerp/inventory/items       (resolve item_id → name)
 *
 * Header card: PO number, vendor NAME, status Badge (color+text), created/approved
 * dates. Lines table (AC11-5): item | ordered | received | outstanding. Per-line
 * outstanding = qty_ordered − qty_received; the Decimals arrive as exact STRINGS
 * (D-11) — Number() is used ONLY to derive the outstanding figure for display.
 *
 * Actions (FSM — server is the source of truth, buttons only mirror it):
 *   - Approve — visible/enabled ONLY on `draft`. POST …/approve.
 *   - Close   — visible on approved | partially_received | received. POST …/close.
 *   Both invalidate the detail + list queries and toast on success; a 4xx surfaces
 *   toast.error(server detail). An illegal transition forced past the UI is still
 *   rejected 422 by the backend.
 *
 * Receive seam: a per-line "Receive" button (shown only when the PO is `approved`
 * or `partially_received`, and the line still has outstanding > 0) opens the
 * ReceiveLineDialog (Task 23 stub today). onSuccess invalidates the detail + list.
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import { ReceiveLineDialog } from './components/ReceiveLineDialog'
import type { PartnerRead } from './components/PartnerSheet'
import type { InventoryItemRead } from './components/InventoryItemSheet'
import type { PORead } from './PurchaseOrders'

// ─── Types ───────────────────────────────────────────────────────────────────
// Decimal fields are string-serialized (D-11) — render as-is; Number() only to
// derive per-line outstanding for DISPLAY.

/** A PO line as embedded in the detail GET (POLineRead). */
interface POLineRead {
  id: string
  po_id: string
  item_id: string
  line_no: number
  qty_ordered: string
  unit_cost: string
  qty_received: string
  need_by_date: string | null
}

/** Detail response: the PO header roll-up (PORead) plus its nested lines. */
interface PODetailRead extends PORead {
  lines: POLineRead[]
}

// Statuses for which the per-line receive seam and the Close action are offered.
const RECEIVABLE_STATUSES = new Set(['approved', 'partially_received'])
const CLOSABLE_STATUSES = new Set(['approved', 'partially_received', 'received'])

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchOrder(id: string): Promise<PODetailRead> {
  return apiClient
    .get<PODetailRead>(`/api/v1/syerp/purchasing/orders/${id}`)
    .then((r) => r.data)
}

function fetchVendors(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=vendor')
    .then((r) => r.data)
}

function fetchItems(): Promise<InventoryItemRead[]> {
  return apiClient
    .get<InventoryItemRead[]>('/api/v1/syerp/inventory/items')
    .then((r) => r.data)
}

// Surface the server's real reason (e.g. 422 illegal FSM transition) rather than a
// generic message. FastAPI returns either a string `detail` or a validation array.
function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined
          const field = typeof loc === 'string' ? loc : undefined
          const msg = typeof d?.msg === 'string' ? d.msg : 'invalid value'
          return field ? `${field}: ${msg}` : msg
        })
        .filter(Boolean)
      if (msgs.length) return msgs.join('; ')
    }
  }
  return fallback
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label (mirrors the PurchaseOrders list map). */
function StatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
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

// ─── Helper: format ISO date (date-only) ──────────────────────────────────────

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

// Per-line outstanding = ordered − received, derived ONLY for display. Falls back
// to the raw ordered value if either figure is not a finite number.
function outstandingOf(line: POLineRead): string {
  const ordered = Number(line.qty_ordered)
  const received = Number(line.qty_received)
  if (!Number.isFinite(ordered) || !Number.isFinite(received)) return line.qty_ordered
  return String(ordered - received)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PurchaseOrderDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Receive dialog state (Task 23 seam) ──
  const [receiveLine, setReceiveLine] = useState<POLineRead | null>(null)

  // ── Data ──
  const {
    data: po,
    isLoading,
    isError,
  } = useQuery<PODetailRead, Error>({
    queryKey: ['syerp', 'purchasing', 'orders', id],
    queryFn: () => fetchOrder(id),
    enabled: !!id,
  })

  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
  })

  const { data: items = [] } = useQuery<InventoryItemRead[], Error>({
    queryKey: ['syerp', 'inventory', 'items'],
    queryFn: fetchItems,
  })

  // Resolve foreign keys → display names client-side.
  const vendorName = (vid: string) => vendors.find((v) => v.id === vid)?.name ?? '—'
  const itemName = (iid: string) => {
    const it = items.find((i) => i.id === iid)
    return it ? `${it.code} — ${it.name}` : iid
  }

  // ── Refresh the detail + list after a state change ──
  function invalidatePo() {
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'purchasing', 'orders', id] })
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'purchasing', 'orders'] })
  }

  // ── FSM mutations: approve / close ──
  const approveMutation = useMutation<PODetailRead, Error, void>({
    mutationFn: () =>
      apiClient
        .post<PODetailRead>(`/api/v1/syerp/purchasing/orders/${id}/approve`)
        .then((r) => r.data),
    onSuccess: () => {
      invalidatePo()
      toast.success('Purchase order approved.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to approve purchase order.'))
    },
  })

  const closeMutation = useMutation<PODetailRead, Error, void>({
    mutationFn: () =>
      apiClient
        .post<PODetailRead>(`/api/v1/syerp/purchasing/orders/${id}/close`)
        .then((r) => r.data),
    onSuccess: () => {
      invalidatePo()
      toast.success('Purchase order closed.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to close purchase order.'))
    },
  })

  const isMutating = approveMutation.isPending || closeMutation.isPending

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !po) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load purchase order. Check your connection and try again.
        </p>
      </div>
    )
  }

  const canApprove = po.status === 'draft'
  const canClose = CLOSABLE_STATUSES.has(po.status)
  const canReceive = RECEIVABLE_STATUSES.has(po.status)

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/syerp/purchasing/orders')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Purchase Orders
      </Button>

      {/* PO header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{po.po_number}</p>
                <StatusBadge status={po.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">
                {vendorName(po.vendor_id)}
              </p>
            </div>
            {/* FSM actions — mirror server-allowed transitions */}
            <div className="flex items-center gap-2 shrink-0">
              {canApprove && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => approveMutation.mutate()}
                  disabled={isMutating}
                >
                  {approveMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Approving…
                    </>
                  ) : (
                    'Approve'
                  )}
                </Button>
              )}
              {canClose && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => closeMutation.mutate()}
                  disabled={isMutating}
                >
                  {closeMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Closing…
                    </>
                  ) : (
                    'Close'
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Total</p>
              <p className="font-mono font-semibold">{po.total}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Created</p>
              <p>{formatDate(po.created_at)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Approved</p>
              <p>{po.approved_at ? formatDate(po.approved_at) : '—'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lines roll-up (AC11-5): item | ordered | received | outstanding */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Order Lines</h2>
        </CardHeader>
        <CardContent>
          {po.lines.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              This purchase order has no lines.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Ordered</TableHead>
                  <TableHead className="text-right">Received</TableHead>
                  <TableHead className="text-right">Outstanding</TableHead>
                  {canReceive && <TableHead className="text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.lines.map((line) => {
                  const outstanding = outstandingOf(line)
                  const hasOutstanding = Number(outstanding) > 0
                  return (
                    <TableRow key={line.id} className="h-12">
                      <TableCell className="font-medium">{itemName(line.item_id)}</TableCell>
                      <TableCell className="text-right font-mono">{line.qty_ordered}</TableCell>
                      <TableCell className="text-right font-mono">{line.qty_received}</TableCell>
                      <TableCell className="text-right font-mono">{outstanding}</TableCell>
                      {canReceive && (
                        <TableCell className="text-right">
                          {hasOutstanding && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setReceiveLine(line)}
                              aria-label={`Receive line ${line.line_no}`}
                            >
                              Receive
                            </Button>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Receive Line dialog (Task 23 stub) ─────────────────────────────── */}
      {receiveLine && (
        <ReceiveLineDialog
          poId={id}
          lineId={receiveLine.id}
          outstandingQty={outstandingOf(receiveLine)}
          open={receiveLine !== null}
          onOpenChange={(open) => {
            if (!open) setReceiveLine(null)
          }}
          onSuccess={invalidatePo}
        />
      )}
    </div>
  )
}
