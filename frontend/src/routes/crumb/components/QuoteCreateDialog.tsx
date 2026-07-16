// ABOUTME: Create-a-quote dialog (CRUMB-01) — pick the customer, then POST /crumb/quotes.
// ABOUTME: The quote is created empty in Draft; lines are added on the detail screen. On
// ABOUTME: success invalidates the quote list, toasts, and closes; a 4xx surfaces the reason.

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
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
import { useCreateQuote } from '../hooks'
import { useCustomers } from './lookups'
import { getApiErrorMessage } from './apiError'

interface QuoteCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function QuoteCreateDialog({ open, onOpenChange }: QuoteCreateDialogProps) {
  const { data: customers = [] } = useCustomers(open)
  const [partnerId, setPartnerId] = useState('')

  useEffect(() => {
    if (!open) return
    setPartnerId('')
  }, [open])

  const createMutation = useCreateQuote()
  const isSaving = createMutation.isPending
  const canSubmit = partnerId !== ''

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate(
      { partner_id: partnerId },
      {
        onSuccess: (quote) => {
          toast.success(`Quote ${quote.quote_number} created.`)
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to create the quote. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="quote-create-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Quote</DialogTitle>
          <DialogDescription id="quote-create-description">
            Choose the customer this quote is for. It's created as a Draft — add priced
            lines on the quote detail screen.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="quote-customer">Customer</Label>
            <Select value={partnerId} onValueChange={setPartnerId}>
              <SelectTrigger id="quote-customer" aria-label="Customer">
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
              'Create Quote'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
