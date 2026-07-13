// ABOUTME: Complete-a-work-order dialog (MOUSSE-01, SC7, D-P10-9) — receives the finished
// ABOUTME: good and clears WIP via POST /mousse/work-orders/{id}/complete. Under-issued WOs
// ABOUTME: require ticking an "override incomplete" checkbox (sends override_incomplete=true).

/**
 * CompleteWorkOrderDialog — completes an In-Progress work order, receiving the planned
 * finished-good quantity into stock and clearing WIP to zero (MOUSSE-01, SC7, D-P10-9).
 *
 * Props:
 *   workOrderId — the WO being completed.
 *   components  — the WO's resolved component lines, used to detect under-issue.
 *   partName    — resolver child_part_id → display label.
 *   open / onOpenChange — Radix-controlled visibility.
 *   onSuccess   — called after a successful completion; the host invalidates the detail + list.
 *
 * Under-issue policy (D-P10-9): a component with issued_so_far < qty_required is "short".
 * When any line is short, the dialog surfaces a warning listing the short components and
 * requires ticking an "override incomplete" checkbox before submit — completion then sends
 * override_incomplete=true. A fully-issued WO completes without the checkbox.
 *
 * Mutation: POST /api/v1/mousse/work-orders/{id}/complete with { override_incomplete }.
 *   Success: onSuccess(), toast the received FG qty + WIP cleared, close.
 *   Error (e.g. 4xx under-issue rejection with no override): toast.error(server detail)
 *   and DO NOT close.
 */

import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { apiClient } from '@/api/client'
import { isUnderIssued } from '../WorkOrderDetail'
import type { WorkOrderComponentRead } from '../hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface CompleteWorkOrderDialogProps {
  workOrderId: string
  components: WorkOrderComponentRead[]
  partName: (childPartId: string) => string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

interface CompletePayload {
  override_incomplete: boolean
}

interface CompleteResult {
  work_order_id: string
  output_item_id: string
  quantity_received: string
  wip_cleared_value: string
  completed_at: string
}

// ─── API helpers ─────────────────────────────────────────────────────────────

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

export function CompleteWorkOrderDialog({
  workOrderId,
  components,
  partName,
  open,
  onOpenChange,
  onSuccess,
}: CompleteWorkOrderDialogProps) {
  const [override, setOverride] = useState(false)

  const shortComponents = components.filter(isUnderIssued)
  const hasShort = shortComponents.length > 0

  // ── Reset the checkbox each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setOverride(false)
  }, [open])

  // A short WO cannot complete until the override is acknowledged.
  const canSubmit = !hasShort || override

  // ── Mutation ──
  const completeMutation = useMutation<CompleteResult, Error, CompletePayload>({
    mutationFn: (payload) =>
      apiClient
        .post<CompleteResult>(`/api/v1/mousse/work-orders/${workOrderId}/complete`, payload)
        .then((r) => r.data),
    onSuccess: (result) => {
      onSuccess()
      toast.success(
        `Work order completed — received ${result.quantity_received} (WIP cleared ${result.wip_cleared_value}).`,
      )
      onOpenChange(false)
    },
    onError: (err) => {
      // A 4xx under-issue rejection (no override) lands here — surface it and keep open.
      toast.error(getApiErrorMessage(err, 'Failed to complete the work order. Please try again.'))
    },
  })

  const isSaving = completeMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    completeMutation.mutate({ override_incomplete: hasShort && override })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="wo-complete-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Complete Work Order</DialogTitle>
          <DialogDescription id="wo-complete-description">
            Completing receives the planned finished-good quantity into stock at the
            accumulated WIP unit cost and clears the work order's WIP to zero.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {hasShort ? (
            <div className="space-y-3 rounded-md border border-amber-300 bg-amber-50 p-3">
              <p className="text-sm font-semibold text-amber-800">
                Some components are under-issued.
              </p>
              <ul className="list-disc space-y-0.5 pl-5 text-sm text-amber-800">
                {shortComponents.map((c) => (
                  <li key={c.id}>
                    {partName(c.child_part_id)} — issued {c.issued_so_far} of {c.qty_required}
                  </li>
                ))}
              </ul>
              <label className="flex items-start gap-2 text-sm text-amber-900">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4"
                  aria-label="Override incomplete and complete anyway"
                  checked={override}
                  onChange={(e) => setOverride(e.target.checked)}
                />
                <span>
                  Override incomplete and complete anyway. The finished good is still valued
                  at accumulated WIP; this override is audited.
                </span>
              </label>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              All components are fully issued. This work order is ready to complete.
            </p>
          )}
          <Label className="sr-only">Confirm work-order completion.</Label>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Completing…
              </>
            ) : (
              'Complete Work Order'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
