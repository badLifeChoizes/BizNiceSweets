// ABOUTME: CRUMB quote detail screen (/crumb/quotes/:id) — placeholder stub. Fleshed out in
// ABOUTME: a later task; renders CrumbNav so the module sub-nav is wired now.
import { CrumbNav } from './components/CrumbNav'

export function QuoteDetail() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-xl font-semibold text-foreground">Quote</h1>
    </div>
  )
}
