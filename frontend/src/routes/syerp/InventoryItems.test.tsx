// ABOUTME: Component tests for the SYERP Inventory Items screen — heading, Create
// ABOUTME: Item button, empty state, and graceful degradation of the PLUM part
// ABOUTME: Select when GET /api/v1/plum/parts errors (PLUM disabled).

/**
 * InventoryItems screen — component tests.
 *
 * Mounts the InventoryItems screen with apiClient.get mocked, then asserts:
 *   1. The "Inventory Items" heading renders
 *   2. The "Create Item" button is present
 *   3. The "No items yet" empty state renders when the API returns an empty array
 *   4. The item creation Sheet opens and stays usable even when the PLUM parts
 *      fetch REJECTS (PLUM module disabled — the part-link Select must not crash).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InventoryItems } from '@/routes/syerp/InventoryItems'

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

import { apiClient } from '@/api/client'
const mockApiClientGet = vi.mocked(apiClient.get)

function renderInventoryItems() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <InventoryItems />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InventoryItems screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the heading and Create Item button with empty state', async () => {
    mockApiClientGet.mockResolvedValueOnce({ data: [] }) // GET /syerp/inventory/items

    renderInventoryItems()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Inventory Items' })).toBeInTheDocument()

    // Create Item button is present
    expect(screen.getByRole('button', { name: 'Create Item' })).toBeInTheDocument()

    // After data loads, empty state shows
    await waitFor(() => {
      expect(screen.getByText('No items yet')).toBeInTheDocument()
    })

    expect(screen.getByText('Add your first item to get started.')).toBeInTheDocument()
  })

  it('keeps the item Sheet usable when the PLUM parts fetch errors (PLUM disabled)', async () => {
    const user = userEvent.setup()
    // items list resolves empty; the PLUM parts fetch REJECTS (module off).
    mockApiClientGet
      .mockResolvedValueOnce({ data: [] }) // GET /syerp/inventory/items
      .mockRejectedValue(new Error('module disabled')) // GET /plum/parts

    renderInventoryItems()

    await user.click(screen.getByRole('button', { name: 'Create Item' }))

    // The Sheet opens with its required fields — no crash despite PLUM error.
    expect(await screen.findByRole('heading', { name: 'Create Item' })).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Unit of measure')).toBeInTheDocument()

    // The optional PLUM part link Select is present and never becomes required.
    expect(screen.getByText('Linked PLUM part')).toBeInTheDocument()
    // Save is enabled once name + unit are filled — link is not required.
    await user.type(screen.getByLabelText('Name'), 'M3 bolt')
    await user.type(screen.getByLabelText('Unit of measure'), 'ea')
    expect(screen.getByRole('button', { name: 'Save Item' })).toBeEnabled()
  })
})
