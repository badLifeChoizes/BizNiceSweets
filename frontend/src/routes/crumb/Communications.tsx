// ABOUTME: CRUMB communication-log timeline (/crumb/communications) — pick a customer, log a
// ABOUTME: call/email/note/meeting, and read an append-only, newest-first timeline over
// ABOUTME: /api/v1/crumb/interactions. No edit or delete affordance by design (CRUMB-01).

/**
 * Communications screen — the per-customer interaction timeline (/crumb/communications).
 *
 * Layout: p-8 space-y-6. A customer picker drives useCustomerTimeline(partnerId); the
 * timeline is append-only (server returns newest-first) so there is no edit/delete UI.
 * Each entry shows its type, the UTC timestamp, the acting user, and the body.
 */

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CrumbNav } from './components/CrumbNav'
import { LogInteractionForm } from './components/LogInteractionForm'
import { useCustomers } from './components/lookups'
import { useCustomerTimeline } from './hooks'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  call: 'Call',
  email: 'Email',
  note: 'Note',
  meeting: 'Meeting',
}

/** Interaction type → Badge label. Neutral outline; the label carries the meaning. */
function InteractionTypeBadge({ type }: { type: string }) {
  return <Badge variant="outline">{TYPE_LABELS[type] ?? type}</Badge>
}

/** Render an ISO instant explicitly in UTC so timestamps are unambiguous across zones. */
function formatUtc(iso: string): string {
  try {
    return `${new Date(iso).toISOString().replace('T', ' ').slice(0, 19)} UTC`
  } catch {
    return iso
  }
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Communications() {
  const [partnerId, setPartnerId] = useState('')

  const { data: customers = [] } = useCustomers()
  const {
    data: timeline = [],
    isLoading,
    isError,
  } = useCustomerTimeline(partnerId)

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Communications</h1>
        <p className="text-base font-normal text-muted-foreground">
          Log calls, emails, notes and meetings against a customer and read the
          append-only history.
        </p>
      </div>

      {/* Customer picker */}
      <div className="space-y-2 max-w-sm">
        <Label htmlFor="comm-customer">Customer</Label>
        <Select value={partnerId} onValueChange={setPartnerId}>
          <SelectTrigger id="comm-customer" aria-label="Customer">
            <SelectValue placeholder="Select a customer" />
          </SelectTrigger>
          <SelectContent>
            {customers.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!partnerId ? (
        <p className="text-sm text-muted-foreground">
          Choose a customer to view and log interactions.
        </p>
      ) : (
        <>
          {/* Log form */}
          <LogInteractionForm partnerId={partnerId} />

          {/* Timeline */}
          <Card>
            <CardHeader className="pb-2">
              <h2 className="text-base font-semibold text-foreground">Timeline</h2>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : isError ? (
                <p className="text-sm text-muted-foreground text-center py-6">
                  Failed to load the timeline. Check your connection and try again.
                </p>
              ) : timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-6">
                  No interactions logged yet.
                </p>
              ) : (
                <ul className="space-y-4">
                  {timeline.map((entry) => (
                    <li
                      key={entry.id}
                      className="border-l-2 border-border pl-4 space-y-1"
                    >
                      <div className="flex items-center gap-2">
                        <InteractionTypeBadge type={entry.interaction_type} />
                        <span className="text-xs text-muted-foreground">
                          {formatUtc(entry.occurred_at)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          · {entry.actor_id}
                        </span>
                      </div>
                      <p className="text-sm text-foreground whitespace-pre-wrap">
                        {entry.body}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
