import { Routes, Route } from 'react-router-dom'
import { Login } from '@/routes/Login'
import { AppShell } from '@/components/AppShell'

// Admin routes
import { Users } from '@/routes/admin/Users'
import { Settings } from '@/routes/admin/Settings'
import { Modules } from '@/routes/admin/Modules'

// Home landing (neutral post-login screen — D-06)
import { Home } from '@/routes/Home'

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
      </Route>
    </Routes>
  )
}
