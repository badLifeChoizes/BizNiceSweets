# ABOUTME: Package stub for MOUSSE — the Manufacturing Execution module.
# ABOUTME: Holds the ORM models only; module self-registration (MODULE_NAME +
# ABOUTME: router import + registry.register) is deferred until the router
# ABOUTME: exists (Task 11) — registering now would break app boot.
"""
MOUSSE — Manufacturing Execution module.

Minimal package stub. Module self-registration is deliberately deferred until
the router exists (Task 11); for the moment this package only holds the ORM
models in mousse/models.py.
"""
