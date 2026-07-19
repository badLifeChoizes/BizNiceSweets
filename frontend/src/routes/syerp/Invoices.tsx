// ABOUTME: SYERP Accounts Receivable Invoices list screen (/syerp/ar/invoices) — invoice
// ABOUTME: number, customer, date, status badge, total and open balance over
// ABOUTME: /api/v1/syerp/ar/invoices, with a "New invoice" button opening InvoiceCreateDialog.

/**
 * Invoices screen — SYERP accounts-receivable invoice list (SYERP-13, Phase 13).
 *
 * Layout: p-8 space-y-6 (mirrors Bills / PurchaseOrders), SyerpNav strip.
 *
 * Toolbar: a single "New invoice" Button (variant="default" — the only accent element)
 *   that opens InvoiceCreateDialog. On a successful create the dialog fires onSuccess,
 *   which invalidates the list query so the new invoice appears.
 *
 * Table columns: Invoice Number | Customer | Date | Status | Total | Open Balance. Each row
 *   links to the invoice detail screen (/syerp/ar/invoices/:id).
 *
 * Customer name resolution: InvoiceRead carries only customer_id, so customers are fetched
 *   once (GET /api/v1/syerp/partners?role=customer) and mapped id→name client-side. Decimal
 *   `total` / `open_balance` are exact strings — rendered as-is, never float math (D-11).
 *
 * Data: GET /api/v1/syerp/ar/invoices — InvoiceRead[].
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
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
import { apiClient } from '@/api/client'
import { SyerpNav } from './components/SyerpNav'
import { InvoiceCreateDialog } from './components/InvoiceCreateDialog'
import type { PartnerRead } from './components/PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

interface InvoiceLineRead {
  id: string
  line_no: number
  sales_order_line_id: string
  invoiced_qty: string
  unit_price: string
  amount: string
}

/** AR invoice header + lines as returned by GET /syerp/ar/invoices. */
export interface InvoiceRead {
  id: string
  invoice_number: string
  customer_id: string
  sales_order_id: string | null
  invoice_date: string
  status: string
  memo: string | null
  posted_at: string | null
  // Decimal roll-ups arrive as exact strings — render as-is, never float math.
  total: string
  open_balance: string
  lines: InvoiceLineRead[]
  created_at: string
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchInvoices(): Promise<InvoiceRead[]> {
  return apiClient.get<InvoiceRead[]>('/api/v1/syerp/ar/invoices').then((r) => r.data)
}

function fetchCustomers(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=customer')
    .then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label. Color AND text together (never color alone). */
function StatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
    draft: { variant: 'secondary', label: 'Draft' },
    posted: { variant: 'default', label: 'Posted' },
    partially_paid: {
      variant: 'outline',
      className: 'border-amber-300 bg-amber-50 text-amber-700',
      label: 'Partially paid',
    },
    paid: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Paid',
    },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return (
    <Badge variant={cfg.variant} className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Helper: format ISO date (date-only) ──────────────────────────────────────

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

// ─── Main component ──────────────────────────────────────────────────────────

export function Invoices() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: customers = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'customer'],
    queryFn: fetchCustomers,
  })

  const {
    data: invoices = [],
    isLoading,
    isError,
  } = useQuery<InvoiceRead[], Error>({
    queryKey: ['syerp', 'ar', 'invoices'],
    queryFn: fetchInvoices,
  })

  // Resolve customer_id → name client-side (InvoiceRead carries only the id).
  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? '—'

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Invoices</h1>
        <p className="text-base font-normal text-muted-foreground">
          Customer invoices raised against shipped sales orders.
        </p>
      </div>

      {/* Toolbar: the "New invoice" button is the only accent element */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setDialogOpen(true)}>
          New invoice
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
            Failed to load invoices. Check your connection and refresh the page.
          </p>
        </div>
      ) : invoices.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No invoices yet</p>
          <p className="text-sm text-muted-foreground">
            Raise your first customer invoice to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice Number</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="text-right">Open Balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((invoice) => (
              <TableRow
                key={invoice.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/syerp/ar/invoices/${invoice.id}`)}
                aria-label={`View invoice ${invoice.invoice_number}`}
              >
                <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
                <TableCell>{customerName(invoice.customer_id)}</TableCell>
                <TableCell>{formatDate(invoice.invoice_date)}</TableCell>
                <TableCell>
                  <StatusBadge status={invoice.status} />
                </TableCell>
                <TableCell className="text-right font-mono">{invoice.total}</TableCell>
                <TableCell className="text-right font-mono">{invoice.open_balance}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <InvoiceCreateDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['syerp', 'ar', 'invoices'] })}
      />
    </div>
  )
}
