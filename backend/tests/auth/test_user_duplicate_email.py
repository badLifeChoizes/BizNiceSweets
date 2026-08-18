# ABOUTME: Pins UAT defect U1 (v4.0 Phase 5) — creating a user with an existing email
# ABOUTME: returned HTTP 500 from an unhandled ix_users_email UniqueViolationError. Asserts
# ABOUTME: a clean 409 with an actionable message, that no partial row or audit row lands,
# ABOUTME: that the narrowing rejects a NON-email IntegrityError (so an unrelated
# ABOUTME: constraint can never be reported as a duplicate email), and that the edit path
# ABOUTME: still cannot change an email — the second route to the same defect.
"""
Pins UAT defect U1 (v4.0 Phase 5) — duplicate-email user creation must not 500.

WHAT U1 WAS
  `users.email` is UNIQUE (``ix_users_email``) but nothing guarded it, so creating a
  second user with an existing address raised an unhandled
  ``sqlalchemy.exc.IntegrityError`` / ``asyncpg UniqueViolationError`` and the endpoint
  answered **HTTP 500** — on a perfectly ordinary operator mistake. Found by the Phase-5
  pre-flight (SC3) before any human clicked, and the same shape as the v1.0 **D2** defect
  (a 500 when re-adding an already-linked AVL vendor) that this UAT was told to weight
  its checks toward.

WHAT IS PINNED
  1. The first create still succeeds (201) — the guard must not break the happy path.
  2. The duplicate create returns **409** with an actionable message, matching the house
     convention for a caller-supplied unique key (partners / items / locations / parts).
  3. It is not merely non-500: any 5xx fails loudly, so a future refactor that swaps one
     unhandled exception for another cannot pass.
  4. **NOTHING is persisted** — still exactly one row for that address, still carrying the
     FIRST request's full_name, and no second ``user.created`` audit row.
  5. The narrowing itself: ``_is_duplicate_email_violation`` must reject an IntegrityError
     that is NOT an ``ix_users_email`` violation, so an unrelated constraint failure can
     never be reported to the operator as a duplicate email. `users` carries TWO unique
     indexes (``users_pkey`` and ``ix_users_email``), and the Phase-13 lesson —
     create_invoice copying create_bill's broad ``except IntegrityError`` and misreading an
     FK error as a number collision, recursing until it 500'd — is exactly what a broad
     handler here would reproduce.
"""
import httpx
import pytest
import sqlalchemy.exc
from sqlalchemy import func, select

from app.core.db import AsyncSessionLocal
from app.modules.auth.models import AuditLog, User
from app.modules.auth.service import _is_duplicate_email_violation
from tests.auth.conftest_helpers import admin_login_token

_DUP_EMAIL = "u1-duplicate@test.example"


async def test_duplicate_email_create_returns_409_not_500(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """U1: the second create with the same email is a clean 409, never a 5xx."""
    token = await admin_login_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/api/v1/auth/users",
        json={"email": _DUP_EMAIL, "password": "securepass123", "full_name": "First Wins"},
        headers=headers,
    )
    assert first.status_code == 201, f"the happy path regressed: {first.status_code} {first.text}"

    second = await client.post(
        "/api/v1/auth/users",
        json={"email": _DUP_EMAIL, "password": "otherpass456", "full_name": "Second Loses"},
        headers=headers,
    )

    # The defect signature was 500. Assert the absence of ANY 5xx explicitly, so that
    # swapping one unhandled exception for another cannot slip through.
    assert second.status_code < 500, (
        f"U1 regressed: duplicate-email create returned {second.status_code} "
        f"(a 5xx means the IntegrityError is unhandled again). Body: {second.text}"
    )
    assert second.status_code == 409, (
        f"expected 409 Conflict per the house convention for a caller-supplied unique "
        f"key; got {second.status_code}. Body: {second.text}"
    )
    detail = second.json()["detail"]
    assert _DUP_EMAIL in detail, f"the message must name the offending address; got {detail!r}"
    assert "already exists" in detail, (
        f"message form should match partners/items/locations ('… already exists.'); "
        f"got {detail!r}"
    )


async def test_duplicate_email_create_persists_nothing(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """U1: the rejected create leaves no partial row and does not overwrite the original."""
    token = await admin_login_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    email = "u1-nopartial@test.example"

    created = await client.post(
        "/api/v1/auth/users",
        json={"email": email, "password": "securepass123", "full_name": "Original Name"},
        headers=headers,
    )
    assert created.status_code == 201

    async with AsyncSessionLocal() as session:
        audit_before = (
            await session.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "user.created", AuditLog.detail.contains(email))
            )
        ).scalar()

    rejected = await client.post(
        "/api/v1/auth/users",
        json={"email": email, "password": "otherpass456", "full_name": "Should Not Land"},
        headers=headers,
    )
    assert rejected.status_code == 409

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(select(User).where(User.email == email))
        ).scalars().all()
    assert len(rows) == 1, f"expected exactly one row for {email}, found {len(rows)}"
    assert rows[0].full_name == "Original Name", (
        "the rejected create must not have overwritten the existing user "
        f"(full_name is {rows[0].full_name!r})"
    )

    async with AsyncSessionLocal() as session:
        audit_after = (
            await session.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "user.created", AuditLog.detail.contains(email))
            )
        ).scalar()
    assert audit_after == audit_before, (
        f"a rejected create wrote an audit row ({audit_before} -> {audit_after}); "
        "the audit trail must record only the create that actually happened"
    )


def test_narrowing_rejects_a_non_email_integrity_error() -> None:
    """
    U1's narrowing: only an `ix_users_email` violation may be reported as a duplicate.

    This is the Phase-13 keeper in test form. A broad ``except IntegrityError`` here would
    tell an operator "that email already exists" when the real failure was, say, the
    users_pkey index or a role FK — sending them to debug the wrong thing entirely.
    """

    class _FakeCause(Exception):
        constraint_name = "some_other_constraint"

    other = sqlalchemy.exc.IntegrityError("INSERT ...", {}, _FakeCause("boom"))
    other.orig.__cause__ = _FakeCause("boom")  # type: ignore[union-attr]
    assert _is_duplicate_email_violation(other) is False

    class _EmailCause(Exception):
        constraint_name = "ix_users_email"

    dup = sqlalchemy.exc.IntegrityError("INSERT ...", {}, _EmailCause("boom"))
    dup.orig.__cause__ = _EmailCause("boom")  # type: ignore[union-attr]
    assert _is_duplicate_email_violation(dup) is True


@pytest.mark.parametrize("field", ["email"])
def test_update_user_cannot_change_an_email(field: str) -> None:
    """
    The edit path does NOT share U1's hole — asserted so it stays that way.

    `UserUpdate` exposes only full_name / is_active / role, and `update_user` takes no
    email parameter, so an admin cannot move one user's address onto another's and there
    is no second route to the unique-index violation. If someone later adds email editing,
    this fails and forces them to carry the same 409 guard across.
    """
    import inspect

    from app.modules.auth.schemas import UserUpdate
    from app.modules.auth.service import update_user

    assert field not in UserUpdate.model_fields, (
        f"UserUpdate now accepts {field!r}: the edit path can reach ix_users_email, so it "
        "needs the same duplicate guard create_user has (U1)."
    )
    assert field not in inspect.signature(update_user).parameters, (
        f"update_user now takes {field!r}: see above — U1's guard must cover it."
    )
