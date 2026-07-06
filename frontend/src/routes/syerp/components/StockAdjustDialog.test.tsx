// ABOUTME: Component tests for the SYERP StockAdjustDialog (Phase 8, Task 12) —
// ABOUTME: fields render, a blank reason blocks submit, and a 422 negative-stock
// ABOUTME: rejection surfaces a toast.error while keeping the dialog open (AC10-6).

/**
 * StockAdjustDialog — component tests.
 *
 * Mounts the dialog with apiClient mocked, then asserts:
 *   1. Location / Quantity / Reason fields render when open.
 *   2. A blank reason keeps the "Post Adjustment" button disabled; filling it
 *      (with a valid signed qty) enables it.
 *   3. A 422 rejection from POST …/adjustments surfaces a toast.error carrying the
 *      server `detail` and does NOT close the dialog (onOpenChange(false) is never
 *      called, onSuccess is never called).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StockAdjustDialog } from '@/routes/syerp/components/StockAdjustDialog'

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

// Mock sonner toasts so we can assert error surfacing.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
import { toast } from 'sonner'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)
const mockToastError = vi.mocked(toast.error)

const LOCATIONS = [
  { id: 1, name: 'Main', active: true },
  { id: 2, name: 'Overflow', active: true },
]

function renderDialog(overrides: { onOpenChange?: () => void; onSuccess?: () => void } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const onOpenChange = overrides.onOpenChange ?? vi.fn()
  const onSuccess = overrides.onSuccess ?? vi.fn()
  render(
    <QueryClientProvider client={queryClient}>
      <StockAdjustDialog
        itemId="item-123"
        open={true}
        onOpenChange={onOpenChange}
        onSuccess={onSuccess}
      />
    </QueryClientProvider>,
  )
  return { onOpenChange, onSuccess }
}

describe('StockAdjustDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the location, quantity and reason fields', async () => {
    mockGet.mockResolvedValue({ data: LOCATIONS }) // GET …/inventory/locations

    renderDialog()

    expect(await screen.findByRole('heading', { name: 'Adjust Stock' })).toBeInTheDocument()
    expect(screen.getByLabelText('Location')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Post Adjustment' })).toBeInTheDocument()
  })

  it('blocks submit while the reason is blank', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })

    renderDialog()

    await screen.findByRole('heading', { name: 'Adjust Stock' })

    // A valid signed quantity but no reason yet → still disabled.
    await user.type(screen.getByLabelText('Quantity'), '-3')
    expect(screen.getByRole('button', { name: 'Post Adjustment' })).toBeDisabled()

    // Filling the reason enables the submit.
    await user.type(screen.getByLabelText('Reason'), 'Damaged in transit')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Post Adjustment' })).toBeEnabled()
    })
  })

  it('surfaces a 422 negative-stock rejection and keeps the dialog open', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })
    // Backend rejects a delta that would drive this location negative.
    mockPost.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: 'Adjustment would drive Main negative' } },
    })

    const { onOpenChange, onSuccess } = renderDialog()

    await screen.findByRole('heading', { name: 'Adjust Stock' })

    await user.type(screen.getByLabelText('Quantity'), '-999')
    await user.type(screen.getByLabelText('Reason'), 'Write-off')
    await user.click(screen.getByRole('button', { name: 'Post Adjustment' }))

    // The server detail is surfaced via toast.error.
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Adjustment would drive Main negative')
    })

    // Dialog stays open and nothing was invalidated.
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(onSuccess).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Adjust Stock' })).toBeInTheDocument()
  })
})
