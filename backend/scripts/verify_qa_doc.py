# ABOUTME: Standalone document verification for `.zj/QA.md`'s coverage map (v4.0 Phase 5, SC1).
# ABOUTME: Reads NO database — it parses `.zj/SRD.md` and `.zj/QA.md` and re-proves the
# ABOUTME: §3/§4/§5 arithmetic, naming the requirement that drifted and in which direction.
"""
Standalone verification that `.zj/QA.md`'s coverage map still tallies (SC1).

WHY THIS EXISTS (`/zj:verify 5` gap G-1):
  `.zj/QA.md` is the project's **standing** QA checklist, not a phase artifact. Its §3
  coverage map claims "31 of 47 requirements have at least one human check" — true at
  Phase-5 close only because the verifier machine-checked it once, by hand. Nothing
  re-checked it afterwards, so the next requirement added to `.zj/SRD.md` would silently
  make the standing QA document lie, and staleness there is permanent rather than
  transient. This script is Task 32's own "Verify" line made permanent.

  It is deliberately named ``verify_*`` and takes no ``_api`` suffix, so CI's
  ``verify-scripts`` job globs it for free (`.github/workflows/ci.yml`). It touches no
  database: every assertion is a statement about two Markdown files.

HOW TO RUN (no database, no PYTHONPATH, no container — it is pure text):
  python backend/scripts/verify_qa_doc.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. REQUIREMENT SET, BOTH DIRECTIONS. Every ``^## <REQ-ID>:`` heading in `.zj/SRD.md`
     appears exactly once as a §3 row, and §3 introduces no requirement the SRD does not
     have. Both directions, because a map that quietly invents a requirement is as wrong
     as one that quietly drops it.
  2. COVERED COUNT == §4 HEADINGS. The §3 rows that name at least one check are exactly
     the requirements that own a ``### <REQ> — …`` section in §4 — again both ways, so a
     check section for an uncovered requirement is caught too.
  3. HEADLINE PROSE. §3's "**N of M requirements have at least one human check.**" matches
     the actual covered count and the actual row count.
  4. §5 PARTITIONS THE REMAINDER. The §5 buckets ("Real gaps", "Not built yet",
     "Machine-only by nature", "Self-referential") are pairwise disjoint, their union is
     exactly the set of §3 rows with no check, and buckets + covered == the SRD total.

HOW §5 IS PARSED (the one non-obvious rule, stated so a failure is legible):
  A bucket's members are the **bolded requirement IDs** in its body. Two exclusions,
  both needed and both deliberate:
    * blockquote lines (``>``) are prose commentary — the NFR-1 re-triage note names
      NFR-1 while explaining it, and the re-key note names none — so they never count;
    * a bucket whose body opens with ``_None._`` is empty by declaration. "Real gaps"
      does exactly that and then explains, in prose, which two requirements *used* to be
      gaps; those two are covered now and must not be counted as members.
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
SRD_PATH = REPO_ROOT / ".zj" / "SRD.md"
QA_PATH = REPO_ROOT / ".zj" / "QA.md"

# `## CORE-01: Containerized single-command deploy  [traces: PRD-1]  **Status: …**`
# Prose section headings ("## Foundation (Core)", "## Traceability") never match.
SRD_REQ_HEADING = re.compile(r"^## ([A-Z]+-\d+):", re.MULTILINE)
# `| **CORE-01** — Containerized single-command deploy | implemented | `C-CORE-08` |`
# Groups: 1 = requirement ID, 2 = title, 3 = status, 4 = the Checks cell ("—" when none).
QA_MAP_ROW = re.compile(r"^\|\s*\*\*([A-Z]+-\d+)\*\*\s*—\s*(.*?)\|(.*?)\|(.*?)\|\s*$")
# `### CORE-01 — Containerized single-command deploy` (suite banners like
# "### 6.2 PLUM — product lifecycle" do not match: they start with a digit).
QA_CHECK_SECTION = re.compile(r"^### ([A-Z]+-\d+)\s*—")
# `**31 of 47 requirements have at least one human check.**`
QA_HEADLINE = re.compile(r"\*\*(\d+) of (\d+) requirements have at least one human check\.\*\*")
BOLD_REQ = re.compile(r"\*\*([A-Z]+-\d+)\*\*")

# The §5 buckets, in document order. Every `### ` heading in §5 must be one of these —
# a renamed or added bucket is itself a drift worth failing on.
BUCKET_HEADINGS = (
    "Real gaps — human-checkable, currently unchecked",
    "Not built yet — correctly uncovered",
    "Machine-only by nature — correctly uncovered",
    "Self-referential",
)


def section(text: str, heading: str) -> list[str]:
    """Return the lines of the `## <heading>` section, up to the next `## ` heading."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == f"## {heading}"), None)
    if start is None:
        print(f"FAIL: `.zj/QA.md` has no `## {heading}` section — the parser cannot proceed.")
        sys.exit(1)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return lines[start + 1 : end]


def describe(ids: set[str]) -> str:
    """Render a requirement-ID set for a failure message — sorted, never a bare count."""
    return ", ".join(sorted(ids)) if ids else "(none)"


def parse_buckets(lines: list[str]) -> dict[str, set[str]]:
    """Split §5 into `### ` buckets and collect each one's bolded requirement IDs."""
    buckets: dict[str, set[str]] = {}
    current: str | None = None
    declared_empty: set[str] = set()
    for line in lines:
        if line.startswith("### "):
            current = line[4:].strip()
            buckets[current] = set()
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith(">"):  # blockquote prose — commentary, never membership
            continue
        if stripped.startswith("_None._"):
            declared_empty.add(current)
        if current in declared_empty:
            continue
        buckets[current].update(BOLD_REQ.findall(line))
    return buckets


def run() -> None:
    srd_text = SRD_PATH.read_text(encoding="utf-8")
    qa_text = QA_PATH.read_text(encoding="utf-8")

    # -----------------------------------------------------------------------
    # 1. Requirement set — both directions
    # -----------------------------------------------------------------------
    srd_ids: list[str] = SRD_REQ_HEADING.findall(srd_text)
    srd_set = set(srd_ids)
    check(
        "SRD requirement headings are unique",
        len(srd_ids) == len(srd_set),
        f"duplicated in `.zj/SRD.md`: {describe({i for i in srd_set if srd_ids.count(i) > 1})}",
    )

    map_lines = section(qa_text, "3. Coverage map")
    map_rows = [QA_MAP_ROW.match(ln) for ln in map_lines]
    map_ids = [m.group(1) for m in map_rows if m]
    map_set = set(map_ids)
    check(
        "§3 coverage-map rows are unique",
        len(map_ids) == len(map_set),
        f"listed twice in `.zj/QA.md` §3: {describe({i for i in map_set if map_ids.count(i) > 1})}",
    )

    missing_from_map = srd_set - map_set
    check(
        "every `.zj/SRD.md` requirement has a §3 coverage-map row",
        not missing_from_map,
        f"in `.zj/SRD.md` but MISSING from `.zj/QA.md` §3: {describe(missing_from_map)} — "
        f"add a row (or a §5 bucket entry) for each",
    )
    unknown_in_map = map_set - srd_set
    check(
        "§3 introduces no requirement `.zj/SRD.md` does not have",
        not unknown_in_map,
        f"in `.zj/QA.md` §3 but NOT in `.zj/SRD.md`: {describe(unknown_in_map)} — "
        f"either the SRD heading was renamed/removed, or §3 invented a requirement",
    )

    # -----------------------------------------------------------------------
    # 2. Covered set == §4 check sections — both directions
    # -----------------------------------------------------------------------
    covered = {m.group(1) for m in map_rows if m and m.group(4).strip() not in ("", "—")}
    uncovered = map_set - covered

    check_lines = section(qa_text, "4. The checks")
    section_matches = [QA_CHECK_SECTION.match(ln) for ln in check_lines]
    section_set = {m.group(1) for m in section_matches if m}

    covered_without_section = covered - section_set
    check(
        "every §3 requirement that names a check owns a §4 section",
        not covered_without_section,
        f"§3 names checks for {describe(covered_without_section)} but `.zj/QA.md` §4 has no "
        f"`### <REQ> — …` section for them",
    )
    section_without_coverage = section_set - covered
    check(
        "every §4 check section is a requirement §3 marks as covered",
        not section_without_coverage,
        f"`.zj/QA.md` §4 has a section for {describe(section_without_coverage)} but §3 shows "
        f"them with no check (or has no row at all)",
    )
    check(
        "§3 covered count equals the distinct §4 check-section count",
        len(covered) == len(section_set),
        f"§3 covered = {len(covered)}, distinct §4 sections = {len(section_set)}",
    )

    # -----------------------------------------------------------------------
    # 3. Headline prose
    # -----------------------------------------------------------------------
    headline = QA_HEADLINE.search("\n".join(map_lines))
    if headline is None:
        check(
            "§3 carries its `**N of M requirements have at least one human check.**` headline",
            False,
            "the headline sentence is missing or was re-worded — the arithmetic it states "
            "can no longer be checked",
        )
    else:
        stated_covered, stated_total = int(headline.group(1)), int(headline.group(2))
        check(
            "§3 headline's covered figure matches the rows that name a check",
            stated_covered == len(covered),
            f"§3 prose says {stated_covered} covered; the rows say {len(covered)}",
        )
        check(
            "§3 headline's total matches the actual row count",
            stated_total == len(map_ids),
            f"§3 prose says {stated_total} requirements; the table has {len(map_ids)} rows",
        )
        check(
            "§3 headline's total matches `.zj/SRD.md`",
            stated_total == len(srd_set),
            f"§3 prose says {stated_total} requirements; `.zj/SRD.md` has {len(srd_set)}",
        )

    # -----------------------------------------------------------------------
    # 4. §5 partitions the uncovered remainder
    # -----------------------------------------------------------------------
    buckets = parse_buckets(section(qa_text, "5. Requirements with no human check"))
    unexpected = set(buckets) - set(BUCKET_HEADINGS)
    check(
        "§5 carries exactly its four documented buckets",
        set(buckets) == set(BUCKET_HEADINGS),
        f"unexpected bucket(s): {describe(unexpected) if unexpected else '(none)'}; "
        f"missing: {describe(set(BUCKET_HEADINGS) - set(buckets))}",
    )

    seen: dict[str, str] = {}
    overlaps: list[str] = []
    for name in BUCKET_HEADINGS:
        for req in sorted(buckets.get(name, set())):
            if req in seen:
                overlaps.append(f"{req} in both '{seen[req]}' and '{name}'")
            seen[req] = name
    check("§5's buckets are pairwise disjoint", not overlaps, "; ".join(overlaps))

    bucketed = set(seen)
    not_bucketed = uncovered - bucketed
    check(
        "every §3 row with no check is itemised in a §5 bucket",
        not not_bucketed,
        f"§3 shows no check for {describe(not_bucketed)}, and §5 never says why — "
        f"file each under 'Not built yet', 'Machine-only by nature' or 'Real gaps'",
    )
    bucketed_but_covered = bucketed - uncovered
    check(
        "no §5 bucket claims a requirement §3 shows as covered",
        not bucketed_but_covered,
        f"§5 lists {describe(bucketed_but_covered)} as having no human check, but §3 names "
        f"one — the bucket is stale",
    )

    check(
        "§5's buckets plus §3's covered count sum to the `.zj/SRD.md` total",
        len(bucketed) + len(covered) == len(srd_set),
        f"{len(bucketed)} bucketed + {len(covered)} covered = {len(bucketed) + len(covered)}, "
        f"but `.zj/SRD.md` has {len(srd_set)} requirements",
    )

    print(
        f"\n{len(srd_set)} requirements in `.zj/SRD.md`; {len(covered)} covered by "
        f"{len(section_set)} §4 section(s); {len(bucketed)} itemised across "
        f"{len(BUCKET_HEADINGS)} §5 bucket(s)."
    )


def main() -> int:
    run()
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
