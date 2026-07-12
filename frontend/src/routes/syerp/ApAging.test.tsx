// ABOUTME: Component tests for the SYERP AP Aging screen (Phase 09c, SYERP-12 AC6) — per-vendor
// ABOUTME: bucket cells and a grand-total footer render from a mocked GET, changing the as-of
// ABOUTME: date refetches with the new as_of param, and the 2110 tie-out badge renders.

/**
 * ApAging screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GET /ap/aging routed by URL), then asserts:
 *   1. Each vendor's bucket cells render (scoped to that vendor's row).
 *   2. The grand-total footer row renders.
 *   3. Changing the "As of" date refetches with the new as_of query param.
 *   4. The in-balance tie-out badge renders.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApAging } from '@/routes/syerp/ApAging'

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
  vendors: [
    {
      vendor_id: 'v1',
      vendor_name: 'Acme Metals',
      current: '100.00',
      d31_60: '40.00',
      d61_90: '25.00',
      d90_plus: '10.00',
      total: '175.00',
    },
    {
      vendor_id: 'v2',
      vendor_name: 'Beta Supply',
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
    if (url.includes('/ap/aging')) return Promise.resolve({ data: report })
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
        <ApAging />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ApAging screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders per-vendor bucket cells for each vendor', async () => {
    routeGet()

    renderScreen()

    // Acme's row carries its five bucket figures.
    const acmeRow = (await screen.findByText('Acme Metals')).closest('tr')!
    expect(within(acmeRow).getByText('100.00')).toBeInTheDocument()
    expect(within(acmeRow).getByText('40.00')).toBeInTheDocument()
    expect(within(acmeRow).getByText('25.00')).toBeInTheDocument()
    expect(within(acmeRow).getByText('10.00')).toBeInTheDocument()
    expect(within(acmeRow).getByText('175.00')).toBeInTheDocument()

    // Beta's row carries its own figures.
    const betaRow = screen.getByText('Beta Supply').closest('tr')!
    expect(within(betaRow).getByText('200.00')).toBeInTheDocument()
    expect(within(betaRow).getByText('250.00')).toBeInTheDocument()
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
      expect(mockGet).toHaveBeenCalledWith('/api/v1/syerp/ap/aging', {
        params: { as_of: '2026-03-15' },
      })
    })
  })

  it('renders the 2110 tie-out badge when in balance', async () => {
    routeGet()

    renderScreen()

    expect(await screen.findByText(/In balance — ties to 2110/)).toBeInTheDocument()
  })
})
