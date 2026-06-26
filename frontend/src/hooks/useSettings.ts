/**
 * useSettings — TanStack Query hook for the settings list.
 *
 * Queries GET /api/v1/core/settings to get all global settings.
 * Readable by any authenticated user (D-02 company name in header for non-admins).
 * Consumed by Topbar (company name) and the admin Settings screen.
 *
 * queryKey: ['core', 'settings'] — MUST match the Settings screen invalidation key
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export interface SettingRecord {
  key: string
  value: string | null
  value_type: string
  category: string
  scope: string
  description: string | null
}

export function useSettings() {
  return useQuery<SettingRecord[], Error>({
    queryKey: ['core', 'settings'],
    queryFn: () => apiClient.get<SettingRecord[]>('/api/v1/core/settings').then((r) => r.data),
  })
}
