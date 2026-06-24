/**
 * Login page unit tests.
 *
 * Tests key behaviors from UI-SPEC Screen 1:
 *   1. Successful login: apiClient.post resolves → setAccessToken called + navigation
 *   2. Bad credentials (401): error copy renders ("Incorrect email or password…")
 *   3. Server error (network): server-unreachable copy renders
 *   4. No "Create account" or "Forgot password" links appear (D-01, D-13)
 *
 * apiClient and useNavigate are mocked so no real network or router setup is needed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import axios, { AxiosError } from 'axios'
import { Login } from '@/routes/Login'
import { setAccessToken } from '@/auth/token'

// Mock the axios apiClient module
vi.mock('@/api/client', () => ({
  apiClient: {
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

// Mock react-router-dom navigate (keep MemoryRouter for rendering)
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock token module so we can assert setAccessToken was called
vi.mock('@/auth/token', () => ({
  setAccessToken: vi.fn(),
  getAccessToken: vi.fn(() => null),
  clearAccessToken: vi.fn(),
}))

import { apiClient } from '@/api/client'
const mockApiClientPost = vi.mocked(apiClient.post)
const mockSetAccessToken = vi.mocked(setAccessToken)

function renderLogin() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Sign In form with email and password fields', () => {
    renderLogin()
    expect(screen.getByRole('heading', { name: 'BizNiceSweets' })).toBeInTheDocument()
    expect(screen.getByText('Sign in to your account')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })

  it('calls setAccessToken and navigates on successful login', async () => {
    mockApiClientPost.mockResolvedValueOnce({
      data: { access_token: 'test-token-abc', token_type: 'bearer' },
    })

    renderLogin()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'admin@test.local' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'adminpass' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(mockSetAccessToken).toHaveBeenCalledWith('test-token-abc')
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
    })
  })

  it('shows bad-credentials error copy on 401', async () => {
    // Create an AxiosError with status 401
    const axiosErr = new AxiosError('Request failed with status 401')
    axiosErr.response = { status: 401 } as AxiosError['response']
    // Mark it as an axios error
    Object.defineProperty(axiosErr, 'isAxiosError', { value: true })
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    mockApiClientPost.mockRejectedValueOnce(axiosErr)

    renderLogin()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'admin@test.local' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'wrongpassword' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(
        screen.getByText('Incorrect email or password. Check your credentials and try again.'),
      ).toBeInTheDocument()
    })
    expect(mockSetAccessToken).not.toHaveBeenCalled()
  })

  it('shows server-unreachable error copy when no response', async () => {
    const networkErr = new AxiosError('Network Error')
    // No response property = network failure
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    mockApiClientPost.mockRejectedValueOnce(networkErr)

    renderLogin()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'admin@test.local' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'somepass' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(
        screen.getByText('Unable to reach the server. Check that the backend is running.'),
      ).toBeInTheDocument()
    })
  })

  it('has no Create account or Forgot password text (D-01, D-13)', () => {
    renderLogin()
    expect(screen.queryByText(/create account/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/forgot password/i)).not.toBeInTheDocument()
  })

  it('password toggle changes field type and aria-label', () => {
    renderLogin()

    const passwordInput = screen.getByLabelText('Password')
    const toggleButton = screen.getByRole('button', { name: 'Show password' })

    // Initially password type
    expect(passwordInput).toHaveAttribute('type', 'password')
    expect(toggleButton).toHaveAttribute('aria-label', 'Show password')

    // Click to show
    fireEvent.click(toggleButton)
    expect(passwordInput).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
      'aria-label',
      'Hide password',
    )
  })
})
