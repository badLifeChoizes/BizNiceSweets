// ABOUTME: CRUMB quote detail / builder (/crumb/quotes/:id) — header + status FSM actions
// ABOUTME: (Send / Accept / Reject / Expire), the priced line editor, and the quote total
// ABOUTME: over /api/v1/crumb/quotes/{id}. The server owns the FSM; 4xx surface as toasts.

/**
 * QuoteDetail — single quote view + builder (/crumb/quotes/:id) (CRUMB-01).
 *
 * Layout: p-8 space-y-6, Back link → /crumb/quotes.
 *
 * Data: useQuote(id) → header + priced lines + total_value; useCustomers() resolves
 * partner_id → name. total_value / line_total are service-derived STRINGS (D-11).
 *
 * Status FSM (server-enforced; buttons only mirror allowed transitions):
 *   draft → Send;  sent → Accept | Reject | Expire;  accepted/rejected/expired terminal.
 * Lines are only editable while Draft — the editor hides its controls otherwise, matching
 * the server's 409. Every action toasts; a 4xx surfaces the server reason.
 */

import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { CrumbNav } from './components/CrumbNav'
import { QuoteStatusBadge } from './Quotes'
import { QuoteLineEditor } from './components/QuoteLineEditor'
import { useCustomers } from './components/lookups'
import { getApiErrorMessage } from './components/apiError'
import { useQuote, useAdvanceQuoteStatus } from './hooks'

// Allowed forward transitions per status. The server is the source of truth; this only
// decides which buttons to render. Accepted / rejected / expired are terminal.
const NEXT_STATUSES: Record<string, string[]> = {
  draft: ['sent'],
  sent: ['accepted', 'rejected', 'expired'],
  accepted: [],
  rejected: [],
  expired: [],
}

const STATUS_ACTION_LABEL: Record<string, string> = {
  sent: 'Send',
  accepted: 'Accept',
  rejected: 'Reject',
  expired: 'Expire',
}

export function QuoteDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: quote, isLoading, isError } = useQuote(id)
  const { data: customers = [] } = useCustomers()

  const advanceMutation = useAdvanceQuoteStatus()

  function handleAdvance(target: string) {
    if (!quote) return
    advanceMutation.mutate(
      { id: quote.id, target_status: target },
      {
        onSuccess: () => toast.success(`Quote ${STATUS_ACTION_LABEL[target] ?? target}.`),
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Could not change the quote status.')),
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
  if (isError || !quote) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load quote. Check your connection and try again.
        </p>
      </div>
    )
  }

  const customerName =
    customers.find((c) => c.id === quote.partner_id)?.name ?? quote.partner_id
  const isDraft = quote.status === 'draft'
  const nextStatuses = NEXT_STATUSES[quote.status] ?? []
  const isMoving = advanceMutation.isPending

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/crumb/quotes')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Quotes
      </Button>

      {/* Header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{quote.quote_number}</p>
                <QuoteStatusBadge status={quote.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">{customerName}</p>
            </div>
            {/* Status FSM actions */}
            <div className="flex items-center gap-2 shrink-0">
              {nextStatuses.map((target) => (
                <Button
                  key={target}
                  variant={target === 'sent' || target === 'accepted' ? 'default' : 'outline'}
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
        <CardContent>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Quote total</p>
            <p className="text-lg font-mono font-semibold">{quote.total_value}</p>
          </div>
        </CardContent>
      </Card>

      {/* Line editor */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Lines</h2>
        </CardHeader>
        <CardContent>
          <QuoteLineEditor quoteId={quote.id} lines={quote.lines} isDraft={isDraft} />
        </CardContent>
      </Card>
    </div>
  )
}
