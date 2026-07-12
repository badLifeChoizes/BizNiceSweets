// ABOUTME: Create-a-bill dialog (Phase 09b, SYERP-12 AC4) — pick a vendor, check its
// ABOUTME: unbilled receipt lines to match (matched_qty = full unbilled_qty), add non-PO
// ABOUTME: expense/asset lines, then POST /api/v1/syerp/ap/bills. 422s surface a toast.

/**
 * BillCreateDialog — records a vendor bill, matching received purchases and/or adding
 * non-PO expense lines (SYERP-12 AC4, three-way match SC5).
 *
 * Props:
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful create; the host invalidates the
 *              bills list query so the new bill appears.
 *
 * Flow:
 *   1. Vendor — required Select (GET /api/v1/syerp/partners?role=vendor). Selecting a
 *      vendor loads its unbilled receipts (GET /ap/unbilled-receipts?vendor_id=).
 *   2. Vendor invoice ref — optional free text.
 *   3. Unbilled receipt lines — each with a "bill this line" checkbox. Qty + unit cost
 *      are read-only; the exact-match rule is enforced server-side, so a checked line
 *      bills the FULL unbilled_qty (matched_qty is not user-editable here).
 *   4. Non-PO lines — a dynamic grid; each picks an EXPENSE/ASSET account (GET
 *      /gl/accounts, filtered) and a positive amount.
 *
 * Mutation: POST /api/v1/syerp/ap/bills with { vendor_id, vendor_invoice_ref?, lines }
 *   where matched lines are { line_type:'matched', po_line_id, matched_qty } and expense
 *   lines are { line_type:'expense', account_id, amount }.
 *   Success: onSuccess() (host invalidates the list), close, toast.
 *   Error (esp. 422 no lines / exact-match mismatch): toast.error with the server
 *          `detail` and DO NOT close — let the user fix the input.
 */

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2, Trash2 } from 'lucide-react'
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

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface UnbilledReceiptRead {
  po_line_id: string
  po_number: string
  item_id: string
  unbilled_qty: string
  unit_cost: string
}

interface ExpenseLineDraft {
  key: number
  accountId: string
  amount: string
}

interface BillCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// Non-PO lines only post to expense-like accounts.
const NON_PO_ACCOUNT_TYPES = new Set(['EXPENSE', 'ASSET'])

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchVendors(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=vendor')
    .then((r) => r.data)
}

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient.get<GLAccount[]>('/api/v1/syerp/gl/accounts').then((r) => r.data)
}

function fetchUnbilledReceipts(vendorId: string): Promise<UnbilledReceiptRead[]> {
  return apiClient
    .get<UnbilledReceiptRead[]>(`/api/v1/syerp/ap/unbilled-receipts?vendor_id=${vendorId}`)
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 exact-match mismatch) or a
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
// The server defaults bill_date to today when omitted, so this default keeps the
// posted date matching what the user sees unless they pick another date.
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

interface MatchedLinePayload {
  line_type: 'matched'
  po_line_id: string
  matched_qty: string
}
interface ExpenseLinePayload {
  line_type: 'expense'
  account_id: number
  amount: string
}
type BillLinePayload = MatchedLinePayload | ExpenseLinePayload

interface BillCreatePayload {
  vendor_id: string
  vendor_invoice_ref?: string
  bill_date?: string
  lines: BillLinePayload[]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function BillCreateDialog({ open, onOpenChange, onSuccess }: BillCreateDialogProps) {
  // ── Options ──
  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })

  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })
  const nonPoAccounts = accounts.filter((a) => NON_PO_ACCOUNT_TYPES.has(a.account_type))

  // ── Form state ──
  const [vendorId, setVendorId] = useState('')
  const [vendorInvoiceRef, setVendorInvoiceRef] = useState('')
  // Optional bill date (the vendor's invoice date AP aging buckets from). Defaults to
  // today; the server also defaults to today when omitted.
  const [billDate, setBillDate] = useState(todayISO)
  // po_line_ids of the unbilled receipts the user has checked to bill.
  const [checkedLines, setCheckedLines] = useState<Set<string>>(new Set())
  const keyCounter = useRef(0)
  const [expenseLines, setExpenseLines] = useState<ExpenseLineDraft[]>([])

  // Unbilled receipts for the chosen vendor (loaded only once a vendor is picked).
  const { data: unbilled = [], isFetching: unbilledLoading } = useQuery<
    UnbilledReceiptRead[],
    Error
  >({
    queryKey: ['syerp', 'ap', 'unbilled-receipts', { vendorId }],
    queryFn: () => fetchUnbilledReceipts(vendorId),
    enabled: open && vendorId !== '',
    retry: false,
  })

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setVendorId('')
    setVendorInvoiceRef('')
    setBillDate(todayISO())
    setCheckedLines(new Set())
    setExpenseLines([])
  }, [open])

  // ── Changing vendor clears any prior selections (they belonged to another vendor) ──
  function handleVendorChange(id: string) {
    setVendorId(id)
    setCheckedLines(new Set())
  }

  function toggleLine(poLineId: string, checked: boolean) {
    setCheckedLines((prev) => {
      const next = new Set(prev)
      if (checked) next.add(poLineId)
      else next.delete(poLineId)
      return next
    })
  }

  function addExpenseLine() {
    const key = keyCounter.current
    keyCounter.current += 1
    setExpenseLines((prev) => [...prev, { key, accountId: '', amount: '' }])
  }

  function updateExpenseLine(key: number, patch: Partial<ExpenseLineDraft>) {
    setExpenseLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function removeExpenseLine(key: number) {
    setExpenseLines((prev) => prev.filter((l) => l.key !== key))
  }

  // ── Validation ──
  const expenseLineValid = (l: ExpenseLineDraft) => l.accountId !== '' && toCents(l.amount) > 0
  const allExpenseValid = expenseLines.every(expenseLineValid)
  const hasAnyLine = checkedLines.size > 0 || expenseLines.length > 0
  const canSubmit = vendorId !== '' && hasAnyLine && allExpenseValid

  // ── Mutation ──
  const createMutation = useMutation<unknown, Error, BillCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post('/api/v1/syerp/ap/bills', payload).then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Bill created.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input (the backend rejects
      // an empty bill or an inexact match with 422).
      toast.error(getApiErrorMessage(err, 'Failed to create the bill. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    const matchedLines: BillLinePayload[] = unbilled
      .filter((u) => checkedLines.has(u.po_line_id))
      .map((u) => ({
        line_type: 'matched',
        po_line_id: u.po_line_id,
        matched_qty: u.unbilled_qty,
      }))
    const expensePayload: BillLinePayload[] = expenseLines.map((l) => ({
      line_type: 'expense',
      account_id: Number(l.accountId),
      amount: l.amount.trim(),
    }))
    const payload: BillCreatePayload = {
      vendor_id: vendorId,
      ...(vendorInvoiceRef.trim() ? { vendor_invoice_ref: vendorInvoiceRef.trim() } : {}),
      ...(billDate ? { bill_date: billDate } : {}),
      lines: [...matchedLines, ...expensePayload],
    }
    createMutation.mutate(payload)
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="bill-create-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Bill</DialogTitle>
          <DialogDescription id="bill-create-description">
            Record a vendor bill. Check received lines to match against purchases, and add
            non-PO lines for expenses. Matched lines bill the full outstanding quantity.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Vendor + invoice ref */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="bill-vendor">Vendor</Label>
              <Select value={vendorId} onValueChange={handleVendorChange}>
                <SelectTrigger id="bill-vendor" aria-label="Vendor">
                  <SelectValue placeholder="Select a vendor" />
                </SelectTrigger>
                <SelectContent>
                  {vendors.map((v) => (
                    <SelectItem key={v.id} value={v.id}>
                      {v.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bill-invoice-ref">Vendor invoice ref</Label>
              <Input
                id="bill-invoice-ref"
                value={vendorInvoiceRef}
                onChange={(e) => setVendorInvoiceRef(e.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bill-date">Bill date</Label>
              <Input
                id="bill-date"
                type="date"
                aria-label="Bill date"
                value={billDate}
                onChange={(e) => setBillDate(e.target.value)}
              />
            </div>
          </div>

          {/* Unbilled receipt lines */}
          <div className="space-y-2">
            <Label>Unbilled receipts</Label>
            {vendorId === '' ? (
              <p className="text-sm text-muted-foreground">Select a vendor to load receipts.</p>
            ) : unbilledLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : unbilled.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No unbilled receipts for this vendor.
              </p>
            ) : (
              <div className="space-y-1">
                <div className="grid grid-cols-[2rem_1fr_6rem_7rem] items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span />
                  <span>PO</span>
                  <span className="text-right">Qty</span>
                  <span className="text-right">Unit cost</span>
                </div>
                {unbilled.map((u) => (
                  <div
                    key={u.po_line_id}
                    className="grid grid-cols-[2rem_1fr_6rem_7rem] items-center gap-2"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      aria-label={`Bill line ${u.po_number}`}
                      checked={checkedLines.has(u.po_line_id)}
                      onChange={(e) => toggleLine(u.po_line_id, e.target.checked)}
                    />
                    <span className="text-sm">{u.po_number}</span>
                    <span className="text-right font-mono text-sm">{u.unbilled_qty}</span>
                    <span className="text-right font-mono text-sm">{u.unit_cost}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Non-PO expense lines */}
          <div className="space-y-2">
            <Label>Non-PO lines</Label>
            {expenseLines.length > 0 && (
              <div className="grid grid-cols-[1fr_8rem_2rem] items-center gap-2 text-xs font-medium text-muted-foreground">
                <span>Account</span>
                <span className="text-right">Amount</span>
                <span />
              </div>
            )}
            {expenseLines.map((line, idx) => (
              <div key={line.key} className="grid grid-cols-[1fr_8rem_2rem] items-center gap-2">
                <Select
                  value={line.accountId}
                  onValueChange={(v) => updateExpenseLine(line.key, { accountId: v })}
                >
                  <SelectTrigger aria-label={`Non-PO line ${idx + 1} account`}>
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {nonPoAccounts.map((a) => (
                      <SelectItem key={a.id} value={String(a.id)}>
                        {a.code} — {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  aria-label={`Non-PO line ${idx + 1} amount`}
                  inputMode="decimal"
                  className="text-right"
                  value={line.amount}
                  onChange={(e) => updateExpenseLine(line.key, { amount: e.target.value })}
                  placeholder="0.00"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove non-PO line ${idx + 1}`}
                  onClick={() => removeExpenseLine(line.key)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addExpenseLine}>
              Add non-PO line
            </Button>
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
              'Create Bill'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
