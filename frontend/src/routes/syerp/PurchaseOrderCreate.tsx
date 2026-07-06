// ABOUTME: SYERP Purchase Order create/draft-edit screen (/syerp/purchasing/orders/new)
// ABOUTME: — vendor picker + line editor (item, qty, unit cost, need-by). Creates a Draft
// ABOUTME: PO then POSTs each line; line edits are Draft-only (AC11-1, vendor-only AC11-3).

/**
 * PurchaseOrderCreate screen — build a Draft purchase order (/syerp/purchasing/orders/new).
 *
 * Layout: p-8 space-y-6 (matches PurchaseOrders/InventoryItems pattern).
 *
 * Vendor picker:
 *   Required Select populated from GET /api/v1/syerp/partners?role=vendor (vendor-only,
 *   AC11-3). Uses the __none__ sentinel for the unselected default (Radix forbids "").
 *
 * Line editor:
 *   An editable list of rows, each: item Select (GET /api/v1/syerp/inventory/items,
 *   active only), qty ordered, unit cost, and an optional need-by date. Add-row /
 *   remove-row controls. Decimal values are kept as STRINGS and sent verbatim — never
 *   coerced to float (D-11). Editing lines is only meaningful while the PO is Draft
 *   (AC11-1); this screen only ever creates a fresh Draft.
 *
 * Submit flow (two-phase — the backend adds lines to an existing Draft):
 *   1. POST /api/v1/syerp/purchasing/orders { vendor_id, notes? } → new Draft PORead.
 *   2. For each non-empty line, POST /orders/{id}/lines { item_id, qty_ordered,
 *      unit_cost, need_by_date? }.
 *   On success → toast.success + navigate to /syerp/purchasing/orders/{id} (Task 22).
 *   If a line POST fails, the PO already exists as Draft — surface the server reason
 *   via toast.error and navigate to the PO so the user can fix the remaining lines
 *   there (no rollback of the created header).
 *
 * Accessibility: every field has a paired Label; rows carry an index-scoped aria-label.
 */

import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'
import type { PartnerRead } from './components/PartnerSheet'
import type { PORead } from './PurchaseOrders'
import type { InventoryItemRead } from './components/InventoryItemSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

/** A single editable draft line before it is POSTed to the PO. */
interface DraftLine {
  key: number
  itemId: string
  qtyOrdered: string
  unitCost: string
  needByDate: string
}

/** Payload for POST /orders/{id}/lines — Decimals travel as exact strings. */
interface LinePayload {
  item_id: string
  qty_ordered: string
  unit_cost: string
  need_by_date?: string
}

// Sentinel for the unselected vendor / item option — Radix Select forbids an
// empty-string value, so an explicit token stands in for "nothing chosen".
const NONE = '__none__'

let nextLineKey = 1

function makeLine(): DraftLine {
  return { key: nextLineKey++, itemId: NONE, qtyOrdered: '', unitCost: '', needByDate: '' }
}

// ─── API helpers ─────────────────────────────────────────────────────────────

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

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` or a 422 validation array of
// { loc, msg }. Map both to a readable, actionable message.
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

export function PurchaseOrderCreate() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Form state ──
  const [vendorId, setVendorId] = useState<string>(NONE)
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<DraftLine[]>(() => [makeLine()])

  // ── Data ──
  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
  })

  const { data: items = [] } = useQuery<InventoryItemRead[], Error>({
    queryKey: ['syerp', 'inventory', 'items'],
    queryFn: fetchItems,
  })
  const activeItems = items.filter((i) => i.active)

  // ── Line editing helpers ──
  function updateLine(key: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function addLine() {
    setLines((prev) => [...prev, makeLine()])
  }

  function removeLine(key: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((l) => l.key !== key) : prev))
  }

  // A line counts once an item is chosen; empty extra rows are skipped on submit.
  function lineIsFilled(l: DraftLine): boolean {
    return l.itemId !== NONE
  }

  function lineIsValid(l: DraftLine): boolean {
    const qty = Number(l.qtyOrdered)
    const cost = Number(l.unitCost)
    return (
      l.itemId !== NONE &&
      l.qtyOrdered.trim() !== '' &&
      Number.isFinite(qty) &&
      qty > 0 &&
      l.unitCost.trim() !== '' &&
      Number.isFinite(cost) &&
      cost >= 0
    )
  }

  // ── Validation ──
  const vendorInvalid = vendorId === NONE
  const filledLines = lines.filter(lineIsFilled)
  const hasLine = filledLines.length > 0
  const allFilledValid = filledLines.every(lineIsValid)
  const formInvalid = vendorInvalid || !hasLine || !allFilledValid

  // Holds the id of a Draft header that was created before a line POST failed, so
  // onError can route the user to it (the header is not rolled back).
  const createdIdRef = useRef<string | null>(null)

  // ── Submit: create the Draft header, then POST each filled line ──
  const createMutation = useMutation<PORead, Error, void>({
    mutationFn: async () => {
      createdIdRef.current = null
      // 1. Create the Draft PO header (empty lines).
      const po = await apiClient
        .post<PORead>('/api/v1/syerp/purchasing/orders', {
          vendor_id: vendorId,
          notes: notes.trim() || undefined,
        })
        .then((r) => r.data)
      createdIdRef.current = po.id

      // 2. Add each filled line to the freshly-created Draft. Sent sequentially so
      //    a mid-line failure names the offending row and the rest can be retried
      //    against the already-persisted Draft.
      for (const l of filledLines) {
        const payload: LinePayload = {
          item_id: l.itemId,
          qty_ordered: l.qtyOrdered.trim(),
          unit_cost: l.unitCost.trim(),
          need_by_date: l.needByDate.trim() || undefined,
        }
        await apiClient.post(`/api/v1/syerp/purchasing/orders/${po.id}/lines`, payload)
      }
      return po
    },
    onSuccess: (po) => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'purchasing', 'orders'] })
      toast.success('Purchase order created.')
      navigate(`/syerp/purchasing/orders/${po.id}`)
    },
    onError: (err) => {
      // The header may already exist as a Draft (a line POST failed). Surface the
      // server reason and route to the PO — if we know its id — so the user can fix
      // the remaining lines there rather than losing the Draft (no rollback).
      toast.error(getApiErrorMessage(err, 'Failed to create purchase order. Please try again.'))
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'purchasing', 'orders'] })
      if (createdIdRef.current) navigate(`/syerp/purchasing/orders/${createdIdRef.current}`)
    },
  })

  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    createMutation.mutate()
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Create Purchase Order</h1>
        <p className="text-base font-normal text-muted-foreground">
          Choose a vendor and add order lines. The order is created as a Draft you can
          continue to edit.
        </p>
      </div>

      {/* Vendor + notes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Vendor</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="po-vendor">Vendor</Label>
            <Select value={vendorId} onValueChange={setVendorId}>
              <SelectTrigger id="po-vendor" className="w-full max-w-md" aria-label="Vendor">
                <SelectValue placeholder="Select a vendor" />
              </SelectTrigger>
              <SelectContent>
                {vendors.map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    {v.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {vendorInvalid && <p className="text-sm text-destructive">Select a vendor.</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="po-notes">Notes</Label>
            <Input
              id="po-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional — order notes"
            />
          </div>
        </CardContent>
      </Card>

      {/* Line editor */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Order Lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {lines.map((line, idx) => (
            <div
              key={line.key}
              className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_8rem_8rem_10rem_auto] md:items-end"
              aria-label={`Order line ${idx + 1}`}
            >
              {/* Item */}
              <div className="space-y-2">
                <Label htmlFor={`line-item-${line.key}`}>Item</Label>
                <Select
                  value={line.itemId}
                  onValueChange={(v) => updateLine(line.key, { itemId: v })}
                >
                  <SelectTrigger
                    id={`line-item-${line.key}`}
                    aria-label={`Item for line ${idx + 1}`}
                  >
                    <SelectValue placeholder="Select an item" />
                  </SelectTrigger>
                  <SelectContent>
                    {activeItems.map((i) => (
                      <SelectItem key={i.id} value={i.id}>
                        {i.code} — {i.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Qty ordered */}
              <div className="space-y-2">
                <Label htmlFor={`line-qty-${line.key}`}>Qty</Label>
                <Input
                  id={`line-qty-${line.key}`}
                  inputMode="decimal"
                  value={line.qtyOrdered}
                  onChange={(e) => updateLine(line.key, { qtyOrdered: e.target.value })}
                  placeholder="e.g. 10"
                />
              </div>

              {/* Unit cost */}
              <div className="space-y-2">
                <Label htmlFor={`line-cost-${line.key}`}>Unit cost</Label>
                <Input
                  id={`line-cost-${line.key}`}
                  inputMode="decimal"
                  value={line.unitCost}
                  onChange={(e) => updateLine(line.key, { unitCost: e.target.value })}
                  placeholder="e.g. 2.50"
                />
              </div>

              {/* Need-by date (optional) */}
              <div className="space-y-2">
                <Label htmlFor={`line-needby-${line.key}`}>Need by</Label>
                <Input
                  id={`line-needby-${line.key}`}
                  type="date"
                  value={line.needByDate}
                  onChange={(e) => updateLine(line.key, { needByDate: e.target.value })}
                />
              </div>

              {/* Remove row */}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeLine(line.key)}
                disabled={lines.length === 1}
                aria-label={`Remove line ${idx + 1}`}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          ))}

          <Button type="button" variant="outline" size="sm" onClick={addLine}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add line
          </Button>

          {!hasLine && (
            <p className="text-sm text-destructive">Add at least one order line.</p>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() => navigate('/syerp/purchasing/orders')}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button variant="default" onClick={handleSubmit} disabled={isSaving || formInvalid}>
          {isSaving ? (
            <>
              <Loader2 className="animate-spin" aria-hidden="true" />
              Creating…
            </>
          ) : (
            'Create Draft PO'
          )}
        </Button>
      </div>
    </div>
  )
}
