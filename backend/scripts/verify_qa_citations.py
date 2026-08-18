# ABOUTME: Standalone document verification for `.zj/QA.md`'s machine-proof citations (SC3).
# ABOUTME: Reads NO database — it extracts every citation from the `✅ Machine already proved`
# ABOUTME: blocks and greps the cited file for it, failing on the citation it cannot resolve.
"""
Standalone verification that every `.zj/QA.md` machine-proof citation still resolves (SC3).

WHY THIS EXISTS (`/zj:verify 5` gap G-3):
  Each check in `.zj/QA.md` §4 opens with a `✅ **Machine already proved:**` block that tells
  the tester **"do not re-check this"**. Those blocks cite vitest `it(...)` titles, pytest
  test names and `verify_*.py` `check()` labels / scenario letters — all of them **plain
  substrings of source files**. Renaming a test title or reformatting a label silently orphans
  the citation, and the checklist then waves a tester off a surface nothing asserts. Phase 5's
  PLAN flagged exactly this (`## Noticed` #9(a)) and no guard ever landed; the citations then
  moved into `.zj/QA.md`, which is a *standing* document, so the rot became permanent.

  It is deliberately named ``verify_*`` with no ``_api`` suffix, so CI's ``verify-scripts``
  job globs it for free. It touches no database.

HOW TO RUN (no database, no PYTHONPATH, no container — it is pure text):
  python backend/scripts/verify_qa_citations.py

CITATION GRAMMAR (four forms, exactly as `.zj/phases/05-human-uat/PREFLIGHT.md` documents
them, plus the bare-path form the checklist also uses). Every citation is a backtick span:
  `path::test_name`     a pytest test          → grep the file for ``test_name``
  `path "title"`        a vitest title, or a `check()` label in a verify script
                                               → grep the file for ``title``
  `path (S)`            a verify_* scenario     → grep the file for ``(S)``
  `path`                a whole file            → assert the file exists
A span that carries no path — ```::name```, ```"title"```, ```(S)``` — continues the most
recently named path **within the same block**, which is how the checklist writes runs of
citations against one file.

WHAT IS DELIBERATELY NOT COVERED (stated so this pin is not read as wider than it is):
  * Only the `✅ Machine already proved` blocks of `.zj/QA.md` are scanned. Nothing else in
    the file cites a test *title* — the only other code spans naming a source file are bare
    paths and the `backend/scripts/verify_*.py` glob (checked by hand at authoring time).
  * `.zj/phases/05-human-uat/PREFLIGHT.md` carries the same citations in table form but is a
    **frozen phase artifact**; `.zj/QA.md` is the document a tester reads, so that is what is
    pinned here. Extending the extractor to PREFLIGHT.md is a backlog-sized follow-up.
  * A citation resolves as a **substring**. Some titles in the checklist are deliberately
    truncated (`"shows "`, `"labels a direct parent "`) and match near-vacuously; they still
    catch a *deleted* file or a *renamed* prefix, which is the failure mode that matters.
  * `verify_gl.py` labels its scenarios `(a)`–`(h)` in lower case while `.zj/QA.md` cites
    `(A)`/`(B)`. Those two resolve only incidentally (via ``derive_account_balance(A)``), so
    the run prints a **WEAK** advisory for any scenario citation whose file has no scenario
    marker at the start of a line. Advisory, not a failure — tightening it means re-lettering
    the letterless scripts, which is its own change.

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. Every `#### C-…` check in §4 owns exactly one machine-proof block. A block the extractor
     cannot see is a check nothing re-greps, so a reformat can never make this script
     vacuously green.
  2. Every extracted citation names a path that resolves to a real file.
  3. Every extracted citation's needle is present in that file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping — identical to the DB-driven verify_* scripts
# ---------------------------------------------------------------------------

_FAILURES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


# ---------------------------------------------------------------------------
# Locations + patterns
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
QA_PATH = REPO_ROOT / ".zj" / "QA.md"

# Loose on purpose: matching the *phrase*, not its punctuation, so re-bolding or dropping the
# colon cannot quietly hide a block from the extractor.
BLOCK_MARKER = "Machine already proved"
CHECK_HEADING = re.compile(r"^#### (C-[\w-]+)")
# A backtick span. DOTALL because the checklist wraps long citations across lines.
SPAN = re.compile(r"`([^`]+)`", re.S)
# A cited source path: any .py / .ts / .tsx file. No spaces, so a shell command that happens
# to name a .py file (there are none in these blocks, but be defensive) never matches.
PATH = r"[\w./-]+\.(?:py|tsx|ts)"
# Ordered: the path-bearing forms must be tried before their bare continuations.
CITATION_FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pytest test", re.compile(rf"^({PATH})::(\w+)$")),
    ("pytest test", re.compile(r"^()::(\w+)$")),
    ("title", re.compile(rf'^({PATH})\s+"(.+)"$')),
    ("title", re.compile(r'^()"(.+)"$')),
    ("scenario", re.compile(rf"^({PATH})\s+\(([A-Z]\d?)\)$")),
    ("scenario", re.compile(r"^()\(([A-Z]\d?)\)$")),
    ("file", re.compile(rf"^({PATH})()$")),
)
# `  (G) BIN EXISTENCE …` or `        # (G) BIN EXISTENCE …` — a real scenario marker.
SCENARIO_MARKER = r"^\s*(?:#\s*)?\({letter}\)"


class Citation:
    """One citation: where it was written, the file it names, and the needle to grep for."""

    def __init__(self, line: int, form: str, path: str, needle: str, raw: str) -> None:
        self.line = line
        self.form = form
        self.path = path
        self.needle = needle
        self.raw = raw

    def __str__(self) -> str:
        return f"`{self.raw}` (.zj/QA.md:{self.line}, {self.form} in {self.path})"


def resolve(path: str) -> Path | None:
    """Map a citation's path onto the repo. Mirrors how the checklist writes them."""
    if path.startswith(("backend/", "frontend/")):
        return REPO_ROOT / path
    if path.startswith("src/"):  # vitest titles are cited frontend-relative
        return REPO_ROOT / "frontend" / path
    if path.startswith("tests/"):  # pytest names are cited backend-relative
        return REPO_ROOT / "backend" / path
    if path.startswith(("verify_", "seed_")):  # bare script filenames
        return REPO_ROOT / "backend" / "scripts" / path
    return None


def machine_proof_blocks(lines: list[str], offset: int) -> list[tuple[int, str]]:
    """Return (1-based file line, joined text) for every `✅ Machine already proved` block."""
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        if BLOCK_MARKER in lines[i] and lines[i].lstrip().startswith("-"):
            body = [lines[i]]
            j = i + 1
            # Continuation lines are indented under the bullet; a blank line ends the block.
            while j < len(lines) and lines[j].startswith("  ") and lines[j].strip():
                body.append(lines[j])
                j += 1
            blocks.append((offset + i + 1, "\n".join(body)))
            i = j
        else:
            i += 1
    return blocks


def the_checks(lines: list[str]) -> tuple[int, list[str]]:
    """Return (0-based offset, lines) of `## 4. The checks` — the only section that cites."""
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "## 4. The checks"), None)
    if start is None:
        print("FAIL: `.zj/QA.md` has no `## 4. The checks` section — the parser cannot proceed.")
        sys.exit(1)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start + 1, lines[start + 1 : end]


def blocks_per_check(section: list[str]) -> dict[str, int]:
    """Count the machine-proof blocks each `#### C-…` check in §4 owns (must be exactly 1)."""
    owned: dict[str, int] = {}
    current: str | None = None
    for line in section:
        heading = CHECK_HEADING.match(line)
        if heading:
            current = heading.group(1)
            owned.setdefault(current, 0)
        elif current and BLOCK_MARKER in line and line.lstrip().startswith("-"):
            owned[current] += 1
    return owned


def extract(blocks: list[tuple[int, str]]) -> tuple[list[Citation], list[str]]:
    """Pull every citation out of the blocks. Returns (citations, skipped spans)."""
    citations: list[Citation] = []
    skipped: list[str] = []
    for start, body in blocks:
        current_path: str | None = None
        for match in SPAN.finditer(body):
            span = " ".join(match.group(1).split())  # collapse the line wrapping
            for form, pattern in CITATION_FORMS:
                parsed = pattern.match(span)
                if parsed is None:
                    continue
                path, needle = parsed.group(1), parsed.group(2)
                if path:
                    current_path = path
                if current_path is None:
                    skipped.append(f"`{span}` (.zj/QA.md:{start}) — no path in scope")
                    break
                if form == "scenario":
                    needle = f"({needle})"
                citations.append(Citation(start, form, current_path, needle, span))
                break
            else:
                skipped.append(span)
    return citations, skipped


def run() -> None:
    lines = QA_PATH.read_text(encoding="utf-8").split("\n")

    # -----------------------------------------------------------------------
    # 1. The extractor still sees the blocks it is supposed to scan
    # -----------------------------------------------------------------------
    offset, section = the_checks(lines)
    owned = blocks_per_check(section)
    orphans = sorted(c for c, n in owned.items() if n != 1)
    check(
        "every §4 check owns exactly one `✅ Machine already proved` block",
        bool(owned) and not orphans,
        f"{len(owned)} check(s) in §4; wrong block count for: "
        + ", ".join(f"{c} ({owned[c]})" for c in orphans)
        + " — a check whose block the extractor cannot see is a check nothing re-greps",
    )

    blocks = machine_proof_blocks(section, offset)

    citations, skipped = extract(blocks)
    check(
        "the extractor found citations to check",
        bool(citations),
        "zero citations extracted from `.zj/QA.md` — the citation grammar changed",
    )

    # -----------------------------------------------------------------------
    # 2 + 3. Every citation resolves to a file, and its needle is in that file
    # -----------------------------------------------------------------------
    cache: dict[Path, str] = {}
    unresolved: list[str] = []
    missing: list[str] = []
    weak: list[str] = []

    for citation in citations:
        target = resolve(citation.path)
        if target is None:
            unresolved.append(f"{citation} — no repo location is known for that path prefix")
            continue
        if not target.exists():
            unresolved.append(f"{citation} — no such file: {target.relative_to(REPO_ROOT)}")
            continue
        if target not in cache:
            cache[target] = target.read_text(encoding="utf-8")
        source = cache[target]
        if citation.needle not in source:
            missing.append(
                f"{citation} — {citation.form} {citation.needle!r} is NOT in "
                f"{target.relative_to(REPO_ROOT)}"
            )
            continue
        if citation.form == "scenario":
            letter = re.escape(citation.needle[1:-1])
            if not re.search(SCENARIO_MARKER.format(letter=letter), source, re.M):
                weak.append(
                    f"{citation} — matched only mid-line; "
                    f"{target.name} declares no `{citation.needle}` scenario marker"
                )

    check(
        "every citation names a file this repo can locate",
        not unresolved,
        "\n    " + "\n    ".join(unresolved),
    )
    check(
        "every citation resolves inside the file it names",
        not missing,
        "\n    " + "\n    ".join(missing),
    )

    forms = {form for form, _ in CITATION_FORMS}
    tally = ", ".join(f"{sum(1 for c in citations if c.form == f)} {f}" for f in sorted(forms))
    print(f"\n{len(citations)} citation(s) across {len(blocks)} block(s): {tally}.")
    print(f"{len(skipped)} non-citation code span(s) skipped (fixture literals, symbol names).")
    if weak:
        print(f"\nWEAK (advisory, not a failure) — {len(weak)} scenario citation(s):")
        for note in weak:
            print(f"  {note}")


def main() -> int:
    run()
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
