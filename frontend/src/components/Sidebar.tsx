/**
 * Sidebar — desktop persistent navigation (D-01, D-02, D-04).
 *
 * Renders a NavLink per visible module. Active state uses accent background
 * (bg-accent text-accent-foreground) per UI-SPEC. Inactive uses muted foreground.
 * Never compares window.location manually — uses react-router NavLink isActive.
 *
 * Accepts an optional onNavigate callback used by MobileSidebar to close the drawer.
 * Receives pre-computed visibleModules from AppShell (or MobileSidebar).
 */

import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import type { ModuleRecord } from '@/hooks/useModules'

interface SidebarProps {
  visibleModules: ModuleRecord[]
  onNavigate?: () => void
}

export function Sidebar({ visibleModules, onNavigate }: SidebarProps) {
  return (
    <nav
      className="flex flex-col gap-1 p-3 flex-1 overflow-y-auto"
      aria-label="Module navigation"
    >
      {visibleModules.map((mod) => (
        <NavLink
          key={mod.key}
          to={`/${mod.key}`}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-colors',
              isActive
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          {/* Decorative placeholder icon space; module icons can be added later */}
          <span aria-hidden="true" className="shrink-0 w-4 h-4" />
          {mod.display_name}
        </NavLink>
      ))}
    </nav>
  )
}
