/**
 * Customers screen — Wave 0 component tests.
 *
 * Mounts the Customers screen with apiClient.get mocked, then asserts:
 *   1. The "Customers" heading renders
 *   2. The "Create Customer" button is present
 *   3. The "No customers yet" empty state renders when API returns an empty array
 *
 * Also mocks the settings GET that PartnerSheet uses for currency default.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Customers } from '@/routes/syerp/Customers'

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

function renderCustomers() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Customers />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Customers screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Customers heading and Create Customer button with empty state', async () => {
    // First call: partners list (empty); second call: settings (for PartnerSheet currency)
    mockApiClientGet
      .mockResolvedValueOnce({ data: [] })         // GET /api/v1/syerp/partners?role=customer
      .mockResolvedValueOnce({ data: [] })          // GET /api/v1/core/settings (PartnerSheet)

    renderCustomers()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Customers' })).toBeInTheDocument()

    // Create Customer button is present
    expect(screen.getByRole('button', { name: 'Create Customer' })).toBeInTheDocument()

    // After data loads, empty state shows
    await waitFor(() => {
      expect(screen.getByText('No customers yet')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Add your first customer to get started.'),
    ).toBeInTheDocument()
  })
})
