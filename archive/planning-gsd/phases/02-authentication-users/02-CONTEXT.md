# Phase 2: Authentication & Users - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

> **Discussion note:** The user reviewed the four gray areas (account creation & first-admin, session/token storage, role-model granularity, password recovery & MFA) and explicitly delegated all of them to builder's judgment ("leave you to your best judgement"). The decisions below are therefore Claude's reasoned defaults, grounded in the project's locked constraints: self-hosted, typically single-business-per-instance, modular suite with SYERP as the always-on hub, and a standing medical-device audit posture. They are defaults the user can override at plan/execute time, not hard user mandates.

<domain>
## Phase Boundary

Deliver secure access to the suite and admin management of who can access what. This is the auth/identity foundation every later module (Phase 3 shell, Phase 4 SYERP, Phases 5–6 PLUM) sits behind.

**Delivers (CORE-02, CORE-03, CORE-04, CORE-05):**
- Email/password login issuing a JWT via FastAPI's OAuth2 flow (CORE-02).
- A session that persists across page reloads and API calls without re-login, via access-token + refresh-token issuance and refresh (CORE-03).
- Admin screens/endpoints to create, edit, and deactivate user accounts (CORE-04).
- A role model where roles gate access to modules and actions; a user with the wrong role is denied gated resources (CORE-05).
- The first admin account, bootstrapped on a fresh deploy (consumes the Phase-1 `core/seed.py:run_seeds()` hook, D-10).

**NOT in this phase:**
- App shell / navigation / system settings / module enable-disable UI (Phase 3, CORE-06–08) — Phase 2 provides the *role/permission primitives* that Phase 3's module-toggle will consume, but not the toggle UI itself.
- Any SYERP / PLUM business feature code (Phases 4–6).
- Third-party / social SSO (Google, GitHub, SAML, OIDC providers) — deferred.
- Full cross-module audit framework (CRISP / later) — only a minimal auth/user/role audit log is in scope here (see D-14).
- Multi-factor authentication (TOTP/WebAuthn) — deferred (see Deferred Ideas).

</domain>

<decisions>
## Implementation Decisions

### Account Creation & First-Admin Bootstrap
- **D-01:** **No open public self-signup by default.** This is a self-hosted, typically single-business deployment — an internet-reachable `/signup` is a liability and doesn't fit the use case. User accounts are **admin-provisioned** (CORE-04 already requires admin create/edit/deactivate). A `signup_enabled` config flag (default `false`, `pydantic-settings` like `config.py`) leaves the door open to enable open registration later without a rewrite.
- **D-02:** **First admin is bootstrapped from environment via the existing seed hook.** Wire `seed_admin_user(db)` into `core/seed.py:run_seeds()` (the stub already names this). Reads e.g. `BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD` from settings; creates the admin idempotently (no-op if it already exists) so repeated `podman-compose up` stays safe (matches the D-09 auto-migrate-on-startup model). Exact env-var names are planner's discretion but must follow the `SecretStr`-for-secrets pattern from `config.py`.
- **⚠ Spec divergence to confirm:** ROADMAP success-criterion #1 / CORE-02 read literally as "*user* can create an account." In a single-tenant internal business suite this is interpreted as **admin-creates-the-account; the user logs in (and sets/changes their own password)** — not open self-registration. If the user actually wants open public signup, flip `signup_enabled` default and add a signup route. Flagged here per the project's "flag divergence from spec" rule.

### Session & Token Storage (CORE-03)
- **D-03:** **OAuth2 = FastAPI's OAuth2 *password* bearer flow with JWT, not third-party OAuth providers.** "OAuth2/JWT" in the requirements is satisfied by `OAuth2PasswordBearer` + a `/token` (login) endpoint returning a signed JWT. Social/enterprise SSO is explicitly out (deferred).
- **D-04:** **Two-token model.** Short-lived **access token** (stateless JWT, ~15–30 min) + longer-lived **refresh token** (~7-day sliding). Access token authorizes API calls; refresh token mints new access tokens silently so the session survives reloads without re-login.
- **D-05:** **Refresh tokens are tracked server-side and revocable** (a `refresh_token`/session table). This is required so that **deactivating a user (CORE-04) immediately kills their live sessions** and so a medical-device audit posture has a revocation surface. Stateless-only refresh would make CORE-04 deactivation soft.
- **D-06:** **Storage: access token in memory (JS), refresh token in an `httpOnly`, `Secure`, `SameSite` cookie** — the XSS-resistant default. Avoid putting the refresh token in `localStorage`. CSRF mitigation (SameSite=Strict/Lax, or a CSRF token if cross-site needs arise) is planner's discretion. If the cookie approach proves awkward against the static-served SPA (same-origin in production per D-08, which *helps* here), the fallback is access+refresh in memory with silent refresh; cookie path is preferred.
- **D-07:** **Refresh-token rotation with reuse detection** — each refresh issues a new refresh token and invalidates the prior; a replayed old token revokes the chain. Reasonable security default; planner may simplify to non-rotating revocable tokens if rotation proves heavy for Phase 2.

### Role Model / RBAC (CORE-05)
- **D-08:** **Permission-based RBAC, module+action aware, but seeded simply.** Schema: `User` ↔ `Role` (start with a single role per user; many-to-many is fine if cheap), `Role` ↔ `Permission`, where a permission is a `module:action` string (e.g. `syerp:read`, `plum:write`, `users:manage`). This directly satisfies "roles gate access to **modules and actions**" and scales to every later suite without a model change.
- **D-09:** **Seed two roles initially:** `admin` (wildcard / all permissions, incl. user & role management) and a standard `user` role (sensible read/write on business modules, no user-management). Roles being **data, not hardcoded enums**, lets Phase 3+ add/edit roles later without a migration.
- **D-10:** **Enforcement via a FastAPI dependency**, e.g. `require_permission("module:action")` (or `require_role`), applied to gated routers/endpoints. A user lacking the permission gets `403`. This is the gate that ROADMAP success-criterion #4 verifies. Module-level gating here is also what Phase 3's module enable/disable will lean on.
- **D-11:** Do **not** build full ABAC / attribute or row-level policies in Phase 2 — `module:action` RBAC is the right altitude. Finer-grained (per-record ownership, field-level) is deferred unless a later phase needs it.

### Password Handling, Recovery & MFA
- **D-12:** **Passwords hashed with a modern KDF** (argon2 or bcrypt via `passlib`/equivalent — planner's lib choice). Enforce a sane minimum policy (length floor; complexity optional). Never store or log plaintext (consistent with the `SecretStr` discipline already in `config.py`).
- **D-13:** **Recovery is admin-reset-first (no email dependency).** Because a self-hosted box may have **no SMTP configured**, the always-available path is: an admin resets/sets a user's password (or issues a one-time temp credential the user must change). **Email-based self-service reset is optional**, active only when SMTP/email is configured — gated behind config, not assumed. Email verification on signup is **not required** (accounts are admin-provisioned and therefore trusted). MFA (TOTP/WebAuthn) is **out of scope** for Phase 2 (deferred).

### Audit Trail (medical-device posture)
- **D-14:** **Include a minimal auth/identity audit log now** — the project's audit/traceability posture is a *standing* constraint ("designed for even before CRISP ships"), and the cheapest, highest-value events to start with are exactly the security events this phase creates: login success/failure, user create/edit/deactivate, role/permission change. A lightweight `audit_log` table written by the auth service is sufficient. This is **builder's-discretion and de-scopable** — if it threatens Phase 2 delivery, the planner may reduce it to the seed-the-pattern level (table + hook, like D-10 did for seeds) and defer population. Not a full cross-module audit framework.

### Claude's Discretion (delegated by user — open to planner/researcher)
- Exact JWT library (`pyjwt` vs `python-jose`), hashing lib (`passlib[bcrypt]` vs `argon2-cffi`), and token signing algorithm/secret-rotation approach — follow current FastAPI security best practice; secret via `config.py` `SecretStr` pattern.
- Exact env-var names for the admin bootstrap and JWT secret.
- Access/refresh token TTLs within the ranges in D-04.
- Whether user↔role is one-to-many or many-to-many at the schema level.
- Frontend auth implementation: protected-route wrapper for React Router, TanStack Query auth/session hooks, an Axios/fetch interceptor for silent refresh, login page + admin user-management screens (UI hint: yes — a `/gsd-ui-phase 2` design contract is available and recommended before building screens).
- CSRF strategy details given the same-origin SPA (D-08).
- Cookie attributes / domain specifics for the refresh-token cookie.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements (authoritative)
- `.planning/ROADMAP.md` §"Phase 2: Authentication & Users" — phase goal and the 4 success criteria this phase is verified against (account+login, persistent session w/ refresh, admin user CRUD/deactivate, role-gated access).
- `.planning/REQUIREMENTS.md` — CORE-02 (account + OAuth2/JWT login), CORE-03 (session persistence + token refresh), CORE-04 (admin create/edit/deactivate users), CORE-05 (roles gate modules and actions).
- `.planning/PROJECT.md` — locked tech stack (FastAPI + SQLAlchemy 2.0 + PostgreSQL; React/TS/Tailwind/shadcn; TanStack Query), self-hosted + offline constraint, open-core licensing (permissive deps only), and the medical-device **audit/traceability** posture that motivates D-14.

### Phase-1 scaffolding this phase builds on (authoritative for integration)
- `.planning/phases/01-project-scaffolding-deployment/01-CONTEXT.md` — D-02 (module-as-package layout), D-06 (SYERP always-on hub; no graceful-degradation), D-09 (auto-migrate on startup), D-10 (seed hook deferred the first admin to Phase 2). These bound how the auth module is structured and bootstrapped.
- `backend/app/core/seed.py` — the `run_seeds()` hook explicitly stubbed with a `seed_admin_user(db)` extension point for this phase (D-02 above).
- `backend/app/core/config.py` — `pydantic-settings` + `SecretStr` pattern the JWT secret and admin-bootstrap creds must follow.
- `backend/app/core/registry.py` + `backend/app/modules/syerp/__init__.py` — the module self-registration pattern the new `auth` module follows (`MODULE_NAME`, `router`, `registry.register(...)`).
- `backend/app/core/base.py` — shared SQLAlchemy 2.0 `DeclarativeBase`; all auth models (`User`, `Role`, `Permission`, refresh-token/session, `audit_log`) must inherit from it so they land in the single Alembic history.
- `backend/app/main.py` — app factory; auth router mounts via `mount_all` under `/api/v1`; note SPA static mount is same-origin in production (relevant to the D-06 cookie decision).
- `frontend/src/App.tsx`, `frontend/src/lib/queryClient.ts` — current SPA has only a Landing route; auth UI (login, protected routes, admin user mgmt) plugs in here.

### No dedicated auth spec
- No standalone auth ADR/spec exists in `docs/`. `docs/decisions.md` only lists "User/Auth" as a future phase. The decisions above are the authoritative source for this phase's auth approach.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/seed.py:run_seeds()` — ready-made, named hook (`seed_admin_user`) for the first-admin bootstrap (D-02).
- `core/config.py` `Settings` + `SecretStr` — extend with JWT secret, token TTLs, admin-bootstrap creds, and the `signup_enabled` flag.
- `core/registry.py` self-registration — the `auth` module registers exactly like SYERP does; its router mounts under `/api/v1` automatically.
- `core/base.py` `Base` — single declarative base; new auth tables autogenerate into the existing single Alembic history (Phase-1 D-03).
- Frontend: `lib/queryClient.ts` (TanStack Query) and React Router in `App.tsx` — auth/session state and protected routing build on these; no new state lib needed.

### Established Patterns
- **Module-as-package** (`backend/app/modules/<suite>/` with `models.py`/`router.py`/`schemas.py`/`service.py`): the new `backend/app/modules/auth/` follows this exactly.
- **Single Alembic history** — generate one migration adding all auth tables; do not start a per-module history.
- **Auto-migrate + idempotent seed on startup** (D-09/D-10) — admin bootstrap must be idempotent to survive repeated `podman-compose up`.
- Secrets via `SecretStr`, never logged — extend to JWT secret and passwords.

### Integration Points
- The `require_permission(...)` / auth dependency from D-10 becomes the gate that **every later module's routers** (SYERP Phase 4, PLUM Phases 5–6) will use to enforce access. Get the dependency signature and permission-string convention (`module:action`) right — it's the security integration surface for the whole milestone.
- Phase 3's module enable/disable (CORE-07) will consume this phase's **module-level permissions/roles**; keep the permission model module-aware (D-08).
- Auth is the first module to add **real tables + a real seed** to the Phase-1 skeleton — it validates that the scaffolding's migration + seed + registry path actually works end-to-end.

</code_context>

<specifics>
## Specific Ideas

- User explicitly delegated all four discussed gray areas to builder judgment; no specific "I want it like X" references were given. Decisions above are reasoned defaults aligned to the locked constraints, and are open to override at planning/execution.

</specifics>

<deferred>
## Deferred Ideas

- **Third-party / enterprise SSO** (Google, GitHub, SAML, OIDC) — out of scope; revisit if a deployment needs federated identity.
- **Multi-factor authentication** (TOTP, WebAuthn/passkeys) — deferred; D-04/D-05 token model leaves room to add it.
- **Open public self-signup** — schema/flag (`signup_enabled`) supports it (D-01) but it's off by default; enable + add signup/verification flow if a multi-tenant or community deployment ever needs it.
- **Email-based self-service password reset & email verification** — implemented only behind SMTP config (D-13); becomes default-on if/when the project assumes email is always available.
- **Full cross-module audit framework** (immutable audit trail, audit UI, retention/export for medical-device compliance) — CRISP / later milestone; Phase 2 only seeds the auth/identity slice (D-14).
- **Fine-grained / ABAC authorization** (per-record ownership, field-level, row-level security) — deferred; `module:action` RBAC is the Phase-2 altitude (D-11).

None of these block Phase 2.

</deferred>

---

*Phase: 2-Authentication & Users*
*Context gathered: 2026-06-23*
