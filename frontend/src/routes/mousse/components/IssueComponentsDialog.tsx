// ABOUTME: Issue-components dialog (MOUSSE-01, SC7) — consume quantities of a work
// ABOUTME: order's snapshot components from stock, POST /mousse/work-orders/{id}/issue.
// ABOUTME: Each line draws off the WO's target location by default; 4xx surface a toast.

/**
 * IssueComponentsDialog — issues one or more of a work order's snapshot components
 * against stock in a single atomic posting (MOUSSE-01, SC7).
 *
 * Props:
 *   workOrderId — the WO being issued against.
 *   components  — the WO's resolved component lines (with qty_required / issued_so_far
 *                 / on_hand), used to seed the per-line quantities and label the rows.
 *   partName    — resolver child_part_id → display label.
 *   open / onOpenChange — Radix-controlled visibility.
 *   onSuccess   — called after a successful issue; the host invalidates the detail + list.
 *
 * Each row offers a "issue this line" checkbox and an editable quantity, seeded to the
 * line's remaining (qty_required − issued_so_far, floored at 0). Location defaults to the
 * WO's target_location_id server-side, so it is omitted here. Decimal quantities are kept
 * as STRINGS and sent verbatim (D-11).
 *
 * Mutation: POST /api/v1/mousse/work-orders/{id}/issue with { lines: [{ component_id,
 *   quantity }] }. Success: onSuccess(), toast, close. Error (e.g. 4xx insufficient
 *   stock): toast.error(server detail) and DO NOT close.
 */

import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import type { WorkOrderComponentRead } from '../hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface IssueComponentsDialogProps {
  workOrderId: string
  components: WorkOrderComponentRead[]
  partName: (childPartId: string) => string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

interface IssueLinePayload {
  component_id: string
  quantity: string
}

interface IssuePayload {
  lines: IssueLinePayload[]
}

// A row's editable draft state.
interface LineDraft {
  checked: boolean
  quantity: string
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

function toNumber(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

// Remaining to issue = qty_required − issued_so_far, floored at 0. Decimals arrive as
// strings; Number() only to derive the seed value for the input.
function remainingOf(c: WorkOrderComponentRead): string {
  const remaining = Number(c.qty_required) - Number(c.issued_so_far)
  if (!Number.isFinite(remaining) || remaining <= 0) return ''
  return String(remaining)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function IssueComponentsDialog({
  workOrderId,
  components,
  partName,
  open,
  onOpenChange,
  onSuccess,
}: IssueComponentsDialogProps) {
  // Per-component draft state, keyed by component id.
  const [drafts, setDrafts] = useState<Record<string, LineDraft>>({})

  // ── Seed the drafts each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    const seeded: Record<string, LineDraft> = {}
    for (const c of components) {
      const remaining = remainingOf(c)
      seeded[c.id] = { checked: remaining !== '', quantity: remaining }
    }
    setDrafts(seeded)
  }, [open, components])

  function updateDraft(componentId: string, patch: Partial<LineDraft>) {
    setDrafts((prev) => ({ ...prev, [componentId]: { ...prev[componentId], ...patch } }))
  }

  // ── Validation: every checked line needs a positive quantity ──
  const checkedLines = components.filter((c) => drafts[c.id]?.checked)
  const allCheckedValid = checkedLines.every((c) => toNumber(drafts[c.id]?.quantity ?? '') > 0)
  const canSubmit = checkedLines.length > 0 && allCheckedValid

  // ── Mutation ──
  const issueMutation = useMutation<unknown, Error, IssuePayload>({
    mutationFn: (payload) =>
      apiClient
        .post(`/api/v1/mousse/work-orders/${workOrderId}/issue`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Components issued.')
      onOpenChange(false)
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to issue components. Please try again.'))
    },
  })

  const isSaving = issueMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    const lines: IssueLinePayload[] = checkedLines.map((c) => ({
      component_id: c.id,
      quantity: (drafts[c.id]?.quantity ?? '').trim(),
    }))
    issueMutation.mutate({ lines })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="wo-issue-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Issue Components</DialogTitle>
          <DialogDescription id="wo-issue-description">
            Check the components to consume and confirm the quantity. Each line draws from
            the work order's target location at the item's current moving-average cost.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-2">
          {components.length === 0 ? (
            <p className="text-sm text-muted-foreground">This work order has no components.</p>
          ) : (
            <>
              <div className="grid grid-cols-[2rem_1fr_6rem_6rem_7rem] items-center gap-2 text-xs font-medium text-muted-foreground">
                <span />
                <span>Component</span>
                <span className="text-right">Required</span>
                <span className="text-right">On hand</span>
                <span className="text-right">Issue qty</span>
              </div>
              {components.map((c) => {
                const draft = drafts[c.id] ?? { checked: false, quantity: '' }
                return (
                  <div
                    key={c.id}
                    className="grid grid-cols-[2rem_1fr_6rem_6rem_7rem] items-center gap-2"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      aria-label={`Issue ${partName(c.child_part_id)}`}
                      checked={draft.checked}
                      onChange={(e) => updateDraft(c.id, { checked: e.target.checked })}
                    />
                    <span className="text-sm">{partName(c.child_part_id)}</span>
                    <span className="text-right font-mono text-sm">{c.qty_required}</span>
                    <span className="text-right font-mono text-sm">{c.on_hand}</span>
                    <Input
                      aria-label={`Issue qty for ${partName(c.child_part_id)}`}
                      inputMode="decimal"
                      className="h-8 text-right"
                      value={draft.quantity}
                      onChange={(e) => updateDraft(c.id, { quantity: e.target.value })}
                      placeholder="0"
                    />
                  </div>
                )
              })}
              <Label className="sr-only">
                Check components and enter the quantity to issue.
              </Label>
            </>
          )}
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Issuing…
              </>
            ) : (
              'Issue Components'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
