// ABOUTME: Component tests for the GELATO Bins screen (GELATO-01) — pick a location,
// ABOUTME: list its bins, create a bin (POST), surface a dup-code 4xx as a toast, and
// ABOUTME: hide archived bins until the Show-archived Switch is on.

/**
 * Bins screen — component tests.
 *
 * Mounts the screen with apiClient + sonner mocked, then asserts:
 *   1. Selecting a location renders its bins from a mocked GET.
 *   2. Opening the create Sheet and saving POSTs /gelato/bins with the payload.
 *   3. A duplicate-code 4xx (axios error with a string `detail`) surfaces via
 *      toast.error rather than a generic message.
 *   4. Archived bins are hidden by default (include_archived=false) and appear once
 *      the Show-archived Switch is toggled on (include_archived=true).
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Bins } from '@/routes/gelato/Bins'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom
// does not implement. Stub them so the Location Select is operable.
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
import { toast } from 'sonner'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)
const mockToastError = vi.mocked(toast.error)

const LOCATIONS = [{ id: 7, name: 'Main Warehouse', active: true, created_at: '', updated_at: '' }]

const ACTIVE_BIN = {
  id: 1,
  location_id: 7,
  code: 'A-01-01',
  description: 'Front rack',
  active: true,
  created_at: '2026-07-01T00:00:00Z',
}
const ARCHIVED_BIN = {
  id: 2,
  location_id: 7,
  code: 'Z-99-99',
  description: null,
  active: false,
  created_at: '2026-07-01T00:00:00Z',
}

// Route every GET by URL. The bins endpoint honors the include_archived param so
// the Show-archived assertion can drive server-side filtering.
function mockGets() {
  mockGet.mockImplementation((url: string, config?: { params?: { include_archived?: boolean } }) => {
    if (url.includes('/inventory/locations')) return Promise.resolve({ data: LOCATIONS })
    if (url.includes('/gelato/locations/7/bins')) {
      const includeArchived = config?.params?.include_archived === true
      const data = includeArchived ? [ACTIVE_BIN, ARCHIVED_BIN] : [ACTIVE_BIN]
      return Promise.resolve({ data })
    }
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderBins() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Bins />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Pick an option from a Radix Select by its accessible name.
async function selectLocation(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByLabelText('Location'))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name }))
}

describe('Bins screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders bins for the selected location', async () => {
    const user = userEvent.setup()
    mockGets()

    renderBins()

    // Nothing until a location is chosen.
    expect(screen.getByText('Select a location to view and manage its bins.')).toBeInTheDocument()

    await selectLocation(user, 'Main Warehouse')

    await waitFor(() => {
      expect(screen.getByText('A-01-01')).toBeInTheDocument()
    })
    expect(screen.getByText('Front rack')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('creates a bin via the Sheet and POSTs the payload', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockResolvedValueOnce({ data: { ...ACTIVE_BIN, id: 3, code: 'B-02-02' } })

    renderBins()
    await selectLocation(user, 'Main Warehouse')
    await screen.findByText('A-01-01')

    await user.click(screen.getByRole('button', { name: 'Create Bin' }))

    expect(await screen.findByRole('heading', { name: 'Create Bin' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Code'), 'B-02-02')
    await user.type(screen.getByLabelText('Description'), 'Overflow')
    await user.click(screen.getByRole('button', { name: 'Save Bin' }))

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/v1/gelato/bins', {
        location_id: 7,
        code: 'B-02-02',
        description: 'Overflow',
      })
    })
  })

  it('surfaces a duplicate-code 4xx as an error toast', async () => {
    const user = userEvent.setup()
    mockGets()
    mockPost.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'A bin with code A-01-01 already exists.' } },
    })

    renderBins()
    await selectLocation(user, 'Main Warehouse')
    await screen.findByText('A-01-01')

    await user.click(screen.getByRole('button', { name: 'Create Bin' }))
    await screen.findByRole('heading', { name: 'Create Bin' })
    await user.type(screen.getByLabelText('Code'), 'A-01-01')
    await user.click(screen.getByRole('button', { name: 'Save Bin' }))

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('A bin with code A-01-01 already exists.')
    })
  })

  it('hides archived bins until the Show archived switch is on', async () => {
    const user = userEvent.setup()
    mockGets()

    renderBins()
    await selectLocation(user, 'Main Warehouse')

    // Default: only the active bin, archived one hidden.
    await waitFor(() => {
      expect(screen.getByText('A-01-01')).toBeInTheDocument()
    })
    expect(screen.queryByText('Z-99-99')).not.toBeInTheDocument()

    // Toggle Show archived → the archived bin appears.
    await user.click(screen.getByLabelText('Show archived'))

    await waitFor(() => {
      expect(screen.getByText('Z-99-99')).toBeInTheDocument()
    })
    expect(screen.getByText('Archived')).toBeInTheDocument()
  })
})
