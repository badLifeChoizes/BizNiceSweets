// ABOUTME: Component tests for the FLAN Phases screen (FLAN-01.2, D-V5-1) — a row
// ABOUTME: renders the API's OWN percent_complete string (never a recomputed one), an
// ABOUTME: empty phase renders em-dashes and 0.00%, the edit dialog exposes no date or
// ABOUTME: percent input, and deleting names the tasks the cascade takes with it.

/**
 * Phases screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked (the house idiom: mock the
 * axios client and let the real hooks run) at /flan/projects/p1/phases so
 * `useParams().projectId` is the genuine article, then asserts:
 *   1. **The percentage is the server's string, printed verbatim** (D-11,
 *      D-V5-1). The "Validation" fixture's `percent_complete` deliberately
 *      DISAGREES with its own done_count/task_count, so a cell that recomputed
 *      `done / total` — however it rounded — would render a different string and
 *      fail here. That is the whole point: the client renders the rollup, it
 *      does not reproduce it.
 *   2. An empty phase (no tasks: null dates, "0.00", zero counts) renders an
 *      em-dash for both dates and 0.00% — the case FLAN-01.2 names explicitly
 *      and a happy-path fixture misses.
 *   3. The edit dialog has no date and no percent input at all
 *      (`queryByLabelText(/start|due|percent/i)` is null) — `PhaseUpdate` has no
 *      such field and `flan_phase` no such column, so an input would write to
 *      nothing.
 *   4. Create POSTs and edit PATCHes bodies whose every key exists in
 *      PhaseCreate / PhaseUpdate (name, sort_order, status, description).
 *   5. Deleting confirms first, names how many tasks the cascade takes, and only
 *      then sends the DELETE.
 *   6. A 4xx `detail` reaches toast.error in the server's own words.
 *   7. Each derived cell carries the "not editable" tooltip.
 *
 * Modelled on routes/flan/Projects.test.tsx.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Phases } from '@/routes/flan/Phases'

// Radix Select / DropdownMenu / Tooltip drive their triggers with Pointer Events +
// scrollIntoView, which jsdom does not implement. Stub them so the Status Select,
// the row actions menu and the derived-cell tooltips are operable here.
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
const mockDelete = vi.mocked(apiClient.delete)
const mockToastError = vi.mocked(toast.error)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const PROJECT = {
  id: 'p1',
  name: 'Crisis Simulator',
  key_prefix: 'CRIS',
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

// A fully-done phase: its percentage happens to agree with its counts.
const DESIGN = {
  id: 'ph1',
  project_id: 'p1',
  name: 'Design',
  sort_order: 0,
  status: 'complete',
  description: 'Concept and drawings',
  derived_start_date: '2026-01-05',
  derived_due_date: '2026-02-28',
  percent_complete: '100.00',
  task_count: 4,
  done_count: 4,
}

// One of three tasks done — the docstring's own example, "33.33".
const BUILD = {
  id: 'ph2',
  project_id: 'p1',
  name: 'Build',
  sort_order: 1,
  status: 'in-progress',
  description: null,
  derived_start_date: '2026-03-01',
  derived_due_date: '2026-06-30',
  percent_complete: '33.33',
  task_count: 3,
  done_count: 1,
}

// **The crux fixture.** `percent_complete` deliberately does NOT equal
// done_count / task_count (2 of 3 would be 66.67): the screen must print the
// server's string, so any client-side recomputation renders 66.67% here and
// fails. A fixture whose numbers agree could not tell the two apart.
const VALIDATION = {
  id: 'ph3',
  project_id: 'p1',
  name: 'Validation',
  sort_order: 2,
  status: 'in-progress',
  description: null,
  derived_start_date: '2026-05-01',
  derived_due_date: '2026-07-15',
  percent_complete: '41.50',
  task_count: 3,
  done_count: 2,
}

// The empty phase: no tasks at all, so no dates and the server's "0.00".
const HANDOVER = {
  id: 'ph4',
  project_id: 'p1',
  name: 'Handover',
  sort_order: 3,
  status: 'pending',
  description: null,
  derived_start_date: null,
  derived_due_date: null,
  percent_complete: '0.00',
  task_count: 0,
  done_count: 0,
}

const PHASES = [DESIGN, BUILD, VALIDATION, HANDOVER]

/** GET routing: the phases list for p1, plus the project list FlanNav reads. */
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/phases')) return Promise.resolve({ data: PHASES })
    if (url.includes('/flan/projects')) return Promise.resolve({ data: [PROJECT] })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderPhases() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/flan/projects/p1/phases']}>
        <Routes>
          <Route path="/flan/projects/:projectId/phases" element={<Phases />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The row whose accessible name is the row's own "Phase {name}" label. */
function phaseRow(name: string) {
  return screen.getByRole('row', { name: `Phase ${name}` })
}

/** The visible text of a row's cells, left to right. */
function cellText(name: string): string[] {
  return within(phaseRow(name))
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

/** Open a phase's row actions menu and pick an item. */
async function rowAction(user: ReturnType<typeof userEvent.setup>, name: string, item: string) {
  await user.click(screen.getByRole('button', { name: `Phase actions for ${name}` }))
  await user.click(await screen.findByRole('menuitem', { name: item }))
}

describe('Phases screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders each phase's derived dates and the API's OWN percent string", async () => {
    mockGets()
    renderPhases()

    await screen.findByText('Design')

    // Rows come back in the server's order (sort_order, then name) and are not
    // re-sorted here.
    expect(
      screen
        .getAllByRole('row')
        .slice(1)
        .map((row) => row.getAttribute('aria-label'))
    ).toEqual(['Phase Design', 'Phase Build', 'Phase Validation', 'Phase Handover'])

    // Phase | Status | Derived start | Derived due | % complete | Tasks
    const build = cellText('Build')
    expect(build[0]).toBe('Build')
    expect(build[1]).toBe('In Progress')
    expect(build[2]).toMatch(/2026/)
    expect(build[3]).toMatch(/2026/)
    // The server's string, verbatim — not parseFloat'd, not reformatted.
    expect(build[4]).toBe('33.33%')
    expect(build[5]).toBe('1 of 3')

    // The crux: Validation's server percentage disagrees with 2-of-3 (66.67), so
    // only a cell that renders the API's string can produce this.
    expect(cellText('Validation')[4]).toBe('41.50%')
    expect(cellText('Validation')[5]).toBe('2 of 3')

    expect(cellText('Design')[4]).toBe('100.00%')
  })

  it('renders an em-dash for both dates and 0.00% on a phase with no tasks', async () => {
    mockGets()
    renderPhases()

    await screen.findByText('Handover')

    expect(cellText('Handover').slice(0, 6)).toEqual([
      'Handover',
      'Pending',
      '—',
      '—',
      '0.00%',
      '0 of 0',
    ])
  })

  it('offers no date and no percent input in the edit dialog', async () => {
    const user = userEvent.setup()
    mockGets()
    renderPhases()

    await screen.findByText('Build')
    await rowAction(user, 'Build', 'Edit')

    expect(await screen.findByRole('heading', { name: 'Edit Phase' })).toBeInTheDocument()

    // Name, order, status and description — and nothing else (D-V5-1).
    expect(screen.getByLabelText('Name')).toHaveValue('Build')
    expect(screen.getByLabelText('Order')).toHaveValue(1)
    expect(screen.getByLabelText('Status')).toBeInTheDocument()
    expect(screen.getByLabelText('Description')).toBeInTheDocument()

    expect(screen.queryByLabelText(/start|due|percent/i)).toBeNull()
    expect(document.querySelectorAll('input[type="date"]')).toHaveLength(0)
  })

  it('POSTs the PhaseCreate payload from the New Phase dialog', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...HANDOVER, id: 'ph9', name: 'Pilot' } })

    renderPhases()
    await screen.findByText('Design')

    await user.click(screen.getByRole('button', { name: 'New Phase' }))
    expect(await screen.findByRole('heading', { name: 'New Phase' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Name'), 'Pilot')
    const order = screen.getByLabelText('Order')
    await user.clear(order)
    await user.type(order, '4')
    await user.click(screen.getByLabelText('Status'))
    await user.click(await screen.findByRole('option', { name: 'In Progress' }))
    await user.type(screen.getByLabelText('Description'), 'First customer site')

    await user.click(screen.getByRole('button', { name: 'Create Phase' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/flan/projects/p1/phases', {
        name: 'Pilot',
        sort_order: 4,
        status: 'in-progress',
        description: 'First customer site',
      })
    })
  })

  it('PATCHes the PhaseUpdate payload from the edit dialog', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPatch.mockResolvedValueOnce({ data: { ...BUILD, name: 'Build & Integrate' } })

    renderPhases()
    await screen.findByText('Build')
    await rowAction(user, 'Build', 'Edit')
    await screen.findByRole('heading', { name: 'Edit Phase' })

    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Build & Integrate')

    await user.click(screen.getByRole('button', { name: 'Save Phase' }))

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/api/v1/flan/phases/ph2', {
        name: 'Build & Integrate',
        sort_order: 1,
        status: 'in-progress',
        description: null,
      })
    })
  })

  it('names the cascaded task count and deletes only after the confirmation', async () => {
    const user = userEvent.setup()
    mockGets()
    mockDelete.mockResolvedValueOnce({ data: undefined })

    renderPhases()
    await screen.findByText('Design')
    await rowAction(user, 'Design', 'Delete')

    // Confirmation first, naming the four tasks the cascade takes — nothing sent yet.
    expect(await screen.findByRole('heading', { name: 'Delete phase?' })).toBeInTheDocument()
    expect(screen.getByText(/Design has 4 tasks/)).toBeInTheDocument()
    expect(screen.getByText(/those 4 tasks with it/)).toBeInTheDocument()
    expect(mockDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Delete Design' }))

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('/api/v1/flan/phases/ph1')
    })
  })

  it('says a phase has no tasks when nothing will be cascaded', async () => {
    const user = userEvent.setup()
    mockGets()

    renderPhases()
    await screen.findByText('Handover')
    await rowAction(user, 'Handover', 'Delete')

    expect(await screen.findByText(/Handover has no tasks/)).toBeInTheDocument()
  })

  it('surfaces a 4xx detail from create as an error toast', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 422,
        data: { detail: 'Project p1 is archived, so its phases can no longer be changed.' },
      },
    })

    renderPhases()
    await screen.findByText('Design')

    await user.click(screen.getByRole('button', { name: 'New Phase' }))
    await screen.findByRole('heading', { name: 'New Phase' })
    await user.type(screen.getByLabelText('Name'), 'Pilot')
    await user.click(screen.getByRole('button', { name: 'Create Phase' }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        'Project p1 is archived, so its phases can no longer be changed.'
      )
    })
  })

  it('tells the user the percentage is derived from the tasks and not editable', async () => {
    const user = userEvent.setup()
    mockGets()
    renderPhases()

    await screen.findByText('Design')
    await user.hover(screen.getByText('33.33%'))

    expect(
      (await screen.findAllByText("derived from this phase's tasks — not editable")).length
    ).toBeGreaterThan(0)
  })
})
