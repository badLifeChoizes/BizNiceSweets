// ABOUTME: FLAN (Project Management) TanStack Query hooks + shared request/response
// ABOUTME: types. Wraps the /api/v1/flan/* API (projects CRUD + archive, phases CRUD,
// ABOUTME: tasks, team roster and assignment) through the single axios client. Every
// ABOUTME: task write also invalidates its project's phases. A phase's derived_start_date,
// ABOUTME: derived_due_date and percent_complete are DERIVED read-only values — the
// ABOUTME: percentage is an exact STRING (D-11): render as-is, never float math.

/**
 * FLAN project & phase hooks — the query seam shared by the Projects, Phases,
 * Tasks and Team screens (FLAN-01.1, FLAN-01.2, FLAN-01.6).
 *
 * Query keys (kept in one place so mutations can invalidate consistently):
 *   ['flan', 'projects']              — the project list
 *   ['flan', 'projects', id]          — one project's detail
 *   ['flan', 'phases', projectId]     — one project's phases, in sort_order
 *   ['flan', 'tasks', projectId, …]   — one project's tasks (+ optional filters)
 *   ['flan', 'task', id]              — one task's detail
 *   ['flan', 'team', projectId]       — one project's roster
 *
 * Reads are GETs; every mutation invalidates the affected keys after it resolves.
 *
 * **A phase's dates and % complete can never be written** (D-V5-1). They are
 * rolled up from the phase's tasks on every read, so `PhaseCreatePayload` and
 * `PhaseUpdatePayload` deliberately carry no date and no percent field — exactly
 * like the backend's PhaseCreate/PhaseUpdate schemas. If a date field is ever
 * needed in a phase payload, the answer is a task write, not a new field here.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

// ─── Types (mirror backend/app/modules/flan/schemas.py) ───────────────────────
// A phase's percent_complete is a quantized Decimal serialized as an exact
// STRING (D-11) — it is already at two places, so render it verbatim.

/** Phase lifecycle status. */
export type PhaseStatus = 'pending' | 'in-progress' | 'complete'

/** Project row (ProjectRead). `active: false` means archived — data kept, writes refused. */
export interface Project {
  id: string
  name: string
  key_prefix: string
  category: string | null
  description: string | null
  currency: string
  start_date: string | null
  gate_date: string | null
  active: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

/**
 * Phase row (PhaseRead) — the stored fields plus the per-read task rollup.
 *
 * `derived_start_date` / `derived_due_date` are ISO dates and are null when the
 * phase has no tasks (and also when none of its tasks carries a date, since SQL
 * MIN/MAX skip NULLs). `percent_complete` is a two-decimal STRING — "0.00" for an
 * empty phase, "33.33" for one task of three done. **Render it as-is: never float
 * math, never reformat it** (D-11) — the backend already quantized it to two
 * places. `task_count` / `done_count` are the counts that percentage came from,
 * so "2 of 5" needs no recomputation.
 *
 * All three derived values are read-only; no write schema in this module accepts them.
 */
export interface Phase {
  id: string
  project_id: string
  name: string
  sort_order: number
  status: string
  description: string | null
  derived_start_date: string | null
  derived_due_date: string | null
  percent_complete: string
  task_count: number
  done_count: number
}

// ─── Request payload types (mirror the Create/Update schemas) ─────────────────

/** Project creation payload (ProjectCreate). `key_prefix` is derived from the name when omitted. */
export interface ProjectCreatePayload {
  name: string
  key_prefix?: string | null
  category?: string | null
  description?: string | null
  currency?: string
  start_date?: string | null
  gate_date?: string | null
  tags?: string[]
}

/**
 * Project PATCH payload (ProjectUpdate). `active` is absent — archiving is its own
 * endpoint; `key_prefix` is accepted only while the project has no tasks (422 after).
 * Supplying `tags` REPLACES the project's tag set.
 */
export interface ProjectUpdatePayload {
  name?: string | null
  key_prefix?: string | null
  category?: string | null
  description?: string | null
  currency?: string | null
  start_date?: string | null
  gate_date?: string | null
  tags?: string[] | null
}

/** Phase creation payload (PhaseCreate) — no date, no percent, by design (D-V5-1). */
export interface PhaseCreatePayload {
  name: string
  sort_order?: number
  status?: PhaseStatus
  description?: string | null
}

/** Phase PATCH payload (PhaseUpdate) — no date, no percent, by design (D-V5-1). */
export interface PhaseUpdatePayload {
  name?: string | null
  sort_order?: number | null
  status?: PhaseStatus | null
  description?: string | null
}

// ─── Query keys ───────────────────────────────────────────────────────────────

export const projectsKey = () => ['flan', 'projects'] as const
export const projectKey = (id: string) => ['flan', 'projects', id] as const
export const phasesKey = (projectId: string) => ['flan', 'phases', projectId] as const

// ─── API helpers ──────────────────────────────────────────────────────────────

function fetchProjects(includeArchived: boolean): Promise<Project[]> {
  return apiClient
    .get<Project[]>('/api/v1/flan/projects', { params: { include_archived: includeArchived } })
    .then((r) => r.data)
}

function fetchProject(id: string): Promise<Project> {
  return apiClient.get<Project>(`/api/v1/flan/projects/${id}`).then((r) => r.data)
}

function fetchPhases(projectId: string): Promise<Phase[]> {
  return apiClient.get<Phase[]>(`/api/v1/flan/projects/${projectId}/phases`).then((r) => r.data)
}

// ─── Queries ──────────────────────────────────────────────────────────────────

/** Project list (archived excluded unless includeArchived). */
export function useProjects(includeArchived = false) {
  return useQuery<Project[], Error>({
    queryKey: [...projectsKey(), includeArchived] as const,
    queryFn: () => fetchProjects(includeArchived),
  })
}

/** One project's detail. */
export function useProject(id: string) {
  return useQuery<Project, Error>({
    queryKey: projectKey(id),
    queryFn: () => fetchProject(id),
    enabled: !!id,
  })
}

/** One project's phases, in sort_order, each carrying its derived rollup (D-V5-1). */
export function usePhases(projectId: string) {
  return useQuery<Phase[], Error>({
    queryKey: phasesKey(projectId),
    queryFn: () => fetchPhases(projectId),
    enabled: !!projectId,
  })
}

// ─── Mutations ────────────────────────────────────────────────────────────────

/** Create a project. Invalidates the project list. */
export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, ProjectCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Project>('/api/v1/flan/projects', payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: projectsKey() })
    },
  })
}

/** PATCH a project. Invalidates the list and that project's detail. */
export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, { id: string; patch: ProjectUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<Project>(`/api/v1/flan/projects/${id}`, patch).then((r) => r.data),
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: projectsKey() })
      qc.invalidateQueries({ queryKey: projectKey(project.id) })
    },
  })
}

/** Soft-archive a project (idempotent). Invalidates the list and that project's detail. */
export function useArchiveProject() {
  const qc = useQueryClient()
  return useMutation<Project, Error, string>({
    mutationFn: (id) =>
      apiClient.post<Project>(`/api/v1/flan/projects/${id}/archive`).then((r) => r.data),
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: projectsKey() })
      qc.invalidateQueries({ queryKey: projectKey(project.id) })
    },
  })
}

/** Create a phase under a project. Invalidates that project's phases. */
export function useCreatePhase() {
  const qc = useQueryClient()
  return useMutation<Phase, Error, { projectId: string; payload: PhaseCreatePayload }>({
    mutationFn: ({ projectId, payload }) =>
      apiClient
        .post<Phase>(`/api/v1/flan/projects/${projectId}/phases`, payload)
        .then((r) => r.data),
    onSuccess: (phase) => {
      qc.invalidateQueries({ queryKey: phasesKey(phase.project_id) })
    },
  })
}

/** PATCH a phase's name/order/status/description. Invalidates that project's phases. */
export function useUpdatePhase() {
  const qc = useQueryClient()
  return useMutation<Phase, Error, { id: string; patch: PhaseUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<Phase>(`/api/v1/flan/phases/${id}`, patch).then((r) => r.data),
    onSuccess: (phase) => {
      qc.invalidateQueries({ queryKey: phasesKey(phase.project_id) })
    },
  })
}

/**
 * Delete a phase, cascading to its tasks. Invalidates that project's phases AND
 * its tasks — `projectId` is passed in because the deleted row can no longer
 * supply it.
 *
 * The `tasksKey` invalidation is load-bearing, not defensive: `flan_task.phase_id`
 * carries `ondelete="CASCADE"`, so deleting a phase destroys its tasks in the
 * database. Invalidating only `phasesKey` leaves the Tasks screen listing rows
 * that no longer exist. `tasksKey(projectId)` is a strict prefix of every
 * filtered task key, so this one call sweeps the filtered boards too.
 */
export function useDeletePhase() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; projectId: string }>({
    mutationFn: ({ id }) => apiClient.delete<void>(`/api/v1/flan/phases/${id}`).then((r) => r.data),
    onSuccess: (_res, { projectId }) => {
      qc.invalidateQueries({ queryKey: phasesKey(projectId) })
      qc.invalidateQueries({ queryKey: tasksKey(projectId) })
    },
  })
}

// --- Task, roster and assignment hooks: Task 20 ---

// ─── Types (tasks, roster, assignment) ────────────────────────────────────────

/** Task lifecycle status; the Done share is what a phase's percent_complete counts. */
export type TaskStatus = 'To Do' | 'In Progress' | 'Done'

/** Task risk level. */
export type RiskLevel = 'none' | 'low' | 'medium' | 'high'

/**
 * Task row (TaskRead) — the unit of work a phase's rollup is computed from.
 *
 * `key` is the human handle (`<PREFIX>-<n>`, unpadded — D-V5P1-7) and is
 * **server-generated**: it appears here and in no write payload. `project_id`
 * rides alongside `phase_id` so a client never walks the tree to learn the
 * scope — which is also what lets a mutation invalidate `phasesKey` from the
 * response alone. `assignee_ids` names roster members (FLAN-01.5).
 */
export interface Task {
  id: string
  project_id: string
  phase_id: string
  key: string
  summary: string
  status: string
  risk_level: string
  start_date: string | null
  due_date: string | null
  pinned: boolean
  assignee_ids: string[]
  tags: string[]
  created_at: string
  updated_at: string
}

/**
 * Project roster member (TeamMemberRead) — the assignee pool (FLAN-01.4).
 *
 * The roster is per-project, so the same person on two projects is two rows.
 * `active: false` means soft-removed: the row is kept so historical references
 * resolve, but the member is out of the pickers and its assignment rows were
 * cleared in the same transaction (D-V5P1-6).
 *
 * `hourly_rate` is a Decimal serialized as an exact **string** (D-11) — render
 * it as-is; never `parseFloat` it, never reformat it. In v5.0 it is stored and
 * read by nothing (D-V5-2 / D-M5-2): display and round-tripping only.
 */
export interface TeamMember {
  id: string
  project_id: string
  name: string
  role: string | null
  email: string | null
  color: string | null
  hourly_rate: string | null
  user_id: string | null
  active: boolean
  created_at: string
}

// ─── Request payload types (tasks, roster, assignment) ────────────────────────

/**
 * Task creation payload (TaskCreate). Two fields are deliberately absent:
 * `key` (server-generated under a row lock — D-V5P1-2) and `project_id` (the
 * service takes it from the phase, so a task cannot claim a foreign project).
 * `due_date === start_date` is a valid zero-duration milestone; only an earlier
 * due date is refused.
 */
export interface TaskCreatePayload {
  phase_id: string
  summary: string
  status?: TaskStatus
  risk_level?: RiskLevel
  start_date?: string | null
  due_date?: string | null
  pinned?: boolean
  assignee_ids?: string[]
  tags?: string[]
}

/**
 * Task PATCH payload (TaskUpdate). `key` and `project_id` are absent because
 * both are immutable; `phase_id` IS present — moving a task between phases of
 * the SAME project is allowed. Supplying `tags` or `assignee_ids` REPLACES the
 * respective set.
 */
export interface TaskUpdatePayload {
  phase_id?: string | null
  summary?: string | null
  status?: TaskStatus | null
  risk_level?: RiskLevel | null
  start_date?: string | null
  due_date?: string | null
  pinned?: boolean | null
  assignee_ids?: string[] | null
  tags?: string[] | null
}

/**
 * Roster member creation payload (TeamMemberCreate). `name` is the only
 * requirement, so a person can be rostered before an email or a platform
 * account exists; `user_id` is normally null. `active` is absent — removal is
 * its own endpoint. `hourly_rate` crosses the wire as a **string** (D-11).
 */
export interface TeamMemberCreatePayload {
  name: string
  role?: string | null
  email?: string | null
  color?: string | null
  hourly_rate?: string | null
  user_id?: string | null
}

/**
 * Roster member PATCH payload (TeamMemberUpdate). `project_id` is absent (a
 * member belongs to one roster for life) and so is `active`: soft-removal also
 * clears the member's assignment rows (D-V5P1-6), which a flag flip would not.
 */
export interface TeamMemberUpdatePayload {
  name?: string | null
  role?: string | null
  email?: string | null
  color?: string | null
  hourly_rate?: string | null
  user_id?: string | null
}

/**
 * Assignee replacement payload (AssigneeSet) for the two PUT endpoints.
 * `member_ids` is the COMPLETE list after the call, not a delta — an empty
 * array is how assignments are cleared.
 */
export interface AssigneeSetPayload {
  member_ids: string[]
}

// ─── Query keys (tasks, roster) ───────────────────────────────────────────────

/**
 * A project's task list, optionally narrowed by phase and/or assignee.
 *
 * The filters are part of the key so the assignee-filtered board refetches
 * instead of reading another filter's cache (FLAN-01.5). The unfiltered key is
 * a strict PREFIX of every filtered one, so `invalidateQueries(tasksKey(id))`
 * invalidates the whole project's task lists, filtered variants included —
 * which is what the mutations below rely on.
 */
export const tasksKey = (projectId: string, phaseId?: string, assigneeId?: string) => {
  const base = ['flan', 'tasks', projectId] as const
  return phaseId === undefined && assigneeId === undefined
    ? base
    : ([...base, { phaseId: phaseId ?? null, assigneeId: assigneeId ?? null }] as const)
}

/** One task's detail. Singular so it is not swept up by the list key's prefix. */
export const taskKey = (id: string) => ['flan', 'task', id] as const

/** One project's team roster. */
export const teamKey = (projectId: string) => ['flan', 'team', projectId] as const

// ─── API helpers (tasks, roster, assignment) ──────────────────────────────────

function fetchTasks(projectId: string, phaseId?: string, assigneeId?: string): Promise<Task[]> {
  return apiClient
    .get<Task[]>(`/api/v1/flan/projects/${projectId}/tasks`, {
      params: { phase_id: phaseId, assignee_id: assigneeId },
    })
    .then((r) => r.data)
}

function fetchTask(id: string): Promise<Task> {
  return apiClient.get<Task>(`/api/v1/flan/tasks/${id}`).then((r) => r.data)
}

function fetchTeam(projectId: string): Promise<TeamMember[]> {
  return apiClient.get<TeamMember[]>(`/api/v1/flan/projects/${projectId}/team`).then((r) => r.data)
}

// ─── Queries (tasks, roster) ──────────────────────────────────────────────────

/** A project's tasks, optionally filtered by phase and/or assignee (FLAN-01.5). */
export function useTasks(projectId: string, phaseId?: string, assigneeId?: string) {
  return useQuery<Task[], Error>({
    queryKey: tasksKey(projectId, phaseId, assigneeId),
    queryFn: () => fetchTasks(projectId, phaseId, assigneeId),
    enabled: !!projectId,
  })
}

/** One task's detail. */
export function useTask(id: string) {
  return useQuery<Task, Error>({
    queryKey: taskKey(id),
    queryFn: () => fetchTask(id),
    enabled: !!id,
  })
}

/** One project's team roster — the assignee pool (FLAN-01.4). */
export function useTeam(projectId: string) {
  return useQuery<TeamMember[], Error>({
    queryKey: teamKey(projectId),
    queryFn: () => fetchTeam(projectId),
    enabled: !!projectId,
  })
}

// ─── Mutations (tasks) ────────────────────────────────────────────────────────
//
// **Every task write invalidates phasesKey(projectId) as well as its own keys.**
// A phase's derived_start_date, derived_due_date and percent_complete are rolled
// up from its tasks on every read (D-V5-1), so creating, patching, deleting or
// re-assigning a task changes the phase rows the Phases screen is showing. Skip
// the phase invalidation and the backend stays perfectly correct while the UI
// shows stale dates and a stale percentage — the crux dead through the screen.

/** Create a task. Invalidates the project's tasks AND its phases (rollup moved). */
export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation<Task, Error, { projectId: string; payload: TaskCreatePayload }>({
    mutationFn: ({ projectId, payload }) =>
      apiClient.post<Task>(`/api/v1/flan/projects/${projectId}/tasks`, payload).then((r) => r.data),
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: tasksKey(task.project_id) })
      qc.invalidateQueries({ queryKey: phasesKey(task.project_id) })
    },
  })
}

/**
 * PATCH a task. Invalidates the project's tasks, that task's detail AND the
 * project's phases — status, dates and a phase move all shift the rollup. A move
 * is within one project, so the single `phasesKey(project_id)` invalidation
 * refreshes both the old and the new phase.
 */
export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation<Task, Error, { id: string; patch: TaskUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<Task>(`/api/v1/flan/tasks/${id}`, patch).then((r) => r.data),
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: tasksKey(task.project_id) })
      qc.invalidateQueries({ queryKey: taskKey(task.id) })
      qc.invalidateQueries({ queryKey: phasesKey(task.project_id) })
    },
  })
}

/**
 * Delete a task. Invalidates the project's tasks and phases — `projectId` is
 * passed in because the deleted row can no longer supply it.
 */
export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; projectId: string }>({
    mutationFn: ({ id }) => apiClient.delete<void>(`/api/v1/flan/tasks/${id}`).then((r) => r.data),
    onSuccess: (_res, { id, projectId }) => {
      qc.invalidateQueries({ queryKey: tasksKey(projectId) })
      qc.invalidateQueries({ queryKey: taskKey(id) })
      qc.invalidateQueries({ queryKey: phasesKey(projectId) })
    },
  })
}

// ─── Mutations (roster) ───────────────────────────────────────────────────────

/** Add a member to a project's roster. Invalidates that roster. */
export function useCreateMember() {
  const qc = useQueryClient()
  return useMutation<TeamMember, Error, { projectId: string; payload: TeamMemberCreatePayload }>({
    mutationFn: ({ projectId, payload }) =>
      apiClient
        .post<TeamMember>(`/api/v1/flan/projects/${projectId}/team`, payload)
        .then((r) => r.data),
    onSuccess: (member) => {
      qc.invalidateQueries({ queryKey: teamKey(member.project_id) })
    },
  })
}

/** PATCH a roster member. Invalidates that roster. */
export function useUpdateMember() {
  const qc = useQueryClient()
  return useMutation<TeamMember, Error, { id: string; patch: TeamMemberUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<TeamMember>(`/api/v1/flan/team/${id}`, patch).then((r) => r.data),
    onSuccess: (member) => {
      qc.invalidateQueries({ queryKey: teamKey(member.project_id) })
    },
  })
}

/**
 * Soft-remove a roster member. Invalidates the roster AND the project's tasks:
 * the removal clears the member's assignment rows in the same transaction
 * (D-V5P1-6), so every task that named them now reports a shorter
 * `assignee_ids`. Phase rollups are untouched — assignment changes no date and
 * no percentage. `projectId` is passed in because the response cannot supply it.
 */
export function useRemoveMember() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; projectId: string }>({
    mutationFn: ({ id }) => apiClient.delete<void>(`/api/v1/flan/team/${id}`).then((r) => r.data),
    onSuccess: (_res, { projectId }) => {
      qc.invalidateQueries({ queryKey: teamKey(projectId) })
      qc.invalidateQueries({ queryKey: tasksKey(projectId) })
    },
  })
}

// ─── Mutations (assignment) ───────────────────────────────────────────────────

/**
 * Replace a task's assignees (PUT — `memberIds` is the complete list, empty
 * clears them). Invalidates the project's tasks, the task's detail AND the
 * project's phases: it is a task write like any other, and the assignee-filtered
 * board must not keep showing a task the filter no longer matches (FLAN-01.5).
 * `projectId` comes from the variables so the invalidation never depends on the
 * response body's shape.
 */
export function useSetTaskAssignees() {
  const qc = useQueryClient()
  return useMutation<Task, Error, { taskId: string; projectId: string; memberIds: string[] }>({
    mutationFn: ({ taskId, memberIds }) =>
      apiClient
        .put<Task>(`/api/v1/flan/tasks/${taskId}/assignees`, {
          member_ids: memberIds,
        } satisfies AssigneeSetPayload)
        .then((r) => r.data),
    onSuccess: (_task, { taskId, projectId }) => {
      qc.invalidateQueries({ queryKey: tasksKey(projectId) })
      qc.invalidateQueries({ queryKey: taskKey(taskId) })
      qc.invalidateQueries({ queryKey: phasesKey(projectId) })
    },
  })
}

/**
 * Replace a phase's assignees (PUT, same full-replacement semantics).
 * Invalidates the project's phases. `projectId` comes from the variables.
 */
export function useSetPhaseAssignees() {
  const qc = useQueryClient()
  return useMutation<Phase, Error, { phaseId: string; projectId: string; memberIds: string[] }>({
    mutationFn: ({ phaseId, memberIds }) =>
      apiClient
        .put<Phase>(`/api/v1/flan/phases/${phaseId}/assignees`, {
          member_ids: memberIds,
        } satisfies AssigneeSetPayload)
        .then((r) => r.data),
    onSuccess: (_phase, { projectId }) => {
      qc.invalidateQueries({ queryKey: phasesKey(projectId) })
    },
  })
}
