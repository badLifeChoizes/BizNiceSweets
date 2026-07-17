// ABOUTME: Component test for the CRUMB Sales Orders list screen (CRUMB-01, Phase 11b) — the
// ABOUTME: table renders sales orders from a mocked GET (via useSalesOrders over the mocked axios
// ABOUTME: client), showing the SO number, customer name, status badge, and order date per row.

/**
 * SalesOrders screen — component test.
 *
 * Mounts the screen with apiClient + sonner mocked, then asserts the list renders the
 * sales orders returned by a mocked GET /crumb/sales-orders (SO #, the customer resolved
 * from the partners lookup, and the status badge).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SalesOrders } from '@/routes/crumb/SalesOrders'

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

const CUSTOMERS = [
  { id: 'c1', name: 'Acme Corp' },
  { id: 'c2', name: 'Globex' },
]

const SALES_ORDERS = [
  {
    id: 'so1',
    so_number: 'SO-000001',
    partner_id: 'c1',
    source_quote_id: null,
    source_opportunity_id: null,
    status: 'draft',
    order_date: '2026-07-10',
    required_date: null,
    actor_id: 'u1',
    created_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'so2',
    so_number: 'SO-000002',
    partner_id: 'c2',
    source_quote_id: 'q9',
    source_opportunity_id: null,
    status: 'confirmed',
    order_date: '2026-07-11',
    required_date: null,
    actor_id: 'u1',
    created_at: '2026-07-11T00:00:00Z',
  },
]

// Route every GET by URL so query order does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/sales-orders')) return Promise.resolve({ data: SALES_ORDERS })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: CUSTOMERS })
    return Promise.resolve({ data: [] })
  })
}

function renderSalesOrders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SalesOrders />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SalesOrders screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the sales-order list from a mocked GET, showing each row', async () => {
    mockGets()

    renderSalesOrders()

    expect(screen.getByRole('heading', { name: 'Sales Orders' })).toBeInTheDocument()

    // Rows render SO #, the resolved customer name, and the status badge for each order.
    expect(await screen.findByText('SO-000001')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('2026-07-10')).toBeInTheDocument()

    expect(screen.getByText('SO-000002')).toBeInTheDocument()
    expect(screen.getByText('Globex')).toBeInTheDocument()
    expect(screen.getByText('Confirmed')).toBeInTheDocument()
    expect(screen.getByText('2026-07-11')).toBeInTheDocument()
  })
})
