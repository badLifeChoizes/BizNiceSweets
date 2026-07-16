// ABOUTME: CRUMB communications timeline (/crumb/communications) — placeholder stub. Fleshed
// ABOUTME: out in a later task; renders CrumbNav so the module sub-nav is wired now.
import { CrumbNav } from './components/CrumbNav'

export function Communications() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-xl font-semibold text-foreground">Communications</h1>
    </div>
  )
}
