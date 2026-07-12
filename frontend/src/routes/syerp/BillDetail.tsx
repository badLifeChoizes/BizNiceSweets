// ABOUTME: SYERP Accounts Payable Bill detail (/syerp/ap/bills/:id) — header (bill#,
// ABOUTME: vendor, status badge, total, open balance), the bill lines table, and the
// ABOUTME: status-driven Post (draft) + Pay (posted) actions (SC5, AC4, AC5).

/**
 * BillDetail — single accounts-payable bill view (/syerp/ap/bills/:id).
 *
 * Layout: p-8 space-y-6 (matches PurchaseOrderDetail), Back link → /syerp/ap/bills.
 *
 * Data:
 *   - Bill + lines: GET /api/v1/syerp/ap/bills/{id} → key ['syerp','ap','bill', id]
 *   - Vendors:      GET /syerp/partners?role=vendor (resolve vendor_id → name)
 *
 * Header card: bill number, vendor NAME, status Badge, total, open balance, vendor
 * invoice ref, posted date. Decimal roll-ups arrive as exact STRINGS (D-11) — rendered
 * as-is, never float math. Lines table: line # | type | po_line_id/account_id |
 * matched_qty | unit_cost | amount.
 *
 * Actions (FSM — server is the source of truth, buttons only mirror it):
 *   - Post — visible ONLY on `draft`. POST …/post → toast + invalidate detail + list.
 *   - Pay  — visible ONLY on `posted`. Opens PayBillDialog; onSuccess invalidates the
 *            detail + list so status/open_balance refresh.
 *   A 4xx surfaces toast.error(server detail); an illegal transition forced past the UI
 *   is still rejected by the backend.
 */

import { useState } from 'react'
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
import { PayBillDialog } from './components/PayBillDialog'
import type { PartnerRead } from './components/PartnerSheet'

// ─── Types ───────────────────────────────────────────────────────────────────
// Decimal fields are string-serialized (D-11) — render as-is. This mirrors the live
// backend BillLineRead (line_no + matched_qty), which the Bills.tsx list type does
// not need (it renders no lines).

/** A bill line as embedded in the detail GET (BillLineRead). */
interface BillLineRead {
  id: string
  line_no: number
  line_type: string
  po_line_id: string | null
  matched_qty: string | null
  account_id: number | null
  unit_cost: string | null
  amount: string
}

/** AP bill header + lines as returned by GET /syerp/ap/bills/{id} (BillRead). */
interface BillDetailRead {
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

function fetchBill(id: string): Promise<BillDetailRead> {
  return apiClient.get<BillDetailRead>(`/api/v1/syerp/ap/bills/${id}`).then((r) => r.data)
}

function fetchVendors(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=vendor')
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

/** Status → Badge variant + label (mirrors the Bills list map). */
function StatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
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

export function BillDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Pay dialog state ──
  const [payOpen, setPayOpen] = useState(false)

  // ── Data ──
  const {
    data: bill,
    isLoading,
    isError,
  } = useQuery<BillDetailRead, Error>({
    queryKey: ['syerp', 'ap', 'bill', id],
    queryFn: () => fetchBill(id),
    enabled: !!id,
  })

  const { data: vendors = [] } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor'],
    queryFn: fetchVendors,
  })

  const vendorName = (vid: string) => vendors.find((v) => v.id === vid)?.name ?? '—'

  // ── Refresh the detail + list after a state change ──
  function invalidateBill() {
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'ap', 'bill', id] })
    void queryClient.invalidateQueries({ queryKey: ['syerp', 'ap', 'bills'] })
  }

  // ── FSM mutation: post ──
  const postMutation = useMutation<BillDetailRead, Error, void>({
    mutationFn: () =>
      apiClient.post<BillDetailRead>(`/api/v1/syerp/ap/bills/${id}/post`).then((r) => r.data),
    onSuccess: () => {
      invalidateBill()
      toast.success('Bill posted.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to post bill.'))
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
  if (isError || !bill) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load bill. Check your connection and try again.
        </p>
      </div>
    )
  }

  const canPost = bill.status === 'draft'
  const canPay = bill.status === 'posted'

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/syerp/ap/bills')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Bills
      </Button>

      {/* Bill header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{bill.bill_number}</p>
                <StatusBadge status={bill.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">
                {vendorName(bill.vendor_id)}
              </p>
            </div>
            {/* FSM actions — mirror server-allowed transitions */}
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
              {canPay && (
                <Button variant="default" size="sm" onClick={() => setPayOpen(true)}>
                  Pay
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Total</p>
              <p className="font-mono font-semibold">{bill.total}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Open balance</p>
              <p className="font-mono font-semibold">{bill.open_balance}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Vendor invoice ref</p>
              <p>{bill.vendor_invoice_ref ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Posted</p>
              <p>{bill.posted_at ? formatDate(bill.posted_at) : '—'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Created</p>
              <p>{formatDate(bill.created_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bill lines */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Bill Lines</h2>
        </CardHeader>
        <CardContent>
          {bill.lines.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              This bill has no lines.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead className="text-right">Matched qty</TableHead>
                  <TableHead className="text-right">Unit cost</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bill.lines.map((line) => (
                  <TableRow key={line.id} className="h-12">
                    <TableCell className="font-medium">{line.line_no}</TableCell>
                    <TableCell>{line.line_type}</TableCell>
                    <TableCell className="font-mono">
                      {line.po_line_id ?? (line.account_id != null ? line.account_id : '—')}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {line.matched_qty ?? '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {line.unit_cost ?? '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono">{line.amount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ── Pay Bill dialog ─────────────────────────────────────────────────── */}
      <PayBillDialog
        billId={id}
        openBalance={bill.open_balance}
        open={payOpen}
        onOpenChange={setPayOpen}
        onSuccess={invalidateBill}
      />
    </div>
  )
}
