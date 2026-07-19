// ABOUTME: Component tests for the SYERP Invoices screen + InvoiceCreateDialog (Phase 13,
// ABOUTME: SYERP-13) — list rows render from a mocked GET, and the create dialog picks a
// ABOUTME: shipment line (read-only locked price) then POSTs the InvoiceCreate body shape.

/**
 * Invoices screen — component tests.
 *
 * Mounts the screen with apiClient mocked, then asserts:
 *   1. The list renders invoices from a mocked GET (number, resolved customer, status, total).
 *   2. Opening the dialog and selecting a customer loads its uninvoiced shipment lines.
 *   3. The picker renders uninvoiced_qty and the READ-ONLY locked SO unit price.
 *   4. Checking a line + submitting POSTs /ar/invoices with the correct InvoiceCreate shape.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Invoices } from '@/routes/syerp/Invoices'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the customer Select is operable here.
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
const mockPost = vi.mocked(apiClient.post)

const CUSTOMERS = [{ id: 'c1', name: 'Globex Health', is_customer: true }]

const SHIPMENTS = [
  {
    sales_order_line_id: 'sol1',
    so_number: 'SO-2001',
    item_id: 'i1',
    item_label: 'ITEM-0001 — Reservoir Cartridge',
    description: null,
    uninvoiced_qty: '4',
    unit_price: '18.50',
  },
]

const INVOICES = [
  {
    id: 'inv1',
    invoice_number: 'INV-0001',
    customer_id: 'c1',
    sales_order_id: 'so1',
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

// Route every GET by URL so ordering does not matter.
function mockGets(overrides: { invoices?: unknown[]; shipments?: unknown[] } = {}) {
  const invoices = overrides.invoices ?? INVOICES
  const shipments = overrides.shipments ?? SHIPMENTS
  mockGet.mockImplementation((url: string) => {
    if (url.includes('uninvoiced-shipments')) return Promise.resolve({ data: shipments })
    if (url.includes('/ar/invoices')) return Promise.resolve({ data: invoices })
    if (url.includes('/partners')) return Promise.resolve({ data: CUSTOMERS })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderInvoices() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Invoices />
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

describe('Invoices screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders invoices from a mocked GET with resolved customer, status, and total', async () => {
    mockGets()

    renderInvoices()

    expect(screen.getByRole('heading', { name: 'Invoices' })).toBeInTheDocument()
    expect(await screen.findByText('INV-0001')).toBeInTheDocument()
    expect(screen.getByText('Globex Health')).toBeInTheDocument()
    expect(screen.getByText('Posted')).toBeInTheDocument()
    expect(screen.getAllByText('74.00').length).toBeGreaterThan(0)
  })

  it('picker renders uninvoiced_qty + read-only locked price, then POSTs InvoiceCreate', async () => {
    const user = userEvent.setup()
    mockGets({ invoices: [] })
    mockPost.mockResolvedValue({ data: { id: 'inv-new' } })

    renderInvoices()

    // Open the dialog and select a customer → uninvoiced shipments load.
    await user.click(screen.getByRole('button', { name: 'New invoice' }))
    await screen.findByRole('heading', { name: 'New Invoice' })

    // The optional invoice-date field renders, defaulted to today (server aging basis).
    expect(screen.getByLabelText('Invoice date')).toBeInTheDocument()

    await selectOption(user, 'Customer', 'Globex Health')

    // The picker shows the uninvoiced shipped qty and the READ-ONLY locked SO unit price.
    const lineCheckbox = await screen.findByLabelText('Invoice line SO-2001')
    expect(lineCheckbox).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument() // uninvoiced_qty
    // Unit price is rendered read-only (a span, not an editable input) locked to SO price.
    const priceCell = screen.getByLabelText('Unit price SO-2001')
    expect(priceCell.tagName).toBe('SPAN')
    expect(priceCell).toHaveTextContent('18.50')

    // Check the line — its invoice qty defaults to the full uninvoiced qty (4).
    await user.click(lineCheckbox)
    const qtyInput = screen.getByLabelText('Invoice qty SO-2001') as HTMLInputElement
    expect(qtyInput.value).toBe('4')

    // Submit → POST /ar/invoices with the exact InvoiceCreate body shape.
    await user.click(screen.getByRole('button', { name: 'Create Invoice' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/ar/invoices', {
        customer_id: 'c1',
        invoice_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        lines: [{ sales_order_line_id: 'sol1', invoiced_qty: '4' }],
      })
    })
  })
})
