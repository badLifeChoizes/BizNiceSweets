// ABOUTME: CRUMB lead detail screen (/crumb/leads/:id) — placeholder stub. Fleshed out in
// ABOUTME: a later task; renders CrumbNav so the module sub-nav is wired now.
import { CrumbNav } from './components/CrumbNav'

export function LeadDetail() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-xl font-semibold text-foreground">Lead</h1>
    </div>
  )
}
