# Litaviccus targeting and participating forces — 3 November 2026

Date convention: America/Chicago. Parent:
`4f33e09347d809846d61e8cc25ebf711100372fc`. This is the separate follow-up
identified by the [Event Battle repair](event-battle-choices-2026-11-03.md),
not an additional closure in the original 50-finding audit.

## Adopted policy and printed requirements

The owner adopted [PR-12](../provisional-rulings.md#pr-12): for a human Roman
opponent, predict the lower Legion Losses across legal standing and Retreat
responses. Use the actual published non-player Roman response for a bot.
This interpretation is provisional and subject to possible later correction
if an authoritative source is found. It is separate from numeric Arduenna's
PR-11 and does not change that ruling's scope.

The Belgic Event instruction requires the Battle causing the most Losses on
Legions; if none is possible, apply “No Belgae.” The previous implementation
selected the largest Roman stack and considered a Battle effective even when
it could not cause a Legion Loss. Availability and execution must now use the
same prediction and printed conditions. Equal best targets use the state's
seeded RNG when committing to a plan; read-only prediction does not consume
live randomness or consult actual human decisions.

The Event combines Aedui pieces with the executor's and requires Ambush when
able. Ordinary applicable regional Battle safety and Frost/player-victory
restrictions remain binding under §§8.2.3, 8.4.4 and 8.5.1. The printed
Defender-roll convention governs the scoring forecast. Human response
prediction retains ordinary default casualty priority; it is not an
exhaustive optimization over every human casualty assignment. Actual
responses and dice resolve normally after target selection.

This targeting policy is scoped to non-player Belgae executing shaded
numeric 45 under the base rules. Human targets and other factions' Event
instructions retain their own scope. Expansion A45 is a different Event.

## Related participating-force repair

A source-derived position exposed a prerequisite defect: two Aedui Hidden
Warbands could attack four Roman Auxilia for Litaviccus, yet remain Hidden
and untouched after the Roman Counterattack. The old `allied_factions`
parameter contributed attack strength without consistently participating in
Retreat forecasting, casualties and Reveal.

The shared force must participate through the whole Battle, while every
physical counter retains its owner. Aedui acting for themselves must be
counted once. Litaviccus includes all Aedui pieces; Admagetobriga's narrower
Warband/Auxilia loan remains separate. Optional Diviciacus does not become
Ambiorix or grant a named Leader's abilities. Inspection must continue to
show the physical board and explain the temporary participating force.

The combined non-player casualty order also preserves City/Remi Allies
across physical owners, with an exact Tribe attached to those internal
choices. Diviciacus keeps his own save/removal rule and last-piece
restriction; his contribution is additional to a native Leader, without
granting that native Leader's identity or Special Ability range.

Independent forecast regressions cover Caesar's Ambush escape after Slingers
prefire changes Hidden superiority. Forecasting uses the Ambush decision
already validated by the actual executor, rather than rechecking it later.
Battle safety compares full requested Loss totals, even when fewer pieces
remain to absorb them. The result now reports that total separately from
pieces removed and Losses absorbed. Frost checks include physically distinct
casualty ties where the owner's victory margin can differ.

## Validation and limits

The accepted source is 457 Python files, SHA-256
`90a57ffbce8c94a9a4dc2690b15c5cce3bfa45e6b7f2e0b4af367ca883efeb06`,
prepared over parent `4f33e09347d809846d61e8cc25ebf711100372fc`.
All Python files remained byte-identical through the full suite and game
matrix. All 49 protected inputs (47 references, canonical constants and the
balance baseline) are unchanged.

| Check | Measured result |
|---|---|
| Full suite, Python 3.10.22 | 7,427 passed, zero failures/errors/skips |
| New cases, Python 3.12.14 | All 80 passed |
| Independent rules suite | 18 passed; no remaining blocker |
| Bot matrix | 150 completed/audited games across all five scenarios and three card profiles |
| Bot hash-seed repeat | 25 additional executions; recorded gameplay fields match |
| Mixed human/bot seats | 220 distinct cases, replayed and repeated under two hash seeds: 880 executions, zero hard findings or partial plans |
| Strict census | 20 executions, no errors; 100 legal-decline occurrences per hash seed |
| Cross-hash mixed/census evidence | Complete JSON and stdout match for the paired runs |
| Before/after records | 143 unchanged and seven changed in gameplay fields, including two changed winners |
| Paired diagnostic games | 14 executions reproduce all seven changed pairs |
| Balance guardrail | Unchanged baseline and 15-point limit; maximum observed drift 10 percentage points |

Bot seeds: legacy 1–20 per scenario; original and second-edition 201–205.
Mixed seats: legacy 1–40 and explicit editions 201–202, each at Python hash
seeds 0 and 7 with replay. Census: seeds 201–202 at hashes 0 and 7. Diagnostic
trace games and hash repeats are not additional independent outcome samples.
All 60 expansion-scenario comparison records are unchanged in this sample.

The parent 7,347-test suite, 14 successful CI checks and 150 bot records are
reused after exact-source verification. Their original labels are preserved;
the accepted source bytes match the subsequently committed parent. Earlier
failed development attempts are retained. Parent tests distinguish existing
behavioral failures from tests that fail merely because the new forecast API
is absent. Candidate refinements include a before/after Caesar-prefire
witness and a City/Remi priority regression; these are not inflated into
extra historical product bugs.

### Outcome changes reviewed

Each changed game first diverges at numeric 45 after the preceding physical
board and RNG agree. The root and independent review examine the actual
positions and resulting piece changes, not only matching run totals.

| Profile/scenario/seed | First difference supported by the source |
|---|---|
| Legacy Great Revolt 2 | Counterattack removes the participating Aedui Scouted Warband in Provincia. |
| Legacy Great Revolt 13 | The only candidate cannot inflict a Legion Loss, so the Belgae follow No Belgae and Rally. Final winner changes from Arverni to Belgae. |
| Legacy Great Revolt 16 | Counterattack removes two participating Aedui Revealed Warbands in Arverni. Final winner changes from Romans to Aedui. |
| Original and second-edition Pax Gallica 202 | One Aedui Warband cannot cause a Legion Loss against the fortified Romans; No Belgae replaces the Event. Romans still win, at card 54 rather than 42. |
| Original and second-edition Great Revolt 202 | All nine surviving Aedui Warbands Reveal after their Ambush in Sequani. |

These traces explain the first changed mechanism and reproduce final records;
they do not certify every subsequent decision. Bounded seed samples do not
establish human balance or exhaustive rules correctness. The conservative
stance forecast retains default casualty priorities. Real human responses,
dice and later play can differ from the prediction.

No save schema changes. Continuing an older save uses corrected mechanics;
exact replay of old response logs across versions is not promised. Current
revision save/load/resume and replay include a real human Counterattack
choice removing the selected physical Aedui casualty.

## Progress and evidence

This separately discovered follow-up does not close another original audit
finding: **20/50 are closed (40%), with 30 open**. Two source questions still
lack adopted policies; PR-12 brings the provisional register to twelve.

- [Acceptance results](litaviccus-targeting-2026-11-03-results.json)
- [Evidence archive](litaviccus-targeting-2026-11-03-evidence.zip)

Archive: 886,524 bytes, 179 indexed files; SHA-256
`a04a82a42ddc9c173d7bd809fd19b8d6ca4cfd2d595b70d4de3f2b5e749bf2f4`. Member sizes/hashes and ZIP integrity were verified.
