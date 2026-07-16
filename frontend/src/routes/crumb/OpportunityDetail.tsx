// ABOUTME: CRUMB opportunity detail (/crumb/opportunities/:id) — editable fields (name,
// ABOUTME: value, close date), stage-transition actions (the server owns the FSM), and a
// ABOUTME: Create-quote action shown ONLY when the opportunity is Won (D-V3-15).

/**
 * OpportunityDetail — single opportunity view (/crumb/opportunities/:id) (CRUMB-01).
 *
 * Layout: p-8 space-y-6, Back link → /crumb/opportunities.
 *
 * Data: there is no single-opportunity endpoint in the query seam, so the opportunity is
 * selected out of useOpportunities() by id; useCustomers() resolves partner_id → name.
 *
 * Editing: name / estimated_value / expected_close_date PATCH via useUpdateOpportunity
 * (never the stage). Stage moves go through useAdvanceStage — only plausible targets are
 * offered but the server enforces the FSM, so an invalid move surfaces its 422 as a toast.
 * Create-quote (useSpawnQuote) appears ONLY on `won` (D-V3-15) and navigates to the quote.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { CrumbNav } from './components/CrumbNav'
import { StageBadge, STAGE_LABELS } from './Pipeline'
import { useCustomers } from './components/lookups'
import { getApiErrorMessage } from './components/apiError'
import {
  useOpportunities,
  useUpdateOpportunity,
  useAdvanceStage,
  useSpawnQuote,
} from './hooks'

// Plausible next stages per current stage. The server is the source of truth; this only
// keeps the UI from offering obviously pointless moves. `won`/`lost` are terminal.
const NEXT_STAGES: Record<string, string[]> = {
  qualify: ['proposal', 'lost'],
  proposal: ['won', 'lost'],
  won: [],
  lost: [],
}

export function OpportunityDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: opportunities = [], isLoading, isError } = useOpportunities()
  const { data: customers = [] } = useCustomers()
  const opp = opportunities.find((o) => o.id === id)

  // ── Editable field state ──
  const [name, setName] = useState('')
  const [estimatedValue, setEstimatedValue] = useState('')
  const [expectedCloseDate, setExpectedCloseDate] = useState('')

  useEffect(() => {
    if (!opp) return
    setName(opp.name)
    setEstimatedValue(opp.estimated_value ?? '')
    setExpectedCloseDate(opp.expected_close_date ?? '')
  }, [opp])

  const updateMutation = useUpdateOpportunity()
  const advanceMutation = useAdvanceStage()
  const spawnMutation = useSpawnQuote()

  function handleSave() {
    if (!opp) return
    updateMutation.mutate(
      {
        id: opp.id,
        patch: {
          name: name.trim(),
          estimated_value: estimatedValue.trim() || null,
          expected_close_date: expectedCloseDate || null,
        },
      },
      {
        onSuccess: () => toast.success('Opportunity saved.'),
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Failed to save. Please try again.')),
      }
    )
  }

  function handleAdvance(target: string) {
    if (!opp) return
    advanceMutation.mutate(
      { id: opp.id, target_stage: target },
      {
        onSuccess: () => toast.success(`Moved to ${STAGE_LABELS[target] ?? target}.`),
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Could not change the stage.')),
      }
    )
  }

  function handleSpawnQuote() {
    if (!opp) return
    spawnMutation.mutate(
      { id: opp.id },
      {
        onSuccess: (quote) => {
          toast.success(`Quote ${quote.quote_number} created.`)
          navigate(`/crumb/quotes/${quote.id}`)
        },
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Could not create a quote.')),
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

  // ── Render: not found / error ──
  if (isError || !opp) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load opportunity. Check your connection and try again.
        </p>
      </div>
    )
  }

  const customerName = customers.find((c) => c.id === opp.partner_id)?.name ?? opp.partner_id
  const nextStages = NEXT_STAGES[opp.stage] ?? []
  const isMoving = advanceMutation.isPending
  const isSaving = updateMutation.isPending

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/crumb/opportunities')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Pipeline
      </Button>

      {/* Header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{opp.name}</p>
                <StageBadge stage={opp.stage} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">{customerName}</p>
            </div>
            {/* Stage actions + spawn-quote */}
            <div className="flex items-center gap-2 shrink-0">
              {nextStages.map((target) => (
                <Button
                  key={target}
                  variant={target === 'lost' ? 'outline' : 'default'}
                  size="sm"
                  onClick={() => handleAdvance(target)}
                  disabled={isMoving}
                >
                  {`Move to ${STAGE_LABELS[target] ?? target}`}
                </Button>
              ))}
              {opp.stage === 'won' && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleSpawnQuote}
                  disabled={spawnMutation.isPending}
                >
                  {spawnMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Creating…
                    </>
                  ) : (
                    'Create Quote'
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="opp-name">Name</Label>
              <Input
                id="opp-name"
                aria-label="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="opp-value">Estimated value</Label>
              <Input
                id="opp-value"
                aria-label="Estimated value"
                inputMode="decimal"
                value={estimatedValue}
                onChange={(e) => setEstimatedValue(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="opp-close">Expected close date</Label>
              <Input
                id="opp-close"
                aria-label="Expected close date"
                type="date"
                value={expectedCloseDate}
                onChange={(e) => setExpectedCloseDate(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end pt-4">
            <Button
              variant="default"
              onClick={handleSave}
              disabled={isSaving || name.trim() === ''}
            >
              {isSaving ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
