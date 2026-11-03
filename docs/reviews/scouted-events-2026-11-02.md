# Scouted Event removals — 2 November 2026

Audit finding **EXP-12 is closed**. The unshaded effects of A25, A26,
A30 and A56 now remove Scouted Warbands along with Hidden and Revealed
Warbands. Previously, their removal loops omitted the Scouted state,
leaving those pieces on the map despite each card's mandatory text.

| Card | Required removal |
|---|---|
| A25 — Ariovistus's Wife | All non-Leader German pieces in Cisalpina |
| A26 — Divico | Arverni Ally at Helvetii and all Arverni Warbands in Sequani/Aedui Regions |
| A30 — Orgetorix | All Arverni in the selected eligible Region |
| A56 — Galba | All Belgae except their Leader in Atrebates |

Authority: the corresponding entries in the supplied
`Reference Documents/Ariovistus/A Card Reference`, together with Chapter 1
§1.4.3's definition of Scouted Warbands. No new ruling was needed. The
implementation adds `SCOUTED` to four existing loops and retains the
existing piece helpers, Leader exceptions, tribal cleanup and Resource
effects. Protected references, canonical constants and the balance baseline
are unchanged.

## Verification

- Baseline full suite: **6,260 passed**.
- **20 new regression cases** fail against the parent handlers and pass
  with the fix. Sixteen cover both expansion scenarios with Scouted-only
  and mixed-visibility forces; four cover durable pending rollback,
  save/resume and exact replay. An independent focused rerun also passed.
- Final full suite: **6,280 passed**. Piece conservation, Available changes,
  Tribe backing, cached Control, Leader preservation, other factions,
  outside Regions, Resource effects and unchanged RNG are asserted.
- Durable cases explicitly decline optional removal windows, retain the
  same pending request through save/load, and compare complete replayed
  board state and decision logs. They do not test invalid responses.

Commands, source identity and raw test output are in the
[evidence archive](scouted-events-2026-11-02-evidence.zip). This bounded
repair did not repeat the earlier local bot-outcome study. Remote CI results
are separate and can be inspected on the commit containing this report.

The tested working tree is based on commit
`c453f8eb86dfd42a93d75031cd4fb4b2552fc5a2`, with the two Python files in
this repair changed/added. Its **386 Python files** have SHA-256
`575e77365d90067f293e1887c363a7827324f8f2beb10542a275f8813a224dff`.
The digest concatenates sorted repository-relative paths, NUL, and raw
file bytes under `fs_bot/**/*.py`; it identifies the source committed with
this report without requiring a self-referential commit hash.

The initial durable fixture called a lower-level executor without its action
scope, so it did not open a pending choice. That test-only fixture was
corrected before reproducing all 20 failures. A subsequent review added
explicit structural-integrity checks and left game-run Arverni Resources
at their default zero; the final full suite uses those reviewed tests.
Earlier test attempts are retained separately in the archive.

## Remaining scope and compatibility

**44 of the original 50 grouped audit findings remain open** in the
[progress register](../human-choice-progress.json). A30's separate unchecked
geographic restriction remains part of EXP-09. This fix neither resolves
that finding nor certifies every effect on these cards.

Save and response formats are unchanged. A future resolution of these
Events uses corrected removals; already completed turns are not rewritten.
Replaying an older game that depended on the omitted removal can therefore
produce a different board or fail strict replay verification. New transcripts
with the corrected rules are covered by the replay regressions above.
