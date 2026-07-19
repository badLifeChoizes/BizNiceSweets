// ABOUTME: Component tests for the SYERP Invoice detail screen (Phase 13, SYERP-13) — the
// ABOUTME: header + lines render from a mocked GET, the open balance shows, Post is visible on
// ABOUTME: a draft (and POSTs …/post) and hidden once posted.

/**
 * InvoiceDetail — component tests.
 *
 * Mounts the detail screen at /syerp/ar/invoices/:id with apiClient mocked per-endpoint
 * (invoice / customers), then asserts:
 *   1. The header (invoice number + resolved customer + total/open balance) and a line render.
 *   2. A DRAFT invoice shows "Post"; clicking it POSTs …/post.
 *   3. A POSTED invoice hides "Post" and renders the open balance.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InvoiceDetail } from '@/routes/syerp/InvoiceDetail'

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

// Mock sonner toasts.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)

const CUSTOMERS = [{ id: 'c1', name: 'Globex Health', is_customer: true }]

function makeInvoice(status: string) {
  return {
    id: 'inv1',
    invoice_number: 'INV-0001',
    customer_id: 'c1',
    sales_order_id: 'so1',
    invoice_date: '2026-06-01',
    status,
    memo: null,
    posted_at: status === 'draft' ? null : '2026-06-01T12:00:00Z',
    total: '74.00',
    open_balance: '74.00',
    lines: [
      {
        id: 'il1',
        line_no: 1,
        sales_order_line_id: 'sol1',
        invoiced_qty: '4',
        unit_price: '18.50',
        amount: '74.00',
      },
    ],
    created_at: '2026-06-01T12:00:00Z',
  }
}

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl(status: string) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: CUSTOMERS })
    if (url.includes('/ar/invoices/')) return Promise.resolve({ data: makeInvoice(status) })
    return Promise.reject(new Error(`unexpected GET ${url}`))
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
      <MemoryRouter initialEntries={['/syerp/ar/invoices/inv1']}>
        <Routes>
          <Route path="/syerp/ar/invoices/:id" element={<InvoiceDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InvoiceDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the header + a line + the open balance from a mocked GET', async () => {
    mockGetByUrl('posted')
    renderDetail()

    // Header: invoice number + resolved customer name
    expect(await screen.findByText('INV-0001')).toBeInTheDocument()
    expect(screen.getByText('Globex Health')).toBeInTheDocument()
    // Open balance renders as an exact string.
    expect(screen.getAllByText('74.00').length).toBeGreaterThan(0)
    // The line renders (invoiced_qty + locked unit price).
    expect(screen.getByText('18.50')).toBeInTheDocument()
  })

  it('shows Post for a draft invoice and POSTs …/post', async () => {
    const user = userEvent.setup()
    mockGetByUrl('draft')
    mockPost.mockResolvedValue({ data: makeInvoice('posted') })
    renderDetail()

    expect(await screen.findByText('INV-0001')).toBeInTheDocument()
    const postButton = screen.getByRole('button', { name: 'Post' })
    expect(postButton).toBeInTheDocument()

    await user.click(postButton)
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/ar/invoices/inv1/post')
    })
  })

  it('hides Post once the invoice is posted', async () => {
    mockGetByUrl('posted')
    renderDetail()

    expect(await screen.findByText('INV-0001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Post' })).not.toBeInTheDocument()
  })
})
