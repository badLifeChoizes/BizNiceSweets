// ABOUTME: Create/edit Sheet form for a SYERP stock location. A location is just
// ABOUTME: a unique name (active is handled by archive/restore), so this is the
// ABOUTME: simplest name-only clone of InventoryItemSheet (Phase 8, Task 10).

/**
 * StockLocationSheet — shared create/edit form for SYERP stock locations.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, description, and mutation used
 *   location: StockLocationRead | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Discard
 *
 * Fields:
 *   1. Name — required, unique (backend returns 409 on duplicate → toast.error)
 *
 * Mutations:
 *   Create: POST /api/v1/syerp/inventory/locations — invalidate ['syerp','inventory','locations']
 *   Edit:   PATCH /api/v1/syerp/inventory/locations/{id} — invalidate ['syerp','inventory','locations']
 *
 * Accessibility: input has a paired Label; Sheet has aria-labelledby + aria-describedby.
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
import { apiClient } from '@/api/client'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface StockLocationRead {
  id: number
  name: string
  active: boolean
  created_at: string
  updated_at: string
}

interface StockLocationSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  location: StockLocationRead | null
  onClose: () => void
}

// ─── API helpers ─────────────────────────────────────────────────────────────

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 409 duplicate name) or a
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

export function StockLocationSheet({ open, mode, location, onClose }: StockLocationSheetProps) {
  const queryClient = useQueryClient()

  // ── Form state ──
  const [formName, setFormName] = useState('')

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    if (mode === 'create') {
      setFormName('')
    } else if (mode === 'edit' && location) {
      setFormName(location.name)
    }
  }, [open, mode, location])

  // ── Validation ──
  const nameError = !formName.trim()
  const formInvalid = nameError

  // ── Mutations ──
  interface LocationPayload {
    name: string
  }

  function buildPayload(): LocationPayload {
    return { name: formName.trim() }
  }

  const createMutation = useMutation<StockLocationRead, Error, LocationPayload>({
    mutationFn: (payload) =>
      apiClient
        .post<StockLocationRead>('/api/v1/syerp/inventory/locations', payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'locations'] })
      toast('Location saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save location. Please try again.'))
    },
  })

  const updateMutation = useMutation<StockLocationRead, Error, LocationPayload>({
    mutationFn: (payload) =>
      apiClient
        .patch<StockLocationRead>(`/api/v1/syerp/inventory/locations/${location?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'locations'] })
      toast('Location saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save location. Please try again.'))
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
        aria-labelledby="location-sheet-title"
        aria-describedby="location-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="location-sheet-title">
            {mode === 'edit' ? 'Edit Location' : 'Create Location'}
          </SheetTitle>
          <SheetDescription id="location-sheet-description">
            {mode === 'edit'
              ? 'Update the stock location. Changes are audited.'
              : 'Fill in the details to add a new stock location.'}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          <div className="space-y-4">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="location-name">Name</Label>
              <Input
                id="location-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Main"
              />
              {nameError && <p className="text-sm text-destructive">Name is required.</p>}
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
              'Save Location'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
