// ABOUTME: Manual Journal Entry post dialog (Phase 9a, SYERP-12 AC1) — date + memo +
// ABOUTME: a dynamic multi-line debit/credit grid with a live balance footer that gates
// ABOUTME: Post until the entry balances (≥2 lines, each one-sided, debits = credits).

/**
 * JournalEntryDialog — keys and posts a manual GL journal entry.
 *
 * Props:
 *   open / onOpenChange — Radix-controlled visibility
 *   onSuccess: () => void — called after a successful post; the host invalidates
 *              the journal-entries list query so the new entry appears.
 *
 * Fields:
 *   1. Date  — required, defaults to today (YYYY-MM-DD, sent verbatim).
 *   2. Memo  — optional free text.
 *   3. Lines — a dynamic grid; each line has an account Select (options from GET
 *              /api/v1/syerp/gl/accounts), a debit input and a credit input. A line
 *              is valid when it has an account and EXACTLY ONE of debit/credit > 0.
 *              "Add line" appends a blank line; rows past the first two can be removed.
 *
 * Balance footer: totals Debits, Credits and their Difference. Post is disabled unless
 *   there are ≥2 lines, every line is one-sided with an account, and debits === credits.
 *   The comparison is done on integer cents (Math.round(value * 100)) so float noise
 *   never wrongly enables/disables Post — this mirrors the server's 422 balance guard.
 *
 * Mutation: POST /api/v1/syerp/gl/journal-entries
 *   Success: onSuccess() (host invalidates the list), close, toast.
 *   Error (esp. 422 unbalanced / <2 lines / two-sided line): toast.error with the
 *          server `detail` and DO NOT close — let the user fix the input.
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

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface JournalLineDraft {
  key: number
  accountId: string
  debit: string
  credit: string
}

interface JournalEntryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

// Decimal-safe: parse a money string to integer cents so balance comparisons and
// the ">0" one-sided test never trip on float noise. Blank / non-numeric → 0.
function toCents(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return Math.round(n * 100)
}

function formatCents(cents: number): string {
  return (cents / 100).toFixed(2)
}

// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 422 unbalanced entry) or a
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

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient
    .get<GLAccount[]>('/api/v1/syerp/gl/accounts')
    .then((r) => r.data)
}

// A fresh pair of blank lines — a balanced entry needs at least two.
function blankLines(startKey: number): JournalLineDraft[] {
  return [
    { key: startKey, accountId: '', debit: '', credit: '' },
    { key: startKey + 1, accountId: '', debit: '', credit: '' },
  ]
}

// ─── Main component ──────────────────────────────────────────────────────────

export function JournalEntryDialog({ open, onOpenChange, onSuccess }: JournalEntryDialogProps) {
  // ── Account options ──
  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
    enabled: open,
    retry: false,
    staleTime: 60 * 1000,
  })

  // ── Form state ──
  const keyCounter = useRef(0)
  const nextKey = () => {
    const k = keyCounter.current
    keyCounter.current += 2
    return k
  }
  const [entryDate, setEntryDate] = useState(today())
  const [memo, setMemo] = useState('')
  const [lines, setLines] = useState<JournalLineDraft[]>(() => blankLines(nextKey()))

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setEntryDate(today())
    setMemo('')
    setLines(blankLines(nextKey()))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function updateLine(key: number, patch: Partial<JournalLineDraft>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  }

  function addLine() {
    setLines((prev) => [...prev, { key: nextKey(), accountId: '', debit: '', credit: '' }])
  }

  function removeLine(key: number) {
    setLines((prev) => prev.filter((l) => l.key !== key))
  }

  // ── Balance math (integer cents, decimal-safe) ──
  const totalDebitCents = lines.reduce((sum, l) => sum + toCents(l.debit), 0)
  const totalCreditCents = lines.reduce((sum, l) => sum + toCents(l.credit), 0)
  const differenceCents = totalDebitCents - totalCreditCents

  // A line is valid when it has an account and EXACTLY ONE side is > 0.
  const lineValid = (l: JournalLineDraft) => {
    const d = toCents(l.debit)
    const c = toCents(l.credit)
    return l.accountId !== '' && ((d > 0 && c === 0) || (c > 0 && d === 0))
  }
  const allLinesValid = lines.every(lineValid)
  const balanced = differenceCents === 0 && totalDebitCents > 0
  const canPost = lines.length >= 2 && allLinesValid && balanced

  // ── Mutation ──
  interface JournalLinePayload {
    account_id: number
    debit?: string
    credit?: string
  }
  interface JournalEntryPayload {
    entry_date: string
    memo?: string
    lines: JournalLinePayload[]
  }

  const postMutation = useMutation<unknown, Error, JournalEntryPayload>({
    mutationFn: (payload) =>
      apiClient.post('/api/v1/syerp/gl/journal-entries', payload).then((r) => r.data),
    onSuccess: () => {
      onSuccess()
      toast.success('Journal entry posted.')
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can fix the input (the backend rejects
      // unbalanced / <2 line / two-sided entries with 422).
      toast.error(getApiErrorMessage(err, 'Failed to post journal entry. Please try again.'))
    },
  })

  const isSaving = postMutation.isPending

  function handleSubmit() {
    if (!canPost) return
    const payload: JournalEntryPayload = {
      entry_date: entryDate,
      ...(memo.trim() ? { memo: memo.trim() } : {}),
      lines: lines.map((l) => {
        const d = toCents(l.debit)
        return d > 0
          ? { account_id: Number(l.accountId), debit: l.debit.trim() }
          : { account_id: Number(l.accountId), credit: l.credit.trim() }
      }),
    }
    postMutation.mutate(payload)
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="journal-entry-description" className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Journal Entry</DialogTitle>
          <DialogDescription id="journal-entry-description">
            Record a manual balanced journal entry. Each line posts to one account on a
            single side. Post is enabled once debits equal credits across at least two lines.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Date + memo */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="je-date">Date</Label>
              <Input
                id="je-date"
                type="date"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="je-memo">Memo</Label>
              <Input
                id="je-memo"
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="Optional description"
              />
            </div>
          </div>

          {/* Lines grid */}
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_7rem_7rem_2rem] items-center gap-2 text-xs font-medium text-muted-foreground">
              <span>Account</span>
              <span className="text-right">Debit</span>
              <span className="text-right">Credit</span>
              <span />
            </div>
            {lines.map((line, idx) => (
              <div
                key={line.key}
                className="grid grid-cols-[1fr_7rem_7rem_2rem] items-center gap-2"
              >
                <Select
                  value={line.accountId}
                  onValueChange={(v) => updateLine(line.key, { accountId: v })}
                >
                  <SelectTrigger aria-label={`Line ${idx + 1} account`}>
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts.map((a) => (
                      <SelectItem key={a.id} value={String(a.id)}>
                        {a.code} — {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  aria-label={`Line ${idx + 1} debit`}
                  inputMode="decimal"
                  className="text-right"
                  value={line.debit}
                  disabled={toCents(line.credit) > 0}
                  onChange={(e) => updateLine(line.key, { debit: e.target.value })}
                />
                <Input
                  aria-label={`Line ${idx + 1} credit`}
                  inputMode="decimal"
                  className="text-right"
                  value={line.credit}
                  disabled={toCents(line.debit) > 0}
                  onChange={(e) => updateLine(line.key, { credit: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove line ${idx + 1}`}
                  disabled={lines.length <= 2}
                  onClick={() => removeLine(line.key)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addLine}>
              Add line
            </Button>
          </div>

          {/* Balance footer */}
          <div className="grid grid-cols-[1fr_7rem_7rem_2rem] items-center gap-2 border-t border-border pt-3 text-sm font-medium">
            <span className="text-muted-foreground">Totals</span>
            <span className="text-right font-mono" aria-label="Total debits">
              {formatCents(totalDebitCents)}
            </span>
            <span className="text-right font-mono" aria-label="Total credits">
              {formatCents(totalCreditCents)}
            </span>
            <span />
          </div>
          <p
            className={`text-sm ${balanced ? 'text-green-700' : 'text-muted-foreground'}`}
            aria-label="Difference"
          >
            Difference: {formatCents(differenceCents)}
            {balanced ? ' — balanced' : ''}
          </p>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canPost}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Posting…
              </>
            ) : (
              'Post'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
