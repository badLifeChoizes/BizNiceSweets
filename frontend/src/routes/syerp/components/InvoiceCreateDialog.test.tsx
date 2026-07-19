// ABOUTME: Component tests for InvoiceCreateDialog (Phase 13, SYERP-13) — the shipment picker
// ABOUTME: renders uninvoiced_qty + a READ-ONLY locked SO price, and a full submit POSTs the
// ABOUTME: InvoiceCreate body ({customer_id, invoice_date, lines:[{sales_order_line_id, qty}]}).

/**
 * InvoiceCreateDialog — component tests.
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. Selecting a customer loads its uninvoiced shipments; the picker renders the real
 *      payload's uninvoiced_qty and the read-only locked unit_price.
 *   2. The invoiced-qty input defaults to the full uninvoiced_qty and is editable.
 *   3. A complete submit POSTs /ar/invoices with the exact InvoiceCreate shape.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InvoiceCreateDialog } from '@/routes/syerp/components/InvoiceCreateDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the customer Select is operable.
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

const CUSTOMERS = [{ id: 'c1', name: 'Globex Health' }]

// The REAL UninvoicedShipmentRead payload shape from GET /ar/uninvoiced-shipments.
const SHIPMENTS = [
  {
    sales_order_line_id: 'sol1',
    so_number: 'SO-2001',
    item_id: 'i1',
    description: null,
    uninvoiced_qty: '4',
    unit_price: '18.50',
  },
]

function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: CUSTOMERS })
    if (url.includes('/uninvoiced-shipments')) return Promise.resolve({ data: SHIPMENTS })
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
      <InvoiceCreateDialog open={true} onOpenChange={vi.fn()} onSuccess={vi.fn()} />
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

describe('InvoiceCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the shipment picker with uninvoiced_qty and a read-only locked price', async () => {
    const user = userEvent.setup()
    mockGets()

    renderDialog()

    await selectOption(user, 'Customer', 'Globex Health')

    // The uninvoiced shipped qty renders from the real payload.
    expect(await screen.findByText('4')).toBeInTheDocument()

    // The unit price is READ-ONLY — a span locked to the SO line price, never an input.
    const priceCell = screen.getByLabelText('Unit price SO-2001')
    expect(priceCell.tagName).toBe('SPAN')
    expect(priceCell).toHaveTextContent('18.50')
  })

  it('defaults the invoice qty to the full uninvoiced qty and POSTs InvoiceCreate', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValue({ data: { id: 'inv1' } })

    renderDialog()

    await selectOption(user, 'Customer', 'Globex Health')

    // Check the line — invoiced qty defaults to the full uninvoiced qty (4).
    const lineCheckbox = await screen.findByLabelText('Invoice line SO-2001')
    await user.click(lineCheckbox)
    const qtyInput = screen.getByLabelText('Invoice qty SO-2001') as HTMLInputElement
    expect(qtyInput.value).toBe('4')

    // Edit it to a partial quantity.
    await user.clear(qtyInput)
    await user.type(qtyInput, '3')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Create Invoice' })).toBeEnabled(),
    )
    await user.click(screen.getByRole('button', { name: 'Create Invoice' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/ar/invoices',
        expect.objectContaining({
          customer_id: 'c1',
          lines: [{ sales_order_line_id: 'sol1', invoiced_qty: '3' }],
        }),
      )
    })
  })
})
