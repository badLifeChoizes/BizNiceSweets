// ABOUTME: Route-table tests for the FLAN wiring added to App.tsx (v5.0 Phase 1, Task 26)
// ABOUTME: — the /flan → /flan/projects redirect, each URL-scoped project screen resolving
// ABOUTME: at the depth FlanNav expects, and the CORE-07/CORE-08 nav gate asserted the
// ABOUTME: non-vacuous way (FLAN is seeded ENABLED, so the test toggles it OFF).

/**
 * App route table — FLAN routes (FLAN-01.6, FLAN-01.7 / CORE-07, CORE-08).
 *
 * WHY THIS EXISTS
 *   Projects/Phases/Tasks/Team were built and unit-tested before anything mounted
 *   them, so all four were dead in the running app. Their own test files render the
 *   components directly and therefore cannot catch a missing — or misspelled, or
 *   wrongly-nested — <Route>. This file renders the real <App/> at a URL and asserts
 *   the screen that comes back, which is the only assertion that fails if the wiring
 *   in App.tsx regresses.
 *
 * THE PATH DEPTH IS LOAD-BEARING
 *   FlanNav derives the active section from `pathname.split('/')[4]`, i.e. it assumes
 *   `/flan/projects/:projectId/<section>`. Nesting the FLAN routes under an extra
 *   segment would still render the right screen while silently breaking the project
 *   switcher. The section-derivation itself is pinned in
 *   routes/flan/components/FlanNav.test.tsx; what THIS file pins is that App.tsx
 *   serves those screens at exactly the depth that test assumes.
 *
 * THE GATE IS ASSERTED THE OTHER WAY ROUND
 *   FLAN ships seeded `enabled=true, always_on=false`. So "enable FLAN, assert the nav
 *   item appears" would pass even against an App.tsx with no FLAN routes at all — it
 *   asserts nothing. The disabled case below is the one that has teeth: toggle FLAN
 *   OFF and the nav item must go. Same for CORE-08: a user without `flan:read` must
 *   not see it. (The filter itself is unit-tested in components/AppShell.test.tsx;
 *   here it is asserted end-to-end through the rendered sidebar.)
 *
 * Mirrors the apiClient-mock pattern of routes/flan/components/FlanNav.test.tsx.
 */

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from '@/App'
import type { AuthUser } from '@/hooks/useAuth'
import type { ModuleRecord } from '@/hooks/useModules'

// Radix Select (FlanNav's project switcher, the Tasks filters) drives itself with
// Pointer Events + scrollIntoView, which jsdom does not implement.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

// ─── Fixtures ─────────────────────────────────────────────────────────────────

/** The seeded module row, verbatim from the dev database (flan is enabled). */
const FLAN_MODULE: ModuleRecord = {
  key: 'flan',
  display_name: 'FLAN — Project Management',
  enabled: true,
  always_on: false,
  sort_order: 30,
}

const SYERP_MODULE: ModuleRecord = {
  key: 'syerp',
  display_name: 'SYERP — ERP Core',
  enabled: true,
  always_on: true,
  sort_order: 10,
}

const ADMIN: AuthUser = {
  id: 'u-admin',
  email: 'admin@example.com',
  full_name: 'Admin User',
  is_active: true,
  roles: [{ name: 'admin' }],
  permissions: ['*'],
}

/** A standard user who can read SYERP but holds no `flan:read` (CORE-08). */
const NO_FLAN_READ: AuthUser = {
  id: 'u-std',
  email: 'std@example.com',
  full_name: 'Standard User',
  is_active: true,
  roles: [{ name: 'viewer' }],
  permissions: ['syerp:read'],
}

const PROJECT = {
  id: 'P1',
  name: 'Crisis Simulator',
  key_prefix: 'CRIS',
  category: null,
  description: null,
  currency: 'USD',
  start_date: null,
  gate_date: null,
  active: true,
  tags: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

/** Renders the current pathname so the redirect is asserted on the real router. */
function LocationProbe() {
  const { pathname } = useLocation()
  return <div data-testid="pathname">{pathname}</div>
}

interface RenderOptions {
  user?: AuthUser
  modules?: ModuleRecord[]
}

function renderApp(path: string, { user = ADMIN, modules }: RenderOptions = {}) {
  const moduleList = modules ?? [SYERP_MODULE, FLAN_MODULE]
  mockGet.mockImplementation((url: string) => {
    if (url === '/api/v1/auth/me') return Promise.resolve({ data: user })
    if (url === '/api/v1/core/modules') return Promise.resolve({ data: moduleList })
    if (url === '/api/v1/flan/projects') return Promise.resolve({ data: [PROJECT] })
    // Phases / tasks / team all hang off the one project; empty lists are enough
    // to prove the screen mounted, which is what the route table is on trial for.
    if (url.startsWith('/api/v1/flan/')) return Promise.resolve({ data: [] })
    if (url === '/api/v1/auth/users') return Promise.resolve({ data: [] })
    return Promise.resolve({ data: [] })
  })

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <LocationProbe />
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  mockGet.mockReset()
})

// ─── The routes ───────────────────────────────────────────────────────────────

describe('FLAN routes', () => {
  it('redirects /flan to the projects list', async () => {
    renderApp('/flan')

    await waitFor(() => {
      expect(screen.getByTestId('pathname')).toHaveTextContent('/flan/projects')
    })
    expect(await screen.findByRole('heading', { name: 'Projects', level: 1 })).toBeInTheDocument()
  })

  it('renders the projects list at /flan/projects', async () => {
    renderApp('/flan/projects')

    expect(await screen.findByRole('heading', { name: 'Projects', level: 1 })).toBeInTheDocument()
    // The static `projects` segment must win over any `/:projectId` route — a
    // param route matching first would render Phases here instead.
    expect(screen.queryByRole('heading', { name: 'Phases', level: 1 })).not.toBeInTheDocument()
  })

  // The section segment is the 4th, which is where FlanNav.sectionFromPath reads.
  it.each([
    ['phases', 'Phases'],
    ['tasks', 'Tasks'],
    ['team', 'Team'],
  ])('renders %s at /flan/projects/:projectId/%s', async (section, heading) => {
    renderApp(`/flan/projects/P1/${section}`)

    expect(await screen.findByRole('heading', { name: heading, level: 1 })).toBeInTheDocument()
    expect(screen.getByTestId('pathname')).toHaveTextContent(`/flan/projects/P1/${section}`)
  })

  it('scopes the sub-nav tabs to the project in the URL', async () => {
    // FlanNav only renders its tab strip once :projectId resolved, so these links
    // existing is itself proof the route matched as a param route, not literally.
    renderApp('/flan/projects/P1/tasks')

    expect(await screen.findByRole('link', { name: 'Phases' })).toHaveAttribute(
      'href',
      '/flan/projects/P1/phases'
    )
    expect(screen.getByRole('link', { name: 'Team' })).toHaveAttribute(
      'href',
      '/flan/projects/P1/team'
    )
    // NavLink marks the matched tab — this is the section the URL's 4th segment names.
    expect(screen.getByRole('link', { name: 'Tasks' })).toHaveAttribute('aria-current', 'page')
  })
})

// ─── The nav gate (CORE-07 / CORE-08) ─────────────────────────────────────────

describe('FLAN sidebar nav visibility', () => {
  it('shows the FLAN nav item, pointing at the module root', async () => {
    renderApp('/')

    const navLinks = await screen.findAllByRole('link', { name: 'FLAN — Project Management' })
    // Desktop sidebar + mobile drawer both render it.
    expect(navLinks.length).toBeGreaterThan(0)
    navLinks.forEach((link) => expect(link).toHaveAttribute('href', '/flan'))
  })

  it('hides the FLAN nav item when the module is toggled off (CORE-07)', async () => {
    // The teeth of this file. FLAN is seeded ENABLED, so only the disabled case
    // can fail — "enabled ⇒ visible" would pass with no FLAN routes at all.
    renderApp('/', { modules: [SYERP_MODULE, { ...FLAN_MODULE, enabled: false }] })

    await screen.findByRole('link', { name: 'SYERP — ERP Core' })
    expect(screen.queryByRole('link', { name: 'FLAN — Project Management' })).toBeNull()
  })

  it('hides the FLAN nav item from a user without flan:read (CORE-08)', async () => {
    renderApp('/', { user: NO_FLAN_READ })

    await screen.findByRole('link', { name: 'SYERP — ERP Core' })
    expect(screen.queryByRole('link', { name: 'FLAN — Project Management' })).toBeNull()
  })
})
