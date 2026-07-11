// ABOUTME: SYERP Account Register screen (/syerp/gl/register) — pick a GL account plus an
// ABOUTME: optional from/to date range and view its postings with debit/credit/running-balance
// ABOUTME: columns bracketed by the period's opening and closing balances (SYERP-12 AC2).

/**
 * AccountRegister screen — a per-account general-ledger register (SYERP-12 AC2).
 *
 * Layout: p-8 space-y-6 (matches GLAccounts / JournalEntries), SyerpNav strip.
 *
 * Controls: an account Select (options from GET /api/v1/syerp/gl/accounts) and two
 *   optional date inputs (from / to). The register query only runs once an account is
 *   chosen (enabled: !!accountId); the dates are passed straight through as query params.
 *
 * Table columns: Date | Memo | Debit | Credit | Balance. The period's opening balance is
 *   shown above the table and its closing balance below; the running balance walks the
 *   opening figure line by line. All money is rendered verbatim from the server's exact
 *   decimal strings — no float math ever touches it.
 *
 * Data: GET /api/v1/syerp/gl/accounts/{id}/register?from=&to= — AccountRegisterRead.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface AccountRegisterRow {
  entry_date: string
  entry_id: string
  memo: string | null
  debit: string | null
  credit: string | null
  running_balance: string
}

interface AccountRegisterRead {
  account_id: number
  account_code: string
  account_name: string
  opening_balance: string
  closing_balance: string
  rows: AccountRegisterRow[]
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

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient
    .get<GLAccount[]>('/api/v1/syerp/gl/accounts')
    .then((r) => r.data)
}

function fetchRegister(
  accountId: string,
  from: string,
  to: string,
): Promise<AccountRegisterRead> {
  const params: Record<string, string> = {}
  if (from) params.from = from
  if (to) params.to = to
  return apiClient
    .get<AccountRegisterRead>(`/api/v1/syerp/gl/accounts/${accountId}/register`, { params })
    .then((r) => r.data)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function AccountRegister() {
  const [accountId, setAccountId] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
    staleTime: 60 * 1000,
  })

  const {
    data: register,
    isLoading,
    isError,
  } = useQuery<AccountRegisterRead, Error>({
    queryKey: ['syerp', 'gl', 'register', accountId, from, to],
    queryFn: () => fetchRegister(accountId, from, to),
    enabled: !!accountId,
  })

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Account Register</h1>
        <p className="text-sm font-normal text-muted-foreground">
          Postings for a single general-ledger account, with a running balance over the
          selected date range.
        </p>
      </div>

      {/* Controls: account picker + optional date range */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="ar-account">Account</Label>
          <Select value={accountId} onValueChange={setAccountId}>
            <SelectTrigger id="ar-account" aria-label="Account">
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
        </div>
        <div className="space-y-2">
          <Label htmlFor="ar-from">From</Label>
          <Input
            id="ar-from"
            type="date"
            aria-label="From date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="ar-to">To</Label>
          <Input
            id="ar-to"
            type="date"
            aria-label="To date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>

      {/* Register / prompt / loading / states */}
      {!accountId ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Select an account to view its register.
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError || !register ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load the register. Check your connection and refresh the page.
          </p>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold">
              {register.account_code} — {register.account_name}
            </CardTitle>
            <CardDescription>Opening balance: {register.opening_balance}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {register.rows.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                No postings in the selected range.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Memo</TableHead>
                    <TableHead className="text-right">Debit</TableHead>
                    <TableHead className="text-right">Credit</TableHead>
                    <TableHead className="text-right">Balance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {register.rows.map((row) => (
                    <TableRow key={row.entry_id} className="h-12">
                      <TableCell className="font-medium">{formatDate(row.entry_date)}</TableCell>
                      <TableCell>{row.memo ?? '—'}</TableCell>
                      <TableCell className="text-right font-mono">{row.debit ?? '—'}</TableCell>
                      <TableCell className="text-right font-mono">{row.credit ?? '—'}</TableCell>
                      <TableCell className="text-right font-mono">{row.running_balance}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <div className="flex justify-end border-t border-border pt-3 text-sm font-medium">
              <span>Closing balance: {register.closing_balance}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
