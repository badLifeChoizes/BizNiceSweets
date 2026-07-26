# ABOUTME: Pins UAT defect U0 (v4.0 Phase 5, D-P5-10) — the fresh-volume deploy blocker.
# ABOUTME: Asserts the compose `db` service resolves POSTGRES_PASSWORD from a DEDICATED
# ABOUTME: env_file rather than a bare ${POSTGRES_PASSWORD} interpolation (which silently
# ABOUTME: expands to empty and breaks only a FRESH volume), and that the file it reads is
# ABOUTME: NOT the app `.env` — so the secret-spread regression is caught too.
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
