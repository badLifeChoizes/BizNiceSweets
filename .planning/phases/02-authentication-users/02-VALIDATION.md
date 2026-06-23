---
phase: 2
slug: authentication-users
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from the Validation Architecture section of `02-RESEARCH.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + httpx/ASGITransport (async); vitest + React Testing Library (frontend) |
| **Config file** | none yet — Wave 0 installs pytest/pytest-asyncio + vitest |
| **Quick run command** | `cd backend && pytest -q tests/auth` |
| **Full suite command** | `cd backend && pytest -q && cd ../frontend && npm run test -- --run` |
| **Estimated runtime** | ~30–60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/auth` (relevant module slice)
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Task IDs reconciled to the actual 4-plan numbering (02-01..02-04). Plan 01 is the Wave 0 contract layer that creates the test harness stubs for CORE-02..CORE-05; later plans flip them from xfail to green.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | CORE-02 | T-2-PW | Passwords hashed with argon2id (pwdlib); plaintext never stored/logged | unit | `pytest -q tests/auth/test_hashing.py` | ✅ 02-01 | ⬜ pending |
| 2-01-02 | 01 | 1 | CORE-02 | T-2-JWT | JWT encode/decode round-trip with HS256 allowlist; decode rejects foreign-secret tokens | unit | `pytest -q tests/auth/test_hashing.py` | ✅ 02-01 | ⬜ pending |
| 2-02-01 | 02 | 2 | CORE-02 | T-2-LOGIN | Login with valid creds returns signed JWT + refresh cookie; bad creds → 401 | integration | `pytest -q tests/auth/test_login.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-02-02 | 02 | 2 | CORE-03 | T-2-REFRESH | Expired access token + valid refresh cookie mints new access token; session survives reload | integration | `pytest -q tests/auth/test_refresh.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-02-03 | 02 | 2 | CORE-03 | T-2-ROTATE | Refresh-token rotation invalidates prior token; replayed old token revokes chain | integration | `pytest -q tests/auth/test_refresh_rotation.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-03-01 | 03 | 3 | CORE-04 | T-2-BOOT | First-admin seed is idempotent across repeated startups | unit | `pytest -q tests/auth/test_seed_admin.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-03-02 | 03 | 3 | CORE-04 | T-2-DEACT | Admin can create/edit/deactivate users; deactivation revokes live refresh tokens | integration | `pytest -q tests/auth/test_user_admin.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-03-03 | 03 | 3 | CORE-05 | T-2-RBAC | `require_permission("module:action")` returns 403 for missing permission, 200 when granted | integration | `pytest -q tests/auth/test_rbac.py` | ✅ 02-01 (stub) | ⬜ pending |
| 2-04-01 | 04 | 4 | CORE-02/03/04/05 | — | Protected route redirects unauthenticated user to login; login + silent refresh keep session | component | `npm run test -- --run src/auth` | ❌ W0 (plan 04) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest`, `pytest-asyncio`, `httpx` installed in backend (no test framework wired yet from Phase 1)
- [ ] `backend/tests/conftest.py` — async DB session + test-client fixtures (transaction-rollback per test)
- [ ] `backend/tests/auth/` — test module stubs for CORE-02…CORE-05
- [ ] `vitest` + `@testing-library/react` installed in frontend; `frontend/src/auth/*.test.tsx` stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| httpOnly/Secure/SameSite cookie attributes set correctly in a real browser | CORE-03 | Browser cookie jar behavior (Secure flag, SameSite) is environment-dependent and not fully observable from ASGI tests | In a deployed dev build, log in and inspect DevTools → Application → Cookies: refresh cookie is HttpOnly, Secure (prod), SameSite set |
| End-to-end silent refresh across a real page reload | CORE-03 | Full SPA reload + interceptor timing is integration-level browser behavior | Log in, wait past access-token TTL (or shorten TTL), reload page and make an API call — no re-login prompt |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
