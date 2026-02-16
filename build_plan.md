BUILD_PLAN.md — Falling Sky Bot Engine
What This Project Is
An automation engine for the non-player bot flowcharts in Falling Sky: The Gallic Revolt Against Caesar (GMT Games, COIN Series Vol. VI, 2nd Edition) and its Ariovistus expansion. It will handle 0–4 bot-controlled factions via an interactive CLI. The goal is faithful implementation of the published flowcharts and rules — not a variation, not a reinterpretation, not a "simplified" version.
Language: Python 3.10+

Lessons From the Liberty or Death Project
The LOD project (same game series, same architecture goals) went through ~9 audit sessions and ~800+ tests to reach compliance. Its audit report is a catalog of avoidable mistakes. These are the patterns we must not repeat:
1. String Literal Drift Was the #1 Systematic Bug
ChatGPT invented piece tags like "Continental", "Militia", "Tory", "fort" instead of using canonical constants. Every file in the codebase had violations. Fix: rules_consts.py is created first, before any game logic. Every string that refers to a game concept must be imported from it. Claude Code should enforce this from the first line of code.
2. Bot Event Evaluation Used Text Matching — and It Was Fragile
The "should the bot play this event?" nodes (B2, P2, F2, I2) used keyword matching against card text. This produced false positives and false negatives across dozens of cards. Fix: Build a per-card lookup table from the start. Each card gets explicit boolean flags (e.g., shifts_support_roman, places_gallic_allies, inflicts_roman_casualties). No text matching.
3. Direct Dictionary Manipulation of Piece Counts Was Pervasive
Code like sp["British_Regular"] -= 1 bypassed cap enforcement, control recalculation, and Available pool tracking. Fix: All piece operations go through helper functions from day 1. No direct dict access for piece counts, ever.
4. Battle Modifiers Were Systematically Wrong
Wrong sides getting bonuses, missing Fort modifiers, Underground pieces counted in force levels, leaders applied to wrong calculations. Battle was the single most bug-dense module. Fix: Build battle as a standalone, exhaustively tested module early. Every modifier from the battle procedure flowchart and §3.2.4/§3.3.4/§3.4.4 gets its own test.
5. Winter/Year-End Was Treated as an Afterthought
Supply, Redeployment, Desertion, Senate — all had bugs because they were built last and tested least. Fix: Winter is Phase 4, built right after the core game loop, not bolted on at the end.
6. Determinism Wasn't Designed In
random.random() vs state["rng"] was a recurring bug across all four bots. Fix: All randomness goes through state["rng"] (a seeded random.Random instance) from the very first die roll.
7. Queued vs. Immediate Free Operations Caused Confusion
Some cards queue free ops that should execute immediately. The architecture didn't handle this cleanly. Fix: Resolve this upfront: free operations from Events execute immediately during Event resolution. The engine drains any queued ops after each Event handler returns.
8. Card Handler Bugs Were Systematic
Wrong destinations ("to Fallen" vs "to Available" vs "to track"), inverted shaded/unshaded, missing conditions, wrong piece types. 31 cards were wrong in the first audit pass. Fix: Build card handlers methodically against the Card Reference, one at a time, with a test for each that verifies the exact effect against the reference text. Never batch-implement cards.
9. Bot Event Instructions Had Conditional Directives That Were Ignored
Cards marked "force" in the event instruction tables actually had conditions like "if no eligible enemy, choose Command & SA instead." All were implemented as unconditional. Fix: Parse the bot event instruction files carefully. Every conditional gets a proper force_if_X directive with a game-state check.
10. Ariovistus Must Be Designed In, Not Bolted On
The LOD project didn't have an expansion, but the pattern is clear: if the expansion changes fundamental rules (and Ariovistus does — Germans become a full player, Arverni become game-run, Settlements are added, victory conditions change), the data model must accommodate it from day 1. Fix: Every data structure includes an expansion or scenario flag. Germanic Settlements, Diviciacus, the Arverni Phase, Alps crossing — all have hooks in the schema even if the logic comes later.
11. Base Game and Expansion Must Not Bleed Into Each Other
"Design for Ariovistus" is only half the problem. The other half is preventing Ariovistus content from leaking into base game scenarios and vice versa. These are two different rule sets sharing a common core, and the differences are load-bearing:

Pieces that don't exist in a scenario (Settlements in base, Vercingetorix in Ariovistus) must be impossible to place or reference.
Map regions that aren't playable in a scenario (Britannia in Ariovistus, Cisalpina in base without Gallia Togata) must be gated out of March, Rally, and all other region-targeting logic.
Faction roles change between scenarios: Germans go from NP procedure (§6.2) to full player/bot; Arverni go from player/bot to game-run NP. The engine must never give a German bot a Sequence of Play turn in base game or an Arverni bot a turn in Ariovistus.
Victory formulas differ: Arverni don't track victory in Ariovistus; Germanic victory only exists in Ariovistus; Roman/Aedui formulas change.
Bot flowcharts and event instructions are scenario-specific files. The German bot flowchart is Ariovistus-only. The Arverni bot is base-only. A8 modifications to other bots fire only in Ariovistus.
Rule details change: Senate max Legions, Arverni Home Rally marker, Intimidated markers, Alps crossing.

Fix: state["scenario"] gates every scenario-dependent behavior. Available Forces pools are built per-scenario. Map playability is per-scenario. Faction dispatch is per-scenario. Victory is per-scenario. Every scenario branch must be tested in both directions — confirm Ariovistus content is active when it should be AND confirm it's absent when it shouldn't be.

Scope: What the Bots Must Do
Base Game (2nd Edition)
Four non-player flowcharts: Roman (§8.8), Arverni (§8.5), Aedui (§8.6), Belgae (§8.7). Each flowchart decides Event vs. Command, selects Commands and Special Activities, picks targets, and handles retreat/battle decisions. Germans are game-run per §6.2 (not a bot flowchart — a deterministic procedure).
Ariovistus Expansion
Germans become a full player faction with their own bot flowchart. Arverni become game-run via the Arverni Phase (A6.2). The remaining three factions (Roman, Aedui, Belgae) use their base game flowcharts with modifications from Chapter A8. Card deck changes (72 Ariovistus cards replace some/all base cards). Victory conditions change (A7.2). New pieces (Settlements, Diviciacus). New map rules (Cisalpina always playable, Alps crossing, Britannia unplayable).

Source of Truth Hierarchy
These documents are read-only. All code must conform to them.
Tier 1: rules_consts.py — Canonical Labels
Every string label for factions, pieces, markers, leaders, regions, tribes, and space IDs used anywhere in the codebase must come from this file.
Tier 2: Card Reference / A Card Reference — Card Behavior
The authoritative definition of every card's unshaded and shaded effects. Card handler implementations must match these files exactly.
Tier 3: Reference Documents/ — Everything Else
All files in Reference Documents and Reference Documents/Ariovistus are source-of-truth materials. Bot flowcharts, rules chapters, scenario setups, map transcription, available forces, event instructions, battle procedure — all authoritative.
If it's not in the Reference Documents, it doesn't exist.

Build Phases
Phase 0: Foundation (rules_consts.py + CLAUDE.md)
Goal: Establish the canonical vocabulary and project rules before any game logic exists.
Deliverables:

fs_bot/rules_consts.py — All constants extracted from Reference Documents:

Faction identifiers (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS)
Piece tags for every piece type, for every faction, including Ariovistus additions (Settlements, Diviciacus)
Region and tribe names (from Map Transcription)
Support/control levels
Senate track positions (Adulation, Firm, Uproar — and their normal/flipped states per §6.5.1)
Marker types (Devastation, Circumvallation, Colony, Gallia Togata, Frost, At War, Scouted, capabilities)
Piece caps (from available_forces.txt and available_forces_ariovistus.txt)
Resource caps (§5.0: max 45)
Winter card IDs
Leader identifiers and succession chains
Command and Special Activity names
Anything else that is a game label


CLAUDE.md — Project rules document (adapted from LOD's CLAUDE.md for Falling Sky specifics)
QUESTIONS.md — Empty, ready for ambiguities

Key principle: This file will be large. That's fine. It's cheaper to over-define constants than to chase string literal bugs across 60 files later. Claude Code decides the exact organization, but everything must be traceable to a Reference Document.

Phase 1: Map, State, and Piece Infrastructure
Goal: A game state that can be set up from any scenario, queried, and modified through safe helper functions.
Deliverables:

Map data module — Parse Map Transcription into a data structure with regions, tribes, adjacency (including Rhenus and coastal restrictions), control values, stacking restrictions (aedui-only, arverni-only, germanic-only), and Ariovistus modifications (Cisalpina playable, Britannia unplayable, Nori tribe).
Piece operations module — place_piece(), remove_piece(), move_piece(), flip_piece() (Hidden/Revealed/Scouted). All enforce caps from available_forces. All update Available pools. No direct dict access.
Control module — Calculate control per region per §1.6. Must handle the nuances: Allies count, Citadels count, Forts count for Romans, stacking restrictions affect who can be present.
State schema — The master game state dictionary. Includes: spaces (regions with pieces), available pools, resources, Senate track, Legions track (on track, Fallen, removed-by-Event), victory markers, eligibility cylinders, current/upcoming card, capabilities in effect, scenario flags, rng (seeded Random instance), Ariovistus-specific state (Settlements, Diviciacus location, Arverni At War marker, etc.).
Scenario isolation — The state schema must carry state["scenario"] identifying which scenario is active. All scenario-dependent systems must consult this:

The Available Forces pool builder must load from available_forces.txt or available_forces_ariovistus.txt based on scenario, producing a pool that physically cannot contain pieces that don't exist in that scenario (no Settlements in base, no Vercingetorix in Ariovistus, no extra 15 Germanic Warbands in base).
The map builder must mark Britannia as unplayable for Ariovistus scenarios and Cisalpina as unplayable for base scenarios (absent Gallia Togata). Swap Catuvellauni for Nori in Ariovistus. Region-targeting logic (March, Rally, etc.) must check playability.
Faction participation must be gated: in base scenarios, Germans are NP-only (§6.2) and all four Roman/Gallic factions are in the Sequence of Play. In Ariovistus, Germans join the Sequence of Play and Arverni are removed from it (game-run via A6.2).


Scenario setup module — Load any of the 5 scenarios (3 base + 2 Ariovistus) from the scenario reference files. Place all pieces, set all markers, build the deck.
Tests — Map adjacency tests (every adjacency pair from Map Transcription). Piece operation tests (cap enforcement, Available pool integrity). Control calculation tests. Scenario setup tests (piece counts match Reference Documents). Scenario isolation tests: confirm that base game setup produces a state with no Settlements/Diviciacus/extra Warbands/Nori, and that Ariovistus setup produces a state with no Vercingetorix/Catuvellauni/playable Britannia.

Design notes for Claude Code:

The map is 17 regions with 30 tribes (base) / 30 tribes (Ariovistus, swap Catuvellauni for Nori). Regions have control values. Tribes can be Allied to a faction, have Citadels, be Subdued or Dispersed.
Provincia has a permanent Fort. Cisalpina is special (not playable in base unless Gallia Togata; always playable in Ariovistus).
Germania regions have Suebi tribes that don't count for Belgic CV (§7.2 design note).
Ariovistus Settlements are a new piece type limited to 1 per region (A1.4.2).
The Legions track is NOT part of Available Forces — it's a separate track with positions for Senate Phase placement (§6.5.2).


Phase 2: Cards and Deck
Goal: All ~72 base Event cards and ~72 Ariovistus Event cards implemented with correct effects, plus Winter cards.
Deliverables:

Card data module — Metadata for every card: number, title, faction order, non-player instruction symbols (Carnyx/Laurels/Swords per card per faction), capability flag, dual-use flag.
Card effects module(s) — One handler per card implementing both unshaded and shaded effects. Built against the Card Reference, one card at a time.
Event evaluation table — Per-card boolean flags for bot event decision nodes (R3/Ar3/Ae3/Be3). Flags like shifts_support_roman, places_gallic_allies, inflicts_roman_casualties, places_legions, removes_citadel, etc. Built from Card Reference text, not inferred.
Bot event instruction table — Per-card per-faction directives from the *_bot_event_instructions.txt files (base game) and *_bot_event_instructions_ariovistus.txt files (Ariovistus). Every "No [Faction]" → Swords. Every "Auto 1-4" → Carnyx. Every conditional → force_if_X with game-state check. Must load the correct table per scenario — the instruction symbols differ between base and Ariovistus for many cards.
Deck builder — Shuffle and stack per Setup instructions and scenario-specific deck composition. Handle Ariovistus card replacements. Must only include cards that belong to the active scenario's deck.
Capability tracker — Long-duration Event effects (§5.3). Track which capabilities are in play, handle "last year" non-player refusal (§8.1.1).
Tests — Every card handler tested against Card Reference text. Event evaluation flags spot-checked. Deck composition verified per scenario.

Design notes for Claude Code:

Falling Sky has ~72 base Event cards + 5 Winter cards. Ariovistus has ~72 replacement Event cards (some shared, some new). The exact card list comes from the Card Reference and A Card Reference files.
Cards have a faction order shown at the top (e.g., "Ro Ar Ae Be") and non-player symbols after each faction abbreviation.
Capabilities persist until removed or game end. Some are "Momentum" capabilities (removed at Winter). Track both types.
Card effects frequently reference other rules (free Commands, free Special Abilities, "follow normal Rally procedure"). The handlers must call the actual Command/SA modules, not reimplement the logic.


Phase 3: Commands, Special Activities, and Battle
Goal: All Commands and Special Activities fully implemented and tested.
Deliverables:

Commands:

March (§3.2.2, §3.3.2, §3.4.2) — movement with Rhenus restrictions, escort rules, Germanic march rules, Frost restriction
Battle (§3.2.4, §3.3.4, §3.4.4) — the full battle procedure per the flowchart: target selection, Retreat declaration, Attack (Losses calculation with all modifiers — Caesar x2 Legions, Ambiorix x1 Warbands, Fort/Citadel halving, Retreat halving, Leader bonus), Counterattack, Reveal, Retreat execution
Rally (§3.2.1, §3.3.1, §3.4.1) — Roman Recruit is a variant of Rally; Gallic Rally places Allies then Warbands; Germanic Rally per §6.2.1
Recruit (§3.2.1) — Roman-specific: Senate track determines Auxilia/Legion placement
Raid (§3.3.3, §3.4.3) — Gallic and Germanic; steal Resources
Seize (§3.2.3) — Roman-specific: remove Allies/Citadels, Disperse tribes
Besiege (§3.2.4 note, §4.2.3) — remove Citadel/Ally before Losses


Special Activities (one per faction):

Roman: Build (§4.2.1), Scout (§4.2.2), Seize (if SA variant)
Arverni: Devastate (§4.3.1), Ambush (§4.3.3), Craft (if applicable)
Aedui: Suborn (§4.4.1), Trade (§4.4.2), Bribe (§4.4.3)
Belgae: Enlist (§4.5.1), Ambush (§4.5.3), Rampage (§4.5.2)
Germanic (Ariovistus): per expansion rules


Battle module — Standalone, exhaustively tested. Every modifier from the battle procedure flowchart. Caesar defending roll (4-6, or 5-6 vs Belgae Ambush). Ambush mechanics. Loss resolution (Leader/Legion/Fort/Citadel on 1-3 roll; Warband/Auxilia/Ally automatic). Retreat execution with "Hidden Warbands and Leader may stay" (Roman attack only, not Gallic per §3.3.4).
Tests — Battle modifier tests for every combination. Command tests for edge cases. SA tests.

Design notes for Claude Code:

Battle is the most complex single module. The battle_procedure_flowchart.txt is a reference for structuring the code, but the authoritative source is always the rules text (§3.2.4, §3.3.4, §3.4.4).
Commands can be "Limited" (one region, no SA) per §2.3.5. Non-players entitled to Limited Commands instead get full Command + SA (§8.1.2). The command modules must support both modes.
Harassment (§3.2.2-3, §3.3.2) is a mid-March interrupt where certain factions can force-battle marching groups. Bot harassment rules are in §8.4.2.
Germanic commands in the base game only happen during Germans Phase (§6.2) and via Events. In Ariovistus, Germans get their own turn in the Sequence of Play.


Phase 4: Game Engine, Winter, and Victory
Goal: A complete game loop that can run from setup to victory.
Deliverables:

Engine — Main game loop per Chapter 2: reveal cards, determine eligibility, resolve 1st/2nd Eligible actions, adjust eligibility, advance to next card. Handle Frost (§2.3.8). Handle Winter cards (§2.4) by triggering Winter Round.
Sequence of Play — Eligibility tracking, faction order per card, 1st/2nd Eligible options (§2.3.4), Pass mechanics (+1 Resource for Gallic, +2 for Roman per §2.3.3), Limited Command rules.
Winter Round (§6.0) — Five phases in order:

Victory Phase (§6.1)
Germans Phase (§6.2) — Rally, March, Raid, Battle per deterministic procedure
Senate Phase (§6.5) — Legions placement from track, Senate marker shift
Harvest Phase (§6.3-6.4) — Resources income, Supply
Spring Phase (§6.6) — Reset eligibility, flip pieces, remove markers


Victory module (§7.0) — All four faction victory conditions per §7.2. Final Winter margin calculation per §7.3. Tie-breaking per §7.1. Ariovistus victory conditions (A7.2). Must gate on scenario: Arverni victory is not tracked in Ariovistus; Germanic victory only exists in Ariovistus; Roman/Aedui formulas differ between base and Ariovistus.
Ariovistus engine modifications — Germans in Sequence of Play, Arverni Phase (A6.2), modified Winter, modified victory. Faction dispatch must gate on scenario: Germans get SoP turns only in Ariovistus; Arverni get SoP turns only in base game.
Tests — Victory calculation tests for every faction. Winter phase ordering tests. Eligibility flow tests. Frost enforcement tests. Scenario isolation tests: confirm base game victory module does not compute Germanic victory or subtract Settlements; confirm Ariovistus victory module does not compute Arverni victory; confirm the engine does not give Germans a SoP turn in base game or Arverni a SoP turn in Ariovistus.


Phase 5: Bot Flowcharts
Goal: All bot decision trees fully implemented and tested node-by-node.
Deliverables:

Base bot infrastructure — Shared logic for all bots: event vs. command decision (§8.1.1), event evaluation using the per-card lookup table, Limited Command upgrade (§8.1.2), Frost awareness (§8.4.4), random selection (§8.3.4), retreat rules (§8.4.3), Place and Remove priorities (§8.4.1), Harassment rules (§8.4.2).
Roman bot (§8.8) — Full flowchart implementation, every node, every priority, every tiebreaker.
Arverni bot (§8.5) — Full flowchart implementation.
Aedui bot (§8.6) — Full flowchart implementation.
Belgae bot (§8.7) — Full flowchart implementation.
German bot (Ariovistus, Chapter A8) — Full flowchart implementation. Ariovistus-only. Must never be instantiated or invoked in a base game scenario.
Bot event instruction handlers — Per-card per-faction conditional logic from all *_bot_event_instructions*.txt files. Must load the correct instruction set per scenario: base game bots use *_bot_event_instructions.txt, Ariovistus bots use *_bot_event_instructions_ariovistus.txt.
Non-player guidelines — All items from non_player_guidelines_summary.txt implemented: Frost restrictions, Dual Use defaults, Retreat rules, Place/Remove priorities, Harassment rules, Resource sharing rules.
Ariovistus bot modifications — Chapter A8 modifications to Roman, Aedui, and Belgae bots. Must only be active when scenario is Ariovistus. The Arverni bot must NOT be available in Ariovistus (Arverni are game-run via A6.2).
Tests — Every flowchart node exercised. Priority sorting verified. Tiebreakers verified with seeded RNG. Scenario isolation tests: confirm the German bot cannot be dispatched in base game; confirm the Arverni bot cannot be dispatched in Ariovistus; confirm A8 modifications are inactive in base game scenarios; confirm the correct event instruction file is loaded per scenario.

Design notes for Claude Code:

Each bot flowchart is a decision tree with 10-20+ nodes. The LOD project encoded these as method chains with if/else logic. Claude Code should decide the best representation — whether that's method chains, a table-driven interpreter, or something else. What matters is that every node is traceable to a line in the flowchart reference file.
The bot event evaluation nodes (R3, Ar3, Ae3, Be3 equivalents) are the hardest to get right. Use the per-card lookup table, not text matching.
Non-player guidelines from §8.1-8.4 apply to ALL bots. They should be in the base bot class, not duplicated per faction.
Ariovistus modifies the Roman, Aedui, and Belgae bots per Chapter A8. These modifications should be conditional (checked via scenario flag), not separate bot classes. The German bot is a separate class that only exists in Ariovistus. The Arverni bot class must refuse to instantiate in Ariovistus scenarios.


Phase 6: Interactive CLI
Goal: A human-playable interface supporting 0-4 human players alongside bots.
Deliverables:

CLI display — Current card, upcoming card, game state summary (region control, victory markers, resources, Senate, Legions track, capabilities).
Human player menus — Choose Event vs. Command, select Command type, pick regions/targets, execute Special Activities. Menu-driven, no free-text for game actions.
Bot/human dispatcher — Route each faction's turn to either bot logic or human menu based on setup.
Illegal move prevention — Validate all human choices before committing.
Ariovistus UI — Additional displays for Settlements, Diviciacus, modified victory conditions.


Phase 7: Ariovistus Completion and The Gallic War
Goal: Full Ariovistus expansion support, including the two-part Gallic War scenario.
Deliverables:

Ariovistus scenario setup — Both scenarios (Ariovistus, The Gallic War).
The Gallic War Interlude — The full mid-game reset procedure: force adjustments per faction, Britannia expedition, marker removal, Spring Phase, deck rebuild, faction swap (German → Arverni).
Ariovistus card effects — All replacement/new card handlers from A Card Reference.
Modified bot behaviors — Chapter A8 modifications to Roman, Aedui, Belgae bots.
Tests — Scenario setup verification, Interlude state transitions, modified victory calculations.


Critical Rules for Claude Code
Never Guess
If the Reference Documents are ambiguous, contradictory, or silent:

STOP working on that issue.
Document it in QUESTIONS.md with quotes from the reference, what's ambiguous, and what options exist.
Move on to other work.
Do NOT implement a "best guess."

Accuracy Over Simplicity
When faced with a choice between simpler code and faithful rules implementation, always choose faithful. The flowcharts are complex on purpose. Do not simplify tie-breaking logic, skip edge cases, or collapse decision branches.
No Outside References
Do NOT consult BoardGameGeek, other COIN games, other GMT titles, historical sources, or any repository other than this one. The Reference Documents folder is the complete universe of source material.
Ariovistus From Day 1
Every data structure must accommodate Ariovistus. If you're building a region, it needs a flag for "playable in Ariovistus but not base." If you're building a piece type enum, it needs Settlements. If you're building a faction list, it needs Germans-as-player. Don't build base-only structures that will need to be torn apart later.
Test Everything

Tests verify behavior against Reference Documents, not against assumed behavior.
When implementing a flowchart node, add a test that exercises it.
When fixing a bug, add a test that would have caught it.
Run the full test suite before every commit.

One Logical Change Per Commit
Commit messages reference what changed and why, traceable to a Reference Document section.

Complexity Comparison: Falling Sky vs. Liberty or Death
DimensionLiberty or DeathFalling SkyPlayer factions44 (base) + 1 expansion playerNon-player factionssame 4 as bots4 bots (base) + Germanic NP + German bot (Ariovistus) + Arverni NP (Ariovistus)Map spaces~30 colonies/cities/provinces17 regions, 30 tribes, complex adjacencyEvent cards~96 + 8 WQ + 5 BS~72 base + ~72 Ariovistus + 5 WinterBattle complexityModerate (few modifiers)High (Caesar x2, Ambiorix x1, Ambush, Fort/Citadel halving, Leader roll)ExpansionNoneAriovistus (fundamental rule changes)Winter/year-end phases75 (but Germans Phase is itself a multi-step procedure)Track mechanicsFNI (0-3)Senate (6+ positions, Firm/flip), Legions track (12 slots)Special markersPropaganda, Raid, BlockadeDevastation, Circumvallation, Colony, Gallia Togata, Scouted, At War, capabilitiesVictory conditions4 simple thresholds4 varied (Arverni has dual condition; Belgae uses Control Value)
Falling Sky is more complex in nearly every dimension. The Ariovistus expansion alone adds as much complexity as an entirely new game layered on top. Build accordingly — robust, well-tested, designed for the full scope from the start.
