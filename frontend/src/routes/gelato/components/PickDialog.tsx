// ABOUTME: Pick dialog (Phase 12b, Task 14) — per-SO-line source-bin + qty pickers
// ABOUTME: (pre-filled with the suggested source bin + remaining-to-pick) plus a staging
// ABOUTME: bin selector, then POSTs the exact PickRequest body. A 4xx over-pick /
// ABOUTME: non-stock-line / wrong-state rejection surfaces a toast and keeps it open.

/**
 * PickDialog — picks a sales order's lines into a staging bin (GELATO-02, SC2).
 *
 * Mirrors PutawayDialog: per-line Select + qty Input over one mutation, with the
 * server's 4xx reason surfaced as a toast.error (dialog stays open on failure).
 *
 * Props:
 *   soId: string — the sales order being picked (POST target)
 *   lines: PickListLine[] — the pick-list lines (ordered/reserved/picked figures +
 *          suggested_from_bin_id + candidate available_bins), from usePickList
 *   open / onOpenChange — Radix-controlled visibility
 *   onPicked: (shipment) => void — called with the returned Shipment after a pick
 *          (the mutation already invalidates bins/unbinned/on-hand/SO/pick-list; the
 *          host records the shipment so it can then pack/ship it)
 *
 * Per line:
 *   Source bin — defaults to suggested_from_bin_id (falls back to the first candidate
 *                bin holding the item). Options are the line's available_bins.
 *   Quantity   — defaults to remaining-to-pick (qty_ordered − qty_picked), kept as a
 *                raw Decimal string and sent verbatim (no JS float math, D-11).
 * Staging bin — where the whole pick consolidates; options are the union of every
 *               line's available_bins (what the pick list surfaces).
 *
 * Only lines with a positive qty and a chosen source bin are submitted. The POST body
 * is the exact PickRequest shape:
 *   { sales_order_id, staging_bin_id, lines: [{ sales_order_line_id, from_bin_id, qty }] }
 */

import { useState, useEffect, useMemo } from 'react'
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
import {
  useExecutePick,
  type PickListLine,
  type PickListBin,
  type Shipment,
} from '../hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface PickDialogProps {
  soId: string
  lines: PickListLine[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onPicked: (shipment: Shipment) => void
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Remaining to pick = qty_ordered − qty_picked. When nothing is picked yet (the
// common case) return the ordered string verbatim so no float rounding creeps in
// (D-11); only fall back to arithmetic once a partial pick exists.
function remainingToPick(line: PickListLine): string {
  const picked = Number(line.qty_picked)
  if (!Number.isFinite(picked) || picked === 0) return line.qty_ordered
  const remaining = Number(line.qty_ordered) - picked
  return remaining > 0 ? String(remaining) : '0'
}

// The default source bin for a line: its suggestion, else the first candidate bin.
function defaultBinId(line: PickListLine): string {
  if (line.suggested_from_bin_id != null) return String(line.suggested_from_bin_id)
  return line.available_bins.length ? String(line.available_bins[0].bin_id) : ''
}

// Surface the server's real reason instead of a generic message. FastAPI returns
// either a string `detail` (e.g. 409 over-pick / wrong FSM state / non-stock line)
// or a validation array of { loc, msg }; map both to a readable message.
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

export function PickDialog({ soId, lines, open, onOpenChange, onPicked }: PickDialogProps) {
  // ── Staging bin options: the union of every line's candidate bins ──
  const stagingBins = useMemo<PickListBin[]>(() => {
    const seen = new Map<number, PickListBin>()
    for (const line of lines) {
      for (const bin of line.available_bins) {
        if (!seen.has(bin.bin_id)) seen.set(bin.bin_id, bin)
      }
    }
    return [...seen.values()]
  }, [lines])

  // ── Form state (bins + qty keyed by SO line id) + the staging bin ──
  const [binByLine, setBinByLine] = useState<Record<string, string>>({})
  const [qtyByLine, setQtyByLine] = useState<Record<string, string>>({})
  const [stagingBinId, setStagingBinId] = useState('')

  // ── Reset each time the dialog opens: source bins → suggestion, qty → remaining,
  //    staging bin → the first candidate bin. ──
  useEffect(() => {
    if (!open) return
    const bins: Record<string, string> = {}
    const qtys: Record<string, string> = {}
    for (const line of lines) {
      bins[line.sales_order_line_id] = defaultBinId(line)
      qtys[line.sales_order_line_id] = remainingToPick(line)
    }
    setBinByLine(bins)
    setQtyByLine(qtys)
    setStagingBinId(stagingBins.length ? String(stagingBins[0].bin_id) : '')
  }, [open, lines, stagingBins])

  // ── Lines actually being picked: positive qty + a chosen source bin ──
  const pickLines = lines
    .map((line) => {
      const from = binByLine[line.sales_order_line_id] ?? ''
      const qty = (qtyByLine[line.sales_order_line_id] ?? '').trim()
      return { line, from, qty }
    })
    .filter(({ from, qty }) => {
      const n = Number(qty)
      return from !== '' && qty !== '' && Number.isFinite(n) && n > 0
    })

  const formInvalid = !stagingBinId || pickLines.length === 0

  // ── Mutation ──
  const pickMutation = useExecutePick()
  const isSaving = pickMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    pickMutation.mutate(
      {
        sales_order_id: soId,
        staging_bin_id: Number(stagingBinId),
        lines: pickLines.map(({ line, from, qty }) => ({
          sales_order_line_id: line.sales_order_line_id,
          from_bin_id: Number(from),
          qty,
        })),
      },
      {
        onSuccess: (shipment) => {
          onPicked(shipment)
          toast.success('Sales order picked into staging.')
          onOpenChange(false)
        },
        onError: (err) => {
          // Keep the dialog open so the user can correct the pick (e.g. picking more
          // than is on hand / than remains — the backend rejects with a 4xx).
          toast.error(getApiErrorMessage(err, 'Failed to pick the order. Please try again.'))
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="pick-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Pick Sales Order</DialogTitle>
          <DialogDescription id="pick-description">
            Choose a source bin and quantity for each line, then a staging bin to
            consolidate the pick. Picking more than is on hand or remaining is rejected.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Per-line source bin + quantity */}
          {lines.map((line) => (
            <div key={line.sales_order_line_id} className="grid grid-cols-2 gap-3">
              <div className="col-span-2 text-sm font-medium">{line.description}</div>
              <div className="space-y-2">
                <Label htmlFor={`pick-bin-${line.sales_order_line_id}`}>Source bin</Label>
                <Select
                  value={binByLine[line.sales_order_line_id] ?? ''}
                  onValueChange={(v) =>
                    setBinByLine((prev) => ({ ...prev, [line.sales_order_line_id]: v }))
                  }
                >
                  <SelectTrigger id={`pick-bin-${line.sales_order_line_id}`}>
                    <SelectValue placeholder="Select a source bin" />
                  </SelectTrigger>
                  <SelectContent>
                    {line.available_bins.map((bin) => (
                      <SelectItem key={bin.bin_id} value={String(bin.bin_id)}>
                        {bin.code} ({bin.on_hand} on hand)
                        {bin.bin_id === line.suggested_from_bin_id ? ' — suggested' : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor={`pick-qty-${line.sales_order_line_id}`}>Quantity</Label>
                <Input
                  id={`pick-qty-${line.sales_order_line_id}`}
                  inputMode="decimal"
                  value={qtyByLine[line.sales_order_line_id] ?? ''}
                  onChange={(e) =>
                    setQtyByLine((prev) => ({
                      ...prev,
                      [line.sales_order_line_id]: e.target.value,
                    }))
                  }
                  placeholder="e.g. 10"
                />
              </div>
            </div>
          ))}

          {/* Staging bin */}
          <div className="space-y-2">
            <Label htmlFor="pick-staging-bin">Staging bin</Label>
            <Select value={stagingBinId} onValueChange={setStagingBinId}>
              <SelectTrigger id="pick-staging-bin">
                <SelectValue placeholder="Select a staging bin" />
              </SelectTrigger>
              <SelectContent>
                {stagingBins.map((bin) => (
                  <SelectItem key={bin.bin_id} value={String(bin.bin_id)}>
                    {bin.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
                Picking…
              </>
            ) : (
              'Confirm Pick'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
