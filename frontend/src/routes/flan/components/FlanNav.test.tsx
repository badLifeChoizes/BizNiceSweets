// ABOUTME: Component tests for FlanNav (Phase 1, Task 21) — the project switcher's
// ABOUTME: options, that its current value comes from useParams().projectId (not the
// ABOUTME: first project), that switching preserves the section, and the sub-nav hrefs.

/**
 * FlanNav — component tests for the URL-scoped project switcher (D-V5P1-3).
 *
 * Mounts the nav inside a real MemoryRouter (so `useParams` / `useNavigate` are the
 * genuine article, not a spy) with apiClient mocked so `useProjects` resolves a
 * two-project fixture, then asserts:
 *   1. one option per project from the mocked project list,
 *   2. the current project is the URL's `:projectId` — rendered at
 *      /flan/projects/B/tasks the trigger shows Project B, NOT the first project,
 *   3. choosing another project keeps the section: from /flan/projects/A/tasks,
 *      picking B routes to /flan/projects/B/tasks (a switcher that reset to the
 *      default section would land on /phases and fail here),
 *   4. the sub-nav links point at the CURRENT project's phases/tasks/team.
 *
 * Mirrors routes/gelato/Putaway.test.tsx (apiClient mock + Radix Select stubs).
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FlanNav } from '@/routes/flan/components/FlanNav'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the project switcher is operable here.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock the axios apiClient module — useProjects reads through it.
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

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

// Project A is deliberately FIRST so "shows the first project" cannot pass for
// "shows the project in the URL".
const PROJECTS = [
  {
    id: 'A',
    name: 'Project A',
    key_prefix: 'PRJA',
    category: null,
    description: null,
    currency: 'USD',
    start_date: null,
    gate_date: null,
    active: true,
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'B',
    name: 'Project B',
    key_prefix: 'PRJB',
    category: null,
    description: null,
    currency: 'USD',
    start_date: null,
    gate_date: null,
    active: true,
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

/** Renders the pathname so navigation is asserted on the real router, not a spy. */
function LocationProbe() {
  const { pathname } = useLocation()
  return <div data-testid="pathname">{pathname}</div>
}

function renderNav(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const screenElement = (
    <>
      <FlanNav />
      <LocationProbe />
    </>
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/flan/projects" element={screenElement} />
          <Route path="/flan/projects/:projectId/:section" element={screenElement} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('FlanNav', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: PROJECTS })
  })

  it('renders one switcher option per project', async () => {
    const user = userEvent.setup()
    renderNav('/flan/projects/A/phases')

    await user.click(await screen.findByLabelText('Project'))

    const options = await screen.findAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual(['Project A', 'Project B'])
  })

  it('shows the project from useParams().projectId, not the first in the list', async () => {
    renderNav('/flan/projects/B/tasks')

    const trigger = await screen.findByLabelText('Project')
    // The switcher's value resolves once the project list lands.
    await waitFor(() => expect(trigger).toHaveTextContent('Project B'))
    expect(trigger).not.toHaveTextContent('Project A')
  })

  it('switching projects preserves the current section', async () => {
    const user = userEvent.setup()
    renderNav('/flan/projects/A/tasks')

    // Sanity: we start on A's Tasks screen.
    expect(screen.getByTestId('pathname')).toHaveTextContent('/flan/projects/A/tasks')

    await user.click(await screen.findByLabelText('Project'))
    await user.click(await screen.findByRole('option', { name: 'Project B' }))

    // Only the project segment changed — still /tasks, not the default /phases.
    expect(await screen.findByTestId('pathname')).toHaveTextContent('/flan/projects/B/tasks')
  })

  it('points the sub-nav links at the current project', async () => {
    renderNav('/flan/projects/B/tasks')

    expect(await screen.findByRole('link', { name: 'Phases' })).toHaveAttribute(
      'href',
      '/flan/projects/B/phases'
    )
    expect(screen.getByRole('link', { name: 'Tasks' })).toHaveAttribute(
      'href',
      '/flan/projects/B/tasks'
    )
    expect(screen.getByRole('link', { name: 'Team' })).toHaveAttribute(
      'href',
      '/flan/projects/B/team'
    )
    expect(screen.getByRole('link', { name: 'All Projects' })).toHaveAttribute(
      'href',
      '/flan/projects'
    )
  })
})
