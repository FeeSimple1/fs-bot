# Changelog

Entries describe repository changes. Package metadata alone does not imply
that an artifact has been published or that every rules interaction has been
verified. Revision-specific results remain in the validation reports.

## Unreleased — Devastate owner casualties, 4 November 2026

- Ask each affected physical owner for exact Devastate casualties by type and
  visibility; preserve zero-loss skips, rounded quantities and Legions to Fallen.
- Collect and validate all choices before mutation. Reject short, overlarge,
  wrong-owner/type/cohort plans, including previously truncated trusted tuples.
- Correct §8.4.1 default priority to Scouted/Revealed/Hidden, preserving stealth
  before hard pieces; retain explicit legacy tuple None-visibility semantics.
- Add terminal, pending-response, later-Region save/resume and replay coverage.
- Close CMD-DEVASTATE-LOSSES: 31/50 original findings closed (62%), 19 open.
  See the [report](docs/reviews/devastate-losses-2026-11-04.md).

## Unreleased — Gallic Shouts private peek, 4 November 2026

- Put the actual next two facedown cards, text and initiative metadata into
  the Roman Card 35 unshaded decision, excluding the already face-up next card.
- Present the private briefing in the terminal before its free Limited
  Command/Become Eligible choice; share Council's existing card rendering.
- Keep private data out of public receipts/modifiers/board snapshots, preserve
  native defaults and deck/RNG state, and cover pending save/resume/replay.
- Close BE-10: 30/50 original findings closed (60%), 20 open.
  See the [report](docs/reviews/gallic-shouts-peek-2026-11-04.md).

## Unreleased — First-Harvest Legion allocation, 4 November 2026

- Let Romans allocate all first-Harvest Winter Track Legions among any Belgica
  Regions, with terminal board inspection and durable response validation.
- Transfer the actual reserve through `place_piece(from_winter_track=True)`;
  preserve legacy NPC concentration and the default result shape.
- Apply the Pax Harvest after Interlude to a positive expedition reserve;
  previously only the empty-box exception was recorded, stranding those Legions.
- Close WS-F03: 29/50 original findings closed (58%), 21 open. The related
  reserve release is a mechanics follow-up; WS-F02 remains open.
  See the [report](docs/reviews/harvest-legions-2026-11-04.md).

## Unreleased — Physical Besiege target choice, 4 November 2026

- Ask the Roman at the pre-Loss Besiege step to choose an exact Citadel/Ally
  Tribe or German Settlement in Ariovistus, or decline the optional removal.
- Preserve unselected allegiances, Citadel halving, Ballistae and legacy
  non-player defaults; add terminal and durable pending-response support.
- Validate both offered and live targets; preserve save/resume and replay.
- Close BATTLE-BESIEGE-CHOICE: 28/50 original findings closed (56%), 22 open.
  See the [report](docs/reviews/besiege-choice-2026-11-04.md).

## Unreleased — March hide in place, 4 November 2026

- Accept explicit empty March routes as paid origin selections with whole-origin
  visibility handling and no movement, moving cohort or Harassment rolls.
- Offer a terminal stay choice, preserve missing-route legacy behavior and
  report successful selections in `stayed_origins`.
- Preserve Frost, Limited Command, free-action Region/destination constraints,
  once-per-origin costs and Scouted handling; allow an SA with a stay in Britannia.
- Close MARCH-HIDE-IN-PLACE: 27/50 original findings closed (54%), 23 open.
  See the [report](docs/reviews/march-stay-2026-11-04.md).

## Unreleased — Player Build Region order, 4 November 2026

- Preserve selected Region order in both Build collectors and execution using
  `build_plan.region_order`; resolve a Fort before the optional Tribe operation
  in each Region. Preserve legacy controller and §8.8.1 NP passes.
- Validate exact Region coverage, uniqueness and per-Region operation limits
  before an accompanying human Command; retain timing category indices.
- Keep invalid turn/Event plans pending across rollback and save/resume.
- Close CMD-BUILD-ORDER: 26/50 original findings closed (52%), 24 open.
  See the [report](docs/reviews/build-order-2026-11-04.md).

## Unreleased — Ordinary Seize Tribe identity, 4 November 2026

- Extend exact `disperse_tribes` maps to ordinary Seize; preserve explicit
  Forage-only, ordered Regions and interrupted Command portions.
- Offer all legal Tribes with scarce markers, reserve the shared budget on
  detached planning boards, and reject duplicate/malformed physical identities.
- Migrate the synthetic human-policy builder, Arduenna witness and human
  test fixtures to the exact contract; native NPC selection remains supported.
- Close CMD-SEIZE-TRIBES: 25/50 original findings closed (50%), 25 open.
  See the [report](docs/reviews/seize-tribes-2026-11-04.md).

## Unreleased — Rampage quantity, 4 November 2026

- Let humans choose exact positive `count` per Rampage Region, including more
  than two, with both terminal planners and durable quantity validation.
- Reject overlarge quantities before victim reactions instead of clamping;
  preserve accepted actor counts and victim context through save/resume.
- Apply §8.5.1's all-able-Warbands NPC default, retaining its before-Battle
  last-enemy-piece restriction. Reject duplicate Region entries per §4.1.
- Close CMD-RAMPAGE-COUNT: 24/50 original findings closed (48%), 26 open.
  Full victim choices and Circumvallation mechanics remain open. See the
  [report](docs/reviews/rampage-quantity-2026-11-04.md).

## Unreleased — Intimidate Allied Tribe identity, 4 November 2026

- Carry exact `target_tribe` choices through ordinary, intrinsic Raid and
  A45-granted Intimidate, including terminal menus and durable save/resume.
- Validate/reserve the whole Region's removals before any Reveal or marker;
  reject Citadels, duplicate discs and malformed or missing human identities.
- Preserve unnamed bot/default selections and legacy low-level pairs.
- Close CMD-INTIMIDATE-TRIBE: 23/50 original findings closed (46%), 27 open.
  Circumvallation's remaining mechanics are still open separately. See the
  [report](docs/reviews/intimidate-tribes-2026-11-04.md).

## Unreleased — Circumvallation no-Romans cleanup, 4 November 2026

- Remove the marker after successful physical removal or movement leaves no
  Roman piece in its Region, including casualties and March departures.
- Preserve it while any Roman piece remains; other Region markers are untouched.
- Keep Interlude's final marker deletion safe if piece removal already cleared
  it. Exact marked-only Interlude removal remains a known defect.
- This partially repairs separate CV-PERSISTENCE; original progress remains
  22/50 (44%). See the [report](docs/reviews/circumvallation-no-romans-2026-11-04.md).

## Unreleased — Circumvallation choices, 4 November 2026

- Restore numeric4's Roman-owned optional benefit, exact adjacent groups and
  destination, including cooperation, physical formation and save/resume.
- Move marker placement after the accepted March and validate legacy targets.
- Close original BE-01: 22/50 findings closed (44%), 28 open. Record separate
  high-priority CV-PERSISTENCE defects for continuing marker mechanics and
  Interlude cleanup. See the [choice repair](docs/reviews/circumvallation-2026-11-04.md)
  and [persistent-effect follow-up](docs/reviews/circumvallation-persistence-followup-2026-11-04.md).

## Unreleased — Germanic Chieftains choices, 4 November 2026

- Restore numeric17 unshaded's Roman-owned choice of up to three original
  German moving groups and the single following Ambush Region/defender.
- Preserve ownership when another faction executes the Event, exact physical
  cohorts, normal Ambush rules, durable pending decisions and save/resume.
- Apply Roman card instructions to explicit bot delegation; preserve native
  NPC/raw deferral and the separate shaded Germans Phase.
  Partial BE-01 repair; progress remains 21/50 (42%). See the
  [Germanic Chieftains report](docs/reviews/germanic-chieftains-2026-11-04.md).

## Unreleased — German Allegiances guidance, 4 November 2026

- Restore numeric65's executor-owned German origins, quantities and routes,
  followed by order and target choices for every able Ambush Region.
- Preserve original counters, hide-only origins, normal Fort protection,
  Hidden superiority and legal zero-Loss Ambushes. Check defensive cooperation
  before combat rather than allowing Germans to switch to normal Battle.
- Support terminal inspection, pending decisions, rollback and save/resume.
  Partial BE-01 repair; progress remains 21/50 (42%). See the
  [German guidance report](docs/reviews/german-guidance-2026-11-04.md).

## Unreleased — Aduatuca March choices, 4 November 2026

- Give the human executor numeric58 shaded's Fort, German origins, exact
  quantities and visibility formation choices, including hide-only origins.
- Preserve the forced Roman Ambush, resident participants, printed Fort
  exception and separate Roman defender choices, with durable rollback/resume.
- Skip unshaded removal parameters in the shaded terminal flow.
  Partial BE-01 repair; progress remains 21/50 (42%). See the
  [Aduatuca report](docs/reviews/aduatuca-2026-11-04.md).

## Unreleased — Mons Cevenna March choices, 3 November 2026

- Restore human first-March origin, destination and exact mobile-piece choices
  on numeric 9, including origin visibility and separate Diviciacus consent.
- Keep the following free Command/SA in or from the destination; validate
  legacy routes and prevent unavailable movement from broadening the grant.
- Support terminal inspection, durable pending decisions and save/resume.
  This is a partial BE-01 repair; progress remains 21/50 (42%). See the
  [Mons Cevenna report](docs/reviews/mons-cevenna-2026-11-03.md).

## Unreleased — Planning-board inspection, 3 November 2026

- Fix `b`/`board` at Command and cooperation prompts to show the detached
  position used by those menus after preceding operations, including
  SA-first Build. Restore the outer inspection hook when the menu exits.
- Close FE-01; original audit progress is 21/50 closed (42%), 29 open.
  See the [repair report](docs/reviews/planning-board-inspection-2026-11-03.md).

## Unreleased — Camulogenus March choices, 3 November 2026

- Give Romans the optional whole-benefit decision and exact March choices
  on numeric 70, including when another faction executes the Event.
- Allow multiple original groups, a single named destination and at most
  four Legions in total. Preserve route limits, moving-piece visibility,
  physical ownership, separate cooperation agreements and the required
  following Battle.
- Resolve the separate Battle with resident Roman Forces even when the
  marching group is lost or removed before arrival.
- Support terminal inspection and durable pending responses, save/resume
  and replay. This repairs part of BE-01; the other grouped March grants
  remain open, so the original audit stays at 20/50 closed (40%). See the
  [Camulogenus report](docs/reviews/camulogenus-2026-11-03.md).

## Unreleased — Litaviccus targeting and forces, 3 November 2026

- Adopt provisional PR-12 for Litaviccus: predict the published Roman bot
  response or a human Roman's safer legal standing/Retreat choice. Maximize
  Legion Losses, retain Battle/Frost safeguards and use No Belgae if none
  qualify. Eligibility and execution share the same target planner.
- Include Aedui pieces throughout the actual Battle: Retreat forecasts,
  casualties and Reveal, retaining physical ownership, Tribe affiliation
  and native Leader identity. Protect City/Remi Allies across owners.
- Preserve human target freedom, physical board display and save/replay.
  Battle loss reports now distinguish requested Loss totals from actual
  removals/absorptions; forecasts use the executor's validated Ambush timing.
- This follow-up closes no additional original audit finding: 20/50 remain
  closed (40%), with 30 open. See the
  [Litaviccus report](docs/reviews/litaviccus-targeting-2026-11-03.md).

## Unreleased — Event Battle choices, 3 November 2026

- Restore human Region and defender selection for modified Battles on
  11/25/36/45/70, including Aquitani without friendly Forces. Preserve printed
  restrictions, separate Diviciacus consent, board/card information, pending
  responses, save/resume and replay.
- Limit revised Numidians to participating Auxilia during damage, reaction
  choices and Counterattack; keep other Roman counters physically present.
- Count Aedui forces once when they execute Litaviccus. Apply printed Event
  Loss modifiers when non-player defenders evaluate Retreat.
- Close BE-02: 20/50 original audit findings are closed (40%), with 30 open.
  The separate non-player Litaviccus target predictor remains open. See the
  [Event Battle report](docs/reviews/event-battle-choices-2026-11-03.md).

## Unreleased — ordinary Arverni Phase repairs, 3 November 2026

- Enforce one Rally placement category per Region, Arverni Control for a new
  Ally, and protected-Tribe restrictions.
- Require a secondary March's combined arriving groups to remove Aedui or
  Roman Control while preserving Arverni Control at their origins.
- Cap Raid participants per Region; reserve Hidden Warbands only for an
  actually possible damaging Ambush, including eligible Diviciacus sharing.
  Remove raided Resources from victims without crediting the untracked Arverni.
- Repair all five phase follow-ups and two related defects. These are outside
  the original audit, which remains 19/50 closed (38%). See the
  [phase report](docs/reviews/arverni-phase-2026-11-03.md) for source evidence,
  validation, outcome changes and compatibility limits.

## Unreleased — Gallic Event ownership and Arverni policies, 2 November 2026

- Restore beneficiary-owned choices on 35/46/67, Gallic Shouts' full/Limited
  Command order, Celtic Rites' original-executor eligibility, and the actual
  Remi owner's City/Citadel/Warband effect. Preserve card/board information,
  pending decisions, save/resume and replay.
- Implement owner-adopted PR-10 for automatic Arverni Event Commands and
  PR-11 for numeric Arduenna's Legion-Loss prediction. Both remain provisional
  and subject to official correction. Repair initial March cohorts, physical
  ownership/visibility bookkeeping and the Roman Retreat exposure check.
- Close BE-03: the original audit is 19/50 closed (38%). The final source
  passes 7,149 tests and the complete game matrix without changing the
  balance baseline. Five ordinary Arverni Phase defects remain separate
  follow-ups. See the [repair report](docs/reviews/gallic-event-grants-2026-11-02.md)
  for exact scope, evidence, outcome review and compatibility limits.

## Unreleased — Colony Event defaults, 2 November 2026

- Use runtime Colony geography in Savage Dictates and Cross Rhenus defaults,
  including Region grouping and continuation. This prevents a caught TypeError
  from silently rejecting a bot's chosen Event.
- Treat explicitly rejected bot Events as hard mixed-player fuzz findings.
  Preserve human invalid-plan checks and legal optional declines.
- Retain and compare per-game JSON in regular and scheduled fuzz CI, including
  failed runs. See the [repair report](docs/reviews/colony-event-defaults-2026-11-02.md).

## Unreleased — named-faction Event choices, 2 November 2026

- Route optional effects on 2/18/23 unshaded and 26 shaded to their named
  Roman or Arverni owner, including when another faction plays the Event.
  Add explicit decline/default, exact targets, Legion source allocation,
  Gobannitio's separate Ally changes/Rally, and durable saved-session replay.
- Repair Card2's missing non-player Legion placements. Remove Scouted Warbands
  and an unprotected German Successor under expansion A18's all-pieces effect;
  preserve the named Ariovistus exclusion and Roman decision ownership.
- Preserve original-executor removal authority, independent Arverni Spring
  entry and existing follow-on timing. Reject malformed or unconsumed timing
  fields and rebuild Legion source choices after late reclamation.
- Close BE-04. See the [repair report](docs/reviews/named-event-effects-2026-11-02.md)
  for source readings, validation, compatibility and remaining scope.

## Unreleased — Event limits and German Allegiances, 3 November 2026

- Enforce printed counts, areas, alternatives and targets for base cards
  40, 41, 42 and unshaded 51, and expansion A29/A30/A43/A45 unshaded and
  A36 shaded. Preserve valid partial execution and replacement removal
  when incoming pieces are unavailable or would violate stacking.
- Restore beneficiary-owned A29 placements and German-owned A36 choices,
  with current-board menus and durable pending/save/replay support.
- Give Gallic executors their own Warbands under shaded German Allegiances;
  Romans receive Auxilia. Let humans choose exact physical targets and
  ordered removal or replacement within executor Control.
- Reject explicitly malformed human Event parameter objects. Keep invalid
  Events pending without spending eligibility; preserve legal ineffective
  Events. Update NPC derivation and applicability for the repaired sides.
- Close BE-11, BE-12 and EXP-09. See the
  [repair report](docs/reviews/event-validation-2026-11-03.md) for revision-specific
  validation, compatibility and remaining scope.

## Unreleased — Gallia Togata and Dread, 2 November 2026

- Let A5's executor choose affected-owner order, then each owner allocate
  every prohibited Cisalpina piece to legal Home Regions or removal. Preserve
  visibility, exact Tribe metadata, Settlement limits and Diviciacus removal.
- Apply shaded A22's extra Warband to ordinary and Raid Intimidate, A45,
  bot planning and both human interfaces. Three actual Baggage Trains Raiders
  can provide three removals with Dread; a fresh bonus Warband is explicit
  and respects the Event's physical cohort.
- Make unshaded A22's Intimidated-marker immunity apply to Roman Recruit,
  with correct Capability-side switching and removal behavior.
- Preserve pending choices, board inspection, invalid-response rollback and
  save/replay. Close EXP-07 and EXP-10; see the
  [repair report](docs/reviews/expansion-effects-2026-11-02.md) for evidence
  and remaining scope.

## Unreleased — human expansion Event grants, 2 November 2026

- Add human first/second Battle choices for A21/A57 and executor-owned whole
  Roman March choices for shaded A19.
- Restore A67 beneficiary selection, optional acceptance, scoped March and
  subsequent Command choices, then Hide. Moving groups retain their original
  physical pieces through split routes, losses and voluntary removals.
- Let the A29/A69 executor choose Raid and Ambush targets. Removed placed
  pieces cannot be replaced by residents; A69 cannot become an ordinary
  Battle merely because a later removal invalidated Ambush.
- Give Romans the optional A20/A58 benefit regardless of Event executor,
  with separate current-board Battle/Seize choices and exact Dispersal targets.
  Suppress enemy Rally for both cards and Harassment for A58.
- Preserve mandatory human choices after refused loans, refresh retry targets,
  and validate explicit defaults without silently skipping legal actions.
  Add terminal board inspection and durable pending/save/replay regressions.
- Close EXP-01 through EXP-06; see the
  [repair report](docs/reviews/human-event-grants-2026-11-02.md) for validation,
  compatibility limits and outcome changes.

## Unreleased — Scouted Event removals, 2 November 2026

- Include Scouted Warbands in the mandatory unshaded removals for A25, A26,
  A30 and A56, closing audit finding EXP-12. Preserve their existing faction,
  Leader and Region scope. See the [repair report](docs/reviews/scouted-events-2026-11-02.md).

## Unreleased — First small audit repairs, 29 October 2026

- Enforce mandatory Battle casualty tiers and one Seize/Entreat selection per
  Region, including human plans and applicable free grants.
- Keep malformed Supply replacements at the same pending human decision.
- Reject game-run Arverni Resource gifts in Ariovistus and filter transfer
  menus using the shared rule; preserve the raw executor's error reporting.
- Start new sole-human-Belgae Great Revolt games with Ambiorix and retain
  correct setup in replay without rewriting historical saves.
- Close five of the audit's 50 grouped findings. See the
  [repair report](docs/reviews/cheap-fixes-2026-10-29.md) for validation and limits.

## Unreleased — Human-choice audit, 29 October 2026

- Record 50 grouped open findings and a 490-row source-derived inventory
  spanning cards, actions, seasonal decisions and both human interfaces.
- Preserve 11 independently rerun witness scripts, full 6,109-test evidence
  and unchanged-source hashes; distinguish executed cases from static review.
- Publish six ordered repair batches and update current guides with known
  limits. No engine, protected rules or balance-baseline changes in this pass.
  See the [audit report](docs/reviews/human-choice-audit-2026-10-29.md).

## Unreleased — Action timing, 29 October 2026

- Offer voluntary own-piece removal and Citadel downgrades during legal
  Command/Event procedures, with exact physical ownership and participating
  groups retained.
- Offer unlocked boxed Vercingetorix entry within actions and later Winter;
  recheck future legality while preserving completed rolls and effects.
- Permit a Special Ability between Vercingetorix's two Rally options in one
  Region without repeating its cost or bonuses.
- Update planning menus, current-card/change displays, board inspection,
  pending validation, save/resume and historical replay compatibility.
- Correct repeat Scout movement, Scouted Rampage targets, and overlapping
  Diviciacus/Event-force bookkeeping. Execute earned Seize Rallies and
  Surus replacements/Commands, and correct ordinary non-player casualty
  visibility and Roman March destination priorities. See the
  [action-timing report](docs/reviews/action-timing-2026-10-29.md) for the full
  related-fix list and exact validation evidence.

## Unreleased — Rules adoption and Trade choice, 29 October 2026

- Adopt PR-07 through PR-09 provisionally: action-wide Aedui Supply dice,
  ordinary placement prerequisites before bonuses, and randomized tied
  A20 casualty origins. Preserve the earlier six rulings.
- Apply the printed O38 Capability label to both sides, including bot
  final-year decisions and active unshaded Capability bookkeeping.
- Keep A20 losses within participating Warbands, return exact survivors,
  and restore the complete board and RNG if resolution is interrupted.
- Expose the human choice of one Trade Region under shaded River Commerce.
- Allow reconsideration after an actual non-player Aedui Supply refusal,
  preserving prior effects, the fixed answer, Event limits and durable replay.
- Keep deferred Trade choices inside Event-granted Region limits and use
  actual possible income in human planning previews.

## Unreleased — Recruit and Rally choices, 29 October 2026

- Add exact human troop quantities, ordered Vercingetorix Rally options,
  German Enlist quantities and Belgic Citadel choices.
- Preserve physical Diviciacus allocations before later placement menus
  reserve shared pools. Validate ordered plans, Limited Command scope,
  malformed quantities, saved pending answers and rollback.
- Correct Aquitani ownership and missing Rally bonuses, Nervii's placement
  additions, and compulsory Gallia Togata recruitment.
- Enforce one Recruit option per Region in Roman bot plans and forecast the
  preceding Build/Scout before testing Recruit's threshold. Build placements
  remain separate. Allow the printed Build payment from six Resources,
  then stop further spending below six. Correct dynamic Colony and Razed
  Tribe eligibility.
- Confirm Supply Line permissions before bot Recruit effects and replan
  after refusal, including scoped Event grants and Frumentum's used-SA limit.
  Apply printed non-player Supply policies in the shared resolver as well.
- Check Trade's Supply Lines for the acting Aedui. Bind the Roman
  declaration to both routing and income, and exclude Dispersed and Razed
  Tribes from Subdued income. Reuse actual NPC Supply replies between
  Winter Quarters planning and validation.
- Make the experimental Roman human policy check uncertain Recruit Supply
  refusal before choosing a plan. Retain affordable choices and public
  human options without inspecting future dice; advance study policy
  provenance to version 3.
- Preserve archived pending-decision identities across an absent/empty
  Supply-cache difference while retaining strict checks for actual changes.
- Repair overlapping A28/Diviciacus physical forces and the non-player
  Aedui refusal to lend against themselves, including Roman defense.
  Preserve binding loans, Scouted markers on Battle survivors, and A20's
  return of projected surviving Warbands to their original Regions.
- Record unresolved bonus-before-ordinary timing, A20 casualty origins
  and Aedui Supply die scope separately from the six adopted provisional
  rulings.

## Unreleased — Spring Leader placement, 28 October 2026

- Expose human Successor destinations and apply non-player placement
  priorities to every eligible faction, with seeded ties among legal Regions.
- Allow the Arverni to defer Vercingetorix's Spring-box arrival, preserve the
  unlock through saves, and offer later placement at action boundaries.
  Arbitrary interruption within a resolving Command/Event remains open.
- Correct the Gallic War Interlude's named Ambiorix placement and human
  choices among equally preferred named-Leader destinations.
- Preserve pending choices, board/card/change display, rollback and replay.

## Unreleased — Event integrity repairs, 27 October 2026

- Enforce A70 Nervii's Roman/Aedui non-player condition in both expansion
  scenarios: decline when Belgae are non-player, including earlier years.
- Add The Province's printed Auxilia/Resources menu and Ambacti's post-roll,
  exact-piece removal decisions, including durable save/resume and replay.
  Correct related Senate, Fort-prediction and non-player instruction defects.
- Restore Chieftains' Council's executor selections, private card look and
  beneficiary choices in scenario-correct order. Keep its Eligible benefit
  through cleanup and its private card information out of public output.
- Display Germans in the Arverni initiative and NP-symbol slot on retained
  base cards in Ariovistus, including private Council card information.
- Enforce the Aedui's conditional Event exclusions from both instruction
  tables: flagged Events are declined when Romans are human or their
  scenario-specific victory score exceeds 12. This includes the Ambacti
  condition found while investigating the initial outcome drift.
- Require a valid Winter Uprising marker location before recording its
  delayed effect. Non-player placement follows Belgica/Germania instructions
  even when the acting faction has no pieces on the map.
- Add Winter Uprising's held-card timing and physical placement decisions,
  including forced Interlude activation, correct decision ownership,
  non-player placement priorities, mandatory follow-on Command, and durable
  pause/save/replay. Preserve unknown ownership explicitly in legacy saves.
- Derive last-year non-player restrictions from the live Winter cards,
  including the Gallic War's continuation through Interlude, instead of
  relying on an unset flag or inconsistent separate checks.
- Preserve legal German Rally + Settle plans when an Event limits Regions,
  including actions where only the Settlement is placed.
- Reject numeric or malformed free-action defaults/declines while leaving
  durable decisions pending. The
  [second-batch report](docs/reviews/second-batch-2026-10-27.md) records the
  validation and remaining human-play work.
- Reject malformed piece quantities before changing inventory, including
  converted or borrowed forces; rejected placements, removals and movement
  preserve the board and pools. Runtime checks now reject invalid count
  domains even when their totals appear to conserve pieces.
- Validate Boii's complete placement/replacement plan against its printed
  limits, native piece types and geographic scope. Expose legal human choices
  and supply the missing non-player plans; execute legal pool shortages
  partially without allowing excess placements.
- Preserve Event eligibility through card cleanup, including the executor
  exception in shaded Marcus Antonius, Clodius Pulcher and Frumentum.
- Register both sides of Wailing Women and Nervii as capabilities, clear
  removed/replaced effects, and interpret earlier modifier-only saves.
- Repair Parley's legal meeting choices, movement, non-player conditions and
  next-card ineligibility, including Scouted Warbands and Gallia Togata's
  Cisalpina stacking restriction.
- Correct Diviciacus's physical-piece ledger when placement explicitly uses
  the default visibility. Distinguish Ariovistus from a Successor when
  applying Wailing Women's post-Counterattack removals.
- Apply shaded German Phalanx's cancellation to Wailing Women's harmful
  Battle effects; removing or replacing the suppressing capability restores
  the underlying effects.

Validation and remaining comparison findings are recorded in the
[first-batch repair report](docs/reviews/first-batch-2026-10-27.md).

## Provisional rulings adopted 24 October 2026

- Adopt [PR-01 through PR-06](docs/provisional-rulings.md) as explicit project
  policies, each subject to possible later correction if an authoritative
  source is found. Protected source documents remain unchanged.
- Permit A28 lending by both non-player Aedui and Belgae only where the
  executor contributes its own participating pieces; preserve human consent
  and the Roman refusal rule.
- Resolve Ariovistus Harassment in printed faction order with Arverni last.
  During Winter use the last actually played non-Winter card, recovered from
  saved history; document a deterministic fallback for missing history.
- Retain the existing A30 ordinary Belgic handling, Roman ownership of unused
  A53 funding, and post-Interlude dormancy of German-owned A63, now supported
  by the owner's provisional rulings.
- Preserve earlier validation measurements as evidence for their original
  revisions; they do not measure these later rulings.

## 0.1.0 — initial local distribution

- Implement Diviciacus cooperation for Commands, permitted Special Activities,
  and defense, preserving physical ownership through movement and losses.
  Human consent and exact physical-piece choices support pause, save and replay;
  non-player planning accounts for cooperation and replans after refusal.
- Preserve a March cohort’s physical-owner context when only native pieces
  continue after formation, drop-offs or borrowed-piece losses. Transit
  residents cannot be substituted into that cohort.
- Apply Event cooperation to the actual permitted forces. Camulogenus now
  moves its selected cohort to one destination within its printed range;
  stationary pieces are not revealed as if they had marched.
- Add the separate optional Diviciacus setup in original scenarios, including
  O38, saved configuration and the printed non-player restrictions.
- Correct Suborn's complete piece choices, cumulative validation, Vergobret's
  fourth piece and second Ally, and non-player Ally priorities. Track both
  Vergobret sides as capabilities, including compatibility with earlier saves.
- Offer active capabilities in Shifting Loyalties, including legacy
  modifier-only Vergobret saves, and use the same capability list in board
  and change displays.
- Make self-play experiments classify their human seat correctly, support
  German policies and Interlude handover, reject invalid outcomes and resume
  only compatible studies. Historical strategy results retain their caveats.
- Extend validation tools and CI to explicit card editions and held-out seeds.
  Mixed-seat determinism compares the complete state, RNG and returned results;
  unfinished games and replay-only failures can no longer report success.
- Reject prohibited Roman Quarters hosts before asking for consent. Preserve
  accepted Supply-Line agreements for their action and avoid asking again
  between Recruit's budget check and execution.
- Add an installable `falling-sky-bot` package and `fs-bot` launch command,
  while retaining `python -m fs_bot` and standard-library-only gameplay.
- Bundle unchanged reference inputs at build time so installed games retain
  full card text and the rules-citation utility retains its source chapters.
  Include the balance baseline used by the installed validation tool.
- Record the writing engine's version and source digest in new saves, keeping
  save format 1 and support for older valid files without this metadata.
- Preserve compatibility fixtures written by the `8ef88e2` engine, including
  pending human decisions and actual pre/post-Interlude game states. These
  establish the tested continuations, not universal replay compatibility.
- Fix circular imports that could prevent direct setup/Battle API use in a
  fresh Python process. Preserve public convenience imports through lazy
  exports.
- Make Trade's earnings breakdown deterministic across Python hash seeds.
- Preserve source and fixture identities across Windows checkouts: Python
  files use LF, while supplied references and archived compatibility JSON
  bypass automatic line-ending conversion. This repairs the remote fixture
  provenance check without changing its recorded expected hash.
- Add a build/install/play workflow for Linux, Windows, and macOS. It builds
  the wheel from the source archive and exercises it in an isolated environment.

See [release maintenance](RELEASES.md) for installation, build checks, and
the save metadata contract. See [current status](docs/current-status.md) for
gameplay changes and unresolved source questions.
