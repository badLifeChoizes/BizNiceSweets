// ABOUTME: Component tests for the SYERP Stock Locations screen — heading, Create
// ABOUTME: Location button, empty state, and the create Sheet opening with its
// ABOUTME: single required Name field (Phase 8, Task 10).

/**
 * StockLocations screen — component tests.
 *
 * Mounts the StockLocations screen with apiClient.get mocked, then asserts:
 *   1. The "Stock Locations" heading renders
 *   2. The "Create Location" button is present
 *   3. The "No locations yet" empty state renders when the API returns []
 *   4. The create Sheet opens with its single required Name field and a Save
 *      button that enables once a name is entered.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StockLocations } from '@/routes/syerp/StockLocations'

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

function renderStockLocations() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StockLocations />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StockLocations screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the heading and Create Location button with empty state', async () => {
    mockApiClientGet.mockResolvedValueOnce({ data: [] }) // GET /syerp/inventory/locations

    renderStockLocations()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Stock Locations' })).toBeInTheDocument()

    // Create Location button is present
    expect(screen.getByRole('button', { name: 'Create Location' })).toBeInTheDocument()

    // After data loads, empty state shows
    await waitFor(() => {
      expect(screen.getByText('No locations yet')).toBeInTheDocument()
    })

    expect(screen.getByText('Add your first location to get started.')).toBeInTheDocument()
  })

  it('opens the create Sheet with a required Name field', async () => {
    const user = userEvent.setup()
    mockApiClientGet.mockResolvedValueOnce({ data: [] }) // GET /syerp/inventory/locations

    renderStockLocations()

    await user.click(screen.getByRole('button', { name: 'Create Location' }))

    // The Sheet opens with its single required field.
    expect(await screen.findByRole('heading', { name: 'Create Location' })).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()

    // Save is disabled until a name is entered, then enabled.
    expect(screen.getByRole('button', { name: 'Save Location' })).toBeDisabled()
    await user.type(screen.getByLabelText('Name'), 'Warehouse B')
    expect(screen.getByRole('button', { name: 'Save Location' })).toBeEnabled()
  })

  it('renders location rows returned by the API', async () => {
    mockApiClientGet.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          name: 'Main',
          active: true,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    })

    renderStockLocations()

    await waitFor(() => {
      expect(screen.getByText('Main')).toBeInTheDocument()
    })
    expect(screen.getByText('Active')).toBeInTheDocument()
  })
})
