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
import { PurchaseOrderDetail } from '@/routes/syerp/PurchaseOrderDetail'
import { GLAccounts } from '@/routes/syerp/GLAccounts'
import { JournalEntries } from '@/routes/syerp/JournalEntries'
import { AccountRegister } from '@/routes/syerp/AccountRegister'
import { Bills } from '@/routes/syerp/Bills'
import { BillDetail } from '@/routes/syerp/BillDetail'
import { ApAging } from '@/routes/syerp/ApAging'
import { FinancialReports } from '@/routes/syerp/FinancialReports'

// PLUM routes (Phase 5 + 6)
import { PartsList } from '@/routes/plum/PartsList'
import { PartDetail } from '@/routes/plum/PartDetail'
import { ImportExport } from '@/routes/plum/ImportExport'

// MOUSSE routes (Phase 10)
import { WorkOrders } from '@/routes/mousse/WorkOrders'
import { WorkOrderDetail } from '@/routes/mousse/WorkOrderDetail'

// CRUMB routes (Phase 11a)
import { Leads } from '@/routes/crumb/Leads'
import { LeadDetail } from '@/routes/crumb/LeadDetail'
import { Pipeline } from '@/routes/crumb/Pipeline'
import { OpportunityDetail } from '@/routes/crumb/OpportunityDetail'
import { Quotes } from '@/routes/crumb/Quotes'
import { QuoteDetail } from '@/routes/crumb/QuoteDetail'
import { Communications } from '@/routes/crumb/Communications'

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
        {/* Keep the static `new` segment BEFORE the `/:id` detail route. */}
        <Route path="/syerp/purchasing/orders/new" element={<PurchaseOrderCreate />} />
        <Route path="/syerp/purchasing/orders/:id" element={<PurchaseOrderDetail />} />
        <Route path="/syerp/gl" element={<GLAccounts />} />
        <Route path="/syerp/gl/journal" element={<JournalEntries />} />
        <Route path="/syerp/gl/register" element={<AccountRegister />} />
        {/* Keep the static list route BEFORE the `/:id` detail route. */}
        <Route path="/syerp/ap/bills" element={<Bills />} />
        <Route path="/syerp/ap/bills/:id" element={<BillDetail />} />
        <Route path="/syerp/ap/aging" element={<ApAging />} />
        <Route path="/syerp/reports" element={<FinancialReports />} />

        {/* PLUM module routes — Sidebar nav lands on /plum → redirect to parts list */}
        <Route path="/plum" element={<Navigate to="/plum/parts" replace />} />
        <Route path="/plum/parts" element={<PartsList />} />
        <Route path="/plum/parts/:id" element={<PartDetail />} />
        <Route path="/plum/import-export" element={<ImportExport />} />

        {/* MOUSSE module routes — Sidebar nav lands on /mousse → redirect to work orders */}
        <Route path="/mousse" element={<Navigate to="/mousse/work-orders" replace />} />
        <Route path="/mousse/work-orders" element={<WorkOrders />} />
        <Route path="/mousse/work-orders/:id" element={<WorkOrderDetail />} />

        {/* CRUMB module routes — Sidebar nav lands on /crumb → redirect to leads list */}
        <Route path="/crumb" element={<Navigate to="/crumb/leads" replace />} />
        <Route path="/crumb/leads" element={<Leads />} />
        <Route path="/crumb/leads/:id" element={<LeadDetail />} />
        <Route path="/crumb/opportunities" element={<Pipeline />} />
        <Route path="/crumb/opportunities/:id" element={<OpportunityDetail />} />
        <Route path="/crumb/quotes" element={<Quotes />} />
        <Route path="/crumb/quotes/:id" element={<QuoteDetail />} />
        <Route path="/crumb/communications" element={<Communications />} />

        {/* Catch-all: unknown protected paths fall back to Home instead of a blank screen */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
