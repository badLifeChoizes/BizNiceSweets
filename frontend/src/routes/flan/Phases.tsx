// ABOUTME: FLAN Phases screen (/flan/projects/:projectId/phases) — a project's phases in
// ABOUTME: sort_order with their DERIVED start date, due date, % complete and task counts
// ABOUTME: rendered read-only (D-V5-1), plus create/edit (name, order, status, description
// ABOUTME: only — no date, no percent) and a delete that names the tasks it cascades to.

/**
 * Phases screen — one project's ordered stages (FLAN-01.2).
 *
 * Layout: p-8 space-y-6, mirroring routes/flan/Projects.tsx.
 *
 * Table columns: Phase | Status | Derived start | Derived due | % complete
 *                | Tasks | Actions
 *
 * **The four derived columns are the point of this screen** (D-V5-1). A phase's
 * start date, due date and % complete are rolled up from its tasks on every read
 * and are never hand-set, so here they are:
 *
 *   - **rendered, never computed.** `percent_complete` arrives from the server as
 *     an exact two-decimal STRING (D-11 — "33.33", "0.00"); it is printed
 *     verbatim with a `%` appended. It is never `parseFloat`ed, never reformatted
 *     and never re-derived from `done_count / task_count`: client-side arithmetic
 *     would round on its own terms and silently disagree with the server's
 *     ROUND_HALF_UP Decimal.
 *   - **read-only, and said so.** Each derived cell carries a tooltip stating it
 *     is derived from the phase's tasks and not editable, so the absence of an
 *     edit affordance reads as a rule rather than an omission.
 *   - **null-safe.** A phase with no tasks (and equally a phase whose tasks all
 *     lack dates — SQL MIN/MAX skip NULLs) reports no dates at all; both render
 *     an em-dash, and its percentage is the server's "0.00".
 *
 * The create/edit dialog therefore exposes name, order, status and description
 * and nothing else: `PhaseCreate`/`PhaseUpdate` carry no date or percent field
 * and `flan_phase` has no such column, so an input for one would write to
 * nothing.
 *
 * Row order is the server's (`sort_order`, then name) — the list is rendered as
 * it arrives, never re-sorted here.
 *
 * The active project is the URL (D-V5P1-3): `useParams().projectId` scopes every
 * query and mutation on this screen, and no "current project" state exists.
 *
 * Deleting a phase cascades to its tasks in the database, so the confirmation
 * names how many tasks go with it (`task_count`, from the same rollup).
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Loader2, MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { getApiErrorMessage } from '@/routes/crumb/components/apiError'
import { FlanNav } from './components/FlanNav'
import { useCreatePhase, useDeletePhase, usePhases, useUpdatePhase } from './hooks'
import type { Phase, PhaseStatus } from './hooks'

// ─── Constants ───────────────────────────────────────────────────────────────

/** The one sentence every derived cell says: these values come from the tasks. */
const DERIVED_TOOLTIP = "derived from this phase's tasks — not editable"

/** Phase lifecycle values (flan_phase.status / the schema's PhaseStatus literal). */
const STATUSES: Array<{ value: PhaseStatus; label: string }> = [
  { value: 'pending', label: 'Pending' },
  { value: 'in-progress', label: 'In Progress' },
  { value: 'complete', label: 'Complete' },
]

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Format a date-only ISO string (`2026-01-05`) for display; null → em-dash.
 *
 * The `T00:00:00` suffix parses the value in the LOCAL zone (Projects.tsx has
 * the same note): `new Date('2026-01-05')` is UTC midnight and would render as
 * the previous day west of Greenwich.
 */
function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

/** Status slug → display label; an unknown value is shown as it came. */
function formatStatus(status: string): string {
  return STATUSES.find((option) => option.value === status)?.label ?? status
}

/** "no tasks" / "1 task" / "5 tasks" — used in the delete confirmation. */
function taskCountLabel(count: number): string {
  if (count === 0) return 'no tasks'
  return count === 1 ? '1 task' : `${count} tasks`
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Phase status pill — colour AND text together, never colour alone. */
function PhaseStatusBadge({ status }: { status: string }) {
  const className =
    status === 'complete'
      ? 'border-green-300 bg-green-50 text-green-700'
      : status === 'in-progress'
        ? 'border-blue-300 bg-blue-50 text-blue-700'
        : 'text-muted-foreground'
  return (
    <Badge variant="outline" className={className}>
      {formatStatus(status)}
    </Badge>
  )
}

/**
 * A derived cell's content: shown, never edited.
 *
 * The value is passed in already formatted — this wrapper adds no arithmetic of
 * its own, it only says (via the tooltip) where the number came from and that
 * nothing here can change it.
 */
function DerivedValue({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="cursor-default">
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent>{DERIVED_TOOLTIP}</TooltipContent>
    </Tooltip>
  )
}

/**
 * Create / edit a phase — name, order, status and description, and nothing else.
 *
 * **There is deliberately no date input and no percent input here** (D-V5-1).
 * The phase write schemas carry no such field and `flan_phase` has no such
 * column, so an input for one would post a key the server ignores at best and
 * 422s at worst. A phase's dates move by editing its TASKS.
 *
 * `phase === null` is the create case (POST under the project); otherwise the
 * fields seed from the phase and submit is a PATCH. Mirrors
 * components/ProjectCreateDialog.tsx: local field state, one mutation from
 * ./hooks, `getApiErrorMessage` on the failure path so a 4xx is reported in the
 * server's own words.
 */
function PhaseFormDialog({
  open,
  projectId,
  phase,
  onClose,
}: {
  open: boolean
  projectId: string
  phase: Phase | null
  onClose: () => void
}) {
  const [name, setName] = useState('')
  const [sortOrder, setSortOrder] = useState('0')
  const [status, setStatus] = useState<PhaseStatus>('pending')
  const [description, setDescription] = useState('')

  // Seed on open: the edited phase's own values, or a blank create form.
  useEffect(() => {
    if (!open) return
    setName(phase?.name ?? '')
    setSortOrder(String(phase?.sort_order ?? 0))
    setStatus((phase?.status as PhaseStatus) ?? 'pending')
    setDescription(phase?.description ?? '')
  }, [open, phase])

  const createMutation = useCreatePhase()
  const updateMutation = useUpdatePhase()
  const isEditing = phase !== null
  const isSaving = createMutation.isPending || updateMutation.isPending
  const canSubmit = name.trim() !== ''

  function handleSubmit() {
    if (!canSubmit) return
    // Every key below exists in PhaseCreate / PhaseUpdate — and none of them is
    // a date or a percentage, because neither schema has one (D-V5-1).
    const payload = {
      name: name.trim(),
      sort_order: Number.parseInt(sortOrder, 10) || 0,
      status,
      description: description.trim() || null,
    }
    const onError = (err: unknown) => {
      toast.error(
        getApiErrorMessage(
          err,
          isEditing ? 'Failed to save the phase. Please try again.' : 'Failed to create the phase.'
        )
      )
    }

    if (isEditing) {
      updateMutation.mutate(
        { id: phase.id, patch: payload },
        {
          onSuccess: (saved) => {
            toast.success(`Phase “${saved.name}” saved.`)
            onClose()
          },
          onError,
        }
      )
      return
    }
    createMutation.mutate(
      { projectId, payload },
      {
        onSuccess: (created) => {
          toast.success(`Phase “${created.name}” created.`)
          onClose()
        },
        onError,
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent aria-describedby="phase-form-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Phase' : 'New Phase'}</DialogTitle>
          <DialogDescription id="phase-form-description">
            A phase’s start date, due date and % complete are derived from its tasks and cannot be
            set here — add or update tasks to move them.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="phase-name">Name</Label>
            <Input
              id="phase-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Design"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phase-order">Order</Label>
              <Input
                id="phase-order"
                aria-label="Order"
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phase-status">Status</Label>
              <Select value={status} onValueChange={(value) => setStatus(value as PhaseStatus)}>
                <SelectTrigger id="phase-status" aria-label="Status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="phase-description">Description</Label>
            <Input
              id="phase-description"
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
            />
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                {isEditing ? 'Saving…' : 'Creating…'}
              </>
            ) : isEditing ? (
              'Save Phase'
            ) : (
              'Create Phase'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Delete confirmation — a hard delete that takes the phase's tasks with it.
 *
 * `flan_task.phase_id` is ON DELETE CASCADE, so deleting a phase deletes its
 * tasks (and their tags and assignments) in the database. The copy therefore
 * names the count from the phase's own rollup rather than saying "and its
 * tasks": a user about to lose five tasks should be told it is five.
 */
function PhaseDeleteDialog({
  open,
  projectId,
  phase,
  onClose,
}: {
  open: boolean
  projectId: string
  phase: Phase | null
  onClose: () => void
}) {
  const deleteMutation = useDeletePhase()
  const isDeleting = deleteMutation.isPending

  function handleConfirm() {
    if (!phase) return
    deleteMutation.mutate(
      { id: phase.id, projectId },
      {
        onSuccess: () => {
          toast(`Phase “${phase.name}” deleted with ${taskCountLabel(phase.task_count)}.`)
          onClose()
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to delete the phase. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        aria-labelledby="phase-delete-title"
        aria-describedby="phase-delete-description"
      >
        <DialogHeader>
          <DialogTitle id="phase-delete-title">Delete phase?</DialogTitle>
          <DialogDescription id="phase-delete-description">
            {phase
              ? phase.task_count === 0
                ? `${phase.name} has no tasks. Deleting it cannot be undone.`
                : `${phase.name} has ${taskCountLabel(phase.task_count)}. Deleting the phase deletes ${
                    phase.task_count === 1 ? 'that task' : `those ${phase.task_count} tasks`
                  } with it, and cannot be undone.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Keep Phase
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting}
            aria-label={phase ? `Delete ${phase.name}` : 'Delete phase'}
          >
            {isDeleting ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Deleting…
              </>
            ) : (
              'Delete Phase'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Phases() {
  // The URL is the active project (D-V5P1-3) — no "current project" state here.
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [createOpen, setCreateOpen] = useState(false)
  const [editPhase, setEditPhase] = useState<Phase | null>(null)
  const [deletePhase, setDeletePhase] = useState<Phase | null>(null)

  const { data: phases = [], isLoading, isError } = usePhases(projectId)

  return (
    <div className="p-8 space-y-6">
      <FlanNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Phases</h1>
        <p className="text-base font-normal text-muted-foreground">
          Phases are the project’s ordered stages. Their dates and progress come from the tasks
          inside them, so they are shown here but never entered.
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Phase
        </Button>
      </div>

      {/* Phases table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load phases. Check your connection and refresh the page.
          </p>
        </div>
      ) : phases.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No phases yet</p>
          <p className="text-sm text-muted-foreground">
            Create the first phase to start planning this project.
          </p>
        </div>
      ) : (
        <TooltipProvider delayDuration={0}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Phase</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Derived start</TableHead>
                <TableHead>Derived due</TableHead>
                <TableHead>% complete</TableHead>
                <TableHead>Tasks</TableHead>
                <TableHead className="w-12">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {/* Server order (sort_order, then name) — never re-sorted here. */}
              {phases.map((phase) => (
                <TableRow key={phase.id} className="h-12" aria-label={`Phase ${phase.name}`}>
                  <TableCell className="font-medium">{phase.name}</TableCell>
                  <TableCell>
                    <PhaseStatusBadge status={phase.status} />
                  </TableCell>
                  <TableCell>
                    <DerivedValue>{formatDate(phase.derived_start_date)}</DerivedValue>
                  </TableCell>
                  <TableCell>
                    <DerivedValue>{formatDate(phase.derived_due_date)}</DerivedValue>
                  </TableCell>
                  {/* The server's own two-decimal string, printed verbatim (D-11).
                      Never parseFloat, never reformat, never done/task math. */}
                  <TableCell className="font-mono text-sm">
                    <DerivedValue>{`${phase.percent_complete}%`}</DerivedValue>
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    <DerivedValue>{`${phase.done_count} of ${phase.task_count}`}</DerivedValue>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11"
                          aria-label={`Phase actions for ${phase.name}`}
                        >
                          <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Open actions menu</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditPhase(phase)}>Edit</DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeletePhase(phase)}
                          className="text-destructive focus:text-destructive"
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TooltipProvider>
      )}

      {/* ─── Create / edit dialog ─────────────────────────────────────────── */}
      <PhaseFormDialog
        open={createOpen || editPhase !== null}
        projectId={projectId}
        phase={editPhase}
        onClose={() => {
          setCreateOpen(false)
          setEditPhase(null)
        }}
      />

      {/* ─── Delete confirmation ──────────────────────────────────────────── */}
      <PhaseDeleteDialog
        open={deletePhase !== null}
        projectId={projectId}
        phase={deletePhase}
        onClose={() => setDeletePhase(null)}
      />
    </div>
  )
}
