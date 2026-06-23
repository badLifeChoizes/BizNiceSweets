"""
Lightweight module registry for BizNiceSweets.

Each module's __init__.py calls register(module_object) so that
mount_all(app) can wire every registered router into the FastAPI app
under a versioned prefix (/api/v1) at startup.

Usage (in a module __init__.py):
    from app.core import registry
    MODULE_NAME = "syerp"
    router = ...
    registry.register(sys.modules[__name__])

Usage (in app/main.py):
    from app.core.registry import mount_all
    import app.modules.syerp        # side-effect: registers itself
    ...
    mount_all(app)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fastapi import FastAPI


class Module(Protocol):
    """Protocol satisfied by every module's top-level package object."""

    router: object  # fastapi.APIRouter
    MODULE_NAME: str


_registry: list[Module] = []


def register(module: Module) -> None:
    """Add *module* to the global registry. Called by each module's __init__.py."""
    _registry.append(module)


def mount_all(app: "FastAPI", prefix: str = "/api/v1") -> None:
    """Mount all registered module routers onto *app* under *prefix*."""
    for mod in _registry:
        app.include_router(mod.router, prefix=prefix, tags=[mod.MODULE_NAME])
