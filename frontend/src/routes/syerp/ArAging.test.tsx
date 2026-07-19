// ABOUTME: Component tests for the SYERP AR Aging screen (Phase 13, SYERP-13) — per-customer
// ABOUTME: bucket cells and a grand-total footer render from a mocked GET, changing the as-of
// ABOUTME: date refetches with the new as_of param, and the 1120 tie-out badge renders.

/**
 * ArAging screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GET /ar/aging routed by URL), then asserts:
 *   1. Each customer's bucket cells render (scoped to that customer's row).
 *   2. The grand-total footer row renders.
 *   3. Changing the "As of" date refetches with the new as_of query param.
 *   4. The in-balance 1120 tie-out badge renders.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ArAging } from '@/routes/syerp/ArAging'

// Mock the axios apiClient module.
vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

// Mock sonner toasts so nothing throws in jsdom.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

// Distinct bucket values so per-cell assertions are unambiguous within each row.
const REPORT = {
  as_of: '2026-07-12',
  customers: [
    {
      customer_id: 'c1',
      customer_name: 'Globex Health',
      current: '100.00',
      d31_60: '40.00',
      d61_90: '25.00',
      d90_plus: '10.00',
      total: '175.00',
    },
    {
      customer_id: 'c2',
      customer_name: 'Initech Clinics',
      current: '200.00',
      d31_60: '30.00',
      d61_90: '15.00',
      d90_plus: '5.00',
      total: '250.00',
    },
  ],
  grand_total: {
    current: '300.00',
    d31_60: '70.00',
    d61_90: '40.00',
    d90_plus: '15.00',
    total: '425.00',
  },
  control_balance: '425.00',
  in_balance: true,
}

function routeGet(report: unknown = REPORT) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/ar/aging')) return Promise.resolve({ data: report })
    return Promise.resolve({ data: [] })
  })
}

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ArAging />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ArAging screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders per-customer bucket cells for each customer', async () => {
    routeGet()

    renderScreen()

    // Globex's row carries its five bucket figures.
    const globexRow = (await screen.findByText('Globex Health')).closest('tr')!
    expect(within(globexRow).getByText('100.00')).toBeInTheDocument()
    expect(within(globexRow).getByText('40.00')).toBeInTheDocument()
    expect(within(globexRow).getByText('25.00')).toBeInTheDocument()
    expect(within(globexRow).getByText('10.00')).toBeInTheDocument()
    expect(within(globexRow).getByText('175.00')).toBeInTheDocument()

    // Initech's row carries its own figures.
    const initechRow = screen.getByText('Initech Clinics').closest('tr')!
    expect(within(initechRow).getByText('200.00')).toBeInTheDocument()
    expect(within(initechRow).getByText('250.00')).toBeInTheDocument()
  })

  it('renders the grand-total footer row', async () => {
    routeGet()

    renderScreen()

    const totalRow = (await screen.findByText('Grand total')).closest('tr')!
    expect(within(totalRow).getByText('300.00')).toBeInTheDocument()
    expect(within(totalRow).getByText('70.00')).toBeInTheDocument()
    expect(within(totalRow).getByText('425.00')).toBeInTheDocument()
  })

  it('refetches with the new as_of when the date changes', async () => {
    routeGet()

    renderScreen()

    // First fetch uses the default (today) as_of.
    await waitFor(() => expect(mockGet).toHaveBeenCalled())

    // Change the "As of" date → the query key changes and a new fetch fires.
    fireEvent.change(screen.getByLabelText('As of date'), {
      target: { value: '2026-03-15' },
    })

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/api/v1/syerp/ar/aging', {
        params: { as_of: '2026-03-15' },
      })
    })
  })

  it('renders the 1120 tie-out badge when in balance', async () => {
    routeGet()

    renderScreen()

    expect(await screen.findByText(/In balance — ties to 1120/)).toBeInTheDocument()
  })
})
