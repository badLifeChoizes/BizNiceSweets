# ABOUTME: pytest conftest for the tests/auth package.
# ABOUTME: Re-exports the seeded_db fixture from conftest_helpers for auto-discovery.
"""
Auto-discovered fixtures for the tests/auth package.

Re-exports seeded_db from conftest_helpers so pytest injects it by name across
the auth test modules. Sharing via conftest (rather than a module-level import
in each test file) avoids the F811 that arose when the imported fixture name
shadowed the seeded_db test-function parameters.
"""
from tests.auth.conftest_helpers import seeded_db  # noqa: F401 (re-exported)
