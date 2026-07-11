/**
 * PartDetail — Part detail page showing header card, advance-status strip, revision timeline,
 * and four Phase-6 section cards (BOM, AVL, Cost & Margin, Where-Used).
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
 *   - Bill of Materials card (Phase 6 — PLUM-04/05)
 *   - Approved Vendor List card (Phase 6 — PLUM-07)
 *   - Cost & Margin card (Phase 6 — PLUM-08/09)
 *   - Where Used card (Phase 6 — PLUM-06)
 *
 * Data: useQuery key ['plum','parts',partId] → GET /api/v1/plum/parts/{partId}
 * Mutations: POST /api/v1/plum/parts/{partId}/revisions/{revId}/advance → invalidate same key
 *
 * Threat mitigation T-05-12: No dangerouslySetInnerHTML — all user content via JSX interpolation
 * Threat mitigation T-05-14: Release flows through AdvanceStatusDialog confirmation
 * Threat mitigation T-06-21: Client hides BOM/cost edits on Released; backend enforces
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Loader2,
  CheckCircle,
  Circle,
} from 'lucide-react'
import { MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { PartSheet } from './components/PartSheet'
import { NewRevisionDialog } from './components/NewRevisionDialog'
import { AdvanceStatusDialog } from './components/AdvanceStatusDialog'
import { BomTree } from './components/BomTree'
import { BomLineSheet } from './components/BomLineSheet'
import { AvlLinkSheet } from './components/AvlLinkSheet'
import type { BomTreeNode } from './components/BomTree'
import type { AvlLinkRead } from './components/AvlLinkSheet'
import type { RevisionRead } from './components/NewRevisionDialog'
import type { PartRead } from './components/PartSheet'
import type { SettingRecord } from '@/hooks/useSettings'

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

interface PriceBreakRead {
  id: string
  avl_link_id: string
  qty_threshold: number
  unit_cost: number | string
  lead_days?: number | null
  sort_order: number
}

interface WhereUsedEntry {
  parent_part_id: string
  parent_part_number: string
  parent_revision_label?: string | null
  parent_revision_status?: string | null
  relationship?: string | null
  direct?: boolean
  indirect?: boolean
  via_part_number?: string | null
  depth?: number
}

interface CostRead {
  material_cost?: number | string | null
  sale_price?: number | string | null
  bom_rollup_cost?: number | string | null
  effective_cost?: number | string | null
  effective_cost_source?: string | null
  margin?: number | string | null
  margin_pct?: number | string | null
  released_cost_snapshot?: number | string | null
  selected_vendor_link_id?: string | null
  selected_price_break_index?: number | null
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

// ─── Helper: format cost values ───────────────────────────────────────────────

function formatCostValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return num.toFixed(2)
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

  // ── BOM state ──
  const [bomLineSheetOpen, setBomLineSheetOpen] = useState(false)
  const [bomLineSheetMode, setBomLineSheetMode] = useState<'create' | 'edit'>('create')
  const [editingBomLine, setEditingBomLine] = useState<BomTreeNode | null>(null)
  const [removingBomLine, setRemovingBomLine] = useState<BomTreeNode | null>(null)

  // ── AVL state ──
  const [avlSheetOpen, setAvlSheetOpen] = useState(false)
  const [avlSheetMode, setAvlSheetMode] = useState<'create' | 'edit'>('create')
  const [editingAvlLink, setEditingAvlLink] = useState<AvlLinkRead | null>(null)
  const [removingAvlLinkId, setRemovingAvlLinkId] = useState<string | null>(null)
  const [removingAvlLinkName, setRemovingAvlLinkName] = useState<string>('')
  const [expandedAvlIds, setExpandedAvlIds] = useState<Set<string>>(new Set())

  // ── Cost & Margin state ──
  const [costMaterialInput, setCostMaterialInput] = useState('')
  const [costSalePriceInput, setCostSalePriceInput] = useState('')

  // ── Data ──
  const { data: part, isLoading, isError } = useQuery<PartDetailRead, Error>({
    queryKey: ['plum', 'parts', partId],
    queryFn: () =>
      apiClient.get<PartDetailRead>(`/api/v1/plum/parts/${partId}`).then((r) => r.data),
    enabled: !!partId,
  })

  // ── Settings (currency) ──
  const { data: settings = [] } = useQuery<SettingRecord[], Error>({
    queryKey: ['core', 'settings'],
    queryFn: () =>
      apiClient.get<SettingRecord[]>('/api/v1/core/settings').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  function getSystemCurrency(): string {
    const rec = settings.find((s) => s.key === 'locale.currency')
    return rec?.value ?? 'USD'
  }

  // ── Computed values ──
  const revisions = part?.revisions ?? []
  // Revisions from the API are newest-first (revision_number DESC)
  const currentRevision = getCurrentRevision(revisions)
  const isDraft = currentRevision?.status === 'draft'
  const isReleased = currentRevision?.status === 'released'
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

  // ── AVL query (part-level) ──
  const { data: avlLinks = [] } = useQuery<AvlLinkRead[], Error>({
    queryKey: ['plum', 'parts', partId, 'avl'],
    queryFn: () =>
      apiClient
        .get<AvlLinkRead[]>(`/api/v1/plum/parts/${partId}/avl`)
        .then((r) => r.data),
    enabled: !!partId,
  })

  // ── Where-used query ──
  const { data: whereUsed = [] } = useQuery<WhereUsedEntry[], Error>({
    queryKey: ['plum', 'parts', partId, 'where-used'],
    queryFn: () =>
      apiClient
        .get<WhereUsedEntry[]>(`/api/v1/plum/parts/${partId}/where-used`)
        .then((r) => r.data),
    enabled: !!partId,
  })

  // ── Cost query (current revision) ──
  const { data: costData } = useQuery<CostRead, Error>({
    queryKey: ['plum', 'parts', partId, 'cost', currentRevision?.id],
    queryFn: () =>
      apiClient
        .get<CostRead>(`/api/v1/plum/parts/${partId}/revisions/${currentRevision!.id}/cost`)
        .then((r) => r.data),
    enabled: !!partId && !!currentRevision?.id,
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

  // ── Save cost mutation ──
  const saveCostMutation = useMutation<CostRead, Error, { materialCost?: number | null; salePrice?: number | null }>({
    mutationFn: ({ materialCost, salePrice }) =>
      apiClient
        .patch<CostRead>(
          `/api/v1/plum/parts/${partId}/revisions/${currentRevision!.id}/cost`,
          {
            material_cost: materialCost,
            sale_price: salePrice,
          },
        )
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId, 'cost', currentRevision?.id] })
      toast('Costs saved.')
    },
    onError: () => {
      toast.error('Failed to save costs. Please try again.')
    },
  })

  // ── BOM remove mutation ──
  const removeBomLineMutation = useMutation<void, Error, string>({
    mutationFn: (lineId: string) =>
      apiClient
        .delete(`/api/v1/plum/parts/${partId}/bom/${lineId}`)
        .then(() => undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      setRemovingBomLine(null)
      toast('BOM line removed.')
    },
    onError: () => {
      toast.error('Failed to remove BOM line. Please try again.')
    },
  })

  // ── AVL remove mutation ──
  const removeAvlLinkMutation = useMutation<void, Error, string>({
    mutationFn: (linkId: string) =>
      apiClient
        .delete(`/api/v1/plum/parts/${partId}/avl/${linkId}`)
        .then(() => undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId, 'avl'] })
      setRemovingAvlLinkId(null)
      setRemovingAvlLinkName('')
      toast('Vendor link removed.')
    },
    onError: () => {
      toast.error('Failed to remove vendor link. Please try again.')
    },
  })

  // ── AVL select-for-costing mutation ──
  const selectForCostingMutation = useMutation<
    CostRead,
    Error,
    { vendorLinkId: string; priceBreakIndex: number }
  >({
    mutationFn: ({ vendorLinkId, priceBreakIndex }) =>
      apiClient
        .patch<CostRead>(
          `/api/v1/plum/parts/${partId}/revisions/${currentRevision!.id}/cost`,
          {
            selected_vendor_link_id: vendorLinkId,
            selected_price_break_index: priceBreakIndex,
          },
        )
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId, 'cost', currentRevision?.id] })
      toast('Costs saved.')
    },
    onError: () => {
      toast.error('Failed to save costs. Please try again.')
    },
  })

  // ── Handlers ──

  function handleBomEdit(line: BomTreeNode) {
    setEditingBomLine(line)
    setBomLineSheetMode('edit')
    setBomLineSheetOpen(true)
  }

  function handleBomRemove(line: BomTreeNode) {
    setRemovingBomLine(line)
  }

  function handleBomLineSheetClose() {
    setBomLineSheetOpen(false)
    setEditingBomLine(null)
  }

  function handleAvlEdit(link: AvlLinkRead) {
    setEditingAvlLink(link)
    setAvlSheetMode('edit')
    setAvlSheetOpen(true)
  }

  function handleAvlRemove(link: AvlLinkRead) {
    setRemovingAvlLinkId(link.id)
    setRemovingAvlLinkName(link.vendor_name ?? link.vendor_id)
  }

  function handleAvlSheetClose() {
    setAvlSheetOpen(false)
    setEditingAvlLink(null)
  }

  function toggleAvlExpand(linkId: string) {
    setExpandedAvlIds((prev) => {
      const next = new Set(prev)
      if (next.has(linkId)) {
        next.delete(linkId)
      } else {
        next.add(linkId)
      }
      return next
    })
  }

  function handleSaveCosts() {
    const materialCost = costMaterialInput !== '' ? parseFloat(costMaterialInput) : null
    const salePrice = costSalePriceInput !== '' ? parseFloat(costSalePriceInput) : null
    saveCostMutation.mutate({ materialCost, salePrice })
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
  if (isError || !part) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load part details. Check your connection and try again.
        </p>
      </div>
    )
  }

  const currency = getSystemCurrency()

  // ── Computed cost display values ──
  const effectiveCost = costData?.effective_cost
  const effectiveCostSource = costData?.effective_cost_source
  const materialCostDisplay = formatCostValue(costData?.material_cost)
  const bomRollupDisplay = formatCostValue(costData?.bom_rollup_cost)
  const effectiveCostDisplay = formatCostValue(effectiveCost)
  const salePriceDisplay = formatCostValue(costData?.sale_price)
  const marginDisplay = formatCostValue(costData?.margin)
  const marginPctDisplay = formatCostValue(costData?.margin_pct)
  const frozenCostDisplay = formatCostValue(costData?.released_cost_snapshot)

  const marginNum = costData?.margin !== null && costData?.margin !== undefined
    ? (typeof costData.margin === 'string' ? parseFloat(costData.margin) : costData.margin)
    : null
  const isNegativeMargin = marginNum !== null && !isNaN(marginNum) && marginNum < 0

  const hasSalePrice = costData?.sale_price !== null && costData?.sale_price !== undefined && costData.sale_price !== ''
  const hasEffectiveCost = effectiveCost !== null && effectiveCost !== undefined && effectiveCost !== ''

  // Sort where-used: direct first, then indirect
  const sortedWhereUsed = [...whereUsed].sort((a, b) => {
    const aIsDirect = !a.indirect
    const bIsDirect = !b.indirect
    if (aIsDirect && !bIsDirect) return -1
    if (!aIsDirect && bIsDirect) return 1
    return (a.parent_part_number ?? '').localeCompare(b.parent_part_number ?? '')
  })

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

      {/* ── Section 1: Bill of Materials ──────────────────────────────────────── */}
      {currentRevision && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-foreground">Bill of Materials</h2>
              {isDraft && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditingBomLine(null)
                    setBomLineSheetMode('create')
                    setBomLineSheetOpen(true)
                  }}
                >
                  Add Part
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <BomTree
              partId={partId}
              revisionId={currentRevision.id}
              isDraft={isDraft}
              rollupCost={costData?.bom_rollup_cost}
              onEdit={isDraft ? handleBomEdit : undefined}
              onRemove={isDraft ? handleBomRemove : undefined}
            />

            {/* Inline BOM remove confirmation (Draft only) */}
            {removingBomLine && (
              <div className="mt-3 flex items-center gap-3 rounded-md border border-border p-3 text-sm">
                <span className="text-foreground">
                  Remove {removingBomLine.child_part_number}?
                </span>
                <Button
                  variant="destructive"
                  size="sm"
                  aria-label={`Confirm remove ${removingBomLine.child_part_number} from BOM`}
                  disabled={removeBomLineMutation.isPending}
                  onClick={() => removeBomLineMutation.mutate(removingBomLine.bom_item_id)}
                >
                  {removeBomLineMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    'Yes, Remove'
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Keep ${removingBomLine.child_part_number} in BOM`}
                  disabled={removeBomLineMutation.isPending}
                  onClick={() => setRemovingBomLine(null)}
                >
                  Keep {removingBomLine.child_part_number}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Section 2: Approved Vendor List ───────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">Approved Vendor List</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setEditingAvlLink(null)
                setAvlSheetMode('create')
                setAvlSheetOpen(true)
              }}
            >
              Add Vendor
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {avlLinks.length === 0 ? (
            <>
              <p className="text-sm text-muted-foreground text-center py-6">
                No approved vendors yet.
              </p>
              <p className="text-xs text-muted-foreground text-center">
                Link a vendor to track sourcing options and vendor-driven pricing.
              </p>
            </>
          ) : (
            <div className="space-y-2">
              {avlLinks.map((link) => {
                const isExpanded = expandedAvlIds.has(link.id)
                const priceBreaks = (link.price_breaks ?? [])
                  .slice()
                  .sort((a, b) => a.sort_order - b.sort_order)

                return (
                  <div key={link.id} className="rounded-md border border-border">
                    {/* Vendor row */}
                    <div className="flex items-center gap-2 px-3 py-2">
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground flex-none"
                        onClick={() => toggleAvlExpand(link.id)}
                        aria-label={isExpanded ? 'Collapse price breaks' : 'Expand price breaks'}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ChevronRight className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                      <span className="text-sm font-medium text-foreground">
                        {link.vendor_name ?? link.vendor_id}
                      </span>
                      {link.preferred && (
                        <span
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700"
                          title="Preferred vendor"
                        >
                          Preferred
                        </span>
                      )}
                      {link.vendor_part_number && (
                        <span className="text-sm text-muted-foreground font-mono ml-1">
                          {link.vendor_part_number}
                        </span>
                      )}
                      <div className="ml-auto">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-11 w-11"
                              aria-label={`Actions for ${link.vendor_name ?? link.vendor_id}`}
                            >
                              <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleAvlEdit(link)}>
                              Edit Vendor Link
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => handleAvlRemove(link)}
                            >
                              Remove Vendor Link
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>

                    {/* Price-break sub-table (expanded) */}
                    {isExpanded && (
                      <div className="border-t border-border px-3 pb-3">
                        {priceBreaks.length === 0 ? (
                          <p className="text-xs text-muted-foreground py-2">No price breaks defined.</p>
                        ) : (
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="text-right">Qty Threshold</TableHead>
                                <TableHead className="text-right">Unit Cost</TableHead>
                                <TableHead>Lead Days</TableHead>
                                <TableHead>Costing</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {priceBreaks.map((pb: PriceBreakRead, idx: number) => {
                                const isSelected =
                                  costData?.selected_vendor_link_id === link.id &&
                                  costData?.selected_price_break_index === idx
                                const rowBg = isSelected ? 'bg-green-50' : ''

                                return (
                                  <TableRow key={pb.id} className={rowBg}>
                                    <TableCell className="font-mono text-sm text-right">
                                      {pb.qty_threshold}
                                    </TableCell>
                                    <TableCell className="font-mono text-sm text-right">
                                      {formatCostValue(pb.unit_cost)} {currency}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                      {pb.lead_days ?? '—'}
                                    </TableCell>
                                    <TableCell>
                                      {isDraft ? (
                                        <button
                                          type="button"
                                          aria-label={isSelected ? 'Selected for costing' : 'Select for costing'}
                                          onClick={() =>
                                            selectForCostingMutation.mutate({
                                              vendorLinkId: link.id,
                                              priceBreakIndex: idx,
                                            })
                                          }
                                          className="text-muted-foreground hover:text-foreground"
                                        >
                                          {isSelected ? (
                                            <CheckCircle className="h-4 w-4 text-green-600" aria-hidden="true" />
                                          ) : (
                                            <Circle className="h-4 w-4" aria-hidden="true" />
                                          )}
                                        </button>
                                      ) : (
                                        isSelected && (
                                          <CheckCircle
                                            className="h-4 w-4 text-green-600"
                                            aria-label="Selected for costing"
                                          />
                                        )
                                      )}
                                    </TableCell>
                                  </TableRow>
                                )
                              })}
                            </TableBody>
                          </Table>
                        )}

                        {/* D-14 dual-cost notice (Released) */}
                        {isReleased && costData?.released_cost_snapshot !== null && costData?.released_cost_snapshot !== undefined && (
                          <div className="mt-2 text-xs text-muted-foreground">
                            Released at:{' '}
                            <span className="font-mono text-foreground">{frozenCostDisplay} {currency}</span>
                            {effectiveCostDisplay !== frozenCostDisplay && effectiveCostDisplay !== '—' && (
                              <span className="text-amber-600 ml-2">
                                Current would be {effectiveCostDisplay} {currency}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Remove vendor link confirmation dialog */}
      <Dialog
        open={!!removingAvlLinkId}
        onOpenChange={(open) => {
          if (!open) {
            setRemovingAvlLinkId(null)
            setRemovingAvlLinkName('')
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove vendor link?</DialogTitle>
            <DialogDescription>
              This will remove {removingAvlLinkName} from the approved vendor list for this part.
              Existing revision cost data is not affected.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRemovingAvlLinkId(null)
                setRemovingAvlLinkName('')
              }}
              disabled={removeAvlLinkMutation.isPending}
            >
              Keep Link
            </Button>
            <Button
              variant="destructive"
              onClick={() => removingAvlLinkId && removeAvlLinkMutation.mutate(removingAvlLinkId)}
              disabled={removeAvlLinkMutation.isPending}
            >
              {removeAvlLinkMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Removing…
                </>
              ) : (
                'Remove Link'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Section 3: Cost & Margin ───────────────────────────────────────────── */}
      {currentRevision && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-foreground">Cost & Margin</h2>
            </div>
          </CardHeader>
          <CardContent>
            {/* Cost display grid */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground mb-0.5">
                  Material Cost{' '}
                  <span className="text-xs text-muted-foreground">{currency}</span>
                </p>
                <p className="font-mono">{materialCostDisplay}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-0.5">BOM Roll-up Cost</p>
                <p className="font-mono">{bomRollupDisplay}</p>
              </div>
              <div className="col-span-2">
                <p className="text-xs text-muted-foreground mb-0.5">
                  Effective Cost{' '}
                  {effectiveCostSource && (
                    <span className="text-xs text-muted-foreground">({effectiveCostSource})</span>
                  )}
                </p>
                <p className="font-mono font-semibold">{effectiveCostDisplay}</p>
                {/* D-14: Released frozen + live cost */}
                {isReleased && costData?.released_cost_snapshot !== null && costData?.released_cost_snapshot !== undefined && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Released at:{' '}
                    <span className="font-mono text-foreground">{frozenCostDisplay}</span>
                    {effectiveCostDisplay !== frozenCostDisplay && effectiveCostDisplay !== '—' && (
                      <span className="text-amber-600 ml-1">
                        · Current: {effectiveCostDisplay}
                      </span>
                    )}
                  </p>
                )}
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-0.5">Sale Price</p>
                <p className="font-mono">{salePriceDisplay}</p>
              </div>
              {hasSalePrice && hasEffectiveCost && (
                <>
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Margin</p>
                    <p className={`font-mono ${isNegativeMargin ? 'text-destructive' : ''}`}>
                      {marginDisplay}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Margin %</p>
                    <p className={`font-mono ${isNegativeMargin ? 'text-destructive' : ''}`}>
                      {marginPctDisplay !== '—' ? `${marginPctDisplay}%` : '—'}
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Inline edit form (Draft only) */}
            {isDraft && (
              <div className="mt-6 space-y-4">
                <div className="flex gap-4 flex-wrap">
                  <div className="space-y-1">
                    <Label htmlFor="cost-material">Material Cost</Label>
                    <Input
                      id="cost-material"
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-36 font-mono"
                      placeholder={materialCostDisplay !== '—' ? materialCostDisplay : '0.00'}
                      value={costMaterialInput}
                      onChange={(e) => setCostMaterialInput(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Optional. Leave blank to use vendor price or BOM roll-up.
                    </p>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="cost-sale-price">Sale Price</Label>
                    <Input
                      id="cost-sale-price"
                      type="number"
                      step="0.01"
                      min="0"
                      className="w-36 font-mono"
                      placeholder={salePriceDisplay !== '—' ? salePriceDisplay : '0.00'}
                      value={costSalePriceInput}
                      onChange={(e) => setCostSalePriceInput(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Optional. Used to compute margin.
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveCosts}
                  disabled={saveCostMutation.isPending}
                >
                  {saveCostMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      Saving…
                    </>
                  ) : (
                    'Save Costs'
                  )}
                </Button>
              </div>
            )}

            {/* Margin summary box (when sale price and effective cost are both available) */}
            {hasSalePrice && hasEffectiveCost && (
              <div className="mt-3 rounded-md border border-border p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Sale Price</span>
                  <span className="font-mono">{salePriceDisplay}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Effective Cost</span>
                  <span className="font-mono">{effectiveCostDisplay}</span>
                </div>
                <div
                  className={`flex justify-between border-t border-border pt-2 mt-2 font-semibold ${
                    isNegativeMargin ? 'text-destructive' : ''
                  }`}
                >
                  <span>Margin</span>
                  <span className="font-mono">
                    {marginDisplay}
                    {marginPctDisplay !== '—' ? ` (${marginPctDisplay}%)` : ''}
                  </span>
                </div>
              </div>
            )}

            {/* Empty state when no cost data and not in Draft edit mode */}
            {!isDraft && !costData && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No cost data yet.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Section 4: Where Used ──────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">Where Used</h2>
          </div>
        </CardHeader>
        <CardContent>
          {/* Extensive notice (>20 results) */}
          {sortedWhereUsed.length > 20 && (
            <div className="rounded-md border border-border p-3 text-xs text-muted-foreground mb-3">
              Showing {sortedWhereUsed.length} assemblies. This part is used extensively across the product
              structure.
            </div>
          )}

          {sortedWhereUsed.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              This part is not used in any assembly.
            </p>
          ) : (
            <ul aria-label="Where used" className="space-y-2">
              {sortedWhereUsed.map((entry) => (
                <li
                  key={`${entry.parent_part_id}-${entry.parent_revision_label ?? ''}`}
                  className="flex items-center gap-2 text-sm"
                >
                  <span className="font-medium text-foreground">
                    {entry.parent_part_number}
                  </span>
                  {entry.parent_revision_label && (
                    <span className="text-xs text-muted-foreground">
                      {entry.parent_revision_label}
                    </span>
                  )}
                  {entry.parent_revision_status && (
                    <RevisionStatusBadge status={entry.parent_revision_status} />
                  )}
                  <span className="text-xs text-muted-foreground">
                    {!entry.indirect
                      ? 'Direct parent'
                      : entry.via_part_number
                        ? `Indirect via ${entry.via_part_number}`
                        : 'Indirect parent'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

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

      {/* ── BOM Line Sheet ─────────────────────────────────────────────────── */}
      {currentRevision && (
        <BomLineSheet
          open={bomLineSheetOpen}
          mode={bomLineSheetMode}
          partId={partId}
          revisionId={currentRevision.id}
          existingLine={
            editingBomLine
              ? {
                  id: editingBomLine.bom_item_id,
                  child_part_id: editingBomLine.child_part_id,
                  child_part_number: editingBomLine.child_part_number,
                  qty: editingBomLine.quantity,
                  ref_des: editingBomLine.reference_designators,
                  unit_of_measure: editingBomLine.unit_of_measure,
                }
              : null
          }
          onClose={handleBomLineSheetClose}
        />
      )}

      {/* ── AVL Link Sheet ─────────────────────────────────────────────────── */}
      <AvlLinkSheet
        open={avlSheetOpen}
        mode={avlSheetMode}
        partId={partId}
        existingLink={editingAvlLink}
        onClose={handleAvlSheetClose}
      />
    </div>
  )
}
