// ABOUTME: Component test for the CRUMB Pipeline board (CRUMB-01) — the stage-grouped columns
// ABOUTME: render from a mocked GET /crumb/opportunities?pipeline=true (via usePipeline over the
// ABOUTME: mocked axios client), and an opportunity lands under its own stage column.

/**
 * Pipeline screen — component test.
 *
 * Mounts the board with apiClient + sonner mocked, then asserts the four stage column
 * headers (Qualify / Proposal / Won / Lost) render and that an opportunity placed in the
 * "proposal" group is displayed under the Proposal column (and not under Qualify).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Pipeline } from '@/routes/crumb/Pipeline'

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
const mockGet = vi.mocked(apiClient.get)

const OPP = {
  id: 'o1',
  name: 'Acme Line Expansion',
  partner_id: 'c1',
  lead_id: null,
  estimated_value: '50000.00',
  expected_close_date: '2026-09-01',
  stage: 'proposal',
  actor_id: 'u1',
  created_at: '2026-07-01T00:00:00Z',
}

// The stage-grouped board (?pipeline=true): the sole opportunity sits in "proposal".
const BOARD = {
  qualify: [],
  proposal: [OPP],
  won: [],
  lost: [],
}

// Route every GET by URL so query order does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/opportunities')) return Promise.resolve({ data: BOARD })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: [] })
    return Promise.resolve({ data: [] })
  })
}

function renderPipeline() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Pipeline />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Pipeline screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the four stage columns and groups the opportunity under Proposal', async () => {
    mockGets()

    renderPipeline()

    // The four stage-group headers render once the board resolves.
    const proposalHeader = await screen.findByText('Proposal')
    expect(screen.getByText('Qualify')).toBeInTheDocument()
    expect(proposalHeader).toBeInTheDocument()
    expect(screen.getByText('Won')).toBeInTheDocument()
    expect(screen.getByText('Lost')).toBeInTheDocument()

    // The opportunity lands under its own stage column (Proposal), not another.
    const proposalColumn = proposalHeader.parentElement!.parentElement!
    expect(within(proposalColumn).getByText('Acme Line Expansion')).toBeInTheDocument()

    const qualifyColumn = screen.getByText('Qualify').parentElement!.parentElement!
    expect(within(qualifyColumn).queryByText('Acme Line Expansion')).not.toBeInTheDocument()
  })
})
