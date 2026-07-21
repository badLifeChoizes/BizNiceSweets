/**
 * AppShell — layout route that merges auth guard and application chrome (D-01).
 *
 * Replaces the former ProtectedRoute + Landing layout. All protected routes
 * render as children via <Outlet /> inside this shell.
 *
 * Auth guard behavior (mirrors ProtectedRoute):
 *   isLoading → full-screen Loader2 spinner (no chrome rendered)
 *   !user     → Navigate to /login with state={{ from: location }}
 *   user      → render sidebar + topbar + Outlet chrome
 *
 * Nav visibility (D-04): enabled ∩ permitted
 *   admin role is wildcard — sees all enabled modules
 *   standard user — needs <key>:read permission in user.permissions[]
 *
 * UI-SPEC: flex h-screen bg-background overflow-hidden container;
 *          aside hidden md:flex md:w-64 md:flex-col;
 *          main flex-1 overflow-y-auto p-4
 */

import { useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useModules, type ModuleRecord } from '@/hooks/useModules'
import { Sidebar } from '@/components/Sidebar'
import { Topbar } from '@/components/Topbar'
import { MobileSidebar } from '@/components/MobileSidebar'
import type { AuthUser } from '@/hooks/useAuth'

/**
 * Computes which modules to show in the sidebar nav.
 * Intersects enabled modules with user permissions (D-04).
 * Admin role is wildcard — sees all enabled modules (Pitfall 4).
 */
// eslint-disable-next-line react-refresh/only-export-components -- pure helper reused by Home/SalesOrderDetail; not a component
export function getVisibleModules(user: AuthUser | null, modules: ModuleRecord[]): ModuleRecord[] {
  if (!user) return []
  return modules.filter((mod) => {
    if (!mod.enabled) return false
    // Admin role is wildcard
    if (user.roles.some((r) => r.name === 'admin')) return true
    // Standard user: must have <key>:read permission
    return user.permissions.includes(`${mod.key}:read`)
  })
}

export function AppShell() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  const { data: modules = [] } = useModules()
  const [mobileOpen, setMobileOpen] = useState(false)

  // Auth guard — replaces ProtectedRoute (Pitfall 3: merge, not nest)
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  const visibleModules = getVisibleModules(user, modules)

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop sidebar — hidden on narrow screens */}
      <aside className="hidden md:flex md:w-64 md:flex-col border-r">
        <Sidebar visibleModules={visibleModules} />
      </aside>

      {/* Main content column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar
          user={user}
          onMenuClick={() => setMobileOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-4">
          <Outlet />
        </main>
      </div>

      {/* Mobile sidebar — Sheet drawer triggered by Topbar hamburger */}
      <MobileSidebar
        open={mobileOpen}
        onOpenChange={setMobileOpen}
        visibleModules={visibleModules}
      />
    </div>
  )
}
