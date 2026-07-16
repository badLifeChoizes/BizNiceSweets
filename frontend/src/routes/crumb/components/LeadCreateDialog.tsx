// ABOUTME: Create-a-lead dialog (CRUMB-01) — capture name (required), company, contact
// ABOUTME: and source, then POST /crumb/leads. Success invalidates the lead list, toasts,
// ABOUTME: and closes; a 4xx keeps the dialog open and surfaces the server reason.

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
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
import { useCreateLead } from '../hooks'
import { getApiErrorMessage } from './apiError'

interface LeadCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function LeadCreateDialog({ open, onOpenChange }: LeadCreateDialogProps) {
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [contact, setContact] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setCompany('')
    setContact('')
    setSource('')
  }, [open])

  const createMutation = useCreateLead()
  const canSubmit = name.trim() !== ''
  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate(
      {
        name: name.trim(),
        company: company.trim() || null,
        contact: contact.trim() || null,
        source: source.trim() || null,
      },
      {
        onSuccess: (lead) => {
          toast.success(`Lead “${lead.name}” created.`)
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to create the lead. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="lead-create-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Lead</DialogTitle>
          <DialogDescription id="lead-create-description">
            Capture a prospect. Only a name is required — you can link a customer and
            convert to an opportunity later.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="lead-name">Name</Label>
            <Input
              id="lead-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Hospital procurement"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="lead-company">Company</Label>
            <Input
              id="lead-company"
              aria-label="Company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="lead-contact">Contact</Label>
            <Input
              id="lead-contact"
              aria-label="Contact"
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="lead-source">Source</Label>
            <Input
              id="lead-source"
              aria-label="Source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Optional — e.g. trade show, referral"
            />
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Creating…
              </>
            ) : (
              'Create Lead'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
