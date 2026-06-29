/**
 * ProtectedRoute unit tests.
 *
 * Tests the two key behaviors from UI-SPEC Screen 2:
 *   1. Unauthenticated → redirect to /login
 *   2. Authenticated → render child Outlet content
 *
 * useAuth is mocked so no real network or queryClient setup is needed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/components/ProtectedRoute'

// Mock the useAuth hook — controls returned session state
vi.mock('@/hooks/useAuth')

import { useAuth } from '@/hooks/useAuth'
const mockUseAuth = vi.mocked(useAuth)

function renderWithRouter(initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<div>Protected Content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('redirects to /login when user is null (unauthenticated)', () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: false })

    renderWithRouter(['/'])

    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('renders Outlet (children) when user is authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: {
        id: 'user-1',
        email: 'admin@test.local',
        full_name: 'Admin User',
        is_active: true,
        roles: [{ name: 'admin' }],
        permissions: [],
      },
      isLoading: false,
    })

    renderWithRouter(['/'])

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
  })

  it('renders loading spinner while auth state is being determined', () => {
    mockUseAuth.mockReturnValue({ user: null, isLoading: true })

    renderWithRouter(['/'])

    // Spinner should be present — no redirect, no protected content
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    // The spinner is a Loader2 SVG — verify neither page renders
  })
})
