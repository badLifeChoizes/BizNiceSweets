/**
 * Users admin screen — component test.
 *
 * Mounts the Users screen with apiClient.get mocked to return an empty
 * users array, then asserts:
 *   1. The "Users" heading renders
 *   2. The "Create User" button is present
 *   3. The empty state copy ("No users found") renders for the empty result
 *
 * This gives behavioral coverage so the screen is not type-check-only.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Users } from '@/routes/admin/Users'

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

function renderUsers() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Users />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Users admin screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Users heading and Create User button with empty state', async () => {
    // Mock GET /api/v1/auth/users to return an empty array
    mockApiClientGet.mockResolvedValueOnce({ data: [] })

    renderUsers()

    // Heading is present immediately (before data loads)
    expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument()

    // Create User button is present
    expect(screen.getByRole('button', { name: 'Create User' })).toBeInTheDocument()

    // After data loads, empty state shows
    await waitFor(() => {
      expect(screen.getByText('No users found')).toBeInTheDocument()
    })

    expect(
      screen.getByText('No users match your search. Clear the filter or create a new user.'),
    ).toBeInTheDocument()
  })

  it('renders users in a table when data is returned', async () => {
    mockApiClientGet.mockResolvedValueOnce({
      data: [
        {
          id: 'user-1',
          email: 'admin@test.local',
          full_name: 'Admin User',
          is_active: true,
          roles: [{ name: 'admin' }],
        },
      ],
    })

    renderUsers()

    await waitFor(() => {
      expect(screen.getByText('Admin User')).toBeInTheDocument()
    })

    expect(screen.getByText('admin@test.local')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    // Status badge — shows "Active" text (not just color)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('has no "No users found" text when users exist', async () => {
    mockApiClientGet.mockResolvedValueOnce({
      data: [
        {
          id: 'user-1',
          email: 'admin@test.local',
          full_name: 'Admin User',
          is_active: true,
          roles: [{ name: 'admin' }],
        },
      ],
    })

    renderUsers()

    await waitFor(() => {
      expect(screen.getByText('Admin User')).toBeInTheDocument()
    })

    expect(screen.queryByText('No users found')).not.toBeInTheDocument()
  })
})
