// ABOUTME: SYERP Inventory Item detail (/syerp/inventory/items/:id) — derived
// ABOUTME: on-hand-by-location + valuation card and the immutable transaction
// ABOUTME: ledger, with Adjust/Transfer action seams (Tasks 12/13).

/**
 * InventoryItemDetail — single inventory item view (/syerp/inventory/items/:id).
 *
 * Layout: p-8 space-y-6 (standard page wrapper), Back link → /syerp/inventory/items.
 *
 * Data (three read queries, all keyed under ['syerp','inventory','items', id, …]):
 *   - Item:         GET /api/v1/syerp/inventory/items/{id}      → key [...,'items',id]
 *   - On-hand:      GET …/items/{id}/onhand                     → key [...,id,'onhand']
 *   - Transactions: GET …/items/{id}/transactions              → key [...,id,'transactions']
 *
 * On-hand & valuation card (AC10-3,5): per-location quantity table plus grand-total
 * quantity, moving-average cost, and on-hand value. Zero-net locations are omitted
 * by the backend, so a location column of "—" means all stock nets out elsewhere.
 *
 * Transaction ledger (AC10-4): read-only, newest-first, immutable — type / qty /
 * unit cost / location / timestamp / reason. Never edited from the client.
 *
 * Decimal fields (moving_avg_cost, quantity, onhand_value, unit_cost) arrive as
 * JSON STRINGS — displayed as-is (no float math in JS) to preserve fixed-point
 * precision.
 *
 * Action seams: "Adjust Stock" and "Transfer Stock" open StockAdjustDialog /
 * StockTransferDialog. Their onSuccess invalidates the onhand + transactions
 * queries so the derived view refreshes. (Dialogs are Task 12/13 stubs today.)
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { StockAdjustDialog } from './components/StockAdjustDialog'
import { StockTransferDialog } from './components/StockTransferDialog'
import type { InventoryItemRead } from './components/InventoryItemSheet'

// ─── Types ────────────────────────────────────────────────────────────────────
// Decimal fields are string-serialized (see file docstring) — display only.

interface OnHandByLocation {
  location_id: number
  location_name: string
  quantity: string
}

interface ItemOnHandRead {
  item_id: string
  moving_avg_cost: string
  locations: OnHandByLocation[]
  total_quantity: string
  onhand_value: string
}

interface TransactionRead {
  id: string
  item_id: string
  location_id: number
  location_name: string
  txn_type: string
  quantity: string
  unit_cost?: string | null
  reason?: string | null
  created_at: string
}

// ─── Transaction-type badge map ─────────────────────────────────────────────────
// Color + label together (never color alone) — accessibility requirement.

const TXN_TYPE_CLASSES: Record<string, string> = {
  receipt: 'bg-green-50 text-green-600',
  adjustment: 'bg-yellow-50 text-yellow-700',
  transfer: 'bg-blue-50 text-blue-700',
  issue: 'bg-gray-100 text-gray-500',
}

const TXN_TYPE_LABELS: Record<string, string> = {
  receipt: 'Receipt',
  adjustment: 'Adjustment',
  transfer: 'Transfer',
  issue: 'Issue',
}

function TxnTypeBadge({ type }: { type: string }) {
  const classes = TXN_TYPE_CLASSES[type] ?? 'bg-gray-100 text-gray-500'
  const label = TXN_TYPE_LABELS[type] ?? type
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {label}
    </span>
  )
}

// ─── Helper: format ISO datetime ────────────────────────────────────────────────

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

// ─── Main component ──────────────────────────────────────────────────────────

export function InventoryItemDetail() {
  const { id: itemId = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Action dialog state (Tasks 12/13) ──
  const [adjustOpen, setAdjustOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)

  // ── Item ──
  const {
    data: item,
    isLoading: itemLoading,
    isError: itemError,
  } = useQuery<InventoryItemRead, Error>({
    queryKey: ['syerp', 'inventory', 'items', itemId],
    queryFn: () =>
      apiClient
        .get<InventoryItemRead>(`/api/v1/syerp/inventory/items/${itemId}`)
        .then((r) => r.data),
    enabled: !!itemId,
  })

  // ── Derived on-hand + valuation ──
  const { data: onhand } = useQuery<ItemOnHandRead, Error>({
    queryKey: ['syerp', 'inventory', 'items', itemId, 'onhand'],
    queryFn: () =>
      apiClient
        .get<ItemOnHandRead>(`/api/v1/syerp/inventory/items/${itemId}/onhand`)
        .then((r) => r.data),
    enabled: !!itemId,
  })

  // ── Immutable transaction ledger (newest-first) ──
  const { data: transactions = [] } = useQuery<TransactionRead[], Error>({
    queryKey: ['syerp', 'inventory', 'items', itemId, 'transactions'],
    queryFn: () =>
      apiClient
        .get<TransactionRead[]>(`/api/v1/syerp/inventory/items/${itemId}/transactions`)
        .then((r) => r.data),
    enabled: !!itemId,
  })

  // ── Success seam for Adjust/Transfer — refresh the derived views ──
  function invalidateStockViews() {
    void queryClient.invalidateQueries({
      queryKey: ['syerp', 'inventory', 'items', itemId, 'onhand'],
    })
    void queryClient.invalidateQueries({
      queryKey: ['syerp', 'inventory', 'items', itemId, 'transactions'],
    })
  }

  // ── Render: loading ──
  if (itemLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (itemError || !item) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load item details. Check your connection and try again.
        </p>
      </div>
    )
  }

  const locations = onhand?.locations ?? []
  const uom = item.unit_of_measure

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/syerp/inventory/items')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Items
      </Button>

      {/* Item header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xl font-semibold text-foreground">{item.name}</p>
              <p className="text-base text-muted-foreground mt-0.5">
                {item.code} · {uom}
              </p>
            </div>
            {/* Action seams — Tasks 12/13 dialogs */}
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="outline" size="sm" onClick={() => setAdjustOpen(true)}>
                Adjust Stock
              </Button>
              <Button variant="outline" size="sm" onClick={() => setTransferOpen(true)}>
                Transfer Stock
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Total On Hand</p>
              <p className="font-mono font-semibold">
                {onhand?.total_quantity ?? '—'} {uom}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Moving-Avg Cost</p>
              <p className="font-mono">{onhand?.moving_avg_cost ?? item.moving_avg_cost}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">On-Hand Value</p>
              <p className="font-mono font-semibold">{onhand?.onhand_value ?? '—'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* On-hand by location */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">On Hand by Location</h2>
        </CardHeader>
        <CardContent>
          {locations.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No stock on hand. Adjust or transfer stock to populate locations.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Location</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {locations.map((loc) => (
                  <TableRow key={loc.location_id} className="h-12">
                    <TableCell className="font-medium">{loc.location_name}</TableCell>
                    <TableCell className="text-right font-mono">
                      {loc.quantity} {uom}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Transaction history (immutable ledger, newest-first) */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Transaction History</h2>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No transactions yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Unit Cost</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.map((txn) => (
                  <TableRow key={txn.id} className="h-12">
                    <TableCell>
                      <TxnTypeBadge type={txn.txn_type} />
                    </TableCell>
                    <TableCell className="text-right font-mono">{txn.quantity}</TableCell>
                    <TableCell className="text-right font-mono">
                      {txn.unit_cost ?? '—'}
                    </TableCell>
                    <TableCell>{txn.location_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(txn.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{txn.reason ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Adjust Stock dialog (Task 12 stub) ─────────────────────────────── */}
      <StockAdjustDialog
        itemId={itemId}
        open={adjustOpen}
        onOpenChange={setAdjustOpen}
        onSuccess={invalidateStockViews}
      />

      {/* ── Transfer Stock dialog (Task 13 stub) ───────────────────────────── */}
      <StockTransferDialog
        itemId={itemId}
        open={transferOpen}
        onOpenChange={setTransferOpen}
        onSuccess={invalidateStockViews}
      />
    </div>
  )
}
