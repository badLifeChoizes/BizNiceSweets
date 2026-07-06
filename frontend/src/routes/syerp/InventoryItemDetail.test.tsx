// ABOUTME: Component tests for the SYERP Inventory Item detail screen — header,
// ABOUTME: on-hand-by-location + valuation, immutable transaction ledger, and the
// ABOUTME: Adjust/Transfer action seams (stub dialogs, Tasks 12/13).

/**
 * InventoryItemDetail — component tests.
 *
 * Mounts the detail screen at /syerp/inventory/items/:id with apiClient.get
 * mocked per-endpoint (item / onhand / transactions), then asserts:
 *   1. The item header (name + code) renders.
 *   2. Per-location on-hand rows + grand-total qty, moving-avg cost and value
 *      are shown as-is (Decimal strings, no float math).
 *   3. The immutable ledger renders its rows (type / qty / location / reason).
 *   4. "Adjust Stock" and "Transfer Stock" buttons exist and open their dialogs.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InventoryItemDetail } from '@/routes/syerp/InventoryItemDetail'

// Mock the axios apiClient module
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

import { apiClient } from '@/api/client'
const mockApiClientGet = vi.mocked(apiClient.get)

const ITEM = {
  id: 'item-1',
  code: 'ITEM-0001',
  name: 'M3 hex bolt',
  unit_of_measure: 'ea',
  plum_part_id: null,
  moving_avg_cost: '0.4200',
  active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const ONHAND = {
  item_id: 'item-1',
  moving_avg_cost: '0.4200',
  locations: [
    { location_id: 1, location_name: 'Main Warehouse', quantity: '120.000000' },
    { location_id: 2, location_name: 'Assembly Line', quantity: '30.000000' },
  ],
  total_quantity: '150.000000',
  onhand_value: '63.0000',
}

const TRANSACTIONS = [
  {
    id: 'txn-2',
    item_id: 'item-1',
    location_id: 2,
    location_name: 'Assembly Line',
    txn_type: 'transfer',
    quantity: '30.000000',
    unit_cost: null,
    reason: null,
    created_at: '2026-02-02T10:00:00Z',
  },
  {
    id: 'txn-1',
    item_id: 'item-1',
    location_id: 1,
    location_name: 'Main Warehouse',
    txn_type: 'receipt',
    quantity: '150.000000',
    unit_cost: '0.4200',
    reason: 'Initial stock',
    created_at: '2026-02-01T09:00:00Z',
  },
]

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl() {
  mockApiClientGet.mockImplementation((url: string) => {
    if (url.endsWith('/onhand')) return Promise.resolve({ data: ONHAND })
    if (url.endsWith('/transactions')) return Promise.resolve({ data: TRANSACTIONS })
    return Promise.resolve({ data: ITEM })
  })
}

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/syerp/inventory/items/item-1']}>
        <Routes>
          <Route path="/syerp/inventory/items/:id" element={<InventoryItemDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InventoryItemDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders header, per-location on-hand, valuation and the ledger', async () => {
    mockGetByUrl()
    renderDetail()

    // Item header
    expect(await screen.findByText('M3 hex bolt')).toBeInTheDocument()
    expect(screen.getByText('ITEM-0001 · ea')).toBeInTheDocument()

    // Per-location on-hand rows (location names also appear in the ledger below)
    expect((await screen.findAllByText('Main Warehouse')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Assembly Line').length).toBeGreaterThan(0)

    // Valuation figures rendered as-is (Decimal strings)
    expect(screen.getByText('63.0000')).toBeInTheDocument()
    expect(screen.getAllByText('0.4200').length).toBeGreaterThan(0)

    // Ledger rows: type badge + reason
    expect(screen.getByText('Receipt')).toBeInTheDocument()
    expect(screen.getByText('Transfer')).toBeInTheDocument()
    expect(screen.getByText('Initial stock')).toBeInTheDocument()
  })

  it('opens the Adjust Stock and Transfer Stock dialogs from the action seams', async () => {
    const user = userEvent.setup()
    mockGetByUrl()
    renderDetail()

    await screen.findByText('M3 hex bolt')

    await user.click(screen.getByRole('button', { name: 'Adjust Stock' }))
    expect(await screen.findByRole('heading', { name: 'Adjust Stock' })).toBeInTheDocument()

    // Close, then open the transfer dialog.
    await user.keyboard('{Escape}')
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Adjust Stock' })).not.toBeInTheDocument(),
    )

    await user.click(screen.getByRole('button', { name: 'Transfer Stock' }))
    expect(await screen.findByRole('heading', { name: 'Transfer Stock' })).toBeInTheDocument()
  })
})
