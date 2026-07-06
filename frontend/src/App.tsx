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
import { InventoryItems } from '@/routes/syerp/InventoryItems'
import { InventoryItemDetail } from '@/routes/syerp/InventoryItemDetail'
import { StockLocations } from '@/routes/syerp/StockLocations'
import { PurchaseOrders } from '@/routes/syerp/PurchaseOrders'
import { PurchaseOrderCreate } from '@/routes/syerp/PurchaseOrderCreate'
import { GLAccounts } from '@/routes/syerp/GLAccounts'

// PLUM routes (Phase 5 + 6)
import { PartsList } from '@/routes/plum/PartsList'
import { PartDetail } from '@/routes/plum/PartDetail'
import { ImportExport } from '@/routes/plum/ImportExport'

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
        <Route path="/syerp/inventory/items" element={<InventoryItems />} />
        <Route path="/syerp/inventory/items/:id" element={<InventoryItemDetail />} />
        <Route path="/syerp/inventory/locations" element={<StockLocations />} />
        <Route path="/syerp/purchasing/orders" element={<PurchaseOrders />} />
        {/* Keep the static `new` segment BEFORE any future `/:id` detail route. */}
        <Route path="/syerp/purchasing/orders/new" element={<PurchaseOrderCreate />} />
        <Route path="/syerp/gl" element={<GLAccounts />} />

        {/* PLUM module routes — Sidebar nav lands on /plum → redirect to parts list */}
        <Route path="/plum" element={<Navigate to="/plum/parts" replace />} />
        <Route path="/plum/parts" element={<PartsList />} />
        <Route path="/plum/parts/:id" element={<PartDetail />} />
        <Route path="/plum/import-export" element={<ImportExport />} />

        {/* Catch-all: unknown protected paths fall back to Home instead of a blank screen */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
