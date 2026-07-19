// ABOUTME: Component tests for the SYERP Receipts screen (Phase 13, SYERP-13) — recorded
// ABOUTME: receipts render from a mocked GET with the cash account + allocations resolved to
// ABOUTME: invoice numbers, and the "Record receipt" button opens RecordReceiptDialog.

/**
 * Receipts screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GETs routed by URL), then asserts:
 *   1. The list renders receipts (date, resolved cash account, reference, amount).
 *   2. Each receipt's allocations resolve invoice_id → invoice_number with the amount.
 *   3. The "Record receipt" button opens the dialog.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Receipts } from '@/routes/syerp/Receipts'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the dialog's account Select is operable here.
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

// Mock sonner toasts.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

const ACCOUNTS = [{ id: 100, code: '1110', name: 'Cash', account_type: 'ASSET' }]

const INVOICES = [
  {
    id: 'inv1',
    invoice_number: 'INV-0001',
    customer_id: 'c1',
    sales_order_id: null,
    invoice_date: '2026-06-01',
    status: 'paid',
    memo: null,
    posted_at: '2026-06-01T12:00:00Z',
    total: '74.00',
    open_balance: '0.00',
    lines: [],
    created_at: '2026-06-01T12:00:00Z',
  },
]

const RECEIPTS = [
  {
    id: 'rcpt1',
    receipt_date: '2026-06-15',
    cash_account_id: 100,
    amount: '74.00',
    reference: 'CHK-880',
    allocations: [{ invoice_id: 'inv1', amount: '74.00' }],
    created_at: '2026-06-15T09:00:00Z',
  },
]

function mockGets(overrides: { receipts?: unknown[] } = {}) {
  const receipts = overrides.receipts ?? RECEIPTS
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/ar/receipts')) return Promise.resolve({ data: receipts })
    if (url.includes('/ar/invoices')) return Promise.resolve({ data: INVOICES })
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderReceipts() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Receipts />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Receipts screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders receipts with the resolved account, amount, and allocations', async () => {
    mockGets()

    renderReceipts()

    expect(screen.getByRole('heading', { name: 'Receipts' })).toBeInTheDocument()
    // Amount + reference render.
    expect(await screen.findByText('74.00')).toBeInTheDocument()
    expect(screen.getByText('CHK-880')).toBeInTheDocument()
    // cash_account_id → code/name.
    expect(screen.getByText('1110 — Cash')).toBeInTheDocument()
    // Allocation invoice_id → invoice_number.
    expect(screen.getByText('INV-0001')).toBeInTheDocument()
  })

  it('opens the Record receipt dialog', async () => {
    const user = userEvent.setup()
    mockGets({ receipts: [] })

    renderReceipts()

    await user.click(screen.getByRole('button', { name: 'Record receipt' }))
    expect(await screen.findByRole('heading', { name: 'Record Receipt' })).toBeInTheDocument()
  })
})
