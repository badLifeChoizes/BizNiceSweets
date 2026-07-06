// ABOUTME: Stub Adjust-Stock dialog for a SYERP inventory item (Phase 8). Task 11
// ABOUTME: established the seam (open/onOpenChange/onSuccess) and hosts it from
// ABOUTME: InventoryItemDetail; Task 12 fleshes out the signed-delta + reason form.

/**
 * StockAdjustDialog — posts a signed stock adjustment for an inventory item.
 *
 * Props:
 *   itemId: string — the item being adjusted (POST target)
 *   open: boolean — controls dialog visibility
 *   onOpenChange: (open: boolean) => void — Radix-controlled open state
 *   onSuccess: () => void — called after a successful post; the host invalidates
 *              the item's onhand + transactions queries so the view refreshes.
 *
 * NOTE: This is a thin placeholder shell so the InventoryItemDetail seam builds
 * tsc-clean today. Task 12 replaces the body with the full form
 * (location + signed qty_delta + required reason → POST
 * /api/v1/syerp/inventory/items/{itemId}/adjustments) and calls onSuccess().
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface StockAdjustDialogProps {
  itemId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// TODO(Task 12): full form — location, signed qty_delta, required reason,
// POST …/adjustments, then call onSuccess() to invalidate onhand+transactions.
export function StockAdjustDialog({ open, onOpenChange }: StockAdjustDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adjust Stock</DialogTitle>
          <DialogDescription>
            Stock adjustment form coming soon.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}
