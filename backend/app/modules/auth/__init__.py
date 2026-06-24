"""
Auth module — self-registration (mirrors syerp/__init__.py).

Importing this package:
  1. Defines MODULE_NAME = "auth".
  2. Imports the auth router (satisfies Module Protocol).
  3. Calls registry.register() so the router is mounted under /api/v1/auth
     by mount_all() in app/main.py.

See backend/app/core/registry.py for the Module Protocol definition.
"""
import sys

from app.core import registry
from app.modules.auth.router import router  # noqa: F401

MODULE_NAME = "auth"

registry.register(sys.modules[__name__])
