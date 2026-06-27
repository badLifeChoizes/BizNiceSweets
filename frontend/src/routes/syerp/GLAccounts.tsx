/**
 * Chart of Accounts browse screen — SYERP GL account structure (/syerp/gl).
 *
 * Read-only by design (D-11 scope guard). No toolbar, no mutation controls,
 * no accent elements anywhere on this screen.
 *
 * Layout: p-8 space-y-6 — matches other SYERP screens.
 *
 * Renders the seeded flat GL account list as 5 grouped Cards, one per
 * account_type (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE). Within each
 * card, top-level (round-hundred) accounts are bold; sub-accounts are
 * indented with pl-6.
 *
 * Data: useQuery(['syerp','gl','accounts']) — GET /api/v1/syerp/gl/accounts.
 * Response: GLAccount[] — flat list ordered by code; grouping is frontend-side.
 *
 * Accessibility rule 8: account rows are plain div elements, not interactive.
 */

import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string // 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE'
  parent_id: number | null
  active: boolean
}

// ─── Constants ───────────────────────────────────────────────────────────────

const ACCOUNT_TYPE_ORDER: string[] = [
  'ASSET',
  'LIABILITY',
  'EQUITY',
  'REVENUE',
  'EXPENSE',
]

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  ASSET: 'Assets',
  LIABILITY: 'Liabilities',
  EQUITY: 'Equity',
  REVENUE: 'Revenue',
  EXPENSE: 'Expenses',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Derive the code range label for a card's CardDescription.
 * Takes min and max account codes in the group (e.g. "1000–1999").
 */
function codeRange(accounts: GLAccount[]): string {
  if (accounts.length === 0) return ''
  const codes = accounts.map((a) => a.code).sort()
  return `${codes[0]}–${codes[codes.length - 1]}`
}

/**
 * True when a code ends in one or more zeros, making it a "round-hundred"
 * top-level group account. Examples: "1000", "1100", "2000", "5100".
 * Sub-accounts: "1110", "1120", "5110" — these get pl-6 indent.
 */
function isTopLevel(code: string): boolean {
  return /0+$/.test(code)
}

// ─── API helper ──────────────────────────────────────────────────────────────

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient
    .get<GLAccount[]>('/api/v1/syerp/gl/accounts')
    .then((r) => r.data)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function GLAccounts() {
  const {
    data: accounts = [],
    isLoading,
    isError,
  } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
  })

  // Group accounts by account_type for rendering
  const groupedAccounts: Record<string, GLAccount[]> = {}
  for (const account of accounts) {
    if (!groupedAccounts[account.account_type]) {
      groupedAccounts[account.account_type] = []
    }
    groupedAccounts[account.account_type].push(account)
  }

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Chart of Accounts</h1>
        <p className="text-sm font-normal text-muted-foreground">
          General ledger account structure. Read-only in this version.
        </p>
      </div>

      {/* Loading state */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        /* Error state */
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load accounts. Check your connection and refresh the page.
          </p>
        </div>
      ) : (
        /* 5 account-type cards — rendered in canonical order */
        <div className="space-y-4">
          {ACCOUNT_TYPE_ORDER.map((type) => {
            const typeAccounts = groupedAccounts[type] ?? []
            if (typeAccounts.length === 0) return null

            return (
              <Card key={type}>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">
                    {ACCOUNT_TYPE_LABELS[type] ?? type}
                  </CardTitle>
                  <CardDescription>{codeRange(typeAccounts)}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {typeAccounts.map((account) => (
                      /* Accessibility rule 8: plain div, not interactive */
                      <div
                        key={account.id}
                        className={`flex items-center gap-3 py-1.5${
                          isTopLevel(account.code) ? '' : ' pl-6'
                        }`}
                      >
                        <span className="text-sm font-mono text-muted-foreground w-14 shrink-0">
                          {account.code}
                        </span>
                        <span
                          className={`text-sm text-foreground${
                            isTopLevel(account.code) ? ' font-semibold' : ''
                          }`}
                        >
                          {account.name}
                        </span>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {account.account_type}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
