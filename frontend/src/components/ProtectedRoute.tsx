/**
 * ProtectedRoute — layout route that guards authenticated surfaces.
 *
 * Loading state: full-screen centered Loader2 spinner, no text (UI-SPEC Screen 2).
 * Unauthenticated: redirect to /login, preserving `location` in state so the
 *   login page can send the user back to where they tried to go.
 * Authenticated: render <Outlet /> so child routes display normally.
 *
 * RESEARCH.md Pattern 6; threat T-02-20 (UI gating is convenience only —
 * the backend require_permission("users:manage") is the real authz gate).
 */

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

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

  return <Outlet />
}
