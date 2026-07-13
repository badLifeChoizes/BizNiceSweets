// ABOUTME: Component tests for the MOUSSE WorkOrders list screen (MOUSSE-01, SC7) — the
// ABOUTME: table renders WOs from a mocked GET with the plum part resolved to its number,
// ABOUTME: and the create dialog submits a WO then refetches the invalidated list.

/**
 * WorkOrders screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked, then asserts:
 *   1. The list renders WOs from a mocked GET (number, resolved part, planned qty, status).
 *   2. Opening the create dialog and submitting POSTs /mousse/work-orders and invalidates
 *      the list query so the new WO is fetched again without a manual refresh.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WorkOrders } from '@/routes/mousse/WorkOrders'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the part / location Selects are operable.
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

const PARTS = [
  {
    id: 'p1',
    part_number: 'FG-100',
    active: true,
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

const LOCATIONS = [{ id: 7, name: 'Main Warehouse', active: true, created_at: '', updated_at: '' }]

const ORDERS = [
  {
    id: 'wo1',
    wo_number: 'WO-000001',
    plum_part_id: 'p1',
    released_revision_id: null,
    output_item_id: null,
    planned_qty: '10',
    target_location_id: 7,
    status: 'draft',
    wo_date: '2026-07-01',
    actor_id: 'u1',
    created_at: '2026-07-01T00:00:00Z',
    completed_at: null,
  },
]

// Route every GET by URL so ordering does not matter.
function mockGets(overrides: { orders?: unknown[] } = {}) {
  const orders = overrides.orders ?? ORDERS
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/mousse/work-orders')) return Promise.resolve({ data: orders })
    if (url.includes('/plum/parts')) return Promise.resolve({ data: PARTS })
    if (url.includes('/inventory/locations')) return Promise.resolve({ data: LOCATIONS })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderWorkOrders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <WorkOrders />
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

describe('WorkOrders screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders work orders from a mocked GET with the part resolved to its number', async () => {
    mockGets()

    renderWorkOrders()

    expect(screen.getByRole('heading', { name: 'Work Orders' })).toBeInTheDocument()
    expect(await screen.findByText('WO-000001')).toBeInTheDocument()
    // plum_part_id resolves to part_number client-side.
    expect(screen.getByText('FG-100')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })

  it('creates a work order from the dialog and refetches the invalidated list', async () => {
    const user = userEvent.setup()
    mockGets({ orders: [] })
    mockPost.mockResolvedValue({ data: { id: 'wo-new', wo_number: 'WO-000002' } })

    renderWorkOrders()

    // Empty state before creating.
    expect(await screen.findByText('No work orders yet')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Create Work Order' }))
    await screen.findByRole('heading', { name: 'New Work Order' })

    await selectOption(user, 'Part', 'FG-100')
    await user.type(screen.getByLabelText('Planned qty'), '10')
    await selectOption(user, 'Target location', 'Main Warehouse')

    // Once the list is invalidated the server returns the freshly-created WO.
    mockGets({ orders: ORDERS })

    // The dialog's submit button; the toolbar button shares the "Create Work Order" name,
    // so scope the click to the open dialog.
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Create Work Order' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders', {
        plum_part_id: 'p1',
        planned_qty: '10',
        target_location_id: 7,
      })
    })

    // Invalidation refetches the list → the new WO appears without a manual refresh.
    expect(await screen.findByText('WO-000001')).toBeInTheDocument()
  })
})
