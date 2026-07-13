// ABOUTME: MOUSSE Work Order detail (/mousse/work-orders/:id) — header/status, the
// ABOUTME: Release/Hold/Resume FSM actions, an Issue-components seam, and the snapshot
// ABOUTME: component lines (qty_required / on_hand / issued_so_far, under-issue flagged).

/**
 * WorkOrderDetail — single work-order view (/mousse/work-orders/:id) (MOUSSE-01, SC7).
 *
 * Layout: p-8 space-y-6 (matches the SYERP PurchaseOrderDetail), Back link →
 * /mousse/work-orders.
 *
 * Data:
 *   - WO + components: GET /api/v1/mousse/work-orders/{id} (useWorkOrder) → key
 *                      ['mousse','work-orders', id]
 *   - Parts:           GET /api/v1/plum/parts (resolve part ids → part_number)
 *
 * Header card: WO number, status Badge (color+text), part NAME, planned qty, dates.
 *
 * Actions (FSM — server is the source of truth, buttons only mirror it):
 *   - Release — visible/enabled ONLY on `draft`.               POST …/release
 *   - Issue   — visible on `released` | `in_progress`.         opens IssueComponentsDialog
 *   - Hold    — visible ONLY on `in_progress`.                 POST …/hold
 *   - Resume  — visible ONLY on `on_hold`.                     POST …/resume
 *   All invalidate the detail + list queries and toast on success; a 4xx surfaces
 *   toast.error(server detail).
 *
 * Component lines: child part | required | on hand | issued so far. A line where
 * issued_so_far < qty_required is flagged (amber "Short" badge) so under-issue is
 * visible at a glance. Decimals arrive as STRINGS (D-11); Number() only to compare.
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
import { MousseNav } from './components/MousseNav'
import { IssueComponentsDialog } from './components/IssueComponentsDialog'
import { CompleteWorkOrderDialog } from './components/CompleteWorkOrderDialog'
import { WorkOrderStatusBadge } from './WorkOrders'
import { useWorkOrder, workOrdersKey, workOrderKey } from './hooks'
import type { WorkOrderComponentRead } from './hooks'
import type { PartRead } from '../plum/components/PartSheet'

// Statuses for which the Issue-components action is offered.
const ISSUABLE_STATUSES = new Set(['released', 'in_progress'])

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchParts(): Promise<PartRead[]> {
  return apiClient.get<PartRead[]>('/api/v1/plum/parts').then((r) => r.data)
}

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

// A component line is under-issued when it has issued less than it requires.
export function isUnderIssued(c: WorkOrderComponentRead): boolean {
  const required = Number(c.qty_required)
  const issued = Number(c.issued_so_far)
  if (!Number.isFinite(required) || !Number.isFinite(issued)) return false
  return issued < required
}

// ─── Main component ──────────────────────────────────────────────────────────

export function WorkOrderDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [issueOpen, setIssueOpen] = useState(false)
  const [completeOpen, setCompleteOpen] = useState(false)

  // ── Data ──
  const { data: wo, isLoading, isError } = useWorkOrder(id)

  const { data: parts = [] } = useQuery<PartRead[], Error>({
    queryKey: ['plum', 'parts'],
    queryFn: fetchParts,
  })

  const partName = (pid: string) => parts.find((p) => p.id === pid)?.part_number ?? pid

  // ── Refresh the detail + list after a state change ──
  function invalidateWo() {
    void queryClient.invalidateQueries({ queryKey: workOrderKey(id) })
    void queryClient.invalidateQueries({ queryKey: workOrdersKey })
  }

  // ── FSM mutations: release / hold / resume ──
  const releaseMutation = useMutation<unknown, Error, void>({
    mutationFn: () =>
      apiClient.post(`/api/v1/mousse/work-orders/${id}/release`).then((r) => r.data),
    onSuccess: () => {
      invalidateWo()
      toast.success('Work order released.')
    },
    onError: (err) => toast.error(getApiErrorMessage(err, 'Failed to release work order.')),
  })

  const holdMutation = useMutation<unknown, Error, void>({
    mutationFn: () =>
      apiClient.post(`/api/v1/mousse/work-orders/${id}/hold`).then((r) => r.data),
    onSuccess: () => {
      invalidateWo()
      toast.success('Work order placed on hold.')
    },
    onError: (err) => toast.error(getApiErrorMessage(err, 'Failed to hold work order.')),
  })

  const resumeMutation = useMutation<unknown, Error, void>({
    mutationFn: () =>
      apiClient.post(`/api/v1/mousse/work-orders/${id}/resume`).then((r) => r.data),
    onSuccess: () => {
      invalidateWo()
      toast.success('Work order resumed.')
    },
    onError: (err) => toast.error(getApiErrorMessage(err, 'Failed to resume work order.')),
  })

  const isMutating =
    releaseMutation.isPending || holdMutation.isPending || resumeMutation.isPending

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !wo) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load work order. Check your connection and try again.
        </p>
      </div>
    )
  }

  const canRelease = wo.status === 'draft'
  const canIssue = ISSUABLE_STATUSES.has(wo.status)
  const canHold = wo.status === 'in_progress'
  const canResume = wo.status === 'on_hold'
  const canComplete = wo.status === 'in_progress'

  // ── Render: main ──
  return (
    <div className="p-8 space-y-6">
      <MousseNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/mousse/work-orders')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Work Orders
      </Button>

      {/* WO header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{wo.wo_number}</p>
                <WorkOrderStatusBadge status={wo.status} />
              </div>
              <p className="text-base text-muted-foreground mt-0.5">
                {partName(wo.plum_part_id)}
              </p>
            </div>
            {/* FSM actions — mirror server-allowed transitions */}
            <div className="flex items-center gap-2 shrink-0">
              {canRelease && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => releaseMutation.mutate()}
                  disabled={isMutating}
                >
                  {releaseMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Releasing…
                    </>
                  ) : (
                    'Release'
                  )}
                </Button>
              )}
              {canIssue && (
                <Button variant="default" size="sm" onClick={() => setIssueOpen(true)}>
                  Issue Components
                </Button>
              )}
              {canComplete && (
                <Button variant="default" size="sm" onClick={() => setCompleteOpen(true)}>
                  Complete
                </Button>
              )}
              {canHold && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => holdMutation.mutate()}
                  disabled={isMutating}
                >
                  {holdMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Holding…
                    </>
                  ) : (
                    'Hold'
                  )}
                </Button>
              )}
              {canResume && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => resumeMutation.mutate()}
                  disabled={isMutating}
                >
                  {resumeMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Resuming…
                    </>
                  ) : (
                    'Resume'
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Planned qty</p>
              <p className="font-mono font-semibold">{wo.planned_qty}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">WO date</p>
              <p>{formatDate(wo.wo_date)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Completed</p>
              <p>{wo.completed_at ? formatDate(wo.completed_at) : '—'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Component lines: child part | required | on hand | issued so far */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Components</h2>
        </CardHeader>
        <CardContent>
          {wo.components.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No components snapshotted yet — release the work order to snapshot its BOM.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Component</TableHead>
                  <TableHead className="text-right">Required</TableHead>
                  <TableHead className="text-right">On hand</TableHead>
                  <TableHead className="text-right">Issued so far</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {wo.components.map((c) => {
                  const short = isUnderIssued(c)
                  return (
                    <TableRow key={c.id} className="h-12">
                      <TableCell className="font-medium">{partName(c.child_part_id)}</TableCell>
                      <TableCell className="text-right font-mono">{c.qty_required}</TableCell>
                      <TableCell className="text-right font-mono">{c.on_hand}</TableCell>
                      <TableCell className="text-right font-mono">{c.issued_so_far}</TableCell>
                      <TableCell>
                        {short ? (
                          <Badge
                            variant="outline"
                            className="border-amber-300 bg-amber-50 text-amber-700"
                          >
                            Short
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="border-green-300 bg-green-50 text-green-700"
                          >
                            Fully issued
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Issue-components dialog */}
      <IssueComponentsDialog
        workOrderId={id}
        components={wo.components}
        partName={partName}
        open={issueOpen}
        onOpenChange={setIssueOpen}
        onSuccess={invalidateWo}
      />

      {/* Complete dialog */}
      <CompleteWorkOrderDialog
        workOrderId={id}
        components={wo.components}
        partName={partName}
        open={completeOpen}
        onOpenChange={setCompleteOpen}
        onSuccess={invalidateWo}
      />
    </div>
  )
}
