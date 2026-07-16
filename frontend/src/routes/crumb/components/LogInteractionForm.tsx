// ABOUTME: Log-interaction form (CRUMB-01) — append one customer touch (type, body, and an
// ABOUTME: optional link to a lead / opportunity / quote for that customer) via POST
// ABOUTME: /crumb/interactions. Append-only: there is no edit or delete affordance anywhere.

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useCreateInteraction,
  useLeads,
  useOpportunities,
  useQuotes,
  type InteractionCreatePayload,
} from '../hooks'
import { getApiErrorMessage } from './apiError'

interface LogInteractionFormProps {
  partnerId: string
}

const INTERACTION_TYPES = [
  { value: 'call', label: 'Call' },
  { value: 'email', label: 'Email' },
  { value: 'note', label: 'Note' },
  { value: 'meeting', label: 'Meeting' },
] as const

type LinkKind = 'none' | 'lead' | 'opportunity' | 'quote'

export function LogInteractionForm({ partnerId }: LogInteractionFormProps) {
  const [interactionType, setInteractionType] = useState<string>('note')
  const [body, setBody] = useState('')
  const [linkKind, setLinkKind] = useState<LinkKind>('none')
  const [linkId, setLinkId] = useState('')

  // Records that can be linked, scoped to the selected customer.
  const { data: leads = [] } = useLeads()
  const { data: opportunities = [] } = useOpportunities()
  const { data: quotes = [] } = useQuotes()

  const linkableLeads = leads.filter((l) => l.partner_id === partnerId)
  const linkableOpps = opportunities.filter((o) => o.partner_id === partnerId)
  const linkableQuotes = quotes.filter((q) => q.partner_id === partnerId)

  // Reset the optional-link record whenever the kind or customer changes.
  useEffect(() => {
    setLinkId('')
  }, [linkKind, partnerId])

  const createMutation = useCreateInteraction()
  const isSaving = createMutation.isPending
  const canSubmit = body.trim() !== ''

  function handleSubmit() {
    if (!canSubmit) return
    const payload: InteractionCreatePayload = {
      partner_id: partnerId,
      interaction_type: interactionType,
      body: body.trim(),
    }
    if (linkKind === 'lead' && linkId) payload.lead_id = linkId
    if (linkKind === 'opportunity' && linkId) payload.opportunity_id = linkId
    if (linkKind === 'quote' && linkId) payload.quote_id = linkId

    createMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('Interaction logged.')
        setBody('')
        setLinkKind('none')
        setLinkId('')
      },
      onError: (err) =>
        toast.error(getApiErrorMessage(err, 'Could not log the interaction. Please try again.')),
    })
  }

  return (
    <div className="space-y-4 rounded-md border border-border p-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {/* Type */}
        <div className="space-y-2">
          <Label htmlFor="log-type">Type</Label>
          <Select value={interactionType} onValueChange={setInteractionType}>
            <SelectTrigger id="log-type" aria-label="Type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {INTERACTION_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Optional link kind */}
        <div className="space-y-2">
          <Label htmlFor="log-link-kind">Related record (optional)</Label>
          <Select value={linkKind} onValueChange={(v) => setLinkKind(v as LinkKind)}>
            <SelectTrigger id="log-link-kind" aria-label="Related record">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="lead">Lead</SelectItem>
              <SelectItem value="opportunity">Opportunity</SelectItem>
              <SelectItem value="quote">Quote</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Related record picker (only when a kind is chosen) */}
      {linkKind !== 'none' && (
        <div className="space-y-2">
          <Label htmlFor="log-link-id">
            {linkKind === 'lead' ? 'Lead' : linkKind === 'opportunity' ? 'Opportunity' : 'Quote'}
          </Label>
          <Select value={linkId} onValueChange={setLinkId}>
            <SelectTrigger id="log-link-id" aria-label="Related record item">
              <SelectValue placeholder="Select a record" />
            </SelectTrigger>
            <SelectContent>
              {linkKind === 'lead' &&
                linkableLeads.map((l) => (
                  <SelectItem key={l.id} value={l.id}>
                    {l.name}
                  </SelectItem>
                ))}
              {linkKind === 'opportunity' &&
                linkableOpps.map((o) => (
                  <SelectItem key={o.id} value={o.id}>
                    {o.name}
                  </SelectItem>
                ))}
              {linkKind === 'quote' &&
                linkableQuotes.map((q) => (
                  <SelectItem key={q.id} value={q.id}>
                    {q.quote_number}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Body */}
      <div className="space-y-2">
        <Label htmlFor="log-body">Details</Label>
        <textarea
          id="log-body"
          aria-label="Details"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={3}
          placeholder="What happened?"
          className={cn(
            'flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm',
            'shadow-sm placeholder:text-muted-foreground focus-visible:outline-none',
            'focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed',
            'disabled:opacity-50'
          )}
        />
      </div>

      <div className="flex justify-end">
        <Button
          variant="default"
          size="sm"
          onClick={handleSubmit}
          disabled={!canSubmit || isSaving}
        >
          {isSaving ? (
            <>
              <Loader2 className="animate-spin" aria-hidden="true" />
              Logging…
            </>
          ) : (
            'Log Interaction'
          )}
        </Button>
      </div>
    </div>
  )
}
