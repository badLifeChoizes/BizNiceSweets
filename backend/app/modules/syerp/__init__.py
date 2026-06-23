"""
SYERP — the always-on hub module (D-06).

SYERP is bundled with the platform. It is NOT optional and has NO
graceful-degradation code paths. All other modules (PLUM, FLAN, …)
may hold FK references to SYERP tables, which are always present.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so SYERP self-registers
     when app/main.py does `import app.modules.syerp`.
"""
import sys

from app.core import registry
from app.modules.syerp.router import router  # noqa: F401

MODULE_NAME = "syerp"

# Self-register with the module registry (D-06: no profile guard, no missing-
# dependency check — SYERP is always present).
registry.register(sys.modules[__name__])
