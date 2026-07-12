// ABOUTME: Component tests for the SYERP Bills screen + BillCreateDialog (Phase 09b,
// ABOUTME: SYERP-12 AC4) — list rows render from a mocked GET, and the create dialog
// ABOUTME: matches an unbilled receipt + a non-PO line then POSTs the correct body shape.

/**
 * Bills screen — component tests.
 *
 * Mounts the screen with apiClient mocked, then asserts:
 *   1. The list renders bills from a mocked GET (number, resolved vendor, status, total).
 *   2. Opening the dialog and selecting a vendor loads its unbilled receipt lines.
 *   3. Checking an unbilled line adds it to the POST payload (matched line).
 *   4. A non-PO expense line can be added and filled.
 *   5. Submit calls POST /ap/bills with the correct { vendor_id, lines: [...] } shape.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Bills } from '@/routes/syerp/Bills'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the vendor / account Selects are operable here.
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

const ACCOUNTS = [
  { id: 500, code: '6000', name: 'Office Supplies', account_type: 'EXPENSE' },
  { id: 100, code: '1000', name: 'Cash', account_type: 'ASSET' },
  { id: 900, code: '4000', name: 'Sales Revenue', account_type: 'REVENUE' },
]

const UNBILLED = [
  { po_line_id: 'pol1', po_number: 'PO-1001', item_id: 'i1', unbilled_qty: '6', unit_cost: '12.00' },
]

const BILLS = [
  {
    id: 'b1',
    bill_number: 'BILL-0001',
    vendor_id: 'v1',
    vendor_invoice_ref: 'INV-42',
    status: 'posted',
    memo: null,
    posted_at: '2026-06-01T12:00:00Z',
    total: '72.00',
    open_balance: '50.00',
    lines: [],
    created_at: '2026-06-01T12:00:00Z',
  },
]

// Route every GET by URL so ordering does not matter.
function mockGets(overrides: { bills?: unknown[]; unbilled?: unknown[] } = {}) {
  const bills = overrides.bills ?? BILLS
  const unbilled = overrides.unbilled ?? UNBILLED
  mockGet.mockImplementation((url: string) => {
    if (url.includes('unbilled-receipts')) return Promise.resolve({ data: unbilled })
    if (url.includes('/ap/bills')) return Promise.resolve({ data: bills })
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    if (url.includes('/partners')) return Promise.resolve({ data: VENDORS })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderBills() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Bills />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Pick an option from a Radix Select by its accessible name.
async function selectOption(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  option: string,
) {
  await user.click(screen.getByLabelText(label))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: option }))
}

describe('Bills screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders bills from a mocked GET with resolved vendor, status, and total', async () => {
    mockGets()

    renderBills()

    expect(screen.getByRole('heading', { name: 'Bills' })).toBeInTheDocument()
    expect(await screen.findByText('BILL-0001')).toBeInTheDocument()
    expect(screen.getByText('Acme Metals')).toBeInTheDocument()
    expect(screen.getByText('Posted')).toBeInTheDocument()
    expect(screen.getByText('72.00')).toBeInTheDocument()
    expect(screen.getByText('50.00')).toBeInTheDocument()
  })

  it('opens the dialog, matches an unbilled line + a non-PO line, and POSTs the right body', async () => {
    const user = userEvent.setup()
    mockGets({ bills: [] })
    mockPost.mockResolvedValue({ data: { id: 'b-new' } })

    renderBills()

    // (2) Open the dialog and select a vendor → unbilled receipts load.
    await user.click(screen.getByRole('button', { name: 'New bill' }))
    await screen.findByRole('heading', { name: 'New Bill' })

    // The optional bill-date field renders, defaulted to today (server aging basis).
    expect(screen.getByLabelText('Bill date')).toBeInTheDocument()

    await selectOption(user, 'Vendor', 'Acme Metals')

    // Unbilled receipt line for the vendor appears with a "bill this line" checkbox.
    const lineCheckbox = await screen.findByLabelText('Bill line PO-1001')
    expect(lineCheckbox).toBeInTheDocument()

    // (3) Check the unbilled line — it will be posted as a matched line.
    await user.click(lineCheckbox)

    // Optional vendor invoice ref.
    await user.type(screen.getByLabelText('Vendor invoice ref'), 'INV-9')

    // (4) Add a non-PO expense line, pick an EXPENSE account, enter an amount.
    await user.click(screen.getByRole('button', { name: 'Add non-PO line' }))
    await selectOption(user, 'Non-PO line 1 account', '6000 — Office Supplies')
    await user.type(screen.getByLabelText('Non-PO line 1 amount'), '25.00')

    // (5) Submit → POST /ap/bills with the exact body shape.
    await user.click(screen.getByRole('button', { name: 'Create Bill' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/ap/bills', {
        vendor_id: 'v1',
        vendor_invoice_ref: 'INV-9',
        bill_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        lines: [
          { line_type: 'matched', po_line_id: 'pol1', matched_qty: '6' },
          { line_type: 'expense', account_id: 500, amount: '25.00' },
        ],
      })
    })
  })

  it('omits REVENUE accounts from the non-PO account Select', async () => {
    const user = userEvent.setup()
    mockGets({ bills: [] })

    renderBills()

    await user.click(screen.getByRole('button', { name: 'New bill' }))
    await screen.findByRole('heading', { name: 'New Bill' })
    await user.click(screen.getByRole('button', { name: 'Add non-PO line' }))

    await user.click(screen.getByLabelText('Non-PO line 1 account'))
    const listbox = await screen.findByRole('listbox')
    // EXPENSE + ASSET are offered; REVENUE is filtered out.
    expect(within(listbox).getByRole('option', { name: '6000 — Office Supplies' })).toBeInTheDocument()
    expect(within(listbox).getByRole('option', { name: '1000 — Cash' })).toBeInTheDocument()
    expect(within(listbox).queryByRole('option', { name: '4000 — Sales Revenue' })).toBeNull()
  })
})
