// ABOUTME: Component tests for RecordReceiptDialog (Phase 13, SYERP-13) — the cash account
// ABOUTME: defaults to code 1110, open invoices are allocatable, and a full submit POSTs the
// ABOUTME: ArReceiptCreate body ({receipt_date, cash_account_id, allocations:[{invoice_id, amount}]}).

/**
 * RecordReceiptDialog — component tests.
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. The cash/bank account defaults to the 1110 (Cash) option once accounts load.
 *   2. Checking an open invoice defaults its allocation to the full open balance.
 *   3. A complete submit POSTs /ar/receipts with the exact ArReceiptCreate shape.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RecordReceiptDialog } from '@/routes/syerp/components/RecordReceiptDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the cash/bank account Select is operable.
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

// Mock sonner toasts so nothing throws in jsdom.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)

// 1110 Cash is the default cash account; 1111 Bank – Checking is the alternative.
const ACCOUNTS = [
  { id: 101, code: '1111', name: 'Bank – Checking', account_type: 'ASSET' },
  { id: 100, code: '1110', name: 'Cash', account_type: 'ASSET' },
  { id: 900, code: '4000', name: 'Sales Revenue', account_type: 'REVENUE' },
]

const INVOICES = [
  {
    id: 'inv1',
    invoice_number: 'INV-0001',
    customer_id: 'c1',
    sales_order_id: null,
    invoice_date: '2026-06-01',
    status: 'posted',
    memo: null,
    posted_at: '2026-06-01T12:00:00Z',
    total: '74.00',
    open_balance: '74.00',
    lines: [],
    created_at: '2026-06-01T12:00:00Z',
  },
]

function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    if (url.includes('/ar/invoices')) return Promise.resolve({ data: INVOICES })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <RecordReceiptDialog open={true} onOpenChange={vi.fn()} onSuccess={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('RecordReceiptDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('defaults the cash account to 1110 and lists open invoices', async () => {
    mockGets()

    renderDialog()

    // The account Select resolves to the 1110 (Cash) label by default.
    expect(await screen.findByText('1110 — Cash')).toBeInTheDocument()
    // The open invoice is offered for allocation.
    expect(screen.getByLabelText('Allocate to INV-0001')).toBeInTheDocument()
  })

  it('POSTs ArReceiptCreate with the allocation shape and the 1110 account default', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValue({ data: { id: 'rcpt1' } })

    renderDialog()

    // Wait for the default account to settle to 1110 (id 100).
    await screen.findByText('1110 — Cash')

    // Check the invoice — its allocation defaults to the full open balance (74.00).
    const checkbox = screen.getByLabelText('Allocate to INV-0001')
    await user.click(checkbox)
    const amountInput = screen.getByLabelText('Allocation amount INV-0001') as HTMLInputElement
    expect(amountInput.value).toBe('74.00')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Record Receipt' })).toBeEnabled(),
    )
    await user.click(screen.getByRole('button', { name: 'Record Receipt' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/ar/receipts', {
        receipt_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        cash_account_id: 100,
        allocations: [{ invoice_id: 'inv1', amount: '74.00' }],
      })
    })
  })
})
