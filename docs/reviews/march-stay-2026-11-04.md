# March hide in place — 4 November 2026

Client date: America/Chicago. Parent `518172beac3c5c348ad50fb6529ae89d81cd80f7`.
Tested working Python digest:
`9b50d0f5cc54ba02385b1647f76f41cea84ef48f8cb54a8a741162ed212441fb`
(483 Python files). The publishing commit includes this frozen source.

## Source and correction

Chapter 3 §3.2.2 selects Roman origins, charges per origin, hides all Revealed
Auxilia, then moves groups as desired. §3.3.2 permits Gallic moving and/or
hiding: hide all Revealed Warbands or remove Scouted markers, then move if
desired. §3.4.2 explicitly hides base German Warbands whether or not they move;
A3.4.2 gives German Leaders/Warbands the Gallic procedure. §2.3.8 still blocks
ordinary March at Frost. §4.1.3 prohibits an SA with movement into/out of
Britannia, not an origin selection with no crossing.

Previously, terminal plans needed a destination, route normalization discarded
empty paths, and origin affordability required a nonempty route. A paid hiding
selection could therefore never execute through the ordinary human interface.
The existing low-level per-origin hiding mechanic already supported no movement.

An explicit `routes[origin] = []` now selects a stay. The normal affordability,
origin payment and whole-origin visibility procedure run, with no moving group
allocation, movement, Harassment or dice. Successful stays report
`stayed_origins`; `marches` continues to contain actual movements only. Mixed
moving/staying origins share selected order and the Resource budget. Multiple
groups at one origin still pay once and flip once, preserving de-Scouted pieces
as Revealed. The terminal appends a clearly priced stay option and permits
origins even without a reachable neighbor; required-destination Events offer
movement only. Missing paths do not become inferred stays.

## Limits and compatibility

Explicit empty routes now mean stay; callers wanting automatic destination
routing must omit the route rather than send an empty list. Existing moving
routes and missing-route bot planning remain supported. A stay requires mobile
pieces, just as the existing origin selector does. It may accompany an otherwise
legal SA, before or after, and an SA is not prohibited solely because a staying
origin is Britannia. The normal free-action Region, destination and Limited
Command restrictions apply. Ordinary March at Frost remains rejected; Event
March retains its existing exemption. No bot priorities, baseline, costs,
reference files or canonical constants were changed.

This closes MARCH-HIDE-IN-PLACE only. Ordinary transit dropoffs, general
mid-March SA timing, full Rampage victim choices, CV-PERSISTENCE, NPC Intimidate
targeting and other open findings retain their dispositions.

## Validation

**7,880 tests pass** in the final full suite (318.23 seconds), with zero failures, errors or skips. **203 targeted tests pass**, including 40 new
regressions. Coverage includes all four base player factions, all four expansion
player factions, Devastation, Scouted handling, affordability and mixed origins,
preview/RNG isolation, save/load, ordinary/free-Event durable acceptance,
required-destination rejection, base German mechanics, once-only flips, Frost,
Limited Commands, before/after Build and the Britannia crossing constraint.

An isolated parent checkout runs the same new test file against parent code:
17 behavioral failures reproduce missing hiding/paid-origin deferral; two
controls pass and 21 other cases are deselected. No missing imports or APIs
are used as proof. Ten native-bot cases cover seeds 1–2 in all five scenarios.
Mixed-seat matrices use the same seed set, hash seeds 0/987, reactions, Events
and internal replay (40 executions total).

All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 74 successful Events, zero hard findings, zero partials,
batch digest `c7366266d0681cf4`. Internal replay makes 40 executions in total. These small matrices are
compatibility/determinism checks, not a new balance study or full rules proof.
All 47 supplied references, canonical constants and the balance baseline are
protected (49 inputs total).

## Progress

MARCH-HIDE-IN-PLACE closes one original finding: **27/50 closed (54%), 23 open**.
The separate defects, 34 unverified inventory rows, two source questions and
twelve provisional rulings are not absorbed into that denominator.

[Machine-readable results](march-stay-2026-11-04-results.json) ·
[Evidence archive](march-stay-2026-11-04-evidence.zip)
