// ABOUTME: Component tests for the MOUSSE IssueComponentsDialog (MOUSSE-01, SC7) — checked
// ABOUTME: component lines POST /mousse/work-orders/{id}/issue with the { lines: [...] } body
// ABOUTME: (component_id + quantity) and the host's onSuccess invalidation seam fires.

/**
 * IssueComponentsDialog — component tests.
 *
 * Mounts the dialog open with apiClient + sonner mocked, then asserts:
 *   1. Lines seed to their remaining (qty_required − issued_so_far) and submit POSTs the
 *      exact { lines: [{ component_id, quantity }] } body to …/issue.
 *   2. On success the onSuccess callback (the detail/list invalidation seam) is called.
 *   3. Unchecking a line drops it from the posted body.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IssueComponentsDialog } from '@/routes/mousse/components/IssueComponentsDialog'
import type { WorkOrderComponentRead } from '@/routes/mousse/hooks'

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
        partName={partName}
        open={true}
        onOpenChange={vi.fn()}
        onSuccess={onSuccess}
      />
    </QueryClientProvider>,
  )
  return { onSuccess, ...utils }
}

describe('IssueComponentsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('POSTs the seeded remaining quantities and calls onSuccess', async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValue({ data: {} })

    const { onSuccess } = renderDialog()

    // Lines seed to their remaining: c1 → 20 (all required), c2 → 6 (10 − 4 issued).
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [
          { component_id: 'c1', quantity: '20' },
          { component_id: 'c2', quantity: '6' },
        ],
      })
    })

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1))
  })

  it('drops an unchecked line from the posted body', async () => {
    const user = userEvent.setup()
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // Uncheck the first component — only the second line should be issued.
    await user.click(screen.getByLabelText('Issue Widget A'))
    await user.click(screen.getByRole('button', { name: 'Issue Components' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/mousse/work-orders/wo1/issue', {
        lines: [{ component_id: 'c2', quantity: '6' }],
      })
    })
  })
})
