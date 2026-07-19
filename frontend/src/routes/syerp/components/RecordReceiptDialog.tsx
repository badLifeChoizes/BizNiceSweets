// ABOUTME: Record-a-receipt dialog (Phase 13, SYERP-13) — pick a cash/bank account (defaults
// ABOUTME: to code 1110 Cash), a receipt date + optional reference, then allocate amounts across
// ABOUTME: one or more open (posted) invoices → POST /api/v1/syerp/ar/receipts. 422s toast.

/**
 * RecordReceiptDialog — records a cash collection allocated across one or more posted
 * (open-balance) customer invoices (SYERP-13, Phase 13).
 *
 * Props:
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful receipt; the host invalidates the
 *              receipts + invoices list queries so balances refresh.
 *
 * Fields:
 *   1. Cash / bank account — required Select (GET /gl/accounts filtered to ASSET). The
 *      option whose code is 1110 (Cash) is selected by default; the seed also ships
 *      1111 Bank – Checking. Resolved to cash_account_id (int) on submit.
 *   2. Receipt date — required, defaults to today (YYYY-MM-DD).
 *   3. Reference — optional check/transfer reference (free text).
 *   4. Open invoices — each posted invoice with an open balance carries a checkbox and an
 *      amount Input defaulting to its full open balance; checked invoices become allocations.
 *
 * Mutation: POST /api/v1/syerp/ar/receipts with
 *   { receipt_date, cash_account_id, reference?, allocations:[{ invoice_id, amount }] }.
 *   The receipt amount is NOT sent — the server sums the allocations.
 *   Success: onSuccess() (host invalidates lists), close, toast.
 *   Error (esp. 422 over-application): toast.error with the server `detail` and DO NOT
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
import type { InvoiceRead } from '../Invoices'

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface RecordReceiptDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// The cash/bank Select only offers asset accounts; 1110 (Cash) is the default.
const CASH_ACCOUNT_TYPE = 'ASSET'
const DEFAULT_CASH_CODE = '1110'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient.get<GLAccount[]>('/api/v1/syerp/gl/accounts').then((r) => r.data)
}

// Only posted invoices carry an AR balance to collect against.
function fetchPostedInvoices(): Promise<InvoiceRead[]> {
  return apiClient
    .get<InvoiceRead[]>('/api/v1/syerp/ar/invoices?status=posted')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 over-application) or a
// validation array of { loc, msg }. Map both to a readable, actionable message.
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
function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

// A money string parsed to integer cents for a decimal-safe ">0" test. Blank /
// non-numeric → 0.
function toCents(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return Math.round(n * 100)
}

// ─── Payload types ───────────────────────────────────────────────────────────

interface ReceiptPayload {
  receipt_date: string
  cash_account_id: number
  reference?: string
  allocations: { invoice_id: string; amount: string }[]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function RecordReceiptDialog({
  open,
  onOpenChange,
  onSuccess,
}: RecordReceiptDialogProps) {
  // ── Options ──
  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const cashAccounts = accounts.filter((a) => a.account_type === CASH_ACCOUNT_TYPE)

  const { data: invoices = [] } = useQuery<InvoiceRead[], Error>({
    queryKey: ['syerp', 'ar', 'invoices', 'posted'],
    queryFn: fetchPostedInvoices,
    enabled: open,
    retry: false,
  })
  // Only invoices that still have an open balance are worth collecting against.
  const openInvoices = invoices.filter((inv) => toCents(inv.open_balance) > 0)

  // ── Form state ──
  const [cashAccountId, setCashAccountId] = useState('')
  const [receiptDate, setReceiptDate] = useState(todayISO)
  const [reference, setReference] = useState('')
  const [checkedInvoices, setCheckedInvoices] = useState<Set<string>>(new Set())
  const [allocAmount, setAllocAmount] = useState<Record<string, string>>({})

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setCashAccountId('')
    setReceiptDate(todayISO())
    setReference('')
    setCheckedInvoices(new Set())
    setAllocAmount({})
  }, [open])

  // ── Default the account to code 1110 (Cash) once loaded; fall back to the first
  //    asset account so shops that renamed the chart still get a sensible default. ──
  useEffect(() => {
    if (!open || cashAccountId) return
    const def = cashAccounts.find((a) => a.code === DEFAULT_CASH_CODE) ?? cashAccounts[0]
    if (def) setCashAccountId(String(def.id))
  }, [open, cashAccountId, cashAccounts])

  // Checking an invoice defaults its allocation to the full open balance.
  function toggleInvoice(inv: InvoiceRead, checked: boolean) {
    setCheckedInvoices((prev) => {
      const next = new Set(prev)
      if (checked) next.add(inv.id)
      else next.delete(inv.id)
      return next
    })
    if (checked) {
      setAllocAmount((prev) => ({
        ...prev,
        [inv.id]: prev[inv.id] ?? inv.open_balance,
      }))
    }
  }

  function updateAmount(invoiceId: string, value: string) {
    setAllocAmount((prev) => ({ ...prev, [invoiceId]: value }))
  }

  // ── Validation: every checked invoice needs an amount > 0 (server rejects
  //    over-application). At least one invoice must be checked. ──
  const checkedList = openInvoices.filter((inv) => checkedInvoices.has(inv.id))
  const allAmountsValid = checkedList.every((inv) => toCents(allocAmount[inv.id] ?? '') > 0)
  const canSubmit = cashAccountId !== '' && checkedList.length > 0 && allAmountsValid

  // ── Mutation ──
  const receiptMutation = useMutation<unknown, Error, ReceiptPayload>({
    mutationFn: (payload) =>
      apiClient.post('/api/v1/syerp/ar/receipts', payload).then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Receipt recorded.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (the backend rejects
      // an over-application with 422).
      toast.error(getApiErrorMessage(err, 'Failed to record the receipt. Please try again.'))
    },
  })

  const isSaving = receiptMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    const allocations = checkedList.map((inv) => ({
      invoice_id: inv.id,
      amount: (allocAmount[inv.id] ?? '').trim(),
    }))
    const payload: ReceiptPayload = {
      receipt_date: receiptDate,
      cash_account_id: Number(cashAccountId),
      ...(reference.trim() ? { reference: reference.trim() } : {}),
      allocations,
    }
    receiptMutation.mutate(payload)
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="record-receipt-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Record Receipt</DialogTitle>
          <DialogDescription id="record-receipt-description">
            Record a cash collection into the chosen cash or bank account, allocated across
            one or more open invoices.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Cash account + date */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="receipt-account">Cash / bank account</Label>
              <Select value={cashAccountId} onValueChange={setCashAccountId}>
                <SelectTrigger id="receipt-account" aria-label="Cash / bank account">
                  <SelectValue placeholder="Select an account" />
                </SelectTrigger>
                <SelectContent>
                  {cashAccounts.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.code} — {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="receipt-date">Receipt date</Label>
              <Input
                id="receipt-date"
                type="date"
                aria-label="Receipt date"
                value={receiptDate}
                onChange={(e) => setReceiptDate(e.target.value)}
              />
            </div>
          </div>

          {/* Reference */}
          <div className="space-y-2">
            <Label htmlFor="receipt-reference">Reference</Label>
            <Input
              id="receipt-reference"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Optional (check / transfer no.)"
            />
          </div>

          {/* Open invoices to allocate against */}
          <div className="space-y-2">
            <Label>Open invoices</Label>
            {openInvoices.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No posted invoices with an open balance.
              </p>
            ) : (
              <div className="space-y-1">
                <div className="grid grid-cols-[2rem_1fr_7rem_8rem] items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span />
                  <span>Invoice</span>
                  <span className="text-right">Open</span>
                  <span className="text-right">Allocate</span>
                </div>
                {openInvoices.map((inv) => {
                  const checked = checkedInvoices.has(inv.id)
                  return (
                    <div
                      key={inv.id}
                      className="grid grid-cols-[2rem_1fr_7rem_8rem] items-center gap-2"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        aria-label={`Allocate to ${inv.invoice_number}`}
                        checked={checked}
                        onChange={(e) => toggleInvoice(inv, e.target.checked)}
                      />
                      <span className="text-sm">{inv.invoice_number}</span>
                      <span className="text-right font-mono text-sm">{inv.open_balance}</span>
                      <Input
                        aria-label={`Allocation amount ${inv.invoice_number}`}
                        inputMode="decimal"
                        className="h-8 text-right"
                        disabled={!checked}
                        value={checked ? (allocAmount[inv.id] ?? '') : ''}
                        onChange={(e) => updateAmount(inv.id, e.target.value)}
                        placeholder={inv.open_balance}
                      />
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
                Recording…
              </>
            ) : (
              'Record Receipt'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
