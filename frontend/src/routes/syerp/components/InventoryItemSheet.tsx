// ABOUTME: Create/edit Sheet form for a SYERP inventory item (name, code, UoM,
// ABOUTME: optional PLUM part link). The part-link Select degrades gracefully to a
// ABOUTME: standalone "No linked part" option when PLUM is disabled (Phase 8, Task 9).

/**
 * InventoryItemSheet — shared create/edit form for SYERP inventory items.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, description, and mutation used
 *   item: InventoryItemRead | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Discard
 *
 * Fields:
 *   1. Name              — required
 *   2. Code              — optional; server auto-generates ITEM-#### when blank
 *   3. Unit of measure   — required (e.g. ea, kg, m)
 *   4. Linked PLUM part  — OPTIONAL. Populated from GET /api/v1/plum/parts.
 *                          Stays fully usable when that list is empty or errors
 *                          (PLUM module disabled — D-P8-2): the "No linked part"
 *                          option is always present and selected by default.
 *
 * Mutations:
 *   Create: POST /api/v1/syerp/inventory/items — invalidate ['syerp','inventory','items']
 *   Edit:   PATCH /api/v1/syerp/inventory/items/{id} — invalidate ['syerp','inventory','items']
 *
 * Accessibility: every input has a paired Label; Sheet has aria-labelledby + aria-describedby.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/api/client'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface InventoryItemRead {
  id: string
  code: string
  name: string
  unit_of_measure: string
  plum_part_id?: string | null
  moving_avg_cost: string
  active: boolean
  created_at: string
  updated_at: string
}

interface InventoryItemSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  item: InventoryItemRead | null
  onClose: () => void
}

// PLUM part option — the only fields we need to render a link choice.
interface PartOption {
  id: string
  part_number: string
}

// Sentinel value for "no linked part". Radix Select disallows an empty-string
// item value, so we use an explicit token and map it back to undefined on save.
const NO_PART = '__none__'

// ─── API helpers ─────────────────────────────────────────────────────────────

// Fetch the PLUM parts list to populate the optional link Select. When PLUM is
// disabled the route 404s / errors — the query's error is swallowed here and the
// Select falls back to just the "No linked part" option (never blocks the form).
function fetchPartOptions(): Promise<PartOption[]> {
  return apiClient
    .get<PartOption[]>('/api/v1/plum/parts')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 409 duplicate code) or a
// 422 validation array of { loc, msg }. Map both to a readable, actionable message.
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

export function InventoryItemSheet({ open, mode, item, onClose }: InventoryItemSheetProps) {
  const queryClient = useQueryClient()

  // ── PLUM part options (optional link) ──
  // retry:false so a disabled PLUM module fails fast; errors are non-blocking —
  // we default the list to [] and keep the Select usable regardless.
  const { data: partOptions = [] } = useQuery<PartOption[], Error>({
    queryKey: ['plum', 'parts', 'link-options'],
    queryFn: fetchPartOptions,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })

  // ── Form state ──
  const [formName, setFormName] = useState('')
  const [formCode, setFormCode] = useState('')
  const [formUnitOfMeasure, setFormUnitOfMeasure] = useState('')
  const [formPlumPartId, setFormPlumPartId] = useState<string>(NO_PART)

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    if (mode === 'create') {
      setFormName('')
      setFormCode('')
      setFormUnitOfMeasure('')
      setFormPlumPartId(NO_PART)
    } else if (mode === 'edit' && item) {
      setFormName(item.name)
      setFormCode(item.code)
      setFormUnitOfMeasure(item.unit_of_measure)
      setFormPlumPartId(item.plum_part_id ?? NO_PART)
    }
  }, [open, mode, item])

  // ── Validation ──
  const nameError = !formName.trim()
  const unitError = !formUnitOfMeasure.trim()
  const formInvalid = nameError || unitError

  // If the item is linked to a part that isn't in the fetched options (e.g. PLUM
  // disabled), keep the current selection visible so editing doesn't silently
  // drop the existing link.
  const linkedPartMissing =
    formPlumPartId !== NO_PART && !partOptions.some((p) => p.id === formPlumPartId)

  // ── Mutations ──
  interface ItemPayload {
    name: string
    code?: string
    unit_of_measure: string
    plum_part_id?: string
  }

  function buildPayload(): ItemPayload {
    return {
      name: formName.trim(),
      code: formCode.trim() || undefined,
      unit_of_measure: formUnitOfMeasure.trim(),
      plum_part_id: formPlumPartId === NO_PART ? undefined : formPlumPartId,
    }
  }

  const createMutation = useMutation<InventoryItemRead, Error, ItemPayload>({
    mutationFn: (payload) =>
      apiClient
        .post<InventoryItemRead>('/api/v1/syerp/inventory/items', payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'items'] })
      toast('Item saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save item. Please try again.'))
    },
  })

  const updateMutation = useMutation<InventoryItemRead, Error, ItemPayload>({
    mutationFn: (payload) =>
      apiClient
        .patch<InventoryItemRead>(`/api/v1/syerp/inventory/items/${item?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'items'] })
      toast('Item saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save item. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  function handleSave() {
    if (formInvalid) return
    const payload = buildPayload()
    if (mode === 'create') {
      createMutation.mutate(payload)
    } else {
      updateMutation.mutate(payload)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  // ── Render ──
  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        aria-labelledby="item-sheet-title"
        aria-describedby="item-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="item-sheet-title">
            {mode === 'edit' ? 'Edit Item' : 'Create Item'}
          </SheetTitle>
          <SheetDescription id="item-sheet-description">
            {mode === 'edit'
              ? 'Update the inventory item. Changes are audited.'
              : 'Fill in the details to add a new inventory item.'}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          <div className="space-y-4">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="item-name">Name</Label>
              <Input
                id="item-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="M3 hex bolt"
              />
              {nameError && <p className="text-sm text-destructive">Name is required.</p>}
            </div>

            {/* Code */}
            <div className="space-y-2">
              <Label htmlFor="item-code">Code</Label>
              <Input
                id="item-code"
                value={formCode}
                onChange={(e) => setFormCode(e.target.value)}
                placeholder="ITEM-0001"
              />
              <p className="text-xs text-muted-foreground">
                Optional — leave blank to auto-generate an ITEM-#### code.
              </p>
            </div>

            {/* Unit of measure */}
            <div className="space-y-2">
              <Label htmlFor="item-uom">Unit of measure</Label>
              <Input
                id="item-uom"
                value={formUnitOfMeasure}
                onChange={(e) => setFormUnitOfMeasure(e.target.value)}
                placeholder="ea"
              />
              {unitError && (
                <p className="text-sm text-destructive">Unit of measure is required.</p>
              )}
            </div>

            {/* Optional PLUM part link */}
            <div className="space-y-2">
              <Label htmlFor="item-plum-part">Linked PLUM part</Label>
              <Select value={formPlumPartId} onValueChange={setFormPlumPartId}>
                <SelectTrigger id="item-plum-part">
                  <SelectValue placeholder="No linked part" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PART}>No linked part</SelectItem>
                  {/* Preserve an existing link even when PLUM's list is unavailable */}
                  {linkedPartMissing && (
                    <SelectItem value={formPlumPartId}>
                      Linked part ({formPlumPartId})
                    </SelectItem>
                  )}
                  {partOptions.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.part_number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Optional — link this stock item to a PLUM part, or leave unlinked.
              </p>
            </div>
          </div>
        </div>

        <SheetFooter className="flex gap-2 pt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Discard Changes
          </Button>
          <Button variant="default" onClick={handleSave} disabled={isSaving || formInvalid}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Saving…
              </>
            ) : (
              'Save Item'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
