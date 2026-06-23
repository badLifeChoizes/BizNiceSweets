# Phase 2: Authentication & Users - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 2-Authentication & Users
**Areas presented:** Account creation & first-admin, Session & token storage, Role model granularity, Password recovery & MFA

---

## Gray-area selection

Four phase-specific gray areas were presented for selection (multiSelect). The user responded: **"Im not sure about any of these and will leave you to your best judgement."**

All four areas were therefore resolved by Claude as reasoned builder defaults grounded in the locked project constraints (self-hosted, single-business-per-instance, modular suite, medical-device audit posture), rather than through option-by-option selection. The alternatives that were on the table for each area are recorded below for audit.

---

## Account creation & first-admin

| Option | Description | Selected |
|--------|-------------|----------|
| Open registration page | Anyone hits `/signup` | |
| Admin invites/creates users; no public signup | Closed onboarding | ✓ (Claude) |
| First admin from seed env vars | `BNS_ADMIN_EMAIL/PW` via seed hook | ✓ (Claude) |
| First-run setup wizard | UI creates first admin | |

**Resolution:** Admin-provisioned accounts, `signup_enabled=false` by default; first admin idempotently seeded from env via the existing `core/seed.py` hook. Flagged a spec divergence vs. literal "user can create an account." (CONTEXT.md D-01, D-02)

## Session & token storage

| Option | Description | Selected |
|--------|-------------|----------|
| Access in memory + refresh in httpOnly cookie | XSS-resistant | ✓ (Claude) |
| Both tokens in localStorage | Simpler, XSS-exposed | |
| Short access + sliding refresh | ~15–30m / ~7d | ✓ (Claude) |
| Rotating refresh tokens w/ reuse detection | Revoke chain on replay | ✓ (Claude) |

**Resolution:** Two-token model; access JWT in memory, refresh token in httpOnly/Secure/SameSite cookie; refresh tokens tracked server-side and revocable (so deactivation kills sessions); rotation with reuse detection. (CONTEXT.md D-03–D-07)

## Role model granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Two fixed roles: Admin / User | Hardcoded | |
| Fixed roles + per-module access flags | Module-aware | |
| Configurable roles w/ permission sets | Data-driven | ✓ (Claude) |
| Full ABAC (per-record/field) | Maximum granularity | |

**Resolution:** Permission-based RBAC with `module:action` permissions; roles as data; seed `admin` + `user`; enforce via a `require_permission(...)` FastAPI dependency. ABAC deferred. (CONTEXT.md D-08–D-11)

## Password recovery & MFA

| Option | Description | Selected |
|--------|-------------|----------|
| Admin-reset only (no email) | Always works self-hosted | ✓ (Claude) |
| Email reset link | Requires SMTP config | ✓ optional (Claude) |
| Email verification on signup | Requires SMTP | |
| TOTP MFA | Optional/required | deferred |

**Resolution:** Admin-reset is the baseline (no email dependency); email self-service reset only when SMTP configured; no signup email verification; MFA deferred. Passwords hashed with a modern KDF. (CONTEXT.md D-12, D-13)

---

## Claude's Discretion

The user delegated the entire discussion to builder judgment. In addition, these specifics are left to researcher/planner: JWT & hashing library choice, signing algorithm, exact env-var names, token TTLs within range, user↔role cardinality, frontend auth wiring (protected routes, refresh interceptor, login/admin screens), CSRF strategy, and cookie attributes. A minimal auth audit log (D-14) is included as discretionary/de-scopable.

## Deferred Ideas

- Third-party / enterprise SSO (Google, GitHub, SAML, OIDC)
- Multi-factor authentication (TOTP, WebAuthn/passkeys)
- Open public self-signup (flag exists, off by default)
- Email-based self-service password reset & email verification (behind SMTP config)
- Full cross-module audit framework (CRISP / later)
- Fine-grained / ABAC authorization
