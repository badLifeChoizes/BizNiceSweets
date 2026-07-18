// ABOUTME: GELATO sub-navigation tab strip (copies MousseNav) — lets users move
// ABOUTME: between the module's screens: Bins and Putaway.

/**
 * GelatoNav — sub-navigation tab strip for the GELATO (warehouse management)
 * module screens.
 *
 * The left sidebar only exposes the GELATO module root (which redirects to Bins),
 * so this strip lets users move between the module's screens without typing URLs.
 * Mirrors routes/mousse/components/MousseNav.tsx.
 *
 * Rendered at the top of each GELATO screen. Uses NavLink so the active screen is
 * highlighted automatically from the current route.
 */
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS: Array<{ to: string; label: string; end?: boolean }> = [
  { to: '/gelato/bins', label: 'Bins' },
  { to: '/gelato/putaway', label: 'Putaway' },
]

export function GelatoNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="GELATO sections">
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
