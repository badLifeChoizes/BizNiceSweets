// ABOUTME: Component test for the CRUMB SalesOrderDetail screen (CRUMB-01, Phase 11b) — the
// ABOUTME: detail renders from a mocked GET /crumb/sales-orders/:id (via useSalesOrder over the
// ABOUTME: mocked axios client): the ordered/reserved/shortage line figures, a highlighted
// ABOUTME: shortage, a Non-stock flag, and the status-appropriate FSM action buttons.

/**
 * SalesOrderDetail — component test.
 *
 * Mounts the detail at /crumb/sales-orders/:id with apiClient + sonner mocked, then asserts:
 *   - a draft SO renders its ordered / reserved / shortage figures, flags the shortage line
 *     (amber) and the non-stock line (Non-stock badge), and shows Confirm + Cancel;
 *   - a confirmed SO shows Fulfill + Cancel (and not Confirm).
 *
 * Money & quantity fields are Decimals serialized as exact STRINGS (D-11).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SalesOrderDetail } from '@/routes/crumb/SalesOrderDetail'

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

const CUSTOMERS = [{ id: 'c1', name: 'Acme Corp' }]
const PARTS = [{ id: 'p1', part_number: 'PN-001' }]

// A shortage line (stock part PN-001, ordered 8 / reserved 6 / shortage 2) and a non-stock
// free-text line (item_id null → Non-stock flag, no shortage).
function salesOrder(status: string) {
  return {
    id: 'so1',
    so_number: 'SO-000001',
    partner_id: 'c1',
    source_quote_id: null,
    source_opportunity_id: null,
    status,
    order_date: '2026-07-10',
    required_date: null,
    actor_id: 'u1',
    created_at: '2026-07-10T00:00:00Z',
    total_value: '130.00',
    lines: [
      {
        id: 'sol1',
        sales_order_id: 'so1',
        item_id: 'i1',
        plum_part_id: 'p1',
        description: null,
        qty_ordered: '8',
        unit_price: '10.00',
        qty_reserved: '6',
        sort_order: 0,
        line_total: '80.00',
        shortage: '2',
      },
      {
        id: 'sol2',
        sales_order_id: 'so1',
        item_id: null,
        plum_part_id: null,
        description: 'Installation service',
        qty_ordered: '1',
        unit_price: '50.00',
        qty_reserved: '0',
        sort_order: 1,
        line_total: '50.00',
        shortage: '0',
      },
    ],
  }
}

// Route every GET by URL so query order does not matter.
function mockGets(status: string) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/sales-orders/')) return Promise.resolve({ data: salesOrder(status) })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: CUSTOMERS })
    if (url.includes('/plum/parts')) return Promise.resolve({ data: PARTS })
    return Promise.resolve({ data: [] })
  })
}

function renderSalesOrderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/crumb/sales-orders/so1']}>
        <Routes>
          <Route path="/crumb/sales-orders/:id" element={<SalesOrderDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SalesOrderDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a draft SO with ordered/reserved/shortage figures, flags, and Confirm + Cancel', async () => {
    mockGets('draft')

    renderSalesOrderDetail()

    // Header: SO number + status badge.
    expect(await screen.findByText('SO-000001')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()

    // Ordered qty is editable while Draft (shown as an input value); reserved & shortage as text.
    expect(screen.getByDisplayValue('8')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()

    // The shortage cell renders its value and is visually flagged (amber).
    const shortageCell = screen.getByText('2')
    expect(shortageCell).toBeInTheDocument()
    expect(shortageCell).toHaveClass('text-amber-600')

    // The non-stock (item_id null) line carries a Non-stock flag.
    expect(screen.getByText('Non-stock')).toBeInTheDocument()

    // Draft FSM actions: Confirm + Cancel (no Fulfill).
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fulfill' })).not.toBeInTheDocument()
  })

  it('shows Fulfill + Cancel for a confirmed SO', async () => {
    mockGets('confirmed')

    renderSalesOrderDetail()

    expect(await screen.findByText('SO-000001')).toBeInTheDocument()
    expect(screen.getByText('Confirmed')).toBeInTheDocument()

    // Confirmed FSM actions: Fulfill + Cancel (no Confirm).
    expect(screen.getByRole('button', { name: 'Fulfill' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  })
})
