// ABOUTME: Create-a-sales-order dialog (CRUMB-01, Phase 11b) — pick the customer, optionally
// ABOUTME: set an order date, build ordered lines, then POST /crumb/sales-orders. The SO is
// ABOUTME: created as a Draft. On success invalidates the SO list, toasts, and closes.

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
import { useCreateSalesOrder, type SalesOrderLinePayload } from '../hooks'
import { useCustomers } from './lookups'
import { getApiErrorMessage } from './apiError'
import { SalesOrderLineEditor } from './SalesOrderLineEditor'

interface SalesOrderCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SalesOrderCreateDialog({ open, onOpenChange }: SalesOrderCreateDialogProps) {
  const { data: customers = [] } = useCustomers(open)
  const [partnerId, setPartnerId] = useState('')
  const [orderDate, setOrderDate] = useState('')
  const [lines, setLines] = useState<SalesOrderLinePayload[]>([])

  useEffect(() => {
    if (!open) return
    setPartnerId('')
    setOrderDate('')
    setLines([])
  }, [open])

  const createMutation = useCreateSalesOrder()
  const isSaving = createMutation.isPending
  const canSubmit = partnerId !== ''

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate(
      {
        partner_id: partnerId,
        order_date: orderDate.trim() || null,
        lines: lines.length ? lines : undefined,
      },
      {
        onSuccess: (so) => {
          toast.success(`Sales order ${so.so_number} created.`)
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(
            getApiErrorMessage(err, 'Failed to create the sales order. Please try again.')
          )
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="so-create-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Sales Order</DialogTitle>
          <DialogDescription id="so-create-description">
            Choose the customer, optionally set an order date, and add ordered lines. The
            order is created as a Draft.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="so-customer">Customer</Label>
              <Select value={partnerId} onValueChange={setPartnerId}>
                <SelectTrigger id="so-customer" aria-label="Customer">
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
              <Label htmlFor="so-order-date">Order date</Label>
              <Input
                id="so-order-date"
                type="date"
                aria-label="Order date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Lines</Label>
            <SalesOrderLineEditor lines={lines} onChange={setLines} />
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
              'Create Sales Order'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
