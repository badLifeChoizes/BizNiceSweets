/**
 * Home — neutral post-login landing screen (D-06).
 *
 * Default route at / inside the AppShell. Shows a welcome message and
 * prompts the user to select a module. If the user has no visible modules
 * (none enabled or none they have permission for), shows the D-05 empty state
 * with the exact UI-SPEC copy.
 *
 * Low complexity: no mutations, no data fetching beyond useAuth and useModules
 * (already fetched in AppShell — cache hit, no extra network request).
 */

import { useAuth } from '@/hooks/useAuth'
import { useModules } from '@/hooks/useModules'
import { useVisibleModules } from '@/components/AppShell'

export function Home() {
  const { user } = useAuth()
  const { data: modules = [] } = useModules()

  // Compute visible modules (same logic as AppShell; cache hit — no re-fetch)
  const visibleModules = useVisibleModules(user, modules)

  if (visibleModules.length === 0) {
    // D-05 empty state
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <h1 className="text-xl font-semibold text-foreground">No modules available</h1>
        <p className="text-sm font-normal text-muted-foreground max-w-sm text-center">
          No modules are enabled for your account. Contact your administrator to request access.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4 py-8 px-4">
      <h1 className="text-3xl font-semibold text-foreground">Welcome to BizNiceSweets</h1>
      <p className="text-sm font-normal text-muted-foreground">
        Select a module from the sidebar to get started.
      </p>
    </div>
  )
}
