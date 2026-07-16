// ABOUTME: Convert-lead dialog (CRUMB-01) — spin a qualified, customer-linked lead into a
// ABOUTME: pipeline opportunity (name, estimated value, expected close date) via POST
// ABOUTME: /crumb/leads/{id}/convert. On success navigates to the new opportunity; 422s
// ABOUTME: (e.g. convert without a linked customer) surface as a toast, dialog stays open.

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { useConvertLead } from '../hooks'
import { getApiErrorMessage } from './apiError'

interface ConvertLeadDialogProps {
  leadId: string
  defaultName: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ConvertLeadDialog({
  leadId,
  defaultName,
  open,
  onOpenChange,
}: ConvertLeadDialogProps) {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [estimatedValue, setEstimatedValue] = useState('')
  const [expectedCloseDate, setExpectedCloseDate] = useState('')

  useEffect(() => {
    if (!open) return
    setName(defaultName)
    setEstimatedValue('')
    setExpectedCloseDate('')
  }, [open, defaultName])

  const convertMutation = useConvertLead()
  const isSaving = convertMutation.isPending
  const canSubmit = name.trim() !== ''

  function handleSubmit() {
    if (!canSubmit) return
    convertMutation.mutate(
      {
        id: leadId,
        payload: {
          name: name.trim(),
          estimated_value: estimatedValue.trim() || null,
          expected_close_date: expectedCloseDate || null,
        },
      },
      {
        onSuccess: (opp) => {
          toast.success(`Opportunity “${opp.name}” created.`)
          onOpenChange(false)
          navigate(`/crumb/opportunities/${opp.id}`)
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to convert the lead. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="convert-lead-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Convert to Opportunity</DialogTitle>
          <DialogDescription id="convert-lead-description">
            Promote this lead into a pipeline opportunity. The lead must already be linked
            to a customer.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="convert-name">Opportunity name</Label>
            <Input
              id="convert-name"
              aria-label="Opportunity name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Hospital — Q3 simulators"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="convert-value">Estimated value</Label>
            <Input
              id="convert-value"
              aria-label="Estimated value"
              inputMode="decimal"
              value={estimatedValue}
              onChange={(e) => setEstimatedValue(e.target.value)}
              placeholder="Optional — e.g. 25000.00"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="convert-close">Expected close date</Label>
            <Input
              id="convert-close"
              aria-label="Expected close date"
              type="date"
              value={expectedCloseDate}
              onChange={(e) => setExpectedCloseDate(e.target.value)}
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
                Converting…
              </>
            ) : (
              'Convert Lead'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
