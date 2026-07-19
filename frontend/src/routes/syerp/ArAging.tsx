// ABOUTME: SYERP Accounts Receivable Aging screen (/syerp/ar/aging) — customer open balances
// ABOUTME: bucketed by age (current / 31–60 / 61–90 / 90+) as of a chosen date over
// ABOUTME: /api/v1/syerp/ar/aging, with a grand-total footer and a 1120 tie-out badge (SYERP-13).

/**
 * ArAging screen — SYERP accounts-receivable aging report (SYERP-13, Phase 13).
 *
 * Layout: p-8 space-y-6 (mirrors ApAging), SyerpNav strip.
 *
 * Controls: an "As of" date Input (defaults to today) that drives the query — the date is
 *   in the query key, so changing it refetches the report for the new cut-off.
 *
 * Table columns: Customer | Current | 31–60 | 61–90 | 90+ | Total, one row per customer, plus
 *   a grand-total footer row. All money is rendered verbatim from the server's exact decimal
 *   strings — no float math ever touches it (D-11).
 *
 * Tie-out: a Badge renders `in_balance` — green when the aging grand total ties to the 1120
 *   Accounts-Receivable control account, a destructive style when it does not. The control
 *   balance is surfaced alongside so a mismatch is diagnosable.
 *
 * Data: GET /api/v1/syerp/ar/aging?as_of=YYYY-MM-DD — ArAgingReport.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'

// ─── Types ───────────────────────────────────────────────────────────────────

/** Aging buckets shared by each customer row and the grand total. Money = exact strings. */
interface ArAgingBuckets {
  current: string
  d31_60: string
  d61_90: string
  d90_plus: string
  total: string
}

interface ArAgingCustomerRow extends ArAgingBuckets {
  customer_id: string
  customer_name: string
}

/** AR aging report as returned by GET /syerp/ar/aging. */
interface ArAgingReport {
  as_of: string
  customers: ArAgingCustomerRow[]
  grand_total: ArAgingBuckets
  control_balance: string
  in_balance: boolean
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Today as YYYY-MM-DD in the local timezone (the <input type="date"> value format).
function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchAging(asOf: string): Promise<ArAgingReport> {
  return apiClient
    .get<ArAgingReport>('/api/v1/syerp/ar/aging', { params: { as_of: asOf } })
    .then((r) => r.data)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ArAging() {
  const [asOf, setAsOf] = useState(todayISO)

  const {
    data: report,
    isLoading,
    isError,
  } = useQuery<ArAgingReport, Error>({
    queryKey: ['syerp', 'ar', 'aging', asOf],
    queryFn: () => fetchAging(asOf),
    enabled: !!asOf,
  })

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">AR Aging</h1>
        <p className="text-base font-normal text-muted-foreground">
          Open customer balances bucketed by age as of the selected date.
        </p>
      </div>

      {/* Controls: the "As of" date drives the report */}
      <div className="flex items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="aging-as-of">As of</Label>
          <Input
            id="aging-as-of"
            type="date"
            aria-label="As of date"
            className="w-auto"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
          />
        </div>
        {report && (
          <Badge
            variant="outline"
            className={
              report.in_balance
                ? 'border-green-300 bg-green-50 text-green-700'
                : 'border-destructive bg-destructive/10 text-destructive'
            }
          >
            {report.in_balance
              ? `In balance — ties to 1120 (${report.control_balance})`
              : `Out of balance — 1120 control is ${report.control_balance}`}
          </Badge>
        )}
      </div>

      {/* Table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError || !report ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load the aging report. Check your connection and refresh the page.
          </p>
        </div>
      ) : report.customers.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No open balances</p>
          <p className="text-sm text-muted-foreground">
            No customer has an outstanding balance as of this date.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead className="text-right">Current</TableHead>
              <TableHead className="text-right">31–60</TableHead>
              <TableHead className="text-right">61–90</TableHead>
              <TableHead className="text-right">90+</TableHead>
              <TableHead className="text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.customers.map((c) => (
              <TableRow key={c.customer_id} className="h-12">
                <TableCell className="font-medium">{c.customer_name}</TableCell>
                <TableCell className="text-right font-mono">{c.current}</TableCell>
                <TableCell className="text-right font-mono">{c.d31_60}</TableCell>
                <TableCell className="text-right font-mono">{c.d61_90}</TableCell>
                <TableCell className="text-right font-mono">{c.d90_plus}</TableCell>
                <TableCell className="text-right font-mono">{c.total}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell className="font-semibold">Grand total</TableCell>
              <TableCell className="text-right font-mono font-semibold">
                {report.grand_total.current}
              </TableCell>
              <TableCell className="text-right font-mono font-semibold">
                {report.grand_total.d31_60}
              </TableCell>
              <TableCell className="text-right font-mono font-semibold">
                {report.grand_total.d61_90}
              </TableCell>
              <TableCell className="text-right font-mono font-semibold">
                {report.grand_total.d90_plus}
              </TableCell>
              <TableCell className="text-right font-mono font-semibold">
                {report.grand_total.total}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      )}
    </div>
  )
}
