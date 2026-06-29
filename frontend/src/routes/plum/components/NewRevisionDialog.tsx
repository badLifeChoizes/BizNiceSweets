/**
 * NewRevisionDialog — dialog for creating a new Draft revision of a part.
 *
 * Props:
 *   open: boolean
 *   partId: string — the part to create a revision for
 *   revisions: RevisionRead[] — all existing revisions (newest-first)
 *   onClose: () => void — called on success or cancel
 *
 * Creates a Draft revision copying attributes from the selected source revision.
 * Default source: latest Released revision, fallback to latest overall.
 *
 * Mutation: POST /api/v1/plum/parts/{partId}/revisions
 * On success: invalidates ['plum','parts',partId], toasts "New revision {label} created."
 *
 * Accessibility: aria-labelledby + aria-describedby; see Accessibility Contract 8.
 */

import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/api/client'
import { cn } from '@/lib/utils'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RevisionRead {
  id: string
  part_id: string
  revision_number: number
  revision_label: string
  status: 'draft' | 'in_review' | 'released' | 'obsolete'
  description: string
  category?: string | null
  unit_of_measure?: string | null
  notes?: string | null
  reason_for_revision?: string | null
  created_at: string
  released_at?: string | null
  obsoleted_at?: string | null
}

interface NewRevisionDialogProps {
  open: boolean
  partId: string
  revisions: RevisionRead[]
  onClose: () => void
}

// ─── API error helper ─────────────────────────────────────────────────────────

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

// ─── Helper: determine default source revision ────────────────────────────────

function getDefaultSourceRevision(revisions: RevisionRead[]): RevisionRead | undefined {
  // Prefer latest Released revision, fallback to latest overall (revisions already newest-first)
  const released = revisions.find((r) => r.status === 'released')
  return released ?? revisions[0]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function NewRevisionDialog({
  open,
  partId,
  revisions,
  onClose,
}: NewRevisionDialogProps) {
  const queryClient = useQueryClient()

  const defaultSource = getDefaultSourceRevision(revisions)
  const [selectedSourceId, setSelectedSourceId] = useState<string>(defaultSource?.id ?? '')
  const [reason, setReason] = useState('')

  // Reset form state when the dialog opens
  useEffect(() => {
    if (!open) return
    const src = getDefaultSourceRevision(revisions)
    setSelectedSourceId(src?.id ?? '')
    setReason('')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const selectedRevision = revisions.find((r) => r.id === selectedSourceId)

  interface RevisionCreatePayload {
    source_revision_id?: string
    reason_for_revision?: string
  }

  const createRevisionMutation = useMutation<RevisionRead, Error, RevisionCreatePayload>({
    mutationFn: (payload) =>
      apiClient
        .post<RevisionRead>(`/api/v1/plum/parts/${partId}/revisions`, payload)
        .then((r) => r.data),
    onSuccess: (rev) => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast(`New revision ${rev.revision_label} created.`)
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to create revision. Please try again.'))
    },
  })

  function handleCreate() {
    if (!reason.trim()) {
      toast.error('Reason for revision is required.')
      return
    }
    createRevisionMutation.mutate({
      source_revision_id: selectedSourceId || undefined,
      reason_for_revision: reason.trim(),
    })
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isCreating = createRevisionMutation.isPending

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="new-rev-dialog-title"
        aria-describedby="new-rev-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="new-rev-dialog-title">Create New Revision</DialogTitle>
          <DialogDescription id="new-rev-dialog-description">
            A new Draft revision will be created, copying attributes from{' '}
            {selectedRevision
              ? `${selectedRevision.revision_label} (${selectedRevision.status.replace('_', ' ')})`
              : 'the selected revision'}
            . You may choose a different source below.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Clone-from selector */}
          <div className="space-y-2">
            <Label htmlFor="new-rev-source">Copy attributes from</Label>
            <Select
              value={selectedSourceId}
              onValueChange={setSelectedSourceId}
            >
              <SelectTrigger id="new-rev-source">
                <SelectValue placeholder="Select source revision" />
              </SelectTrigger>
              <SelectContent>
                {revisions.map((rev) => (
                  <SelectItem key={rev.id} value={rev.id}>
                    {rev.revision_label} — {rev.status.replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Reason for revision — required */}
          <div className="space-y-2">
            <Label htmlFor="new-rev-reason">
              Reason for revision
              <span className="text-destructive ml-1" aria-hidden="true">*</span>
            </Label>
            <textarea
              id="new-rev-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Describe why this revision is being created…"
              rows={3}
              required
              className={cn(
                'flex w-full rounded-md border border-input bg-transparent px-3 py-2',
                'text-base shadow-sm placeholder:text-muted-foreground',
                'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
                'disabled:cursor-not-allowed disabled:opacity-50',
              )}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isCreating}>
            Cancel
          </Button>
          <Button
            variant="default"
            onClick={handleCreate}
            disabled={isCreating}
          >
            {isCreating ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Creating…
              </>
            ) : (
              'Create Revision'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
