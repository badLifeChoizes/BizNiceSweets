/**
 * PartSheet — create/edit form for PLUM parts.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, description, and mutation used
 *   part: PartRead | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Cancel
 *
 * Sections (Separator-divided):
 *   1. Identity       — Part Number (auto-prefilled on create), Description (required)
 *   2. Classification — Checkbox group over seeded tag vocabulary (zero-or-more, D-12)
 *   3. Revision seed  — "Reason for first revision" note (create mode only, optional)
 *
 * Mutations:
 *   Create: POST /api/v1/plum/parts — onSuccess invalidate ['plum','parts'], toast "Part created."
 *   Edit:   PATCH /api/v1/plum/parts/{id} — onSuccess invalidate ['plum','parts'], toast "Part saved."
 *
 * PartRead is the single exported TypeScript interface for the PLUM part entity.
 * It is consumed by PartsList and ArchivePartDialog.
 *
 * Accessibility: every input has a paired Label; Sheet has aria-labelledby + aria-describedby.
 */

import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
import { cn } from '@/lib/utils'

// ─── Types ───────────────────────────────────────────────────────────────────

/**
 * PartRead — TypeScript interface for the PLUM part entity.
 *
 * Single source of truth consumed by PartsList, PartSheet, and ArchivePartDialog.
 * Mirrors the backend PartRead Pydantic schema (05-01/05-02).
 */
export interface PartRead {
  id: string
  part_number: string
  active: boolean
  tags: string[]
  current_revision_label?: string | null
  current_revision_status?: string | null
  created_at: string
  updated_at: string
}

interface PartSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  part: PartRead | null
  onClose: () => void
}

// ─── Seeded tag vocabulary (D-12) ─────────────────────────────────────────────
// IDs match the database seed in backend/app/modules/plum/seed.py.
// The create body accepts tag_ids: number[].

const TAG_VOCABULARY = [
  { id: 1, name: 'Purchased' },
  { id: 2, name: 'Manufactured' },
  { id: 3, name: 'Assembly' },
  { id: 4, name: 'Finished Good' },
  { id: 5, name: 'Tool' },
  { id: 6, name: 'Raw Material' },
]

// ─── API error helper ─────────────────────────────────────────────────────────
// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 409 duplicate part number) or
// a 422 validation array of { loc, msg }. Map both to a readable message.
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

export function PartSheet({ open, mode, part, onClose }: PartSheetProps) {
  const queryClient = useQueryClient()

  // ── Form state ──
  const [formPartNumber, setFormPartNumber] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formTagIds, setFormTagIds] = useState<number[]>([])
  const [formReasonForRevision, setFormReasonForRevision] = useState('')

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    if (mode === 'create') {
      // Auto-prefill part number from server
      apiClient
        .get<{ part_number: string }>('/api/v1/plum/parts/next-number')
        .then((r) => setFormPartNumber(r.data.part_number))
        .catch(() => setFormPartNumber(''))
      setFormDescription('')
      setFormTagIds([])
      setFormReasonForRevision('')
    } else if (mode === 'edit' && part) {
      setFormPartNumber(part.part_number)
      setFormDescription('')   // description is revision-controlled; not in PartRead list response
      // Map tag names back to IDs for pre-selection
      const selectedIds = part.tags
        .map((name) => TAG_VOCABULARY.find((t) => t.name === name)?.id)
        .filter((id): id is number => id !== undefined)
      setFormTagIds(selectedIds)
      setFormReasonForRevision('')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, part])

  // ── Tag toggle handler ──
  function toggleTag(tagId: number) {
    setFormTagIds((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId],
    )
  }

  // ── Payload builder ──
  interface PartCreatePayload {
    part_number?: string
    description: string
    tag_ids: number[]
    reason_for_revision?: string
  }

  interface PartUpdatePayload {
    part_number?: string
    tag_ids?: number[]
  }

  function buildCreatePayload(): PartCreatePayload {
    return {
      part_number: formPartNumber || undefined,
      description: formDescription,
      tag_ids: formTagIds,
      reason_for_revision: formReasonForRevision || undefined,
    }
  }

  function buildUpdatePayload(): PartUpdatePayload {
    return {
      part_number: formPartNumber || undefined,
      tag_ids: formTagIds,
    }
  }

  // ── Mutations ──
  const createMutation = useMutation<PartRead, Error, PartCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<PartRead>('/api/v1/plum/parts', payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
      toast('Part created.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save part. Please try again.'))
    },
  })

  const updateMutation = useMutation<PartRead, Error, PartUpdatePayload>({
    mutationFn: (payload) =>
      apiClient
        .patch<PartRead>(`/api/v1/plum/parts/${part?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
      toast('Part saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save part. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  function handleSave() {
    if (mode === 'create') {
      if (!formDescription.trim()) {
        toast.error('Description is required.')
        return
      }
      createMutation.mutate(buildCreatePayload())
    } else {
      updateMutation.mutate(buildUpdatePayload())
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  // ── Sheet title / description ──
  const sheetTitle = mode === 'create' ? 'Create Part' : 'Edit Part'
  const sheetDescription =
    mode === 'create'
      ? 'Fill in the details to add a new part. A Draft revision will be created automatically.'
      : 'Update the part record. Changes to revision-controlled fields require a new revision.'

  // ── Render ──
  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        aria-labelledby="part-sheet-title"
        aria-describedby="part-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="part-sheet-title">{sheetTitle}</SheetTitle>
          <SheetDescription id="part-sheet-description">
            {sheetDescription}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          {/* ─── Section 1: Identity ─────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="part-number">Part Number</Label>
              <Input
                id="part-number"
                value={formPartNumber}
                onChange={(e) => setFormPartNumber(e.target.value)}
                placeholder="P00001"
              />
              {mode === 'create' && (
                <p className="text-xs text-muted-foreground">
                  System-generated. You may change it before saving.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="part-description">
                Description
                {mode === 'create' && (
                  <span className="text-destructive ml-1" aria-hidden="true">*</span>
                )}
              </Label>
              <Input
                id="part-description"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Short description of this part"
                required={mode === 'create'}
              />
            </div>
          </div>

          <Separator />

          {/* ─── Section 2: Classification ───────────────────────────────── */}
          <div className="space-y-4">
            <Label>Classification Tags</Label>
            <p className="text-xs text-muted-foreground -mt-2">
              Select zero or more categories that describe this part (D-12).
            </p>
            <div className="space-y-2">
              {TAG_VOCABULARY.map((tag) => (
                <div key={tag.id} className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id={`tag-${tag.id}`}
                    checked={formTagIds.includes(tag.id)}
                    onChange={() => toggleTag(tag.id)}
                    className="h-4 w-4 rounded border-input accent-primary"
                  />
                  <Label htmlFor={`tag-${tag.id}`} className="font-normal cursor-pointer">
                    {tag.name}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* ─── Section 3: Revision seed (create mode only) ─────────────── */}
          {mode === 'create' && (
            <>
              <Separator />
              <div className="space-y-4">
                <Label htmlFor="part-reason-for-revision">Reason for First Revision</Label>
                <p className="text-xs text-muted-foreground -mt-2">
                  Optional. Describe why this part is being created.
                </p>
                <textarea
                  id="part-reason-for-revision"
                  value={formReasonForRevision}
                  onChange={(e) => setFormReasonForRevision(e.target.value)}
                  placeholder="Initial design for project X…"
                  rows={3}
                  className={cn(
                    'flex w-full rounded-md border border-input bg-transparent px-3 py-2',
                    'text-base shadow-sm placeholder:text-muted-foreground',
                    'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                />
              </div>
            </>
          )}
        </div>

        <SheetFooter className={cn('flex gap-2 pt-4')}>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            variant="default"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Saving…
              </>
            ) : (
              'Save Part'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
