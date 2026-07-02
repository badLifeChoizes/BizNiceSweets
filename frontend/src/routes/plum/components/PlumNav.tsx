/**
 * PlumNav — sub-navigation tab strip for the PLUM module screens.
 *
 * The left sidebar only exposes the PLUM module root (which redirects to
 * Parts), so this strip lets users move between the module's screens.
 * Phase 6 will add a "BOMs" tab when the BOM screen is built.
 *
 * Rendered at the top of each PLUM screen. Uses NavLink so the active screen
 * is highlighted automatically from the current route.
 */
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/plum/parts', label: 'Parts' },
  { to: '/plum/import-export', label: 'Import / Export' },
]

export function PlumNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="PLUM sections">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
