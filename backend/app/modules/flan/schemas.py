# ABOUTME: FLAN (Project Management) Pydantic request/response schemas —
# ABOUTME: project, phase, task, team-roster and assignment create/update/read,
# ABOUTME: each with its opaque tag list (FLAN-01.1 through FLAN-01.5).
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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

# ---------------------------------------------------------------------------
# --- Tasks --- create / update / read (FLAN-01.3)
# ---------------------------------------------------------------------------

# Task status values, matching the flan_task.status column; the Done share is
# what a phase's derived percent_complete counts (FLAN-01.3, D-V5-1)
TaskStatus = Literal["To Do", "In Progress", "Done"]

# Task risk levels, matching the flan_task.risk_level column (FLAN-01.3)
RiskLevel = Literal["none", "low", "medium", "high"]


def _check_date_order(start: date | None, due: date | None) -> None:
    """
    Reject a task whose due date precedes its start date (FLAN-01.3).

    `due == start` is a **valid zero-duration milestone** and passes; only
    `due < start` raises. Either date being None is fine — a task may carry one,
    both or neither.

    This can only judge the two dates it can see. A PATCH that moves ONLY one of
    them passes here by construction, because the schema cannot read the stored
    row; `update_task` re-checks the order over the MERGED values (Task 14). That
    service check is load-bearing, not belt-and-braces.
    """
    if start is not None and due is not None and due < start:
        raise ValueError(
            f"due_date ({due}) must not precede start_date ({start}); "
            "due_date == start_date is a valid zero-duration milestone."
        )


def _normalize_member_ids(member_ids: list[str]) -> list[str]:
    """
    Strip and de-duplicate a list of roster member ids, order-preserving.

    Assignment rows are keyed `(task_id, member_id)` / `(phase_id, member_id)`,
    so a payload naming the same member twice would collide on the composite PK
    at insert. De-duplicating here makes the repeat a no-op rather than a 500.
    Membership itself (active, same project) is the service's call — the schema
    knows no project scope.
    """
    seen: list[str] = []
    for raw in member_ids:
        member_id = raw.strip()
        if not member_id:
            raise ValueError("A member id must not be empty or whitespace-only.")
        if member_id not in seen:
            seen.append(member_id)
    return seen


class TaskCreate(BaseModel):
    """
    Task creation payload (POST /flan/projects/{project_id}/tasks).

    `phase_id` and `summary` are required. Two fields are deliberately ABSENT:

      * **`key`** — the task key is server-generated as `<PREFIX>-<n>` from the
        project's key_prefix (D-V5P1-2, D-V5P1-7) under a row lock, and is never
        client-supplied. There is no field for a caller to fight over.
      * **`project_id`** — the service sets it from the phase, so a task can
        never claim a project its phase does not belong to.

    `start_date`/`due_date` are optional and `due == start` is a valid
    zero-duration milestone; only `due < start` is refused (422 here, re-checked
    in the service). `assignee_ids` names roster members to link on create; the
    service validates each is an ACTIVE member of the same project (FLAN-01.5).
    `tags` are opaque strings (D-V5P1-5), same rules as a project's.
    """

    phase_id: str
    summary: str = Field(..., min_length=1)
    status: TaskStatus = "To Do"
    risk_level: RiskLevel = "none"
    start_date: date | None = None
    due_date: date | None = None
    pinned: bool = False
    assignee_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Strip, reject-if-blank and de-duplicate the tag list (D-V5P1-5)."""
        return _normalize_tags(value)

    @field_validator("assignee_ids")
    @classmethod
    def normalize_assignee_ids(cls, value: list[str]) -> list[str]:
        """Strip and de-duplicate the assignee list (composite-PK safety)."""
        return _normalize_member_ids(value)

    @model_validator(mode="after")
    def check_date_order(self) -> TaskCreate:
        """Refuse `due_date < start_date`; `due == start` is a milestone."""
        _check_date_order(self.start_date, self.due_date)
        return self


class TaskUpdate(BaseModel):
    """
    Task PATCH payload (PATCH /flan/tasks/{task_id}).

    All fields optional — only the supplied fields are changed. `key` and
    `project_id` are absent because both are immutable: the key is
    server-generated once (D-V5P1-2) and the project follows the phase.
    `phase_id` IS present — moving a task to another phase of the SAME project
    is allowed (the service 422s a cross-project move).

    The date check here sees only what the payload carries. **A PATCH that moves
    only one of the two dates passes this schema** — it cannot read the stored
    row — so `update_task` re-checks the order over the merged values (Task 14).
    Supplying `tags` or `assignee_ids` REPLACES the respective set.
    """

    phase_id: str | None = None
    summary: str | None = Field(None, min_length=1)
    status: TaskStatus | None = None
    risk_level: RiskLevel | None = None
    start_date: date | None = None
    due_date: date | None = None
    pinned: bool | None = None
    assignee_ids: list[str] | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        """Strip, reject-if-blank and de-duplicate the tag list (D-V5P1-5)."""
        return None if value is None else _normalize_tags(value)

    @field_validator("assignee_ids")
    @classmethod
    def normalize_assignee_ids(cls, value: list[str] | None) -> list[str] | None:
        """Strip and de-duplicate the assignee list (composite-PK safety)."""
        return None if value is None else _normalize_member_ids(value)

    @model_validator(mode="after")
    def check_date_order(self) -> TaskUpdate:
        """
        Refuse `due_date < start_date` when the payload carries BOTH dates.

        A one-date PATCH is invisible here by construction; the service's merged
        re-check is what closes that gap.
        """
        _check_date_order(self.start_date, self.due_date)
        return self


class TaskRead(BaseModel):
    """
    Task returned to API callers, serialized from a Task ORM instance via
    from_attributes=True.

    `key` is the human handle (`<PREFIX>-<n>`, unpadded — D-V5P1-7) and
    `project_id` is carried alongside `phase_id` so a client never has to walk
    the tree to learn the scope. `assignee_ids` and `tags` are service-filled
    from `flan_task_assignee` / `flan_task_tag` (join tables, not columns, hence
    the empty defaults when unfetched).
    """

    id: str
    project_id: str
    phase_id: str
    key: str
    summary: str
    status: str
    risk_level: str
    start_date: date | None = None
    due_date: date | None = None
    pinned: bool
    assignee_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# --- Team roster --- create / update / read (FLAN-01.4)
# ---------------------------------------------------------------------------


class TeamMemberCreate(BaseModel):
    """
    Roster member creation payload (POST /flan/projects/{project_id}/team).

    `name` is the only required field, so a person can be rostered before an
    email or a platform account exists. `project_id` comes from the path — the
    roster is per-project by design (FLAN-01.4), so the same person on two
    projects is two rows.

    `user_id` optionally links the member to a platform user and is **normally
    None**: an unlinked member is fully usable as an assignee. The service
    checks the user exists and that no other active member of the project
    already links it (uq_flan_member_project_user).

    `hourly_rate` is a fixed-point Decimal (never float — D-11) and is
    **stored and read by nothing in v5.0** (D-V5-2 / D-M5-2): no rollup, report
    or endpoint in this release computes cost from it. It crosses the wire as a
    JSON string, matching `Decimal` handling everywhere else in the platform.

    `active` is absent — it is the soft-remove flag, owned by
    DELETE /flan/team/{member_id} (which also clears the member's assignment
    rows, D-V5P1-6); a member is always created active.
    """

    name: str = Field(..., min_length=1)
    role: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=7)
    hourly_rate: Decimal | None = Field(None, ge=0)
    user_id: str | None = None


class TeamMemberUpdate(BaseModel):
    """
    Roster member PATCH payload (PATCH /flan/team/{member_id}).

    All fields optional — only the supplied fields are changed. `project_id` is
    absent because a member belongs to exactly one project's roster for its
    whole life (FLAN-01.4).

    `active` is absent for the same reason it is absent from ProjectUpdate:
    removal is its own endpoint (DELETE /flan/team/{member_id}), a soft-remove
    that ALSO deletes the member's `flan_task_assignee` / `flan_phase_assignee`
    rows in the same transaction (D-V5P1-6). A PATCH able to flip the flag on
    its own would leave those assignment rows orphaned — exactly the state the
    soft-remove exists to prevent.

    `hourly_rate` remains stored-and-unread in v5.0 (D-V5-2 / D-M5-2).
    """

    name: str | None = Field(None, min_length=1)
    role: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=7)
    hourly_rate: Decimal | None = Field(None, ge=0)
    user_id: str | None = None


class TeamMemberRead(BaseModel):
    """
    Roster member returned to API callers, serialized from a TeamMember ORM
    instance via from_attributes=True.

    `active` is the soft-remove flag — False means removed: the row is retained
    so historical references still resolve, but the member is excluded from
    assignee pickers and from the default roster listing (FLAN-01.4). `user_id`
    is None for the common unlinked member. `hourly_rate` is emitted as a JSON
    string (never a float — D-11) and, in v5.0, is read by nothing (D-V5-2 /
    D-M5-2) — it is returned for display and round-tripping only.
    """

    id: str
    project_id: str
    name: str
    role: str | None = None
    email: str | None = None
    color: str | None = None
    hourly_rate: Decimal | None = None
    user_id: str | None = None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# --- Assignment --- full-replacement assignee set (FLAN-01.5)
# ---------------------------------------------------------------------------


class AssigneeSet(BaseModel):
    """
    Assignee replacement payload for PUT /flan/tasks/{task_id}/assignees and
    PUT /flan/phases/{phase_id}/assignees.

    It is a PUT, not a PATCH: `member_ids` is the COMPLETE assignee list after
    the call, and the service replaces the existing rows with it. An empty list
    is valid and means "no assignees" — that is how assignments are cleared.

    Ids are stripped and de-duplicated here; the service enforces the part the
    schema cannot see: every id must name an ACTIVE member of the SAME project
    as the target (422 naming the offending id), which is what makes "assignees
    drawn from the project roster" (FLAN-01.5) enforced rather than
    conventional.
    """

    member_ids: list[str] = Field(default_factory=list)

    @field_validator("member_ids")
    @classmethod
    def normalize_member_ids(cls, value: list[str]) -> list[str]:
        """Strip, reject-if-blank and de-duplicate the member id list."""
        return _normalize_member_ids(value)
