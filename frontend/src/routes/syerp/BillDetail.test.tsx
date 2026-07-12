// ABOUTME: Component tests for the SYERP Bill detail screen + PayBillDialog (Phase 09b,
// ABOUTME: SYERP-12 AC4/AC5) — detail renders from a mocked GET, the status-driven Post
// ABOUTME: (draft) + Pay (posted) actions, the open-balance amount guard, and the pay POST.

/**
 * BillDetail — component tests.
 *
 * Mounts the detail screen at /syerp/ap/bills/:id with apiClient mocked per-endpoint
 * (bill / vendors / accounts), then asserts:
 *   1. The header (bill number + resolved vendor + total/open balance) and a line render.
 *   2. A DRAFT bill shows "Post" (and hides "Pay"); clicking it POSTs …/post.
 *   3. A POSTED bill shows "Pay" (and hides "Post").
 *   4. PayBillDialog blocks an amount above the open balance (submit disabled + error).
 *   5. A valid pay POSTs /ap/payments with the correct allocation body.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BillDetail } from '@/routes/syerp/BillDetail'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the cash/bank account Select is operable here.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

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

// Mock sonner toasts.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)

const VENDORS = [{ id: 'v1', name: 'Acme Metals', is_vendor: true }]

// 1110 Cash is the default cash account; 1111 Bank – Checking is the alternative.
const ACCOUNTS = [
  { id: 101, code: '1111', name: 'Bank – Checking', account_type: 'ASSET' },
  { id: 100, code: '1110', name: 'Cash', account_type: 'ASSET' },
  { id: 900, code: '4000', name: 'Sales Revenue', account_type: 'REVENUE' },
]

function makeBill(status: string) {
  return {
    id: 'b1',
    bill_number: 'BILL-0001',
    vendor_id: 'v1',
    vendor_invoice_ref: 'INV-42',
    status,
    memo: null,
    posted_at: status === 'draft' ? null : '2026-06-01T12:00:00Z',
    total: '72.00',
    open_balance: '50.00',
    lines: [
      {
        id: 'bl1',
        line_no: 1,
        line_type: 'matched',
        po_line_id: 'pol1',
        matched_qty: '6',
        account_id: null,
        unit_cost: '12.00',
        amount: '72.00',
      },
    ],
    created_at: '2026-06-01T12:00:00Z',
  }
}

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl(status: string) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    if (url.includes('/partners')) return Promise.resolve({ data: VENDORS })
    if (url.includes('/ap/bills/')) return Promise.resolve({ data: makeBill(status) })
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
      <MemoryRouter initialEntries={['/syerp/ap/bills/b1']}>
        <Routes>
          <Route path="/syerp/ap/bills/:id" element={<BillDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('BillDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the header + a bill line from a mocked GET', async () => {
    mockGetByUrl('posted')
    renderDetail()

    // Header: bill number + resolved vendor name
    expect(await screen.findByText('BILL-0001')).toBeInTheDocument()
    expect(screen.getByText('Acme Metals')).toBeInTheDocument()
    // Roll-ups render as exact strings (total also appears on the line, hence getAllByText)
    expect(screen.getAllByText('72.00').length).toBeGreaterThan(0)
    expect(screen.getByText('50.00')).toBeInTheDocument()
    // The matched line renders (matched_qty)
    expect(screen.getByText('6')).toBeInTheDocument()
  })

  it('shows Post (and hides Pay) for a draft bill and POSTs …/post', async () => {
    const user = userEvent.setup()
    mockGetByUrl('draft')
    mockPost.mockResolvedValue({ data: makeBill('posted') })
    renderDetail()

    expect(await screen.findByText('BILL-0001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pay' })).not.toBeInTheDocument()
    const postButton = screen.getByRole('button', { name: 'Post' })
    expect(postButton).toBeInTheDocument()

    await user.click(postButton)
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/ap/bills/b1/post')
    })
  })

  it('shows Pay (and hides Post) for a posted bill', async () => {
    mockGetByUrl('posted')
    renderDetail()

    expect(await screen.findByText('BILL-0001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Post' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pay' })).toBeInTheDocument()
  })

  it('blocks a pay amount above the open balance', async () => {
    const user = userEvent.setup()
    mockGetByUrl('posted')
    renderDetail()

    await user.click(await screen.findByRole('button', { name: 'Pay' }))
    await screen.findByRole('heading', { name: 'Pay Bill' })

    // The amount defaults to the open balance; over-pay it.
    const amount = screen.getByLabelText('Amount')
    await user.clear(amount)
    await user.type(amount, '999.00')

    expect(await screen.findByText(/cannot exceed the open balance/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Record Payment' })).toBeDisabled()
  })

  it('records a valid payment: POST /ap/payments with the correct allocation body', async () => {
    const user = userEvent.setup()
    mockGetByUrl('posted')
    mockPost.mockResolvedValue({ data: { id: 'pay1' } })
    renderDetail()

    await user.click(await screen.findByRole('button', { name: 'Pay' }))
    await screen.findByRole('heading', { name: 'Pay Bill' })

    // Amount defaults to the open balance (50.00); the account defaults to 1110 Cash.
    await user.click(screen.getByRole('button', { name: 'Record Payment' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/ap/payments',
        expect.objectContaining({
          cash_account_id: 100,
          allocations: [{ bill_id: 'b1', amount: '50.00' }],
        }),
      )
    })
  })
})
