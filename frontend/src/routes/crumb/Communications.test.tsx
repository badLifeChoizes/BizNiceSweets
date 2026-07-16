// ABOUTME: Component test for the CRUMB Communications timeline (CRUMB-01) — after picking a
// ABOUTME: customer, the append-only interaction timeline renders from a mocked GET
// ABOUTME: /crumb/interactions (via useCustomerTimeline), newest-first, with type/timestamp/body.

/**
 * Communications screen — component test.
 *
 * Mounts the screen with apiClient + sonner mocked, picks a customer from the Select, then
 * asserts the timeline renders the interactions returned by a mocked GET in newest-first
 * order, each entry showing its type, UTC timestamp and body.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Communications } from '@/routes/crumb/Communications'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which jsdom does
// not implement. Stub them so the customer Select is operable.
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
    delete: vi.fn(),
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
const mockGet = vi.mocked(apiClient.get)

const CUSTOMERS = [{ id: 'c1', name: 'Globex', role: 'customer' }]

// Server returns the timeline newest-first; the screen renders it as-is.
const TIMELINE = [
  {
    id: 'i1',
    partner_id: 'c1',
    lead_id: null,
    opportunity_id: null,
    quote_id: null,
    interaction_type: 'call',
    occurred_at: '2026-07-15T14:30:00Z',
    body: 'Called about the renewal',
    actor_id: 'u1',
    created_at: '2026-07-15T14:30:00Z',
  },
  {
    id: 'i2',
    partner_id: 'c1',
    lead_id: null,
    opportunity_id: null,
    quote_id: null,
    interaction_type: 'email',
    occurred_at: '2026-07-09T08:00:00Z',
    body: 'Sent the initial proposal',
    actor_id: 'u1',
    created_at: '2026-07-09T08:00:00Z',
  },
]

// Route every GET by URL so query order does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/crumb/interactions')) return Promise.resolve({ data: TIMELINE })
    if (url.includes('/syerp/partners')) return Promise.resolve({ data: CUSTOMERS })
    return Promise.resolve({ data: [] })
  })
}

function renderCommunications() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Communications />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Communications screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the timeline newest-first with type, timestamp and body', async () => {
    const user = userEvent.setup()
    mockGets()

    renderCommunications()

    // Pick a customer to drive useCustomerTimeline(partnerId).
    await user.click(screen.getByLabelText('Customer'))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByRole('option', { name: 'Globex' }))

    // The timeline resolves; entries render newest-first.
    const items = await screen.findAllByRole('listitem')
    expect(items).toHaveLength(2)

    // Newest entry first: type / UTC timestamp / body.
    expect(within(items[0]).getByText('Call')).toBeInTheDocument()
    expect(within(items[0]).getByText('2026-07-15 14:30:00 UTC')).toBeInTheDocument()
    expect(within(items[0]).getByText('Called about the renewal')).toBeInTheDocument()

    // Older entry second.
    expect(within(items[1]).getByText('Email')).toBeInTheDocument()
    expect(within(items[1]).getByText('2026-07-09 08:00:00 UTC')).toBeInTheDocument()
    expect(within(items[1]).getByText('Sent the initial proposal')).toBeInTheDocument()
  })
})
