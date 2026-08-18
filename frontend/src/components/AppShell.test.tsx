// ABOUTME: Probe for getVisibleModules (AppShell.tsx) — the sidebar nav filter behind
// ABOUTME: CORE-05/CORE-07 and SC6's GELATO-off check, which nothing tested before this.
// ABOUTME: Covers enabled ∩ permitted, the admin wildcard, disabled-module exclusion,
// ABOUTME: a permitted-but-disabled module, a missing <key>:read, and the null user.

/**
 * getVisibleModules — pure-function unit tests (Phase 5, Task 10, SC3).
 *
 * WHY THIS EXISTS
 *   The pre-flight map (.zj/phases/05-human-uat/PREFLIGHT.md) found this to be the one
 *   genuinely `machine-unproven` surface worth probing: a pure function with real
 *   branching logic (enabled ∩ permitted, plus an admin wildcard short-circuit) and zero
 *   coverage, sitting behind THREE separate UAT checks — CORE-05 (RBAC nav filtering),
 *   CORE-07 / C-SC6-d (module-toggle propagation), and the GELATO-off degraded path. The
 *   other machine-unproven rows are pure appearance or FE wiring, which a mocked render
 *   cannot reach and which are the human residue by definition.
 *
 * WHAT IS DELIBERATELY NOT ASSERTED
 *   Nothing here renders <AppShell/>. The auth-guard branches (spinner / redirect /
 *   Outlet) are already covered by src/auth/ProtectedRoute.test.tsx, and the *appearance*
 *   of the sidebar is human residue. This file pins the DECISION, not the paint.
 *
 * THE ORDER OF THE TWO RULES IS LOAD-BEARING
 *   `enabled` is checked BEFORE the admin wildcard, so a disabled module is hidden even
 *   from an admin. That is what makes the Settings→Modules toggle meaningful at all: if
 *   the wildcard were checked first, toggling GELATO off would change nothing for the
 *   admin who just toggled it. `mixed_admin_disabled` below is the case that fails if
 *   anyone reorders those two lines.
 */

import { describe, it, expect } from 'vitest'
import { getVisibleModules } from '@/components/AppShell'
import type { AuthUser } from '@/hooks/useAuth'
import type { ModuleRecord } from '@/hooks/useModules'

function mod(key: string, enabled: boolean, sort_order = 0): ModuleRecord {
  return {
    key,
    display_name: key.toUpperCase(),
    enabled,
    always_on: key === 'syerp',
    sort_order,
  }
}

function user(roles: string[], permissions: string[]): AuthUser {
  return {
    id: 'u1',
    email: 'probe@example.com',
    full_name: 'Probe User',
    is_active: true,
    roles: roles.map((name) => ({ name })),
    permissions,
  }
}

// The shape the UAT fixture user produces: one module-read permission, non-admin role.
const PLUM_ONLY = user(['UAT-PLUM-ONLY'], ['plum:read'])
const ADMIN = user(['admin'], ['*', 'plum:read', 'syerp:read', 'gelato:read'])

const ALL_ENABLED: ModuleRecord[] = [
  mod('syerp', true, 1),
  mod('plum', true, 2),
  mod('gelato', true, 3),
]

describe('getVisibleModules', () => {
  it('returns only enabled modules the user has <key>:read for', () => {
    expect(getVisibleModules(PLUM_ONLY, ALL_ENABLED).map((m) => m.key)).toEqual(['plum'])
  })

  it('excludes an enabled module the user lacks <key>:read for', () => {
    const visible = getVisibleModules(PLUM_ONLY, ALL_ENABLED).map((m) => m.key)
    expect(visible).not.toContain('syerp')
    expect(visible).not.toContain('gelato')
  })

  it('treats the admin role as a wildcard over enabled modules', () => {
    expect(getVisibleModules(ADMIN, ALL_ENABLED).map((m) => m.key)).toEqual([
      'syerp',
      'plum',
      'gelato',
    ])
  })

  it('excludes a disabled module even from an admin', () => {
    // The GELATO-off case (C-SC6-d). `enabled` is evaluated BEFORE the wildcard, so
    // toggling a module off hides it from the admin who toggled it. Reorder those two
    // lines in AppShell.tsx and this is the assertion that fails.
    const modules = [mod('syerp', true, 1), mod('plum', true, 2), mod('gelato', false, 3)]
    expect(getVisibleModules(ADMIN, modules).map((m) => m.key)).toEqual(['syerp', 'plum'])
  })

  it('excludes a disabled module the user does hold <key>:read for', () => {
    // Permission alone is not sufficient: enabled ∩ permitted, not enabled ∪ permitted.
    const modules = [mod('plum', false, 1)]
    expect(getVisibleModules(PLUM_ONLY, modules)).toEqual([])
  })

  it('returns nothing when there is no user', () => {
    expect(getVisibleModules(null, ALL_ENABLED)).toEqual([])
  })

  it('returns nothing when every module is disabled', () => {
    const modules = ALL_ENABLED.map((m) => ({ ...m, enabled: false }))
    expect(getVisibleModules(ADMIN, modules)).toEqual([])
    expect(getVisibleModules(PLUM_ONLY, modules)).toEqual([])
  })

  it('does not treat a write permission as read access', () => {
    // plum:write without plum:read must NOT reveal PLUM — the filter keys on :read.
    const writer = user(['editor'], ['plum:write'])
    expect(getVisibleModules(writer, ALL_ENABLED)).toEqual([])
  })

  it('preserves the input order of the modules it keeps', () => {
    // The sidebar renders in the order the API returned (sort_order applied server-side);
    // the filter must not reshuffle. A sort introduced here would silently reorder nav.
    const modules = [mod('gelato', true, 3), mod('syerp', true, 1), mod('plum', true, 2)]
    expect(getVisibleModules(ADMIN, modules).map((m) => m.key)).toEqual([
      'gelato',
      'syerp',
      'plum',
    ])
  })
})
