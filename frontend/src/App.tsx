import { Routes, Route } from 'react-router-dom'
import { Landing } from '@/routes/Landing'
import { Login } from '@/routes/Login'
import { ProtectedRoute } from '@/components/ProtectedRoute'

// Admin routes (lazy-loaded to keep initial bundle small)
// Users.tsx is in src/routes/admin/Users.tsx
import { Users } from '@/routes/admin/Users'

export function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes — wrapped in ProtectedRoute layout */}
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Landing />} />
        <Route path="/admin/users" element={<Users />} />
      </Route>
    </Routes>
  )
}
