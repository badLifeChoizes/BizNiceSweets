// ABOUTME: SYERP Accounts Receivable Receipts list screen (/syerp/ar/receipts) — recorded
// ABOUTME: cash collections (date, cash account, reference, amount, allocations) over
// ABOUTME: /api/v1/syerp/ar/receipts, with a "Record receipt" button opening RecordReceiptDialog.

/**
 * Receipts screen — SYERP accounts-receivable cash-receipt list (SYERP-13, Phase 13).
 *
 * Layout: p-8 space-y-6 (mirrors Bills / Invoices), SyerpNav strip.
 *
 * Toolbar: a single "Record receipt" Button (variant="default" — the only accent element)
 *   that opens RecordReceiptDialog. On success the dialog fires onSuccess, which invalidates
 *   the receipts + invoices list queries so balances refresh.
 *
 * Table columns: Date | Cash account | Reference | Amount | Allocations. Each receipt lists
 *   its allocations (invoice number : amount). cash_account_id is resolved to code/name via
 *   GET /gl/accounts; invoice_id → invoice_number via GET /ar/invoices. Decimal `amount` is an
 *   exact string — rendered as-is, never float math (D-11).
 *
 * Data: GET /api/v1/syerp/ar/receipts — ReceiptRead[].
 */

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { RecordReceiptDialog } from './components/RecordReceiptDialog'
import type { InvoiceRead } from './Invoices'

// ─── Types ───────────────────────────────────────────────────────────────────

interface GLAccount {
  id: number
  code: string
  name: string
  account_type: string
}

interface ReceiptAllocationRead {
  invoice_id: string
  amount: string
}

/** AR receipt header + allocations as returned by GET /syerp/ar/receipts. */
interface ReceiptRead {
  id: string
  receipt_date: string
  cash_account_id: number
  amount: string
  reference: string | null
  allocations: ReceiptAllocationRead[]
  created_at: string
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchReceipts(): Promise<ReceiptRead[]> {
  return apiClient.get<ReceiptRead[]>('/api/v1/syerp/ar/receipts').then((r) => r.data)
}

function fetchGLAccounts(): Promise<GLAccount[]> {
  return apiClient.get<GLAccount[]>('/api/v1/syerp/gl/accounts').then((r) => r.data)
}

function fetchInvoices(): Promise<InvoiceRead[]> {
  return apiClient.get<InvoiceRead[]>('/api/v1/syerp/ar/invoices').then((r) => r.data)
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

export function Receipts() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: accounts = [] } = useQuery<GLAccount[], Error>({
    queryKey: ['syerp', 'gl', 'accounts'],
    queryFn: fetchGLAccounts,
  })

  const { data: invoices = [] } = useQuery<InvoiceRead[], Error>({
    queryKey: ['syerp', 'ar', 'invoices'],
    queryFn: fetchInvoices,
  })

  const {
    data: receipts = [],
    isLoading,
    isError,
  } = useQuery<ReceiptRead[], Error>({
    queryKey: ['syerp', 'ar', 'receipts'],
    queryFn: fetchReceipts,
  })

  // Resolve ids → human labels client-side (ReceiptRead carries only ids).
  const accountLabel = (id: number) => {
    const a = accounts.find((acc) => acc.id === id)
    return a ? `${a.code} — ${a.name}` : String(id)
  }
  const invoiceNumber = (id: string) =>
    invoices.find((inv) => inv.id === id)?.invoice_number ?? id

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Receipts</h1>
        <p className="text-base font-normal text-muted-foreground">
          Cash collections recorded against posted customer invoices.
        </p>
      </div>

      {/* Toolbar: the "Record receipt" button is the only accent element */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setDialogOpen(true)}>
          Record receipt
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
            Failed to load receipts. Check your connection and refresh the page.
          </p>
        </div>
      ) : receipts.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No receipts yet</p>
          <p className="text-sm text-muted-foreground">
            Record your first cash collection to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Cash account</TableHead>
              <TableHead>Reference</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead>Allocations</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {receipts.map((receipt) => (
              <TableRow key={receipt.id} className="h-12">
                <TableCell className="font-medium">{formatDate(receipt.receipt_date)}</TableCell>
                <TableCell>{accountLabel(receipt.cash_account_id)}</TableCell>
                <TableCell>{receipt.reference ?? '—'}</TableCell>
                <TableCell className="text-right font-mono">{receipt.amount}</TableCell>
                <TableCell>
                  <div className="space-y-0.5">
                    {receipt.allocations.map((alloc, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{invoiceNumber(alloc.invoice_id)}</span>
                        <span className="font-mono text-muted-foreground"> · {alloc.amount}</span>
                      </div>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <RecordReceiptDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['syerp', 'ar', 'receipts'] })
          void queryClient.invalidateQueries({ queryKey: ['syerp', 'ar', 'invoices'] })
        }}
      />
    </div>
  )
}
