// ABOUTME: SYERP manual Journal Entries list screen (/syerp/gl/journal-entries) —
// ABOUTME: date, memo, source and line count over /api/v1/syerp/gl/journal-entries, with
// ABOUTME: a "New journal entry" button opening JournalEntryDialog to post a balanced entry.

/**
 * JournalEntries screen — SYERP general-ledger journal list (SYERP-12 AC1).
 *
 * Layout: p-8 space-y-6 (matches GLAccounts / PurchaseOrders pattern), SyerpNav strip.
 *
 * Toolbar: a single "New journal entry" Button (variant="default" — the only accent
 *   element) that opens JournalEntryDialog. On a successful post the dialog fires
 *   onSuccess, which invalidates the list query so the new entry appears.
 *
 * Table columns: Date | Memo | Source | Lines. Each line's debit/credit is an exact
 * Decimal string; the roll-up column shows the entry's total debits, rendered from
 * integer cents so no float math ever touches money.
 *
 * Data: GET /api/v1/syerp/gl/journal-entries — JournalEntryRead[], newest first.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'
import { JournalEntryDialog } from './components/JournalEntryDialog'

// ─── Types ───────────────────────────────────────────────────────────────────

interface JournalLineRead {
  id: string
  line_no: number
  account_id: number
  debit: string | null
  credit: string | null
}

/** Journal-entry header + lines as returned by GET /syerp/gl/journal-entries. */
export interface JournalEntryRead {
  id: string
  entry_date: string
  memo: string | null
  source_type: string | null
  source_id: string | null
  reversal_of_id: string | null
  actor_id: string
  created_at: string
  lines: JournalLineRead[]
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

// Total debits for an entry, summed in integer cents so money never sees a float.
function totalDebits(entry: JournalEntryRead): string {
  const cents = entry.lines.reduce((sum, l) => {
    const n = Number(l.debit ?? '0')
    return sum + (Number.isFinite(n) ? Math.round(n * 100) : 0)
  }, 0)
  return (cents / 100).toFixed(2)
}

function fetchJournalEntries(): Promise<JournalEntryRead[]> {
  return apiClient
    .get<JournalEntryRead[]>('/api/v1/syerp/gl/journal-entries')
    .then((r) => r.data)
}

// Surface the server's real reason (FastAPI string/array `detail`) over a generic message.
function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  return fallback
}

// ─── Main component ──────────────────────────────────────────────────────────

export function JournalEntries() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  // The entry a "Reverse" click is confirming against; null when the confirm is closed.
  const [reverseTarget, setReverseTarget] = useState<JournalEntryRead | null>(null)

  const {
    data: entries = [],
    isLoading,
    isError,
  } = useQuery<JournalEntryRead[], Error>({
    queryKey: ['syerp', 'gl', 'journal-entries'],
    queryFn: fetchJournalEntries,
  })

  // Reversal is append-only: it POSTs a new offsetting entry (reversal_of_id = the
  // original) and never mutates or removes the original client-side — we only
  // invalidate so the newly-created reversal is fetched into the list.
  const reverseMutation = useMutation<JournalEntryRead, Error, string>({
    mutationFn: (id) =>
      apiClient
        .post<JournalEntryRead>(`/api/v1/syerp/gl/journal-entries/${id}/reverse`, {})
        .then((r) => r.data),
    onSuccess: () => {
      toast.success('Journal entry reversed.')
      queryClient.invalidateQueries({ queryKey: ['syerp', 'gl', 'journal-entries'] })
      setReverseTarget(null)
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to reverse the entry. Please try again.'))
    },
  })

  // Ids of entries that a reversal already points at — those are already reversed,
  // so their "Reverse" action is disabled to avoid a double reversal.
  const reversedIds = new Set(
    entries.map((e) => e.reversal_of_id).filter((id): id is string => id !== null),
  )

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Journal Entries</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manual general-ledger entries. Every entry is balanced and audited.
        </p>
      </div>

      {/* Toolbar: the "New journal entry" button is the only accent element */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setDialogOpen(true)}>
          New journal entry
        </Button>
      </div>

      {/* Table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load journal entries. Check your connection and refresh the page.
          </p>
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No journal entries yet</p>
          <p className="text-sm text-muted-foreground">
            Post your first manual journal entry to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Memo</TableHead>
              <TableHead>Source</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="text-right">Lines</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const isReversal = entry.reversal_of_id !== null
              const alreadyReversed = reversedIds.has(entry.id)
              return (
                <TableRow key={entry.id} className="h-12">
                  <TableCell className="font-medium">{formatDate(entry.entry_date)}</TableCell>
                  <TableCell>{entry.memo ?? '—'}</TableCell>
                  <TableCell>{entry.source_type ?? 'Manual'}</TableCell>
                  <TableCell className="text-right font-mono">{totalDebits(entry)}</TableCell>
                  <TableCell className="text-right">{entry.lines.length}</TableCell>
                  <TableCell className="text-right">
                    {isReversal ? (
                      <span className="text-xs text-muted-foreground">Reversal</span>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={alreadyReversed || reverseMutation.isPending}
                        onClick={() => setReverseTarget(entry)}
                      >
                        {alreadyReversed ? 'Reversed' : 'Reverse'}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      <JournalEntryDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSuccess={() =>
          queryClient.invalidateQueries({ queryKey: ['syerp', 'gl', 'journal-entries'] })
        }
      />

      {/* Reverse confirmation — reversal posts a new offsetting entry; the original is
          left untouched (audit-safe, append-only). */}
      <Dialog
        open={reverseTarget !== null}
        onOpenChange={(open) => {
          if (!open) setReverseTarget(null)
        }}
      >
        <DialogContent aria-describedby="reverse-entry-description">
          <DialogHeader>
            <DialogTitle>Reverse journal entry</DialogTitle>
            <DialogDescription id="reverse-entry-description">
              This posts a new offsetting entry with swapped debits and credits. The original
              entry is preserved for the audit trail and is not changed or deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setReverseTarget(null)}
              disabled={reverseMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="default"
              onClick={() => reverseTarget && reverseMutation.mutate(reverseTarget.id)}
              disabled={reverseMutation.isPending}
            >
              {reverseMutation.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Reversing…
                </>
              ) : (
                'Reverse entry'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
