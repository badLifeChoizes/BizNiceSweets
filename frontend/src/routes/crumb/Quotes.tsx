// ABOUTME: CRUMB Quotes list screen (/crumb/quotes) — a table of quotes (number, customer,
// ABOUTME: status) over /api/v1/crumb/quotes with a "New quote" create dialog. Rows navigate
// ABOUTME: to the quote builder / detail screen (CRUMB-01).

/**
 * Quotes screen — the CRUMB quote-header list (/crumb/quotes).
 *
 * Layout: p-8 space-y-6 (matches the other module list screens).
 *
 * Table columns: Quote # | Customer | Status
 *
 * QuoteRead carries only partner_id, so customers are fetched once and mapped
 * id→name client-side. Row click navigates to /crumb/quotes/{id} (the builder).
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CrumbNav } from './components/CrumbNav'
import { QuoteCreateDialog } from './components/QuoteCreateDialog'
import { useCustomers } from './components/lookups'
import { useQuotes } from './hooks'

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Quote status → Badge variant + label. Color AND text together (never color alone). */
export function QuoteStatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
    draft: { variant: 'secondary', label: 'Draft' },
    sent: {
      variant: 'outline',
      className: 'border-blue-300 bg-blue-50 text-blue-700',
      label: 'Sent',
    },
    accepted: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Accepted',
    },
    rejected: {
      variant: 'outline',
      className: 'border-red-300 bg-red-50 text-red-700',
      label: 'Rejected',
    },
    expired: { variant: 'outline', className: 'text-muted-foreground', label: 'Expired' },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return (
    <Badge variant={cfg.variant} className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Quotes() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const { data: quotes = [], isLoading, isError } = useQuotes()
  const { data: customers = [] } = useCustomers()

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? '—'

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Quotes</h1>
        <p className="text-base font-normal text-muted-foreground">
          Build priced quotes from PLUM parts or free-text lines, then move them through
          the Draft → Sent → Accepted / Rejected / Expired lifecycle.
        </p>
      </div>

      {/* Toolbar: create */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Quote
        </Button>
      </div>

      {/* Quotes table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load quotes. Check your connection and refresh the page.
          </p>
        </div>
      ) : quotes.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No quotes yet</p>
          <p className="text-sm text-muted-foreground">
            Create your first quote to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Quote #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {quotes.map((quote) => (
              <TableRow
                key={quote.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/crumb/quotes/${quote.id}`)}
                aria-label={`View quote ${quote.quote_number}`}
              >
                <TableCell className="font-medium">{quote.quote_number}</TableCell>
                <TableCell>{customerName(quote.partner_id)}</TableCell>
                <TableCell>
                  <QuoteStatusBadge status={quote.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create dialog */}
      <QuoteCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
