// ABOUTME: Pay-a-bill dialog (Phase 09b, SYERP-12 AC5) — pick a cash/bank account
// ABOUTME: (defaults to code 1110 Cash), a payment date + amount (capped at the open
// ABOUTME: balance) and an optional reference → POST /api/v1/syerp/ap/payments. 422s toast.

/**
 * PayBillDialog — records a cash disbursement against a single posted bill
 * (SYERP-12 AC5, Phase 09b).
 *
 * Props:
 *   billId: string — the bill this payment is allocated to (allocation target)
 *   openBalance: string — the bill's open balance as an exact Decimal string; the
 *                         amount defaults to (and is capped at) this value
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful payment; the host invalidates
 *              the bill detail + list queries so status/open_balance refresh.
 *
 * Fields:
 *   1. Cash / bank account — required Select (GET /gl/accounts filtered to ASSET). The
 *      option whose code is 1110 (Cash) is selected by default; the seed also ships
 *      1111 Bank – Checking. Resolved to cash_account_id (int) on submit.
 *   2. Payment date — required, defaults to today (YYYY-MM-DD).
 *   3. Amount — required, > 0 and ≤ open_balance (client guard mirrors the server 422;
 *      the submit button is disabled and an inline error shows otherwise). Sent verbatim
 *      as a string so the backend parses it as a Decimal (no JS float mangling — D-11).
 *   4. Reference — optional check/transfer reference (free text).
 *
 * Mutation: POST /api/v1/syerp/ap/payments with
 *   { payment_date, cash_account_id, reference?, allocations:[{ bill_id, amount }] }.
 *   Success: onSuccess() (host invalidates detail + list), close, toast.
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

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface PayBillDialogProps {
  billId: string
  openBalance: string
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

// A money string parsed to integer cents for decimal-safe comparisons. Blank /
// non-numeric → NaN so callers can distinguish "empty" from "0".
function toCents(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return NaN
  return Math.round(n * 100)
}

// ─── Payload types ───────────────────────────────────────────────────────────

interface PaymentPayload {
  payment_date: string
  cash_account_id: number
  reference?: string
  allocations: { bill_id: string; amount: string }[]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PayBillDialog({
  billId,
  openBalance,
  open,
  onOpenChange,
  onSuccess,
}: PayBillDialogProps) {
  // ── Cash/bank account options ──
  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const cashAccounts = accounts.filter((a) => a.account_type === CASH_ACCOUNT_TYPE)

  // ── Form state ──
  const [cashAccountId, setCashAccountId] = useState('')
  const [paymentDate, setPaymentDate] = useState('')
  const [amount, setAmount] = useState('')
  const [reference, setReference] = useState('')

  // ── Reset the form each time the dialog opens; amount defaults to the full open
  //    balance so the common "pay in full" case is one click, and the date to today. ──
  useEffect(() => {
    if (!open) return
    setCashAccountId('')
    setPaymentDate(new Date().toISOString().slice(0, 10))
    setAmount(openBalance)
    setReference('')
  }, [open, openBalance])

  // ── Default the account to code 1110 (Cash) once loaded; fall back to the first
  //    asset account so shops that renamed the chart still get a sensible default. ──
  useEffect(() => {
    if (!open || cashAccountId) return
    const def = cashAccounts.find((a) => a.code === DEFAULT_CASH_CODE) ?? cashAccounts[0]
    if (def) setCashAccountId(String(def.id))
  }, [open, cashAccountId, cashAccounts])

  // ── Validation: amount must be > 0 and ≤ open_balance (mirrors the server 422). ──
  const amountCents = toCents(amount)
  const balanceCents = toCents(openBalance)
  const amountTooHigh =
    Number.isFinite(amountCents) && Number.isFinite(balanceCents) && amountCents > balanceCents
  const amountError = !Number.isFinite(amountCents) || amountCents <= 0 || amountTooHigh
  const accountError = !cashAccountId
  const dateError = paymentDate.trim() === ''
  const formInvalid = amountError || accountError || dateError

  // ── Mutation ──
  const payMutation = useMutation<unknown, Error, PaymentPayload>({
    mutationFn: (payload) =>
      apiClient.post('/api/v1/syerp/ap/payments', payload).then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Payment recorded.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (the backend rejects
      // an over-application with 422).
      toast.error(getApiErrorMessage(err, 'Failed to record payment. Please try again.'))
    },
  })

  const isSaving = payMutation.isPending

  function handleSubmit() {
    if (formInvalid) return
    const payload: PaymentPayload = {
      payment_date: paymentDate,
      cash_account_id: Number(cashAccountId),
      ...(reference.trim() ? { reference: reference.trim() } : {}),
      allocations: [{ bill_id: billId, amount: amount.trim() }],
    }
    payMutation.mutate(payload)
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="pay-bill-description">
        <DialogHeader>
          <DialogTitle>Pay Bill</DialogTitle>
          <DialogDescription id="pay-bill-description">
            Record a cash disbursement against this bill ({openBalance} open). The payment
            posts from the chosen cash or bank account.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Cash / bank account */}
          <div className="space-y-2">
            <Label htmlFor="pay-account">Cash / bank account</Label>
            <Select value={cashAccountId} onValueChange={setCashAccountId}>
              <SelectTrigger id="pay-account" aria-label="Cash / bank account">
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
            {accountError && <p className="text-sm text-destructive">Select an account.</p>}
          </div>

          {/* Payment date */}
          <div className="space-y-2">
            <Label htmlFor="pay-date">Payment date</Label>
            <Input
              id="pay-date"
              type="date"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
            />
          </div>

          {/* Amount */}
          <div className="space-y-2">
            <Label htmlFor="pay-amount">Amount</Label>
            <Input
              id="pay-amount"
              inputMode="decimal"
              className="text-right"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
            />
            {amountTooHigh ? (
              <p className="text-sm text-destructive">
                Amount cannot exceed the open balance ({openBalance}).
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Defaults to the open balance. Paying more than the open balance is rejected.
              </p>
            )}
          </div>

          {/* Reference */}
          <div className="space-y-2">
            <Label htmlFor="pay-reference">Reference</Label>
            <Input
              id="pay-reference"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Optional (check / transfer no.)"
            />
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || formInvalid}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Recording…
              </>
            ) : (
              'Record Payment'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
