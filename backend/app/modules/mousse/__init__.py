# ABOUTME: Package init for MOUSSE — the Manufacturing Execution module. Defines
# ABOUTME: MODULE_NAME, imports the router (Module Protocol), and self-registers
# ABOUTME: via registry.register so app/main.py's import_module wires it up. The
# ABOUTME: ORM models live in mousse/models.py (aggregated by app.core.models).
"""
MOUSSE — Manufacturing Execution module.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so MOUSSE self-registers
     when app/main.py does `importlib.import_module("app.modules.mousse")`.
"""
import sys

from app.core import registry
from app.modules.mousse.router import router  # noqa: F401

MODULE_NAME = "mousse"

registry.register(sys.modules[__name__])
