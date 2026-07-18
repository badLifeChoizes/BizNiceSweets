// ABOUTME: GELATO Fulfillment screen (/gelato/fulfillment) — outbound pick/pack/ship
// ABOUTME: for a sales order (GELATO-02). SO selector (Confirmed/Fulfilling) → pick list
// ABOUTME: (ordered/reserved/picked/shipped) → Pick (into staging) → Pack → Ship, each
// ABOUTME: surfacing the server's 4xx reason as a toast. Ship asks for confirmation.

/**
 * Fulfillment screen — GELATO outbound pick/pack/ship (/gelato/fulfillment).
 *
 * Layout: p-8 space-y-6 (matches the GELATO Bins/Putaway pattern).
 *
 * Flow (GELATO-02, SC2–SC4):
 *   1. SO selector at the top, limited to Confirmed/Fulfilling sales orders (the CRUMB
 *      SO list has no status filter param, so we fetch and filter client-side). An
 *      initial ?so=<id> query param (the SO-detail "Fulfil" affordance) preselects one.
 *   2. On an SO, the pick list (usePickList) renders per line: ordered / reserved /
 *      picked / shipped. "Pick" opens PickDialog (per-line source bin + qty + staging
 *      bin) and POSTs the pick; the returned Shipment is recorded here.
 *   3. Once a shipment exists it walks the FSM: "Pack" (picking→packed) then "Ship"
 *      (packed→shipped, behind a confirm dialog — shipping issues stock + posts COGS).
 *   4. Every action toasts success; a 4xx (over-pick/over-ship/non-stock/wrong-state)
 *      surfaces its `detail` as a toast.error (mirrors PutawayDialog).
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { GelatoNav } from '@/routes/gelato/components/GelatoNav'
import { PickDialog } from '@/routes/gelato/components/PickDialog'
import {
  usePickList,
  useExecutePack,
  useExecuteShip,
  type Shipment,
} from '@/routes/gelato/hooks'
import { useSalesOrders } from '@/routes/crumb/hooks'

// ─── Helpers ─────────────────────────────────────────────────────────────────

// SOs that can be fulfilled: confirmed (stock reserved) or already fulfilling.
const FULFILLABLE_STATUSES = new Set(['confirmed', 'fulfilling'])

// Surface the server's real reason (string `detail` or a validation array) instead
// of a generic message — mirrors PutawayDialog / PickDialog.
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

function ShipmentStatusBadge({ status }: { status: string }) {
  const map: Record<string, { className: string; label: string }> = {
    picking: { className: 'border-amber-300 bg-amber-50 text-amber-700', label: 'Picking' },
    packed: { className: 'border-blue-300 bg-blue-50 text-blue-700', label: 'Packed' },
    shipped: { className: 'border-green-300 bg-green-50 text-green-700', label: 'Shipped' },
    cancelled: { className: 'text-muted-foreground', label: 'Cancelled' },
  }
  const cfg = map[status] ?? { className: '', label: status }
  return (
    <Badge variant="outline" className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function Fulfillment() {
  // ── SO options limited to fulfillable (confirmed/fulfilling) orders ──
  const { data: salesOrders = [] } = useSalesOrders()
  const fulfillable = salesOrders.filter((so) => FULFILLABLE_STATUSES.has(so.status))

  // ── Selected SO — seeded from ?so=<id> when present, else user-chosen ──
  const [searchParams] = useSearchParams()
  const [soId, setSoId] = useState('')
  useEffect(() => {
    const initial = searchParams.get('so')
    if (initial) setSoId(initial)
  }, [searchParams])

  // ── Pick list for the selected SO ──
  const { data: pickList, isLoading } = usePickList(soId)

  // ── The active shipment (set once a pick returns it; updated on pack/ship) ──
  const [shipment, setShipment] = useState<Shipment | null>(null)
  useEffect(() => {
    // Switching SO clears any shipment held from a previous one.
    setShipment(null)
  }, [soId])

  // ── Dialog seams ──
  const [pickOpen, setPickOpen] = useState(false)
  const [shipConfirmOpen, setShipConfirmOpen] = useState(false)

  // ── Pack / Ship mutations ──
  const packMutation = useExecutePack()
  const shipMutation = useExecuteShip()

  function handlePack() {
    if (!shipment) return
    packMutation.mutate(
      { shipmentId: shipment.id, payload: {} },
      {
        onSuccess: (updated) => {
          setShipment(updated)
          toast.success('Shipment packed.')
        },
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Failed to pack the shipment. Please try again.')),
      },
    )
  }

  function handleShip() {
    if (!shipment) return
    shipMutation.mutate(shipment.id, {
      onSuccess: (updated) => {
        setShipment(updated)
        setShipConfirmOpen(false)
        toast.success('Shipment shipped.')
      },
      onError: (err) =>
        toast.error(getApiErrorMessage(err, 'Failed to ship the shipment. Please try again.')),
    })
  }

  const lines = pickList?.lines ?? []
  const canPick = !!soId && lines.length > 0

  return (
    <div className="p-8 space-y-6">
      <GelatoNav />

      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Fulfillment</h1>
        <p className="text-sm text-muted-foreground">
          Pick a confirmed sales order into staging, then pack and ship it.
        </p>
      </div>

      {/* SO selector */}
      <div className="max-w-md space-y-2">
        <Label htmlFor="fulfillment-so">Sales order</Label>
        <Select value={soId} onValueChange={setSoId}>
          <SelectTrigger id="fulfillment-so">
            <SelectValue placeholder="Select a sales order" />
          </SelectTrigger>
          <SelectContent>
            {fulfillable.map((so) => (
              <SelectItem key={so.id} value={so.id}>
                {so.so_number}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Pick list */}
      {!soId ? (
        <p className="text-sm text-muted-foreground">
          Select a sales order to view its pick list.
        </p>
      ) : isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="animate-spin" aria-hidden="true" />
          Loading pick list…
        </div>
      ) : lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">This sales order has no lines to pick.</p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-medium">Pick list</h2>
              {shipment && <ShipmentStatusBadge status={shipment.status} />}
            </div>
            <div className="flex gap-2">
              <Button variant="default" onClick={() => setPickOpen(true)} disabled={!canPick}>
                Pick
              </Button>
              {shipment?.status === 'picking' && (
                <Button
                  variant="outline"
                  onClick={handlePack}
                  disabled={packMutation.isPending}
                >
                  {packMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Packing…
                    </>
                  ) : (
                    'Pack'
                  )}
                </Button>
              )}
              {shipment?.status === 'packed' && (
                <Button variant="outline" onClick={() => setShipConfirmOpen(true)}>
                  Ship
                </Button>
              )}
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead className="text-right">Ordered</TableHead>
                <TableHead className="text-right">Reserved</TableHead>
                <TableHead className="text-right">Picked</TableHead>
                <TableHead className="text-right">Shipped</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.sales_order_line_id}>
                  <TableCell className="font-medium">{line.description}</TableCell>
                  <TableCell className="text-right tabular-nums">{line.qty_ordered}</TableCell>
                  <TableCell className="text-right tabular-nums">{line.qty_reserved}</TableCell>
                  <TableCell className="text-right tabular-nums">{line.qty_picked}</TableCell>
                  <TableCell className="text-right tabular-nums">{line.qty_shipped}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pick dialog */}
      {pickOpen && (
        <PickDialog
          soId={soId}
          lines={lines}
          open={pickOpen}
          onOpenChange={setPickOpen}
          onPicked={(s) => setShipment(s)}
        />
      )}

      {/* Ship confirmation */}
      <Dialog open={shipConfirmOpen} onOpenChange={setShipConfirmOpen}>
        <DialogContent aria-describedby="ship-confirm-description">
          <DialogHeader>
            <DialogTitle>Ship this shipment?</DialogTitle>
            <DialogDescription id="ship-confirm-description">
              Shipping issues the picked stock out of inventory and posts the COGS journal
              entry. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setShipConfirmOpen(false)}
              disabled={shipMutation.isPending}
            >
              Cancel
            </Button>
            <Button variant="default" onClick={handleShip} disabled={shipMutation.isPending}>
              {shipMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Shipping…
                </>
              ) : (
                'Confirm Ship'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
