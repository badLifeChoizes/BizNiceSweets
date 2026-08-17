# ABOUTME: Pins UAT defect U0 (v4.0 Phase 5, D-P5-10) — the fresh-volume deploy blocker.
# ABOUTME: Asserts the compose `db` service resolves POSTGRES_PASSWORD from a DEDICATED
# ABOUTME: env_file rather than a bare ${POSTGRES_PASSWORD} interpolation (which silently
# ABOUTME: expands to empty and breaks only a FRESH volume), and that the file it reads is
# ABOUTME: NOT the app `.env` — so the secret-spread regression is caught too. Also pins the
# ABOUTME: UAT-seed opt-in split (Phase-5 review finding 1): the dev overlay sets
# ABOUTME: BNS_ALLOW_UAT_SEED=1, the production file never does.
"""
Compose configuration invariants for defect U0 (v4.0 Phase 5).

WHAT U0 WAS
  `compose/compose.yml`'s `db` service took its password from a bare
  ``POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`` interpolation. Compose resolves
  ``${...}`` against the compose file's OWN directory (``compose/``), where no
  ``.env`` exists, so it expanded to the empty string and the container started
  with ``POSTGRES_PASSWORD=``. An ALREADY-INITIALIZED Postgres data directory does
  not need the password at start-up, so the fault was invisible for the entire life
  of a volume and fired only on a genuinely FRESH one:

      Error: Database is uninitialized and superuser password is not specified.

  i.e. it broke exactly one scenario — somebody's first-ever deploy — which is the
  scenario the project's whole self-hosting value proposition rests on.

WHY THIS IS A CONFIG TEST AND NOT A BRING-UP TEST
  The honest proof is `podman-compose down -v` followed by a fresh `up`, and that is
  far too heavy (and too privileged) for CI. So this pins the CONFIG INVARIANT that
  made the bring-up fail. It is cheap, runs in the existing `backend-tests` job, and
  fails on revert — which is what D-P5-4 requires of a blocker fix.

WHY IT IS PARSED TEXTUALLY RATHER THAN WITH PyYAML
  PyYAML happens to be present in the local venv, but it is declared in NEITHER
  `requirements.txt` NOR `requirements-dev.txt`, and CI installs only those. An
  ``import yaml`` would therefore ImportError in CI — a RED for the wrong reason,
  which is the trap this project has been bitten by twice. So the service block is
  extracted structurally by indentation and matched line-by-line, with comments
  stripped FIRST. Stripping comments is load-bearing: the pre-fix file carried the
  comment "POSTGRES_PASSWORD comes from ../.env (env_file)", so a naive substring
  search for "env_file" would have PASSED against the broken config.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE = _REPO_ROOT / "compose" / "compose.yml"
_COMPOSE_DEV = _REPO_ROOT / "compose" / "compose.dev.yml"

# The UAT-seed opt-in (Phase-5 review finding 1). podman-compose names BOTH stacks
# after the compose/ directory, so prod and dev share the container `compose_api_1`
# and the documented `podman exec … seed_uat_fixtures.py` cannot tell them apart.
# This variable is what does: the dev overlay declares itself a UAT stack, the prod
# file never may.
_UAT_SEED_OPT_IN = "BNS_ALLOW_UAT_SEED"

# The app env file — the one carrying JWT_SECRET / BNS_ADMIN_PASSWORD. The db
# container must never be pointed at it (that was the rejected "easy" fix).
_APP_ENV_FILE = "../.env"
_DB_ENV_FILE = "../.env.db"


def _strip_comment(line: str) -> str:
    """
    Drop a trailing ``#`` comment, ignoring ``#`` inside a quoted string.

    Comments must go before any matching: the pre-fix compose file documented an
    env_file for `db` in a comment while not actually configuring one.
    """
    out, quote = [], None
    for char in line:
        if quote:
            out.append(char)
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
            out.append(char)
        elif char == "#":
            break
        else:
            out.append(char)
    return "".join(out).rstrip()


def _service_block(text: str, service: str) -> list[str]:
    """
    Return the comment-stripped, non-blank lines belonging to one compose service.

    Services sit at 2-space indentation under ``services:``; the block runs until
    the next key at that same indentation (or EOF).
    """
    lines = text.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if _strip_comment(ln) == f"  {service}:"), None
    )
    assert start is not None, f"no `{service}:` service found in {_COMPOSE}"

    block: list[str] = []
    for raw in lines[start + 1 :]:
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if indent <= 2:
            break  # next service, or a top-level key
        block.append(stripped)
    return block


def _env_files(block: list[str]) -> list[str]:
    """
    Collect the env_file value(s) from a service block.

    Handles both compose spellings: the scalar ``env_file: ../x`` and the list
    form ``env_file:`` followed by ``- ../x`` items.
    """
    files: list[str] = []
    for idx, line in enumerate(block):
        match = re.match(r"^\s*env_file:\s*(.*)$", line)
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            files.append(inline.strip("'\""))
            continue
        # List form: consume the more-indented `- item` lines that follow.
        key_indent = len(line) - len(line.lstrip())
        for follower in block[idx + 1 :]:
            f_indent = len(follower) - len(follower.lstrip())
            item = follower.strip()
            if f_indent <= key_indent or not item.startswith("- "):
                break
            files.append(item[2:].strip().strip("'\""))
    return files


@pytest.fixture(scope="module")
def compose_text() -> str:
    assert _COMPOSE.is_file(), f"compose file not found at {_COMPOSE}"
    return _COMPOSE.read_text(encoding="utf-8")


def test_db_service_reads_password_from_an_env_file(compose_text: str) -> None:
    """U0: `db` must take POSTGRES_PASSWORD from an env_file, not interpolation."""
    block = _service_block(compose_text, "db")
    env_files = _env_files(block)

    assert env_files, (
        "compose `db` service declares NO env_file. This is defect U0: a bare "
        "${POSTGRES_PASSWORD} interpolation resolves against compose/ (which has no "
        ".env), expands to the empty string, and Postgres refuses to initialize a "
        "FRESH volume — while an existing volume keeps working, hiding the fault."
    )

    interpolated = [
        line
        for line in block
        if re.search(r"POSTGRES_PASSWORD:\s*\$\{POSTGRES_PASSWORD", line)
    ]
    assert not interpolated, (
        "compose `db` service still sets POSTGRES_PASSWORD by interpolation: "
        f"{interpolated!r}. An `environment:` entry takes PRECEDENCE over env_file, "
        "so this silently overrides the file value with an empty string — U0 again."
    )


def test_db_service_does_not_read_the_app_secrets(compose_text: str) -> None:
    """D-P5-10: the db container must not be handed JWT_SECRET / BNS_ADMIN_PASSWORD."""
    env_files = _env_files(_service_block(compose_text, "db"))
    assert _APP_ENV_FILE not in env_files, (
        f"compose `db` service reads {_APP_ENV_FILE!r}, which carries JWT_SECRET and "
        "BNS_ADMIN_PASSWORD. The database container needs neither; this is the "
        "secret-spread fix that D-P5-10 explicitly rejected. Point `db` at "
        f"{_DB_ENV_FILE!r} instead."
    )
    assert _DB_ENV_FILE in env_files, (
        f"compose `db` service should read {_DB_ENV_FILE!r} (D-P5-10); got {env_files!r}."
    )


def test_api_service_also_reads_the_db_credentials(compose_text: str) -> None:
    """
    The api authenticates to Postgres, so it needs the same credentials.

    Guards the other half of the split: if POSTGRES_PASSWORD has exactly one home,
    removing it from the app `.env` without adding `.env.db` to the api would break
    the backend instead of the database — the same outage, one container over.
    """
    env_files = _env_files(_service_block(compose_text, "api"))
    assert _DB_ENV_FILE in env_files, (
        f"compose `api` service must also read {_DB_ENV_FILE!r} — POSTGRES_PASSWORD "
        f"lives there and only there (D-P5-10); got {env_files!r}."
    )
    assert _APP_ENV_FILE in env_files, (
        f"compose `api` service must still read {_APP_ENV_FILE!r} for JWT_SECRET and "
        f"BNS_ADMIN_PASSWORD; got {env_files!r}."
    )


def test_prod_compose_never_declares_itself_a_uat_stack(compose_text: str) -> None:
    """
    Finding 1: `compose.yml` must not set BNS_ALLOW_UAT_SEED — anywhere.

    The seeder writes append-only journal entries and an active login whose password
    is in this repository. Its only defence against being pointed at a self-hoster's
    real books is that the production stack does not opt in, so this is asserted over
    the WHOLE file (comment-stripped), not just the `api` block.
    """
    offenders = [
        line for line in compose_text.splitlines() if _UAT_SEED_OPT_IN in _strip_comment(line)
    ]
    assert not offenders, (
        f"compose/compose.yml sets {_UAT_SEED_OPT_IN}: {offenders!r}. The production "
        "stack must never opt into the UAT fixture seed — a deliberate load into a "
        f"prod artifact passes `-e {_UAT_SEED_OPT_IN}=1` on the podman exec line."
    )


def test_dev_overlay_declares_itself_a_uat_stack() -> None:
    """The other half: without the overlay's opt-in the documented runbook stops working."""
    assert _COMPOSE_DEV.is_file(), f"dev overlay not found at {_COMPOSE_DEV}"
    block = [
        line
        for line in _service_block(_COMPOSE_DEV.read_text(encoding="utf-8"), "api")
        if _UAT_SEED_OPT_IN in line
    ]
    assert any(re.search(rf"{_UAT_SEED_OPT_IN}:\s*['\"]?1['\"]?\s*$", line) for line in block), (
        f"compose/compose.dev.yml `api` service must set {_UAT_SEED_OPT_IN}: \"1\" — it is "
        "what lets backend/scripts/seed_uat_fixtures.py seed the dev stack while the "
        f"identical command refuses against production; got {block!r}."
    )


def test_db_env_file_template_is_tracked() -> None:
    """A documented env file nobody can copy is not a fix."""
    template = _REPO_ROOT / ".env.db.example"
    assert template.is_file(), (
        f"{template} is missing — compose points `db` at {_DB_ENV_FILE!r}, so the "
        "template a first-time self-hoster copies must exist and be tracked."
    )
    keys = {
        line.split("=", 1)[0].strip()
        for line in template.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert "POSTGRES_PASSWORD" in keys, f".env.db.example must define POSTGRES_PASSWORD; got {keys}"
