// ABOUTME: Link-customer dialog (CRUMB-01) — attach a lead to a SYERP customer either by
// ABOUTME: picking an existing customer partner OR by naming a new one to be created, then
// ABOUTME: POST /crumb/leads/{id}/link-customer. Success toasts + closes; 4xx surfaces.

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
import { useLinkCustomer } from '../hooks'
import { useCustomers } from './lookups'
import { getApiErrorMessage } from './apiError'

interface LinkCustomerDialogProps {
  leadId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Mode = 'existing' | 'new'

export function LinkCustomerDialog({ leadId, open, onOpenChange }: LinkCustomerDialogProps) {
  const { data: customers = [] } = useCustomers(open)
  const [mode, setMode] = useState<Mode>('existing')
  const [partnerId, setPartnerId] = useState('')
  const [newName, setNewName] = useState('')

  useEffect(() => {
    if (!open) return
    setMode('existing')
    setPartnerId('')
    setNewName('')
  }, [open])

  const linkMutation = useLinkCustomer()
  const isSaving = linkMutation.isPending
  const canSubmit = mode === 'existing' ? partnerId !== '' : newName.trim() !== ''

  function handleSubmit() {
    if (!canSubmit) return
    const payload =
      mode === 'existing'
        ? { partner_id: partnerId }
        : { new_customer_name: newName.trim(), is_customer: true }
    linkMutation.mutate(
      { id: leadId, payload },
      {
        onSuccess: () => {
          toast.success('Customer linked to lead.')
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to link the customer. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="link-customer-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Link Customer</DialogTitle>
          <DialogDescription id="link-customer-description">
            Point this lead at an existing SYERP customer, or create a new customer from
            a name. A lead must be linked before it can be converted.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Mode toggle */}
          <div className="flex gap-2">
            <Button
              type="button"
              variant={mode === 'existing' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('existing')}
            >
              Existing customer
            </Button>
            <Button
              type="button"
              variant={mode === 'new' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('new')}
            >
              New customer
            </Button>
          </div>

          {mode === 'existing' ? (
            <div className="space-y-2">
              <Label htmlFor="link-partner">Customer</Label>
              <Select value={partnerId} onValueChange={setPartnerId}>
                <SelectTrigger id="link-partner" aria-label="Customer">
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
          ) : (
            <div className="space-y-2">
              <Label htmlFor="link-new-name">New customer name</Label>
              <Input
                id="link-new-name"
                aria-label="New customer name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Acme Hospital"
              />
            </div>
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
                Linking…
              </>
            ) : (
              'Link Customer'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
