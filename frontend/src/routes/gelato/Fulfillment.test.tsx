// ABOUTME: Component tests for the GELATO Fulfillment screen (Phase 12b, Task 14) — the
// ABOUTME: pick list (ordered/reserved/picked/shipped), the dialog's suggested-source-bin
// ABOUTME: pre-fill, the EXACT PickRequest POST body (the 11b/12a keeper), and the
// ABOUTME: pick → pack → ship POST walk ending at /shipments/{id}/ship.

/**
 * Fulfillment — component tests.
 *
 * Mounts the screen with apiClient mocked per-endpoint and the SO preselected via a
 * ?so=<id> query param, then asserts:
 *   1. The pick list renders per line (ordered / reserved / picked / shipped).
 *   2. Opening the pick dialog pre-fills each line's suggested source bin.
 *   3. Confirm posts the EXACT PickRequest body
 *      { sales_order_id, staging_bin_id, lines: [{ sales_order_line_id, from_bin_id, qty }] }
 *      — the keeper: correct field NAMES + the qty as an exact Decimal string.
 *   4. The ship action POSTs to /api/v1/gelato/shipments/{id}/ship after a confirm.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Fulfillment from '@/routes/gelato/Fulfillment'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the bin/SO Selects are operable here.
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
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const SALES_ORDERS = [
  {
    id: 'so-1',
    so_number: 'SO-0001',
    partner_id: 'p-1',
    source_quote_id: null,
    source_opportunity_id: null,
    status: 'confirmed',
    order_date: '2026-07-01',
    required_date: null,
    actor_id: 'u-1',
    created_at: 'x',
  },
]

// One line, remaining-to-pick = 5.000000 (nothing picked yet). suggested_from_bin_id
// (bin 6 / B-02) is deliberately different from the first candidate bin (bin 5 / A-01)
// so the staging default and the source default are distinguishable in the payload.
const PICK_LIST = {
  sales_order_id: 'so-1',
  lines: [
    {
      sales_order_line_id: 'sol-1',
      item_id: 'item-1',
      description: 'M3 hex bolt',
      qty_ordered: '5.000000',
      qty_reserved: '5.000000',
      qty_picked: '0.000000',
      qty_shipped: '0.000000',
      suggested_from_bin_id: 6,
      available_bins: [
        { bin_id: 5, code: 'A-01', on_hand: '20.000000' },
        { bin_id: 6, code: 'B-02', on_hand: '8.000000' },
      ],
    },
  ],
}

const SHIPMENT_PICKING = {
  id: 100,
  sales_order_id: 'so-1',
  location_id: 1,
  staging_bin_id: 5,
  status: 'picking',
  journal_entry_id: null,
  lines: [
    {
      id: 1,
      sales_order_line_id: 'sol-1',
      item_id: 'item-1',
      from_bin_id: 6,
      qty: '5.000000',
      inventory_txn_id: null,
    },
  ],
  created_at: 'x',
}

const SHIPMENT_PACKED = { ...SHIPMENT_PICKING, status: 'packed' }
const SHIPMENT_SHIPPED = { ...SHIPMENT_PICKING, status: 'shipped' }

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/sales-orders')) return Promise.resolve({ data: SALES_ORDERS })
    if (url.includes('/pick-list')) return Promise.resolve({ data: PICK_LIST })
    return Promise.resolve({ data: [] })
  })
}

// Route POSTs by URL through the pick → pack → ship FSM.
function mockPostByUrl() {
  mockPost.mockImplementation((url: string) => {
    if (url.endsWith('/shipments/pick')) return Promise.resolve({ data: SHIPMENT_PICKING })
    if (url.endsWith('/pack')) return Promise.resolve({ data: SHIPMENT_PACKED })
    if (url.endsWith('/ship')) return Promise.resolve({ data: SHIPMENT_SHIPPED })
    return Promise.resolve({ data: {} })
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
      <MemoryRouter initialEntries={['/gelato/fulfillment?so=so-1']}>
        <Fulfillment />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Fulfillment screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the pick list with ordered/reserved/picked/shipped for the preselected SO', async () => {
    mockGetByUrl()
    renderScreen()

    expect(await screen.findByText('M3 hex bolt')).toBeInTheDocument()
    // Ordered/reserved 5, picked/shipped 0 — Decimal strings rendered as-is.
    expect(screen.getAllByText('5.000000')).toHaveLength(2)
    expect(screen.getAllByText('0.000000')).toHaveLength(2)
  })

  it('pre-fills the suggested source bin in the pick dialog', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    renderScreen()

    await screen.findByText('M3 hex bolt')
    await user.click(screen.getByRole('button', { name: 'Pick' }))

    // Dialog opens; the source bin pre-fills to the suggestion (bin 6 → 'B-02').
    expect(await screen.findByRole('heading', { name: 'Pick Sales Order' })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText('Source bin')).toHaveTextContent('B-02')
    })
    // Quantity defaults to remaining-to-pick (the full ordered qty).
    expect(screen.getByLabelText('Quantity')).toHaveValue('5.000000')
  })

  it('posts the EXACT PickRequest body on Confirm (the 11b/12a keeper)', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    mockPostByUrl()
    renderScreen()

    await screen.findByText('M3 hex bolt')
    await user.click(screen.getByRole('button', { name: 'Pick' }))
    await screen.findByRole('heading', { name: 'Pick Sales Order' })
    await waitFor(() => expect(screen.getByLabelText('Source bin')).toHaveTextContent('B-02'))

    await user.click(screen.getByRole('button', { name: 'Confirm Pick' }))

    // The load-bearing assertion: correct field NAMES + a string qty. Source bin is
    // the suggestion (6); staging bin defaults to the first candidate bin (5).
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/gelato/shipments/pick', {
        sales_order_id: 'so-1',
        staging_bin_id: 5,
        lines: [{ sales_order_line_id: 'sol-1', from_bin_id: 6, qty: '5.000000' }],
      })
    })
  })

  it('walks pick → pack → ship, POSTing the ship endpoint after confirmation', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    mockPostByUrl()
    renderScreen()

    // Pick.
    await screen.findByText('M3 hex bolt')
    await user.click(screen.getByRole('button', { name: 'Pick' }))
    await screen.findByRole('heading', { name: 'Pick Sales Order' })
    await waitFor(() => expect(screen.getByLabelText('Source bin')).toHaveTextContent('B-02'))
    await user.click(screen.getByRole('button', { name: 'Confirm Pick' }))

    // Pack becomes available once the shipment is 'picking'.
    await user.click(await screen.findByRole('button', { name: 'Pack' }))

    // Ship becomes available once the shipment is 'packed'; it asks for confirmation.
    await user.click(await screen.findByRole('button', { name: 'Ship' }))
    await user.click(await screen.findByRole('button', { name: 'Confirm Ship' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/gelato/shipments/100/ship', {})
    })
  })
})
