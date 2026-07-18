// ABOUTME: Create/edit Sheet form for a GELATO bin (a subdivision of a SYERP stock
// ABOUTME: location). Code is set at create time (immutable after); description is
// ABOUTME: editable in both modes. Server 4xx (dup code / bad location) → toast.error.

/**
 * BinSheet — shared create/edit form for GELATO bins.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, fields, and mutation used
 *   locationId: number — the location the bin belongs to (used for create)
 *   bin: Bin | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Discard
 *
 * Fields:
 *   1. Code        — required, unique within the location (create only; immutable
 *                    after — the backend BinUpdate has no code). Read-only in edit.
 *   2. Description — optional free text (editable in both modes).
 *
 * Mutations (from ../hooks):
 *   Create: useCreateBin  → POST /api/v1/gelato/bins
 *   Edit:   useUpdateBin  → PATCH /api/v1/gelato/bins/{id}
 * Both invalidate the location's bins query on success. A 4xx (duplicate code,
 * unknown/archived location) surfaces its server `detail` via toast.error.
 *
 * Accessibility: each input has a paired Label; Sheet has aria-labelledby +
 * aria-describedby.
 */

import { useState, useEffect } from 'react'
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
import { useCreateBin, useUpdateBin } from '../hooks'
import type { Bin } from '../hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface BinSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  locationId: number
  bin: Bin | null
  onClose: () => void
}

// ─── API error helper ────────────────────────────────────────────────────────

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 409 duplicate code) or a 422
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

export function BinSheet({ open, mode, locationId, bin, onClose }: BinSheetProps) {
  const createBin = useCreateBin()
  const updateBin = useUpdateBin()

  // ── Form state ──
  const [formCode, setFormCode] = useState('')
  const [formDescription, setFormDescription] = useState('')

  // ── Populate form when the sheet opens ──
  useEffect(() => {
    if (!open) return

    if (mode === 'create') {
      setFormCode('')
      setFormDescription('')
    } else if (mode === 'edit' && bin) {
      setFormCode(bin.code)
      setFormDescription(bin.description ?? '')
    }
  }, [open, mode, bin])

  // ── Validation ──
  const codeError = !formCode.trim()
  const formInvalid = mode === 'create' && codeError

  const isSaving = createBin.isPending || updateBin.isPending

  function handleSave() {
    if (formInvalid) return
    const description = formDescription.trim() || null

    if (mode === 'create') {
      createBin.mutate(
        { location_id: locationId, code: formCode.trim(), description },
        {
          onSuccess: () => {
            toast('Bin saved.')
            onClose()
          },
          onError: (err) => {
            toast.error(getApiErrorMessage(err, 'Failed to save bin. Please try again.'))
          },
        },
      )
    } else if (bin) {
      updateBin.mutate(
        { id: bin.id, patch: { description } },
        {
          onSuccess: () => {
            toast('Bin saved.')
            onClose()
          },
          onError: (err) => {
            toast.error(getApiErrorMessage(err, 'Failed to save bin. Please try again.'))
          },
        },
      )
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
        aria-labelledby="bin-sheet-title"
        aria-describedby="bin-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="bin-sheet-title">
            {mode === 'edit' ? 'Edit Bin' : 'Create Bin'}
          </SheetTitle>
          <SheetDescription id="bin-sheet-description">
            {mode === 'edit'
              ? 'Update the bin. Its code is fixed once created.'
              : 'Fill in the details to add a new bin to this location.'}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          <div className="space-y-4">
            {/* Code */}
            <div className="space-y-2">
              <Label htmlFor="bin-code">Code</Label>
              <Input
                id="bin-code"
                value={formCode}
                onChange={(e) => setFormCode(e.target.value)}
                placeholder="A-01-01"
                disabled={mode === 'edit'}
              />
              {mode === 'create' && codeError && (
                <p className="text-sm text-destructive">Code is required.</p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="bin-description">Description</Label>
              <Input
                id="bin-description"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Optional"
              />
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
              'Save Bin'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
