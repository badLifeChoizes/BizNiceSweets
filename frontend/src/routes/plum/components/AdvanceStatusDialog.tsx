/**
 * AdvanceStatusDialog — confirmation dialog for releasing a revision (In Review → Released).
 *
 * Props:
 *   open: boolean
 *   partId: string — the part ID (for URL construction and cache invalidation)
 *   revision: RevisionRead — the revision to release
 *   priorReleasedLabel: string | undefined — label of the currently released revision, if any
 *   onClose: () => void — called on success or cancel
 *
 * Releasing is irreversible and auto-obsoletes the prior released revision (D-08).
 * This dialog forces explicit confirmation before the action.
 *
 * Mutation: POST /api/v1/plum/parts/{partId}/revisions/{revision.id}/advance
 *           with { target_status: 'released' }
 * On success: invalidates ['plum','parts',partId], toasts "Revision {label} released. Prior revision obsoleted."
 *
 * Accessibility: aria-labelledby + aria-describedby; Release button has aria-label.
 *   See Accessibility Contracts 7-8 in 05-UI-SPEC.md.
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
import type { RevisionRead } from './NewRevisionDialog'

// ─── Props ────────────────────────────────────────────────────────────────────

interface AdvanceStatusDialogProps {
  open: boolean
  partId: string
  revision: RevisionRead
  priorReleasedLabel?: string
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function AdvanceStatusDialog({
  open,
  partId,
  revision,
  priorReleasedLabel,
  onClose,
}: AdvanceStatusDialogProps) {
  const queryClient = useQueryClient()

  const releaseMutation = useMutation<RevisionRead, Error, void>({
    mutationFn: () =>
      apiClient
        .post<RevisionRead>(
          `/api/v1/plum/parts/${partId}/revisions/${revision.id}/advance`,
          { target_status: 'released' },
        )
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast(`Revision ${revision.revision_label} released. Prior revision obsoleted.`)
      onClose()
    },
    onError: () => {
      toast.error('Status transition failed. Please try again.')
    },
  })

  function handleRelease() {
    releaseMutation.mutate()
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isReleasing = releaseMutation.isPending

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="release-dialog-title"
        aria-describedby="release-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="release-dialog-title">
            Release revision {revision.revision_label}?
          </DialogTitle>
          <DialogDescription id="release-dialog-description">
            {priorReleasedLabel
              ? `This will release ${revision.revision_label} and automatically obsolete the current released revision (${priorReleasedLabel}). Released revisions cannot be edited.`
              : `This will release ${revision.revision_label}. Released revisions cannot be edited.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isReleasing}>
            Cancel
          </Button>
          <Button
            variant="default"
            onClick={handleRelease}
            disabled={isReleasing}
            aria-label={`Release revision ${revision.revision_label}`}
          >
            {isReleasing ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Releasing…
              </>
            ) : (
              'Release'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
