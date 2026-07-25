// ABOUTME: Component tests for the MOUSSE WorkOrderDetail screen (MOUSSE-01, SC7) — the
// ABOUTME: snapshot component lines render with on_hand/issued_so_far, and the Issue and
// ABOUTME: Complete actions POST the right requests and invalidate the detail + list queries.

/**
 * WorkOrderDetail — component tests.
 *
 * Mounts the detail screen at /mousse/work-orders/:id with apiClient + sonner mocked, then
 * asserts:
 *   1. The header + snapshot component lines render (required / on hand / issued so far).
 *   2. Issuing components POSTs …/issue and invalidates the detail + list queries.
 *   3. Completing a fully-issued WO POSTs …/complete { override_incomplete: false } and
 *      invalidates the detail + list queries.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WorkOrderDetail } from '@/routes/mousse/WorkOrderDetail'
import { workOrderKey, workOrdersKey } from '@/routes/mousse/hooks'

// Radix Dialog/Select rely on Pointer Events + scrollIntoView, which jsdom lacks. Stub them.
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
  { id: 'cp1', part_number: 'CMP-A', active: true, tags: [], created_at: '', updated_at: '' },
  { id: 'cp2', part_number: 'CMP-B', active: true, tags: [], created_at: '', updated_at: '' },
  { id: 'fg1', part_number: 'FG-100', active: true, tags: [], created_at: '', updated_at: '' },
]

// issuedSoFar controls whether the lines are under- or fully-issued.
function makeWorkOrder(status: string, issuedSoFar: [string, string]) {
  return {
    id: 'wo1',
    wo_number: 'WO-000001',
    plum_part_id: 'fg1',
    released_revision_id: 'rev1',
    output_item_id: 'i-fg',
    planned_qty: '10',
    target_location_id: 7,
    status,
    wo_date: '2026-07-01',
    actor_id: 'u1',
    created_at: '2026-07-01T00:00:00Z',
    completed_at: null,
    components: [
      {
        id: 'c1',
        work_order_id: 'wo1',
        child_part_id: 'cp1',
        item_id: 'i1',
        qty_per: '2',
        qty_required: '20',
        unit_of_measure: 'ea',
        sort_order: 0,
        on_hand: '100',
        issued_so_far: issuedSoFar[0],
      },
      {
        id: 'c2',
        work_order_id: 'wo1',
        child_part_id: 'cp2',
        item_id: 'i2',
        qty_per: '1',
        qty_required: '10',
        unit_of_measure: 'ea',
        sort_order: 1,
        on_hand: '50',
        issued_so_far: issuedSoFar[1],
      },
    ],
  }
}

// Route the mocked GET by URL so query order doesn't matter.
function mockGetByUrl(wo: ReturnType<typeof makeWorkOrder>) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/mousse/work-orders/')) return Promise.resolve({ data: wo })
    if (url.includes('/plum/parts')) return Promise.resolve({ data: PARTS })
    // The issue dialog's useBins query (Phase 4, Task 12) — no bins here, so the
    // per-line bin pickers stay hidden and issue lines carry bin_id: null.
    if (url.includes('/bins')) return Promise.resolve({ data: [] })
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
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/mousse/work-orders/wo1']}>
        <Routes>
          <Route path="/mousse/work-orders/:id" element={<WorkOrderDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { queryClient, ...utils }
}

describe('WorkOrderDetail screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the header + snapshot lines with on_hand and issued_so_far', async () => {
    mockGetByUrl(makeWorkOrder('in_progress', ['4', '0']))
    renderDetail()

    // Header: WO number + resolved part name + status.
    expect(await screen.findByText('WO-000001')).toBeInTheDocument()
    expect(screen.getByText('In progress')).toBeInTheDocument()

    // Component lines resolve child_part_id → part_number.
    expect(screen.getByText('CMP-A')).toBeInTheDocument()
    expect(screen.getByText('CMP-B')).toBeInTheDocument()
    // on_hand + issued_so_far figures render.
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    // Both lines are under-issued (issued < required) → flagged "Short".
    expect(screen.getAllByText('Short')).toHaveLength(2)
  })

  it('issues components: POSTs …/issue and invalidates the detail + list queries', async () => {
    const user = userEvent.setup()
    mockGetByUrl(makeWorkOrder('in_progress', ['0', '0']))
    mockPost.mockResolvedValue({ data: {} })

    const { queryClient } = renderDetail()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await screen.findByText('WO-000001')
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    // The dialog submit button shares the header button's name — scope to the dialog.
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [
          { component_id: 'c1', quantity: '20', bin_id: null },
          { component_id: 'c2', quantity: '10', bin_id: null },
        ],
      })
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: workOrderKey('wo1') })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: workOrdersKey })
    })
  })

  it('completes a fully-issued WO: POSTs …/complete and invalidates the queries', async () => {
    const user = userEvent.setup()
    // Fully issued (issued == required) → no override checkbox required.
    mockGetByUrl(makeWorkOrder('in_progress', ['20', '10']))
    mockPost.mockResolvedValue({
      data: {
        work_order_id: 'wo1',
        output_item_id: 'i-fg',
        quantity_received: '10',
        wip_cleared_value: '120.00',
        completed_at: '2026-07-02T00:00:00Z',
      },
    })

    const { queryClient } = renderDetail()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    await screen.findByText('WO-000001')
    await user.click(screen.getByRole('button', { name: 'Complete' }))

    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Complete Work Order' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/complete', {
        override_incomplete: false,
      })
    })

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: workOrderKey('wo1') })
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: workOrdersKey })
    })
  })
})
