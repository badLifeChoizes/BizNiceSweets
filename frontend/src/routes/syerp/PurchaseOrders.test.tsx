// ABOUTME: Component tests for the SYERP Purchase Orders screen — heading, a PO
// ABOUTME: row rendering status badge + total + resolved vendor name, and the
// ABOUTME: vendor filter Select over /api/v1/syerp/purchasing/orders.

/**
 * PurchaseOrders screen — component tests.
 *
 * Mounts the screen with apiClient.get mocked, then asserts:
 *   1. The "Purchase Orders" heading and "Create PO" button render
 *   2. A PO row shows its number, resolved vendor name, status badge, and total
 *   3. The vendor filter Select is present (AC11-3 narrowing surface)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PurchaseOrders } from '@/routes/syerp/PurchaseOrders'

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

function renderPurchaseOrders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PurchaseOrders />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Route the two GETs (vendors + orders) by URL so ordering does not matter.
function mockGets(vendors: unknown[], orders: unknown[]) {
  mockApiClientGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: vendors })
    if (url.includes('/purchasing/orders')) return Promise.resolve({ data: orders })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

describe('PurchaseOrders screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the heading, Create PO button, and vendor filter with empty state', async () => {
    mockGets([], [])

    renderPurchaseOrders()

    expect(screen.getByRole('heading', { name: 'Purchase Orders' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create PO' })).toBeInTheDocument()
    // Vendor filter Select is present (AC11-3 narrowing surface).
    expect(screen.getByLabelText('Filter by vendor')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('No purchase orders yet')).toBeInTheDocument()
    })
  })

  it('renders a PO row with status badge, total, and resolved vendor name', async () => {
    mockGets(
      [{ id: 'v1', name: 'Acme Metals' }],
      [
        {
          id: 'po1',
          po_number: 'PO-1001',
          vendor_id: 'v1',
          status: 'partially_received',
          notes: null,
          approved_at: null,
          created_at: '2026-06-01T12:00:00Z',
          updated_at: '2026-06-01T12:00:00Z',
          total: '1234.56',
          total_ordered_qty: '10',
          total_received_qty: '4',
          outstanding_qty: '6',
        },
      ],
    )

    renderPurchaseOrders()

    // PO number, resolved vendor name, status label, and exact Decimal total.
    expect(await screen.findByText('PO-1001')).toBeInTheDocument()
    expect(screen.getByText('Acme Metals')).toBeInTheDocument()
    expect(screen.getByText('Partially received')).toBeInTheDocument()
    expect(screen.getByText('1234.56')).toBeInTheDocument()
  })
})
