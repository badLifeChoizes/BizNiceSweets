/**
 * PartDetail — Part detail page showing header card, advance-status strip, and revision timeline.
 *
 * Route: /plum/parts/:id
 *
 * Layout: p-8 space-y-6 (standard page wrapper)
 *
 * Sections:
 *   - Back navigation button ("Back to Parts" → /plum/parts)
 *   - Part header Card: part number, current revision description, classification tags,
 *     current revision label + status badge, timestamps
 *   - Header actions row: "Edit Part" (opens PartSheet) + "New Revision" (opens NewRevisionDialog)
 *   - Advance-status strip: shown only when current revision is Draft or In Review
 *     - Draft → "Submit for Review" (target: in_review)
 *     - In Review → "Release" (opens AdvanceStatusDialog) + "Reject to Draft" (target: draft)
 *   - Revision History: <ol aria-label="Revision history"> listing revisions newest-first
 *     Each <li> shows label, status badge, date, snapshot attributes, reason, and diff from prior
 *
 * Data: useQuery key ['plum','parts',partId] → GET /api/v1/plum/parts/{partId}
 * Mutations: POST /api/v1/plum/parts/{partId}/revisions/{revId}/advance → invalidate same key
 *
 * Threat mitigation T-05-12: No dangerouslySetInnerHTML — all user content via JSX interpolation
 * Threat mitigation T-05-14: Release flows through AdvanceStatusDialog confirmation
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card'
import { apiClient } from '@/api/client'
import { PartSheet } from './components/PartSheet'
import { NewRevisionDialog } from './components/NewRevisionDialog'
import { AdvanceStatusDialog } from './components/AdvanceStatusDialog'
import type { RevisionRead } from './components/NewRevisionDialog'
import type { PartRead } from './components/PartSheet'

// ─── Types ────────────────────────────────────────────────────────────────────

interface PartDetailRead {
  id: string
  part_number: string
  active: boolean
  tags: string[]
  created_at: string
  updated_at: string
  revisions: RevisionRead[]
}

// ─── Status badge color map ───────────────────────────────────────────────────
// Implements UI-SPEC color contract (color + text, never color alone).

const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  in_review: 'bg-yellow-50 text-yellow-700',
  released: 'bg-green-50 text-green-600',
  obsolete: 'bg-gray-100 text-gray-400',
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  in_review: 'In Review',
  released: 'Released',
  obsolete: 'Obsolete',
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function RevisionStatusBadge({ status }: { status: string }) {
  const classes = STATUS_BADGE_CLASSES[status] ?? 'bg-gray-100 text-gray-500'
  const label = STATUS_LABELS[status] ?? status
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {label}
    </span>
  )
}

// ─── Helper: compute "current" revision ───────────────────────────────────────
// Current = the highest revision_number that is NOT obsolete.
// If all are obsolete, fall back to highest overall.

function getCurrentRevision(revisions: RevisionRead[]): RevisionRead | undefined {
  if (!revisions.length) return undefined
  const nonObsolete = revisions.filter((r) => r.status !== 'obsolete')
  if (nonObsolete.length) {
    return nonObsolete.reduce((a, b) =>
      a.revision_number > b.revision_number ? a : b,
    )
  }
  return revisions.reduce((a, b) =>
    a.revision_number > b.revision_number ? a : b,
  )
}

// ─── Helper: format ISO datetime ──────────────────────────────────────────────

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

// ─── Helper: compute field diff between two revisions ─────────────────────────
// Returns a comma-separated list of field names that differ.

const DIFF_FIELDS: Array<{ key: keyof RevisionRead; label: string }> = [
  { key: 'description', label: 'Description' },
  { key: 'category', label: 'Category' },
  { key: 'unit_of_measure', label: 'Unit of Measure' },
  { key: 'notes', label: 'Notes' },
]

function getDiffFromPrior(current: RevisionRead, prior: RevisionRead): string[] {
  return DIFF_FIELDS
    .filter(({ key }) => current[key] !== prior[key])
    .map(({ label }) => label)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PartDetail() {
  const { id: partId = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Sheet / dialog state ──
  const [editSheetOpen, setEditSheetOpen] = useState(false)
  const [newRevDialogOpen, setNewRevDialogOpen] = useState(false)
  const [releaseDialogOpen, setReleaseDialogOpen] = useState(false)

  // ── Data ──
  const { data: part, isLoading, isError } = useQuery<PartDetailRead, Error>({
    queryKey: ['plum', 'parts', partId],
    queryFn: () =>
      apiClient.get<PartDetailRead>(`/api/v1/plum/parts/${partId}`).then((r) => r.data),
    enabled: !!partId,
  })

  // ── Advance mutation (Draft → In Review, In Review → Draft) ──
  const advanceMutation = useMutation<RevisionRead, Error, { revisionId: string; targetStatus: string }>({
    mutationFn: ({ revisionId, targetStatus }) =>
      apiClient
        .post<RevisionRead>(
          `/api/v1/plum/parts/${partId}/revisions/${revisionId}/advance`,
          { target_status: targetStatus },
        )
        .then((r) => r.data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      if (variables.targetStatus === 'in_review') {
        toast('Submitted for review.')
      } else if (variables.targetStatus === 'draft') {
        toast('Revision returned to Draft.')
      }
    },
    onError: () => {
      toast.error('Status transition failed. Please try again.')
    },
  })

  // ── Computed values ──
  const revisions = part?.revisions ?? []
  // Revisions from the API are newest-first (revision_number DESC)
  const currentRevision = getCurrentRevision(revisions)
  const priorReleasedRevision = revisions.find((r) => r.status === 'released' && r.id !== currentRevision?.id)

  // Build a PartRead-compatible object to pass to PartSheet edit mode
  const partReadForSheet: PartRead | null = part
    ? {
        id: part.id,
        part_number: part.part_number,
        active: part.active,
        tags: part.tags,
        current_revision_label: currentRevision?.revision_label ?? null,
        current_revision_status: currentRevision?.status ?? null,
        created_at: part.created_at,
        updated_at: part.updated_at,
      }
    : null

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !part) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load part details. Check your connection and try again.
        </p>
      </div>
    )
  }

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/plum/parts')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Parts
      </Button>

      {/* Part header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xl font-semibold text-foreground">{part.part_number}</p>
              {currentRevision && (
                <p className="text-base text-muted-foreground mt-0.5">
                  {currentRevision.description}
                </p>
              )}
            </div>
            {/* Header actions */}
            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditSheetOpen(true)}
              >
                Edit Part
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => setNewRevDialogOpen(true)}
              >
                New Revision
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {/* Classification tags */}
            <div>
              <p className="text-xs text-muted-foreground mb-1">Classification Tags</p>
              {part.tags.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {part.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>

            {/* Current revision */}
            <div>
              <p className="text-xs text-muted-foreground mb-1">Current Revision</p>
              {currentRevision ? (
                <div className="flex items-center gap-2">
                  <span className="font-medium">{currentRevision.revision_label}</span>
                  <RevisionStatusBadge status={currentRevision.status} />
                </div>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>

            {/* Created date */}
            <div>
              <p className="text-xs text-muted-foreground mb-1">Created</p>
              <span className="text-muted-foreground">{formatDate(part.created_at)}</span>
            </div>

            {/* Last updated */}
            <div>
              <p className="text-xs text-muted-foreground mb-1">Last Updated</p>
              <span className="text-muted-foreground">{formatDate(part.updated_at)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Advance-status strip — only shown for draft or in_review */}
      {currentRevision && (currentRevision.status === 'draft' || currentRevision.status === 'in_review') && (
        <div className="flex items-center justify-between rounded-md border border-border p-4">
          <div className="flex items-center gap-3">
            <RevisionStatusBadge status={currentRevision.status} />
            <span className="text-sm text-muted-foreground">
              {currentRevision.status === 'draft' ? '→ In Review' : '→ Released or back to Draft'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {currentRevision.status === 'draft' && (
              <Button
                variant="default"
                size="sm"
                disabled={advanceMutation.isPending}
                onClick={() =>
                  advanceMutation.mutate({
                    revisionId: currentRevision.id,
                    targetStatus: 'in_review',
                  })
                }
              >
                {advanceMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Submitting…
                  </>
                ) : (
                  'Submit for Review'
                )}
              </Button>
            )}
            {currentRevision.status === 'in_review' && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={advanceMutation.isPending}
                  onClick={() =>
                    advanceMutation.mutate({
                      revisionId: currentRevision.id,
                      targetStatus: 'draft',
                    })
                  }
                >
                  Reject to Draft
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  disabled={advanceMutation.isPending}
                  onClick={() => setReleaseDialogOpen(true)}
                  aria-label={`Release revision ${currentRevision.revision_label}`}
                >
                  Release
                </Button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Revision History */}
      <div className="space-y-4">
        <h2 className="text-base font-semibold text-foreground">Revision History</h2>
        {revisions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No revisions yet.</p>
        ) : (
          <ol className="space-y-0" aria-label="Revision history">
            {revisions.map((rev, index) => {
              // Compute diff vs the next-older revision (index+1 in newest-first array)
              const priorRev = revisions[index + 1]
              const diffFields = priorRev ? getDiffFromPrior(rev, priorRev) : []
              const isFirst = index === 0
              const isLast = index === revisions.length - 1

              // Dot color matches status badge
              const dotColor =
                rev.status === 'released'
                  ? 'bg-green-500'
                  : rev.status === 'in_review'
                    ? 'bg-yellow-400'
                    : rev.status === 'obsolete'
                      ? 'bg-gray-300'
                      : 'bg-gray-400'

              return (
                <li key={rev.id} className="relative flex gap-4 pb-6 last:pb-0">
                  {/* Connector column */}
                  <div className="relative flex flex-col items-center">
                    {/* Connector line above dot (skip for first item) */}
                    {!isFirst && (
                      <div className="absolute top-0 bottom-4 w-0.5 bg-border" />
                    )}
                    {/* Status dot */}
                    <div
                      className={`relative z-10 h-2 w-2 rounded-full mt-1.5 shrink-0 ${dotColor}`}
                    />
                    {/* Connector line below dot (skip for last item) */}
                    {!isLast && (
                      <div className="flex-1 w-0.5 bg-border mt-1" />
                    )}
                  </div>

                  {/* Revision content */}
                  <div className="flex-1 min-w-0">
                    {/* Label + badge + date */}
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="font-medium text-sm text-foreground">
                        {rev.revision_label}
                      </span>
                      <RevisionStatusBadge status={rev.status} />
                      <span className="text-xs text-muted-foreground">
                        {rev.released_at
                          ? `Released ${formatDate(rev.released_at)}`
                          : rev.obsoleted_at
                            ? `Obsoleted ${formatDate(rev.obsoleted_at)}`
                            : `Created ${formatDate(rev.created_at)}`}
                      </span>
                    </div>

                    {/* Snapshot attributes */}
                    <dl className="text-sm space-y-1 mb-2">
                      <div>
                        <dt className="inline text-muted-foreground">Description: </dt>
                        <dd className="inline">{rev.description}</dd>
                      </div>
                      {rev.category && (
                        <div>
                          <dt className="inline text-muted-foreground">Category: </dt>
                          <dd className="inline">{rev.category}</dd>
                        </div>
                      )}
                      {rev.unit_of_measure && (
                        <div>
                          <dt className="inline text-muted-foreground">Unit of Measure: </dt>
                          <dd className="inline">{rev.unit_of_measure}</dd>
                        </div>
                      )}
                      {rev.notes && (
                        <div>
                          <dt className="inline text-muted-foreground">Notes: </dt>
                          <dd className="inline">{rev.notes}</dd>
                        </div>
                      )}
                    </dl>

                    {/* Reason for revision */}
                    {rev.reason_for_revision && (
                      <p className="text-sm text-muted-foreground italic mb-1">
                        {rev.reason_for_revision}
                      </p>
                    )}

                    {/* Diff from prior (only for non-first revisions where fields differ) */}
                    {!isLast && diffFields.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        Changed from prior: {diffFields.join(', ')}
                      </p>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </div>

      {/* ── Edit Part Sheet ────────────────────────────────────────────────── */}
      <PartSheet
        open={editSheetOpen}
        mode="edit"
        part={partReadForSheet}
        onClose={() => setEditSheetOpen(false)}
      />

      {/* ── New Revision Dialog ────────────────────────────────────────────── */}
      <NewRevisionDialog
        open={newRevDialogOpen}
        partId={partId}
        revisions={revisions}
        onClose={() => setNewRevDialogOpen(false)}
      />

      {/* ── Release Confirmation Dialog ────────────────────────────────────── */}
      {currentRevision && currentRevision.status === 'in_review' && (
        <AdvanceStatusDialog
          open={releaseDialogOpen}
          partId={partId}
          revision={currentRevision}
          priorReleasedLabel={priorReleasedRevision?.revision_label}
          onClose={() => setReleaseDialogOpen(false)}
        />
      )}
    </div>
  )
}
