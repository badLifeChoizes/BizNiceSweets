// ABOUTME: Receive-a-PO-line dialog (Phase 8, Task 23) — qty received (default =
// ABOUTME: outstanding) + location Select → POST …/lines/{lineId}/receive, posting a
// ABOUTME: real inventory receipt. A 422 over-receipt surfaces a toast, dialog stays.

/**
 * ReceiveLineDialog — records a receipt against a single purchase-order line.
 *
 * Props (final contract — set in Task 22):
 *   poId: string — the PO the line belongs to (POST target)
 *   lineId: string — the line being received against
 *   outstandingQty: string — qty_ordered − qty_received, as an exact Decimal string;
 *                            the receive qty defaults to (and is capped at) this value
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful receipt; the host invalidates
 *              the PO detail + list queries so the roll-up + status refresh.
 *
 * Fields:
 *   1. Location — required. Populated from GET /api/v1/syerp/inventory/locations
 *                 (active only); the first active location is selected by default.
 *   2. Quantity — required, positive, defaults to outstandingQty. Kept as a raw
 *                 string and sent verbatim so the backend parses it as a Decimal
 *                 (no JS float mangling). Over-receipt is rejected server-side (422).
 *
 * Mutation: POST /api/v1/syerp/purchasing/orders/{poId}/lines/{lineId}/receive
 *   Success: onSuccess() (host invalidates PO detail + list), close, toast. The
 *            dialog does not hold the received item's id, so the item on-hand /
 *            transactions views refetch on next visit rather than being invalidated
 *            here; the PO roll-up (the crux of this path) refreshes immediately.
 *   Error (esp. 422 over-receipt / wrong PO status): toast.error with the server
 *          `detail` and DO NOT close — let the user fix the input.
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

// ─── Types ───────────────────────────────────────────────────────────────────

interface LocationOption {
  id: number
  name: string
  active: boolean
}

interface ReceiveLineDialogProps {
  poId: string
  lineId: string
  outstandingQty: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── API helpers ─────────────────────────────────────────────────────────────

// Active stock locations for the receipt destination Select. The list endpoint
// omits archived rows by default, so no query param is needed; we still guard on
// `active` in case that ever changes.
function fetchLocationOptions(): Promise<LocationOption[]> {
  return apiClient
    .get<LocationOption[]>('/api/v1/syerp/inventory/locations')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 over-receipt / wrong PO
// status) or a validation array of { loc, msg }. Map both to a readable,
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

export function ReceiveLineDialog({
  poId,
  lineId,
  outstandingQty,
  open,
  onOpenChange,
  onSuccess,
}: ReceiveLineDialogProps) {
  // ── Active location options ──
  const { data: locations = [] } = useQuery<LocationOption[], Error>({
    queryKey: ['syerp', 'inventory', 'locations', 'receive-options'],
    queryFn: fetchLocationOptions,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Form state ──
  const [locationId, setLocationId] = useState('')
  const [qty, setQty] = useState('')

  // ── Reset the form each time the dialog opens; qty defaults to the outstanding
  //    balance so the common "receive the whole line" case is one click. ──
  useEffect(() => {
    if (!open) return
    setLocationId('')
    setQty(outstandingQty)
  }, [open, outstandingQty])

  // ── Default to the first active location once loaded (single-location shops
  //    never have to touch the Select) ──
  useEffect(() => {
    if (!open || locationId) return
    if (activeLocations.length > 0) {
      setLocationId(String(activeLocations[0].id))
    }
  }, [open, locationId, activeLocations])

  // ── Validation ──
  const qtyNumber = Number(qty)
  const qtyError = qty.trim() === '' || !Number.isFinite(qtyNumber) || qtyNumber <= 0
  const locationError = !locationId
  const formInvalid = qtyError || locationError

  // ── Mutation ──
  interface ReceivePayload {
    location_id: number
    qty: string
  }

  const receiveMutation = useMutation<unknown, Error, ReceivePayload>({
    mutationFn: (payload) =>
      apiClient
        .post(
          `/api/v1/syerp/purchasing/orders/${poId}/lines/${lineId}/receive`,
          payload,
        )
        .then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Receipt posted.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (e.g. receiving
      // more than outstanding — the backend rejects with 422 over-receipt).
      toast.error(getApiErrorMessage(err, 'Failed to post receipt. Please try again.'))
    },
  })

  const isSaving = receiveMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    receiveMutation.mutate({
      location_id: Number(locationId),
      qty: qty.trim(),
    })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="receive-line-description">
        <DialogHeader>
          <DialogTitle>Receive Line</DialogTitle>
          <DialogDescription id="receive-line-description">
            Record a receipt against this line ({outstandingQty} outstanding). The
            quantity posts a real inventory receipt at the chosen location.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Location */}
          <div className="space-y-2">
            <Label htmlFor="receive-location">Location</Label>
            <Select value={locationId} onValueChange={setLocationId}>
              <SelectTrigger id="receive-location">
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

          {/* Quantity */}
          <div className="space-y-2">
            <Label htmlFor="receive-qty">Quantity</Label>
            <Input
              id="receive-qty"
              inputMode="decimal"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="e.g. 10"
            />
            <p className="text-xs text-muted-foreground">
              Defaults to the outstanding balance. Receiving more than outstanding is
              rejected.
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
                Receiving…
              </>
            ) : (
              'Post Receipt'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
