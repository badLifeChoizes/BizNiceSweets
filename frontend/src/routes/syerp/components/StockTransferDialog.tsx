// ABOUTME: Transfer-Stock dialog for a SYERP inventory item (Phase 8, Task 13) —
// ABOUTME: from-location + optional from-bin (D-P4-1) + to-location Selects + positive
// ABOUTME: qty → POST …/transfers. A 422 rejection surfaces a toast, dialog stays.

/**
 * StockTransferDialog — posts a from→to stock transfer for an inventory item.
 *
 * Props:
 *   itemId: string — the item being transferred (POST target)
 *   open: boolean — controls dialog visibility
 *   onOpenChange: (open: boolean) => void — Radix-controlled open state
 *   onSuccess: () => void — called after a successful post; the host invalidates
 *              the item's onhand + transactions queries so the view refreshes.
 *
 * Fields:
 *   1. From location — required. Populated from GET
 *                      /api/v1/syerp/inventory/locations (active only).
 *   2. From bin      — optional (D-P4-1). Populated from useBins(source) once a
 *                      source is chosen; defaults to "Unbinned pool" →
 *                      from_bin_id: null (draw from unbinned stock only). Hidden —
 *                      and null sent — when the bins query errors (GELATO off) or
 *                      the source has no bins.
 *   3. To location   — required. Same source. Must differ from the source; a
 *                      from==to selection is blocked client-side (submit disabled
 *                      + inline error) and never POSTed. There is deliberately NO
 *                      destination bin control: transfers arrive in the
 *                      destination's unbinned pool (D-P4-5) — direct with Putaway.
 *   4. Quantity      — required, positive. Kept as a raw string and sent verbatim
 *                      so the backend parses it as a Decimal (no JS float mangling).
 *
 * Mutation: POST /api/v1/syerp/inventory/items/{itemId}/transfers
 *   Success: onSuccess() (host invalidates onhand+transactions), close, toast.
 *   Error (esp. 422 source over-draw, incl. an insufficient unbinned pool):
 *          toast.error with the server `detail` and DO NOT close — let the user
 *          fix the input (AC10-6).
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/api/client'
import { useBins } from '@/routes/gelato/hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

// Sentinel Select value for the "no bin — unbinned pool" default (Radix Select
// forbids an empty-string item value).
const UNBINNED_POOL = 'unbinned'

interface LocationOption {
  id: number
  name: string
  active: boolean
}

interface TransactionRead {
  id: string
  item_id: string
  location_id: number
  txn_type: string
  quantity: string
  created_at: string
}

interface StockTransferDialogProps {
  itemId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── API helpers ─────────────────────────────────────────────────────────────

// Active stock locations for the from/to Selects. The list endpoint omits
// archived rows by default, so no query param is needed; we still guard on
// `active` in case that ever changes.
function fetchLocationOptions(): Promise<LocationOption[]> {
  return apiClient
    .get<LocationOption[]>('/api/v1/syerp/inventory/locations')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 over-draw / same-location
// violation) or a validation array of { loc, msg }. Map both to a readable,
// actionable message.
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

// ─── Main component ──────────────────────────────────────────────────────────

export function StockTransferDialog({
  itemId,
  open,
  onOpenChange,
  onSuccess,
}: StockTransferDialogProps) {
  // ── Active location options ──
  const { data: locations = [] } = useQuery<LocationOption[], Error>({
    queryKey: ['syerp', 'inventory', 'locations', 'transfer-options'],
    queryFn: fetchLocationOptions,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Form state ──
  const [fromLocationId, setFromLocationId] = useState('')
  const [fromBinId, setFromBinId] = useState(UNBINNED_POOL)
  const [toLocationId, setToLocationId] = useState('')
  const [qty, setQty] = useState('')

  // ── Bins at the SOURCE location (optional from-bin picker, D-P4-1) ──
  // NULL from_bin_id = draw from the source's unbinned pool only; at a binned
  // source the operator should name a bin. When the bins query errors (GELATO
  // off) or the source has no bins, the picker hides and the draw stays unbinned.
  // The destination gets no bin control — transfers arrive unbinned (D-P4-5).
  const { data: fromBins = [], isError: binsUnavailable } = useBins(Number(fromLocationId))
  const activeFromBins = fromBins.filter((b) => b.active)
  const showFromBinSelect = !!fromLocationId && !binsUnavailable && activeFromBins.length > 0

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setFromLocationId('')
    setFromBinId(UNBINNED_POOL)
    setToLocationId('')
    setQty('')
  }, [open])

  // ── Validation ──
  const qtyNumber = Number(qty)
  const qtyError = qty.trim() === '' || !Number.isFinite(qtyNumber) || qtyNumber <= 0
  const fromError = !fromLocationId
  const toError = !toLocationId
  // Block a from==to transfer client-side — never POST it.
  const sameLocationError = !!fromLocationId && fromLocationId === toLocationId
  const formInvalid = qtyError || fromError || toError || sameLocationError

  // ── Mutation ──
  interface TransferPayload {
    from_location_id: number
    from_bin_id: number | null
    to_location_id: number
    qty: string
  }

  const transferMutation = useMutation<TransactionRead[], Error, TransferPayload>({
    mutationFn: (payload) =>
      apiClient
        .post<TransactionRead[]>(
          `/api/v1/syerp/inventory/items/${itemId}/transfers`,
          payload,
        )
        .then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Stock transferred.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (e.g. moving more
      // than the source holds — the backend rejects with 422 over-draw).
      toast.error(getApiErrorMessage(err, 'Failed to transfer stock. Please try again.'))
    },
  })

  const isSaving = transferMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    transferMutation.mutate({
      from_location_id: Number(fromLocationId),
      from_bin_id:
        showFromBinSelect && fromBinId !== UNBINNED_POOL ? Number(fromBinId) : null,
      to_location_id: Number(toLocationId),
      qty: qty.trim(),
    })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="transfer-stock-description">
        <DialogHeader>
          <DialogTitle>Transfer Stock</DialogTitle>
          <DialogDescription id="transfer-stock-description">
            Move quantity from one location to another. The source and destination
            must differ, and the source must hold enough to cover the transfer.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* From location */}
          <div className="space-y-2">
            <Label htmlFor="transfer-from">From location</Label>
            <Select
              value={fromLocationId}
              onValueChange={(v) => {
                setFromLocationId(v)
                setFromBinId(UNBINNED_POOL) // a bin belongs to one location — never carry it over
              }}
            >
              <SelectTrigger id="transfer-from">
                <SelectValue placeholder="Select a source location" />
              </SelectTrigger>
              <SelectContent>
                {activeLocations.map((loc) => (
                  <SelectItem key={loc.id} value={String(loc.id)}>
                    {loc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fromError && <p className="text-sm text-destructive">Select a source location.</p>}
          </div>

          {/* From bin (optional — shown only when the source has active bins) */}
          {showFromBinSelect && (
            <div className="space-y-2">
              <Label htmlFor="transfer-from-bin">From bin</Label>
              <Select value={fromBinId} onValueChange={setFromBinId}>
                <SelectTrigger id="transfer-from-bin">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNBINNED_POOL}>Unbinned pool</SelectItem>
                  {activeFromBins.map((bin) => (
                    <SelectItem key={bin.id} value={String(bin.id)}>
                      {bin.code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Optional — "Unbinned pool" draws from stock not yet put away.
              </p>
            </div>
          )}

          {/* To location */}
          <div className="space-y-2">
            <Label htmlFor="transfer-to">To location</Label>
            <Select value={toLocationId} onValueChange={setToLocationId}>
              <SelectTrigger id="transfer-to">
                <SelectValue placeholder="Select a destination location" />
              </SelectTrigger>
              <SelectContent>
                {activeLocations.map((loc) => (
                  <SelectItem key={loc.id} value={String(loc.id)}>
                    {loc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {toError && (
              <p className="text-sm text-destructive">Select a destination location.</p>
            )}
            {sameLocationError && (
              <p className="text-sm text-destructive">
                Source and destination must be different.
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Arrives in the destination's unbinned pool — direct it with Putaway.
            </p>
          </div>

          {/* Quantity */}
          <div className="space-y-2">
            <Label htmlFor="transfer-qty">Quantity</Label>
            <Input
              id="transfer-qty"
              inputMode="decimal"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="e.g. 10"
            />
            <p className="text-xs text-muted-foreground">
              Positive — the amount to move from the source to the destination.
            </p>
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || formInvalid}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Transferring…
              </>
            ) : (
              'Transfer Stock'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
