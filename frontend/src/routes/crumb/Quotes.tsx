// ABOUTME: CRUMB quotes list screen (/crumb/quotes) — placeholder stub. Fleshed out in
// ABOUTME: a later task; renders CrumbNav so the module sub-nav is wired now.
import { CrumbNav } from './components/CrumbNav'

export function Quotes() {
  return (
    <div className="p-8 space-y-6">
      <CrumbNav />
      <h1 className="text-xl font-semibold text-foreground">Quotes</h1>
    </div>
  )
}
