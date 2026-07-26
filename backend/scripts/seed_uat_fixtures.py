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
from decimal import ROUND_HALF_UP, Decimal

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
from app.modules.plum.schemas import (
    AvlLinkCreate,
    BomItemCreate,
    CostUpdate,
    PartCreate,
    PriceBreakCreate,
)
from app.modules.plum.service import (
    add_avl_link,
    add_bom_line,
    add_price_break,
    advance_revision_status,
    create_part,
    get_cost_read,
    get_part_with_revisions,
    get_where_used,
    list_avl_links,
    list_parts,
    load_bom_tree,
    load_flat_bom,
    update_cost,
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


def decimal_str(value: Decimal) -> str:
    """
    Render a Decimal in canonical form — LOSSLESS, never exponent notation.

    Numeric(_, 6) columns multiplied through a BOM roll-up come back as
    ``99.150000000000000000000000``; an owner comparing that against a screen reading
    ``99.15`` is being asked to do the wrong job. Trailing zeros are therefore stripped,
    but NOTHING else is: no rounding, no quantizing, so a genuine 99.154 still prints as
    99.154 and a two-run diff still catches it. ``normalize()`` alone would render 33 as
    ``3.3E+1``, hence the re-expansion of positive exponents.
    """
    normalized = value.normalize()
    if normalized.as_tuple().exponent > 0:
        normalized = normalized.quantize(Decimal(1))
    return f"{normalized:f}"


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

        Pass Decimals (never floats): they are rendered through ``decimal_str`` so the
        stored form is canonical and lossless — what the owner reads on screen, without a
        column-scale tail. Everything else is stored as ``str(literal)``.
        """
        if label in self._values:
            raise ValueError(f"duplicate manifest value label: {label!r}")
        self._values[label] = (
            decimal_str(literal) if isinstance(literal, Decimal) else str(literal)
        )

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


# ---------------------------------------------------------------------------
# Layer: PLUM (Task 3)
# ---------------------------------------------------------------------------
#
# Four purpose-built structures, all on UAT-P… part numbers so the auto-numbering check
# is not perturbed (generate_part_number matches ``^P[0-9]+$`` only — service.py:139).
#
# 1. COST / SHARED-SUB-ASSEMBLY TREE — the shape .zj/UAT-v1.0.md:19-30 proved, rebuilt
#    with arithmetic chosen so a WRONG formula cannot land on the right number:
#
#      UAT-P104 ──3×──► UAT-P103 ──2×──► UAT-P102 ──3×──► UAT-P101  (material 2.75)
#         ├────5×──────────────────────► UAT-P102        ← shared sub-assembly
#         └────7×──────────────────────► UAT-P105        (material 1.20)
#
#    UAT-P102 = 3 × 2.75          = 8.25
#    UAT-P103 = 2 × 8.25          = 16.50
#    UAT-P104 = 3×16.50 + 5×8.25 + 7×1.20 = 49.50 + 41.25 + 8.40 = 99.15
#    sale price 40.00 → margin −59.15, below cost (the UI must render it red).
#    Flat BOM: UAT-P102 appears ONCE at total qty 5 + 3×2 = 11 (the dedupe), UAT-P101 at
#    11 × 3 = 33, UAT-P103 at 3, UAT-P105 at 7.
#
#    WHY THESE NUMBERS (the Phase-2b keeper — a fixture whose arithmetic divides evenly
#    cannot guard its own mutation):
#      * The v1.0 D1 defect summed the flat rows' extended costs into the footer. Here that
#        wrong sum is 49.50 + 90.75 + 90.75 + 8.40 = 239.40 — nowhere near 99.15.
#      * A SECOND costed leaf (UAT-P105) exists precisely so that no single flat row equals
#        the total. With one costed leaf the total is structurally identical to that leaf's
#        extended cost, and a footer that printed one row would look correct.
#      * Dropping the shared sub-assembly's direct 5× leg gives 57.90; dropping the nested
#        leg gives 90.75; forgetting to multiply down the path gives 27.95. All distinct.
#      * 99.15 is not an integer multiple of any child cost (99.15 / 8.25 = 12.018…), so a
#        dropped or doubled quantity cannot land back on it.
#
# 2. WHERE-USED CHAIN — UAT-P201 ──2×──► UAT-P202 ──3×──► UAT-P203, kept separate from the
#    cost tree so a mutating check on one cannot poison the other. Where-Used of UAT-P203
#    must show UAT-P202 as DIRECT and UAT-P201 as INDIRECT (via UAT-P202).
#
# 3. RELEASED REVISION — UAT-P301 (6 × UAT-P302 @ 4.40 → 26.40, sale 35.00, margin +8.60,
#    ABOVE cost, so the red-margin check has a black-margin control). v1.0 had no Released
#    part at all, which is why its read-only checks went unrun. Released after its BOM and
#    cost are set, so released_cost_snapshot freezes at 26.40.
#
# 4. AVL — UAT-P401 has NO vendor link (the happy-path Add-Vendor target); UAT-P402 has two
#    links (UAT-VEND-1 preferred with two price breaks, UAT-VEND-2 not preferred, so the
#    Preferred badge has something to distinguish) and selects price-break index 1, making
#    the "vendor price" cost source reachable. Its manual material_cost 9.99 is deliberately
#    NOT the answer: the vendor break at index 1 is 6.15, and index 0 is 7.30 — three
#    distinct candidates, so the effective cost proves WHICH rule fired.

# -- 1. cost / shared-sub-assembly tree
PLUM_LEAF = "UAT-P101"
PLUM_SUB = "UAT-P102"
PLUM_MID = "UAT-P103"
PLUM_TOP = "UAT-P104"
PLUM_LEAF2 = "UAT-P105"
PLUM_LEAF_COST = Decimal("2.75")
PLUM_LEAF2_COST = Decimal("1.20")
PLUM_TOP_SALE_PRICE = Decimal("40.00")
PLUM_QTY_LEAF_IN_SUB = Decimal("3")
PLUM_QTY_SUB_IN_MID = Decimal("2")
PLUM_QTY_MID_IN_TOP = Decimal("3")
PLUM_QTY_SUB_IN_TOP = Decimal("5")
PLUM_QTY_LEAF2_IN_TOP = Decimal("7")

# -- 2. where-used chain
PLUM_WU_TOP = "UAT-P201"
PLUM_WU_MID = "UAT-P202"
PLUM_WU_LEAF = "UAT-P203"

# -- 3. released revision
PLUM_REL_ASM = "UAT-P301"
PLUM_REL_CHILD = "UAT-P302"
PLUM_REL_CHILD_COST = Decimal("4.40")
PLUM_REL_QTY = Decimal("6")
PLUM_REL_SALE_PRICE = Decimal("35.00")

# -- 4. AVL
PLUM_AVL_NONE = "UAT-P401"
PLUM_AVL_LINKED = "UAT-P402"
PLUM_AVL_MATERIAL_COST = Decimal("9.99")
PLUM_AVL_SALE_PRICE = Decimal("12.00")
PLUM_AVL_BREAKS = ((1, Decimal("7.30"), 21), (100, Decimal("6.15"), 35))
PLUM_AVL_SELECTED_INDEX = 1

_PCT_QUANTUM = Decimal("0.01")


def _expect(label: str, actual: object, expected: object) -> None:
    """
    Assert the product agrees with an independently-computed oracle.

    The manifest always prints what the SERVICE computed; this only guards against
    printing a number the product no longer produces. Raises loudly (the pattern the
    verify_* scripts use) rather than silently recording a stale literal.
    """
    if actual != expected:
        raise RuntimeError(f"oracle mismatch for {label}: service={actual!r} oracle={expected!r}")


async def _plum_part_id(session: AsyncSession, part_number: str) -> str | None:
    """Resolve a part id from its natural key through the REAL list service."""
    rows = await list_parts(session, q=part_number, include_archived=True)
    return next((r["id"] for r in rows if r["part_number"] == part_number), None)


async def _current_revision(session: AsyncSession, part_id: str):
    """The newest revision of a part (get_part_with_revisions orders newest-first)."""
    detail = await get_part_with_revisions(session, part_id)
    revisions = detail["revisions"]
    return revisions[0] if revisions else None


async def _ensure_part(ctx: SeedContext, part_number: str, description: str) -> str:
    """
    Get-or-create one part by its natural key `part_number`.

    Found → returned UNCHANGED (its BOM, costs and revision status are left exactly as
    they are). Created → through the real create_part, which auto-creates the first Draft
    revision, plus the router's part.created audit row.
    """
    async with ctx.session_factory() as session:
        existing = await _plum_part_id(session, part_number)
        if existing is not None:
            return existing

        part = await create_part(
            session, PartCreate(part_number=part_number, description=description)
        )
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="part.created",
            target_type="part",
            target_id=str(part.id),
            detail=f"Part created: {part.part_number}",
        )
        return part.id


async def _ensure_bom_line(
    ctx: SeedContext, parent_id: str, child_id: str, child_number: str, qty: Decimal
) -> None:
    """
    Get-or-create one BOM edge, keyed on (parent revision, child part).

    (parent_revision_id, child_part_id) is UNIQUE, so an unguarded re-add would 409. An
    existing edge is left alone even if its qty differs — the owner may have edited it
    mid-UAT, and re-writing it would violate the contract.
    """
    async with ctx.session_factory() as session:
        revision = await _current_revision(session, parent_id)
        tree = await load_bom_tree(session, parent_id, revision.id)
        if any(node["part_number"] == child_number for node in tree):
            return
        await add_bom_line(
            session,
            parent_id,
            BomItemCreate(child_part_id=child_id, qty=qty),
            revision.id,
            ctx.actor_id,
        )


async def _ensure_cost(ctx: SeedContext, part_id: str, **fields) -> None:
    """
    Apply cost fields to a part's current revision only when they are not already set.

    Skipping the no-op write matters: update_cost writes a part.cost_updated audit row on
    every call, so an unconditional PATCH would grow the audit trail on every seed run and
    break idempotency in exactly the place nobody looks.
    """
    async with ctx.session_factory() as session:
        revision = await _current_revision(session, part_id)
        if all(getattr(revision, name) == value for name, value in fields.items()):
            return
        await update_cost(session, part_id, revision.id, CostUpdate(**fields), ctx.actor_id)


async def _ensure_released(ctx: SeedContext, part_id: str) -> None:
    """Drive draft → in_review → released through the real FSM, once."""
    async with ctx.session_factory() as session:
        revision = await _current_revision(session, part_id)
        if revision.status == "released":
            return
        if revision.status == "draft":
            await advance_revision_status(
                session, part_id, revision.id, "in_review", ctx.actor_id
            )
        await advance_revision_status(session, part_id, revision.id, "released", ctx.actor_id)


async def _ensure_avl_link(
    ctx: SeedContext, part_id: str, vendor_id: str, vendor_part_number: str, preferred: bool
) -> str:
    """Get-or-create one AVL link, keyed on (part, vendor); returns the link id."""
    async with ctx.session_factory() as session:
        for link in await list_avl_links(session, part_id):
            if link["vendor_id"] == vendor_id:
                return link["id"]
        link = await add_avl_link(
            session,
            part_id,
            AvlLinkCreate(
                vendor_id=vendor_id,
                vendor_part_number=vendor_part_number,
                preferred=preferred,
            ),
            ctx.actor_id,
        )
        return link["id"]


async def _ensure_price_break(
    ctx: SeedContext, part_id: str, link_id: str, qty_threshold: int, unit_cost: Decimal,
    lead_days: int,
) -> None:
    """Get-or-create one price break, keyed on (link, qty_threshold)."""
    async with ctx.session_factory() as session:
        links = await list_avl_links(session, part_id)
        link = next((r for r in links if r["id"] == link_id), None)
        if link and any(pb["qty_threshold"] == qty_threshold for pb in link["price_breaks"]):
            return
        await add_price_break(
            session,
            part_id,
            link_id,
            PriceBreakCreate(
                qty_threshold=qty_threshold, unit_cost=unit_cost, lead_days=lead_days
            ),
            ctx.actor_id,
        )


async def build_plum(ctx: SeedContext) -> None:
    """Get-or-create the four PLUM structures. Every step is skip-if-present."""
    # -- 1. cost / shared-sub-assembly tree -------------------------------------------
    leaf = await _ensure_part(ctx, PLUM_LEAF, "UAT costed leaf part")
    leaf2 = await _ensure_part(ctx, PLUM_LEAF2, "UAT second costed leaf part")
    sub = await _ensure_part(ctx, PLUM_SUB, "UAT shared sub-assembly")
    mid = await _ensure_part(ctx, PLUM_MID, "UAT mid-level assembly")
    top = await _ensure_part(ctx, PLUM_TOP, "UAT top-level costed assembly")

    await _ensure_cost(ctx, leaf, material_cost=PLUM_LEAF_COST)
    await _ensure_cost(ctx, leaf2, material_cost=PLUM_LEAF2_COST)
    await _ensure_bom_line(ctx, sub, leaf, PLUM_LEAF, PLUM_QTY_LEAF_IN_SUB)
    await _ensure_bom_line(ctx, mid, sub, PLUM_SUB, PLUM_QTY_SUB_IN_MID)
    await _ensure_bom_line(ctx, top, mid, PLUM_MID, PLUM_QTY_MID_IN_TOP)
    await _ensure_bom_line(ctx, top, sub, PLUM_SUB, PLUM_QTY_SUB_IN_TOP)
    await _ensure_bom_line(ctx, top, leaf2, PLUM_LEAF2, PLUM_QTY_LEAF2_IN_TOP)
    await _ensure_cost(ctx, top, sale_price=PLUM_TOP_SALE_PRICE)

    # -- 2. where-used chain ------------------------------------------------------------
    wu_top = await _ensure_part(ctx, PLUM_WU_TOP, "UAT where-used top assembly")
    wu_mid = await _ensure_part(ctx, PLUM_WU_MID, "UAT where-used mid assembly")
    wu_leaf = await _ensure_part(ctx, PLUM_WU_LEAF, "UAT where-used leaf part")
    await _ensure_bom_line(ctx, wu_top, wu_mid, PLUM_WU_MID, Decimal("2"))
    await _ensure_bom_line(ctx, wu_mid, wu_leaf, PLUM_WU_LEAF, Decimal("3"))

    # -- 3. released revision -----------------------------------------------------------
    rel_child = await _ensure_part(ctx, PLUM_REL_CHILD, "UAT released-assembly component")
    rel_asm = await _ensure_part(ctx, PLUM_REL_ASM, "UAT released assembly")
    await _ensure_cost(ctx, rel_child, material_cost=PLUM_REL_CHILD_COST)
    await _ensure_bom_line(ctx, rel_asm, rel_child, PLUM_REL_CHILD, PLUM_REL_QTY)
    # Cost must be set while the revision is still Draft — releasing freezes it.
    await _ensure_cost(ctx, rel_asm, sale_price=PLUM_REL_SALE_PRICE)
    await _ensure_released(ctx, rel_asm)

    # -- 4. AVL --------------------------------------------------------------------------
    await _ensure_part(ctx, PLUM_AVL_NONE, "UAT part with no approved vendor")
    avl_part = await _ensure_part(ctx, PLUM_AVL_LINKED, "UAT part with approved vendors")

    async with ctx.session_factory() as session:
        partners = await list_partners(session, include_archived=True)
    vendors = {p.code: p.id for p in partners}
    preferred_link = await _ensure_avl_link(
        ctx, avl_part, vendors["UAT-VEND-1"], "VEND1-P402", preferred=True
    )
    await _ensure_avl_link(ctx, avl_part, vendors["UAT-VEND-2"], "VEND2-P402", preferred=False)
    for qty_threshold, unit_cost, lead_days in PLUM_AVL_BREAKS:
        await _ensure_price_break(
            ctx, avl_part, preferred_link, qty_threshold, unit_cost, lead_days
        )
    # material_cost is set but must LOSE to the selected vendor break (D-07 step 1).
    await _ensure_cost(
        ctx,
        avl_part,
        material_cost=PLUM_AVL_MATERIAL_COST,
        sale_price=PLUM_AVL_SALE_PRICE,
        selected_vendor_link_id=preferred_link,
        selected_price_break_index=PLUM_AVL_SELECTED_INDEX,
    )


async def report_plum(ctx: SeedContext) -> None:
    """
    Read every PLUM literal back out of the REAL costing/BOM services (READ-ONLY).

    Nothing here is hand-computed into the manifest: the rolled-up cost, margin, flat-BOM
    quantities and Where-Used labels are whatever the product returns. The independent
    oracle (_expect) recomputes the roll-up straight from the literal quantities and leaf
    costs and fails the run if the two disagree.
    """
    manifest = ctx.manifest

    async with ctx.session_factory() as session:
        rows = await list_parts(session, q="UAT-P", include_archived=True)
        for row in sorted(rows, key=lambda r: r["part_number"]):
            if not row["part_number"].startswith("UAT-P"):
                continue
            number = manifest.key("plum.part", row["part_number"])
            manifest.value(
                f"plum.part.{number}.revision",
                f"{row['current_revision_label']} ({row['current_revision_status']})",
            )

        # -- 1. cost tree: rolled-up cost, sale price, margin, flat-BOM dedupe ----------
        top_id = await _plum_part_id(session, PLUM_TOP)
        if top_id is not None:
            revision = await _current_revision(session, top_id)
            cost = await get_cost_read(session, top_id, revision.id)

            # Independent oracle, recomputed from the literals rather than re-read.
            sub_cost = PLUM_QTY_LEAF_IN_SUB * PLUM_LEAF_COST
            oracle_rollup = (
                PLUM_QTY_MID_IN_TOP * (PLUM_QTY_SUB_IN_MID * sub_cost)
                + PLUM_QTY_SUB_IN_TOP * sub_cost
                + PLUM_QTY_LEAF2_IN_TOP * PLUM_LEAF2_COST
            )
            _expect(f"{PLUM_TOP} bom_rollup_cost", cost["bom_rollup_cost"], oracle_rollup)
            _expect(
                f"{PLUM_TOP} margin",
                cost["margin"],
                PLUM_TOP_SALE_PRICE - oracle_rollup,
            )

            manifest.value(f"plum.cost.{PLUM_TOP}.bom_rollup_cost", cost["bom_rollup_cost"])
            manifest.value(f"plum.cost.{PLUM_TOP}.effective_cost", cost["effective_cost"])
            manifest.value(
                f"plum.cost.{PLUM_TOP}.effective_cost_source", cost["effective_cost_source"]
            )
            manifest.value(f"plum.cost.{PLUM_TOP}.sale_price", cost["sale_price"])
            manifest.value(f"plum.cost.{PLUM_TOP}.margin", cost["margin"])
            manifest.value(f"plum.cost.{PLUM_TOP}.margin_pct", cost["margin_pct"])
            manifest.value(
                f"plum.cost.{PLUM_TOP}.margin_pct_2dp",
                cost["margin_pct"].quantize(_PCT_QUANTUM, ROUND_HALF_UP),
            )
            manifest.value(
                f"plum.cost.{PLUM_TOP}.below_cost", str(cost["margin"] < 0).lower()
            )

            flat = await load_flat_bom(session, top_id, revision.id)
            manifest.value(f"plum.flat_bom.{PLUM_TOP}.row_count", len(flat))
            for line in flat:
                child = line["part_number"]
                manifest.value(
                    f"plum.flat_bom.{PLUM_TOP}.{child}.total_qty", line["total_qty"]
                )
                manifest.value(
                    f"plum.flat_bom.{PLUM_TOP}.{child}.extended_cost", line["extended_cost"]
                )

        # -- 2. where-used: the ordered direct/indirect labels ---------------------------
        wu_leaf_id = await _plum_part_id(session, PLUM_WU_LEAF)
        if wu_leaf_id is not None:
            parents = await get_where_used(session, wu_leaf_id)
            # Recorded as ONE ordered value: the service's own order is the literal the
            # checklist quotes, and sorting the manifest must not destroy it.
            manifest.value(
                f"plum.where_used.{PLUM_WU_LEAF}.parents",
                "; ".join(
                    f"{p['parent_part_number']}="
                    + ("direct" if p["direct"] else f"indirect via {p['via_part_number']}")
                    for p in parents
                ),
            )

        # -- 3. released revision: frozen label, status, snapshot ------------------------
        rel_id = await _plum_part_id(session, PLUM_REL_ASM)
        if rel_id is not None:
            revision = await _current_revision(session, rel_id)
            cost = await get_cost_read(session, rel_id, revision.id)
            _expect(
                f"{PLUM_REL_ASM} bom_rollup_cost",
                cost["bom_rollup_cost"],
                PLUM_REL_QTY * PLUM_REL_CHILD_COST,
            )
            manifest.value(f"plum.released.{PLUM_REL_ASM}.status", revision.status)
            manifest.value(f"plum.released.{PLUM_REL_ASM}.label", revision.revision_label)
            manifest.value(
                f"plum.released.{PLUM_REL_ASM}.released_cost_snapshot",
                cost["released_cost_snapshot"],
            )
            manifest.value(
                f"plum.released.{PLUM_REL_ASM}.bom_rollup_cost", cost["bom_rollup_cost"]
            )
            manifest.value(f"plum.released.{PLUM_REL_ASM}.sale_price", cost["sale_price"])
            manifest.value(f"plum.released.{PLUM_REL_ASM}.margin", cost["margin"])

        # -- 4. AVL: the unlinked target and the vendor-priced part ----------------------
        none_id = await _plum_part_id(session, PLUM_AVL_NONE)
        if none_id is not None:
            manifest.value(
                f"plum.avl.{PLUM_AVL_NONE}.link_count", len(await list_avl_links(session, none_id))
            )

        avl_id = await _plum_part_id(session, PLUM_AVL_LINKED)
        if avl_id is not None:
            vendor_names = {p.id: p.code for p in await list_partners(session, include_archived=True)}
            links = await list_avl_links(session, avl_id)
            manifest.value(f"plum.avl.{PLUM_AVL_LINKED}.link_count", len(links))
            for link in links:
                vendor = vendor_names.get(link["vendor_id"], link["vendor_id"])
                manifest.value(
                    f"plum.avl.{PLUM_AVL_LINKED}.{vendor}.preferred",
                    str(link["preferred"]).lower(),
                )
                manifest.value(
                    f"plum.avl.{PLUM_AVL_LINKED}.{vendor}.price_breaks",
                    ", ".join(
                        f"qty>={pb['qty_threshold']}:{decimal_str(pb['unit_cost'])}"
                        for pb in link["price_breaks"]
                    )
                    or "none",
                )

            revision = await _current_revision(session, avl_id)
            cost = await get_cost_read(session, avl_id, revision.id)
            # The whole point of this fixture: the selected vendor break WINS over the
            # manual material_cost, and it is index 1's price, not index 0's.
            _expect(
                f"{PLUM_AVL_LINKED} effective_cost",
                cost["effective_cost"],
                PLUM_AVL_BREAKS[PLUM_AVL_SELECTED_INDEX][1],
            )
            manifest.value(
                f"plum.cost.{PLUM_AVL_LINKED}.material_cost", cost["material_cost"]
            )
            manifest.value(
                f"plum.cost.{PLUM_AVL_LINKED}.selected_price_break_index",
                cost["selected_price_break_index"],
            )
            manifest.value(
                f"plum.cost.{PLUM_AVL_LINKED}.effective_cost", cost["effective_cost"]
            )
            manifest.value(
                f"plum.cost.{PLUM_AVL_LINKED}.effective_cost_source",
                cost["effective_cost_source"],
            )
            manifest.value(f"plum.cost.{PLUM_AVL_LINKED}.sale_price", cost["sale_price"])
            manifest.value(f"plum.cost.{PLUM_AVL_LINKED}.margin", cost["margin"])


PLUM_LAYER = FixtureLayer(
    name="plum",
    tables=(
        TableSpec("plum_part", "part_number LIKE 'UAT-P%'", "plum_part (UAT-P)"),
        TableSpec(
            "plum_bom_item",
            "parent_revision_id IN (SELECT r.id FROM plum_part_revision r "
            "JOIN plum_part p ON p.id = r.part_id WHERE p.part_number LIKE 'UAT-P%')",
            "plum_bom_item (UAT-P)",
        ),
        TableSpec(
            "plum_avl_link",
            "part_id IN (SELECT id FROM plum_part WHERE part_number LIKE 'UAT-P%')",
            "plum_avl_link (UAT-P)",
        ),
    ),
    build=build_plum,
    report=report_plum,
)


def _layers() -> tuple[FixtureLayer, ...]:
    """
    The registered fixture layers, in DEPENDENCY order (builders run in this order).

    PLUM depends on core+partners (its AVL links point at the UAT vendors).

    Tasks 4-7 append here:
      4. SYERP inventory + purchasing   6. MOUSSE + CRUMB
      5. GELATO bins                    7. SYERP GL / AP / AR
    """
    return (CORE_PARTNERS_LAYER, PLUM_LAYER)


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
