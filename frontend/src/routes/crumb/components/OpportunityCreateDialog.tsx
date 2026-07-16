// ABOUTME: Create-an-opportunity dialog (CRUMB-01) — pick the customer, name the deal, and
// ABOUTME: optionally set an estimated value + expected close date, then POST
// ABOUTME: /crumb/opportunities. New opportunities enter the pipeline at the Qualify stage.

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateOpportunity } from '../hooks'
import { useCustomers } from './lookups'
import { getApiErrorMessage } from './apiError'

interface OpportunityCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function OpportunityCreateDialog({ open, onOpenChange }: OpportunityCreateDialogProps) {
  const { data: customers = [] } = useCustomers(open)
  const [name, setName] = useState('')
  const [partnerId, setPartnerId] = useState('')
  const [estimatedValue, setEstimatedValue] = useState('')
  const [expectedCloseDate, setExpectedCloseDate] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setPartnerId('')
    setEstimatedValue('')
    setExpectedCloseDate('')
  }, [open])

  const createMutation = useCreateOpportunity()
  const isSaving = createMutation.isPending
  const canSubmit = name.trim() !== '' && partnerId !== ''

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate(
      {
        name: name.trim(),
        partner_id: partnerId,
        estimated_value: estimatedValue.trim() || null,
        expected_close_date: expectedCloseDate || null,
      },
      {
        onSuccess: (opp) => {
          toast.success(`Opportunity “${opp.name}” created.`)
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(
            getApiErrorMessage(err, 'Failed to create the opportunity. Please try again.')
          )
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="opp-create-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Opportunity</DialogTitle>
          <DialogDescription id="opp-create-description">
            Open a pipeline opportunity for a customer. It starts in the Qualify stage.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="opp-name">Name</Label>
            <Input
              id="opp-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Hospital — Q3 simulators"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="opp-customer">Customer</Label>
            <Select value={partnerId} onValueChange={setPartnerId}>
              <SelectTrigger id="opp-customer" aria-label="Customer">
                <SelectValue placeholder="Select a customer" />
              </SelectTrigger>
              <SelectContent>
                {customers.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="opp-value">Estimated value</Label>
            <Input
              id="opp-value"
              aria-label="Estimated value"
              inputMode="decimal"
              value={estimatedValue}
              onChange={(e) => setEstimatedValue(e.target.value)}
              placeholder="Optional — e.g. 25000.00"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="opp-close">Expected close date</Label>
            <Input
              id="opp-close"
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
                Creating…
              </>
            ) : (
              'Create Opportunity'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
