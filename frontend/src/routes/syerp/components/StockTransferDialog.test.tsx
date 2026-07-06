// ABOUTME: Component tests for the SYERP StockTransferDialog (Phase 8, Task 13) —
// ABOUTME: from/to Selects + qty render, a from==to selection blocks submit, and a
// ABOUTME: 422 over-draw surfaces a toast.error while keeping the dialog open (AC10-6).

/**
 * StockTransferDialog — component tests.
 *
 * Mounts the dialog with apiClient mocked, then asserts:
 *   1. From-location / To-location / Quantity fields render when open.
 *   2. Selecting the same source and destination shows the inline guard and keeps
 *      the "Transfer Stock" button disabled; picking a different pair enables it.
 *   3. A 422 over-draw from POST …/transfers surfaces a toast.error carrying the
 *      server `detail` and does NOT close the dialog (onOpenChange(false) is never
 *      called, onSuccess is never called).
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StockTransferDialog } from '@/routes/syerp/components/StockTransferDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the from/to Selects are operable here.
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
      <StockTransferDialog
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

describe('StockTransferDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the from-location, to-location and quantity fields', async () => {
    mockGet.mockResolvedValue({ data: LOCATIONS }) // GET …/inventory/locations

    renderDialog()

    expect(await screen.findByRole('heading', { name: 'Transfer Stock' })).toBeInTheDocument()
    expect(screen.getByLabelText('From location')).toBeInTheDocument()
    expect(screen.getByLabelText('To location')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Transfer Stock' })).toBeInTheDocument()
  })

  it('blocks submit when source and destination are the same', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })

    renderDialog()

    await screen.findByRole('heading', { name: 'Transfer Stock' })

    // Same source and destination + a valid qty → guard shows, submit disabled.
    await selectOption(user, 'From location', 'Main')
    await selectOption(user, 'To location', 'Main')
    await user.type(screen.getByLabelText('Quantity'), '5')

    expect(
      screen.getByText('Source and destination must be different.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Transfer Stock' })).toBeDisabled()

    // Choosing a distinct destination clears the guard and enables submit.
    await selectOption(user, 'To location', 'Overflow')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Transfer Stock' })).toBeEnabled()
    })
  })

  it('surfaces a 422 over-draw rejection and keeps the dialog open', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })
    // Backend rejects a transfer larger than the source holds.
    mockPost.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: 'Insufficient stock at Main to transfer' } },
    })

    const { onOpenChange, onSuccess } = renderDialog()

    await screen.findByRole('heading', { name: 'Transfer Stock' })

    await selectOption(user, 'From location', 'Main')
    await selectOption(user, 'To location', 'Overflow')
    await user.type(screen.getByLabelText('Quantity'), '999')
    await user.click(screen.getByRole('button', { name: 'Transfer Stock' }))

    // The server detail is surfaced via toast.error.
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Insufficient stock at Main to transfer')
    })

    // Dialog stays open and nothing was invalidated.
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(onSuccess).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Transfer Stock' })).toBeInTheDocument()
  })
})
