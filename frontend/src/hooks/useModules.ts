/**
 * useModules — TanStack Query hook for the modules list.
 *
 * Queries GET /api/v1/core/modules to get all modules with their enabled state.
 * Consumed by the sidebar nav (for filtering) and the admin Modules screen.
 *
 * Key options:
 *   staleTime: 10_000         — short staleTime so focus-refetch picks up toggle changes quickly (D-09)
 *   refetchOnWindowFocus: true — override the global false so tab-switching propagates admin changes (D-09)
 *   queryKey: ['core', 'modules'] — MUST match the Modules screen invalidation key (Pitfall 6)
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export interface ModuleRecord {
  key: string
  display_name: string
  enabled: boolean
  always_on: boolean
  sort_order: number
}

export function useModules() {
  return useQuery<ModuleRecord[], Error>({
    queryKey: ['core', 'modules'],
    queryFn: () => apiClient.get<ModuleRecord[]>('/api/v1/core/modules').then((r) => r.data),
    staleTime: 10_000,
    refetchOnWindowFocus: true, // override global false for D-09 toggle propagation
  })
}
