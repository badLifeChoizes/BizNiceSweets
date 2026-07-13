// ABOUTME: Component tests for BillCreateDialog (Phase 09c, SYERP-12 AC6 / D-P9c-1) — the
// ABOUTME: optional bill-date field renders defaulted to today, and a full submit includes
// ABOUTME: the chosen bill_date in the POST /ap/bills body (the AP-aging date basis).

/**
 * BillCreateDialog — bill-date field tests (Phase 09c).
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. The "Bill date" field renders, defaulted to today (YYYY-MM-DD).
 *   2. A complete submit (vendor + one non-PO expense line) POSTs to /ap/bills with the
 *      chosen bill_date in the body — the field flows through to the server.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BillCreateDialog } from '@/routes/syerp/components/BillCreateDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the vendor / account Selects are operable.
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

const VENDORS = [{ id: 'v1', name: 'Acme Metals' }]
const ACCOUNTS = [
  { id: 5100, code: '5100', name: 'Office Supplies', account_type: 'EXPENSE' },
]

// Route the GETs (vendors + gl accounts + unbilled receipts) by URL so ordering does
// not matter. The dialog loads vendors + accounts on open; unbilled receipts only once
// a vendor is picked.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: VENDORS })
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    if (url.includes('/unbilled-receipts')) return Promise.resolve({ data: [] })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

// Today as YYYY-MM-DD in the local timezone — mirrors the dialog's own default so the
// assertion tracks the component rather than duplicating its date math incorrectly.
function todayISO(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
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
      <BillCreateDialog open={true} onOpenChange={vi.fn()} onSuccess={vi.fn()} />
    </QueryClientProvider>,
  )
}

// Pick an option from a Radix Select by its accessible name.
async function selectOption(
  user: ReturnType<typeof userEvent.setup>,
  triggerLabel: string,
  option: string,
) {
  await user.click(screen.getByLabelText(triggerLabel))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: option }))
}

describe('BillCreateDialog — bill date field', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the bill-date field defaulted to today', async () => {
    mockGets()

    renderDialog()

    const billDate = (await screen.findByLabelText('Bill date')) as HTMLInputElement
    expect(billDate).toBeInTheDocument()
    expect(billDate.type).toBe('date')
    expect(billDate.value).toBe(todayISO())
  })

  it('includes the chosen bill_date in the POST /ap/bills body on submit', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValue({ data: { id: 'bill1' } })

    renderDialog()

    // Vendor (required) — enables the unbilled-receipts load and satisfies canSubmit.
    await selectOption(user, 'Vendor', 'Acme Metals')

    // Pick a specific bill date distinct from today so the assertion is unambiguous.
    const billDate = await screen.findByLabelText('Bill date')
    await user.clear(billDate)
    await user.type(billDate, '2026-03-15')

    // One non-PO expense line gives the bill a line so submit is allowed.
    await user.click(screen.getByRole('button', { name: 'Add non-PO line' }))
    await selectOption(user, 'Non-PO line 1 account', '5100 — Office Supplies')
    await user.type(screen.getByLabelText('Non-PO line 1 amount'), '42.00')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Create Bill' })).toBeEnabled(),
    )
    await user.click(screen.getByRole('button', { name: 'Create Bill' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/ap/bills',
        expect.objectContaining({ vendor_id: 'v1', bill_date: '2026-03-15' }),
      )
    })
  })
})
