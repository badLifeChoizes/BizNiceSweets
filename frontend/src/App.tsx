import { Navigate, Routes, Route } from 'react-router-dom'
import { Login } from '@/routes/Login'
import { AppShell } from '@/components/AppShell'

// Admin routes
import { Users } from '@/routes/admin/Users'
import { Settings } from '@/routes/admin/Settings'
import { Modules } from '@/routes/admin/Modules'

// Home landing (neutral post-login screen — D-06)
import { Home } from '@/routes/Home'

// SYERP routes (Phase 4)
import { Vendors } from '@/routes/syerp/Vendors'
import { Customers } from '@/routes/syerp/Customers'
import { GLAccounts } from '@/routes/syerp/GLAccounts'

export function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes — wrapped in AppShell layout (merges auth guard + chrome) */}
      <Route element={<AppShell />}>
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/settings/modules" element={<Modules />} />
        <Route path="/admin/users" element={<Users />} />

        {/* SYERP module routes — Sidebar nav lands on /syerp → redirect to vendors list */}
        <Route path="/syerp" element={<Navigate to="/syerp/vendors" replace />} />
        <Route path="/syerp/vendors" element={<Vendors />} />
        <Route path="/syerp/customers" element={<Customers />} />
        <Route path="/syerp/gl" element={<GLAccounts />} />

        {/* Catch-all: unknown protected paths fall back to Home instead of a blank screen */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
