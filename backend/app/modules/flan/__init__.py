# ABOUTME: Package init for FLAN — the Project Management module. Defines
# ABOUTME: MODULE_NAME, imports the router (Module Protocol), and self-registers
# ABOUTME: via registry.register so app/main.py's import_module wires it up. The
# ABOUTME: ORM models live in flan/models.py (aggregated by app.core.models).
"""
FLAN — Project Management module.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so FLAN self-registers
     when app/main.py does `importlib.import_module("app.modules.flan")`.
"""
import sys

from app.core import registry
from app.modules.flan.router import router  # noqa: F401

MODULE_NAME = "flan"

registry.register(sys.modules[__name__])
