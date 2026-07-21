// ABOUTME: CRUMB opportunity pipeline (/crumb/opportunities) — the stage-grouped board
// ABOUTME: (Qualify / Proposal / Won / Lost) from /api/v1/crumb/opportunities?pipeline=true,
// ABOUTME: a "New opportunity" create dialog, and cards that open the detail (CRUMB-01).

/**
 * Pipeline screen — the CRUMB opportunity board (/crumb/opportunities).
 *
 * Layout: p-8 space-y-6; the board is a fixed four-column grid, one column per stage
 * in STAGE_ORDER. usePipeline() returns a { stage: Opportunity[] } map; a customer
 * lookup resolves partner_id → name. Cards navigate to /crumb/opportunities/{id}.
 * estimated_value is a STRING (D-11) — rendered as-is, never coerced to float.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { CrumbNav } from './components/CrumbNav'
import { OpportunityCreateDialog } from './components/OpportunityCreateDialog'
import { useCustomers } from './components/lookups'
import { usePipeline } from './hooks'

// ─── Stage vocabulary (shared with OpportunityDetail) ─────────────────────────

/** Fixed column order for the board. The server owns the FSM; this is display only. */
// eslint-disable-next-line react-refresh/only-export-components -- shared display constant (also used by OpportunityDetail); not a component
export const STAGE_ORDER = ['qualify', 'proposal', 'won', 'lost'] as const

// eslint-disable-next-line react-refresh/only-export-components -- shared display constant (also used by OpportunityDetail); not a component
export const STAGE_LABELS: Record<string, string> = {
  qualify: 'Qualify',
  proposal: 'Proposal',
  won: 'Won',
  lost: 'Lost',
}

/** Stage → Badge styling. Color AND text together (never color alone). */
export function StageBadge({ stage }: { stage: string }) {
  const map: Record<string, { className?: string }> = {
    qualify: { className: 'border-blue-300 bg-blue-50 text-blue-700' },
    proposal: { className: 'border-amber-300 bg-amber-50 text-amber-700' },
    won: { className: 'border-green-300 bg-green-50 text-green-700' },
    lost: { className: 'text-muted-foreground' },
  }
  const cfg = map[stage] ?? {}
  return (
    <Badge variant="outline" className={cfg.className}>
      {STAGE_LABELS[stage] ?? stage}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Pipeline() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const { data: board = {}, isLoading, isError } = usePipeline()
  const { data: customers = [] } = useCustomers()

  const customerName = (id: string) => customers.find((c) => c.id === id)?.name ?? '—'

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Pipeline</h1>
        <p className="text-base font-normal text-muted-foreground">
          Track opportunities through Qualify, Proposal, Won and Lost. Won opportunities
          can spawn a quote.
        </p>
      </div>

      {/* Toolbar: create */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Opportunity
        </Button>
      </div>

      {/* Board / loading / error states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load the pipeline. Check your connection and refresh the page.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {STAGE_ORDER.map((stage) => {
            const items = board[stage] ?? []
            return (
              <div key={stage} className="space-y-3">
                <div className="flex items-center justify-between">
                  <StageBadge stage={stage} />
                  <span className="text-xs text-muted-foreground">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.length === 0 ? (
                    <p className="text-xs text-muted-foreground px-1 py-4">
                      No opportunities.
                    </p>
                  ) : (
                    items.map((opp) => (
                      <Card
                        key={opp.id}
                        className="cursor-pointer transition-colors hover:border-primary"
                        onClick={() => navigate(`/crumb/opportunities/${opp.id}`)}
                        aria-label={`View opportunity ${opp.name}`}
                      >
                        <CardContent className="p-3 space-y-1">
                          <p className="text-sm font-medium text-foreground">{opp.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {customerName(opp.partner_id)}
                          </p>
                          {opp.estimated_value && (
                            <p className="text-xs font-mono text-foreground">
                              {opp.estimated_value}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create dialog */}
      <OpportunityCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
