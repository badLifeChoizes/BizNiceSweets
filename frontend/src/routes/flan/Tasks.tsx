// ABOUTME: FLAN Tasks screen (/flan/projects/:projectId/tasks) — one project's tasks in
// ABOUTME: the ORDER THE API RETURNS THEM (numeric key order, never re-sorted here),
// ABOUTME: with filters for phase and assignee (FLAN-01.5) and a create/edit Sheet.
// ABOUTME: The key column renders the server-generated key; nothing here can type one.

/**
 * Tasks screen — one project's units of work (FLAN-01.3, FLAN-01.5).
 *
 * Layout: p-8 space-y-6, mirroring routes/flan/Phases.tsx.
 *
 * Table columns: Key | Summary | Phase | Status | Start | Due | Risk | Pinned
 *                | Assignees | Actions
 *
 * Two rules are load-bearing here:
 *
 *   - **The rows are rendered in the order the API returns them.** Task keys are
 *     UNPADDED (`PRJ-9`, `PRJ-10` — D-V5P1-7), so a plain string sort would put
 *     `PRJ-10` before `PRJ-9`; `tasks.py::list_tasks` therefore orders on the
 *     key's NUMERIC suffix. Re-sorting that list in the browser would reintroduce
 *     exactly the bug the service went out of its way to avoid, so this screen
 *     has no `.sort()` at all.
 *   - **There is no key input anywhere** (D-V5P1-2). A task's key is generated
 *     server-side; `TaskCreate` has no `key` field, so a key in a POST body would
 *     be a 422. The column below shows what the API assigned.
 *
 * The two filters are part of the query key (`tasksKey(projectId, phaseId,
 * assigneeId)`), so choosing one re-fetches with `phase_id` / `assignee_id` in
 * the request rather than narrowing a cached list on the client — the board is
 * filtered by the database, which is what makes the assignee filter FLAN-01.5's
 * "the board can be filtered by assignee" and not a display trick.
 *
 * The active project is the URL (D-V5P1-3): `useParams().projectId` scopes every
 * query and mutation here, and no "current project" state exists.
 */

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
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
import { FlanNav } from './components/FlanNav'
import { TaskSheet } from './components/TaskSheet'
import { usePhases, useTasks, useTeam } from './hooks'
import type { Task } from './hooks'

// ─── Constants ───────────────────────────────────────────────────────────────

/** Sentinel for "no filter" — Radix forbids an empty SelectItem value. */
const ALL = 'all'

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Format a date-only ISO string (`2026-01-05`) for display; null → em-dash.
 *
 * The `T00:00:00` suffix parses the value in the LOCAL zone (Phases.tsx carries
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

/** Risk slug → display label; an unknown value is shown as it came. */
function formatRisk(risk: string): string {
  return risk.charAt(0).toUpperCase() + risk.slice(1)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Task status pill — colour AND text together, never colour alone. */
function TaskStatusBadge({ status }: { status: string }) {
  const className =
    status === 'Done'
      ? 'border-green-300 bg-green-50 text-green-700'
      : status === 'In Progress'
        ? 'border-blue-300 bg-blue-50 text-blue-700'
        : 'text-muted-foreground'
  return (
    <Badge variant="outline" className={className}>
      {status}
    </Badge>
  )
}

/** Risk pill — same rule: the level is always spelled out, not just coloured. */
function RiskBadge({ risk }: { risk: string }) {
  const className =
    risk === 'high'
      ? 'border-red-300 bg-red-50 text-red-700'
      : risk === 'medium'
        ? 'border-amber-300 bg-amber-50 text-amber-700'
        : risk === 'low'
          ? 'border-slate-300 bg-slate-50 text-slate-700'
          : 'text-muted-foreground'
  return (
    <Badge variant="outline" className={className}>
      {formatRisk(risk)}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Tasks() {
  // The URL is the active project (D-V5P1-3) — no "current project" state here.
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [phaseFilter, setPhaseFilter] = useState(ALL)
  const [assigneeFilter, setAssigneeFilter] = useState(ALL)
  const [createOpen, setCreateOpen] = useState(false)
  const [editTask, setEditTask] = useState<Task | null>(null)

  const { data: phases = [] } = usePhases(projectId)
  const { data: team = [] } = useTeam(projectId)
  // Active members only — a soft-removed member is out of the pickers
  // (D-V5P1-6); the API already excludes them, this is belt-and-braces.
  const members = team.filter((member) => member.active)

  // The filters ride in the query key AND in the request params, so a change
  // re-fetches from the server rather than filtering a cached list.
  const {
    data: tasks = [],
    isLoading,
    isError,
  } = useTasks(
    projectId,
    phaseFilter === ALL ? undefined : phaseFilter,
    assigneeFilter === ALL ? undefined : assigneeFilter
  )

  const phaseNames = new Map(phases.map((phase) => [phase.id, phase.name]))
  const memberNames = new Map(team.map((member) => [member.id, member.name]))

  /** Assignee ids → roster names; an id with no roster row shows as itself. */
  function assigneeLabel(ids: string[]): string {
    if (ids.length === 0) return '—'
    return ids.map((id) => memberNames.get(id) ?? id).join(', ')
  }

  return (
    <div className="p-8 space-y-6">
      <FlanNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Tasks</h1>
        <p className="text-base font-normal text-muted-foreground">
          Every task belongs to a phase, and its key is assigned by the server when it is created.
        </p>
      </div>

      {/* Toolbar: the two filters, then New Task */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="task-filter-phase">Phase</Label>
          <Select value={phaseFilter} onValueChange={setPhaseFilter}>
            <SelectTrigger id="task-filter-phase" aria-label="Filter by phase" className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All phases</SelectItem>
              {phases.map((phase) => (
                <SelectItem key={phase.id} value={phase.id}>
                  {phase.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="task-filter-assignee">Assignee</Label>
          <Select value={assigneeFilter} onValueChange={setAssigneeFilter}>
            <SelectTrigger
              id="task-filter-assignee"
              aria-label="Filter by assignee"
              className="w-56"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All assignees</SelectItem>
              {members.map((member) => (
                <SelectItem key={member.id} value={member.id}>
                  {member.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="default"
          className="ml-auto"
          onClick={() => setCreateOpen(true)}
          disabled={phases.length === 0}
        >
          New Task
        </Button>
      </div>

      {/* Tasks table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load tasks. Check your connection and refresh the page.
          </p>
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No tasks</p>
          <p className="text-sm text-muted-foreground">
            {phaseFilter === ALL && assigneeFilter === ALL
              ? 'Create the first task to start tracking work on this project.'
              : 'No task matches the current filters.'}
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Summary</TableHead>
              <TableHead>Phase</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>Due</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Pinned</TableHead>
              <TableHead>Assignees</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* The server's order (numeric key suffix — D-V5P1-7). Never sorted
                here: `PRJ-10` sorts before `PRJ-9` as a string. */}
            {tasks.map((task) => (
              <TableRow key={task.id} className="h-12" aria-label={`Task ${task.key}`}>
                {/* The server-generated key, exactly as the API returned it. */}
                <TableCell className="font-mono font-medium">{task.key}</TableCell>
                <TableCell>{task.summary}</TableCell>
                <TableCell>{phaseNames.get(task.phase_id) ?? '—'}</TableCell>
                <TableCell>
                  <TaskStatusBadge status={task.status} />
                </TableCell>
                <TableCell>{formatDate(task.start_date)}</TableCell>
                <TableCell>{formatDate(task.due_date)}</TableCell>
                <TableCell>
                  <RiskBadge risk={task.risk_level} />
                </TableCell>
                <TableCell>{task.pinned ? 'Pinned' : '—'}</TableCell>
                <TableCell>{assigneeLabel(task.assignee_ids)}</TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Edit ${task.key}`}
                    onClick={() => setEditTask(task)}
                  >
                    Edit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Create / edit sheet ──────────────────────────────────────────── */}
      <TaskSheet
        open={createOpen || editTask !== null}
        mode={editTask ? 'edit' : 'create'}
        projectId={projectId}
        task={editTask}
        defaultPhaseId={phaseFilter === ALL ? '' : phaseFilter}
        onClose={() => {
          setCreateOpen(false)
          setEditTask(null)
        }}
      />
    </div>
  )
}
