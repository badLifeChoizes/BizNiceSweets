// ABOUTME: CRUMB sales-order detail / builder (/crumb/sales-orders/:id) — header + status FSM
// ABOUTME: actions (Confirm / Cancel / Fulfill / Close), the ordered-line grid with reserved /
// ABOUTME: shortage figures, and Draft-only line editing over /api/v1/crumb/sales-orders/{id}.

/**
 * SalesOrderDetail — single sales-order view + builder (/crumb/sales-orders/:id) (CRUMB-01).
 *
 * Layout: p-8 space-y-6, Back link → /crumb/sales-orders. Mirrors QuoteDetail.
 *
 * Data: useSalesOrder(id) → header + ordered lines (with server-derived reserved / shortage /
 * line_total) + total_value; useCustomers() resolves partner_id → name. Money & quantity fields
 * are Decimals serialized as exact STRINGS (D-11) — rendered as-is, never float math.
 *
 * Status FSM (server-enforced; buttons only mirror allowed transitions):
 *   draft → Confirm | Cancel;  confirmed → Fulfill | Cancel;  fulfilling → Close;
 *   closed / cancelled terminal.
 * Confirm reserves stock; its reserved / shortage figures refresh via query invalidation.
 * Cancelling a Confirmed order frees those reservations. Lines are only editable while Draft.
 * Every action toasts; an invalid transition (422) surfaces the server reason.
 */

import { Link, useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { CrumbNav } from './components/CrumbNav'
import { SalesOrderStatusBadge } from './SalesOrders'
import { SalesOrderDetailLines } from './components/SalesOrderDetailLines'
import { useCustomers } from './components/lookups'
import { getApiErrorMessage } from './components/apiError'
import { useSalesOrder, useAdvanceSalesOrderStatus } from './hooks'
import { useAuth } from '@/hooks/useAuth'
import { useModules } from '@/hooks/useModules'
import { useVisibleModules } from '@/components/AppShell'

// SO statuses that can be handed off to GELATO fulfillment (stock reserved / picking).
const FULFILLABLE_STATUSES = new Set(['confirmed', 'fulfilling'])

// Allowed forward transitions per status. The server is the source of truth; this only
// decides which buttons to render. Closed / cancelled are terminal.
const NEXT_STATUSES: Record<string, string[]> = {
  draft: ['confirmed', 'cancelled'],
  confirmed: ['fulfilling', 'cancelled'],
  fulfilling: ['closed'],
  closed: [],
  cancelled: [],
}

const STATUS_ACTION_LABEL: Record<string, string> = {
  confirmed: 'Confirm',
  cancelled: 'Cancel',
  fulfilling: 'Fulfill',
  closed: 'Close',
}

export function SalesOrderDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: so, isLoading, isError } = useSalesOrder(id)
  const { data: customers = [] } = useCustomers()

  // GELATO fulfillment affordance gating: reuse the app-wide visible-modules signal
  // (module enabled ∩ gelato:read) — the same intersection AppShell/Sidebar nav uses.
  const { user } = useAuth()
  const { data: modules = [] } = useModules()
  const gelatoVisible = useVisibleModules(user, modules).some((m) => m.key === 'gelato')

  const advanceMutation = useAdvanceSalesOrderStatus()

  function handleAdvance(target: string) {
    if (!so) return
    advanceMutation.mutate(
      { id: so.id, target_status: target },
      {
        onSuccess: () => toast.success(`Sales order ${STATUS_ACTION_LABEL[target] ?? target}.`),
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Could not change the sales-order status.')),
      }
    )
  }

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !so) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load sales order. Check your connection and try again.
        </p>
      </div>
    )
  }

  const customerName = customers.find((c) => c.id === so.partner_id)?.name ?? so.partner_id
  const isDraft = so.status === 'draft'
  const nextStatuses = NEXT_STATUSES[so.status] ?? []
  const isMoving = advanceMutation.isPending
  // Show the Fulfill / Ship hand-off only when GELATO is visible to this user and the
  // order is in a fulfillable state (stock reserved / already picking).
  const canFulfill = gelatoVisible && FULFILLABLE_STATUSES.has(so.status)

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/crumb/sales-orders')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Sales Orders
      </Button>

      {/* Header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{so.so_number}</p>
                <SalesOrderStatusBadge status={so.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">{customerName}</p>
            </div>
            {/* Status FSM actions */}
            <div className="flex items-center gap-2 shrink-0">
              {canFulfill && (
                <Button asChild variant="secondary" size="sm">
                  <Link to={`/gelato/fulfillment?so=${so.id}`}>Fulfill / Ship</Link>
                </Button>
              )}
              {nextStatuses.map((target) => (
                <Button
                  key={target}
                  variant={target === 'cancelled' ? 'outline' : 'default'}
                  size="sm"
                  onClick={() => handleAdvance(target)}
                  disabled={isMoving}
                >
                  {STATUS_ACTION_LABEL[target] ?? target}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-muted-foreground">Order date</dt>
              <dd className="font-mono">{so.order_date}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Required date</dt>
              <dd className="font-mono">{so.required_date ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Source quote</dt>
              <dd>
                {so.source_quote_id ? (
                  <Link
                    to={`/crumb/quotes/${so.source_quote_id}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    View quote
                  </Link>
                ) : (
                  '—'
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Source opportunity</dt>
              <dd>
                {so.source_opportunity_id ? (
                  <Link
                    to={`/crumb/opportunities/${so.source_opportunity_id}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    View opportunity
                  </Link>
                ) : (
                  '—'
                )}
              </dd>
            </div>
          </dl>
          <div className="flex items-center justify-between border-t border-border pt-3">
            <p className="text-xs text-muted-foreground">Order total</p>
            <p className="text-lg font-mono font-semibold">{so.total_value}</p>
          </div>
        </CardContent>
      </Card>

      {/* Ordered lines */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Lines</h2>
        </CardHeader>
        <CardContent>
          <SalesOrderDetailLines soId={so.id} lines={so.lines} isDraft={isDraft} />
        </CardContent>
      </Card>
    </div>
  )
}
