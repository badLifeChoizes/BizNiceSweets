// ABOUTME: GELATO Bins screen (/gelato/bins) — STUB placeholder wiring the route so
// ABOUTME: nav resolves and the build compiles. Replaced by Phase 12a task 13.

/**
 * Bins screen — GELATO bins management (/gelato/bins).
 *
 * STUB: this is a minimal placeholder created by task 12 so App.tsx route wiring
 * resolves and `npm run build` is clean. Task 13 replaces this file with the real
 * bins list + create/edit/archive screen over the hooks in ./hooks.ts.
 */
import { GelatoNav } from '@/routes/gelato/components/GelatoNav'

export function Bins() {
  return (
    <div className="p-8 space-y-6">
      <GelatoNav />
    </div>
  )
}
