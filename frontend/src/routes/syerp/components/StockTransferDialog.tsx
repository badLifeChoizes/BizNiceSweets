// ABOUTME: Stub Transfer-Stock dialog for a SYERP inventory item (Phase 8). Task 11
// ABOUTME: established the seam (open/onOpenChange/onSuccess) and hosts it from
// ABOUTME: InventoryItemDetail; Task 13 fleshes out the from→to + qty form.

/**
 * StockTransferDialog — posts a from→to stock transfer for an inventory item.
 *
 * Props:
 *   itemId: string — the item being transferred (POST target)
 *   open: boolean — controls dialog visibility
 *   onOpenChange: (open: boolean) => void — Radix-controlled open state
 *   onSuccess: () => void — called after a successful post; the host invalidates
 *              the item's onhand + transactions queries so the view refreshes.
 *
 * NOTE: This is a thin placeholder shell so the InventoryItemDetail seam builds
 * tsc-clean today. Task 13 replaces the body with the full form
 * (from_location + to_location + qty → POST
 * /api/v1/syerp/inventory/items/{itemId}/transfers) and calls onSuccess().
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface StockTransferDialogProps {
  itemId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// TODO(Task 13): full form — from_location, to_location, positive qty,
// POST …/transfers, then call onSuccess() to invalidate onhand+transactions.
export function StockTransferDialog({ open, onOpenChange }: StockTransferDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Transfer Stock</DialogTitle>
          <DialogDescription>
            Stock transfer form coming soon.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}
