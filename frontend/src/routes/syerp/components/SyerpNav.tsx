/**
 * SyerpNav — sub-navigation tab strip for the SYERP module screens.
 *
 * The left sidebar only exposes the SYERP module root (which redirects to
 * Vendors), so this strip lets users move between the module's screens
 * (Vendors / Customers / Chart of Accounts) without typing URLs. Aligns with
 * decision D-02 (separate Vendor and Customer entries over the shared partner).
 *
 * Rendered at the top of each SYERP screen. Uses NavLink so the active screen
 * is highlighted automatically from the current route.
 */
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/syerp/vendors', label: 'Vendors' },
  { to: '/syerp/customers', label: 'Customers' },
  { to: '/syerp/inventory/items', label: 'Inventory Items' },
  { to: '/syerp/gl', label: 'Chart of Accounts' },
]

export function SyerpNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="SYERP sections">
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
