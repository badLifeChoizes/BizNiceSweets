// ABOUTME: SYERP Financial Reports screen (/syerp/reports) — a tabbed page hosting the
// ABOUTME: Trial Balance, Profit & Loss, and Balance Sheet reports over the read-only
// ABOUTME: /api/v1/syerp/reports endpoints, with shared date controls (SC3, SC4, SC5, AC7).

/**
 * FinancialReports screen — SYERP financial statements (SYERP-13, Phase 09c).
 *
 * Layout: p-8 space-y-6 (matches AccountRegister / JournalEntries), SyerpNav strip.
 *
 * Tabs: no shadcn `tabs` primitive exists in the repo, so the three sub-reports are
 *   switched via a small Button toggle group (active = variant="default", inactive =
 *   variant="outline"), matching the accent-button convention used across SYERP.
 *
 *   - Trial Balance — an "As of" date; GET /reports/trial-balance. Account rows
 *     (code, name, debit, credit) with a totals footer (total_debit / total_credit)
 *     and an in-balance indicator.
 *   - Profit & Loss — a from/to range; GET /reports/profit-loss. Revenue and Expense
 *     sections (lines + section total) and a Net Income line.
 *   - Balance Sheet — an "As of" date; GET /reports/balance-sheet. Assets / Liabilities
 *     / Equity sections (lines + section total, equity including the API's current-year
 *     net-income line) and a balanced Assets == Liabilities + Equity total.
 *
 * Only the active tab's query runs (enabled: tab === …); query keys carry the relevant
 * dates. The "As of" date is shared by Trial Balance and Balance Sheet.
 *
 * All money is rendered verbatim from the server's exact decimal strings (font-mono),
 * never float math (D-11) — the same convention as Bills / AccountRegister.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

/** A code/name-tagged Decimal amount (as an exact string) — used by P&L and BS lines. */
interface ReportLine {
  account_id: number
  code: string
  name: string
  amount: string
}

interface TrialBalanceRow {
  account_id: number
  code: string
  name: string
  account_type: string
  debit: string
  credit: string
}

interface TrialBalanceReport {
  as_of: string
  rows: TrialBalanceRow[]
  total_debit: string
  total_credit: string
  in_balance: boolean
}

interface ProfitLossReport {
  date_from: string
  date_to: string
  revenue: ReportLine[]
  total_revenue: string
  expense: ReportLine[]
  total_expense: string
  net_income: string
}

interface BalanceSheetReport {
  as_of: string
  assets: ReportLine[]
  total_assets: string
  liabilities: ReportLine[]
  total_liabilities: string
  equity: ReportLine[]
  total_equity: string
  in_balance: boolean
}

type ReportTab = 'trial-balance' | 'profit-loss' | 'balance-sheet'

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Today as an ISO date (YYYY-MM-DD) for the default "as of" / range end.
function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Balanced / out-of-balance indicator — color AND text together (never color alone). */
function BalanceBadge({ inBalance }: { inBalance: boolean }) {
  return inBalance ? (
    <Badge variant="outline" className="border-green-300 bg-green-50 text-green-700">
      Balanced
    </Badge>
  ) : (
    <Badge variant="outline" className="border-red-300 bg-red-50 text-red-700">
      Out of balance
    </Badge>
  )
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchTrialBalance(asOf: string): Promise<TrialBalanceReport> {
  return apiClient
    .get<TrialBalanceReport>('/api/v1/syerp/reports/trial-balance', { params: { as_of: asOf } })
    .then((r) => r.data)
}

function fetchProfitLoss(from: string, to: string): Promise<ProfitLossReport> {
  return apiClient
    .get<ProfitLossReport>('/api/v1/syerp/reports/profit-loss', { params: { from, to } })
    .then((r) => r.data)
}

function fetchBalanceSheet(asOf: string): Promise<BalanceSheetReport> {
  return apiClient
    .get<BalanceSheetReport>('/api/v1/syerp/reports/balance-sheet', { params: { as_of: asOf } })
    .then((r) => r.data)
}

// ─── Shared UI ───────────────────────────────────────────────────────────────

function Loading() {
  return (
    <div className="flex justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}

function LoadError({ what }: { what: string }) {
  return (
    <div className="text-center py-12">
      <p className="text-sm text-muted-foreground">
        Failed to load the {what}. Check your connection and refresh the page.
      </p>
    </div>
  )
}

// A labelled section of amount lines with a section total (P&L and Balance Sheet).
function AmountSection({
  title,
  lines,
  total,
  totalLabel,
}: {
  title: string
  lines: ReportLine[]
  total: string
  totalLabel: string
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">Code</TableHead>
            <TableHead>Account</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.length === 0 ? (
            <TableRow>
              <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">
                No accounts.
              </TableCell>
            </TableRow>
          ) : (
            lines.map((line) => (
              <TableRow key={line.account_id} className="h-10">
                <TableCell className="font-mono">{line.code}</TableCell>
                <TableCell>{line.name}</TableCell>
                <TableCell className="text-right font-mono">{line.amount}</TableCell>
              </TableRow>
            ))
          )}
          <TableRow className="border-t-2 font-semibold">
            <TableCell colSpan={2}>{totalLabel}</TableCell>
            <TableCell className="text-right font-mono">{total}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  )
}

// ─── Report bodies ───────────────────────────────────────────────────────────

function TrialBalanceBody({ asOf }: { asOf: string }) {
  const { data, isLoading, isError } = useQuery<TrialBalanceReport, Error>({
    queryKey: ['syerp', 'reports', 'trial-balance', asOf],
    queryFn: () => fetchTrialBalance(asOf),
  })

  if (isLoading) return <Loading />
  if (isError || !data) return <LoadError what="trial balance" />

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-32">Code</TableHead>
            <TableHead>Account</TableHead>
            <TableHead className="text-right">Debit</TableHead>
            <TableHead className="text-right">Credit</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row) => (
            <TableRow key={row.account_id} className="h-10">
              <TableCell className="font-mono">{row.code}</TableCell>
              <TableCell>{row.name}</TableCell>
              <TableCell className="text-right font-mono">{row.debit}</TableCell>
              <TableCell className="text-right font-mono">{row.credit}</TableCell>
            </TableRow>
          ))}
          <TableRow className="border-t-2 font-semibold">
            <TableCell colSpan={2}>Totals</TableCell>
            <TableCell className="text-right font-mono">{data.total_debit}</TableCell>
            <TableCell className="text-right font-mono">{data.total_credit}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <div className="flex justify-end">
        <BalanceBadge inBalance={data.in_balance} />
      </div>
    </div>
  )
}

function ProfitLossBody({ from, to }: { from: string; to: string }) {
  const { data, isLoading, isError } = useQuery<ProfitLossReport, Error>({
    queryKey: ['syerp', 'reports', 'profit-loss', from, to],
    queryFn: () => fetchProfitLoss(from, to),
  })

  if (isLoading) return <Loading />
  if (isError || !data) return <LoadError what="profit and loss report" />

  return (
    <div className="space-y-6">
      <AmountSection
        title="Revenue"
        lines={data.revenue}
        total={data.total_revenue}
        totalLabel="Total Revenue"
      />
      <AmountSection
        title="Expenses"
        lines={data.expense}
        total={data.total_expense}
        totalLabel="Total Expenses"
      />
      <div className="flex justify-between border-t-2 border-border pt-3 text-base font-semibold">
        <span>Net Income</span>
        <span className="font-mono">{data.net_income}</span>
      </div>
    </div>
  )
}

function BalanceSheetBody({ asOf }: { asOf: string }) {
  const { data, isLoading, isError } = useQuery<BalanceSheetReport, Error>({
    queryKey: ['syerp', 'reports', 'balance-sheet', asOf],
    queryFn: () => fetchBalanceSheet(asOf),
  })

  if (isLoading) return <Loading />
  if (isError || !data) return <LoadError what="balance sheet" />

  return (
    <div className="space-y-6">
      <AmountSection
        title="Assets"
        lines={data.assets}
        total={data.total_assets}
        totalLabel="Total Assets"
      />
      <AmountSection
        title="Liabilities"
        lines={data.liabilities}
        total={data.total_liabilities}
        totalLabel="Total Liabilities"
      />
      <AmountSection
        title="Equity"
        lines={data.equity}
        total={data.total_equity}
        totalLabel="Total Equity"
      />
      <div className="flex items-center justify-between border-t-2 border-border pt-3 text-base font-semibold">
        <span>Assets vs. Liabilities + Equity</span>
        <BalanceBadge inBalance={data.in_balance} />
      </div>
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

const TABS: Array<{ id: ReportTab; label: string }> = [
  { id: 'trial-balance', label: 'Trial Balance' },
  { id: 'profit-loss', label: 'Profit & Loss' },
  { id: 'balance-sheet', label: 'Balance Sheet' },
]

export function FinancialReports() {
  const [tab, setTab] = useState<ReportTab>('trial-balance')
  // Shared "as of" date drives Trial Balance and Balance Sheet.
  const [asOf, setAsOf] = useState(today())
  // P&L period range.
  const [from, setFrom] = useState('')
  const [to, setTo] = useState(today())

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Financial Reports</h1>
        <p className="text-sm font-normal text-muted-foreground">
          Trial balance, profit &amp; loss, and balance sheet, generated from the general
          ledger for the selected dates.
        </p>
      </div>

      {/* Tab toggle group (no shadcn tabs primitive — accent-button convention) */}
      <div className="flex gap-2" role="tablist" aria-label="Financial reports">
        {TABS.map((t) => (
          <Button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            variant={tab === t.id ? 'default' : 'outline'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {/* Date controls — relevant to the active tab */}
      {tab === 'profit-loss' ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="fr-from">From</Label>
            <Input
              id="fr-from"
              type="date"
              aria-label="From date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="fr-to">To</Label>
            <Input
              id="fr-to"
              type="date"
              aria-label="To date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="fr-as-of">As of</Label>
            <Input
              id="fr-as-of"
              type="date"
              aria-label="As of date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
            />
          </div>
        </div>
      )}

      {/* Active report */}
      {tab === 'trial-balance' && <TrialBalanceBody asOf={asOf} />}
      {tab === 'profit-loss' && <ProfitLossBody from={from} to={to} />}
      {tab === 'balance-sheet' && <BalanceSheetBody asOf={asOf} />}
    </div>
  )
}
