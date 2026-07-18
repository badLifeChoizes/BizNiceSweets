// ABOUTME: GELATO Putaway screen (/gelato/putaway) — STUB placeholder wiring the route
// ABOUTME: so nav resolves and the build compiles. Replaced by Phase 12a task 14.

/**
 * Putaway screen — GELATO directed putaway (/gelato/putaway).
 *
 * STUB: this is a minimal placeholder created by task 12 so App.tsx route wiring
 * resolves and `npm run build` is clean. Task 14 replaces this file with the real
 * unbinned-stock + putaway-suggestion + execute-putaway screen over ./hooks.ts.
 */
import { GelatoNav } from '@/routes/gelato/components/GelatoNav'

export function Putaway() {
  return (
    <div className="p-8 space-y-6">
      <GelatoNav />
    </div>
  )
}
