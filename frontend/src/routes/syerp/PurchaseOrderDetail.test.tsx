// ABOUTME: Component tests for the SYERP Purchase Order detail screen — header
// ABOUTME: (PO#, vendor, status), the ordered/received/outstanding line roll-up, and
// ABOUTME: the status-driven Approve/Close + per-line Receive action visibility.

/**
 * PurchaseOrderDetail — component tests.
 *
 * Mounts the detail screen at /syerp/purchasing/orders/:id with apiClient.get
 * mocked per-endpoint (order / vendors / items), then asserts:
 *   1. The header (PO number + vendor name) and a line row render, showing
 *      ordered / received / outstanding (outstanding = ordered − received).
 *   2. A DRAFT PO shows "Approve" and hides "Close" and per-line "Receive".
 *   3. An APPROVED PO hides "Approve", shows "Close", and shows "Receive" on a
 *      line that still has outstanding quantity.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PurchaseOrderDetail } from '@/routes/syerp/PurchaseOrderDetail'

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

const VENDORS = [{ id: 'ven-1', name: 'Acme Fasteners', is_vendor: true, is_customer: false }]

const ITEMS = [
  { id: 'item-1', code: 'ITEM-0001', name: 'M3 hex bolt', unit_of_measure: 'ea', active: true },
]

function makePo(status: string) {
  return {
    id: 'po-1',
    po_number: 'PO-0001',
    vendor_id: 'ven-1',
    status,
    notes: null,
    approved_at: status === 'draft' ? null : '2026-03-01T00:00:00Z',
    created_at: '2026-02-01T00:00:00Z',
    updated_at: '2026-02-01T00:00:00Z',
    total: '25.0000',
    total_ordered_qty: '10.000000',
    total_received_qty: '4.000000',
    outstanding_qty: '6.000000',
    lines: [
      {
        id: 'line-1',
        po_id: 'po-1',
        item_id: 'item-1',
        line_no: 1,
        qty_ordered: '10.000000',
        unit_cost: '2.5000',
        qty_received: '4.000000',
        need_by_date: null,
      },
    ],
  }
}

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl(status: string) {
  mockApiClientGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: VENDORS })
    if (url.includes('/inventory/items')) return Promise.resolve({ data: ITEMS })
    return Promise.resolve({ data: makePo(status) })
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
      <MemoryRouter initialEntries={['/syerp/purchasing/orders/po-1']}>
        <Routes>
          <Route path="/syerp/purchasing/orders/:id" element={<PurchaseOrderDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PurchaseOrderDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders header + line roll-up (ordered / received / outstanding)', async () => {
    mockGetByUrl('approved')
    renderDetail()

    // Header: PO number + resolved vendor name
    expect(await screen.findByText('PO-0001')).toBeInTheDocument()
    expect(screen.getByText('Acme Fasteners')).toBeInTheDocument()

    // Line item name resolved from item_id
    expect(screen.getByText('ITEM-0001 — M3 hex bolt')).toBeInTheDocument()

    // Ordered (10), received (4), outstanding (10 − 4 = 6) all render
    expect(screen.getByText('10.000000')).toBeInTheDocument()
    expect(screen.getByText('4.000000')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
  })

  it('shows Approve (and hides Close/Receive) for a draft PO', async () => {
    mockGetByUrl('draft')
    renderDetail()

    expect(await screen.findByText('PO-0001')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Receive line/ })).not.toBeInTheDocument()
  })

  it('shows Close + per-line Receive (and hides Approve) for an approved PO', async () => {
    mockGetByUrl('approved')
    renderDetail()

    expect(await screen.findByText('PO-0001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Receive line 1' })).toBeInTheDocument()
  })
})
