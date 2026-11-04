# Mons Cevenna March choices — 3 November 2026

Date convention: America/Chicago. Parent: `c3883b2c242528d77b6b25e595fc43c47e7f1229`.
This is a partial repair of BE-01, not another closed original finding.

## Printed contract and resulting behavior

Card Reference 9 and its Tips require a March from one Region into an
adjacent Region, both within Provincia, Sequani and Arverni, followed by
a free Command and optional Special Ability in/from the destination, in
any order. The selected origin undergoes ordinary March visibility changes.
Sections 3.2.2/3.3.2, 5.1.3 and 5.4 govern formation, partial execution
and free actions. Supplied references and canonical constants are unchanged.

The human executor now receives `mons_cevenna_march`, selecting the origin,
one adjacent destination and an exact mobile force. It supports every player
faction in its proper scenario. Piece quantities and Leader participation
are validated; extra origins, routes, static pieces, unavailable counters
and independent decline cannot bypass the grant. An impossible first March
still allows a named, single-region follow-on through partial execution.

The first March reserves physical cohorts through the existing exact Event
March executor. Both moving and stationary pieces at the selected origin
undergo the ordinary visibility step; Scouted pieces change once, rather
than disappearing or becoming Hidden immediately. Cooperation retains actual
ownership and requires fresh consent for each Command; a refused first loan
reoffers planning. The following Command/SA uses the resulting board and is
restricted to the destination, while March/Scout may move out of it.

The native default retains its existing first-move selection priorities.
Its unavailable/failed March no longer broadens the follow-on to all nearby
Regions. Initial legacy `march_from`/`march_to` parameters must form a complete
adjacent pair inside the printed theatre; malformed routes are rejected
before the handler installs its grant. Human actual force selections belong
to the live request, not the old initial parameter form.

Terminal prompts support board inspection and validate selections without
changing the live game or RNG. Durable missing or rejected replies stay
pending; a later invalid follow-on rolls back the first March. Save/load at
the follow-on replays the accepted first decision and completes correctly.
The save schema is unchanged, but old transcripts may need the new decision;
exact replay across code revisions is not promised.

## Validation

Python 3.12.14. Frozen Python source: 467 files, SHA-256
`d6da1ebb1d1c05706eabfc76b36c96c9b8e1861a4e6f05632697dca719af9536`.

- **7,517 tests pass** in the final full suite, with no failures, errors or
  skips. The parent checkpoint had 7,489 tests; its full suite was not rerun.
- 28 added regression cases cover player factions, quantities, geography,
  origin visibility, physical cooperation, refusal, both Event texts,
  Command/SA ordering, live-state rollback and durable save/resume.
- 19 behavioral cases run against the parent all fail on existing behavior;
  they do not rely on importing the new module. The other nine cases were
  excluded from this parent proof.
- The final targeted Command/CLI/schema suite passes 54 tests. An earlier
  integration run passed 188 tests before the last three regressions were
  added; it is supporting evidence, not the final full-suite result.
- Ten accepted bot games (seeds 1–2 in all five scenarios, legacy edition)
  match fresh same-runtime parent gameplay records and final-state hashes.
  Runtime/source metadata is excluded from that comparison. This is not a
  complete turn-by-turn trajectory comparison.
- Ten mixed-player cases, each with replay, pass under both hash seeds 0
  and 987: 40 executions, zero hard findings and zero partial plans. Complete
  JSON results match across hash seeds. Each ten-case pass records 282 human
  turns and 83 attempted Events, of which 80 succeeded; rejected generated
  inputs are not silently counted as successful Events.
- The existing balance baseline and tolerances are unchanged. These small
  fixed-seed checks are bounded evidence, not exhaustive rules certification.

## Remaining scope

**21/50 original findings remain closed (42%); 29 remain open.** BE-01 still
covers numeric 4/17/58/65. Two unadopted source questions, twelve provisional
rulings and 34 unverified inventory rows remain separate. No official rule
clarification or new provisional project ruling is introduced here.

Machine-readable [results](mons-cevenna-2026-11-03-results.json) and
[evidence archive](mons-cevenna-2026-11-03-evidence.zip) retain full-suite logs,
parent witnesses, bot records, mixed runs and the exact implementation patch.
