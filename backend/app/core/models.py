"""
Central model aggregator — the single file Alembic imports.

Alembic's env.py imports THIS module so that Base.metadata is fully
populated before autogenerate runs. Every module's models.py must be
imported here as a side effect (Pitfall 1 — empty autogenerate avoidance).

Adding a new module:
  1. Create backend/app/modules/<suite>/models.py inheriting from Base.
  2. Add an import line below in the "Phase 4+" block.
  3. The next `alembic revision --autogenerate` will discover the new tables.
"""

# Phase 1: SYERP hub stub (no concrete tables yet)
from app.modules.syerp import models as syerp_models  # noqa: F401

# Phase 2: Auth module — users, roles, permissions, refresh_tokens, audit_log
from app.modules.auth import models as auth_models  # noqa: F401

# Phase 3: Core platform — modules table (CORE-07) + settings table (CORE-06)
from app.core.modules_model import Module  # noqa: F401
from app.core.settings_model import Setting  # noqa: F401

# -------------------------------------------------------------------------
# Phase 4+: add module model imports here as each suite lands
# -------------------------------------------------------------------------
from app.modules.plum import models as plum_models  # noqa: F401
# from app.modules.flan import models as flan_models    # noqa: F401
from app.modules.mousse import models as mousse_models  # noqa: F401
from app.modules.crumb import models as crumb_models  # noqa: F401
from app.modules.gelato import models as gelato_models  # noqa: F401
# from app.modules.crisp import models as crisp_models  # noqa: F401
# -------------------------------------------------------------------------
