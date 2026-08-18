// ABOUTME: Component tests for the FLAN Projects screen (FLAN-01.1, FLAN-01.6) — rows
// ABOUTME: render each project's OWN key prefix, the create dialog POSTs a ProjectCreate
// ABOUTME: body, the edit dialog opens pre-filled and PATCHes a ProjectUpdate body,
// ABOUTME: archived rows stay hidden until the Show-archived switch is on, a 4xx detail
// ABOUTME: reaches toast.error, and archiving confirms before POSTing /archive.

/**
 * Projects screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked (the house idiom: mock the
 * axios client and let the real hooks run), then asserts:
 *   1. Rows render from a mocked GET, **key-prefix cell included** — two active
 *      projects with DIFFERENT prefixes are asserted in the same test, so a
 *      hard-coded literal in that cell cannot satisfy both (the LEARNINGS
 *      counter-measure: assert the column renders its value, not that it exists).
 *   2. The create dialog POSTs /api/v1/flan/projects with exactly the fields
 *      `ProjectCreate` declares — a blank key prefix crosses as null so the
 *      server derives it (D-V5P1-2).
 *   3. Archived projects are hidden by default (include_archived=false) and
 *      appear once the Show-archived Switch is on (include_archived=true) — the
 *      switch drives the query param, not a client-side filter.
 *   4. A 4xx with a string `detail` (a refused key prefix) surfaces via
 *      toast.error in the server's own words.
 *   5. Archiving asks for confirmation first, then POSTs the archive endpoint.
 *   6. The edit dialog opens seeded with the edited row's OWN values — asserted
 *      for TWO different rows in one test, so a blank form, or one with
 *      hard-coded defaults, cannot satisfy both (the same LEARNINGS
 *      counter-measure as the key-prefix cell).
 *   7. The edit dialog PATCHes a body whose every key exists in the backend's
 *      `ProjectUpdate` and which carries neither `id` nor `active` — both are
 *      absent from that schema (the id is immutable, archiving is its own
 *      endpoint).
 *   8. A 422 refusing a `key_prefix` change on a project that already has tasks
 *      (D-V5P1-2) surfaces the server's own `detail` through toast.error — the
 *      client never predicts that lock.
 *
 * Modelled on routes/gelato/Bins.test.tsx.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Projects } from '@/routes/flan/Projects'

// Radix Select / DropdownMenu drive their triggers with Pointer Events +
// scrollIntoView, which jsdom does not implement. Stub them so the Category
// Select and the row actions menu are operable here.
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

/**
 * The field set of the backend's `ProjectUpdate` schema, verified against the
 * real class with
 * `python -c "from app.modules.flan.schemas import ProjectUpdate; print(sorted(ProjectUpdate.model_fields))"`
 * → ['category', 'currency', 'description', 'gate_date', 'key_prefix', 'name',
 * 'start_date', 'tags'] — `id` and `active` are absent by design.
 */
const PROJECT_UPDATE_FIELDS = [
  'category',
  'currency',
  'description',
  'gate_date',
  'key_prefix',
  'name',
  'start_date',
  'tags',
]

// ─── Fixtures ─────────────────────────────────────────────────────────────────

// TWO active projects with DIFFERENT key prefixes: a literal in the prefix cell
// would satisfy one row and fail the other.
const CRISIS = {
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
const MANIKIN = {
  id: 'p2',
  name: 'Manikin Refresh',
  key_prefix: 'MANI',
  category: null,
  description: null,
  currency: 'EUR',
  start_date: null,
  gate_date: null,
  active: true,
  tags: [],
  created_at: '2026-01-02T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}
const ARCHIVED = {
  id: 'p3',
  name: 'Legacy Rig',
  key_prefix: 'LEGA',
  category: 'work',
  description: null,
  currency: 'USD',
  start_date: null,
  gate_date: null,
  active: false,
  tags: [],
  created_at: '2026-01-03T00:00:00Z',
  updated_at: '2026-01-03T00:00:00Z',
}

// The projects endpoint honors include_archived, so the Show-archived assertion
// drives server-side filtering exactly as the real API does (name order).
function mockGets() {
  mockGet.mockImplementation(
    (url: string, config?: { params?: { include_archived?: boolean } }) => {
      if (url.includes('/flan/projects')) {
        const includeArchived = config?.params?.include_archived === true
        const data = includeArchived ? [CRISIS, ARCHIVED, MANIKIN] : [CRISIS, MANIKIN]
        return Promise.resolve({ data })
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    }
  )
}

function renderProjects() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/flan/projects']}>
        <Projects />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The row whose accessible name is the row's own "Open project {name}" label. */
function projectRow(name: string) {
  return screen.getByRole('row', { name: `Open project ${name}` })
}

/** The visible text of a row's cells, left to right. */
function cellText(name: string): string[] {
  return within(projectRow(name))
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

describe('Projects screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a row per project, each with its OWN key prefix', async () => {
    mockGets()
    renderProjects()

    await screen.findByText('Crisis Simulator')

    // Name | Key prefix | Category | Currency — the prefix is the stored value,
    // and the two rows carry different ones.
    expect(cellText('Crisis Simulator').slice(0, 4)).toEqual([
      'Crisis Simulator',
      'CRIS',
      'Client',
      'USD',
    ])
    expect(cellText('Manikin Refresh').slice(0, 4)).toEqual(['Manikin Refresh', 'MANI', '—', 'EUR'])

    // Undated project renders an em-dash for both dates; both rows read Active.
    expect(cellText('Manikin Refresh').slice(4, 7)).toEqual(['—', '—', 'Active'])
    expect(cellText('Crisis Simulator')[6]).toBe('Active')
  })

  it('POSTs the ProjectCreate payload from the create dialog', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...CRISIS, id: 'p9', name: 'Gate Review Rig' } })

    renderProjects()
    await screen.findByText('Crisis Simulator')

    await user.click(screen.getByRole('button', { name: 'New Project' }))
    expect(await screen.findByRole('heading', { name: 'New Project' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Name'), 'Gate Review Rig')
    // Typed lowercase: the dialog uppercases it the way the server's derivation does.
    await user.type(screen.getByLabelText('Key prefix'), 'gate')

    await user.click(screen.getByLabelText('Category'))
    await user.click(await screen.findByRole('option', { name: 'Client' }))

    const currency = screen.getByLabelText('Currency')
    await user.clear(currency)
    await user.type(currency, 'eur')

    // <input type="date"> is driven with fireEvent.change (the syerp test idiom).
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-02-01' } })
    fireEvent.change(screen.getByLabelText('Gate date'), { target: { value: '2026-09-30' } })
    await user.type(screen.getByLabelText('Description'), 'Second-gen sim rig')

    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/flan/projects', {
        name: 'Gate Review Rig',
        key_prefix: 'GATE',
        category: 'client',
        description: 'Second-gen sim rig',
        currency: 'EUR',
        start_date: '2026-02-01',
        gate_date: '2026-09-30',
      })
    })
  })

  it('sends key_prefix null when the field is left blank (server derives it)', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...CRISIS, id: 'p9', name: 'Derived Prefix' } })

    renderProjects()
    await screen.findByText('Crisis Simulator')

    await user.click(screen.getByRole('button', { name: 'New Project' }))
    await screen.findByRole('heading', { name: 'New Project' })
    await user.type(screen.getByLabelText('Name'), 'Derived Prefix')
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/flan/projects', {
        name: 'Derived Prefix',
        key_prefix: null,
        category: null,
        description: null,
        currency: 'USD',
        start_date: null,
        gate_date: null,
      })
    })
  })

  it('hides archived projects until the Show archived switch is on', async () => {
    const user = userEvent.setup()
    mockGets()

    renderProjects()

    await screen.findByText('Crisis Simulator')
    expect(screen.queryByText('Legacy Rig')).not.toBeInTheDocument()

    await user.click(screen.getByLabelText('Show archived'))

    await waitFor(() => {
      expect(screen.getByText('Legacy Rig')).toBeInTheDocument()
    })
    // The archived row is badged, and renders its own key prefix too.
    expect(cellText('Legacy Rig').slice(0, 2)).toEqual(['Legacy Rig', 'LEGA'])
    expect(cellText('Legacy Rig')[6]).toBe('Archived')
  })

  it('surfaces a 4xx detail from create as an error toast', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 422,
        data: {
          detail:
            'Project p1 already has tasks, so its key prefix (CRIS) can no longer be changed.',
        },
      },
    })

    renderProjects()
    await screen.findByText('Crisis Simulator')

    await user.click(screen.getByRole('button', { name: 'New Project' }))
    await screen.findByRole('heading', { name: 'New Project' })
    await user.type(screen.getByLabelText('Name'), 'Crisis Simulator')
    await user.click(screen.getByRole('button', { name: 'Create Project' }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        'Project p1 already has tasks, so its key prefix (CRIS) can no longer be changed.'
      )
    })
  })

  it('archives a project only after the confirmation is accepted', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...CRISIS, active: false } })

    renderProjects()
    await screen.findByText('Crisis Simulator')

    await user.click(screen.getByRole('button', { name: 'Project actions for Crisis Simulator' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Archive' }))

    // Confirmation first — nothing has been sent yet.
    expect(await screen.findByRole('heading', { name: 'Archive project?' })).toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Archive Crisis Simulator' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/flan/projects/p1/archive')
    })
  })

  // ─── Edit dialog (FLAN-01.1's "edit" verb) ─────────────────────────────────

  /** Open the row-actions menu for `name` and pick Edit. */
  async function openEditDialog(user: ReturnType<typeof userEvent.setup>, name: string) {
    await user.click(screen.getByRole('button', { name: `Project actions for ${name}` }))
    await user.click(await screen.findByRole('menuitem', { name: 'Edit' }))
    expect(await screen.findByRole('heading', { name: 'Edit Project' })).toBeInTheDocument()
  }

  it('opens the edit dialog pre-filled with the edited row’s OWN values', async () => {
    const user = userEvent.setup()
    mockGets()

    renderProjects()
    await screen.findByText('Crisis Simulator')

    // Row 1: fully populated — every field must show that project's value.
    await openEditDialog(user, 'Crisis Simulator')
    expect(screen.getByLabelText('Name')).toHaveValue('Crisis Simulator')
    expect(screen.getByLabelText('Key prefix')).toHaveValue('CRIS')
    expect(screen.getByLabelText('Currency')).toHaveValue('USD')
    expect(screen.getByLabelText('Start date')).toHaveValue('2026-01-05')
    expect(screen.getByLabelText('Gate date')).toHaveValue('2026-06-30')
    expect(screen.getByLabelText('Category')).toHaveTextContent('Client')
    expect(screen.getByLabelText('Description')).toHaveValue('')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Edit Project' })).not.toBeInTheDocument()
    })

    // Row 2: DIFFERENT values, nulls included. A blank form or hard-coded
    // defaults would fail one of these two rows.
    await openEditDialog(user, 'Manikin Refresh')
    expect(screen.getByLabelText('Name')).toHaveValue('Manikin Refresh')
    expect(screen.getByLabelText('Key prefix')).toHaveValue('MANI')
    expect(screen.getByLabelText('Currency')).toHaveValue('EUR')
    expect(screen.getByLabelText('Start date')).toHaveValue('')
    expect(screen.getByLabelText('Gate date')).toHaveValue('')
    expect(screen.getByLabelText('Category')).toHaveTextContent('None')
  })

  it('PATCHes a ProjectUpdate body carrying neither id nor active', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPatch.mockResolvedValueOnce({ data: { ...CRISIS, name: 'Crisis Simulator II' } })

    renderProjects()
    await screen.findByText('Crisis Simulator')
    await openEditDialog(user, 'Crisis Simulator')

    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Crisis Simulator II')

    // Typed lowercase: the dialog uppercases it the way derive_key_prefix does.
    const keyPrefix = screen.getByLabelText('Key prefix')
    await user.clear(keyPrefix)
    await user.type(keyPrefix, 'cris2')

    // Clearing an OPTIONAL field is legitimate — category crosses as null.
    await user.click(screen.getByLabelText('Category'))
    await user.click(await screen.findByRole('option', { name: 'None' }))

    fireEvent.change(screen.getByLabelText('Gate date'), { target: { value: '2026-07-31' } })
    await user.type(screen.getByLabelText('Description'), 'Gate slipped a month')

    await user.click(screen.getByRole('button', { name: 'Save Project' }))

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/api/v1/flan/projects/p1', {
        name: 'Crisis Simulator II',
        key_prefix: 'CRIS2',
        category: null,
        description: 'Gate slipped a month',
        currency: 'USD',
        start_date: '2026-01-05',
        gate_date: '2026-07-31',
      })
    })

    // Every key is one ProjectUpdate declares, and the two it deliberately
    // omits are omitted here too.
    const body = mockPatch.mock.calls[0][1] as Record<string, unknown>
    expect(PROJECT_UPDATE_FIELDS).toEqual(expect.arrayContaining(Object.keys(body)))
    expect(body).not.toHaveProperty('id')
    expect(body).not.toHaveProperty('active')
  })

  it('surfaces the server’s 422 detail when a key prefix can no longer change', async () => {
    const user = userEvent.setup()
    mockGets()
    // The client never predicts the lock (D-V5P1-2) — it tries, and reports back.
    mockPatch.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 422,
        data: {
          detail:
            'Project p1 already has tasks, so its key prefix (CRIS) can no longer be changed.',
        },
      },
    })

    renderProjects()
    await screen.findByText('Crisis Simulator')
    await openEditDialog(user, 'Crisis Simulator')

    const keyPrefix = screen.getByLabelText('Key prefix')
    await user.clear(keyPrefix)
    await user.type(keyPrefix, 'NEWP')
    await user.click(screen.getByRole('button', { name: 'Save Project' }))

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith(
        '/api/v1/flan/projects/p1',
        expect.objectContaining({ key_prefix: 'NEWP' })
      )
    })
    // The server's own words, verbatim — no generic fallback.
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        'Project p1 already has tasks, so its key prefix (CRIS) can no longer be changed.'
      )
    })
    // A refused edit keeps the dialog open so the user can fix it.
    expect(screen.getByRole('heading', { name: 'Edit Project' })).toBeInTheDocument()
  })
})
