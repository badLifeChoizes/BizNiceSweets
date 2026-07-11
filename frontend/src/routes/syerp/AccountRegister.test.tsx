// ABOUTME: Component tests for the SYERP Account Register screen (Phase 9a, SYERP-12
// ABOUTME: AC2) — picking an account renders its postings with a running balance, bracketed
// ABOUTME: by the period's opening and closing balances.

/**
 * AccountRegister screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GET routed by URL to the accounts list vs
 * the per-account register), then asserts:
 *   1. Selecting an account renders its posting rows and the running-balance column.
 *   2. The period's opening and closing balances are displayed.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AccountRegister } from '@/routes/syerp/AccountRegister'

// Radix Select drives its trigger with Pointer Events + scrollIntoView, which
// jsdom does not implement. Stub them so the account Select is operable here.
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

// Mock sonner toasts so nothing throws in jsdom.
vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

const ACCOUNTS = [
  { id: 1000, code: '1000', name: 'Cash', account_type: 'ASSET' },
  { id: 4000, code: '4000', name: 'Sales', account_type: 'REVENUE' },
]

// Opening 100.00 → +300.00 debit → 400.00 → -150.00 credit → 250.00 closing.
// Values are deliberately distinct so each assertion below is unambiguous.
const REGISTER = {
  account_id: 1000,
  account_code: '1000',
  account_name: 'Cash',
  opening_balance: '100.00',
  closing_balance: '250.00',
  rows: [
    {
      entry_date: '2026-07-01',
      entry_id: 'je-1',
      memo: 'Opening deposit',
      debit: '300.00',
      credit: null,
      running_balance: '400.00',
    },
    {
      entry_date: '2026-07-02',
      entry_id: 'je-2',
      memo: 'Payment',
      debit: null,
      credit: '150.00',
      running_balance: '250.00',
    },
  ],
}

// Route GET by URL: the register (checked first — its URL also contains
// "/gl/accounts") vs the accounts list.
function routeGet(register: unknown = REGISTER) {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/register')) return Promise.resolve({ data: register })
    if (url.includes('/gl/accounts')) return Promise.resolve({ data: ACCOUNTS })
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
        <AccountRegister />
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

describe('AccountRegister screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders posting rows with a running balance once an account is selected', async () => {
    const user = userEvent.setup()
    routeGet()

    renderScreen()

    // Nothing is fetched until an account is chosen.
    expect(
      screen.getByText('Select an account to view its register.'),
    ).toBeInTheDocument()

    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    await selectAccount(user, 'Account', '1000 — Cash')

    // Posting memos and the running-balance column render from the register response.
    await waitFor(() => {
      expect(screen.getByText('Opening deposit')).toBeInTheDocument()
    })
    expect(screen.getByText('Payment')).toBeInTheDocument()
    // Running balance after the first (debit) line — unique to that cell.
    expect(screen.getByText('400.00')).toBeInTheDocument()
  })

  it('displays the opening and closing balances for the period', async () => {
    const user = userEvent.setup()
    routeGet()

    renderScreen()

    await waitFor(() => expect(mockGet).toHaveBeenCalled())
    await selectAccount(user, 'Account', '1000 — Cash')

    await waitFor(() => {
      expect(screen.getByText('Opening balance: 100.00')).toBeInTheDocument()
    })
    expect(screen.getByText('Closing balance: 250.00')).toBeInTheDocument()
  })
})
