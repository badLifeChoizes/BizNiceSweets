// ABOUTME: Adjust-Stock dialog for a SYERP inventory item (Phase 8, Task 12) —
// ABOUTME: location Select + optional bin Select (D-P4-1) + signed qty_delta + required
// ABOUTME: reason → POST …/adjustments. A 422 rejection toasts and keeps the dialog open.

/**
 * StockAdjustDialog — posts a signed stock adjustment for an inventory item.
 *
 * Props:
 *   itemId: string — the item being adjusted (POST target)
 *   open: boolean — controls dialog visibility
 *   onOpenChange: (open: boolean) => void — Radix-controlled open state
 *   onSuccess: () => void — called after a successful post; the host invalidates
 *              the item's onhand + transactions queries so the view refreshes.
 *
 * Fields:
 *   1. Location  — required. Populated from GET /api/v1/syerp/inventory/locations
 *                  (active only); the first active location is selected by default.
 *   2. Bin       — optional (D-P4-1). Populated from useBins(location) once a
 *                  location is chosen; defaults to "Unbinned pool" → bin_id: null
 *                  (draw from unbinned stock only). Hidden — and null sent — when
 *                  the bins query errors (GELATO off) or the location has no bins.
 *   3. Quantity  — required, SIGNED. A negative delta is how manual write-offs /
 *                  issues are recorded. Kept as a raw string and sent verbatim so
 *                  the backend parses it as a Decimal (no JS float mangling).
 *   4. Reason    — required, non-empty. Blocks submit while blank.
 *
 * Mutation: POST /api/v1/syerp/inventory/items/{itemId}/adjustments
 *   Success: onSuccess() (host invalidates onhand+transactions), close, toast.
 *   Error (esp. 422 per-location negative-stock or insufficient unbinned pool):
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

interface StockAdjustDialogProps {
  itemId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── API helpers ─────────────────────────────────────────────────────────────

// Active stock locations for the destination Select. The list endpoint omits
// archived rows by default, so no query param is needed; we still guard on
// `active` in case that ever changes.
function fetchLocationOptions(): Promise<LocationOption[]> {
  return apiClient
    .get<LocationOption[]>('/api/v1/syerp/inventory/locations')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 negative-stock violation) or
// a validation array of { loc, msg }. Map both to a readable, actionable message.
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

export function StockAdjustDialog({
  itemId,
  open,
  onOpenChange,
  onSuccess,
}: StockAdjustDialogProps) {
  // ── Active location options ──
  const { data: locations = [] } = useQuery<LocationOption[], Error>({
    queryKey: ['syerp', 'inventory', 'locations', 'adjust-options'],
    queryFn: fetchLocationOptions,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Form state ──
  const [locationId, setLocationId] = useState('')
  const [binId, setBinId] = useState(UNBINNED_POOL)
  const [qtyDelta, setQtyDelta] = useState('')
  const [reason, setReason] = useState('')

  // ── Bins at the chosen location (optional picker, D-P4-1) ──
  // NULL bin_id = draw from the unbinned pool only; at a binned location the
  // operator should name a bin. When the bins query errors (GELATO off) or the
  // location has no bins, the picker hides and the adjustment stays unbinned.
  const { data: bins = [], isError: binsUnavailable } = useBins(Number(locationId))
  const activeBins = bins.filter((b) => b.active)
  const showBinSelect = !!locationId && !binsUnavailable && activeBins.length > 0

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setLocationId('')
    setBinId(UNBINNED_POOL)
    setQtyDelta('')
    setReason('')
  }, [open])

  // ── Default to the first active location once loaded (single-location shops
  //    never have to touch the Select) ──
  useEffect(() => {
    if (!open || locationId) return
    if (activeLocations.length > 0) {
      setLocationId(String(activeLocations[0].id))
    }
  }, [open, locationId, activeLocations])

  // ── Validation ──
  const reasonError = !reason.trim()
  const qtyNumber = Number(qtyDelta)
  const qtyError = qtyDelta.trim() === '' || !Number.isFinite(qtyNumber) || qtyNumber === 0
  const locationError = !locationId
  const formInvalid = reasonError || qtyError || locationError

  // ── Mutation ──
  interface AdjustmentPayload {
    location_id: number
    bin_id: number | null
    qty_delta: string
    reason: string
  }

  const adjustMutation = useMutation<TransactionRead, Error, AdjustmentPayload>({
    mutationFn: (payload) =>
      apiClient
        .post<TransactionRead>(
          `/api/v1/syerp/inventory/items/${itemId}/adjustments`,
          payload,
        )
        .then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Stock adjusted.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (e.g. a delta that
      // would drive this location negative — the backend rejects with 422).
      toast.error(getApiErrorMessage(err, 'Failed to adjust stock. Please try again.'))
    },
  })

  const isSaving = adjustMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    adjustMutation.mutate({
      location_id: Number(locationId),
      bin_id: showBinSelect && binId !== UNBINNED_POOL ? Number(binId) : null,
      qty_delta: qtyDelta.trim(),
      reason: reason.trim(),
    })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="adjust-stock-description">
        <DialogHeader>
          <DialogTitle>Adjust Stock</DialogTitle>
          <DialogDescription id="adjust-stock-description">
            Record a signed quantity change at a location. Use a negative quantity for
            write-offs or issues. A reason is required — every adjustment is audited.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Location */}
          <div className="space-y-2">
            <Label htmlFor="adjust-location">Location</Label>
            <Select
              value={locationId}
              onValueChange={(v) => {
                setLocationId(v)
                setBinId(UNBINNED_POOL) // a bin belongs to one location — never carry it over
              }}
            >
              <SelectTrigger id="adjust-location">
                <SelectValue placeholder="Select a location" />
              </SelectTrigger>
              <SelectContent>
                {activeLocations.map((loc) => (
                  <SelectItem key={loc.id} value={String(loc.id)}>
                    {loc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {locationError && (
              <p className="text-sm text-destructive">Select a location.</p>
            )}
          </div>

          {/* Bin (optional — shown only when the location has active bins) */}
          {showBinSelect && (
            <div className="space-y-2">
              <Label htmlFor="adjust-bin">Bin</Label>
              <Select value={binId} onValueChange={setBinId}>
                <SelectTrigger id="adjust-bin">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNBINNED_POOL}>Unbinned pool</SelectItem>
                  {activeBins.map((bin) => (
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

          {/* Signed quantity */}
          <div className="space-y-2">
            <Label htmlFor="adjust-qty">Quantity</Label>
            <Input
              id="adjust-qty"
              inputMode="decimal"
              value={qtyDelta}
              onChange={(e) => setQtyDelta(e.target.value)}
              placeholder="e.g. 10 or -3"
            />
            <p className="text-xs text-muted-foreground">
              Signed — positive adds stock, negative removes it.
            </p>
          </div>

          {/* Reason (required) */}
          <div className="space-y-2">
            <Label htmlFor="adjust-reason">Reason</Label>
            <Input
              id="adjust-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Cycle count correction"
            />
            {reasonError && <p className="text-sm text-destructive">Reason is required.</p>}
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
                Posting…
              </>
            ) : (
              'Post Adjustment'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
