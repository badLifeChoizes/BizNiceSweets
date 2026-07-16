// ABOUTME: Component test for the CRUMB Leads list screen (CRUMB-01) — the table renders
// ABOUTME: leads from a mocked GET (via useLeads over the mocked axios client), showing the
// ABOUTME: name / company / status of each row.

/**
 * Leads screen — component test.
 *
 * Mounts the screen with apiClient + sonner mocked, then asserts the list renders the
 * leads returned by a mocked GET /crumb/leads (name, company, and the status badge).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Leads } from '@/routes/crumb/Leads'

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

const LEADS = [
  {
    id: 'l1',
    name: 'Ada Lovelace',
    company: 'Analytical Engines',
    contact: 'ada@analytical.example',
    source: 'referral',
    status: 'new',
    active: true,
    partner_id: null,
    opportunity_id: null,
    actor_id: 'u1',
    created_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'l2',
    name: 'Grace Hopper',
    company: 'Compiler Works',
    contact: 'grace@compiler.example',
    source: 'web',
    status: 'qualified',
    active: true,
    partner_id: null,
    opportunity_id: null,
    actor_id: 'u1',
    created_at: '2026-07-02T00:00:00Z',
  },
]

// Route every GET by URL so query order does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/leads')) return Promise.resolve({ data: LEADS })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: [] })
    return Promise.resolve({ data: [] })
  })
}

function renderLeads() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Leads />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Leads screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the leads list from a mocked GET, showing each row', async () => {
    mockGets()

    renderLeads()

    expect(screen.getByRole('heading', { name: 'Leads' })).toBeInTheDocument()

    // Rows render name, company, and the status badge for each lead.
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('Analytical Engines')).toBeInTheDocument()
    expect(screen.getByText('New')).toBeInTheDocument()

    expect(screen.getByText('Grace Hopper')).toBeInTheDocument()
    expect(screen.getByText('Compiler Works')).toBeInTheDocument()
    expect(screen.getByText('Qualified')).toBeInTheDocument()
  })
})
