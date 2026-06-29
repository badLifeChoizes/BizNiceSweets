/**
 * PartsList screen — Wave 0 component smoke tests.
 *
 * Mounts the PartsList screen with apiClient.get mocked, then asserts:
 *   1. The "Parts" heading renders
 *   2. The "Create Part" button is present
 *   3. The "No parts yet" empty state renders when the API returns an empty array
 *
 * Mirrors the pattern from Vendors.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PartsList } from '@/routes/plum/PartsList'

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

function renderPartsList() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/plum/parts']}>
        <PartsList />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PartsList screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Parts heading and Create Part button', async () => {
    // Parts list (empty); settings query not needed (PartSheet is closed by default)
    mockApiClientGet.mockResolvedValueOnce({ data: [] })

    renderPartsList()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Parts' })).toBeInTheDocument()

    // Create Part button is present
    expect(screen.getByRole('button', { name: 'Create Part' })).toBeInTheDocument()
  })

  it('renders the No parts yet empty state when API returns an empty array', async () => {
    mockApiClientGet.mockResolvedValueOnce({ data: [] })

    renderPartsList()

    // After data resolves, the empty state should appear
    await waitFor(() => {
      expect(screen.getByText('No parts yet')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Create your first part to get started.'),
    ).toBeInTheDocument()
  })
})
