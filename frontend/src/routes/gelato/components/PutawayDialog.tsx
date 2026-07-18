// ABOUTME: Directed-putaway dialog (Phase 12a, Task 14) — pre-fills the suggested
// ABOUTME: target bin + full unbinned qty, lets the user override the bin, then POSTs
// ABOUTME: a putaway (from_bin_id null = unbinned pool). A 422 over-draw / bad-bin
// ABOUTME: rejection surfaces a toast and keeps the dialog open.

/**
 * PutawayDialog — moves unbinned stock of one item into a bin at its location.
 *
 * Mirrors routes/syerp/components/StockTransferDialog: a target Select + qty Input →
 * a single mutation, with the server's 422 reason surfaced as a toast.error.
 *
 * Props:
 *   itemId: string — the SYERP inventory item being put away (POST target)
 *   itemLabel: string — human label for the header (item code/name, falls back to id)
 *   locationId: number — the stock location the unbinned stock (and target bins) live in
 *   unbinnedQty: string — the item's unbinned qty at the location, as an exact Decimal
 *                         string; the putaway qty defaults to this full amount
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful putaway (the mutation already
 *              invalidates bins + unbinned + item on-hand; the host may do extra)
 *
 * Fields:
 *   1. Target bin — required. Populated from GET …/locations/{id}/bins (active bins).
 *                   Pre-filled from usePutawaySuggestion (D-P12a-10 heuristic); the
 *                   user may override it.
 *   2. Quantity   — required, positive, defaults to the full unbinned qty. Kept as a
 *                   raw string and sent verbatim so the backend parses a Decimal
 *                   (no JS float mangling). Over-draw is rejected server-side (422).
 *
 * Mutation: POST /api/v1/gelato/putaway with the exact PutawayRequest body
 *   { item_id, location_id, to_bin_id, qty, from_bin_id: null } — from_bin_id null
 *   means the source is the unbinned pool.
 *   Success: onSuccess(), toast, close.
 *   Error (esp. 422 over-draw / bad bin): toast.error with the server `detail`, and
 *          DO NOT close — let the user fix the input.
 */

import { useState, useEffect } from 'react'
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
import { useBins, usePutawaySuggestion, useExecutePutaway } from '../hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface PutawayDialogProps {
  itemId: string
  itemLabel: string
  locationId: number
  unbinnedQty: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── API error mapping ───────────────────────────────────────────────────────

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 over-draw / bad bin) or a
// validation array of { loc, msg }. Map both to a readable, actionable message.
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

export function PutawayDialog({
  itemId,
  itemLabel,
  locationId,
  unbinnedQty,
  open,
  onOpenChange,
  onSuccess,
}: PutawayDialogProps) {
  // ── Active bins for the target Select + the suggested target bin ──
  const { data: bins = [] } = useBins(locationId)
  const activeBins = bins.filter((b) => b.active)
  const { data: suggestion } = usePutawaySuggestion(itemId, locationId)
  const suggestedBinId = suggestion?.suggested_bin_id ?? null

  // ── Form state ──
  const [toBinId, setToBinId] = useState('')
  const [qty, setQty] = useState('')

  // ── Reset the form each time the dialog opens; qty defaults to the full unbinned
  //    qty so the common "put the whole lot away" case is one click. ──
  useEffect(() => {
    if (!open) return
    setToBinId('')
    setQty(unbinnedQty)
  }, [open, unbinnedQty])

  // ── Pre-fill the target bin from the suggestion once it loads (the user can
  //    still override it). Only sets while the field is untouched. ──
  useEffect(() => {
    if (!open || toBinId) return
    if (suggestedBinId != null) setToBinId(String(suggestedBinId))
  }, [open, toBinId, suggestedBinId])

  // ── Validation ──
  const qtyNumber = Number(qty)
  const qtyError = qty.trim() === '' || !Number.isFinite(qtyNumber) || qtyNumber <= 0
  const binError = !toBinId
  const formInvalid = qtyError || binError

  // ── Mutation ──
  const putawayMutation = useExecutePutaway()

  const isSaving = putawayMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    putawayMutation.mutate(
      {
        item_id: itemId,
        location_id: locationId,
        to_bin_id: Number(toBinId),
        qty: qty.trim(),
        from_bin_id: null,
      },
      {
        onSuccess: () => {
          onSuccess()
          toast.success('Stock put away.')
          onOpenChange(false)
        },
        onError: (err) => {
          // Keep the dialog open so the user can correct the input (e.g. putting
          // away more than is unbinned — the backend rejects with 422 over-draw).
          toast.error(getApiErrorMessage(err, 'Failed to put stock away. Please try again.'))
        },
      },
    )
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="putaway-description">
        <DialogHeader>
          <DialogTitle>Put Away Stock</DialogTitle>
          <DialogDescription id="putaway-description">
            Move {itemLabel} ({unbinnedQty} unbinned) into a bin. The suggested bin is
            pre-filled — override it if needed. Putting away more than is unbinned is
            rejected.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Target bin */}
          <div className="space-y-2">
            <Label htmlFor="putaway-bin">Target bin</Label>
            <Select value={toBinId} onValueChange={setToBinId}>
              <SelectTrigger id="putaway-bin">
                <SelectValue placeholder="Select a target bin" />
              </SelectTrigger>
              <SelectContent>
                {activeBins.map((bin) => (
                  <SelectItem key={bin.id} value={String(bin.id)}>
                    {bin.code}
                    {bin.id === suggestedBinId ? ' (suggested)' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {binError && <p className="text-sm text-destructive">Select a target bin.</p>}
          </div>

          {/* Quantity */}
          <div className="space-y-2">
            <Label htmlFor="putaway-qty">Quantity</Label>
            <Input
              id="putaway-qty"
              inputMode="decimal"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="e.g. 10"
            />
            <p className="text-xs text-muted-foreground">
              Defaults to the full unbinned quantity. Putting away more than is unbinned
              is rejected.
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
                Putting away…
              </>
            ) : (
              'Confirm Putaway'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
