# ABOUTME: FLAN (Project Management) Pydantic request/response schemas —
# ABOUTME: project create/update/read (with its opaque tag list) and phase
# ABOUTME: create/update/read (FLAN-01.1, FLAN-01.2).
# ABOUTME: The phase WRITE schemas carry no date and no percent field at all:
# ABOUTME: those three values are derived from the phase's tasks on every read
# ABOUTME: (D-V5-1), so "never hand-set" is structural, not a rule to remember.
"""
FLAN Pydantic schemas (request/response models) — FLAN-01.

Separation (mirrors gelato/schemas.py):
  - Input schemas (Create/Update): no from_attributes — they validate incoming
    JSON. Update schemas are all-optional PATCH payloads.
  - Response schemas (Read): from_attributes=True where they serialize an ORM
    instance; service-DERIVED figures (a phase's rolled-up dates, percentage and
    task counts; a project's tag list, which lives in its own join table) are
    plain fields the service fills.

Two rules are load-bearing here:

  * **No date or percent field appears anywhere in the phase write schemas**
    (D-V5-1). `flan_phase` has no such column, `PhaseCreate`/`PhaseUpdate` have
    no such field, and `PhaseRead` names its rolled-up dates `derived_*` so a
    caller cannot mistake them for something it may send back. A `PhaseUpdate`
    carrying a `due_date` is the exact defect this shape prevents.
  * **`percent_complete` crosses the wire as a string, never a float** (D-11).
    The service computes it as a quantized `Decimal`; the before-validator below
    formats a `Decimal` to two places and a `float` is refused outright.

A Phase-1 tag is an **opaque string** (D-V5P1-5): tags are stripped, rejected
when blank, and de-duplicated case-sensitively (`"Client"` and `"client"` are
two different tags). No `Facet:Value` parsing, no exclusivity rules and no
reserved facets exist yet — that is FLAN-04, next phase.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# --- Projects --- create / update / read (FLAN-01.1)
# ---------------------------------------------------------------------------

# Phase status values, matching the flan_phase.status column (FLAN-01.2)
PhaseStatus = Literal["pending", "in-progress", "complete"]

# key_prefix: leading letter then up to nine alphanumerics — the task-key prefix
# (D-V5P1-2); the service derives one from the project name when it is omitted
KEY_PREFIX_PATTERN = r"^[A-Za-z][A-Za-z0-9]{0,9}$"


def _normalize_tags(tags: list[str]) -> list[str]:
    """
    Strip, validate and de-duplicate an incoming tag list (D-V5P1-5).

    Each tag is stripped of surrounding whitespace; a tag that is empty after
    stripping is rejected (a blank tag is not a tag), as is one longer than the
    60-character `flan_project_tag.tag` column. De-duplication is
    **case-sensitive** and order-preserving: in Phase 1 a tag is an opaque
    string, so "Client" and "client" are deliberately two distinct tags.
    """
    seen: list[str] = []
    for raw in tags:
        tag = raw.strip()
        if not tag:
            raise ValueError("A tag must not be empty or whitespace-only.")
        if len(tag) > 60:
            raise ValueError(f"Tag exceeds 60 characters: {tag[:20]}…")
        if tag not in seen:
            seen.append(tag)
    return seen


class ProjectCreate(BaseModel):
    """
    Project creation payload (POST /flan/projects).

    `name` is required and duplicates ARE allowed (FLAN-01.1), so nothing here
    enforces uniqueness. `key_prefix` is optional: when omitted the service
    derives it from the name (D-V5P1-2); when supplied it must match
    KEY_PREFIX_PATTERN. `category` classifies the project (work | personal |
    client | none) and `currency` defaults to USD so no caller has to send it.
    `start_date` and `gate_date` are the project's own hand-set dates — unlike a
    phase's, which are derived.

    `tags` are opaque strings (D-V5P1-5), defaulting to none; they are stripped,
    rejected when blank and de-duplicated case-sensitively. `id`, `active` and
    the timestamps are server-owned and so absent here.
    """

    name: str = Field(..., min_length=1)
    key_prefix: str | None = Field(None, pattern=KEY_PREFIX_PATTERN)
    category: str | None = Field(None, max_length=30)
    description: str | None = None
    currency: str = Field("USD", min_length=3, max_length=3)
    start_date: date | None = None
    gate_date: date | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Strip, reject-if-blank and de-duplicate the tag list (D-V5P1-5)."""
        return _normalize_tags(value)


class ProjectUpdate(BaseModel):
    """
    Project PATCH payload (PATCH /flan/projects/{project_id}).

    All fields optional — only the supplied fields are changed. `id` is absent
    because the project id is immutable (FLAN-01.1), and `active` is absent
    because archiving is its own endpoint (POST /flan/projects/{id}/archive),
    not a field a general update can flip. `key_prefix` is settable only while
    the project has no tasks; the service refuses it afterwards with a 422
    (D-V5P1-2). Supplying `tags` REPLACES the project's tag set with the
    normalized list.
    """

    name: str | None = Field(None, min_length=1)
    key_prefix: str | None = Field(None, pattern=KEY_PREFIX_PATTERN)
    category: str | None = Field(None, max_length=30)
    description: str | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    start_date: date | None = None
    gate_date: date | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        """Strip, reject-if-blank and de-duplicate the tag list (D-V5P1-5)."""
        return None if value is None else _normalize_tags(value)


class ProjectRead(BaseModel):
    """
    Project returned to API callers, serialized from a Project ORM instance via
    from_attributes=True.

    `key_prefix` is the project's task-key prefix and `active` is the archive
    flag — False means archived: the project keeps all its data and rejects
    writes (FLAN-01.1). `tags` is service-filled from `flan_project_tag` (it is
    a join table, not a column, so it defaults to none when unfetched).
    """

    id: str
    name: str
    key_prefix: str
    category: str | None = None
    description: str | None = None
    currency: str
    start_date: date | None = None
    gate_date: date | None = None
    active: bool
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# --- Phases --- create / update / read (FLAN-01.2, D-V5-1)
# ---------------------------------------------------------------------------


class PhaseCreate(BaseModel):
    """
    Phase creation payload (POST /flan/projects/{project_id}/phases).

    `name` is required; `sort_order` drives display order within the project and
    `status` walks pending → in-progress → complete. `project_id` comes from the
    path (the service sets it, never the client), and `id`/`created_at` are
    server-owned.

    **There is deliberately no start_date, due_date or percent_complete field**
    (D-V5-1): a phase's dates and % complete are derived from its tasks on every
    read and can never be hand-set — omitting the fields makes that structural.
    """

    name: str = Field(..., min_length=1)
    sort_order: int = 0
    status: PhaseStatus = "pending"
    description: str | None = None


class PhaseUpdate(BaseModel):
    """
    Phase PATCH payload (PATCH /flan/phases/{phase_id}).

    All fields optional — only the supplied fields are changed. `project_id` is
    absent because a phase belongs to exactly one project for its whole life
    (FLAN-01.2).

    **No date or percent field exists here, by design** (D-V5-1): a PhaseUpdate
    carrying `due_date` or `percent_complete` is precisely the defect this shape
    exists to prevent. Those three values are derived in the read rollup.
    """

    name: str | None = Field(None, min_length=1)
    sort_order: int | None = None
    status: PhaseStatus | None = None
    description: str | None = None


class PhaseRead(BaseModel):
    """
    Phase returned to API callers — an ORM row plus its service-computed rollup.

    The identity fields (`id`, `project_id`, `name`, `sort_order`, `status`,
    `description`) come from the Phase ORM instance; the last five are DERIVED
    per read from the phase's tasks and stored in no column (D-V5-1):

      - `derived_start_date` — the earliest task start date (NULL when the phase
        has no tasks, and also when none of its tasks carries a start date,
        since SQL MIN skips NULLs);
      - `derived_due_date` — the latest task due date, same NULL semantics;
      - `percent_complete` — the share of the phase's tasks in status Done, as a
        two-decimal STRING (never a float — D-11); an empty phase reports
        "0.00";
      - `task_count` / `done_count` — the counts that percentage came from, so a
        caller can show "2 of 5" without recomputing it.

    They are named `derived_*` so no caller mistakes them for something it may
    send back: no write schema in this module accepts them.
    """

    id: str
    project_id: str
    name: str
    sort_order: int
    status: str
    description: str | None = None

    # --- Derived per read from the phase's tasks — never stored (D-V5-1) ----
    derived_start_date: date | None = None
    derived_due_date: date | None = None
    percent_complete: str
    task_count: int
    done_count: int

    model_config = ConfigDict(from_attributes=True)

    @field_validator("percent_complete", mode="before")
    @classmethod
    def percent_as_string(cls, value: object) -> object:
        """
        Format the rollup's quantized Decimal to a two-place string (D-11).

        The service computes the percentage as a Decimal; it crosses the wire as
        a string so no float ever represents it. A float reaching this field is
        left untouched and rejected by the `str` annotation — deliberately.
        """
        if isinstance(value, Decimal):
            return f"{value:.2f}"
        return value


# --- Tasks, roster and assignment schemas: Task 8 ---
