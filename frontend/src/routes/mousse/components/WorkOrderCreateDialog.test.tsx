// ABOUTME: Component tests for the MOUSSE WorkOrderCreateDialog (MOUSSE-01, SC7) — the
// ABOUTME: part/qty/location form POSTs the correct { plum_part_id, planned_qty,
// ABOUTME: target_location_id } body and invalidates the work-order list on success.

/**
 * WorkOrderCreateDialog — component tests.
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. A complete submit (part + planned qty + target location) POSTs to
 *      /mousse/work-orders with the exact body shape.
 *   2. On success the work-order list query (['mousse','work-orders']) is invalidated.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WorkOrderCreateDialog } from '@/routes/mousse/components/WorkOrderCreateDialog'
import { workOrdersKey } from '@/routes/mousse/hooks'

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

// Mock sonner toasts so nothing throws in jsdom.
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

const LOCATIONS = [
  { id: 7, name: 'Main Warehouse', active: true, created_at: '', updated_at: '' },
  { id: 8, name: 'Archived Bay', active: false, created_at: '', updated_at: '' },
]

// Route the GETs (parts + locations) by URL so ordering does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/plum/parts')) return Promise.resolve({ data: PARTS })
    if (url.includes('/inventory/locations')) return Promise.resolve({ data: LOCATIONS })
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
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <WorkOrderCreateDialog open={true} onOpenChange={vi.fn()} />
    </QueryClientProvider>,
  )
  return { queryClient, ...utils }
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

describe('WorkOrderCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('POSTs the right body and invalidates the work-order list on submit', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValue({ data: { id: 'wo-new', wo_number: 'WO-000001' } })

    const { queryClient } = renderDialog()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    // Part (required) — from GET /plum/parts.
    await selectOption(user, 'Part', 'FG-100')

    // Planned qty — a positive Decimal kept as a string and sent verbatim.
    await user.type(screen.getByLabelText('Planned qty'), '10')

    // Target location (required) — only active locations are offered.
    await selectOption(user, 'Target location', 'Main Warehouse')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Create Work Order' })).toBeEnabled(),
    )
    await user.click(screen.getByRole('button', { name: 'Create Work Order' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders', {
        plum_part_id: 'p1',
        planned_qty: '10',
        target_location_id: 7,
      })
    })

    // On success the list query is invalidated so the new WO shows without a refresh.
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: workOrdersKey })
    })
  })

  it('omits inactive locations from the target-location Select', async () => {
    const user = userEvent.setup()
    mockGets()

    renderDialog()

    await user.click(screen.getByLabelText('Target location'))
    const listbox = await screen.findByRole('listbox')
    expect(within(listbox).getByRole('option', { name: 'Main Warehouse' })).toBeInTheDocument()
    expect(within(listbox).queryByRole('option', { name: 'Archived Bay' })).toBeNull()
  })
})
