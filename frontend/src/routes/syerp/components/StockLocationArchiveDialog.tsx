// ABOUTME: Destructive confirmation dialog for archiving a SYERP stock location.
// ABOUTME: Fires PATCH /syerp/inventory/locations/{id} {active:false} and invalidates
// ABOUTME: the location list query. Cloned from ItemArchiveDialog (Phase 8, Task 10).

/**
 * StockLocationArchiveDialog — destructive confirmation dialog for archiving a location.
 *
 * Props:
 *   open: boolean
 *   location: StockLocationRead | null — the location to archive (body copy uses location.name)
 *   onClose: () => void — called on confirm success or cancel
 *
 * Confirm fires PATCH /api/v1/syerp/inventory/locations/{id} with { active: false }.
 * On success: invalidates ['syerp','inventory','locations'], toasts "Location archived.".
 *
 * Accessibility: aria-labelledby + aria-describedby; confirm button has aria-label="Archive {name}".
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { apiClient } from '@/api/client'
import type { StockLocationRead } from './StockLocationSheet'

// ─── Props ────────────────────────────────────────────────────────────────────

interface StockLocationArchiveDialogProps {
  open: boolean
  location: StockLocationRead | null
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function StockLocationArchiveDialog({
  open,
  location,
  onClose,
}: StockLocationArchiveDialogProps) {
  const queryClient = useQueryClient()

  const archiveMutation = useMutation<StockLocationRead, Error, number>({
    mutationFn: (locationId) =>
      apiClient
        .patch<StockLocationRead>(`/api/v1/syerp/inventory/locations/${locationId}`, {
          active: false,
        })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'locations'] })
      toast('Location archived.')
      onClose()
    },
    onError: () => {
      toast.error('Failed to archive location. Please try again.')
    },
  })

  function handleConfirm() {
    if (location) {
      archiveMutation.mutate(location.id)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isArchiving = archiveMutation.isPending

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="location-archive-dialog-title"
        aria-describedby="location-archive-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="location-archive-dialog-title">Archive location?</DialogTitle>
          <DialogDescription id="location-archive-dialog-description">
            {location
              ? `${location.name} will be hidden from the locations list. Existing references are preserved and can be restored at any time.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isArchiving}>
            Keep Location
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isArchiving}
            aria-label={location ? `Archive ${location.name}` : 'Archive location'}
          >
            {isArchiving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Archiving…
              </>
            ) : (
              'Archive Location'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
