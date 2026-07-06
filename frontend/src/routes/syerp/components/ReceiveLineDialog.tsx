// ABOUTME: Receive-a-PO-line dialog (Phase 8, Task 23) — STUB shell only. The final
// ABOUTME: form (qty received ≤ outstanding, location, unit cost → POST …/receive) is
// ABOUTME: filled in by Task 23; the host (PurchaseOrderDetail) already wires the seam.

/**
 * ReceiveLineDialog — records a receipt against a single purchase-order line.
 *
 * STUB (Task 22): renders only the Dialog shell + title so the host can wire the
 * per-line "Receive" seam now. Task 23 fleshes out the body (qty-received input
 * capped at outstandingQty, location Select, optional unit cost) and the mutation
 * POST /api/v1/syerp/purchasing/orders/{poId}/lines/{lineId}/receive.
 *
 * Props (final contract — do not change in Task 23):
 *   poId: string — the PO the line belongs to (POST target)
 *   lineId: string — the line being received against
 *   outstandingQty: string — qty_ordered − qty_received, as an exact Decimal string;
 *                            the receive form caps input at this value
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful receipt; the host invalidates
 *              the PO detail + list queries so the roll-up refreshes.
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// ─── Types ───────────────────────────────────────────────────────────────────

interface ReceiveLineDialogProps {
  poId: string
  lineId: string
  outstandingQty: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── Main component (stub) ─────────────────────────────────────────────────────

export function ReceiveLineDialog({
  poId: _poId,
  lineId: _lineId,
  outstandingQty,
  open,
  onOpenChange,
  onSuccess: _onSuccess,
}: ReceiveLineDialogProps) {
  // TODO(Task 23): full form — qty received (≤ outstandingQty), location Select,
  // optional unit cost → POST …/receive; on success call onSuccess() + close.
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="receive-line-description">
        <DialogHeader>
          <DialogTitle>Receive Line</DialogTitle>
          <DialogDescription id="receive-line-description">
            Record a receipt against this line ({outstandingQty} outstanding). The
            receiving form is added in Task 23.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}
