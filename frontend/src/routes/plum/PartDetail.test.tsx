// ABOUTME: Regression tests for PartDetail's Where-Used card labelling (PLUM-06)
// ABOUTME: — guards milestone-audit defect G1, where every parent rendered as
// ABOUTME: "Direct parent" because the label keyed off a field the API never sent.

/**
 * PartDetail — Where-Used card labelling (PLUM-06).
 *
 * Regression guard for the v1.0 milestone-audit defect G1: the card used to
 * derive its label from `via_part_number` alone, a field the backend did not
 * send, so every parent — including transitive ancestors — rendered as
 * "Direct parent" and "Indirect via {part}" was unreachable. The label and the
 * direct-first sort must both key off the `indirect` flag the API returns.
 *
 * Mirrors the apiClient-mocking pattern from PartsList.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PartDetail } from '@/routes/plum/PartDetail'

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

const PART_ID = 'part-c'

/** C is used by B directly; A contains B, so A reaches C indirectly via B. */
const WHERE_USED = [
  {
    parent_part_id: 'part-a',
    parent_part_number: 'ASM-A',
    parent_revision_id: 'rev-a',
    parent_revision_label: 'A.1',
    parent_revision_status: 'Draft',
    direct: false,
    indirect: true,
    via_part_number: 'SUB-B',
  },
  {
    parent_part_id: 'part-b',
    parent_part_number: 'SUB-B',
    parent_revision_id: 'rev-b',
    parent_revision_label: 'B.1',
    parent_revision_status: 'Draft',
    direct: true,
    indirect: false,
    via_part_number: null,
  },
]

const PART = {
  id: PART_ID,
  part_number: 'PRT-C',
  description: 'Where-used target',
  tags: [],
  revisions: [
    { id: 'rev-c', revision_label: 'C.1', status: 'Draft', is_current: true },
  ],
}

function routeFor(url: string) {
  if (url.endsWith('/where-used')) return Promise.resolve({ data: WHERE_USED })
  if (url.endsWith('/avl')) return Promise.resolve({ data: [] })
  if (url.includes('/cost')) return Promise.resolve({ data: {} })
  if (url.includes('/core/settings')) return Promise.resolve({ data: [] })
  if (url.includes(`/plum/parts/${PART_ID}`)) return Promise.resolve({ data: PART })
  return Promise.resolve({ data: [] })
}

function renderPartDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/plum/parts/${PART_ID}`]}>
        <Routes>
          <Route path="/plum/parts/:id" element={<PartDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PartDetail — Where-Used labels (PLUM-06)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => routeFor(url))
  })

  it('labels a transitive ancestor "Indirect via {part}", not "Direct parent"', async () => {
    renderPartDetail()
    expect(await screen.findByText('Indirect via SUB-B')).toBeInTheDocument()
  })

  it('labels a direct parent "Direct parent"', async () => {
    renderPartDetail()
    expect(await screen.findByText('Direct parent')).toBeInTheDocument()
  })

  it('does not label every parent as direct', async () => {
    renderPartDetail()
    await screen.findByText('Direct parent')
    expect(screen.getAllByText('Direct parent')).toHaveLength(1)
  })

  it('sorts the direct parent above the indirect ancestor', async () => {
    renderPartDetail()
    await screen.findByText('Direct parent')
    const labels = screen
      .getAllByText(/Direct parent|Indirect via/)
      .map((el) => el.textContent)
    expect(labels).toEqual(['Direct parent', 'Indirect via SUB-B'])
  })

  it('falls back to "Indirect parent" when the API omits via_part_number', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.endsWith('/where-used')) {
        return Promise.resolve({
          data: [{ ...WHERE_USED[0], via_part_number: null }],
        })
      }
      return routeFor(url)
    })
    renderPartDetail()
    expect(await screen.findByText('Indirect parent')).toBeInTheDocument()
  })
})
