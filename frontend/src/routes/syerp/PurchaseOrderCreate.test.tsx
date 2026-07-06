// ABOUTME: Component tests for the SYERP PurchaseOrderCreate screen (Phase 8, Task 21)
// ABOUTME: — vendor Select + a line row render, adding a line adds a row, submit is
// ABOUTME: blocked without a vendor, and a full submit POSTs the Draft PO then its line.

/**
 * PurchaseOrderCreate screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked, then asserts:
 *   1. The heading, vendor Select, and one initial line row render.
 *   2. "Add line" adds a second line row.
 *   3. "Create Draft PO" is disabled until a vendor is chosen (submit blocked).
 *   4. A complete form POSTs the PO header, then POSTs the filled line to it.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PurchaseOrderCreate } from '@/routes/syerp/PurchaseOrderCreate'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the vendor/item Selects are operable.
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

const VENDORS = [{ id: 'v1', name: 'Acme Metals' }]
const ITEMS = [
  { id: 'i1', code: 'ITEM-0001', name: 'M3 hex bolt', active: true },
  { id: 'i2', code: 'ITEM-0002', name: 'Retired washer', active: false },
]

// Route the two GETs (vendors + items) by URL so ordering does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/partners')) return Promise.resolve({ data: VENDORS })
    if (url.includes('/inventory/items')) return Promise.resolve({ data: ITEMS })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PurchaseOrderCreate />
      </MemoryRouter>
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

describe('PurchaseOrderCreate screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the heading, vendor Select, and one line row', async () => {
    mockGets()

    renderScreen()

    expect(
      screen.getByRole('heading', { name: 'Create Purchase Order' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Vendor')).toBeInTheDocument()
    expect(screen.getByLabelText('Order line 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Item for line 1')).toBeInTheDocument()
  })

  it('adds a line row when "Add line" is clicked', async () => {
    const user = userEvent.setup()
    mockGets()

    renderScreen()

    expect(screen.queryByLabelText('Order line 2')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add line' }))
    expect(screen.getByLabelText('Order line 2')).toBeInTheDocument()
  })

  it('blocks submit until a vendor is selected', async () => {
    const user = userEvent.setup()
    mockGets()

    renderScreen()
    await screen.findByRole('heading', { name: 'Create Purchase Order' })

    // No vendor yet → submit disabled even with a complete line.
    await selectOption(user, 'Item for line 1', 'ITEM-0001 — M3 hex bolt')
    await user.type(screen.getByLabelText('Qty'), '10')
    await user.type(screen.getByLabelText('Unit cost'), '2.50')
    expect(screen.getByRole('button', { name: 'Create Draft PO' })).toBeDisabled()

    // Choosing a vendor enables submit.
    await selectOption(user, 'Vendor', 'Acme Metals')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create Draft PO' })).toBeEnabled()
    })
  })

  it('POSTs the Draft PO header then the filled line on submit', async () => {
    const user = userEvent.setup()
    mockGets()
    // Header POST returns the new Draft PO; line POST resolves.
    mockPost.mockImplementation((url: string) => {
      if (url.endsWith('/purchasing/orders')) {
        return Promise.resolve({ data: { id: 'po1', po_number: 'PO-1001', status: 'draft' } })
      }
      return Promise.resolve({ data: {} })
    })

    renderScreen()
    await screen.findByRole('heading', { name: 'Create Purchase Order' })

    await selectOption(user, 'Vendor', 'Acme Metals')
    await selectOption(user, 'Item for line 1', 'ITEM-0001 — M3 hex bolt')
    await user.type(screen.getByLabelText('Qty'), '10')
    await user.type(screen.getByLabelText('Unit cost'), '2.50')

    await user.click(screen.getByRole('button', { name: 'Create Draft PO' }))

    // Header first (vendor_id), then the line (Decimals as exact strings).
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/purchasing/orders', {
        vendor_id: 'v1',
        notes: undefined,
      })
    })
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/syerp/purchasing/orders/po1/lines', {
        item_id: 'i1',
        qty_ordered: '10',
        unit_cost: '2.50',
        need_by_date: undefined,
      })
    })
  })

  it('excludes inactive items from the line item Select', async () => {
    const user = userEvent.setup()
    mockGets()

    renderScreen()
    await screen.findByRole('heading', { name: 'Create Purchase Order' })

    await user.click(screen.getByLabelText('Item for line 1'))
    const listbox = await screen.findByRole('listbox')
    expect(within(listbox).getByRole('option', { name: 'ITEM-0001 — M3 hex bolt' })).toBeInTheDocument()
    expect(within(listbox).queryByRole('option', { name: /Retired washer/ })).not.toBeInTheDocument()
  })
})
