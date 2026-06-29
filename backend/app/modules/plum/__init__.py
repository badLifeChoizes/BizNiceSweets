"""
PLUM — Product Lifecycle Management module.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so PLUM self-registers
     when app/main.py does `import app.modules.plum`.
"""
import sys

from app.core import registry
from app.modules.plum.router import router  # noqa: F401

MODULE_NAME = "plum"

registry.register(sys.modules[__name__])
