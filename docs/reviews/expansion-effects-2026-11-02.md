# Gallia Togata evacuation and Dread — 2 November 2026

This batch closes **EXP-07 and EXP-10**, two findings from the
[29 October human-choice audit](human-choice-audit-2026-10-29.md). A5 unshaded
now evacuates every affected non-Roman piece under its owner's direction;
A22 shaded now supplies its added Intimidating Warband and removal. The
related unshaded A22 protection also applies to Roman Recruit in Intimidated
Regions.

The [progress register](../human-choice-progress.json) records **14 of 50
findings closed (28%) and 36 open**. This two-finding batch is **2/2 complete
(100%)**. Finding sizes vary; these percentages describe the identified repair
bundle, not overall rules accuracy or work-hours remaining. Historical audit
measurements and previously unverified scope remain distinct. The task began
2 November; final validation continued on 3 November UTC.

## Repaired behavior

### EXP-07: A5 unshaded Gallia Togata

The Event executor selects the resolution order when several non-Roman
owners have pieces in Cisalpina. Each affected owner then chooses where its
own pieces go, using the board after earlier owners have resolved. A human
may split a Hidden, Revealed or Scouted group among legal Home Regions and
removal, or remove pieces even when movement is available. Every affected
piece must be accounted for; structures cannot remain behind.

Movement preserves physical ownership, visibility and Leader identity.
Allies retain exact source-Tribe identity and require legal destination
Tribes; source and destination allegiance records stay synchronized. Normal
Tribe restrictions, occupied and Dispersed spaces, and Settlement limits
still apply. German Regions with Settlements count as Homes, while Cisalpina
itself is excluded. Diviciacus removal uses his existing removed-from-play
handling. The Roman garrison and the existing Gallia Togata movement,
Recruit, setup and Interlude mechanics retain their separate behavior.

Owner order can matter on a legal board: Colony can add a second Tribe and
another owner's Ally in Cisalpina, while German Settlement Homes can overlap
Belgic Homes. Both owners may want the same vacant destination Tribe. The
new order choice and subsequent owner choices resolve this explicitly.

Non-player defaults preserve pieces whenever a legal move exists, favor the
Leader destination with most own pieces and provide a four-Warband escort
as able, apply the ordinary Ally priorities and use seeded ties. Expansion
Arverni resolve automatically. A5 is a direct Event relocation, so it does
not import March-only hiding, adjacency or Control-retention restrictions.

### EXP-10: A22 Dread

Ordinary Intimidate can use up to three Hidden German Warbands with shaded
Dread, removing the same number of eligible pieces from one Faction. The
usual Region, target-type and protected-Leader restrictions still apply.
The added Reveal must fund an added removal; it cannot produce an extra
marker-only benefit. Human planning, execution, non-player/default choices,
A45's grant and terminal menus use the same capability-aware limit.

Raid's intrinsic free Intimidate remains a separate application from an
ordinary accompanying Special Ability. It uses actual successful Raiders,
with Dread's optional additional participant handled as follows:

| Available participants | Intrinsic Intimidate limit |
|---|---|
| One or two Raiders, no shaded Dread | No more removals than actual Raiders |
| Three Raiders from shaded Baggage Trains, no shaded Dread | Two removals |
| Three actual Raiders with shaded Dread | Three removals; no fourth Hidden Warband required |
| One or two actual Raiders with shaded Dread and another eligible Hidden Warband | One extra Reveal/removal, up to three removals total |

An A29 Raid remains confined to its surviving newly placed cohort, including
any fresh Dread participant. Resident Warbands cannot substitute for those
pieces; resident Ariovistus can still satisfy the separate Leader-presence
requirement. A29's Event executor owns the offensive choice. Any subsequent
ordinary Intimidate uses the Hidden Warbands actually remaining after Raid's
intrinsic effect.

The same-card review also corrected unshaded Dread: its protection now
prevents Intimidated markers from blocking Roman Recruit. It does not waive
Devastation or protect another Faction's Rally. The active Capability side
takes precedence over a stale legacy modifier; modifier-only older saves
retain their supported behavior.

## Source basis

The supplied [Ariovistus card reference](../../Reference%20Documents/Ariovistus/A%20Card%20Reference)
provides A5's owner-directed move-or-remove instruction and both A22 effects.
[Chapter 5](../../Reference%20Documents/Chapter%205) §§5.1, 5.1.1 and 5.1.3
assign otherwise-unspecified implementation choices to the executor,
preserve ordinary stacking and require possible Event effects to occur.
A5 delegates each owner's piece disposition, but not owner-group order.
Cards 47 and 48 explicitly prescribe initiative order where intended; A5
does not. This applies the general rule rather than adding a new ruling.

[Chapter 1](../../Reference%20Documents/Chapter%201) §1.4.2 and
[Chapter A1](../../Reference%20Documents/Ariovistus/Chapter%20A1) supply
Tribe/City restrictions, Settlement Homes and limits, and Diviciacus removal.
[Chapter 8](../../Reference%20Documents/Chapter%208) §§8.3.1–8.3.4/8.4.1 and
[Chapter A8](../../Reference%20Documents/Ariovistus/Chapter%20A8) govern
non-player priorities and seeded choices.

[Chapter A3](../../Reference%20Documents/Ariovistus/Chapter%20A3) A3.4.3 makes
the actual Raiding Warbands' free Intimidate simultaneous with Raid. Read
with [Chapter A4](../../Reference%20Documents/Ariovistus/Chapter%20A4) A4.6.2,
A22 and base card 8, this allows the third actual Raider to supply Dread's
added Reveal. Sequential engine bookkeeping cannot require an additional
fourth counter. This is a combined reading of supplied text, independently
reviewed, not a new designer clarification or provisional project ruling.
The existing provisional rulings are unchanged.

## Human choices, validation and compatibility

A5 adds specialized free-action requests for affected-owner order and each
owner's complete physical allocation. Responses cannot override ownership,
omit pieces, over-allocate a cohort or reuse an occupied Tribe. Validation
uses a detached board and RNG; terminal planning does likewise. The common
human decision display supplies current/upcoming card text and changes
before decisions, with `board`/`b` available during the new menus.

Raid Intimidate retains its existing request kind and targets-only response.
Targets-only uses actual Raider credits. With shaded Dread, the request also
reports the actual-Raider limit and fresh-Warband availability; an optional
strict boolean `extra_warband` explicitly selects one fresh participant.
Forged credits, excessive removals, ineligible counters and malformed values
are rejected. Without shaded Dread, the existing request shape remains.

Explicit human defaults stay distinct from missing input. Missing or invalid
durable responses remain pending; invalid retries preserve the decision ID,
live board, RNG and journal. Regression coverage includes pausing after an
earlier A5 owner has moved, save/load, exact response replay, terminal EOF
and board inspection. Old affected transcripts may stop at changed decision
signatures and require new input; newly necessary choices are not silently
filled in. There is no new persistent save-format version.

## Validation record

Two isolated implementation branches and independent source/code review
preceded integration. The parent then validated the combined source.

| Check | Accepted result and revision scope |
|---|---|
| A5 focused regressions and compatibility paths | 29 new cases; 257 related cases passed |
| A5 full suite before its source commit | 6,506 passed on its isolated branch |
| Dread focused regressions and compatibility paths | 45 new cases passed; 141 related/message-compatibility checks passed |
| Dread full suite before its source commit | 6,522 passed on its isolated branch |
| Combined full suite | 6,551 passed, zero failures; 74 new cases versus the 6,477-test parent |
| Final documentation full-suite rerun | 6,551 passed; zero failures, errors or skips; JUnit retained |
| Integration games, replay, census and outcome comparisons performed | 150 audited bot games; 120 mixed-seat executions including replay; 20 strict-census executions; all passed |
| Protected references, canonical constants and baseline | All 49 SHA-256 hashes unchanged (47 supplied references, constants, baseline) |

A5 source commit: `cf982d289fd350266c758f2ab0d71c858e7e9490`. Integrated Dread source commit:
`9a2bad256073cbc5c76329af0e02d352d9d0a041`. Final validated engine source:
`9a2bad256073cbc5c76329af0e02d352d9d0a041`; **407 Python files**, SHA-256 `d78d921cdb2db2c60bd433270bca2a80fb92462888610e8199522de41b749797`.

Evidence: [machine-readable results](expansion-effects-2026-11-02-results.json) and [evidence archive](expansion-effects-2026-11-02-evidence.zip). The archive retains
source/implementation handoffs, before/after witnesses and raw accepted
validation alongside clearly labeled earlier failures. A pre-final Dread
suite exposed an established error-message compatibility expectation; the
implementation restored that wording without weakening the existing test.
Earlier test-fixture errors and incomplete/superseded runs are not counted
as final-source successes. Focused and full-suite counts overlap and must
not be added together.

### Matrix scope and changed outcomes

The fresh bot matrix covers all five scenarios: 100 legacy games at seeds
1–20, plus 25 original and 25 second-edition games at seeds 201–205.
Each game and audit completed, reported its final ranking, and had no errors,
integrity findings or nonlegal diagnostics. Thirty distinct mixed-seat cases
(seeds 201–202 × five scenarios × three editions), each at hash seeds 0/7
with replay, produced matching digests, zero hard findings and no partials.
The strict census covers ten games at each hash seed; both reports match
and contain only 133 legal-decline incidents each.

The original balance baseline remains unchanged at the existing 15-point
band; the largest absolute faction win-rate difference is five percentage
points. Seven winner/card-count pairs differ from that baseline, six already
explained in the preceding Event-grant report. Compared with the immediate
parent's byte-identical measured Python source, one additional pair changes:
The Gallic War, legacy seed 1, changes from Aedui after 102 cards to Belgae
after 103. The 100 parent records are explicitly reused evidence from the
previous report, not claimed as fresh runs; `task-baseline.json` records
identity and provenance.

A fresh trace of just that parent/candidate pair reproduces both outcomes.
All 134 preceding trace rows, the incoming board/RNG and the Event decision
match. The first divergence is Roman unshaded A5 at played-card count 37:
the old resolver moves only a German Warband and illegally strands the
Settlement and Nori Ally in Cisalpina. The repaired resolver moves the
Settlement and Hidden Warband to Ubii and the Ally to Suebi (North) in
Sugambri, clearing Cisalpina and its Tribe record. Both versions place the
same available Roman Auxilia; only the repaired evacuation leaves Roman
Control there. Exact replay of that execution confirms two legitimate
random destination selections, with no RNG use for the Ally's sole legal
slot. No unexplained first divergence was found. This explains the initial
change, not every downstream winner/length difference; the two trace runs
are separate diagnostic repetitions, not added to the 150-game matrix.

Commands and raw records are retained in the archive. Full suites use
Python 3.12.14 and `python -m pytest -q -n 2`; the final documentation check
also records JUnit. Integration commands and the unchanged-source assertions
are in `integration-commands.json` and `integration_checks.py`. The baseline
SHA-256 remains `207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3`.

## Remaining scope

- **A5 shaded and other exact Event removals remain open under EXP-11.**
  This repair changes unshaded evacuation, not the Roman shaded-removal
  choices. Interlude Cisalpina relocation remains a separate seasonal issue.
- **CMD-INTIMIDATE-TRIBE remains open.** Dread's quantity/participant correction
  does not add exact Allied-Tribe selection to ordinary Intimidate. A5's
  exact Tribe allocation does not close that separate command finding.
- **A separate NPC pre-Battle projection lead remains unverified.**
  `_check_intimidate_before_battle` excludes an entire planned defender
  Faction, whereas A8.7.1 refers to pieces guaranteed to be removed in the
  immediately following Battle. Existing tests enforce the current broad
  exclusion. A future review must establish guaranteed losses, Retreat and
  post-Intimidate Battle legality before changing that policy. No executable
  witness was completed for this lead here; it is neither a verified new
  finding nor an additional completed repair.

The remaining audit findings, unverified inventory coverage and source
questions retain their separate status. Passing these bounded checks does
not establish exhaustive rules correctness or statistically conclusive
faction balance.
