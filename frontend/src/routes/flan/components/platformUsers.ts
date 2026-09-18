// ABOUTME: Platform-user lookup shared by the FLAN Team screen and its member dialog —
// ABOUTME: the pool a roster member's OPTIONAL user link is chosen from (FLAN-01.4).
// ABOUTME: It is an auth endpoint, not a FLAN one, so it lives here rather than in
// ABOUTME: flan/hooks.ts, which mirrors /api/v1/flan/* and nothing else.

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

/** A platform user account, as GET /api/v1/auth/users returns it (auth's UserRead). */
export interface PlatformUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
}

/**
 * The platform's user accounts — the pool the optional member link draws from.
 *
 * `GET /api/v1/auth/users` is gated by `users:manage` (auth/router.py), so a
 * FLAN user who is not an admin gets a 403. That is not an error worth shouting
 * about: `retry: false` keeps it to one request and both callers degrade to the
 * unlinked case — the picker offers "No platform user" alone and the Team
 * screen's column falls back to the raw id. Linking is an admin affordance;
 * rostering is not, and an unlinked member is a full collaborator (roster.py).
 *
 * Both callers share the one `['auth', 'users']` key, so the list is fetched
 * once and the column and the picker always agree.
 */
export function usePlatformUsers() {
  return useQuery<PlatformUser[], Error>({
    queryKey: ['auth', 'users'],
    queryFn: () => apiClient.get<PlatformUser[]>('/api/v1/auth/users').then((r) => r.data),
    retry: false,
    staleTime: 5 * 60_000,
  })
}

/** A user's display label: their name when they have one, otherwise the email. */
export function platformUserLabel(user: PlatformUser): string {
  return user.full_name?.trim() || user.email
}
