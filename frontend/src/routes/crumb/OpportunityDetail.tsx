// ABOUTME: CRUMB opportunity detail screen (/crumb/opportunities/:id) — placeholder stub.
// ABOUTME: Fleshed out in a later task; renders CrumbNav so the module sub-nav is wired now.
import { CrumbNav } from './components/CrumbNav'

export function OpportunityDetail() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-xl font-semibold text-foreground">Opportunity</h1>
    </div>
  )
}
