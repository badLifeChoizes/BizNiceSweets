/**
 * Vendors screen — Wave 0 component tests.
 *
 * Mounts the Vendors screen with apiClient.get mocked, then asserts:
 *   1. The "Vendors" heading renders
 *   2. The "Create Vendor" button is present
 *   3. The "No vendors yet" empty state renders when API returns an empty array
 *
 * Also mocks the settings GET that PartnerSheet uses for currency default.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Vendors } from '@/routes/syerp/Vendors'

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

function renderVendors() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Vendors />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Vendors screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Vendors heading and Create Vendor button with empty state', async () => {
    // First call: partners list (empty); second call: settings (for PartnerSheet currency)
    mockApiClientGet
      .mockResolvedValueOnce({ data: [] })         // GET /api/v1/syerp/partners?role=vendor
      .mockResolvedValueOnce({ data: [] })          // GET /api/v1/core/settings (PartnerSheet)

    renderVendors()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Vendors' })).toBeInTheDocument()

    // Create Vendor button is present
    expect(screen.getByRole('button', { name: 'Create Vendor' })).toBeInTheDocument()

    // After data loads, empty state shows
    await waitFor(() => {
      expect(screen.getByText('No vendors yet')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Add your first vendor to get started.'),
    ).toBeInTheDocument()
  })
})
