/**
 * useAuth — TanStack Query hook for session state.
 *
 * Queries GET /api/v1/auth/me to establish session identity.
 * Returns { user, isLoading } — user is null when unauthenticated or on error.
 *
 * Key options:
 *   retry: false  — a 401 means "not logged in", not a transient error; override
 *                   the global queryClient retry:1 default (PATTERNS.md note).
 *   staleTime    — consider the session fresh for 5 minutes to avoid hammering
 *                  /auth/me on every navigation.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: Array<{ name: string }>
}

export function useAuth(): { user: AuthUser | null; isLoading: boolean } {
  const { data: user, isLoading, isError } = useQuery<AuthUser, Error>({
    queryKey: ['auth', 'me'],
    queryFn: () => apiClient.get<AuthUser>('/api/v1/auth/me').then((r) => r.data),
    retry: false, // override global retry:1 — a 401 is not a transient failure
    staleTime: 5 * 60_000,
  })

  return { user: isError ? null : (user ?? null), isLoading }
}
