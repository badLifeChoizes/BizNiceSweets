/**
 * ArchivePartDialog — destructive confirmation dialog for archiving a part.
 *
 * Props:
 *   open: boolean
 *   part: PartRead | null — the part to archive (body copy uses part.part_number)
 *   onClose: () => void — called on confirm success or cancel
 *
 * Confirm fires PATCH /api/v1/plum/parts/{id} with { active: false }.
 * On success: invalidates ['plum','parts'], toasts "Part archived.".
 *
 * Accessibility: aria-labelledby + aria-describedby; confirm button has
 * aria-label="Archive {part_number}".
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
import type { PartRead } from './PartSheet'

// ─── Props ────────────────────────────────────────────────────────────────────

interface ArchivePartDialogProps {
  open: boolean
  part: PartRead | null
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ArchivePartDialog({ open, part, onClose }: ArchivePartDialogProps) {
  const queryClient = useQueryClient()

  const archiveMutation = useMutation<PartRead, Error, string>({
    mutationFn: (partId) =>
      apiClient
        .patch<PartRead>(`/api/v1/plum/parts/${partId}`, { active: false })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
      toast('Part archived.')
      onClose()
    },
    onError: () => {
      toast.error('Failed to archive part. Please try again.')
    },
  })

  function handleConfirm() {
    if (part) {
      archiveMutation.mutate(part.id)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isArchiving = archiveMutation.isPending

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="archive-part-dialog-title"
        aria-describedby="archive-part-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="archive-part-dialog-title">Archive part?</DialogTitle>
          <DialogDescription id="archive-part-dialog-description">
            {part
              ? `${part.part_number} will be hidden from the parts list. Existing revision history and references are preserved and can be restored at any time.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isArchiving}
          >
            Keep Part
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isArchiving}
            aria-label={part ? `Archive ${part.part_number}` : 'Archive part'}
          >
            {isArchiving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Archiving…
              </>
            ) : (
              'Archive Part'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
