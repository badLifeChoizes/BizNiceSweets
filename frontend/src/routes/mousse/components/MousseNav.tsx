// ABOUTME: MOUSSE sub-navigation tab strip (copies SyerpNav) — lets users move
// ABOUTME: between the module's screens. Currently one tab: Work Orders.

/**
 * MousseNav — sub-navigation tab strip for the MOUSSE (manufacturing execution)
 * module screens.
 *
 * The left sidebar only exposes the MOUSSE module root (which redirects to Work
 * Orders), so this strip lets users move between the module's screens without
 * typing URLs. Mirrors routes/syerp/components/SyerpNav.tsx.
 *
 * Rendered at the top of each MOUSSE screen. Uses NavLink so the active screen is
 * highlighted automatically from the current route.
 */
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS: Array<{ to: string; label: string; end?: boolean }> = [
  { to: '/mousse/work-orders', label: 'Work Orders' },
]

export function MousseNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="MOUSSE sections">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
