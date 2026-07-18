// ABOUTME: Component tests for the GELATO Putaway screen (Phase 12a, Task 14) — the
// ABOUTME: unbinned-stock list, the dialog's suggested-bin + full-qty pre-fill, the
// ABOUTME: EXACT PutawayRequest POST body (the 11b keeper), and a 422 over-draw toast.

/**
 * Putaway — component tests.
 *
 * Mounts the screen with apiClient mocked per-endpoint (locations / items / unbinned
 * / bins / suggestion), then asserts:
 *   1. The unbinned-stock list renders for the (default-selected) location.
 *   2. Opening the dialog pre-fills the suggested target bin and defaults qty to the
 *      full unbinned qty.
 *   3. Confirm posts the EXACT PutawayRequest body
 *      { item_id, location_id, to_bin_id, qty, from_bin_id: null } — the 11b keeper:
 *      correct field NAMES and types (item_id string, location_id/to_bin_id numbers,
 *      qty the entered string, from_bin_id null for an unbinned putaway).
 *   4. A 422 over-draw rejection surfaces a toast.error and keeps the dialog open.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Putaway } from '@/routes/gelato/Putaway'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the bin/location Selects are operable here.
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
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

// Mock sonner toasts so we can assert success + error surfacing.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
import { toast } from 'sonner'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)
const mockToastError = vi.mocked(toast.error)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const LOCATIONS = [
  { id: 1, name: 'Main Warehouse', active: true },
  { id: 2, name: 'Assembly Line', active: true },
]

const ITEMS = [
  { id: 'item-1', code: 'ITEM-0001', name: 'M3 hex bolt' },
  { id: 'item-2', code: 'ITEM-0002', name: 'M4 washer' },
]

const UNBINNED = [
  { item_id: 'item-1', location_id: 1, unbinned_qty: '10.000000', suggested_bin_id: 5 },
  { item_id: 'item-2', location_id: 1, unbinned_qty: '3.000000', suggested_bin_id: null },
]

const BINS = [
  { id: 5, location_id: 1, code: 'A-01', description: null, active: true, created_at: 'x' },
  { id: 6, location_id: 1, code: 'A-02', description: null, active: true, created_at: 'x' },
]

const SUGGESTION = { suggested_bin_id: 5 }

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/inventory/locations')) return Promise.resolve({ data: LOCATIONS })
    if (url.includes('/inventory/items')) return Promise.resolve({ data: ITEMS })
    if (url.includes('/unbinned')) return Promise.resolve({ data: UNBINNED })
    if (url.includes('/putaway/suggestion')) return Promise.resolve({ data: SUGGESTION })
    if (url.includes('/bins')) return Promise.resolve({ data: BINS })
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
      <MemoryRouter initialEntries={['/gelato/putaway']}>
        <Putaway />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Putaway screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the unbinned-stock list for the default-selected location', async () => {
    mockGetByUrl()
    renderScreen()

    // item_id resolved to code · name, with the unbinned Decimal string as-is.
    expect(await screen.findByText('ITEM-0001 · M3 hex bolt')).toBeInTheDocument()
    expect(screen.getByText('ITEM-0002 · M4 washer')).toBeInTheDocument()
    expect(screen.getByText('10.000000')).toBeInTheDocument()
    expect(screen.getByText('3.000000')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Put away' })).toHaveLength(2)
  })

  it('pre-fills the suggested bin and defaults qty to the full unbinned qty', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    renderScreen()

    await screen.findByText('ITEM-0001 · M3 hex bolt')
    await user.click(screen.getAllByRole('button', { name: 'Put away' })[0])

    // Dialog opens; qty pre-fills to the item's full unbinned qty.
    expect(await screen.findByRole('heading', { name: 'Put Away Stock' })).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toHaveValue('10.000000')
    // The suggested bin (id 5 → 'A-01') is pre-selected in the target Select.
    await waitFor(() => {
      expect(screen.getByLabelText('Target bin')).toHaveTextContent('A-01')
    })
  })

  it('posts the EXACT PutawayRequest body on Confirm (the 11b keeper)', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    mockPost.mockResolvedValue({
      data: { out_leg: {}, in_leg: {}, bin_on_hand: '10', location_total: '10' },
    })
    renderScreen()

    await screen.findByText('ITEM-0001 · M3 hex bolt')
    await user.click(screen.getAllByRole('button', { name: 'Put away' })[0])
    await screen.findByRole('heading', { name: 'Put Away Stock' })

    // Accept the suggested bin (id 5) + default qty (10.000000), then confirm.
    await waitFor(() => expect(screen.getByLabelText('Target bin')).toHaveTextContent('A-01'))
    await user.click(screen.getByRole('button', { name: 'Confirm Putaway' }))

    // The load-bearing assertion: correct field NAMES and types, from_bin_id null.
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/gelato/putaway', {
        item_id: 'item-1',
        location_id: 1,
        to_bin_id: 5,
        qty: '10.000000',
        from_bin_id: null,
      })
    })
  })

  it('surfaces a 422 over-draw rejection as a toast and keeps the dialog open', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    // Backend rejects putting away more than is unbinned.
    mockPost.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: 'Putaway exceeds unbinned quantity' } },
    })
    renderScreen()

    await screen.findByText('ITEM-0001 · M3 hex bolt')
    await user.click(screen.getAllByRole('button', { name: 'Put away' })[0])
    await screen.findByRole('heading', { name: 'Put Away Stock' })

    await waitFor(() => expect(screen.getByLabelText('Target bin')).toHaveTextContent('A-01'))
    await user.clear(screen.getByLabelText('Quantity'))
    await user.type(screen.getByLabelText('Quantity'), '999')
    await user.click(screen.getByRole('button', { name: 'Confirm Putaway' }))

    // The server detail is surfaced via toast.error and the dialog stays open.
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Putaway exceeds unbinned quantity')
    })
    expect(screen.getByRole('heading', { name: 'Put Away Stock' })).toBeInTheDocument()
  })
})
