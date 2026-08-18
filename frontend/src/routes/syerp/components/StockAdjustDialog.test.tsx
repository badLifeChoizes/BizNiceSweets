// ABOUTME: Component tests for the SYERP StockAdjustDialog (Phase 8, Task 12; bin picker
// ABOUTME: Phase 4, Task 10) — fields render, a blank reason blocks submit, a 422 keeps
// ABOUTME: the dialog open, and the POST body carries bin_id: <n> | null (D-P4-1).

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
 *   4. The bin picker (Phase 4, Task 10 — D-P4-1): choosing a bin POSTs
 *      bin_id: <n>; leaving it on "Unbinned pool" POSTs bin_id: null; a failing
 *      bins query hides the picker and still POSTs bin_id: null.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StockAdjustDialog } from '@/routes/syerp/components/StockAdjustDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the Bin Select is operable here.
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

const BINS = [
  { id: 11, location_id: 1, code: 'A-01', description: null, active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 12, location_id: 1, code: 'A-02', description: null, active: true, created_at: '2026-01-01T00:00:00Z' },
]

// Route the single mocked apiClient.get by URL: the locations Select and the
// per-location bins query (useBins) both go through it. Pass an Error to make
// the bins query fail (GELATO off / endpoint unavailable).
function routeGets(bins: unknown = BINS) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/bins')) {
      return bins instanceof Error ? Promise.reject(bins) : Promise.resolve({ data: bins })
    }
    return Promise.resolve({ data: LOCATIONS })
  })
}

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

// Pick an option from a Radix Select by its accessible name.
async function selectOption(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByLabelText(label))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: option }))
}

describe('StockAdjustDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the location, quantity and reason fields', async () => {
    routeGets() // GET …/inventory/locations + …/bins

    renderDialog()

    expect(await screen.findByRole('heading', { name: 'Adjust Stock' })).toBeInTheDocument()
    expect(screen.getByLabelText('Location')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toBeInTheDocument()
    expect(screen.getByLabelText('Reason')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Post Adjustment' })).toBeInTheDocument()
  })

  it('blocks submit while the reason is blank', async () => {
    const user = userEvent.setup()
    routeGets()

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
    routeGets()
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

  it('POSTs bin_id when a bin is chosen (D-P4-1)', async () => {
    const user = userEvent.setup()
    routeGets()
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // The first active location (Main, id 1) is auto-selected, so its bins load
    // and the optional Bin select appears.
    expect(await screen.findByLabelText('Bin')).toBeInTheDocument()

    await selectOption(user, 'Bin', 'A-02')
    await user.type(screen.getByLabelText('Quantity'), '-3')
    await user.type(screen.getByLabelText('Reason'), 'Cycle count')
    await user.click(screen.getByRole('button', { name: 'Post Adjustment' }))

    // The REAL POST body carries the chosen bin.
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/inventory/items/item-123/adjustments',
        { location_id: 1, bin_id: 12, qty_delta: '-3', reason: 'Cycle count' },
      )
    })
  })

  it('POSTs bin_id: null when the bin picker is left on "Unbinned pool"', async () => {
    const user = userEvent.setup()
    routeGets()
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    // Picker is present but untouched — the default is the unbinned pool.
    expect(await screen.findByLabelText('Bin')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Quantity'), '5')
    await user.type(screen.getByLabelText('Reason'), 'Found stock')
    await user.click(screen.getByRole('button', { name: 'Post Adjustment' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/inventory/items/item-123/adjustments',
        { location_id: 1, bin_id: null, qty_delta: '5', reason: 'Found stock' },
      )
    })
  })

  it('hides the bin picker and POSTs bin_id: null when the bins query fails', async () => {
    const user = userEvent.setup()
    routeGets(new Error('GELATO unavailable')) // bins query errors → degrade gracefully
    mockPost.mockResolvedValue({ data: {} })

    renderDialog()

    await screen.findByRole('heading', { name: 'Adjust Stock' })

    await user.type(screen.getByLabelText('Quantity'), '2')
    await user.type(screen.getByLabelText('Reason'), 'Recount')

    // No Bin select rendered — the dialog degrades to unbinned semantics.
    expect(screen.queryByLabelText('Bin')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Post Adjustment' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/inventory/items/item-123/adjustments',
        { location_id: 1, bin_id: null, qty_delta: '2', reason: 'Recount' },
      )
    })
  })
})
