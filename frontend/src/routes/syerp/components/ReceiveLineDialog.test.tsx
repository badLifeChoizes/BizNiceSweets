// ABOUTME: Component tests for the SYERP ReceiveLineDialog (Phase 8, Task 23) —
// ABOUTME: qty defaults to outstanding + location Select render, a success posts and
// ABOUTME: closes, and a 422 over-receipt surfaces a toast.error keeping the dialog open.

/**
 * ReceiveLineDialog — component tests.
 *
 * Mounts the dialog with apiClient mocked, then asserts:
 *   1. The quantity field defaults to the outstanding balance and the location
 *      Select renders when open.
 *   2. A successful POST …/receive calls onSuccess (host invalidates PO detail +
 *      list) and closes the dialog.
 *   3. A 422 over-receipt from POST …/receive surfaces a toast.error carrying the
 *      server `detail` and does NOT close the dialog (onOpenChange(false) is never
 *      called, onSuccess is never called).
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReceiveLineDialog } from '@/routes/syerp/components/ReceiveLineDialog'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the location Select is operable here.
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
      <ReceiveLineDialog
        poId="po-1"
        lineId="line-1"
        outstandingQty="7"
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

describe('ReceiveLineDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('defaults the quantity to the outstanding balance and renders the location Select', async () => {
    mockGet.mockResolvedValue({ data: LOCATIONS }) // GET …/inventory/locations

    renderDialog()

    expect(await screen.findByRole('heading', { name: 'Receive Line' })).toBeInTheDocument()
    expect(screen.getByLabelText('Location')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity')).toHaveValue('7')
    expect(screen.getByRole('button', { name: 'Post Receipt' })).toBeInTheDocument()
  })

  it('posts the receipt and closes on success', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })
    mockPost.mockResolvedValue({ data: { id: 'po-1' } })

    const { onOpenChange, onSuccess } = renderDialog()

    await screen.findByRole('heading', { name: 'Receive Line' })
    // First active location is selected by default; accept the default qty of 7.
    await user.click(screen.getByRole('button', { name: 'Post Receipt' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/purchasing/orders/po-1/lines/line-1/receive',
        { location_id: 1, qty: '7' },
      )
    })
    expect(onSuccess).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('surfaces a 422 over-receipt rejection and keeps the dialog open', async () => {
    const user = userEvent.setup()
    mockGet.mockResolvedValue({ data: LOCATIONS })
    // Backend rejects receiving more than the line's outstanding balance.
    mockPost.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: 'Receipt exceeds outstanding quantity' } },
    })

    const { onOpenChange, onSuccess } = renderDialog()

    await screen.findByRole('heading', { name: 'Receive Line' })

    await selectOption(user, 'Location', 'Main')
    await user.clear(screen.getByLabelText('Quantity'))
    await user.type(screen.getByLabelText('Quantity'), '999')
    await user.click(screen.getByRole('button', { name: 'Post Receipt' }))

    // The server detail is surfaced via toast.error.
    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Receipt exceeds outstanding quantity')
    })

    // Dialog stays open and nothing was invalidated.
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(onSuccess).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Receive Line' })).toBeInTheDocument()
  })
})
