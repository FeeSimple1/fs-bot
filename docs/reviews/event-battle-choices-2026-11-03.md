# Event Battle choices — 3 November 2026

Date convention: America/Chicago. This repair addresses BE-02 of the
[human-choice audit](human-choice-audit-2026-10-29.md). The parent is
`4e9a82ed35052198987dad4c91dd79ce9c5b4ab9`. Supplied rules and canonical
constants remain read-only. No new provisional rule interpretation is adopted.

## Restored choices

| Event | Human decision and printed restrictions |
|---|---|
| 11 Numidians, original | Romans select the defender in the placement Region. All normal Roman attacking Forces participate; Auxilia inflict double Losses before rounding. |
| 11 Numidians, revised | Romans select the defender in the placement Region. Only Auxilia participate, including eligible cooperating Aedui Warbands treated as Auxilia. |
| 25 Aquitani, unshaded | The executor selects a defender in Pictones or Arverni. An already selected Event Region remains binding; otherwise either is offered. Three extra Losses and the first Allied Tribe Loss apply, even without friendly Forces. |
| 36 Morasses, unshaded | The executor selects one Region and a Gallic defender. No Retreat, Counterattack or Citadel effect on Losses; attackers remain Hidden. |
| 45 Litaviccus, shaded | The executor selects one Region against Romans, using Aedui pieces as its own and Ambushing if able. Aedui playing the Event count their pieces once. |
| 70 Camulogenus, unshaded | Romans select the defender at the resulting March destination. Whole-benefit acceptance and March planning remain separately open under BE-01. |

The compact `fixed_event_battle` response selects only a Region and defender.
Card modifiers, participating-piece restrictions and required Ambush belong
to the engine. Responses cannot add an ungranted Special Activity or change
the printed effect. Human legality is not narrowed to the non-player's target
priorities. Diviciacus agreement follows the selected Battle and still belongs
to the appropriate owners.

Section 5.1.3 requires executable Event text to be carried out. These follow-on
Battles have no independent decline. Card 70's permission covers the compound
March-and-Battle benefit; after its current preceding stage proceeds, Battle
is required if possible. An explicit legal default remains available; missing
durable input never becomes an automatic default.

Terminal menus preserve current/upcoming card information, changes and board
inspection. Invalid or absent durable responses retain the pending decision,
roll back partial execution and preserve RNG. Save/resume and replay retain
the choices and intermediate placement or March context.

## Related mechanics and scope

The revised Numidians flag previously changed damage calculation but allowed
Counterattack to remove excluded Legions and Leaders. Its scoped participating
force now includes only Auxilia for damage, casualties, relevant effects and
reaction menus. Other Roman pieces remain physically on the board, retain
their Control/inventory contribution, and remain visible in inspection.
Original Numidians and ordinary Battles retain full-force participation.

Litaviccus previously added Aedui as an allied force even when Aedui were the
attacker, counting those same pieces twice. That duplication is removed.

Non-player defenders previously forecast ordinary Losses when deciding
whether to Retreat, ignoring Numidians' doubled Auxilia and Aquitani's extra
Losses. Forecasts now retain those modifiers, including the first Ally Loss.
Aquitani's three extra Losses are added after the ordinary force calculation
and halving, matching actual resolution. Ordinary Battle and Card 2 defaults
are unchanged.

The save schema is unchanged. Resuming an older save uses the corrected
mechanics and can introduce a newly required Battle decision. Exact replay
of old response logs across this behavior change is not promised; current
revision save/resume and replay are tested.

The mixed-player fuzzer now selects from the offered Event Battle pairs rather
than silently deferring these decisions to the default planner. That extends
its coverage without changing any non-player strategy.

### Separate follow-ups

The source review also established a non-player Belgic Litaviccus targeting
defect: its current largest-Roman-stack choice does not maximize Losses forced
on Legions. General prediction against a human defender needs the narrow
disposition recorded in
[Q-LITAVICCUS-NP-PREDICTION](../../QUESTIONS.md#q-litaviccus-np-prediction--belgic-target-selection-on-shaded-45-3-november-2026).
The witness is decisive even without uncertain responses; the unresolved
part is the general replacement predictor. PR-11 has not been silently
extended beyond numeric 67. This separate non-player repair remains open.

Possible Capability/prefire omissions in other fixed Battle wrappers are
an investigation lead, not a confirmed finding or a claim of repair here.
BE-09 already tracks outstanding human Capability choices. Other Event
March grants, ordinary casualty identities and general Special Activity
timing retain their separate audit dispositions.

## Validation

The exact accepted Python source is 452 files, SHA-256
`7d627253f5b38bdedcfe5c84214a5476f68898d1f9cd11d50ef29377a42fe108`,
prepared over parent `4e9a82ed35052198987dad4c91dd79ce9c5b4ab9`.
No Python source changed between the freeze, full suite and game matrix.
All 49 protected files (47 supplied references, canonical constants and the
existing balance baseline) retain their original bytes.

| Check | Result |
|---|---|
| Full suite, Python 3.10.22 | 7,347 passed; zero failures, errors or skips |
| New regression cases, Python 3.12.14 | All 142 passed |
| Independent final Retreat review | 57 focused cases passed; no acceptance blocker |
| Zero-player games | 150 completed and audited across all five scenarios and three edition profiles |
| Bot repeat under another Python hash seed | 25 additional executions; matching recorded results |
| Mixed-player validation | 220 distinct cases, replayed and repeated at hash seeds 0 and 7: 880 executions; zero hard findings or partial games |
| Strict census | 20 completed executions; zero illegal or failed games; cross-hash output matches |
| Parent comparison | All 150 records match in gameplay fields, including final-state hash; elapsed time and source labels excluded |
| Existing balance check | Passes the unchanged 15-percentage-point limit; baseline file unchanged |

Bots use legacy seeds 1–20 and original/second-edition seeds 201–205.
Mixed-player checks use legacy seeds 1–40 and each explicit edition's seeds
201–202; census uses seeds 201–202. These are bounded regression samples,
not an exhaustive rules proof or a new balance estimate. Equality of the
recorded game results does not prove every intermediate decision identical.
The constructed regressions exercise repaired edge cases that these bot
seeds did not change.

The six new regression modules cover engine legality and card exceptions,
terminal choices/display, independent source examples, durable sessions,
Numidians physical participants and randomized human-choice coverage.
Final parent-negative runs reproduce defects before repair; retained passing
controls protect existing behavior. Earlier failed development attempts,
including a withdrawn borrowed-only fixture and a private-helper free-cost
fixture correction, remain labeled as superseded evidence rather than
counted as additional product defects. The earlier setup attempt without
pytest is retained separately from passing verification.

The parent's 7,205-test suite and 14 passing GitHub checks are reused after
exact-source verification. Parent gameplay records retain their original
source labels: the previous matrix's production files are byte-identical
to this parent, with only a subsequent test expectation changed. The archive
includes that 187-production-file equivalence proof, original parent records,
commands, manifests, current raw results, focused logs and JUnit. No paired
trajectory rerun was needed because no recorded NPC gameplay result changed.

## Progress and retained evidence

BE-02 is closed. The original audit now stands at **20/50 closed (40%),
with 30 open**. This measures grouped findings, not engineering effort or
overall game correctness. Related mechanics repaired here do not inflate the
original denominator. Three unadopted source questions and the 34 unverified
inventory rows remain separate; the eleven existing provisional rulings are
unchanged.

- [Machine-readable acceptance](event-battle-choices-2026-11-03-results.json)
- [Evidence archive](event-battle-choices-2026-11-03-evidence.zip)

Archive: 627,397 bytes, 146 indexed files; SHA-256
`62b50a93e2e1f91ea77d277d6d4b2a63a4abbf202509f69f874568c07b91ac2b`. Its member sizes and hashes were verified after packaging.
