// ABOUTME: Destructive confirmation dialog for archiving a SYERP inventory item.
// ABOUTME: Fires PATCH /syerp/inventory/items/{id} {active:false} and invalidates
// ABOUTME: the item list query. Cloned from PartnerArchiveDialog (Phase 8, Task 9).

/**
 * ItemArchiveDialog — destructive confirmation dialog for archiving an inventory item.
 *
 * Props:
 *   open: boolean
 *   item: InventoryItemRead | null — the item to archive (body copy uses item.name)
 *   onClose: () => void — called on confirm success or cancel
 *
 * Confirm fires PATCH /api/v1/syerp/inventory/items/{id} with { active: false }.
 * On success: invalidates ['syerp','inventory','items'], toasts "Item archived.".
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
import type { InventoryItemRead } from './InventoryItemSheet'

// ─── Props ────────────────────────────────────────────────────────────────────

interface ItemArchiveDialogProps {
  open: boolean
  item: InventoryItemRead | null
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ItemArchiveDialog({ open, item, onClose }: ItemArchiveDialogProps) {
  const queryClient = useQueryClient()

  const archiveMutation = useMutation<InventoryItemRead, Error, string>({
    mutationFn: (itemId) =>
      apiClient
        .patch<InventoryItemRead>(`/api/v1/syerp/inventory/items/${itemId}`, { active: false })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'items'] })
      toast('Item archived.')
      onClose()
    },
    onError: () => {
      toast.error('Failed to archive item. Please try again.')
    },
  })

  function handleConfirm() {
    if (item) {
      archiveMutation.mutate(item.id)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isArchiving = archiveMutation.isPending

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="item-archive-dialog-title"
        aria-describedby="item-archive-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="item-archive-dialog-title">Archive item?</DialogTitle>
          <DialogDescription id="item-archive-dialog-description">
            {item
              ? `${item.name} will be hidden from the items list. Existing references are preserved and can be restored at any time.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isArchiving}>
            Keep Item
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isArchiving}
            aria-label={item ? `Archive ${item.name}` : 'Archive item'}
          >
            {isArchiving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Archiving…
              </>
            ) : (
              'Archive Item'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
