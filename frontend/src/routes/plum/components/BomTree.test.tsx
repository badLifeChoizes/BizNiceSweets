/**
 * BomTree component — smoke tests (Phase 6, Plan 04).
 *
 * Mounts BomTree with apiClient.get mocked, then asserts:
 *   1. Empty state renders when API returns no children
 *   2. A child row is rendered when API returns one node
 *
 * Mirrors the pattern from PartsList.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BomTree } from '@/routes/plum/components/BomTree'

// Mock the axios apiClient module
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

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

function renderBomTree(
  props: {
    partId: string
    revisionId: string
    isDraft: boolean
    rollupCost?: number | string | null
  } = {
    partId: 'p1',
    revisionId: 'r1',
    isDraft: true,
  },
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BomTree {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('BomTree component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when API returns no children', async () => {
    // Tree query returns empty array
    mockGet.mockResolvedValueOnce({ data: [] })

    renderBomTree()

    await waitFor(() => {
      expect(screen.getByText('No parts added yet.')).toBeInTheDocument()
    })
    expect(
      screen.getByText('Add child parts to build a bill of materials for this revision.'),
    ).toBeInTheDocument()
  })

  it('renders a child row when API returns one BOM node', async () => {
    const bomNode = {
      bom_item_id: 'bom-1',
      child_part_id: 'part-2',
      child_part_number: 'P00002',
      child_revision_label: 'A',
      child_revision_status: 'released',
      quantity: 2,
      reference_designators: 'R1, C4',
      effective_cost: 1.5,
      effective_cost_source: 'manual',
      is_unreleased: false,
      unit_of_measure: 'ea',
      description: 'Resistor 10k',
      children: [],
    }
    // Tree query returns one node
    mockGet.mockResolvedValueOnce({ data: [bomNode] })

    renderBomTree()

    await waitFor(() => {
      expect(screen.getByText('P00002')).toBeInTheDocument()
    })
    // Revision label shown
    expect(screen.getByText('A')).toBeInTheDocument()
    // Quantity shown (the quantity span contains "2" + "ea" child)
    expect(screen.getAllByText(/2/).length).toBeGreaterThan(0)
    // tree role present
    expect(screen.getByRole('tree', { name: 'Bill of Materials' })).toBeInTheDocument()
  })

  // Milestone-audit gap D1: the flat "Total BOM Cost" footer used to sum the
  // extended_cost of every flat row. Because the flat view includes
  // sub-assemblies alongside their children, that double-counts nested material
  // (110 + 110 + 60 = 280 for the audit fixture). The footer must instead show
  // the revision's rolled-up cost (110), passed in as `rollupCost`.
  it('flat footer shows the rolled-up cost, not the sum of the rows', async () => {
    const flatRows = [
      { child_part_id: 'p-leaf', part_number: 'P100001', description: 'leaf',
        total_qty: '44', unit_of_measure: 'ea', effective_cost: '2.5', extended_cost: '110' },
      { child_part_id: 'p-sub1', part_number: 'P100002', description: 'sub',
        total_qty: '11', unit_of_measure: 'ea', effective_cost: '10', extended_cost: '110' },
      { child_part_id: 'p-sub2', part_number: 'P100003', description: 'sub',
        total_qty: '3', unit_of_measure: 'ea', effective_cost: '20', extended_cost: '60' },
    ]
    // First get = tree (unused here), second get = flat rows.
    mockGet.mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: flatRows })

    const user = userEvent.setup()
    renderBomTree({ partId: 'p1', revisionId: 'r1', isDraft: true, rollupCost: '110' })

    await user.click(await screen.findByRole('button', { name: 'Flat' }))
    await screen.findByText('P100001')

    // The footer cell shows the roll-up (110.0000), not the naive sum (280).
    // Scope to the footer row: 110.0000 also appears as a row's extended cost.
    const footerRow = screen.getByText('Total BOM Cost').closest('tr')!
    expect(within(footerRow).getByText('110.0000')).toBeInTheDocument()
    expect(screen.queryByText('280.0000')).not.toBeInTheDocument()
  })

  it('flat footer shows an em dash when no rolled-up cost is available', async () => {
    const flatRows = [
      { child_part_id: 'p-leaf', part_number: 'P100001', description: 'leaf',
        total_qty: '44', unit_of_measure: 'ea', effective_cost: '2.5', extended_cost: '110' },
    ]
    mockGet.mockResolvedValueOnce({ data: [] }).mockResolvedValueOnce({ data: flatRows })

    const user = userEvent.setup()
    renderBomTree({ partId: 'p1', revisionId: 'r1', isDraft: true, rollupCost: null })

    await user.click(await screen.findByRole('button', { name: 'Flat' }))
    await screen.findByText('P100001')
    // Footer shows an em dash (no rollup), not the naive row sum.
    const footerRow = screen.getByText('Total BOM Cost').closest('tr')!
    expect(within(footerRow).getByText('—')).toBeInTheDocument()
    expect(within(footerRow).queryByText('110.0000')).not.toBeInTheDocument()
  })
})
