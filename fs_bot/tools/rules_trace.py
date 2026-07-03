"""Rules traceability — every numbered rule section vs. the codebase.

Parses the section headers (1.2.3 / A4.5.6) out of the Reference Document
chapters and counts citations of each section across fs_bot's source (the
project cites rules pervasively: "§3.2.1", "A8.7.4", "3.2.4-.5"). Sections
with zero citations are the prime suspects for rules that were never
transcribed into the engine.

A citation census is evidence, not proof: a cited rule can still be wrong,
and an uncited rule can be implemented. The tool's job is to make the gap
list small enough to triage by hand (see QUESTIONS.md "Rules traceability
pass" for the classification of every flagged section).

    python -m fs_bot.tools.rules_trace
    python -m fs_bot.tools.rules_trace --all      # show cited ones too
"""
from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict

DOC_DIR = os.path.join(os.path.dirname(__file__), "..", "..",
                       "Reference Documents")

CHAPTERS = [("Chapter %d" % i, "") for i in range(1, 9)] + \
           [(os.path.join("Ariovistus", "Chapter A%d" % i), "A")
            for i in range(1, 9)]

# A section header at line start: "3.2.4 Retreat." / "A8.7.4 Rally?"
_SECTION_RE = re.compile(r"^(A?\d\.\d(?:\.\d+)?)\s+(\S.*)")

# Source citation: the bare section number, optionally §-prefixed, not
# followed by another digit (so "3.2.4" doesn't match inside "3.2.45").
def _cite_re(sec):
    return re.compile(re.escape(sec) + r"(?!\d)")


def parse_sections():
    """{section: title} from every chapter document."""
    sections = {}
    for rel, prefix in CHAPTERS:
        path = os.path.join(DOC_DIR, rel)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8", errors="replace"):
            m = _SECTION_RE.match(line.strip())
            if m:
                sec, title = m.group(1), m.group(2)
                if prefix == "A" and not sec.startswith("A"):
                    continue        # base-numbered refs inside A-chapters
                if prefix == "" and sec.startswith("A"):
                    continue
                # Keep the FIRST occurrence (headers repeat in cross-refs).
                sections.setdefault(sec, title.rstrip(".").strip()[:60])
    return sections


def _iter_source_files():
    for root, _dirs, files in os.walk(
            os.path.join(os.path.dirname(__file__), "..")):
        if "__pycache__" in root:
            continue
        for f in files:
            # This tool's own allowlist must not count as citations.
            if f.endswith(".py") and f != "rules_trace.py":
                yield os.path.join(root, f)


def citation_census():
    """{section: [files citing it]} across fs_bot source."""
    sections = parse_sections()
    hits = defaultdict(set)
    blobs = {}
    for path in _iter_source_files():
        try:
            blobs[path] = open(path, encoding="utf-8",
                               errors="replace").read()
        except OSError:
            continue
    for sec in sections:
        rx = _cite_re(sec)
        for path, blob in blobs.items():
            if rx.search(blob):
                hits[sec].add(os.path.relpath(
                    path, os.path.dirname(__file__)))
    return sections, hits


# Sections with no software counterpart — physical components, meta-text
# about reading the printed materials, or table-seating logistics. Each
# carries its reason; anything NOT here and uncited is a defect in either
# the engine or its documentation (test_rules_trace enforces zero).
NOT_APPLICABLE = {
    "3.1.1": "physical pawns marking selected Regions (plans carry lists)",
    "8.1.3": "how to read the printed flowchart sheets",
    "A1.0": "chapter introduction",
    "A1.4.1": "physical Available Forces display layout",
    "A1.5.1": "three-player seating (no player runs two Factions here; "
              "see commands/transfer.py on the 4-Resource cap)",
    "A2.2": "physical Eligibility cylinder colour swap",
}


def unaccounted():
    """Sections neither cited in source nor allow-listed as N/A."""
    sections, hits = citation_census()
    return sorted(s for s in sections
                  if not hits[s] and s not in NOT_APPLICABLE)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="list cited sections too")
    args = ap.parse_args(argv)

    sections, hits = citation_census()
    uncited = sorted((s for s in sections if not hits[s]),
                     key=lambda x: (x.startswith("A"), x))
    missing = [s for s in uncited if s not in NOT_APPLICABLE]
    print(f"sections={len(sections)}  cited={len(sections) - len(uncited)}"
          f"  n/a={len(uncited) - len(missing)}  UNACCOUNTED={len(missing)}")
    for sec in missing:
        print(f"  {sec:8s} {sections[sec]}")
    if args.all:
        print("\ncited:")
        for sec in sorted(sections, key=lambda x: (x.startswith('A'), x)):
            if hits[sec]:
                print(f"  {sec:8s} [{len(hits[sec]):2d} files] "
                      f"{sections[sec]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
