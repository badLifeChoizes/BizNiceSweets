// ABOUTME: Component test for the CRUMB QuoteDetail / builder (CRUMB-01) — the detail renders
// ABOUTME: from a mocked GET /crumb/quotes/:id (via useQuote over the mocked axios client); the
// ABOUTME: PLUM-derived line unit_price default shows and the service-derived total_value shows.

/**
 * QuoteDetail — component test.
 *
 * Mounts the builder at /crumb/quotes/:id with apiClient + sonner mocked, then asserts a
 * draft quote renders: the PLUM-derived line's default unit_price is displayed in its
 * editable row and the quote's service-derived total_value (D-11 string) is shown.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QuoteDetail } from '@/routes/crumb/QuoteDetail'

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

// A draft quote with a PLUM-derived line (unit_price 100.00, server-defaulted from cost)
// and a free-text line; total_value 150.00 is service-derived and unique among line totals.
const QUOTE = {
  id: 'q1',
  quote_number: 'Q-000001',
  partner_id: 'c1',
  opportunity_id: null,
  status: 'draft',
  actor_id: 'u1',
  created_at: '2026-07-01T00:00:00Z',
  total_value: '150.00',
  lines: [
    {
      id: 'ln1',
      quote_id: 'q1',
      plum_part_id: 'p1',
      description: null,
      quantity: '1',
      unit_price: '100.00',
      markup_pct: null,
      sort_order: 0,
      line_total: '100.00',
    },
    {
      id: 'ln2',
      quote_id: 'q1',
      plum_part_id: null,
      description: 'Installation service',
      quantity: '1',
      unit_price: '50.00',
      markup_pct: null,
      sort_order: 1,
      line_total: '50.00',
    },
  ],
}

// Route every GET by URL so query order does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/quotes/')) return Promise.resolve({ data: QUOTE })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: [] })
    if (url.includes('/plum/parts')) return Promise.resolve({ data: [] })
    return Promise.resolve({ data: [] })
  })
}

function renderQuoteDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/crumb/quotes/q1']}>
        <Routes>
          <Route path="/crumb/quotes/:id" element={<QuoteDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('QuoteDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the line price default and the quote total from a mocked GET', async () => {
    mockGets()

    renderQuoteDetail()

    // Header: quote number + status badge.
    expect(await screen.findByText('Q-000001')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()

    // The PLUM-derived line's default unit_price is displayed (editable input value).
    expect(screen.getByDisplayValue('100.00')).toBeInTheDocument()

    // The service-derived quote total_value (D-11 string) is shown.
    expect(screen.getByText('150.00')).toBeInTheDocument()
  })
})
