/**
 * ImportExport screen — Wave 0 component smoke tests.
 *
 * Mounts the ImportExport screen with apiClient mocked, then asserts:
 *   1. The Step-1 upload zone renders ("Drop a JSON or Excel file here")
 *   2. The "Export as JSON" button is present
 *   3. The "Export as Excel" button is present
 *
 * Mirrors the pattern from PartsList.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ImportExport } from '@/routes/plum/ImportExport'

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

function renderImportExport() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/plum/import-export']}>
        <ImportExport />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ImportExport screen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the upload dropzone in step 1', () => {
    renderImportExport()

    expect(screen.getByText('Drop a JSON or Excel file here')).toBeInTheDocument()
  })

  it('renders the Export as JSON button', () => {
    renderImportExport()

    expect(screen.getByRole('button', { name: /Export as JSON/i })).toBeInTheDocument()
  })

  it('renders the Export as Excel button', () => {
    renderImportExport()

    expect(screen.getByRole('button', { name: /Export as Excel/i })).toBeInTheDocument()
  })
})
