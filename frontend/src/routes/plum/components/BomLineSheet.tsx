/**
 * BomLineSheet — create/edit form for BOM lines.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, description, and mutation used
 *   partId: string — parent part ID
 *   revisionId: string — parent revision ID (included in POST body)
 *   existingLine?: BomLineRead | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Discard
 *
 * Fields:
 *   1. Child Part — server-side search combobox (debounced 300ms)
 *   2. Quantity — type=number step=0.001 min=0.001 (decimal supported)
 *   3. Unit of Measure — read-only display of child part's UoM
 *   4. Reference Designators — optional comma-separated input
 *
 * Mutations:
 *   Create: POST /api/v1/plum/parts/{partId}/bom
 *   Edit:   PATCH /api/v1/plum/parts/{partId}/bom/{lineId}
 *   onSuccess: invalidate ['plum','parts',partId], toast
 *   onError: getApiErrorMessage; 422 cycle detected surfaced inline below Child Part
 *
 * Accessibility: every input has a paired Label; Sheet has aria-labelledby + aria-describedby.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
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
import { Separator } from '@/components/ui/separator'
import { apiClient } from '@/api/client'

// ─── Types ───────────────────────────────────────────────────────────────────

interface PartSearchResult {
  id: string
  part_number: string
  current_revision_label?: string | null
  current_revision_status?: string | null
  description?: string | null
  unit_of_measure?: string | null
  tags?: string[]
}

export interface BomLineRead {
  id: string
  child_part_id: string
  child_part_number?: string
  qty: number | string
  ref_des?: string | null
  unit_of_measure?: string | null
}

interface BomLineSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  partId: string
  revisionId: string
  existingLine?: BomLineRead | null
  onClose: () => void
}

// ─── API error helper ─────────────────────────────────────────────────────────
// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 cycle) or a 422 validation
// array of { loc, msg }. Map both to a readable message.
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

// ─── Helper: is this a cycle 422? ────────────────────────────────────────────
function extractCycleError(err: unknown): string | null {
  if (axios.isAxiosError(err) && err.response?.status === 422) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.toLowerCase().includes('circular')) {
      return detail
    }
    if (typeof detail === 'string' && detail.toLowerCase().includes('cycle')) {
      return detail
    }
  }
  return null
}

// ─── Main component ──────────────────────────────────────────────────────────

export function BomLineSheet({
  open,
  mode,
  partId,
  revisionId,
  existingLine,
  onClose,
}: BomLineSheetProps) {
  const queryClient = useQueryClient()

  // ── Form state ──
  const [formChildPartId, setFormChildPartId] = useState('')
  const [formChildPartNumber, setFormChildPartNumber] = useState('')
  const [formChildUoM, setFormChildUoM] = useState('')
  const [formQty, setFormQty] = useState('1')
  const [formRefDes, setFormRefDes] = useState('')
  const [cycleError, setCycleError] = useState<string | null>(null)

  // ── Combobox / search state ──
  const [searchQuery, setSearchQuery] = useState('')
  const [showResults, setShowResults] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedQuery, setDebouncedQuery] = useState('')

  // ── Debounced search ──
  const handleSearchInput = useCallback((value: string) => {
    setSearchQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(value)
      setShowResults(true)
    }, 300)
  }, [])

  // ── Part search query ──
  const { data: searchResults = [] } = useQuery<PartSearchResult[], Error>({
    queryKey: ['plum', 'parts', 'search', debouncedQuery],
    queryFn: () =>
      apiClient
        .get<PartSearchResult[]>('/api/v1/plum/parts', { params: { q: debouncedQuery } })
        .then((r) => r.data),
    enabled: !!debouncedQuery && debouncedQuery.length >= 1,
  })

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    setCycleError(null)
    setShowResults(false)
    setSearchQuery('')
    setDebouncedQuery('')

    if (mode === 'create') {
      setFormChildPartId('')
      setFormChildPartNumber('')
      setFormChildUoM('')
      setFormQty('1')
      setFormRefDes('')
    } else if (mode === 'edit' && existingLine) {
      setFormChildPartId(existingLine.child_part_id)
      setFormChildPartNumber(existingLine.child_part_number ?? '')
      setFormChildUoM(existingLine.unit_of_measure ?? '')
      setFormQty(String(existingLine.qty))
      setFormRefDes(existingLine.ref_des ?? '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, existingLine])

  // ── Select a part from search results ──
  function selectPart(part: PartSearchResult) {
    setFormChildPartId(part.id)
    setFormChildPartNumber(part.part_number)
    setFormChildUoM(part.unit_of_measure ?? '')
    setSearchQuery(part.part_number)
    setShowResults(false)
    setCycleError(null)
  }

  // ── Mutations ──
  interface BomCreatePayload {
    child_part_id: string
    qty: number
    ref_des?: string
    revision_id: string
  }

  interface BomUpdatePayload {
    qty?: number
    ref_des?: string
  }

  const createMutation = useMutation<unknown, Error, BomCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post(`/api/v1/plum/parts/${partId}/bom`, payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast('Part added to BOM.')
      onClose()
    },
    onError: (err) => {
      const cycle = extractCycleError(err)
      if (cycle) {
        setCycleError(
          `Adding ${formChildPartNumber} here would create a circular BOM. Choose a different part.`,
        )
      } else {
        toast.error(getApiErrorMessage(err, 'Failed to save BOM line. Please try again.'))
      }
    },
  })

  const editMutation = useMutation<unknown, Error, BomUpdatePayload>({
    mutationFn: (payload) =>
      apiClient
        .patch(`/api/v1/plum/parts/${partId}/bom/${existingLine?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast('BOM line updated.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save BOM line. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending || editMutation.isPending

  function handleSave() {
    const qty = parseFloat(formQty)
    if (!formChildPartId) {
      toast.error('Child part is required.')
      return
    }
    if (isNaN(qty) || qty <= 0) {
      toast.error('Quantity must be a positive number.')
      return
    }
    setCycleError(null)
    if (mode === 'create') {
      createMutation.mutate({
        child_part_id: formChildPartId,
        qty,
        ref_des: formRefDes || undefined,
        revision_id: revisionId,
      })
    } else {
      editMutation.mutate({
        qty,
        ref_des: formRefDes || undefined,
      })
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const sheetTitle = mode === 'create' ? 'Add Part to BOM' : 'Edit BOM Line'
  const sheetDescription =
    mode === 'create'
      ? 'Search for a child part and set the quantity and reference designators.'
      : 'Update the quantity or reference designators for this BOM line.'

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        aria-labelledby="bom-line-sheet-title"
        aria-describedby="bom-line-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="bom-line-sheet-title">{sheetTitle}</SheetTitle>
          <SheetDescription id="bom-line-sheet-description">
            {sheetDescription}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          {/* ─── Section 1: Child Part ───────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="bom-child-part">
                Child Part
                <span className="text-destructive ml-1" aria-hidden="true">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="bom-child-part"
                  value={searchQuery || (mode === 'edit' ? formChildPartNumber : searchQuery)}
                  onChange={(e) => {
                    if (mode === 'create') {
                      handleSearchInput(e.target.value)
                      if (formChildPartId) {
                        setFormChildPartId('')
                        setFormChildPartNumber('')
                        setFormChildUoM('')
                      }
                    }
                  }}
                  onFocus={() => {
                    if (debouncedQuery && searchResults.length > 0) setShowResults(true)
                  }}
                  placeholder="Search by part number or description…"
                  disabled={mode === 'edit'}
                  autoComplete="off"
                />
                {showResults && searchResults.length > 0 && mode === 'create' && (
                  <div className="absolute z-10 w-full mt-1 bg-popover border border-border rounded-md shadow-md max-h-48 overflow-y-auto">
                    {searchResults.map((part) => (
                      <button
                        key={part.id}
                        type="button"
                        className="w-full px-3 py-2 text-left hover:bg-muted flex flex-col"
                        onClick={() => selectPart(part)}
                      >
                        <span className="font-medium text-sm text-foreground">
                          {part.part_number}
                        </span>
                        {part.description && (
                          <span className="text-xs text-muted-foreground">{part.description}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {/* Inline cycle error */}
              {cycleError && (
                <p className="text-sm text-destructive" role="alert">
                  {cycleError}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="bom-qty">
                Quantity
                <span className="text-destructive ml-1" aria-hidden="true">*</span>
              </Label>
              <Input
                id="bom-qty"
                type="number"
                step="0.001"
                min="0.001"
                value={formQty}
                onChange={(e) => setFormQty(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                Decimal quantities are supported (e.g. 0.5, 2.3).
              </p>
            </div>

            {formChildUoM && (
              <div className="space-y-1">
                <Label>Unit of Measure</Label>
                <p className="text-sm text-muted-foreground">{formChildUoM}</p>
              </div>
            )}
          </div>

          <Separator />

          {/* ─── Section 2: Reference Designators ──────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="bom-ref-des">Reference Designators</Label>
              <Input
                id="bom-ref-des"
                value={formRefDes}
                onChange={(e) => setFormRefDes(e.target.value)}
                placeholder="e.g. R1, C4, U7"
              />
              <p className="text-xs text-muted-foreground">
                Optional. Comma-separated designator identifiers.
              </p>
            </div>
          </div>
        </div>

        <SheetFooter className="flex gap-2 pt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Discard Line
          </Button>
          <Button variant="default" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Saving…
              </>
            ) : (
              'Save Line'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
