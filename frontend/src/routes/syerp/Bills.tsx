// ABOUTME: SYERP Accounts Payable Bills list screen (/syerp/ap/bills) — bill number,
// ABOUTME: vendor, status badge, total and open balance over /api/v1/syerp/ap/bills, with
// ABOUTME: a "New bill" button opening BillCreateDialog to record a vendor bill (SC5, AC4).

/**
 * Bills screen — SYERP accounts-payable bill list (SYERP-12 AC4, Phase 09b).
 *
 * Layout: p-8 space-y-6 (matches PurchaseOrders / JournalEntries pattern), SyerpNav strip.
 *
 * Toolbar: a single "New bill" Button (variant="default" — the only accent element)
 *   that opens BillCreateDialog. On a successful create the dialog fires onSuccess,
 *   which invalidates the list query so the new bill appears.
 *
 * Table columns: Bill Number | Vendor | Status | Total | Open Balance. Each row links
 *   to the bill detail screen (/syerp/ap/bills/:id — route registered in Task 16).
 *
 * Vendor name resolution: BillRead carries only vendor_id, so vendors are fetched once
 *   (GET /api/v1/syerp/partners?role=vendor) and mapped id→name client-side. Decimal
 *   `total` / `open_balance` are exact strings — rendered as-is, never float math (D-11).
 *
 * Data: GET /api/v1/syerp/ap/bills — BillRead[].
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
import { BillCreateDialog } from './components/BillCreateDialog'
import type { PartnerRead } from './components/PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

interface BillLineRead {
  id: string
  line_type: string
  po_line_id: string | null
  account_id: number | null
  quantity: string | null
  unit_cost: string | null
  amount: string
}

/** AP bill header + lines as returned by GET /syerp/ap/bills. */
export interface BillRead {
  id: string
  bill_number: string
  vendor_id: string
  vendor_invoice_ref: string | null
  status: string
  memo: string | null
  posted_at: string | null
  // Decimal roll-ups arrive as exact strings — render as-is, never float math.
  total: string
  open_balance: string
  lines: BillLineRead[]
  created_at: string
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchBills(): Promise<BillRead[]> {
  return apiClient.get<BillRead[]>('/api/v1/syerp/ap/bills').then((r) => r.data)
}

function fetchVendors(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=vendor')
    .then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label. Color AND text together (never color alone). */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    posted: { variant: 'default', label: 'Posted' },
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

// ─── Main component ──────────────────────────────────────────────────────────

export function Bills() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
  })

  const {
    data: bills = [],
    isLoading,
    isError,
  } = useQuery<BillRead[], Error>({
    queryKey: ['syerp', 'ap', 'bills'],
    queryFn: fetchBills,
  })

  // Resolve vendor_id → name client-side (BillRead carries only the id).
  const vendorName = (id: string) => vendors.find((v) => v.id === id)?.name ?? '—'

  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Bills</h1>
        <p className="text-base font-normal text-muted-foreground">
          Vendor bills matched against received purchases and non-PO expenses.
        </p>
      </div>

      {/* Toolbar: the "New bill" button is the only accent element */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setDialogOpen(true)}>
          New bill
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
            Failed to load bills. Check your connection and refresh the page.
          </p>
        </div>
      ) : bills.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No bills yet</p>
          <p className="text-sm text-muted-foreground">
            Record your first vendor bill to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Bill Number</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="text-right">Open Balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bills.map((bill) => (
              <TableRow
                key={bill.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/syerp/ap/bills/${bill.id}`)}
                aria-label={`View bill ${bill.bill_number}`}
              >
                <TableCell className="font-medium">{bill.bill_number}</TableCell>
                <TableCell>{vendorName(bill.vendor_id)}</TableCell>
                <TableCell>
                  <StatusBadge status={bill.status} />
                </TableCell>
                <TableCell className="text-right font-mono">{bill.total}</TableCell>
                <TableCell className="text-right font-mono">{bill.open_balance}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <BillCreateDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['syerp', 'ap', 'bills'] })}
      />
    </div>
  )
}
