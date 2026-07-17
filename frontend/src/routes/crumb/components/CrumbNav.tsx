// ABOUTME: CRUMB (CRM) sub-navigation tab strip (copies MousseNav) — lets users move
// ABOUTME: between the module's screens: Leads, Pipeline, Quotes, Sales Orders, Communications.

/**
 * CrumbNav — sub-navigation tab strip for the CRUMB (CRM) module screens.
 *
 * The left sidebar only exposes the CRUMB module root (which redirects to Leads),
 * so this strip lets users move between the module's screens without typing URLs.
 * Mirrors routes/mousse/components/MousseNav.tsx.
 *
 * Rendered at the top of each CRUMB screen. Uses NavLink so the active screen is
 * highlighted automatically from the current route.
 */
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS: Array<{ to: string; label: string; end?: boolean }> = [
  { to: '/crumb/leads', label: 'Leads' },
  { to: '/crumb/opportunities', label: 'Pipeline' },
  { to: '/crumb/quotes', label: 'Quotes' },
  { to: '/crumb/sales-orders', label: 'Sales Orders' },
  { to: '/crumb/communications', label: 'Communications' },
]

export function CrumbNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="CRUMB sections">
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
