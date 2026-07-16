# ABOUTME: Package init for CRUMB — the CRM module. Defines MODULE_NAME, imports
# ABOUTME: the router (Module Protocol), and self-registers via registry.register
# ABOUTME: so app/main.py's import_module wires it up. The ORM models live in
# ABOUTME: crumb/models.py (aggregated by app.core.models).
"""
CRUMB — CRM module.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so CRUMB self-registers
     when app/main.py does `importlib.import_module("app.modules.crumb")`.
"""
import sys

from app.core import registry
from app.modules.crumb.router import router  # noqa: F401

MODULE_NAME = "crumb"

registry.register(sys.modules[__name__])
