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
from app.modules.gelato.schemas import BinCreate, PutawayRequest
from app.modules.gelato.service import archive_bin, create_bin, execute_putaway, list_bins
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
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    InventoryItemUpdate,
    PartnerCreate,
    PartnerUpdate,
    POCreate,
    POLineCreate,
    StockLocationCreate,
    StockLocationUpdate,
)
from app.modules.syerp.service.inventory import get_bin_on_hand, get_item_onhand, post_receipt
from app.modules.syerp.service.items import create_item, list_items, update_item
from app.modules.syerp.service.locations import create_location, list_locations, update_location
from app.modules.syerp.service.partners import create_partner, list_partners, update_partner
from app.modules.syerp.service.purchasing import add_line, advance_po_status, create_po, list_pos

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


# ---------------------------------------------------------------------------
# Layer: SYERP inventory + purchasing (Task 4)
# ---------------------------------------------------------------------------
#
# TWO extra stock locations beside the seeded "Main" (one archived, so the locations
# screen's archive state is observable), THREE items — PLUM-linked / standalone /
# archived — with costed receipts giving each a known per-location on-hand and a known
# moving average, and TWO non-contending purchase orders.
#
# WHY THESE RECEIPT NUMBERS (the Phase-2b keeper again — the moving average is this
# layer's crux, so its arithmetic must not divide evenly):
#   UAT-ITEM-1 takes TWO receipts at DIFFERENT unit costs, in DIFFERENT locations and at
#   DIFFERENT quantities: 7 @ 4.50 into Main, then 6 @ 9.20 into UAT-LOC-A.
#     moving average = (7×4.50 + 6×9.20) / 13 = 86.70 / 13 = 6.669230769…
#                    → quantized scale 6, ROUND_HALF_UP → 6.669231
#   Every wrong formula lands somewhere visibly different:
#     * simple mean of the two unit costs        → 6.85
#     * last cost wins                           → 9.20
#     * first cost wins (average never updated)  → 4.50
#     * total cost, forgetting to divide         → 86.70
#     * weighted sum ÷ 2 (count, not quantity)   → 43.35
#     * per-location averaging                   → 4.50 and 9.20, never one number
#     * TRUNCATION instead of ROUND_HALF_UP      → 6.669230  (the 7th decimal is a 7, so
#       the rounding mode is load-bearing here — this is why 13 was chosen as the divisor)
#   13 is prime to 86.70, so no dropped or doubled quantity divides back onto the answer.
#
#   On-hand VALUE is the second, subtler guard: 13 × 6.669231 = 86.700003, NOT the 86.70
#   actually spent. The rounding of the average to scale 6 is visible in the valuation.
#   An implementation that valued stock as Σ(qty × unit_cost) off the ledger would print a
#   clean 86.700000 — so this literal distinguishes "quantity × moving average" (what the
#   product does) from "sum of what we paid" (what it does not).
#
# GL CONTRIBUTION: NONE. Standalone post_receipt writes an InventoryTxn and moves the
# moving average; it posts NO journal entry (only PO receive_line does, Dr 1130 / Cr 2150).
# create_po and approve post nothing either. So this layer leaves the trial balance exactly
# as it found it — Task 7 inherits a clean slate.
#
# The two POs deliberately DO NOT CONTEND:
#   * the Draft PO (two lines) is the approve check's subject;
#   * the Approved PO (one line, fully outstanding) is the receive / partial-receive /
#     over-receipt subject, and its line points at UAT-ITEM-2 — NOT the two-receipt
#     UAT-ITEM-1 — so Task 27's receiving cannot move the moving-average literals that
#     Task 24's read-only checks quote.
# A PO number is SYSTEM-generated and cannot carry the UAT- prefix, so the natural key for
# get-or-create is the header's `notes` marker; the PO-#### number is recorded as a derived
# literal, exactly as the task requires.

UAT_LOC_A = "UAT-LOC-A"
UAT_LOC_ARCHIVED = "UAT-LOC-ARCH"

INV_ITEM_LINKED = "UAT-ITEM-1"
INV_ITEM_STANDALONE = "UAT-ITEM-2"
INV_ITEM_ARCHIVED = "UAT-ITEM-3"
INV_LINKED_PLUM_PART = PLUM_LEAF  # UAT-P101, the costed leaf

# (item code, location name, qty, unit cost) — applied in order; the moving average is
# item-level, so the ORDER of these receipts is part of the fixture.
INV_RECEIPTS: tuple[tuple[str, str, Decimal, Decimal], ...] = (
    (INV_ITEM_LINKED, DEFAULT_LOCATION_NAME, Decimal("7"), Decimal("4.50")),
    (INV_ITEM_LINKED, UAT_LOC_A, Decimal("6"), Decimal("9.20")),
    (INV_ITEM_STANDALONE, DEFAULT_LOCATION_NAME, Decimal("4"), Decimal("12.25")),
)

PO_DRAFT_KEY = "UAT-PO-DRAFT"
PO_APPROVED_KEY = "UAT-PO-APPROVED"
PO_DRAFT_LINES: tuple[tuple[str, Decimal, Decimal], ...] = (
    (INV_ITEM_LINKED, Decimal("10"), Decimal("5.00")),
    (INV_ITEM_STANDALONE, Decimal("3"), Decimal("12.00")),
)
PO_APPROVED_LINES: tuple[tuple[str, Decimal, Decimal], ...] = (
    (INV_ITEM_STANDALONE, Decimal("9"), Decimal("8.00")),
)

_COST_QUANTUM = Decimal("0.000001")


async def _location_by_name(session: AsyncSession, name: str):
    """Resolve a stock location by its natural key `name` through the real list service."""
    locations = await list_locations(session, include_archived=True)
    return next((loc for loc in locations if loc.name == name), None)


async def _item_by_code(session: AsyncSession, code: str):
    """Resolve an inventory item by its natural key `code` through the real list service."""
    items = await list_items(session, include_archived=True)
    return next((item for item in items if item.code == code), None)


async def _po_by_notes(session: AsyncSession, marker: str):
    """
    Resolve a purchase order by its `notes` marker.

    A PO's own natural key (po_number) is SERVER-generated, so it cannot be used to
    get-or-create. The notes marker is the stable key this script controls.
    """
    for po in await list_pos(session):
        if po.notes == marker:
            return po
    return None


async def _ensure_location(ctx: SeedContext, name: str, archived: bool = False) -> int:
    """Get-or-create one stock location; archive only on the run that created it."""
    async with ctx.session_factory() as session:
        existing = await _location_by_name(session, name)
        if existing is not None:
            return existing.id

        location = await create_location(session, StockLocationCreate(name=name))
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="location.created",
            target_type="location",
            target_id=str(location.id),
            detail=f"Location created: {location.name}",
        )
        if archived:
            await update_location(session, location.id, StockLocationUpdate(active=False))
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="location.archived",
                target_type="location",
                target_id=str(location.id),
                detail=f"Location archived: {location.name}",
            )
        return location.id


async def _ensure_item(
    ctx: SeedContext,
    code: str,
    name: str,
    *,
    plum_part_id: str | None = None,
    archived: bool = False,
) -> str:
    """Get-or-create one inventory item; archive only on the run that created it."""
    async with ctx.session_factory() as session:
        existing = await _item_by_code(session, code)
        if existing is not None:
            return existing.id

        item = await create_item(
            session,
            InventoryItemCreate(
                code=code, name=name, unit_of_measure="ea", plum_part_id=plum_part_id
            ),
        )
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="item.created",
            target_type="item",
            target_id=str(item.id),
            detail=f"Item created: {item.name}",
        )
        if archived:
            await update_item(session, item.id, InventoryItemUpdate(active=False))
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="item.archived",
                target_type="item",
                target_id=str(item.id),
                detail=f"Item archived: {item.name}",
            )
        return item.id


async def _ensure_receipt(
    ctx: SeedContext, item_id: str, location_id: int, qty: Decimal, unit_cost: Decimal
) -> None:
    """
    Post one costed receipt, keyed on (item, location, qty, unit_cost).

    A receipt is an append-only ledger row with no natural key of its own, so the tuple of
    its own values IS the key: if a matching row already exists this run made it (or a
    previous one did) and posting again would double the stock. Matching on the tuple also
    means an owner's own mid-UAT receipt of a different quantity never blocks the fixture.
    """
    async with ctx.session_factory() as session:
        existing = await session.execute(
            text(
                "SELECT count(*) FROM syerp_inventory_txn WHERE item_id = :item_id "
                "AND location_id = :location_id AND txn_type = 'receipt' "
                "AND quantity = :qty AND unit_cost = :unit_cost"
            ),
            {
                "item_id": item_id,
                "location_id": location_id,
                "qty": qty,
                "unit_cost": unit_cost,
            },
        )
        if int(existing.scalar_one()) > 0:
            return

        txn = await post_receipt(
            session, item_id, location_id, qty, unit_cost, ctx.actor_id
        )
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="inventory.receipt",
            target_type="item",
            target_id=str(item_id),
            detail=f"Receipt {qty} @ {unit_cost} into location {txn.location_name}",
        )


async def _ensure_po(
    ctx: SeedContext,
    marker: str,
    vendor_id: str,
    lines: tuple[tuple[str, Decimal, Decimal], ...],
    item_ids: dict[str, str],
    *,
    approve: bool,
) -> None:
    """
    Get-or-create one purchase order keyed on its `notes` marker, with its lines.

    Found → returned UNCHANGED (not re-lined, not re-approved), so a PO the owner has
    already advanced or received against during the click-through survives a re-seed.
    """
    async with ctx.session_factory() as session:
        if await _po_by_notes(session, marker) is not None:
            return

        po = await create_po(session, POCreate(vendor_id=vendor_id, notes=marker))
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="po.created",
            target_type="purchase_order",
            target_id=str(po.id),
            detail=f"Purchase order created: {po.po_number}",
        )

    for code, qty_ordered, unit_cost in lines:
        async with ctx.session_factory() as session:
            line = await add_line(
                session,
                po.id,
                POLineCreate(
                    item_id=item_ids[code], qty_ordered=qty_ordered, unit_cost=unit_cost
                ),
            )
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="po.line_added",
                target_type="po_line",
                target_id=str(line.id),
                detail=f"PO line added: {code} qty={qty_ordered} @ {unit_cost}",
            )

    if approve:
        async with ctx.session_factory() as session:
            await advance_po_status(session, po.id, "approved", ctx.actor_id)
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="po.approved",
                target_type="purchase_order",
                target_id=str(po.id),
                detail=f"Purchase order approved: {po.po_number}",
            )


async def build_inventory_purchasing(ctx: SeedContext) -> None:
    """Get-or-create the locations, items, costed receipts and the two POs."""
    await _ensure_location(ctx, UAT_LOC_A)
    await _ensure_location(ctx, UAT_LOC_ARCHIVED, archived=True)

    async with ctx.session_factory() as session:
        plum_part_id = await _plum_part_id(session, INV_LINKED_PLUM_PART)

    await _ensure_item(
        ctx, INV_ITEM_LINKED, "UAT PLUM-linked stock item", plum_part_id=plum_part_id
    )
    await _ensure_item(ctx, INV_ITEM_STANDALONE, "UAT standalone stock item")
    await _ensure_item(ctx, INV_ITEM_ARCHIVED, "UAT archived stock item", archived=True)

    async with ctx.session_factory() as session:
        item_ids = {
            code: (await _item_by_code(session, code)).id
            for code in (INV_ITEM_LINKED, INV_ITEM_STANDALONE, INV_ITEM_ARCHIVED)
        }
        location_ids = {
            name: (await _location_by_name(session, name)).id
            for name in (DEFAULT_LOCATION_NAME, UAT_LOC_A)
        }

    for code, location_name, qty, unit_cost in INV_RECEIPTS:
        await _ensure_receipt(
            ctx, item_ids[code], location_ids[location_name], qty, unit_cost
        )

    async with ctx.session_factory() as session:
        vendors = {p.code: p.id for p in await list_partners(session, include_archived=True)}
    await _ensure_po(
        ctx, PO_DRAFT_KEY, vendors["UAT-VEND-1"], PO_DRAFT_LINES, item_ids, approve=False
    )
    await _ensure_po(
        ctx,
        PO_APPROVED_KEY,
        vendors["UAT-VEND-2"],
        PO_APPROVED_LINES,
        item_ids,
        approve=True,
    )


async def report_inventory_purchasing(ctx: SeedContext) -> None:
    """Read the inventory + purchasing literals back out of the REAL services."""
    manifest = ctx.manifest

    async with ctx.session_factory() as session:
        for location in sorted(
            (
                loc
                for loc in await list_locations(session, include_archived=True)
                if loc.name.startswith(FIXTURE_PREFIX)
            ),
            key=lambda loc: loc.name,
        ):
            name = manifest.key("syerp.location", location.name)
            manifest.value(f"syerp.location.{name}.active", str(location.active).lower())

        items = [
            item
            for item in await list_items(session, include_archived=True)
            if item.code.startswith(FIXTURE_PREFIX)
        ]
        for item in sorted(items, key=lambda i: i.code):
            code = manifest.key("syerp.item", item.code)
            manifest.value(f"syerp.item.{code}.name", item.name)
            manifest.value(f"syerp.item.{code}.active", str(item.active).lower())
            manifest.value(
                f"syerp.item.{code}.plum_linked", str(item.plum_part_id is not None).lower()
            )

            onhand = await get_item_onhand(session, item.id)
            manifest.value(f"syerp.item.{code}.moving_avg_cost", onhand.moving_avg_cost)
            manifest.value(f"syerp.item.{code}.total_quantity", onhand.total_quantity)
            manifest.value(f"syerp.item.{code}.onhand_value", onhand.onhand_value)
            for row in sorted(onhand.locations, key=lambda r: r.location_name):
                manifest.value(
                    f"syerp.item.{code}.onhand.{row.location_name}", row.quantity
                )

        # Independent oracle for the crux: recompute the weighted average from the
        # literal receipts rather than re-reading what the product stored.
        linked = await _item_by_code(session, INV_ITEM_LINKED)
        if linked is not None:
            receipts = [r for r in INV_RECEIPTS if r[0] == INV_ITEM_LINKED]
            total_qty = sum((r[2] for r in receipts), Decimal("0"))
            total_cost = sum((r[2] * r[3] for r in receipts), Decimal("0"))
            oracle_avg = (total_cost / total_qty).quantize(_COST_QUANTUM, ROUND_HALF_UP)
            onhand = await get_item_onhand(session, linked.id)
            _expect(f"{INV_ITEM_LINKED} moving_avg_cost", onhand.moving_avg_cost, oracle_avg)
            _expect(f"{INV_ITEM_LINKED} total_quantity", onhand.total_quantity, total_qty)
            _expect(
                f"{INV_ITEM_LINKED} onhand_value",
                onhand.onhand_value,
                total_qty * oracle_avg,
            )

        # Purchase orders — the PO-#### numbers are system-generated literals.
        item_codes = {item.id: item.code for item in await list_items(session, include_archived=True)}
        for marker in (PO_DRAFT_KEY, PO_APPROVED_KEY):
            po = await _po_by_notes(session, marker)
            if po is None:
                continue
            manifest.value(f"syerp.po.{marker}.po_number", po.po_number)
            manifest.value(f"syerp.po.{marker}.status", po.status)
            manifest.value(f"syerp.po.{marker}.line_count", len(po.lines))
            manifest.value(f"syerp.po.{marker}.total", po.total)
            manifest.value(f"syerp.po.{marker}.total_ordered_qty", po.total_ordered_qty)
            manifest.value(f"syerp.po.{marker}.total_received_qty", po.total_received_qty)
            manifest.value(f"syerp.po.{marker}.outstanding_qty", po.outstanding_qty)
            for line in sorted(po.lines, key=lambda line: line.line_no):
                label = f"syerp.po.{marker}.line{line.line_no}"
                manifest.value(
                    f"{label}",
                    f"{item_codes.get(line.item_id, line.item_id)} "
                    f"ordered={decimal_str(line.qty_ordered)} "
                    f"@ {decimal_str(line.unit_cost)} "
                    f"received={decimal_str(line.qty_received)}",
                )


INVENTORY_PURCHASING_LAYER = FixtureLayer(
    name="syerp-inventory+purchasing",
    tables=(
        TableSpec("syerp_stock_location", "name LIKE 'UAT-%'", "syerp_stock_location (UAT-)"),
        TableSpec("syerp_inventory_item", "code LIKE 'UAT-%'", "syerp_inventory_item (UAT-)"),
        TableSpec(
            "syerp_inventory_txn",
            "item_id IN (SELECT id FROM syerp_inventory_item WHERE code LIKE 'UAT-%')",
            "syerp_inventory_txn (UAT-)",
        ),
        TableSpec(
            "syerp_purchase_order", "notes LIKE 'UAT-%'", "syerp_purchase_order (UAT-)"
        ),
        TableSpec(
            "syerp_purchase_order_line",
            "po_id IN (SELECT id FROM syerp_purchase_order WHERE notes LIKE 'UAT-%')",
            "syerp_purchase_order_line (UAT-)",
        ),
    ),
    build=build_inventory_purchasing,
    report=report_inventory_purchasing,
)


# ---------------------------------------------------------------------------
# Layer: GELATO bins (Task 5)
# ---------------------------------------------------------------------------
#
# THE MOST LOAD-BEARING FIXTURE IN THE PHASE. SC6's three Phase-4 bin pickers are v4.0's
# only new UI surface and have never been human-driven; this layer is what makes their
# behavior observable, and in particular what makes the D-P4-1 pool floor BITE.
#
# THE CRUX — an EXACTLY-ZERO unbinned pool. Under D-P4-1 (explicit-or-unbinned) a NULL
# bin_id draws ONLY the location's unbinned pool and 422s when that pool is short. So an
# item whose stock at a location has been FULLY put away into bins must be IMPOSSIBLE to
# draw without naming a bin — that rejection is precisely what Task 25 asks the owner to
# see as a toast. A pool that merely reads zero in the manifest but is still drawable would
# silently void the whole SC6 check, so report_gelato ASSERTS the zero, and the build-time
# probe (recorded in the task report) drives a real NULL-bin negative adjustment and
# confirms the actual 422.
#
# A DEDICATED ITEM, on purpose. UAT-ITEM-4 is this layer's own item, so fully binning it
# cannot move UAT-ITEM-1/2's per-location on-hand literals that Task 24's read-only checks
# quote. Better still, it puts a contrast INSIDE one location: at UAT-LOC-A, UAT-ITEM-4 is
# fully binned (pool 0, must name a bin) while UAT-ITEM-1's 6 sit entirely unbinned (pool 6,
# drawable with no bin named). Two items, one location, opposite picker behavior.
#
# THE BIN-FREE LOCATION is UAT-LOC-NOBIN — a THIRD, dedicated location, not "Main" and not
# Task 4's archived UAT-LOC-ARCH. Main is out because the verify_*.py scripts create and
# clean up bins there, so its bin-free-ness is not a property this fixture can guarantee;
# UAT-LOC-ARCH is out because an archived location may not be offered by the pickers at all,
# which would test nothing. UAT-ITEM-4 also holds stock at UAT-LOC-NOBIN, so the SAME item
# shows both branches: switch the dialog's location and the bin picker must appear at
# UAT-LOC-A and vanish at UAT-LOC-NOBIN. (PLAN ## Noticed #1 records that the dialogs'
# docstrings are probably wrong about WHY the picker hides — not resolved here; this layer
# only makes the branch reachable.)
#
# THE BIN SPLIT is UNEVEN on purpose: 9 into UAT-BIN-A1, 6 into UAT-BIN-A2 out of 15. Neither
# bin quantity equals the other, and neither equals the location total, so a picker that
# showed one bin's on-hand as the location total, or split evenly at 7.5, is visibly wrong.
# 9 + 6 + 0 == 15 is the roll-up invariant this layer asserts at pool grain.

GELATO_BIN_LOCATION = UAT_LOC_A
GELATO_NOBIN_LOCATION = "UAT-LOC-NOBIN"
GELATO_BIN_1 = "UAT-BIN-A1"
GELATO_BIN_2 = "UAT-BIN-A2"
GELATO_BIN_ARCHIVED = "UAT-BIN-A3"

GELATO_ITEM = "UAT-ITEM-4"
GELATO_ITEM_COST = Decimal("3.10")
GELATO_BINNED_QTY = Decimal("15")  # received into UAT-LOC-A, then fully put away
GELATO_UNBINNED_QTY = Decimal("4")  # received into UAT-LOC-NOBIN, left unbinned
GELATO_PUTAWAY = ((GELATO_BIN_1, Decimal("9")), (GELATO_BIN_2, Decimal("6")))


async def _bin_by_code(session: AsyncSession, location_id: int, code: str):
    """Resolve a bin by its natural key (location, code) through the real list service."""
    bins = await list_bins(session, location_id, include_archived=True)
    return next((b for b in bins if b.code == code), None)


async def _ensure_bin(
    ctx: SeedContext, location_id: int, code: str, description: str, archived: bool = False
) -> int:
    """Get-or-create one bin; archive only on the run that created it."""
    async with ctx.session_factory() as session:
        existing = await _bin_by_code(session, location_id, code)
        if existing is not None:
            return existing.id

        bin_ = await create_bin(
            session, BinCreate(location_id=location_id, code=code, description=description)
        )
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="bin.created",
            target_type="bin",
            target_id=str(bin_.id),
            detail=f"Bin created: {bin_.code}",
        )
        if archived:
            await archive_bin(session, bin_.id)
            await write_audit(
                session,
                actor_id=ctx.actor_id,
                action="bin.archived",
                target_type="bin",
                target_id=str(bin_.id),
                detail=f"Bin archived: {bin_.code}",
            )
        return bin_.id


async def _ensure_putaway(
    ctx: SeedContext, item_id: str, location_id: int, to_bin_id: int, qty: Decimal
) -> None:
    """
    Put `qty` away from the unbinned pool into one bin, keyed on the resulting ledger leg.

    Like a receipt, a putaway leg has no natural key, so the value tuple IS the key: an
    existing `+qty` putaway row into this bin means the move already happened. Keying on
    the LEDGER rather than on the bin's current on-hand matters — if the owner moves that
    stock elsewhere mid-UAT, a re-seed must NOT try to put it away again and 422 against an
    empty pool.
    """
    async with ctx.session_factory() as session:
        existing = await session.execute(
            text(
                "SELECT count(*) FROM syerp_inventory_txn WHERE item_id = :item_id "
                "AND location_id = :location_id AND bin_id = :bin_id "
                "AND txn_type = 'putaway' AND quantity = :qty"
            ),
            {"item_id": item_id, "location_id": location_id, "bin_id": to_bin_id, "qty": qty},
        )
        if int(existing.scalar_one()) > 0:
            return

        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id,
                location_id=location_id,
                from_bin_id=None,  # draw the unbinned pool
                to_bin_id=to_bin_id,
                qty=qty,
            ),
            ctx.actor_id,
        )
        await write_audit(
            session,
            actor_id=ctx.actor_id,
            action="inventory.putaway",
            target_type="item",
            target_id=str(item_id),
            detail=f"Putaway {qty} into bin {to_bin_id} at location {location_id}",
        )


async def build_gelato(ctx: SeedContext) -> None:
    """Get-or-create the bins, the bin-free location, and the fully-binned item."""
    nobin_location_id = await _ensure_location(ctx, GELATO_NOBIN_LOCATION)

    async with ctx.session_factory() as session:
        bin_location_id = (await _location_by_name(session, GELATO_BIN_LOCATION)).id

    bin_ids = {
        GELATO_BIN_1: await _ensure_bin(
            ctx, bin_location_id, GELATO_BIN_1, "UAT active bin (holds the larger split)"
        ),
        GELATO_BIN_2: await _ensure_bin(
            ctx, bin_location_id, GELATO_BIN_2, "UAT active bin (holds the smaller split)"
        ),
    }
    await _ensure_bin(
        ctx, bin_location_id, GELATO_BIN_ARCHIVED, "UAT archived bin", archived=True
    )

    item_id = await _ensure_item(ctx, GELATO_ITEM, "UAT fully-binned stock item")
    await _ensure_receipt(ctx, item_id, bin_location_id, GELATO_BINNED_QTY, GELATO_ITEM_COST)
    await _ensure_receipt(
        ctx, item_id, nobin_location_id, GELATO_UNBINNED_QTY, GELATO_ITEM_COST
    )

    # Fully put the UAT-LOC-A stock away — 9 + 6 == 15 leaves the unbinned pool at EXACTLY
    # zero, which is the entire point of this layer.
    for code, qty in GELATO_PUTAWAY:
        await _ensure_putaway(ctx, item_id, bin_location_id, bin_ids[code], qty)


async def report_gelato(ctx: SeedContext) -> None:
    """Read the bin-grain literals back out of the REAL services, and assert the crux."""
    manifest = ctx.manifest

    async with ctx.session_factory() as session:
        bin_location = await _location_by_name(session, GELATO_BIN_LOCATION)
        nobin_location = await _location_by_name(session, GELATO_NOBIN_LOCATION)
        item = await _item_by_code(session, GELATO_ITEM)
        if bin_location is None or item is None:
            return

        for bin_ in await list_bins(session, bin_location.id, include_archived=True):
            if not bin_.code.startswith(FIXTURE_PREFIX):
                continue
            code = manifest.key("gelato.bin", bin_.code)
            manifest.value(f"gelato.bin.{code}.location", bin_location.name)
            manifest.value(f"gelato.bin.{code}.active", str(bin_.active).lower())
            manifest.value(
                f"gelato.bin.{code}.onhand.{GELATO_ITEM}",
                await get_bin_on_hand(session, item.id, bin_location.id, bin_.id),
            )

        # THE CRUX — the unbinned pool at the fully-binned location must be EXACTLY zero.
        pool = await get_bin_on_hand(session, item.id, bin_location.id, None)
        manifest.value(f"gelato.unbinned.{GELATO_BIN_LOCATION}.{GELATO_ITEM}", pool)
        _expect(f"{GELATO_ITEM} unbinned pool at {GELATO_BIN_LOCATION}", pool, Decimal("0"))

        # Putaway is net-zero at location grain: the location total still equals the
        # RECEIPT quantity, and Σ(bins) + unbinned reconstructs it exactly.
        onhand = await get_item_onhand(session, item.id)
        by_location = {row.location_name: row.quantity for row in onhand.locations}
        binned_total = by_location.get(GELATO_BIN_LOCATION, Decimal("0"))
        _expect(
            f"{GELATO_ITEM} location total at {GELATO_BIN_LOCATION} (putaway is net-zero)",
            binned_total,
            GELATO_BINNED_QTY,
        )
        bin_sum = Decimal("0")
        for bin_ in await list_bins(session, bin_location.id, include_archived=True):
            bin_sum += await get_bin_on_hand(session, item.id, bin_location.id, bin_.id)
        _expect(
            f"{GELATO_ITEM} roll-up at {GELATO_BIN_LOCATION} (Σbins + unbinned == total)",
            bin_sum + pool,
            binned_total,
        )
        manifest.value(
            f"gelato.rollup.{GELATO_BIN_LOCATION}.{GELATO_ITEM}",
            f"bins {decimal_str(bin_sum)} + unbinned {decimal_str(pool)} "
            f"== location total {decimal_str(binned_total)}",
        )

        # The bin-free location: the SAME item, all of it unbinned, and zero bins. Its
        # syerp.location key is recorded by the inventory layer's reporter (which reports
        # every UAT- location), so only the bin-grain facts are added here.
        if nobin_location is not None:
            name = nobin_location.name
            manifest.value(
                f"gelato.bins_at.{name}",
                len(await list_bins(session, nobin_location.id, include_archived=True)),
            )
            manifest.value(
                f"gelato.unbinned.{name}.{GELATO_ITEM}",
                await get_bin_on_hand(session, item.id, nobin_location.id, None),
            )
        # …and the bin-bearing location's own bin count, for the same picker branch.
        manifest.value(
            f"gelato.bins_at.{GELATO_BIN_LOCATION}",
            len(await list_bins(session, bin_location.id, include_archived=True)),
        )

        # The contrast case, same location, different item: UAT-ITEM-1's stock at
        # UAT-LOC-A is entirely UNBINNED, so it IS drawable without naming a bin.
        contrast = await _item_by_code(session, INV_ITEM_LINKED)
        if contrast is not None:
            manifest.value(
                f"gelato.unbinned.{GELATO_BIN_LOCATION}.{INV_ITEM_LINKED}",
                await get_bin_on_hand(session, contrast.id, bin_location.id, None),
            )


GELATO_LAYER = FixtureLayer(
    name="gelato-bins",
    tables=(
        TableSpec("gelato_bin", "code LIKE 'UAT-%'", "gelato_bin (UAT-)"),
    ),
    build=build_gelato,
    report=report_gelato,
)


def _layers() -> tuple[FixtureLayer, ...]:
    """
    The registered fixture layers, in DEPENDENCY order (builders run in this order).

    PLUM depends on core+partners (AVL links point at the UAT vendors); inventory depends
    on both (its PLUM-linked item points at UAT-P101, its POs at the UAT vendors); GELATO
    depends on inventory (its bins subdivide UAT-LOC-A and it stocks its own item).

    Tasks 6-7 append here:
      6. MOUSSE + CRUMB   7. SYERP GL / AP / AR
    """
    return (CORE_PARTNERS_LAYER, PLUM_LAYER, INVENTORY_PURCHASING_LAYER, GELATO_LAYER)


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
