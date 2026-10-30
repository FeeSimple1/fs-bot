# Action timing and exact participating pieces — 29 October 2026

Dates use America/Chicago. This report follows commit
`5ee485e43132e9080a083efece79c66af80afef8`, whose separate rules/Trade report
records its own 5,777-test checkpoint. Those measurements are not results
for this revision.

## Scope and sources

The owner requested repair of the three remaining interface gaps:

1. Voluntary own-piece removal and Citadel downgrades during legal action
   procedures (§1.4.1), including later placements that need those counters.
2. Vercingetorix's entry from the Spring box after the first eligible Spring,
   during other actions and later Winter (Pax Gallica scenario instructions).
3. A Special Ability between Vercingetorix's two Rally options in one Region
   (§§3.3.1 and 4.1).

Implementation follows the repository's supplied Reference Documents,
including scenario/Interlude exceptions, Event text, and the nine existing
owner-adopted provisional rulings. No protected reference or canonical
constant is edited. No additional project ruling is adopted by this batch.

## Resulting behavior

The outer human Sequence-of-Play executor retains the right to reclaim its
own physical pieces throughout its Command/Event. Grants to another faction
do not transfer that right. Non-players do not voluntarily reclaim pieces;
Pass and Winter do not create an independent removal right. Legions return
to their track, Diviciacus leaves play, and the permanent Provincia Fort
cannot be selected. Exact Tribes distinguish Citadel downgrades from other
Allies, including Colony stacking and an exhausted Ally pool.

Unlocked Vercingetorix remains a separate Arverni decision, regardless of
whose action is resolving. Entry is offered between complete procedures,
before the next legal options are computed. Completed dice, loss totals,
Retreat declarations, and initial fortification protection are retained.
The first-Spring and scenario gates still apply; the Interlude does not
unlock the box early, and a completed game offers no further entry.

One ordered Rally plan can resolve a first option, its Special Ability,
and a second option in the same Region. It charges the Region and applies
its placement bonuses once. The second option checks Vercingetorix and the
actual board at that time. Entering or removing him, gaining an Ally by
Entreat, or consuming the same Available pool changes what can happen next.

CLI previews offer timing before computing pools and eligibility. Typed
Events use detached execution of the completed prefix, stopping before the
next operation; they do not consume live decisions or RNG. `board`/`b`
continues to inspect the board used by the current decision. Current and
upcoming card text and changes precede human choices. Some legacy scalar
or dynamically derived Event menus expose their internal timing choices
during execution rather than during initial plan collection.

The durable assistant frontend records explicit optional decisions, keeps
missing/invalid responses pending, and verifies save/resume and replay.
Historical records can skip newly introduced windows only while matching
their older recorded history. Fresh decisions are not silently delegated.
Raw callbacks opt into the additional requests with
`supports_action_windows = True`; their existing fallback contract remains
distinct from a durable human session.
Replay compatibility for inserted timing requests does not reproduce old
incorrect game effects. A historical transcript affected by a substantive
rule correction, including previously omitted Seize Rallies, can fail
verified replay; the frontend reports that mismatch explicitly.

## Related defects exposed by the timing work

- March groups distinguish travellers from residents of the same owner and
  visibility. Removing a carried Leader changes remaining movement; a newly
  arriving Leader does not silently join an already selected group. Enlist
  dropoffs and Harassment retain exact physical-owner counts.
- Diviciacus loans can overlap an Impetuosity force. Removing, moving, or
  flipping a counter updates both memberships, with an explicit human choice
  when only some same-owner counters belong to the selected force.
- Scout can no longer move an arriving counter again. Its preview includes
  arrivals for subsequent Reveal, and distinguishes already-moved pieces
  from residents during voluntary removals.
- Dumnorix distinguishes original replacement targets, newly placed pieces,
  and its subsequent Scout/Raid participants. Related Event cohorts survive
  later windows without substituting unrelated residents.
- Human Vercingetorix's Elite selections retain physical identity for losses
  and Counterattack. Fixed Attack losses do not change when a later window
  removes a piece. A69 counts its surviving placed Warbands when Attack
  losses are determined.
- Suborn previews and execution process ordered timing and shared pools;
  a later invalid operation restores the complete transaction. Rampage
  includes Scouted Warbands as legal targets.
- Roman Quarters preserves completed adjacent moves if later Vercingetorix
  entry blocks a Supply Line. A continuation request revises Provincia
  relocation and payment choices without repeating those earlier moves.
- Surus is restricted to the German Warbands actually placed and uses the
  Event executor's legal Command choice, rather than an unrestricted German
  Battle sweep. Its previously missing bot replacement plans now execute
  both printed sides. Seize's successful Rally rolls grant the printed free Rally
  before later steps instead of returning unused opportunities.
- Ordinary non-player casualties follow the printed Scouted, Revealed,
  Hidden order. The unresolved implicit Elite designation is excluded from
  that correction. Roman March uses the player-priority tier only on a
  roll of 3 or 4 and chooses exact destination ties randomly.
- Corrected durable plans can reuse a decision identifier without a prior
  response receipt swallowing the new answer. Receipt identity includes the
  accepted response ancestry, preserving duplicate-delivery protection.

## Validation

The frozen Python source is
`c24adb23c9018071ed948e295a96fc4b17649e35fecabd985e77dedbfa32fcc5`
(379 files), based on parent `5ee485e`. The 48 protected reference/constant
files, nine compatibility fixture files and three runtime/dependency files
are unchanged. The accepted attempt is `attempt2`; all results below are
from that frozen revision and the explicitly reviewed baseline.

### Preserved failure and outcome review

The first frozen full suite passed 6,108 tests and failed only the bot balance
canary. That test checks seeds 1–3 with its existing 40-point small-sample
band. A separate diagnostic run then completed all 100 legacy games, seeds
1–20 in each scenario, with no audited errors or integrity findings. Against
the original `815b6f36…` baseline, Reconquest Belgic wins rose from 1 to 5 out
of 20: a 20-point increase, failing the unchanged 15-point main guardrail.
The original failure is preserved, not relabeled as a pass.

The original baseline was already different from the immediately preceding
accepted revision. Original-to-parent comparisons changed 63 winner/card
records (47 winners); parent-to-candidate changed 54 records (43 winners).
Each of those aggregate comparisons individually remains within 15 points.
The accumulated original-to-candidate comparison changes 69 records,
55 winners and 49 card counts, with the Reconquest breach above.

The review compares all 100 games against the parent, preserving 200 full
accepted traces and 70 exact local boundary replays. First mechanical
differences on equal input states and plans/options are classified as:

| First difference | Games |
|---|---:|
| Roman ranking changes RNG position but keeps the selected plan | 25 |
| Roman random tie selection changes the selected plan | 10 |
| Successful Seize rolls now resolve their free Rally | 22 |
| Surus replacements and its restricted German Command resolve | 18 |
| Ordinary non-player casualty visibility order | 10 |
| No mechanical divergence | 15 |

Random tie choices are required by the rules. The complete ranked-list draw
sequence is an implementation detail and can change later dice even when
the chosen move is unchanged. A first divergence does not establish that
one change alone caused the eventual winner. No policies, seeds or tolerance
were tuned to obtain preferred outcomes.

Raw comparisons retain a new Seize result-detail field; the separate semantic
comparison normalizes only that documented report expansion. All accepted
traces match their separately audited final hashes. Eighteen intermediate
trace files had incomplete gzip output; all originals and tool versions are
preserved. Fourteen affected pairs were recaptured and verified. These were
diagnostic capture failures, not game-engine failures. Earlier unfrozen
development-test logs are also retained separately and are not counted as
accepted validation.

Root and independent reviews approved the exact diagnostic records as the
new baseline only after that causal review. The active baseline SHA256 is
`207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3`;
the preserved original SHA256 is
`815b6f363134159b4cf5772abd4dc76a5e8e0be8fd0bb852dc571390504814f5`.
Both approvals bind the Python source, both baselines, diagnostic records
and causal summary. The accepted fresh validation below passed the unchanged
guardrail and exactly reproduced all 100 reviewed winner/card records.
The diagnostic games and causal replays are additional investigation, not
part of the accepted 150-game matrix.

### Accepted fresh validation

| Check | Result |
|---|---|
| Full pytest suite | 6,109 passed; zero failures, errors or skips; every frozen collected test matched to JUnit |
| Bot games | 150/150 audited: legacy seeds 1–20, original and second-edition seeds 201–205, all five scenarios |
| Mixed seats and replay | 20 unique cases, 80 executions including replay across hash seeds 0 and 7; matching reports; zero hard findings or partial actions |
| Rejected random plans | 14 per hash seed, disclosed separately from engine defects |
| Strict census | 25 cases, 50 executions across hash seeds 0 and 7; matching reports; zero defects; 322 legal-decline incidents per hash |
| Reviewed balance | Fresh legacy 100 exactly matches all reviewed winner/card records; unchanged 15-point tolerance |
| Original balance | Preserved **FAIL**: Reconquest Belgae +20 points; no claim that the old baseline passed |

The verifier passed 6,009 evidence checks. The census provides exact launch
metadata and aggregate completion rather than individual successful-game
rows; the bot and mixed-seat runners retain individual records. The
[machine-readable results](action-timing-2026-10-29-results.json) preserve
those distinctions and both baseline comparisons.

### Bot outcomes in the accepted matrix

Counts below use the ending faction. In The Gallic War, Arverni represents
the former German seat after the Interlude; Germans can win before it.
Each edition has its own seed range and denominator. These small samples
are regression evidence, not estimates of human competitive balance.

| Edition | Scenario | Games | Romans | Arverni | Aedui | Belgae | Germans |
|---|---|---:|---:|---:|---:|---:|---:|
| legacy | Pax Gallica? | 20 | 11 | 2 | 5 | 2 | — |
| legacy | Reconquest of Gaul | 20 | 10 | 0 | 5 | 5 | — |
| legacy | The Great Revolt | 20 | 6 | 9 | 2 | 3 | — |
| legacy | Ariovistus | 20 | 8 | — | 1 | 4 | 7 |
| legacy | The Gallic War | 20 | 10 | 2 | 2 | 6 | 0 |
| original | Pax Gallica? | 5 | 2 | 0 | 2 | 1 | — |
| original | Reconquest of Gaul | 5 | 1 | 0 | 2 | 2 | — |
| original | The Great Revolt | 5 | 1 | 2 | 0 | 2 | — |
| original | Ariovistus | 5 | 2 | — | 1 | 2 | 0 |
| original | The Gallic War | 5 | 0 | 1 | 0 | 4 | 0 |
| second-edition | Pax Gallica? | 5 | 2 | 0 | 1 | 2 | — |
| second-edition | Reconquest of Gaul | 5 | 1 | 1 | 2 | 1 | — |
| second-edition | The Great Revolt | 5 | 1 | 2 | 1 | 1 | — |
| second-edition | Ariovistus | 5 | 2 | — | 1 | 2 | 0 |
| second-edition | The Gallic War | 5 | 0 | 0 | 0 | 5 | 0 |

The accepted runs completed the Interlude in 12 legacy games, 4 original games, 4 second-edition games.

### Evidence and publication boundary

The [evidence archive](action-timing-2026-10-29-evidence.zip) contains both
attempts, full frozen source/fixture/reference snapshots, exact test
collection and JUnit results, raw game records, paired traces, preserved
failures, and both stages of root/independent approval. It has 2,300 members,
58,789,532 bytes, and SHA256
`a615af1336e1d591649c68ab9e05a6273a0a8a1efd56d86f20386ff94500d354`.
Every archive member was read back and checked. The
[receipt](action-timing-2026-10-29-evidence.receipt.json) records those checks.

This is local validation of the uncommitted source based on `5ee485e`,
identified by its full Python and baseline hashes above. Post-push GitHub
checks are separate evidence on the commit carrying this report; the archive
does not claim a remote CI result.

## Remaining work

The three named interface gaps are addressed within the supported procedure
boundaries. The broader source-derived inventory of every human choice is
still maintenance work; a passing batch is not proof of exhaustive rules
compliance or expert human strategy.

Two separate non-player source questions remain in
[QUESTIONS.md](../../QUESTIONS.md#current-open-source-questions): shaded
Trade Region selection and physical designation of Elite Warbands. The
latter has no newly adopted selection policy. The repository's explicit
Never Guess instruction requires stopping that specific ambiguous policy
while completing the independent fixes. PR-01 through PR-09 retain their
existing provisional status, subject to later authoritative correction.
