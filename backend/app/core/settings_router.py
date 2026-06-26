"""
Settings API router — Phase 3 (CORE-06).

Endpoints:
  GET  /core/settings         — list all global settings (any authenticated user).
                                Shell header needs company.name for every user (D-02/D-05).
  PATCH /core/settings/{key}  — update a global setting's value (admin only, D-12).
                                Uses exclude_unset semantics to avoid overwriting
                                omitted fields with None (RESEARCH Pitfall 8).

Threat mitigations applied (plan 03-02 threat register):
  T-03-05: require_permission gate on PATCH — non-admin → 403.
  T-03-06: get_current_user on GET — unauthenticated → 401.
  T-03-07: model_dump(exclude_unset=True) — PATCH never nulls omitted fields.

RESEARCH Open Question 2 RESOLVED (option a):
  GET /core/settings is any-authenticated (not admin-only). v1 settings are
  non-sensitive identity/locale defaults; the shell header must render company.name
  for every authenticated user. Writes (PATCH) stay admin-only (D-12).

mount_all() in registry.py adds /api/v1 prefix — do NOT include it here.
This router is NOT a module package and is mounted directly in main.py.
Full path: /api/v1/core/settings[/{key}]
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.settings_model import Setting
from app.core.settings_schemas import SettingRead, SettingUpdate
from app.modules.auth.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/core/settings", tags=["core"])


@router.get("", response_model=list[SettingRead])
async def list_settings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Setting]:
    """
    List all global settings (owner_id IS NULL), ordered by category then key.

    Accessible to any authenticated user (D-02/D-05: shell header reads
    company.name for all users). Unauthenticated requests receive 401 (T-03-06).
    """
    result = await db.execute(
        select(Setting)
        .where(Setting.owner_id.is_(None))
        .order_by(Setting.category, Setting.key)
    )
    return list(result.scalars().all())


@router.patch("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    data: SettingUpdate,
    admin=Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> Setting:
    """
    Update a global setting's value.

    Admin-gated (require_permission("settings:manage")); non-admin → 403 (T-03-05, D-12).
    Returns 404 if the setting key does not exist as a global setting.

    Uses model_dump(exclude_unset=True) so only fields explicitly included in the
    request body are written to the DB — omitted fields retain their current values
    (T-03-07, RESEARCH Pitfall 8).
    """
    result = await db.execute(
        select(Setting).where(
            Setting.key == key,
            Setting.owner_id.is_(None),
        )
    )
    setting = result.scalars().first()

    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    # Apply only explicitly-set fields (RESEARCH Pitfall 8 — exclude_unset=True)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(setting, field, val)

    await db.commit()
    await db.refresh(setting)
    return setting
