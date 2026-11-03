# Camulogenus March choices — 3 November 2026

Date convention: America/Chicago. Parent: `4b112b1e5c180b8ff243e9b8e4d8ca76ad22d43e`.
This is a partial repair of BE-01 in the original human-choice audit.
Supplied rules, canonical constants and the balance baseline are unchanged.
No new provisional ruling is introduced.

## Behavior and sources

Numeric 70 unshaded gives the Roman beneficiary the whole-benefit acceptance
decision, even when another faction plays the Event. After acceptance, Romans
choose one destination among Atrebates, Carnutes and Mandubii, then ordered
groups from one or several original Regions. Each group specifies Legions,
Auxilia, Caesar participation and a complete route. The four-Legion limit is
shared across all groups. Ordinary two-step movement and Caesar's third step
apply; dropoffs, Successor/Diviciacus Leader movement and ungranted activities
are rejected. Empty movement can leave a normal Battle at the chosen destination.

Card Reference 70 and its Tips govern these exceptions; §§3.2.2, 3.2.4,
5.1.3 and 5.4 govern the underlying Commands and partial execution. The Tip's
moving-force language is read in its March context: it explains why stationary
pieces do not flip. The separate Battle uses the destination's normal force.
This contextual reading is supported by Card 72's explicit contrasting restriction
that its moved group Battles alone; it is not claimed to be a designer clarification.

Exact physical cohorts are reserved before movement. Arrivals cannot join a
later group; selected pieces cannot move twice. Only participating Auxilia
(including cooperating Aedui Warbands) change visibility. Physical ownership,
Control and inventories remain intact. Cooperation is separately authorized
for March and Battle; refused March loans reoffer planning without asking for
whole-benefit acceptance again.

The related default-planner bug is also repaired: failed movement must not
cancel the separately granted Battle when Roman Forces are already at the
destination. Regressions cover a destroyed mover, a mover removed before its
first step, and static-only resident Forces. Human default selection recognizes
a legal static-only destination; other NPC target priorities are retained.

Terminal menus show card/board information and preserve `board`/`b` inspection.
Durable missing, invalid or wrong-seat responses remain pending with stable
identifiers and board/RNG rollback. Tests use actual assistant play/submit/replay
commands, including saved physical formation and following Battle decisions.
The save schema is unchanged; old response logs can encounter new decisions,
so exact replay across revisions is not promised.

## Verification

Accepted Python source: **463 files**, SHA-256
`bb90b47656f19acfa1f64c0b799292e494aeedf6b414761566fd4290b0ad20f2`. Python **3.12.14**.
The source was frozen for the final suite and matrix; all **49 protected files**
matched their parent hashes.

| Check | Result |
|---|---|
| Parent full suite | 7,427 passed |
| Final full suite | 7,485 passed; no failures, errors or skips |
| Added regression cases | 58 |
| Independent parent proof | 24 existing-behavior failures and one passing control; no missing-API failures |
| Bot games | 120 accepted: 100 legacy seeds 1–20 and 10 each original/second-edition seeds 201–202, all five scenarios |
| Parent comparison | All 120 recorded gameplay results unchanged on the same Python runtime |
| Bot hash repeats | Five exact matches, one per scenario |
| Mixed-player runs | 30 distinct scenario/seed/edition cases, 120 executions including replay and both hash seeds |
| Mixed findings | Zero hard findings and zero partial plans; complete JSON/stdout match across hashes |
| Strict census | 60 executions across three editions and both hashes; legal declines only |
| Balance | Existing 100-game baseline and 15-point band unchanged; maximum shift 10 points |

The mixed-player generator now exercises Camulogenus acceptance and authored
movement instead of silently relying on the old planner. It reports 24 rejected
generated plans across the 30 distinct cases (eight per edition); these rejected
inputs are distinct from engine errors and partial execution. Fixed-seed results
are bounded evidence, not an exhaustive strategy or rules-compliance proof.
Unchanged bot records are not a complete turn-by-turn trajectory comparison.

Earlier development failures and validation attempts are retained. Attempt1
passed its matrix but was superseded after review confirmed the existing default
resident-Battle defect. Attempt2's source changed while checks were running;
those results are not accepted. The final matrix was rerun on attempt3. Its
first full-suite runner ended without a completion report;
`candidate-suite-final.xml` is the completed accepted rerun on the same
frozen source.
Fixture imports and overly broad test wrappers were corrected during development;
these are not reported as production bugs. A duplicate physical-formation prompt
introduced during this implementation was caught and fixed before publication.

Machine-readable results: [results JSON](camulogenus-2026-11-03-results.json).
Raw logs, manifests, prepared patches, parent/candidate records and verification
scripts: [evidence ZIP](camulogenus-2026-11-03-evidence.zip), with an internal
file-size/SHA-256 index. GitHub CI is checked separately after publication.

## Remaining work

Original audit: **20/50 closed (40%), 30 open**. BE-01 remains open for numeric
4/9/17/58/65. Numeric 67 was repaired previously; this repair completes numeric 70.
The 34 unverified inventory rows, two unadopted source questions and twelve
provisional rulings remain separate from that denominator.
