/**
 * PartnerArchiveDialog — destructive confirmation dialog for archiving a partner.
 *
 * Props:
 *   open: boolean
 *   partner: PartnerRead | null — the partner to archive (body copy uses partner.name)
 *   role: 'vendor' | 'customer' — determines copy and query key to invalidate
 *   onClose: () => void — called on confirm success or cancel
 *
 * Confirm fires PATCH /api/v1/syerp/partners/{id} with { active: false }.
 * On success: invalidates ['syerp','partners',role], toasts "Vendor archived." or "Customer archived.".
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
import type { PartnerRead } from './PartnerSheet'

// ─── Props ────────────────────────────────────────────────────────────────────

interface PartnerArchiveDialogProps {
  open: boolean
  partner: PartnerRead | null
  role: 'vendor' | 'customer'
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PartnerArchiveDialog({
  open,
  partner,
  role,
  onClose,
}: PartnerArchiveDialogProps) {
  const queryClient = useQueryClient()

  const archiveMutation = useMutation<PartnerRead, Error, string>({
    mutationFn: (partnerId) =>
      apiClient
        .patch<PartnerRead>(`/api/v1/syerp/partners/${partnerId}`, { active: false })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', role] })
      toast(role === 'vendor' ? 'Vendor archived.' : 'Customer archived.')
      onClose()
    },
    onError: () => {
      toast.error(
        role === 'vendor'
          ? 'Failed to archive vendor. Please try again.'
          : 'Failed to archive customer. Please try again.',
      )
    },
  })

  function handleConfirm() {
    if (partner) {
      archiveMutation.mutate(partner.id)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const isArchiving = archiveMutation.isPending

  // ── Copy ──
  const headingText = role === 'vendor' ? 'Archive vendor?' : 'Archive customer?'
  const cancelLabel = role === 'vendor' ? 'Keep Vendor' : 'Keep Customer'
  const confirmLabel = role === 'vendor' ? 'Archive Vendor' : 'Archive Customer'

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-labelledby="archive-dialog-title"
        aria-describedby="archive-dialog-description"
      >
        <DialogHeader>
          <DialogTitle id="archive-dialog-title">{headingText}</DialogTitle>
          <DialogDescription id="archive-dialog-description">
            {partner
              ? `${partner.name} will be hidden from the ${role} list. Existing references are preserved and can be restored at any time.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isArchiving}
          >
            {cancelLabel}
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isArchiving}
            aria-label={partner ? `Archive ${partner.name}` : 'Archive partner'}
          >
            {isArchiving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Archiving…
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
