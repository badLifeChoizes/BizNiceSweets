/**
 * Topbar — thin top bar with company name and user/admin dropdown (D-02, D-03).
 *
 * Left:  hamburger (md:hidden) that opens the mobile drawer + company name from settings.
 * Right: DropdownMenu with user info + admin-only items + Log out.
 *
 * Company name is readable by ALL authenticated users — settings GET is
 * gated by get_current_user only, not admin (03-02 decision, Open Question 2 RESOLVED).
 *
 * Admin-only dropdown items (Settings, Modules, Users) gated on admin role (D-03, Pitfall 4).
 * Log out: POST /api/v1/auth/logout → clearAccessToken() → window.location.href='/login' (D-02).
 *
 * Accessibility: hamburger has aria-label="Open navigation" + sr-only span;
 *                user menu has aria-label="Open user menu"; decorative icons are aria-hidden.
 * Typography: font-semibold only (UI-SPEC — no font-medium).
 */

import { Menu, User } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useSettings } from '@/hooks/useSettings'
import { apiClient } from '@/api/client'
import { clearAccessToken } from '@/auth/token'
import type { AuthUser } from '@/hooks/useAuth'

interface TopbarProps {
  user: AuthUser
  onMenuClick: () => void
}

export function Topbar({ user, onMenuClick }: TopbarProps) {
  const navigate = useNavigate()
  const { data: settings = [] } = useSettings()

  const companyName =
    settings.find((s) => s.key === 'company.name')?.value ?? 'BizNiceSweets'

  const isAdmin = user.roles.some((r) => r.name === 'admin')

  async function handleLogout() {
    try {
      await apiClient.post('/api/v1/auth/logout')
    } catch {
      // Ignore logout errors — clear the token and redirect regardless
    } finally {
      clearAccessToken()
      window.location.href = '/login'
    }
  }

  // Get initials for avatar (up to 2 chars)
  const initials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : user.email.slice(0, 2).toUpperCase()

  return (
    <header className="h-12 border-b bg-background px-4 flex items-center justify-between shrink-0">
      {/* Left: hamburger (mobile only) + company name */}
      <div className="flex items-center gap-3">
        {/* Mobile hamburger — md:hidden */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden h-8 w-8"
          onClick={onMenuClick}
          aria-label="Open navigation"
        >
          <Menu className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Open navigation</span>
        </Button>

        {/* Company name — visible to all authenticated users */}
        <span className="text-sm font-semibold text-foreground">{companyName}</span>
      </div>

      {/* Right: user/admin dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-full"
            aria-label="Open user menu"
          >
            <span className="text-xs font-semibold" aria-hidden="true">
              {initials}
            </span>
            <User className="h-4 w-4 hidden" aria-hidden="true" />
            <span className="sr-only">Open user menu</span>
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-56">
          {/* User info (non-interactive) */}
          <div className="px-2 py-1.5 space-y-0.5">
            <p className="text-sm font-semibold text-foreground truncate">
              {user.full_name ?? user.email}
            </p>
            <p className="text-xs font-normal text-muted-foreground truncate">
              {user.email}
            </p>
          </div>

          <DropdownMenuSeparator />

          {/* Admin-only items (D-03) */}
          {isAdmin && (
            <>
              <DropdownMenuItem onClick={() => navigate('/settings')}>
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/settings/modules')}>
                Modules
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/admin/users')}>
                Users
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}

          {/* Log out (D-02) */}
          <DropdownMenuItem onClick={() => void handleLogout()}>
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
