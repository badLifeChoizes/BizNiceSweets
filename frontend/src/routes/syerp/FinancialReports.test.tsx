// ABOUTME: Component tests for the SYERP Financial Reports screen (Phase 09c, SYERP-13) —
// ABOUTME: each report endpoint is mocked, then the Trial Balance / P&L / Balance Sheet tabs
// ABOUTME: are asserted to render their rows, section totals, net income, and balance state.

/**
 * FinancialReports screen — component tests.
 *
 * Mounts the screen with apiClient mocked (GETs routed by URL), then asserts:
 *   1. Trial Balance tab renders account rows and a balanced totals footer.
 *   2. Switching to the P&L tab renders revenue/expense lines and net income.
 *   3. Switching to the Balance Sheet tab renders assets/liabilities/equity and a
 *      balanced total.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { FinancialReports } from '@/routes/syerp/FinancialReports'

// Mock the axios apiClient module.
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
const mockGet = vi.mocked(apiClient.get)

const TRIAL_BALANCE = {
  as_of: '2026-07-12',
  rows: [
    { account_id: 100, code: '1000', name: 'Cash', account_type: 'ASSET', debit: '500.00', credit: '0.00' },
    { account_id: 400, code: '4000', name: 'Sales Revenue', account_type: 'REVENUE', debit: '0.00', credit: '500.00' },
  ],
  total_debit: '500.00',
  total_credit: '500.00',
  in_balance: true,
}

const PROFIT_LOSS = {
  date_from: '2026-01-01',
  date_to: '2026-07-12',
  revenue: [{ account_id: 400, code: '4000', name: 'Sales Revenue', amount: '500.00' }],
  total_revenue: '500.00',
  expense: [{ account_id: 600, code: '6000', name: 'Office Supplies', amount: '120.00' }],
  total_expense: '120.00',
  net_income: '380.00',
}

const BALANCE_SHEET = {
  as_of: '2026-07-12',
  assets: [{ account_id: 100, code: '1000', name: 'Cash', amount: '900.00' }],
  total_assets: '900.00',
  liabilities: [{ account_id: 200, code: '2000', name: 'Accounts Payable', amount: '300.00' }],
  total_liabilities: '300.00',
  equity: [
    { account_id: 300, code: '3000', name: 'Owner Equity', amount: '220.00' },
    { account_id: 390, code: '3900', name: 'Current Year Net Income', amount: '380.00' },
  ],
  total_equity: '600.00',
  in_balance: true,
}

// Route every GET by URL so query ordering does not matter.
function mockGets() {
  mockGet.mockImplementation((url: string) => {
    if (url.includes('trial-balance')) return Promise.resolve({ data: TRIAL_BALANCE })
    if (url.includes('profit-loss')) return Promise.resolve({ data: PROFIT_LOSS })
    if (url.includes('balance-sheet')) return Promise.resolve({ data: BALANCE_SHEET })
    return Promise.reject(new Error(`unexpected GET ${url}`))
  })
}

function renderReports() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <FinancialReports />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FinancialReports screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Trial Balance tab with account rows and a balanced totals footer', async () => {
    mockGets()

    renderReports()

    expect(screen.getByRole('heading', { name: 'Financial Reports' })).toBeInTheDocument()

    // Account rows.
    expect(await screen.findByText('Cash')).toBeInTheDocument()
    expect(screen.getByText('Sales Revenue')).toBeInTheDocument()

    // Totals footer with the balanced indicator.
    expect(screen.getByText('Totals')).toBeInTheDocument()
    expect(screen.getAllByText('500.00').length).toBeGreaterThan(0)
    expect(screen.getByText('Balanced')).toBeInTheDocument()
  })

  it('renders the Profit & Loss tab with revenue/expense lines and net income', async () => {
    const user = userEvent.setup()
    mockGets()

    renderReports()
    await screen.findByText('Cash') // wait for the initial tab to settle

    await user.click(screen.getByRole('tab', { name: 'Profit & Loss' }))

    expect(await screen.findByText('Revenue')).toBeInTheDocument()
    expect(screen.getByText('Total Revenue')).toBeInTheDocument()
    expect(screen.getByText('Expenses')).toBeInTheDocument()
    expect(screen.getByText('Total Expenses')).toBeInTheDocument()
    expect(screen.getByText('Office Supplies')).toBeInTheDocument()

    // Net Income line + value.
    expect(screen.getByText('Net Income')).toBeInTheDocument()
    expect(screen.getByText('380.00')).toBeInTheDocument()
  })

  it('renders the Balance Sheet tab with assets/liabilities/equity and a balanced total', async () => {
    const user = userEvent.setup()
    mockGets()

    renderReports()
    await screen.findByText('Cash')

    await user.click(screen.getByRole('tab', { name: 'Balance Sheet' }))

    expect(await screen.findByText('Assets')).toBeInTheDocument()
    expect(screen.getByText('Total Assets')).toBeInTheDocument()
    expect(screen.getByText('Liabilities')).toBeInTheDocument()
    expect(screen.getByText('Total Liabilities')).toBeInTheDocument()
    expect(screen.getByText('Equity')).toBeInTheDocument()
    expect(screen.getByText('Total Equity')).toBeInTheDocument()

    // The API's computed current-year net income line appears under equity.
    expect(screen.getByText('Current Year Net Income')).toBeInTheDocument()

    // Balanced Assets == Liabilities + Equity indicator.
    const balanceRow = screen.getByText('Assets vs. Liabilities + Equity').closest('div')!
    expect(within(balanceRow).getByText('Balanced')).toBeInTheDocument()
  })
})
