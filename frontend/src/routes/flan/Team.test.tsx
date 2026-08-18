// ABOUTME: Component tests for the FLAN Team screen (FLAN-01.4) — the rate cell renders
// ABOUTME: the API's OWN Decimal string ("42.500000", which any float formatting would
// ABOUTME: change), saving with "No platform user" POSTs a literal user_id: null, and the
// ABOUTME: remove confirmation names the assignment clearing before any DELETE is sent.

/**
 * Team screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked (the house idiom: mock the
 * axios client and let the real hooks run) at /flan/projects/p1/team so
 * `useParams().projectId` is the genuine article, then asserts the three
 * Done-when clauses plus their neighbours:
 *
 *   (a) **The hourly-rate cell is the string the API returned.** The fixture's
 *       rate is the backend's own six-place `"42.500000"`, so a cell that
 *       `parseFloat`ed or `toFixed(2)`'d it would render `42.5` / `42.50` and
 *       fail here. A two-place fixture could not tell the two apart — that is
 *       why this one has six.
 *   (b) **"No platform user" POSTs `user_id: null`** — a literal null, present
 *       in the body: not `''` (not a user id), not an omitted key (on a PATCH
 *       that would leave an existing link in place instead of clearing it).
 *       Picking a real user posts that user's id instead.
 *   (c) **The remove confirmation names the assignment clearing** — it is a
 *       soft remove that ALSO deletes the member's task and phase assignment
 *       rows (D-V5P1-6), and the copy says both that and "the tasks themselves
 *       are left intact" before the DELETE is sent.
 *
 * Also covered: the rate field's "no cost is derived from it" helper text
 * (D-V5-2 / D-M5-2), an unlinked member rendering as a full row of em-dashes,
 * a 4xx `detail` reaching toast.error in the server's own words, and the
 * deliberate ABSENCE of any reactivate / show-removed control (owner decision:
 * v5.0 has no reactivation path, and the list endpoint takes no
 * `include_removed` parameter).
 *
 * Modelled on routes/flan/Tasks.test.tsx.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Team } from '@/routes/flan/Team'

// Radix Select / DropdownMenu / Dialog drive their triggers with Pointer Events +
// scrollIntoView, which jsdom does not implement. Stub them so the platform-user
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
const mockDelete = vi.mocked(apiClient.delete)
const mockToastError = vi.mocked(toast.error)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

/**
 * The backend's TeamMemberCreate / TeamMemberUpdate field set, verified against
 * backend/app/modules/flan/schemas.py (both carry exactly these six):
 *   ['color', 'email', 'hourly_rate', 'name', 'role', 'user_id']
 * `active` is in neither — removal is its own endpoint (D-V5P1-6).
 */
const MEMBER_FIELDS = ['color', 'email', 'hourly_rate', 'name', 'role', 'user_id']

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

/**
 * **The rate crux.** `hourly_rate` is a Decimal serialized as a string (D-11)
 * and the backend emits it at the column's full scale — `"42.500000"`. Any
 * client-side formatting changes it (`Number(x).toFixed(2)` → "42.50",
 * `parseFloat` → "42.5"), so the cell assertion below pins "render what the API
 * returned" rather than "render something that looks like the rate".
 */
const ADA = {
  id: 'm1',
  project_id: 'p1',
  name: 'Ada Lovelace',
  role: 'Lead Engineer',
  email: 'ada@example.test',
  color: '#4F46E5',
  hourly_rate: '42.500000',
  user_id: 'u1',
  active: true,
  created_at: '2026-01-01T00:00:00Z',
}

/** The unlinked, unadorned member — a full collaborator, not a lesser row. */
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

const TEAM = [ADA, GRACE]

/** Platform users, as GET /api/v1/auth/users returns them (UserRead). */
const USERS = [
  { id: 'u1', email: 'ada@corp.test', full_name: 'Ada Lovelace (admin)', is_active: true },
  { id: 'u2', email: 'grace@corp.test', full_name: null, is_active: true },
]

/**
 * GET routing: the roster, the platform users the picker and the linked-user
 * column read, plus the project list FlanNav needs. The `/team` branch is
 * checked first — every FLAN url contains "/flan/projects".
 */
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.endsWith('/team')) return Promise.resolve({ data: TEAM })
    if (url.endsWith('/auth/users')) return Promise.resolve({ data: USERS })
    if (url.includes('/flan/projects')) return Promise.resolve({ data: [PROJECT] })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderTeam() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/flan/projects/p1/team']}>
        <Routes>
          <Route path="/flan/projects/:projectId/team" element={<Team />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The row whose accessible name is the row's own "Member {name}" label. */
function memberRow(name: string) {
  return screen.getByRole('row', { name: `Member ${name}` })
}

/** The visible text of a row's cells, left to right. */
function cellText(name: string): string[] {
  return within(memberRow(name))
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

/** Open a member's row actions menu and pick an item. */
async function rowAction(user: ReturnType<typeof userEvent.setup>, name: string, item: string) {
  await user.click(screen.getByRole('button', { name: `Member actions for ${name}` }))
  await user.click(await screen.findByRole('menuitem', { name: item }))
}

/** Choose an option in the dialog's platform-user Select (the list is portalled). */
async function choose(user: ReturnType<typeof userEvent.setup>, trigger: string, option: string) {
  await user.click(screen.getByLabelText(trigger))
  await user.click(await screen.findByRole('option', { name: option }))
}

/** Queries scoped to the open dialog. */
function dialog() {
  return within(screen.getByRole('dialog'))
}

describe('Team screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders a member's hourly rate as the string the API returned", async () => {
    mockGets()
    renderTeam()

    await screen.findByText('Ada Lovelace')

    // (a) The rate cell is the API's own Decimal string, character for
    // character. toFixed(2) would render "42.50" and parseFloat "42.5".
    expect(cellText('Ada Lovelace')[4]).toBe('42.500000')
    // Belt-and-braces on the same point, stated as the mutation it forbids.
    expect(cellText('Ada Lovelace')[4]).not.toBe(Number(ADA.hourly_rate).toFixed(2))
    expect(cellText('Ada Lovelace')[4]).not.toBe(String(Number(ADA.hourly_rate)))
  })

  it('renders the name, role, email, colour and linked user, em-dashing the rest', async () => {
    mockGets()
    renderTeam()

    await screen.findByText('Ada Lovelace')

    // Member | Role | Email | Colour | Hourly rate | Platform user
    expect(cellText('Ada Lovelace').slice(0, 6)).toEqual([
      'Ada Lovelace',
      'Lead Engineer',
      'ada@example.test',
      '#4F46E5',
      '42.500000',
      'Ada Lovelace (admin)',
    ])

    // The unlinked member: every optional value em-dashed, including the link —
    // she is a full collaborator, just an undecorated one.
    expect(cellText('Grace Hopper').slice(0, 6)).toEqual(['Grace Hopper', '—', '—', '—', '—', '—'])

    // Server order (name, then created_at) — the list is not re-sorted here.
    expect(
      screen
        .getAllByRole('row')
        .slice(1)
        .map((row) => row.getAttribute('aria-label'))
    ).toEqual(['Member Ada Lovelace', 'Member Grace Hopper'])
  })

  it('POSTs user_id: null when the member is saved with "No platform user"', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...GRACE, id: 'm3', name: 'Alan Turing' } })

    renderTeam()
    await screen.findByText('Ada Lovelace')

    await user.click(screen.getByRole('button', { name: 'Add Member' }))
    expect(await screen.findByRole('heading', { name: 'Add Team Member' })).toBeInTheDocument()

    // The picker opens on the unlinked case; choosing it explicitly proves the
    // option exists and carries the same meaning.
    await user.type(dialog().getByLabelText('Name'), 'Alan Turing')
    await choose(user, 'Platform user', 'No platform user')

    await user.click(screen.getByRole('button', { name: 'Add to Team' }))

    await waitFor(() => expect(mockPost).toHaveBeenCalled())

    const [url, body] = mockPost.mock.calls[0] as [string, Record<string, unknown>]
    expect(url).toBe('/api/v1/flan/projects/p1/team')
    expect(body).toEqual({
      name: 'Alan Turing',
      role: null,
      email: null,
      color: null,
      hourly_rate: null,
      user_id: null,
    })
    // (b) A literal null, PRESENT in the body — not '' and not omitted.
    expect(Object.keys(body)).toContain('user_id')
    expect(body.user_id).toBeNull()
    expect(body.user_id).not.toBe('')
    // Nothing we send is outside TeamMemberCreate.
    for (const field of Object.keys(body)) {
      expect(MEMBER_FIELDS).toContain(field)
    }
  })

  it('POSTs the chosen user id when a platform user IS linked', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...GRACE, id: 'm4', name: 'Alan Turing' } })

    renderTeam()
    await screen.findByText('Ada Lovelace')

    await user.click(screen.getByRole('button', { name: 'Add Member' }))
    await screen.findByRole('heading', { name: 'Add Team Member' })

    await user.type(dialog().getByLabelText('Name'), 'Alan Turing')
    await user.type(dialog().getByLabelText('Role'), 'Cryptanalyst')
    await user.type(dialog().getByLabelText('Colour'), '#0EA5E9')
    // Typed as a string and sent as a string (D-11) — no float ever appears.
    await user.type(dialog().getByLabelText('Hourly rate'), '37.250000')
    // A user with no full_name is offered by email.
    await choose(user, 'Platform user', 'grace@corp.test')

    await user.click(screen.getByRole('button', { name: 'Add to Team' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/flan/projects/p1/team', {
        name: 'Alan Turing',
        role: 'Cryptanalyst',
        email: null,
        color: '#0EA5E9',
        hourly_rate: '37.250000',
        user_id: 'u2',
      })
    })
  })

  it('says the rate is stored but unused, and derives no cost from it', async () => {
    const user = userEvent.setup()
    mockGets()
    renderTeam()

    await screen.findByText('Ada Lovelace')
    await user.click(screen.getByRole('button', { name: 'Add Member' }))
    await screen.findByRole('heading', { name: 'Add Team Member' })

    expect(
      dialog().getByText('stored for a later milestone; no cost is derived from it in v5.0')
    ).toBeInTheDocument()
  })

  it('PATCHes the edited member, round-tripping the rate string it was given', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPatch.mockResolvedValueOnce({ data: { ...ADA, role: 'Principal Engineer' } })

    renderTeam()
    await screen.findByText('Ada Lovelace')
    await rowAction(user, 'Ada Lovelace', 'Edit')

    expect(await screen.findByRole('heading', { name: 'Edit Team Member' })).toBeInTheDocument()
    // The form seeds the API's string verbatim — the input is not reformatted.
    expect(dialog().getByLabelText('Hourly rate')).toHaveValue('42.500000')

    const role = dialog().getByLabelText('Role')
    await user.clear(role)
    await user.type(role, 'Principal Engineer')
    await user.click(screen.getByRole('button', { name: 'Save Member' }))

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/api/v1/flan/team/m1', {
        name: 'Ada Lovelace',
        role: 'Principal Engineer',
        email: 'ada@example.test',
        color: '#4F46E5',
        hourly_rate: '42.500000',
        user_id: 'u1',
      })
    })
    const patchBody = mockPatch.mock.calls[0][1] as Record<string, unknown>
    for (const field of Object.keys(patchBody)) {
      expect(MEMBER_FIELDS).toContain(field)
    }
  })

  it('names the assignment clearing in the remove confirmation, then DELETEs', async () => {
    const user = userEvent.setup()
    mockGets()
    mockDelete.mockResolvedValueOnce({ data: undefined })

    renderTeam()
    await screen.findByText('Ada Lovelace')
    await rowAction(user, 'Ada Lovelace', 'Remove')

    // (c) The confirmation comes first and says what the soft remove does to the
    // member's assignments — and what it does NOT do to the tasks (D-V5P1-6).
    expect(await screen.findByRole('heading', { name: 'Remove member?' })).toBeInTheDocument()
    expect(screen.getByText(/clears their task and phase assignments/i)).toBeInTheDocument()
    expect(screen.getByText(/tasks themselves are left intact/i)).toBeInTheDocument()
    expect(mockDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Remove Ada Lovelace' }))

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('/api/v1/flan/team/m1')
    })
  })

  it('offers no reactivate action and no way to list removed members', async () => {
    const user = userEvent.setup()
    mockGets()
    renderTeam()

    await screen.findByText('Ada Lovelace')

    // v5.0 has no reactivation path by decision: no control, and no
    // `include_removed` parameter for one to call.
    expect(screen.queryByText(/reactivat/i)).toBeNull()
    expect(screen.queryByText(/removed member/i)).toBeNull()
    expect(JSON.stringify(mockGet.mock.calls)).not.toContain('include_removed')

    await user.click(screen.getByRole('button', { name: 'Member actions for Ada Lovelace' }))
    expect(screen.getAllByRole('menuitem').map((item) => item.textContent)).toEqual([
      'Edit',
      'Remove',
    ])
  })

  it("surfaces a 4xx detail from the save as an error toast in the server's words", async () => {
    const user = userEvent.setup()
    mockGets()
    const detail = 'User u1 is already linked to member Ada Lovelace (m1) on project p1.'
    mockPost.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 422, data: { detail } },
    })

    renderTeam()
    await screen.findByText('Ada Lovelace')

    await user.click(screen.getByRole('button', { name: 'Add Member' }))
    await screen.findByRole('heading', { name: 'Add Team Member' })
    await user.type(dialog().getByLabelText('Name'), 'Ada Again')
    await choose(user, 'Platform user', 'Ada Lovelace (admin)')
    await user.click(screen.getByRole('button', { name: 'Add to Team' }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(detail)
    })
  })
})
