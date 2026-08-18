# ABOUTME: Pins UAT defect U2 (v4.0 Phase 5, Task 34) — the image could not be built at all.
# ABOUTME: Asserts the Containerfile's frontend-builder stage copies `frontend/.npmrc` into the
# ABOUTME: build context BEFORE `npm ci` runs, so npm honours `legacy-peer-deps=true` (D-P1-1).
# ABOUTME: Also asserts the setting is not duplicated as an `npm ci --legacy-peer-deps` flag, so
# ABOUTME: the npmrc stays the single source of truth that CI and the image share.
"""
Containerfile invariants for defect U2 (v4.0 Phase 5, Task 34).

WHAT U2 WAS
  The frontend-builder stage did::

      COPY frontend/package*.json ./
      RUN npm ci

  ``package*.json`` is a glob over regular files and does **not** match the dotfile
  ``frontend/.npmrc``. That file carries ``legacy-peer-deps=true`` (owner decision
  D-P1-1), which exists precisely because ``eslint-plugin-react-hooks@5``'s peer
  range predates the pinned ESLint. Without it, ``npm ci`` inside the builder dies::

      npm error Conflicting peer dependency: eslint@9.39.5
      Error: building at STEP "RUN npm ci": while running runtime: exit status 1

  So ``podman-compose build api`` — the documented way to produce the shipped
  artifact — failed outright. Nobody could build the image.

WHY IT STAYED HIDDEN FOR FIVE PHASES
  The devDependencies that collide were added by v4.0 Phase 1 (NFR-6, the ESLint
  flat-config work). The image had not been rebuilt since before that, so the stale
  image kept working and masked a broken build. Task 34 was the first rebuild, and
  it failed on the first try. This is the same shape as U0: a fault invisible until
  somebody does the thing from scratch.

  It is also why the p1 BACKLOG "rebuild frontend/dist + the API container image"
  item mattered more than it looked — the staleness was not just an old bundle.

A TRAP WORTH KNOWING
  ``podman-compose build`` printed ``exit code: 1`` and still **returned 0**. A
  ``build && next-step`` chain therefore proceeds happily over a failed build. Check
  the log for ``Error: building at STEP``, not just the exit status.

WHY THIS IS A CONFIG TEST AND NOT A BUILD TEST
  The honest proof is a real ``podman build``, which is far too heavy and too
  privileged for the existing test jobs. So this pins the CONFIG INVARIANT that made
  the build fail — cheap, runs in `backend-tests`, and RED on revert, which is what
  D-P5-4 requires of a blocker fix. Same reasoning as `test_compose_config.py`.

  Comments are stripped FIRST, for the same reason they are there: a comment
  mentioning `.npmrc` must not be able to satisfy a substring search.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTAINERFILE = _REPO_ROOT / "Containerfile"
_NPMRC = _REPO_ROOT / "frontend" / ".npmrc"


def _strip_comment(line: str) -> str:
    """Drop a whole-line `#` comment. Containerfile has no inline-comment syntax."""
    return "" if line.lstrip().startswith("#") else line


def _instructions(text: str) -> list[str]:
    """Comment-free, continuation-joined instruction lines, in order."""
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    return [ln.strip() for ln in (_strip_comment(x) for x in joined.splitlines()) if ln.strip()]


@pytest.fixture(scope="module")
def instructions() -> list[str]:
    assert _CONTAINERFILE.is_file(), f"Containerfile missing at {_CONTAINERFILE}"
    return _instructions(_CONTAINERFILE.read_text(encoding="utf-8"))


def test_npmrc_is_copied_before_npm_ci(instructions: list[str]) -> None:
    """The whole of U2: `.npmrc` must reach the builder before `npm ci` runs."""
    copies_npmrc = [
        i for i, ln in enumerate(instructions)
        if ln.upper().startswith("COPY") and ".npmrc" in ln
    ]
    npm_ci = [
        i for i, ln in enumerate(instructions)
        if ln.upper().startswith("RUN") and re.search(r"\bnpm\s+ci\b", ln)
    ]

    assert npm_ci, "no `RUN npm ci` found — has the frontend-builder stage moved?"
    assert copies_npmrc, (
        "Containerfile never COPYs frontend/.npmrc (defect U2). `COPY frontend/package*.json` "
        "does NOT match a dotfile, so `npm ci` runs without legacy-peer-deps=true and fails on "
        "the eslint-plugin-react-hooks@5 peer range."
    )
    assert min(copies_npmrc) < min(npm_ci), (
        "frontend/.npmrc is copied, but only AFTER `npm ci` has already run — it must precede it."
    )


def test_npmrc_exists_and_sets_legacy_peer_deps() -> None:
    """The copy is only worth anything if the file still carries the setting."""
    assert _NPMRC.is_file(), (
        "frontend/.npmrc is missing — the Containerfile copies it and `npm ci` depends on it."
    )
    body = "\n".join(
        ln for ln in _NPMRC.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    )
    assert re.search(r"^\s*legacy-peer-deps\s*=\s*true\s*$", body, re.M), (
        "frontend/.npmrc no longer sets legacy-peer-deps=true; the image build will fail (U2)."
    )


def test_setting_is_not_duplicated_as_a_flag(instructions: list[str]) -> None:
    """Keep one source of truth: the npmrc, which CI honours too."""
    dupes = [
        ln for ln in instructions
        if re.search(r"\bnpm\s+(ci|install)\b", ln) and "--legacy-peer-deps" in ln
    ]
    assert not dupes, (
        "legacy-peer-deps is passed as a CLI flag as well as living in frontend/.npmrc: "
        f"{dupes}. Two homes drift; the npmrc is the one CI already honours."
    )
