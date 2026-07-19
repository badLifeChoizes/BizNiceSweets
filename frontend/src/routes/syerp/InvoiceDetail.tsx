// ABOUTME: SYERP Accounts Receivable Invoice detail (/syerp/ar/invoices/:id) — header
// ABOUTME: (invoice#, customer, status badge, total, open balance), the invoice lines table,
// ABOUTME: and the status-driven Post (draft only) action (SYERP-13, Phase 13).

/**
 * InvoiceDetail — single accounts-receivable invoice view (/syerp/ar/invoices/:id).
 *
 * Layout: p-8 space-y-6 (mirrors BillDetail), Back link → /syerp/ar/invoices.
 *
 * Data:
 *   - Invoice + lines: GET /api/v1/syerp/ar/invoices/{id} → key ['syerp','ar','invoice', id]
 *   - Customers:       GET /syerp/partners?role=customer (resolve customer_id → name)
 *
 * Header card: invoice number, customer NAME, status Badge, total, open balance, invoice
 * date, posted date. Decimal roll-ups arrive as exact STRINGS (D-11) — rendered as-is,
 * never float math. Lines table: line # | SO line | invoiced qty | unit price | amount.
 * The invoice line price is READ-ONLY (locked to the sales order line price).
 *
 * Actions (FSM — server is the source of truth, the button only mirrors it):
 *   - Post — visible ONLY on `draft`. POST …/post → toast + invalidate detail + list.
 *   Cash receipts against a posted invoice are recorded on the Receipts screen, not here.
 *   A 4xx surfaces toast.error(server detail); an illegal transition forced past the UI is
 *   still rejected by the backend.
 */

import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import type { PartnerRead } from './components/PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────
// Decimal fields are string-serialized (D-11) — render as-is.

/** An invoice line as embedded in the detail GET (InvoiceLineRead). */
interface InvoiceLineRead {
  id: string
  line_no: number
  sales_order_line_id: string
  invoiced_qty: string
  unit_price: string
  amount: string
}

/** AR invoice header + lines as returned by GET /syerp/ar/invoices/{id} (InvoiceRead). */
interface InvoiceDetailRead {
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

function fetchInvoice(id: string): Promise<InvoiceDetailRead> {
  return apiClient.get<InvoiceDetailRead>(`/api/v1/syerp/ar/invoices/${id}`).then((r) => r.data)
}

function fetchCustomers(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=customer')
    .then((r) => r.data)
}

// Surface the server's real reason (e.g. 422 illegal transition) rather than a generic
// message. FastAPI returns either a string `detail` or a validation array.
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

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Status → Badge variant + label (mirrors the Invoices list map). */
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

export function InvoiceDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Data ──
  const {
    data: invoice,
    isLoading,
    isError,
  } = useQuery<InvoiceDetailRead, Error>({
    queryKey: ['syerp', 'ar', 'invoice', id],
    queryFn: () => fetchInvoice(id),
    enabled: !!id,
  })

  const { data: customers = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'customer'],
    queryFn: fetchCustomers,
  })

  const customerName = (cid: string) => customers.find((c) => c.id === cid)?.name ?? '—'

  // ── Refresh the detail + list after a state change ──
  function invalidateInvoice() {
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'ar', 'invoice', id] })
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'ar', 'invoices'] })
  }

  // ── FSM mutation: post ──
  const postMutation = useMutation<InvoiceDetailRead, Error, void>({
    mutationFn: () =>
      apiClient
        .post<InvoiceDetailRead>(`/api/v1/syerp/ar/invoices/${id}/post`)
        .then((r) => r.data),
    onSuccess: () => {
      invalidateInvoice()
      toast.success('Invoice posted.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to post invoice.'))
    },
  })

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !invoice) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load invoice. Check your connection and try again.
        </p>
      </div>
    )
  }

  const canPost = invoice.status === 'draft'

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/syerp/ar/invoices')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Invoices
      </Button>

      {/* Invoice header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{invoice.invoice_number}</p>
                <StatusBadge status={invoice.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">
                {customerName(invoice.customer_id)}
              </p>
            </div>
            {/* FSM action — mirror server-allowed transitions */}
            <div className="flex items-center gap-2 shrink-0">
              {canPost && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => postMutation.mutate()}
                  disabled={postMutation.isPending}
                >
                  {postMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Posting…
                    </>
                  ) : (
                    'Post'
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Total</p>
              <p className="font-mono font-semibold">{invoice.total}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Open balance</p>
              <p className="font-mono font-semibold">{invoice.open_balance}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Invoice date</p>
              <p>{formatDate(invoice.invoice_date)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Posted</p>
              <p>{invoice.posted_at ? formatDate(invoice.posted_at) : '—'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Created</p>
              <p>{formatDate(invoice.created_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Invoice lines */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Invoice Lines</h2>
        </CardHeader>
        <CardContent>
          {invoice.lines.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              This invoice has no lines.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line</TableHead>
                  <TableHead>SO line</TableHead>
                  <TableHead className="text-right">Invoiced qty</TableHead>
                  <TableHead className="text-right">Unit price</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.lines.map((line) => (
                  <TableRow key={line.id} className="h-12">
                    <TableCell className="font-medium">{line.line_no}</TableCell>
                    <TableCell className="font-mono">{line.sales_order_line_id}</TableCell>
                    <TableCell className="text-right font-mono">{line.invoiced_qty}</TableCell>
                    <TableCell className="text-right font-mono">{line.unit_price}</TableCell>
                    <TableCell className="text-right font-mono">{line.amount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
