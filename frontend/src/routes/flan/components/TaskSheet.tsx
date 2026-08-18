// ABOUTME: Create/edit Sheet for a FLAN task (FLAN-01.3, FLAN-01.5) — phase, summary,
// ABOUTME: status, risk, start/due dates, pinned and a multi-select assignee picker fed
// ABOUTME: by the project roster. There is NO key input: the key is server-generated
// ABOUTME: (D-V5P1-2), and a `key` in the body would be an unknown-field 422.

/**
 * TaskSheet — the shared create/edit form for a project's tasks.
 *
 * Props:
 *   open: boolean            — controls sheet visibility
 *   mode: 'create' | 'edit'  — title, mutation and which fields seed the form
 *   projectId: string        — the URL's project (D-V5P1-3); scopes phases + roster
 *   task: Task | null        — the row being edited; null in create mode
 *   defaultPhaseId: string   — phase pre-selected on create (the board's filter)
 *   onClose: () => void      — called on save success and on Cancel
 *
 * Three rules are load-bearing here:
 *
 *   - **No key input, anywhere.** A task's key is generated server-side as
 *     `<PREFIX>-<n>` under a row lock (D-V5P1-2) and `TaskCreate` has no `key`
 *     field at all, so an input for one could only post a key the API refuses
 *     with a 422. The key is shown read-only while editing, as a label.
 *   - **`due === start` is a valid zero-duration milestone** (schemas.py
 *     ::_check_date_order). Only `due < start` is refused, and it is refused by
 *     the SERVER: there is deliberately no client-side date comparison here, so
 *     the one rule lives in one place and its 422 `detail` is what the user
 *     reads.
 *   - **Assignees come from the roster** (FLAN-01.5). `useTeam(projectId)` lists
 *     active members only (roster.py::list_members excludes soft-removed ones by
 *     default — D-V5P1-6), so a removed member is structurally unselectable; the
 *     `active` filter below is belt-and-braces over that contract.
 *
 * Every key in the POST/PATCH body exists in the backend's TaskCreate /
 * TaskUpdate: phase_id, summary, status, risk_level, start_date, due_date,
 * pinned, assignee_ids. `tags` is omitted — TaskCreate defaults it to an empty
 * list and Phase 1 has no tag editor (FLAN-04 owns that).
 *
 * Mirrors routes/gelato/components/BinSheet.tsx (create/edit in one sheet, local
 * field state, `getApiErrorMessage` on the failure path).
 */

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { getApiErrorMessage } from '@/routes/crumb/components/apiError'
import { useCreateTask, usePhases, useTeam, useUpdateTask } from '../hooks'
import type { RiskLevel, Task, TaskStatus } from '../hooks'

// ─── Constants ───────────────────────────────────────────────────────────────

/** Task lifecycle values (flan_task.status / the schema's TaskStatus literal). */
const TASK_STATUSES: TaskStatus[] = ['To Do', 'In Progress', 'Done']

/** Task risk levels (flan_task.risk_level / the schema's RiskLevel literal). */
const RISK_LEVELS: Array<{ value: RiskLevel; label: string }> = [
  { value: 'none', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

// ─── Props ───────────────────────────────────────────────────────────────────

interface TaskSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  projectId: string
  task: Task | null
  defaultPhaseId?: string
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function TaskSheet({
  open,
  mode,
  projectId,
  task,
  defaultPhaseId = '',
  onClose,
}: TaskSheetProps) {
  const { data: phases = [] } = usePhases(projectId)
  // Active members only — the assignee pool (FLAN-01.5).
  const { data: team = [] } = useTeam(projectId)
  const members = team.filter((member) => member.active)
  // The seeding effect depends on this id, never on the `phases` ARRAY: the
  // `= []` default is a fresh reference on every render while the query is
  // still loading, which as a dependency would re-run the effect, re-set the
  // state to a fresh [] and loop forever.
  const firstPhaseId = phases[0]?.id ?? ''

  const [phaseId, setPhaseId] = useState('')
  const [summary, setSummary] = useState('')
  const [status, setStatus] = useState<TaskStatus>('To Do')
  const [riskLevel, setRiskLevel] = useState<RiskLevel>('none')
  const [startDate, setStartDate] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [pinned, setPinned] = useState(false)
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])

  // Seed on open: the edited task's own values, or a blank create form whose
  // phase defaults to the board's filter (falling back to the first phase).
  useEffect(() => {
    if (!open) return
    if (mode === 'edit' && task) {
      setPhaseId(task.phase_id)
      setSummary(task.summary)
      setStatus(task.status as TaskStatus)
      setRiskLevel(task.risk_level as RiskLevel)
      setStartDate(task.start_date ?? '')
      setDueDate(task.due_date ?? '')
      setPinned(task.pinned)
      setAssigneeIds(task.assignee_ids)
      return
    }
    setPhaseId(defaultPhaseId || firstPhaseId)
    setSummary('')
    setStatus('To Do')
    setRiskLevel('none')
    setStartDate('')
    setDueDate('')
    setPinned(false)
    setAssigneeIds([])
  }, [open, mode, task, defaultPhaseId, firstPhaseId])

  const createMutation = useCreateTask()
  const updateMutation = useUpdateTask()
  const isSaving = createMutation.isPending || updateMutation.isPending
  // No date rule here on purpose: `due === start` is a legal milestone and
  // `due < start` is the server's 422 to give (see the module docstring).
  const canSubmit = summary.trim() !== '' && phaseId !== ''

  function toggleAssignee(memberId: string, checked: boolean) {
    setAssigneeIds((current) =>
      checked ? [...current, memberId] : current.filter((id) => id !== memberId)
    )
  }

  function handleSave() {
    if (!canSubmit) return
    // Every key below exists in TaskCreate / TaskUpdate — and `key` is not one
    // of them: it is server-generated (D-V5P1-2).
    const payload = {
      phase_id: phaseId,
      summary: summary.trim(),
      status,
      risk_level: riskLevel,
      start_date: startDate || null,
      due_date: dueDate || null,
      pinned,
      assignee_ids: assigneeIds,
    }
    const onError = (err: unknown) => {
      toast.error(
        getApiErrorMessage(
          err,
          mode === 'edit'
            ? 'Failed to save the task. Please try again.'
            : 'Failed to create the task.'
        )
      )
    }

    if (mode === 'edit' && task) {
      updateMutation.mutate(
        { id: task.id, patch: payload },
        {
          onSuccess: (saved) => {
            toast.success(`Task ${saved.key} saved.`)
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
          toast.success(`Task ${created.key} created.`)
          onClose()
        },
        onError,
      }
    )
  }

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent
        side="right"
        aria-labelledby="task-sheet-title"
        aria-describedby="task-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="task-sheet-title">
            {mode === 'edit' ? 'Edit Task' : 'New Task'}
          </SheetTitle>
          <SheetDescription id="task-sheet-description">
            {mode === 'edit'
              ? 'Update the task. Its key was assigned when it was created and never changes.'
              : 'The task key is assigned by the server when the task is created.'}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-4">
          {/* The key is shown, never typed — there is no input for it. */}
          {mode === 'edit' && task && (
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Key</p>
              <p className="font-mono text-sm text-foreground">{task.key}</p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="task-summary">Summary</Label>
            <Input
              id="task-summary"
              aria-label="Summary"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="e.g. Draft the enclosure drawings"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="task-phase">Phase</Label>
            <Select value={phaseId} onValueChange={setPhaseId}>
              <SelectTrigger id="task-phase" aria-label="Phase">
                <SelectValue placeholder="Select a phase" />
              </SelectTrigger>
              <SelectContent>
                {phases.map((phase) => (
                  <SelectItem key={phase.id} value={phase.id}>
                    {phase.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="task-status">Status</Label>
              <Select value={status} onValueChange={(value) => setStatus(value as TaskStatus)}>
                <SelectTrigger id="task-status" aria-label="Status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TASK_STATUSES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-risk">Risk</Label>
              <Select value={riskLevel} onValueChange={(value) => setRiskLevel(value as RiskLevel)}>
                <SelectTrigger id="task-risk" aria-label="Risk">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RISK_LEVELS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="task-start-date">Start date</Label>
              <Input
                id="task-start-date"
                aria-label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-due-date">Due date</Label>
              <Input
                id="task-due-date"
                aria-label="Due date"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
              {/* Same-day is a milestone; only an earlier due date is refused. */}
              <p className="text-xs text-muted-foreground">
                A due date equal to the start date is a valid one-day milestone.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="task-pinned"
              type="checkbox"
              className="h-4 w-4"
              aria-label="Pinned"
              checked={pinned}
              onChange={(e) => setPinned(e.target.checked)}
            />
            <Label htmlFor="task-pinned">Pinned</Label>
          </div>

          {/* Assignees — the project roster, active members only (FLAN-01.5). */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Assignees</p>
            {members.length === 0 ? (
              <p className="text-sm text-muted-foreground">No one is on this project’s team yet.</p>
            ) : (
              <div className="space-y-1">
                {members.map((member) => (
                  <div key={member.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      aria-label={`Assign ${member.name}`}
                      checked={assigneeIds.includes(member.id)}
                      onChange={(e) => toggleAssignee(member.id, e.target.checked)}
                    />
                    <span className="text-sm">
                      {member.name}
                      {member.role ? (
                        <span className="text-muted-foreground"> · {member.role}</span>
                      ) : null}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <SheetFooter className="flex gap-2 pt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSave} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                {mode === 'edit' ? 'Saving…' : 'Creating…'}
              </>
            ) : mode === 'edit' ? (
              'Save Task'
            ) : (
              'Create Task'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
