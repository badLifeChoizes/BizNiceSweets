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
 *
 * Also exports the client-side permission predicate:
 *   hasPermission(user, code) — the same rule the backend applies in
 *     app/modules/auth/dependencies.py::has_permission: an "admin" role is a
 *     wildcard, otherwise the flat `permissions` list must carry the code.
 *   useHasPermission(code)   — that predicate over the current session.
 *
 * This is presentation only. Hiding a control the server would refuse is a
 * courtesy, not a security boundary — the server refuses it either way (FLAN's
 * `flan:rates` omits `hourly_rate` from its responses and 403s a body that sets
 * it, whatever the UI chose to render).
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: Array<{ name: string }>
  permissions: string[] // flat permission codes e.g. ["syerp:read", "plum:write"] (D-04)
}

/**
 * Does this user hold `code`? Admin role is the wildcard, mirroring the backend.
 *
 * Same shape as AppShell's getVisibleModules check (`<key>:read` against
 * `user.permissions`), lifted here because it is needed for FIELDS as well as
 * for modules: `flan:rates` decides whether a roster member's hourly rate is
 * rendered and sent at all.
 */
export function hasPermission(user: AuthUser | null, code: string): boolean {
  if (!user) return false
  if (user.roles.some((r) => r.name === 'admin')) return true
  return user.permissions.includes(code)
}

/** hasPermission over the current session; false while /auth/me is in flight. */
export function useHasPermission(code: string): boolean {
  const { user } = useAuth()
  return hasPermission(user, code)
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
