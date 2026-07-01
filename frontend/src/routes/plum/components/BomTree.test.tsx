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
import { render, screen, waitFor } from '@testing-library/react'
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
  props: { partId: string; revisionId: string; isDraft: boolean } = {
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
})
