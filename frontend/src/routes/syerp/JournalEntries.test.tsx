// ABOUTME: Component tests for the SYERP Journal Entries screen (Phase 9a, SYERP-12
// ABOUTME: AC1) — the list renders posted entries, the New-entry dialog opens and adds
// ABOUTME: lines, and the balance gate keeps Post disabled until debits equal credits.

/**
 * JournalEntries screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GET routed by URL to accounts vs the
 * journal-entries list), then asserts:
 *   1. The list renders posted entries (memo + roll-up amount).
 *   2. The "New journal entry" dialog opens and "Add line" appends a line.
 *   3. The balance gate: Post is disabled while the entry is unbalanced and becomes
 *      enabled only once there are ≥2 one-sided lines whose debits equal credits.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { JournalEntries } from '@/routes/syerp/JournalEntries'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the account Selects are operable here.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

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

// Mock sonner toasts so a post never throws in jsdom.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)
const mockPost = vi.mocked(apiClient.post)

const ACCOUNTS = [
  { id: 1000, code: '1000', name: 'Cash', account_type: 'ASSET' },
  { id: 4000, code: '4000', name: 'Sales', account_type: 'REVENUE' },
]

const ENTRIES = [
  {
    id: 'je-1',
    entry_date: '2026-07-01',
    memo: 'Opening balance',
    source_type: null,
    source_id: null,
    reversal_of_id: null,
    actor_id: 'user-1',
    created_at: '2026-07-01T00:00:00Z',
    lines: [
      { id: 'l-1', line_no: 1, account_id: 1000, debit: '500.00', credit: null },
      { id: 'l-2', line_no: 2, account_id: 4000, debit: null, credit: '500.00' },
    ],
  },
]

// Route GET by URL: accounts (dialog) vs the journal-entries list.
function routeGet(entries: unknown[] = ENTRIES) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
    if (url.includes('/gl/journal-entries')) return Promise.resolve({ data: entries })
    return Promise.resolve({ data: [] })
  })
}

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <JournalEntries />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Pick an option from a Radix Select by the trigger's accessible name.
async function selectAccount(
  user: ReturnType<typeof userEvent.setup>,
  triggerLabel: string,
  option: string,
) {
  await user.click(screen.getByLabelText(triggerLabel))
  const listbox = await screen.findByRole('listbox')
  await user.click(within(listbox).getByRole('option', { name: option }))
}

describe('JournalEntries screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the heading and the posted entries list', async () => {
    routeGet()

    renderScreen()

    expect(screen.getByRole('heading', { name: 'Journal Entries' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'New journal entry' }),
    ).toBeInTheDocument()

    // The posted entry's memo and debit roll-up appear once the list loads.
    await waitFor(() => {
      expect(screen.getByText('Opening balance')).toBeInTheDocument()
    })
    expect(screen.getByText('500.00')).toBeInTheDocument()
  })

  it('opens the dialog and appends a line', async () => {
    const user = userEvent.setup()
    routeGet([])

    renderScreen()

    await user.click(screen.getByRole('button', { name: 'New journal entry' }))

    // Dialog opens with two starter lines.
    expect(await screen.findByRole('heading', { name: 'New Journal Entry' })).toBeInTheDocument()
    expect(screen.getByLabelText('Line 1 account')).toBeInTheDocument()
    expect(screen.getByLabelText('Line 2 account')).toBeInTheDocument()
    expect(screen.queryByLabelText('Line 3 account')).not.toBeInTheDocument()

    // "Add line" appends a third line.
    await user.click(screen.getByRole('button', { name: 'Add line' }))
    expect(await screen.findByLabelText('Line 3 account')).toBeInTheDocument()
  })

  it('gates Post on a balanced ≥2-line entry', async () => {
    const user = userEvent.setup()
    routeGet([])

    renderScreen()

    await user.click(screen.getByRole('button', { name: 'New journal entry' }))
    await screen.findByRole('heading', { name: 'New Journal Entry' })

    const postButton = () => screen.getByRole('button', { name: 'Post' })

    // Nothing keyed yet — Post is disabled.
    expect(postButton()).toBeDisabled()

    // Wait for the account options to load, then pick an account per line.
    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    await selectAccount(user, 'Line 1 account', '1000 — Cash')
    await selectAccount(user, 'Line 2 account', '4000 — Sales')

    // One-sided so far (debit only) — still unbalanced, Post disabled.
    await user.type(screen.getByLabelText('Line 1 debit'), '100')
    expect(postButton()).toBeDisabled()

    // Credit the offsetting line the same amount — now balanced, Post enabled.
    await user.type(screen.getByLabelText('Line 2 credit'), '100')
    await waitFor(() => expect(postButton()).toBeEnabled())

    // Break the balance — Post disables again.
    await user.clear(screen.getByLabelText('Line 2 credit'))
    await user.type(screen.getByLabelText('Line 2 credit'), '50')
    await waitFor(() => expect(postButton()).toBeDisabled())

    // Restore balance and post — the payload is sent to the create endpoint.
    mockPost.mockResolvedValue({ data: { id: 'je-new' } })
    await user.clear(screen.getByLabelText('Line 2 credit'))
    await user.type(screen.getByLabelText('Line 2 credit'), '100')
    await waitFor(() => expect(postButton()).toBeEnabled())
    await user.click(postButton())

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/syerp/gl/journal-entries',
        expect.objectContaining({
          lines: [
            { account_id: 1000, debit: '100' },
            { account_id: 4000, credit: '100' },
          ],
        }),
      )
    })
  })
})
