// ABOUTME: Component tests for the MOUSSE IssueComponentsDialog (MOUSSE-01, SC7; per-line
// ABOUTME: bin picker Phase 4, Task 12) — checked lines POST /mousse/work-orders/{id}/issue
// ABOUTME: with { lines: [{ component_id, quantity, bin_id: <n> | null }] } (D-P4-1).

/**
 * IssueComponentsDialog — component tests.
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. Lines seed to their remaining (qty_required − issued_so_far) and submit POSTs the
 *      exact { lines: [{ component_id, quantity, bin_id }] } body to …/issue — with
 *      bin_id: null while the per-line pickers sit on their "Unbinned pool" default.
 *   2. On success the onSuccess callback (the detail/list invalidation seam) is called.
 *   3. Unchecking a line drops it from the posted body.
 *   4. The per-line bin picker (Phase 4, Task 12 — D-P4-1): choosing a bin on one
 *      line POSTs that line with bin_id: <n> while the untouched line keeps
 *      bin_id: null; a failing bins query hides the pickers and still POSTs null.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IssueComponentsDialog } from '@/routes/mousse/components/IssueComponentsDialog'
import type { WorkOrderComponentRead } from '@/routes/mousse/hooks'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the per-line Bin Selects are operable.
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

const COMPONENTS: WorkOrderComponentRead[] = [
  {
    id: 'c1',
    work_order_id: 'wo1',
    child_part_id: 'p1',
    item_id: 'i1',
    qty_per: '2',
    qty_required: '20',
    unit_of_measure: 'ea',
    sort_order: 0,
    on_hand: '100',
    issued_so_far: '0',
  },
  {
    id: 'c2',
    work_order_id: 'wo1',
    child_part_id: 'p2',
    item_id: 'i2',
    qty_per: '1',
    qty_required: '10',
    unit_of_measure: 'ea',
    sort_order: 1,
    on_hand: '50',
    issued_so_far: '4',
  },
]

// child_part_id → label; the two child parts resolve to friendly names.
const partName = (id: string) =>
  ({ p1: 'Widget A', p2: 'Widget B' })[id] ?? id

// Bins at the WO's target location (id 7) for the per-line pickers.
const BINS = [
  { id: 11, location_id: 7, code: 'A-01', description: null, active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 12, location_id: 7, code: 'A-02', description: null, active: true, created_at: '2026-01-01T00:00:00Z' },
]

// Route the mocked apiClient.get: the only GET here is the useBins query for the
// WO's target location. Pass an Error to make it fail (GELATO off / unavailable).
function routeGets(bins: unknown = BINS) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/bins')) {
      return bins instanceof Error ? Promise.reject(bins) : Promise.resolve({ data: bins })
    }
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderDialog(onSuccess = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <IssueComponentsDialog
        workOrderId="wo1"
        components={COMPONENTS}
        targetLocationId={7}
        partName={partName}
        open={true}
        onOpenChange={vi.fn()}
        onSuccess={onSuccess}
      />
    </QueryClientProvider>,
  )
  return { onSuccess, ...utils }
}

// Pick an option from a Radix Select by its accessible name.
async function selectOption(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByLabelText(label))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: option }))
}

describe('IssueComponentsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('POSTs the seeded remaining quantities (bin_id: null untouched) and calls onSuccess', async () => {
    const user = userEvent.setup()
    routeGets()
    mockPost.mockResolvedValue({ data: {} })

    const { onSuccess } = renderDialog()

    // Wait for the bins to load so the per-line pickers render on their default.
    expect(await screen.findByLabelText('Bin for Widget A')).toBeInTheDocument()

    // Lines seed to their remaining: c1 → 20 (all required), c2 → 6 (10 − 4 issued);
    // both pickers untouched on "Unbinned pool" → bin_id: null.
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [
          { component_id: 'c1', quantity: '20', bin_id: null },
          { component_id: 'c2', quantity: '6', bin_id: null },
        ],
      })
    })

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
  })

  it('drops an unchecked line from the posted body', async () => {
    const user = userEvent.setup()
    routeGets()
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // Uncheck the first component — only the second line should be issued.
    await user.click(screen.getByLabelText('Issue Widget A'))
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [{ component_id: 'c2', quantity: '6', bin_id: null }],
      })
    })
  })

  it('POSTs bin_id on the line whose bin is chosen, null on the untouched line (D-P4-1)', async () => {
    const user = userEvent.setup()
    routeGets()
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // Pick a bin for Widget A only; Widget B stays on "Unbinned pool".
    expect(await screen.findByLabelText('Bin for Widget A')).toBeInTheDocument()
    await selectOption(user, 'Bin for Widget A', 'A-02')
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [
          { component_id: 'c1', quantity: '20', bin_id: 12 },
          { component_id: 'c2', quantity: '6', bin_id: null },
        ],
      })
    })
  })

  it('hides the bin pickers and POSTs bin_id: null when the bins query fails', async () => {
    const user = userEvent.setup()
    routeGets(new Error('GELATO unavailable')) // bins query errors → degrade gracefully
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // No per-line Bin selects rendered — the dialog degrades to unbinned semantics.
    expect(screen.queryByLabelText('Bin for Widget A')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Bin for Widget B')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [
          { component_id: 'c1', quantity: '20', bin_id: null },
          { component_id: 'c2', quantity: '6', bin_id: null },
        ],
      })
    })
  })
})
