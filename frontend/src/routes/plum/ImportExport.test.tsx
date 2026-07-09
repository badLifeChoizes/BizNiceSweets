/**
 * ImportExport screen — Wave 0 component smoke tests + the SC3 cache-invalidation guard.
 *
 * Mounts the ImportExport screen with apiClient mocked, then asserts:
 *   1. The Step-1 upload zone renders ("Drop a JSON or Excel file here")
 *   2. The "Export as JSON" button is present
 *   3. The "Export as Excel" button is present
 *   4. A successful import commit invalidates ['plum','parts'] (Phase-7 SC3) —
 *      and that export/preview mutations do NOT.
 *
 * Mirrors the pattern from PartsList.test.tsx.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ImportExport } from '@/routes/plum/ImportExport'
import { apiClient } from '@/api/client'

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

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function renderImportExport(queryClient: QueryClient = makeQueryClient()) {
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

  /**
   * Phase-7 SC3 regression guard.
   *
   * Before the fix, committing an import left the Parts List showing pre-import
   * data for up to queryClient's 30s staleTime — the user had to refresh by hand.
   * The fix invalidates ['plum','parts'] in commitImportMutation.onSuccess. Nothing
   * pinned it, so deleting that line failed no test. This drives the real flow
   * (choose file -> Upload and Preview -> Confirm Import) against a real
   * QueryClient and asserts the invalidation actually fires.
   */
  describe('SC3 — Parts List cache invalidation on import commit', () => {
    const previewResponse = {
      data: { parts: [], errors: [], total_parts: 1, inserted: 1, updated: 0 },
    }
    const commitResponse = { data: { inserted: 1, updated: 0, deleted: 0 } }

    async function driveImportToCommit(queryClient: QueryClient) {
      const user = userEvent.setup()
      const { container } = renderImportExport(queryClient)

      const file = new File(['{"parts":[]}'], 'plum_export.json', { type: 'application/json' })
      const input = container.querySelector('input[type="file"]') as HTMLInputElement
      await user.upload(input, file)

      await user.click(screen.getByRole('button', { name: /Upload and Preview/i }))
      const confirm = await screen.findByRole('button', { name: /Confirm Import/i })
      await user.click(confirm)
      return user
    }

    it('invalidates the plum parts query after a successful commit', async () => {
      vi.mocked(apiClient.post)
        .mockResolvedValueOnce(previewResponse) // /import/preview
        .mockResolvedValueOnce(commitResponse) // /import/commit

      const queryClient = makeQueryClient()
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

      await driveImportToCommit(queryClient)

      await waitFor(() => {
        expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['plum', 'parts'] })
      })
    })

    it('does NOT invalidate when the commit fails', async () => {
      vi.mocked(apiClient.post)
        .mockResolvedValueOnce(previewResponse) // /import/preview succeeds
        .mockRejectedValueOnce(new Error('commit exploded')) // /import/commit fails

      const queryClient = makeQueryClient()
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

      await driveImportToCommit(queryClient)

      // The failure path must not refetch — a rejected commit made no changes.
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /Confirm Import/i })).toBeInTheDocument()
      })
      expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['plum', 'parts'] })
    })
  })
})
