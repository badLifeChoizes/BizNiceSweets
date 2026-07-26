# ABOUTME: Idempotent named-fixture seeder for the human click-through UAT (Phase 5, NFR-8).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL module services so every fixture is reachable exactly the way the UI
# ABOUTME: reaches it. EVERY fixture is get-or-create on a stable natural key, so a second
# ABOUTME: run changes nothing; it then prints a deterministic, sorted manifest (table row
# ABOUTME: counts + the literal keys and derived values the UAT checklist quotes). Two modes:
# ABOUTME: default seeds then prints; --manifest prints only and writes nothing.
# ABOUTME: Deliberately NOT named verify_* so the CI verify-scripts glob does not run it.
"""
Idempotent UAT fixture seeder for the v4.0 human click-through (Phase 5, SRD NFR-8).

WHY THIS EXISTS (D-P5-3):
  The v1.0 UAT was burned by fixtures that evaporated — "the previously-listed
  fixtures no longer exist — the dev volume was recreated". A click-through
  runbook can only quote literal expected values (this part's rolled-up cost, that
  PO's outstanding quantity) if the dataset behind those literals can be rebuilt,
  byte-identically, on demand. This script is that rebuild: run it against a
  freshly-created volume and the whole named dataset the checklist references
  exists; run it again and NOTHING changes. It is reusable for every future
  milestone UAT.

THE IDEMPOTENCY CONTRACT (the load-bearing rule — every builder obeys it):
  * Every fixture is **get-or-create keyed on a stable natural key** — a code, a
    number, a name, or an email. Never on a surrogate id, never on "the newest
    row", never on row position.
  * A builder that finds its natural key **returns the existing row UNCHANGED**.
    It does not update, re-price, re-post, top up, or "repair" it. Anything the
    owner did to a fixture during a click-through survives a re-seed.
  * A builder that does not find its natural key creates the row **through the
    REAL module service** (the 11a/11b keeper applies to fixtures too: a fixture
    hand-INSERTed into a table proves nothing about reachability, and a service
    is the only thing that also writes the ledger/GL/audit rows the UI expects).
  * Consequence, and the thing Task 8 proves on a genuinely fresh volume:
    ``diff <(seed_run_1) <(seed_run_2)`` is EMPTY.

THE MANIFEST (deterministic and diffable — this is what makes the contract checkable):
  Printed to **stdout**, identical in both modes for the same database state, and
  sorted throughout. It carries three sections:
    * ``## tables``  — table (label) -> row count, restricted to this script's own
      rows by a static WHERE fragment declared alongside the layer.
    * ``## fixture keys`` — the literal natural keys the script MINTS. Every one of
      them carries the ``UAT-`` prefix (see below) so its rows are identifiable in
      the UI and in the database at a glance.
    * ``## derived literals`` — values the SYSTEM produced that the checklist quotes
      as expected values: rolled-up costs, margins, moving averages, on-hand
      quantities, and the auto-generated document numbers (``PO-####``, ``INV-####``)
      that cannot carry a prefix.
  NOTHING that varies run to run may enter the manifest: no timestamps, no elapsed
  times, no surrogate ids, no UUIDs, no iteration-order-dependent output. The mode
  banner goes to **stderr** precisely so stdout stays a pure, diffable artifact.

THE ``UAT-`` PREFIX:
  Every natural key this script mints is registered through ``Manifest.key()``,
  which REJECTS a key that does not start with ``UAT-`` (case-insensitive, so an
  email may read ``uat-...@example.invalid``). System-generated numbers are recorded
  through ``Manifest.value()`` instead — they are literals to quote, not keys we mint.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py --manifest

MODES:
  (default)     seed every registered layer (get-or-create), then print the manifest.
  --manifest    print the manifest ONLY — no builder runs, nothing is written. Use it
                to inspect a database, or to re-read the literals mid click-through.

ADDING A LAYER (Tasks 2-7 each add exactly one):
  Append a ``FixtureLayer`` to ``_layers()`` in dependency order with:
    * ``build``  — async, get-or-create, drives the real services. It WRITES only; it
      records nothing in the manifest.
    * ``report`` — async and STRICTLY READ-ONLY. Runs in BOTH modes, so it is what makes
      ``--manifest`` a faithful re-print of a seeded database. It reads the fixtures back
      (through service read functions where possible) and records BOTH the minted keys and
      the derived literals. Reading them back rather than echoing this file's constants is
      what makes the manifest a statement about the DATABASE — and it is why an unseeded
      database honestly reports an empty manifest instead of a wishful one.
    * ``tables`` — the ``TableSpec`` row counts that layer contributes to the manifest.
  Keep every builder's own writes inside its own layer; never mutate another layer's rows.

This script does NOT clean up after itself — unlike the ``verify_*.py`` scripts, its whole
purpose is to LEAVE the dataset in place for a human to click through.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/seed_uat_fixtures.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated before any
# module's models resolve their cross-module FKs (the Task-8 lesson from Phase 13).
import app.core.models  # noqa: F401
from app.modules.auth.models import Permission, Role
from app.modules.auth.service import (
    collect_permissions,
    create_user,
    get_user_by_email,
    write_audit,
)
from app.modules.syerp.schemas import PartnerCreate, PartnerUpdate
from app.modules.syerp.service.partners import create_partner, list_partners, update_partner

# Every natural key this script mints carries this prefix, so its rows are identifiable
# in the UI, in the database, and in the manifest.
FIXTURE_PREFIX = "UAT-"

# The acting user stamped on audit fields. A fixed literal (never uuid4) so re-runs are
# byte-identical; audit actor columns are free-form strings, not FKs to `users`.
SEED_ACTOR_ID = "00000000-0000-0000-0000-0000000005a7"


# ---------------------------------------------------------------------------
# Own async engine from POSTGRES_* env (NOT the broken conftest fixtures)
# ---------------------------------------------------------------------------


def build_dsn() -> str:
    """
    Assemble the asyncpg DSN directly from POSTGRES_* environment variables.

    Mirrors app.core.config.Settings.database_url but reads os.environ itself so
    the script is fully self-contained and never touches the test conftest.
    """
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("ERROR: POSTGRES_PASSWORD is not set in the environment.", file=sys.stderr)
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


# ---------------------------------------------------------------------------
# The manifest — a deterministic, sorted, diffable record of what exists
# ---------------------------------------------------------------------------


@dataclass
class Manifest:
    """
    Collects the three manifest sections and renders them sorted.

    Every recorder rejects a duplicate label so two layers cannot silently disagree
    about the same fixture, and ``key()`` enforces the ``UAT-`` prefix.
    """

    _counts: dict[str, int] = field(default_factory=dict)
    _keys: dict[str, list[str]] = field(default_factory=dict)
    _values: dict[str, str] = field(default_factory=dict)

    def count(self, label: str, rows: int) -> None:
        """Record one ``table -> row count`` line."""
        if label in self._counts:
            raise ValueError(f"duplicate manifest table label: {label!r}")
        self._counts[label] = rows

    def key(self, category: str, value: str) -> str:
        """
        Record one literal natural key this script MINTS, and return it unchanged.

        Rejects anything not carrying the ``UAT-`` prefix (case-insensitive, so an
        email fixture may read ``uat-...@example.invalid``). System-generated numbers
        belong in ``value()``, not here.
        """
        if not value.upper().startswith(FIXTURE_PREFIX):
            raise ValueError(
                f"minted fixture key {value!r} ({category}) does not carry the "
                f"{FIXTURE_PREFIX!r} prefix"
            )
        bucket = self._keys.setdefault(category, [])
        if value in bucket:
            raise ValueError(f"duplicate manifest key: {category} / {value!r}")
        bucket.append(value)
        return value

    def value(self, label: str, literal: object) -> None:
        """
        Record one derived literal the checklist will quote as an expected value.

        Stored as ``str(literal)`` — pass Decimals (never floats) so the printed form
        keeps its exact scale, which is what the owner will compare against on screen.
        """
        if label in self._values:
            raise ValueError(f"duplicate manifest value label: {label!r}")
        self._values[label] = str(literal)

    def render(self) -> str:
        """Render the whole manifest, sorted throughout. Identical in both modes."""
        lines = [
            "# BizNiceSweets UAT fixture manifest",
            f"# fixture prefix: {FIXTURE_PREFIX}",
            "",
            "## tables",
            "",
            "| table | rows |",
            "| --- | --- |",
        ]
        lines.extend(f"| {label} | {self._counts[label]} |" for label in sorted(self._counts))
        if not self._counts:
            lines.append("| (none registered) | 0 |")

        lines.extend(["", "## fixture keys", "", "| category | key |", "| --- | --- |"])
        for category in sorted(self._keys):
            lines.extend(f"| {category} | {key} |" for key in sorted(self._keys[category]))
        if not self._keys:
            lines.append("| (none registered) | - |")

        lines.extend(["", "## derived literals", "", "| label | value |", "| --- | --- |"])
        lines.extend(f"| {label} | {self._values[label]} |" for label in sorted(self._values))
        if not self._values:
            lines.append("| (none registered) | - |")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer registry — Tasks 2-7 each append exactly one FixtureLayer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableSpec:
    """
    One ``## tables`` manifest line: a table counted through a STATIC WHERE fragment.

    ``where`` is authored in this module and interpolated into the COUNT statement, so it
    must never contain anything derived from the environment or the database — it is a
    literal predicate identifying this script's rows (typically ``code LIKE 'UAT-%'``).
    ``label`` distinguishes two specs over the same table.
    """

    table: str
    where: str = ""
    label: str = ""

    def line_label(self) -> str:
        return self.label or self.table


Builder = Callable[["SeedContext"], Awaitable[None]]
Reporter = Callable[["SeedContext"], Awaitable[None]]


@dataclass(frozen=True)
class FixtureLayer:
    """One fixture layer: what it builds, what it reports, and what it counts."""

    name: str
    tables: tuple[TableSpec, ...] = ()
    build: Builder | None = None
    report: Reporter | None = None


@dataclass
class SeedContext:
    """Everything a builder or reporter needs: sessions, the manifest, the actor."""

    session_factory: async_sessionmaker[AsyncSession]
    manifest: Manifest
    actor_id: str = SEED_ACTOR_ID


# ---------------------------------------------------------------------------
# Layer: CORE + partners (Task 2)
# ---------------------------------------------------------------------------
#
# Four live partners (two vendors, two customers) + one ALREADY-ARCHIVED vendor, so the
# partner lists' "show archived" toggle has something to hide and something to reveal; plus
# one NON-ADMIN user holding a SINGLE-MODULE role, the subject of the RBAC nav-filter check
# (`getVisibleModules` in AppShell.tsx:37-46 shows a non-admin only the modules it holds a
# `<key>:read` permission for). Everything here is created through the REAL service the
# router calls — including the archive, which goes through update_partner(PartnerUpdate(
# active=False)) exactly as `PATCH /syerp/partners/{id}` does, not through the
# archive_partner() convenience alias the router never uses.


@dataclass(frozen=True)
class _PartnerSpec:
    """One get-or-create partner fixture, keyed on its natural key `code`."""

    code: str
    name: str
    is_vendor: bool = False
    is_customer: bool = False
    archived: bool = False


_PARTNER_SPECS: tuple[_PartnerSpec, ...] = (
    _PartnerSpec("UAT-VEND-1", "UAT Vendor One", is_vendor=True),
    _PartnerSpec("UAT-VEND-2", "UAT Vendor Two", is_vendor=True),
    _PartnerSpec("UAT-VEND-ARCH", "UAT Vendor Archived", is_vendor=True, archived=True),
    _PartnerSpec("UAT-CUST-1", "UAT Customer One", is_customer=True),
    _PartnerSpec("UAT-CUST-2", "UAT Customer Two", is_customer=True),
)

# The single-module role and its subject. The role grants exactly ONE module-read
# permission, so the sidebar must show PLUM and nothing else for this user.
UAT_ROLE_NAME = "UAT-PLUM-ONLY"
UAT_ROLE_PERMISSION = "plum:read"
UAT_USER_EMAIL = "uat-plum-user@example.invalid"
UAT_USER_FULL_NAME = "UAT PLUM-only User"
# A FIXED literal (never generated) because the owner has to type it at the login form and
# the checklist quotes it. A throwaway credential for a local UAT fixture on a dev volume —
# it is not, and must never become, a real secret.
UAT_USER_PASSWORD = "uat-plum-user-pw"


async def _partner_by_code(session: AsyncSession, code: str):
    """
    Look one partner up by its natural key through the REAL list service.

    There is no get-by-code service function, and list_partners(include_archived=True) is
    the same read the partners screen issues with "show archived" on — so an archived
    fixture is still found and is NOT re-created.
    """
    partners = await list_partners(session, include_archived=True)
    return next((p for p in partners if p.code == code), None)


async def _ensure_single_module_role(session: AsyncSession) -> None:
    """
    Get-or-create the single-module role, mirroring auth/seed.py's upsert-by-name.

    DEVIATION, recorded deliberately: roles have no service function and no UI — they are
    seed data (D-09), and `auth/seed.py:seed_admin_user` builds them with exactly this
    ORM upsert. So this IS the real code path for a role; there is no router path to
    prefer. The permission row itself is NOT minted here: it must already exist from the
    startup seed, and we fail loudly if it does not rather than invent one.
    """
    role = (
        await session.execute(select(Role).where(Role.name == UAT_ROLE_NAME))
    ).scalars().first()
    if role is None:
        role = Role(
            name=UAT_ROLE_NAME,
            description="UAT fixture: single-module (PLUM read-only) non-admin role",
        )
        session.add(role)
        await session.flush()

    perm = (
        await session.execute(
            select(Permission).where(Permission.code == UAT_ROLE_PERMISSION)
        )
    ).scalars().first()
    if perm is None:
        raise RuntimeError(
            f"permission {UAT_ROLE_PERMISSION!r} is missing — the startup seed "
            "(app.core.seed) has not run against this database"
        )

    existing = {p.code for p in await role.awaitable_attrs.permissions}
    if UAT_ROLE_PERMISSION not in existing:
        role.permissions.append(perm)
    await session.commit()


async def build_core_partners(ctx: SeedContext) -> None:
    """
    Get-or-create the five partners and the non-admin single-module user.

    Every branch is skip-if-present: a partner found by code is returned UNCHANGED (it is
    NOT re-archived, re-named, or re-flagged), and the archive step runs only on the run
    that actually created the row, so an owner who un-archives UAT-VEND-ARCH mid-UAT does
    not have it silently archived again by the next seed.
    """
    for spec in _PARTNER_SPECS:
        async with ctx.session_factory() as session:
            if await _partner_by_code(session, spec.code) is not None:
                continue  # get-or-create: found → leave it exactly as it is

            partner = await create_partner(
                session,
                PartnerCreate(
                    code=spec.code,
                    name=spec.name,
                    is_vendor=spec.is_vendor,
                    is_customer=spec.is_customer,
                ),
            )
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="partner.created",
                target_type="partner",
                target_id=str(partner.id),
                detail=f"Partner created: {partner.name}",
            )

            if spec.archived:
                # The REAL archive path: PATCH {active: false} → update_partner, with the
                # router's partner.archived audit action.
                await update_partner(session, partner.id, PartnerUpdate(active=False))
                await write_audit(
                    session,
                    actor_id=ctx.actor_id,
                    action="partner.archived",
                    target_type="partner",
                    target_id=str(partner.id),
                    detail=f"Partner archived: {partner.name}",
                )

    async with ctx.session_factory() as session:
        await _ensure_single_module_role(session)

    async with ctx.session_factory() as session:
        if await get_user_by_email(session, UAT_USER_EMAIL) is None:
            user = await create_user(
                session,
                email=UAT_USER_EMAIL,
                password=UAT_USER_PASSWORD,
                full_name=UAT_USER_FULL_NAME,
                role_name=UAT_ROLE_NAME,
            )
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="user.created",
                target_type="user",
                target_id=str(user.id),
                detail=f"Admin created user: {user.email}",
            )


async def report_core_partners(ctx: SeedContext) -> None:
    """Read the CORE/partner fixtures back (READ-ONLY) and record their literals."""
    manifest = ctx.manifest

    async with ctx.session_factory() as session:
        partners = await list_partners(session, include_archived=True)
    for partner in sorted(
        (p for p in partners if p.code.startswith(FIXTURE_PREFIX)), key=lambda p: p.code
    ):
        code = manifest.key("syerp.partner", partner.code)
        roles = [
            label
            for label, flag in (("vendor", partner.is_vendor), ("customer", partner.is_customer))
            if flag
        ]
        manifest.value(f"syerp.partner.{code}.name", partner.name)
        manifest.value(f"syerp.partner.{code}.role", "+".join(roles) or "none")
        manifest.value(f"syerp.partner.{code}.active", str(partner.active).lower())

    async with ctx.session_factory() as session:
        role = (
            await session.execute(select(Role).where(Role.name == UAT_ROLE_NAME))
        ).scalars().first()
        if role is not None:
            manifest.key("auth.role", role.name)
            perms = sorted(p.code for p in await role.awaitable_attrs.permissions)
            manifest.value(f"auth.role.{role.name}.permissions", ",".join(perms))

        user = await get_user_by_email(session, UAT_USER_EMAIL)
        if user is not None:
            email = manifest.key("auth.user", user.email)
            manifest.value(f"auth.user.{email}.full_name", user.full_name or "")
            manifest.value(f"auth.user.{email}.is_active", str(user.is_active).lower())
            manifest.value(
                f"auth.user.{email}.roles", ",".join(sorted(r.name for r in user.roles))
            )
            manifest.value(
                f"auth.user.{email}.permissions", ",".join(sorted(collect_permissions(user)))
            )
            # Quoted in the checklist because the owner logs in as this user.
            manifest.value(f"auth.user.{email}.password", UAT_USER_PASSWORD)


CORE_PARTNERS_LAYER = FixtureLayer(
    name="core+partners",
    tables=(
        TableSpec("syerp_partner", "code LIKE 'UAT-%'", "syerp_partner (UAT-)"),
        TableSpec("roles", "name LIKE 'UAT-%'", "roles (UAT-)"),
        TableSpec("users", "email LIKE 'uat-%'", "users (uat-)"),
    ),
    build=build_core_partners,
    report=report_core_partners,
)


def _layers() -> tuple[FixtureLayer, ...]:
    """
    The registered fixture layers, in DEPENDENCY order (builders run in this order).

    Tasks 3-7 append here:
      3. PLUM                           5. GELATO bins        7. SYERP GL / AP / AR
      4. SYERP inventory + purchasing   6. MOUSSE + CRUMB
    """
    return (CORE_PARTNERS_LAYER,)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def _count_rows(session: AsyncSession, spec: TableSpec) -> int:
    """Count one TableSpec's rows via its static predicate."""
    where = f" WHERE {spec.where}" if spec.where else ""
    result = await session.execute(text(f"SELECT count(*) FROM {spec.table}{where}"))
    return int(result.scalar_one())


async def run(*, seed: bool) -> None:
    """Seed (unless manifest-only), then render the manifest to stdout."""
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    manifest = Manifest()
    ctx = SeedContext(session_factory=session_factory, manifest=manifest)
    layers = _layers()

    try:
        # Fail loudly and immediately if the database is unreachable, rather than
        # printing an empty manifest that looks like an empty database.
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))

        if seed:
            for layer in layers:
                if layer.build is not None:
                    await layer.build(ctx)

        # Reporters are read-only and run in BOTH modes — they are what makes
        # --manifest a faithful re-print of an already-seeded database.
        for layer in layers:
            if layer.report is not None:
                await layer.report(ctx)

        async with session_factory() as session:
            for layer in layers:
                for spec in layer.tables:
                    manifest.count(spec.line_label(), await _count_rows(session, spec))

        print(manifest.render())
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed the idempotent named UAT fixture dataset and print its manifest. "
            "Every fixture is get-or-create on a stable natural key, so re-running "
            "changes nothing."
        )
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="print the manifest only — run no builders and write nothing",
    )
    args = parser.parse_args()

    mode = "manifest-only (read-only)" if args.manifest else "seed + manifest"
    layer_names = ", ".join(layer.name for layer in _layers()) or "(none registered)"
    # Banner to STDERR so stdout stays a pure, diffable manifest.
    print(f"mode: {mode}; layers: {layer_names}", file=sys.stderr)

    asyncio.run(run(seed=not args.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
