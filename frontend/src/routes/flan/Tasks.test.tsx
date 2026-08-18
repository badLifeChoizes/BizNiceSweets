// ABOUTME: Component tests for the FLAN Tasks screen (FLAN-01.3, FLAN-01.5) — the key
// ABOUTME: CELL RENDERS THE API'S VALUE, rows keep the server's numeric key order
// ABOUTME: (PRJ-9 before PRJ-10, which a string sort would flip), the create POST body
// ABOUTME: carries no `key`, the assignee filter re-fetches with assignee_id, and a
// ABOUTME: 422 due<start surfaces the server's own detail through toast.error.

/**
 * Tasks screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked (the house idiom: mock the
 * axios client and let the real hooks run) at /flan/projects/p1/tasks so
 * `useParams().projectId` is the genuine article, then asserts:
 *
 *   1. **The key cell renders the VALUE the API returned** — the two fixtures
 *      carry different keys (`PRJ-9`, `PRJ-10`), so no single hard-coded literal
 *      can satisfy the assertion. This is the standing counter-measure for a
 *      column that renders but renders the wrong thing.
 *   2. **No client-side sort.** The mocked list arrives `PRJ-9` then `PRJ-10` —
 *      the server's NUMERIC order (`tasks.py::list_tasks`), which is not string
 *      order, because keys are unpadded (D-V5P1-7). A `.sort()` on the key in the
 *      browser would flip these two rows; the assertion on row order catches it.
 *   3. The create POST body matches `TaskCreate` exactly and contains **no
 *      `key`** — the key is server-generated (D-V5P1-2) and the schema has no
 *      field for one, so a `key` in the body is a 422 in production.
 *   4. Choosing an assignee re-fetches with `assignee_id` in the REQUEST PARAMS
 *      (FLAN-01.5) — the board is filtered by the database, not on the client;
 *      likewise `phase_id` for the phase filter.
 *   5. A mocked 422 on `due < start` reaches `toast.error` with the server's own
 *      `detail`, and `due === start` is submitted without complaint (a valid
 *      zero-duration milestone — the client adds no date rule of its own).
 *   6. The sheet offers no key input at all, and a soft-removed roster member is
 *      neither selectable nor filterable.
 *
 * Modelled on routes/flan/Phases.test.tsx.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Tasks } from '@/routes/flan/Tasks'

// Radix Select / Sheet drive their triggers with Pointer Events + scrollIntoView,
// which jsdom does not implement. Stub them so the filters, the sheet's Selects
// and its checkboxes are operable here.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock the axios apiClient module.
vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

// Mock sonner toasts.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
import { toast } from 'sonner'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)
const mockPatch = vi.mocked(apiClient.patch)
const mockToastError = vi.mocked(toast.error)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

/**
 * The backend's `TaskCreate` field set, verified against
 * backend/app/modules/flan/schemas.py:
 *   ['assignee_ids', 'due_date', 'phase_id', 'pinned', 'risk_level',
 *    'start_date', 'status', 'summary', 'tags']
 * `key` is deliberately absent from it — and therefore from any body we send.
 */
const TASK_CREATE_FIELDS = [
  'assignee_ids',
  'due_date',
  'phase_id',
  'pinned',
  'risk_level',
  'start_date',
  'status',
  'summary',
  'tags',
]

const PROJECT = {
  id: 'p1',
  name: 'Prototype Rig',
  key_prefix: 'PRJ',
  category: 'client',
  description: null,
  currency: 'USD',
  start_date: '2026-01-05',
  gate_date: '2026-06-30',
  active: true,
  tags: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const DESIGN = {
  id: 'ph1',
  project_id: 'p1',
  name: 'Design',
  sort_order: 0,
  status: 'complete',
  description: null,
  derived_start_date: '2026-01-05',
  derived_due_date: '2026-02-28',
  percent_complete: '100.00',
  task_count: 1,
  done_count: 1,
}

const BUILD = {
  id: 'ph2',
  project_id: 'p1',
  name: 'Build',
  sort_order: 1,
  status: 'in-progress',
  description: null,
  derived_start_date: '2026-03-02',
  derived_due_date: '2026-04-10',
  percent_complete: '0.00',
  task_count: 1,
  done_count: 0,
}

const PHASES = [DESIGN, BUILD]

const ADA = {
  id: 'm1',
  project_id: 'p1',
  name: 'Ada Lovelace',
  role: 'Engineer',
  email: null,
  color: null,
  hourly_rate: '95.00',
  user_id: null,
  active: true,
  created_at: '2026-01-01T00:00:00Z',
}

const GRACE = {
  id: 'm2',
  project_id: 'p1',
  name: 'Grace Hopper',
  role: null,
  email: null,
  color: null,
  hourly_rate: null,
  user_id: null,
  active: true,
  created_at: '2026-01-02T00:00:00Z',
}

// Soft-removed (D-V5P1-6). The API's default listing already excludes removed
// members, so this row is belt-and-braces: it proves the screen would not offer
// one even if it arrived.
const REMOVED = {
  ...GRACE,
  id: 'm3',
  name: 'Rita Retired',
  active: false,
  created_at: '2026-01-03T00:00:00Z',
}

const TEAM = [ADA, GRACE, REMOVED]

/**
 * **The order crux.** The API returns these two in the server's NUMERIC key
 * order — `PRJ-9` first, `PRJ-10` second. A string sort would render them the
 * other way round, so the row-order assertion below is what catches a
 * client-side `.sort()`.
 */
const TASK_NINE = {
  id: 't9',
  project_id: 'p1',
  phase_id: 'ph2',
  key: 'PRJ-9',
  summary: 'Wire the sensor harness',
  status: 'In Progress',
  risk_level: 'high',
  start_date: '2026-03-02',
  due_date: '2026-03-16',
  pinned: true,
  assignee_ids: ['m1'],
  tags: [],
  created_at: '2026-01-05T00:00:00Z',
  updated_at: '2026-01-05T00:00:00Z',
}

const TASK_TEN = {
  id: 't10',
  project_id: 'p1',
  phase_id: 'ph1',
  key: 'PRJ-10',
  summary: 'Ship the pilot units',
  status: 'To Do',
  risk_level: 'none',
  start_date: null,
  due_date: null,
  pinned: false,
  // Annotated: an inferred `never[]` cannot be `.includes(someString)`d in the
  // filtering mock below.
  assignee_ids: [] as string[],
  tags: [],
  created_at: '2026-01-06T00:00:00Z',
  updated_at: '2026-01-06T00:00:00Z',
}

const TASKS = [TASK_NINE, TASK_TEN]

/**
 * GET routing: the task list (honouring the filters the screen sends), the
 * phases and roster the columns and pickers read, plus the project list FlanNav
 * needs. The task branch is checked first — every FLAN url contains
 * "/flan/projects".
 */
function mockGets() {
  mockGet.mockImplementation((url: string, config?: { params?: Record<string, string> }) => {
    if (url.endsWith('/tasks')) {
      const { phase_id: phaseId, assignee_id: assigneeId } = config?.params ?? {}
      let rows = TASKS
      if (phaseId) rows = rows.filter((task) => task.phase_id === phaseId)
      if (assigneeId) rows = rows.filter((task) => task.assignee_ids.includes(assigneeId))
      return Promise.resolve({ data: rows })
    }
    if (url.endsWith('/phases')) return Promise.resolve({ data: PHASES })
    if (url.endsWith('/team')) return Promise.resolve({ data: TEAM })
    if (url.includes('/flan/projects')) return Promise.resolve({ data: [PROJECT] })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderTasks() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/flan/projects/p1/tasks']}>
        <Routes>
          <Route path="/flan/projects/:projectId/tasks" element={<Tasks />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The row whose accessible name is the row's own "Task {key}" label. */
function taskRow(key: string) {
  return screen.getByRole('row', { name: `Task ${key}` })
}

/** The visible text of a row's cells, left to right. */
function cellText(key: string): string[] {
  return within(taskRow(key))
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

/** The params of the most recent GET for the task list. */
function lastTasksParams(): Record<string, string | undefined> {
  const calls = mockGet.mock.calls.filter(([url]) => String(url).endsWith('/tasks'))
  const last = calls[calls.length - 1] as [string, { params?: Record<string, string> }]
  return last?.[1]?.params ?? {}
}

/**
 * Choose an option in one of the screen's Selects.
 *
 * `scope` matters: the toolbar's phase filter carries the visible label "Phase"
 * and the sheet's phase Select carries `aria-label="Phase"`, so a document-wide
 * lookup finds both while the sheet is open. Sheet fields are therefore queried
 * inside the dialog; the option list itself is portalled to the body, so it is
 * always found on `screen`.
 */
async function choose(
  user: ReturnType<typeof userEvent.setup>,
  trigger: string,
  option: string,
  scope: { getByLabelText: (text: string) => HTMLElement } = screen
) {
  await user.click(scope.getByLabelText(trigger))
  await user.click(await screen.findByRole('option', { name: option }))
}

/** Queries scoped to the open create/edit sheet. */
function sheet() {
  return within(screen.getByRole('dialog'))
}

describe('Tasks screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders each task's server-generated key in the order the API returned", async () => {
    mockGets()
    renderTasks()

    await screen.findByText('Wire the sensor harness')

    // (a) The key CELL renders the API's value — two different keys, so no
    // single literal could satisfy both.
    expect(cellText('PRJ-9')[0]).toBe('PRJ-9')
    expect(cellText('PRJ-10')[0]).toBe('PRJ-10')

    // No client-side sort: the API's numeric order (PRJ-9 before PRJ-10) is
    // preserved. Sorting the unpadded keys as strings would flip these.
    expect(
      screen
        .getAllByRole('row')
        .slice(1)
        .map((row) => row.getAttribute('aria-label'))
    ).toEqual(['Task PRJ-9', 'Task PRJ-10'])
  })

  it('renders the summary, phase, status, dates, risk, pinned flag and assignees', async () => {
    mockGets()
    renderTasks()

    await screen.findByText('Wire the sensor harness')

    // Key | Summary | Phase | Status | Start | Due | Risk | Pinned | Assignees
    const nine = cellText('PRJ-9')
    expect(nine.slice(0, 4)).toEqual(['PRJ-9', 'Wire the sensor harness', 'Build', 'In Progress'])
    expect(nine[4]).toMatch(/2026/)
    expect(nine[5]).toMatch(/2026/)
    expect(nine[6]).toBe('High')
    expect(nine[7]).toBe('Pinned')
    expect(nine[8]).toBe('Ada Lovelace')

    // The undated, unassigned, unpinned task renders em-dashes rather than blanks.
    expect(cellText('PRJ-10').slice(0, 9)).toEqual([
      'PRJ-10',
      'Ship the pilot units',
      'Design',
      'To Do',
      '—',
      '—',
      'None',
      '—',
      '—',
    ])
  })

  it('POSTs a TaskCreate body with no key field (the server assigns the key)', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...TASK_TEN, id: 't11', key: 'PRJ-11' } })

    renderTasks()
    await screen.findByText('Wire the sensor harness')

    await user.click(screen.getByRole('button', { name: 'New Task' }))
    expect(await screen.findByRole('heading', { name: 'New Task' })).toBeInTheDocument()

    await user.type(sheet().getByLabelText('Summary'), 'Calibrate the rig')
    await choose(user, 'Phase', 'Build', sheet())
    await choose(user, 'Status', 'In Progress', sheet())
    await choose(user, 'Risk', 'Medium', sheet())
    // due === start: a valid zero-duration milestone, which the client must not
    // refuse on its own (only due < start is refused, and only by the server).
    fireEvent.change(sheet().getByLabelText('Start date'), { target: { value: '2026-04-01' } })
    fireEvent.change(sheet().getByLabelText('Due date'), { target: { value: '2026-04-01' } })
    await user.click(sheet().getByLabelText('Pinned'))
    await user.click(sheet().getByLabelText('Assign Ada Lovelace'))

    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    await waitFor(() => expect(mockPost).toHaveBeenCalled())

    const [url, body] = mockPost.mock.calls[0] as [string, Record<string, unknown>]
    expect(url).toBe('/api/v1/flan/projects/p1/tasks')
    expect(body).toEqual({
      phase_id: 'ph2',
      summary: 'Calibrate the rig',
      status: 'In Progress',
      risk_level: 'medium',
      start_date: '2026-04-01',
      due_date: '2026-04-01',
      pinned: true,
      assignee_ids: ['m1'],
    })
    // (b) Nothing we send is outside TaskCreate, and `key` is not in the body:
    // the schema has no such field, so it would be an unknown-key 422.
    expect(Object.keys(body)).not.toContain('key')
    for (const field of Object.keys(body)) {
      expect(TASK_CREATE_FIELDS).toContain(field)
    }
  })

  it('PATCHes a TaskUpdate body from the edit sheet, showing the key read-only', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPatch.mockResolvedValueOnce({ data: { ...TASK_NINE, status: 'Done' } })

    renderTasks()
    await screen.findByText('Wire the sensor harness')

    await user.click(screen.getByRole('button', { name: 'Edit PRJ-9' }))
    expect(await screen.findByRole('heading', { name: 'Edit Task' })).toBeInTheDocument()

    await choose(user, 'Status', 'Done', sheet())
    await user.click(screen.getByRole('button', { name: 'Save Task' }))

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/api/v1/flan/tasks/t9', {
        phase_id: 'ph2',
        summary: 'Wire the sensor harness',
        status: 'Done',
        risk_level: 'high',
        start_date: '2026-03-02',
        due_date: '2026-03-16',
        pinned: true,
        assignee_ids: ['m1'],
      })
    })
  })

  it('re-fetches with assignee_id in the params when the assignee filter is set', async () => {
    const user = userEvent.setup()
    mockGets()
    renderTasks()

    await screen.findByText('Wire the sensor harness')
    expect(lastTasksParams().assignee_id).toBeUndefined()

    // (c) The board is narrowed by the SERVER: the id rides in the request.
    await choose(user, 'Filter by assignee', 'Grace Hopper')

    await waitFor(() => {
      expect(lastTasksParams().assignee_id).toBe('m2')
    })
    expect(lastTasksParams().phase_id).toBeUndefined()

    // Grace is assigned nothing, so the filtered board is empty.
    expect(await screen.findByText('No task matches the current filters.')).toBeInTheDocument()
  })

  it('re-fetches with phase_id in the params when the phase filter is set', async () => {
    const user = userEvent.setup()
    mockGets()
    renderTasks()

    await screen.findByText('Wire the sensor harness')
    await choose(user, 'Filter by phase', 'Design')

    await waitFor(() => {
      expect(lastTasksParams().phase_id).toBe('ph1')
    })
    // Only the Design task survives the server-side filter.
    expect(await screen.findByRole('row', { name: 'Task PRJ-10' })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: 'Task PRJ-9' })).toBeNull()
  })

  it("surfaces a 422 due<start as an error toast in the server's own words", async () => {
    const user = userEvent.setup()
    mockGets()
    const detail =
      'due_date (2026-03-01) must not precede start_date (2026-03-05); ' +
      'due_date == start_date is a valid zero-duration milestone.'
    mockPost.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 422, data: { detail } },
    })

    renderTasks()
    await screen.findByText('Wire the sensor harness')

    await user.click(screen.getByRole('button', { name: 'New Task' }))
    await screen.findByRole('heading', { name: 'New Task' })
    await user.type(sheet().getByLabelText('Summary'), 'Backwards dates')
    await choose(user, 'Phase', 'Build', sheet())
    fireEvent.change(sheet().getByLabelText('Start date'), { target: { value: '2026-03-05' } })
    fireEvent.change(sheet().getByLabelText('Due date'), { target: { value: '2026-03-01' } })

    // The client sends it — the date rule is the server's, in one place (d).
    await user.click(screen.getByRole('button', { name: 'Create Task' }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(detail)
    })
  })

  it('offers no key input in the sheet and no removed member in the pickers', async () => {
    const user = userEvent.setup()
    mockGets()
    renderTasks()

    await screen.findByText('Wire the sensor harness')
    await user.click(screen.getByRole('button', { name: 'Edit PRJ-9' }))
    await screen.findByRole('heading', { name: 'Edit Task' })

    // The key is displayed, never typed — TaskCreate/TaskUpdate have no field.
    expect(screen.queryByLabelText(/key/i)).toBeNull()
    expect(sheet().getByText('PRJ-9')).toBeInTheDocument()

    // The roster pool is the ACTIVE members only (D-V5P1-6).
    expect(sheet().getByLabelText('Assign Ada Lovelace')).toBeInTheDocument()
    expect(sheet().getByLabelText('Assign Grace Hopper')).toBeInTheDocument()
    expect(screen.queryByLabelText('Assign Rita Retired')).toBeNull()

    // …and so is the filter's option list.
    await user.keyboard('{Escape}')
    await user.click(screen.getByLabelText('Filter by assignee'))
    expect(await screen.findByRole('option', { name: 'Grace Hopper' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Rita Retired' })).toBeNull()
  })
})
