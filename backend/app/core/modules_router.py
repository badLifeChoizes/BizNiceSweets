"""
Modules API router — Phase 3 (CORE-07).

Endpoints:
  GET  /core/modules         — list all modules with enabled/always_on flags.
                               Gated by get_current_user (any authenticated user).
                               The nav reads this on every refetch (D-09).
  PATCH /core/modules/{key}  — toggle a module's enabled state.
                               Gated by require_permission("settings:manage") — admin only.
                               Rejects enabled=False on always_on modules with 422 (D-08).

Threat mitigations applied (plan 03-02 threat register):
  T-03-04: always_on guard — backend 422 when enabled=False on always_on module.
  T-03-05: require_permission gate on PATCH — non-admin → 403.
  T-03-06: get_current_user on GET — unauthenticated → 401.

mount_all() in registry.py adds /api/v1 prefix — do NOT include it here.
This router is NOT a module package and is mounted directly in main.py.
Full path: /api/v1/core/modules[/{key}]
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.modules_model import Module
from app.core.modules_schemas import ModuleRead, ModuleUpdate
from app.modules.auth.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/core/modules", tags=["core"])


@router.get("", response_model=list[ModuleRead])
async def list_modules(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Module]:
    """
    List all modules with their enabled/always_on state.

    Accessible to any authenticated user — the sidebar nav reads this endpoint
    to determine which modules to display (D-09 refetch source).
    Unauthenticated requests receive 401 (T-03-06).
    """
    result = await db.execute(select(Module).order_by(Module.sort_order))
    return list(result.scalars().all())


@router.patch("/{key}", response_model=ModuleRead)
async def toggle_module(
    key: str,
    data: ModuleUpdate,
    admin=Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> Module:
    """
    Toggle a module's enabled state.

    Admin-gated (require_permission("settings:manage")); non-admin → 403 (T-03-05).
    Returns 404 if the module key does not exist.
    Returns 422 if the module has always_on=True and enabled=False is requested (D-08, T-03-04).

    The frontend Switch is disabled for always_on modules as a UX convenience only;
    this backend guard is the real enforcement (RESEARCH Pitfall 7).
    """
    result = await db.execute(select(Module).where(Module.key == key))
    mod = result.scalars().first()

    if mod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{key}' not found",
        )

    # Always-on guard (D-08 / T-03-04): backend rejects disable of platform-bundled modules.
    if mod.always_on and data.enabled is False:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Module '{key}' is always-on and cannot be disabled",
        )

    if data.enabled is not None:
        mod.enabled = data.enabled

    await db.commit()
    await db.refresh(mod)
    return mod
