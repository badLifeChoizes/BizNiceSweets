// ABOUTME: Create-an-invoice dialog (Phase 13, SYERP-13) — pick a customer, fetch its
// ABOUTME: uninvoiced shipped SO lines, check lines + set an invoiced qty (price is READ-ONLY,
// ABOUTME: locked to the SO unit_price), then POST /api/v1/syerp/ar/invoices. 422s toast.

/**
 * InvoiceCreateDialog — raises a customer invoice against shipped-but-uninvoiced sales
 * order lines (SYERP-13, Phase 13).
 *
 * Props:
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful create; the host invalidates the
 *              invoices list query so the new invoice appears.
 *
 * Flow:
 *   1. Customer — required Select (GET /api/v1/syerp/partners?role=customer). Selecting a
 *      customer loads its uninvoiced shipments (GET /ar/uninvoiced-shipments?customer_id=).
 *   2. Invoice date — optional; defaults to today (the server also defaults when omitted).
 *   3. Uninvoiced shipment lines — each with a "invoice this line" checkbox and an
 *      invoiced-qty Input defaulting to the full uninvoiced_qty. The unit price is
 *      READ-ONLY text, locked to the sales order line's unit_price (never editable — the
 *      invoice line price is fixed to the SO price).
 *
 * Mutation: POST /api/v1/syerp/ar/invoices with
 *   { customer_id, invoice_date?, lines:[{ sales_order_line_id, invoiced_qty }] }.
 *   Success: onSuccess() (host invalidates the list), close, toast.
 *   Error (esp. 422 over-invoice / empty): toast.error with the server `detail` and DO NOT
 *          close — let the user fix the input.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
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
import { apiClient } from '@/api/client'
import type { PartnerRead } from './PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

interface UninvoicedShipmentRead {
  sales_order_line_id: string
  so_number: string
  item_id: string | null
  description: string | null
  uninvoiced_qty: string
  unit_price: string
}

interface InvoiceCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchCustomers(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=customer')
    .then((r) => r.data)
}

function fetchUninvoicedShipments(customerId: string): Promise<UninvoicedShipmentRead[]> {
  return apiClient
    .get<UninvoicedShipmentRead[]>(
      `/api/v1/syerp/ar/uninvoiced-shipments?customer_id=${customerId}`,
    )
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 over-invoice) or a validation
// array of { loc, msg }. Map both to a readable, actionable message.
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

// Today as YYYY-MM-DD in the local timezone (the <input type="date"> value format).
// The server defaults invoice_date to today when omitted, so this keeps the posted
// date matching what the user sees unless they pick another date.
function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

// A qty string parsed to a number for a ">0" test. Blank / non-numeric → 0.
function toNum(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

// ─── Payload types ───────────────────────────────────────────────────────────

interface InvoiceLinePayload {
  sales_order_line_id: string
  invoiced_qty: string
}

interface InvoiceCreatePayload {
  customer_id: string
  invoice_date?: string
  lines: InvoiceLinePayload[]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function InvoiceCreateDialog({
  open,
  onOpenChange,
  onSuccess,
}: InvoiceCreateDialogProps) {
  // ── Options ──
  const { data: customers = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'customer'],
    queryFn: fetchCustomers,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })

  // ── Form state ──
  const [customerId, setCustomerId] = useState('')
  // Optional invoice date (the aging basis). Defaults to today; server also defaults.
  const [invoiceDate, setInvoiceDate] = useState(todayISO)
  // sales_order_line_ids the user has checked to invoice.
  const [checkedLines, setCheckedLines] = useState<Set<string>>(new Set())
  // Per-line invoiced qty (defaults to the full uninvoiced_qty when checked).
  const [lineQty, setLineQty] = useState<Record<string, string>>({})

  // Uninvoiced shipments for the chosen customer (loaded only once a customer is picked).
  const { data: shipments = [], isFetching: shipmentsLoading } = useQuery<
    UninvoicedShipmentRead[],
    Error
  >({
    queryKey: ['syerp', 'ar', 'uninvoiced-shipments', { customerId }],
    queryFn: () => fetchUninvoicedShipments(customerId),
    enabled: open && customerId !== '',
    retry: false,
  })

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setCustomerId('')
    setInvoiceDate(todayISO())
    setCheckedLines(new Set())
    setLineQty({})
  }, [open])

  // ── Changing customer clears any prior selections (they belonged to another customer) ──
  function handleCustomerChange(id: string) {
    setCustomerId(id)
    setCheckedLines(new Set())
    setLineQty({})
  }

  // Checking a line defaults its qty to the full uninvoiced quantity.
  function toggleLine(line: UninvoicedShipmentRead, checked: boolean) {
    setCheckedLines((prev) => {
      const next = new Set(prev)
      if (checked) next.add(line.sales_order_line_id)
      else next.delete(line.sales_order_line_id)
      return next
    })
    if (checked) {
      setLineQty((prev) => ({
        ...prev,
        [line.sales_order_line_id]: prev[line.sales_order_line_id] ?? line.uninvoiced_qty,
      }))
    }
  }

  function updateQty(salesOrderLineId: string, value: string) {
    setLineQty((prev) => ({ ...prev, [salesOrderLineId]: value }))
  }

  // ── Validation: every checked line needs a qty > 0. ──
  const checkedShipments = shipments.filter((s) => checkedLines.has(s.sales_order_line_id))
  const allQtyValid = checkedShipments.every((s) => toNum(lineQty[s.sales_order_line_id] ?? '') > 0)
  const canSubmit = customerId !== '' && checkedShipments.length > 0 && allQtyValid

  // ── Mutation ──
  const createMutation = useMutation<unknown, Error, InvoiceCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post('/api/v1/syerp/ar/invoices', payload).then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Invoice created.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (the backend rejects
      // an empty invoice or an over-invoice with 422).
      toast.error(getApiErrorMessage(err, 'Failed to create the invoice. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    const lines: InvoiceLinePayload[] = checkedShipments.map((s) => ({
      sales_order_line_id: s.sales_order_line_id,
      invoiced_qty: (lineQty[s.sales_order_line_id] ?? '').trim(),
    }))
    const payload: InvoiceCreatePayload = {
      customer_id: customerId,
      ...(invoiceDate ? { invoice_date: invoiceDate } : {}),
      lines,
    }
    createMutation.mutate(payload)
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="invoice-create-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Invoice</DialogTitle>
          <DialogDescription id="invoice-create-description">
            Raise a customer invoice. Check shipped lines to invoice and set the invoiced
            quantity. Each line's price is locked to the sales order price.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Customer + invoice date */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="invoice-customer">Customer</Label>
              <Select value={customerId} onValueChange={handleCustomerChange}>
                <SelectTrigger id="invoice-customer" aria-label="Customer">
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
              <Label htmlFor="invoice-date">Invoice date</Label>
              <Input
                id="invoice-date"
                type="date"
                aria-label="Invoice date"
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
              />
            </div>
          </div>

          {/* Uninvoiced shipment lines */}
          <div className="space-y-2">
            <Label>Uninvoiced shipments</Label>
            {customerId === '' ? (
              <p className="text-sm text-muted-foreground">
                Select a customer to load shipments.
              </p>
            ) : shipmentsLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : shipments.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No uninvoiced shipments for this customer.
              </p>
            ) : (
              <div className="space-y-1">
                <div className="grid grid-cols-[2rem_1fr_6rem_7rem_7rem] items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span />
                  <span>SO / Item</span>
                  <span className="text-right">Shipped</span>
                  <span className="text-right">Invoice qty</span>
                  <span className="text-right">Unit price</span>
                </div>
                {shipments.map((s) => {
                  const checked = checkedLines.has(s.sales_order_line_id)
                  return (
                    <div
                      key={s.sales_order_line_id}
                      className="grid grid-cols-[2rem_1fr_6rem_7rem_7rem] items-center gap-2"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        aria-label={`Invoice line ${s.so_number}`}
                        checked={checked}
                        onChange={(e) => toggleLine(s, e.target.checked)}
                      />
                      <span className="text-sm">
                        {s.so_number}
                        {s.item_id || s.description ? (
                          <span className="text-muted-foreground">
                            {' '}
                            · {s.item_id ?? s.description}
                          </span>
                        ) : null}
                      </span>
                      <span className="text-right font-mono text-sm">{s.uninvoiced_qty}</span>
                      <Input
                        aria-label={`Invoice qty ${s.so_number}`}
                        inputMode="decimal"
                        className="h-8 text-right"
                        disabled={!checked}
                        value={checked ? (lineQty[s.sales_order_line_id] ?? '') : ''}
                        onChange={(e) => updateQty(s.sales_order_line_id, e.target.value)}
                        placeholder={s.uninvoiced_qty}
                      />
                      {/* Unit price is READ-ONLY — locked to the sales order line price. */}
                      <span
                        className="text-right font-mono text-sm"
                        aria-label={`Unit price ${s.so_number}`}
                      >
                        {s.unit_price}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
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
              'Create Invoice'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
