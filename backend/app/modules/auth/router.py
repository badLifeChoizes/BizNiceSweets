"""
Auth module router.

Minimal stub for plan 02-01.  The router self-registers under /api/v1/auth
(mount_all in registry.py adds the /api/v1 prefix — do NOT add it here).

Endpoints wired in plan 02-02:
  POST /auth/login    — OAuth2 password flow; issues JWT + refresh cookie
  POST /auth/refresh  — rotates refresh token; issues new access token
  POST /auth/logout   — revokes refresh token
  GET  /auth/me       — current user info

Endpoints wired in plan 02-03:
  POST   /auth/users       — admin: create user
  GET    /auth/users       — admin: list users
  GET    /auth/users/{id}  — admin: get user
  PATCH  /auth/users/{id}  — admin: update/deactivate user
  GET    /auth/roles       — admin: list roles
"""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# Endpoints added in subsequent plans (02-02, 02-03).
# Router is importable now so the module self-registers and the OpenAPI schema
# includes the /auth tag from the first startup.
