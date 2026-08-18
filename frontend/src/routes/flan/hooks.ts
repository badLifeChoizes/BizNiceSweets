// ABOUTME: FLAN (Project Management) TanStack Query hooks + shared request/response
// ABOUTME: types. Wraps the /api/v1/flan/* API (projects CRUD + archive, phases CRUD)
// ABOUTME: through the single axios client. A phase's derived_start_date,
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
 * Delete a phase, cascading to its tasks. Invalidates that project's phases —
 * `projectId` is passed in because the deleted row can no longer supply it.
 */
export function useDeletePhase() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; projectId: string }>({
    mutationFn: ({ id }) => apiClient.delete<void>(`/api/v1/flan/phases/${id}`).then((r) => r.data),
    onSuccess: (_res, { projectId }) => {
      qc.invalidateQueries({ queryKey: phasesKey(projectId) })
    },
  })
}

// --- Task, roster and assignment hooks: Task 20 ---
