CLAUDE.md — Falling Sky Bot Engine
Project Summary
This is an automation engine for the non-player bot flowcharts in Falling Sky: The Gallic Revolt Against Caesar (GMT Games, COIN Series Vol. VI, 2nd Edition) and its Ariovistus expansion. It handles 0–4 bot-controlled factions (Roman, Arverni, Aedui, Belgae, plus Germanic in Ariovistus) via an interactive CLI. The goal is faithful implementation of the published flowcharts — not a variation, not a reinterpretation, not a "simplified" version.
Language: Python 3.10+ (100%).
Tests: pytest.
No external game references. Do not consult BoardGameGeek, other COIN games, other GMT titles, or any historical sources outside the Reference Documents.

Source of Truth (Strict Hierarchy)
These are read-only. Never modify them. All other code must conform to them.
1. fs_bot/rules_consts.py — Canonical Labels
Every string label for factions, pieces, markers, leaders, regions, tribes, and space IDs used anywhere in the codebase must come from this file. If a label doesn't exist here, it is wrong.
If you encounter a string literal in the code that doesn't match a constant from rules_consts.py (e.g., "warband", "legion", "auxilia" used as a piece tag, "fort", "Romans" instead of the canonical form, etc.), it is a bug. Replace it with the correct constant.
2. Reference Documents/Card Reference and Reference Documents/Ariovistus/A Card Reference — Card Behavior
The authoritative definition of every card's unshaded and shaded effects. Card handler implementations must match these files exactly — same targets, same piece types, same destinations, same conditions.
3. Reference Documents/ — Everything Else
All files in the Reference Documents/ directory and its Ariovistus/ subdirectory are source-of-truth materials. Always check the full directory contents rather than relying solely on this list. Key files include but are not limited to:

*_bot_flowchart.txt — Non-player decision trees (one per faction, plus German bot in Ariovistus)
*_bot_event_instructions*.txt — Per-card non-player directives
Chapter 1 through Chapter 8 — Full rules (2nd Edition)
Chapter A1 through Chapter A8 — Ariovistus expansion rules
Key Terms Index, Ariovistus/A New Terms Index — Definitions
Map Transcription — Map topology
available_forces.txt, Ariovistus/available_forces_ariovistus.txt — Piece inventories
Scenario: *, A Scenario: * — Setup data (3 base + 2 Ariovistus)
Setup, Ariovistus/A Setup — Setup procedures
non_player_guidelines_summary.txt — NP rules summary
battle_procedure_flowchart.txt — Battle procedure play aid
Ariovistus/arverni_and_other_celts.txt — Arverni Phase and Celtic interactions

If a file exists in Reference Documents/ and is not listed above, it is still authoritative. Any file added to this directory in the future is automatically a source of truth.

Critical Rules
Never Guess
If the Reference Documents are ambiguous, contradictory, or silent on a question:

STOP working on that specific issue.
Document the question in QUESTIONS.md, including:

What you were trying to implement
What the reference says (quote it)
What's ambiguous or contradictory
What options you see


Move on to other work.
Do not implement a "best guess" — wait for the user to answer.

Rules-Accurate Over Simple
When faced with a choice between a simpler implementation and one that faithfully follows the rules, always choose rules-accurate. The flowcharts are complex on purpose. Do not simplify tie-breaking logic, do not skip edge cases, do not collapse decision branches that the flowchart keeps separate.
No Outside References

Do NOT consult BoardGameGeek.com
Do NOT reference other GMT games or other COIN series titles
Do NOT do historical research
Do NOT consult any GitHub repository other than this one
The Reference Documents folder is the complete universe of source material

### Dual-Purpose Data Structures
Data structures that serve multiple purposes (e.g., a dict used for BOTH deck composition AND card text lookup) are a source of duplication bugs. When consuming such a structure, always filter to the subset relevant to the current purpose. Add a comment explaining the filter. When building such a structure, document in a comment which keys serve which purpose. When in doubt, prefer separate data structures over one overloaded structure.

This rule exists because CARD_NAMES_ARIOVISTUS contains both A-prefix replacement cards (for deck building) and integer 2nd Edition keys (for text lookup only), and unfiltered use caused duplicate cards in the Ariovistus deck.

Ariovistus From Day 1
Every data structure must accommodate Ariovistus expansion content. If a region can be playable in one scenario but not another, that's part of the schema. If a piece type only exists in Ariovistus (Settlements, Diviciacus), it's still in rules_consts.py and the piece system. Do not build base-only structures that will need to be refactored.
Scenario Isolation — No Bleed-Through
The base game and Ariovistus are two different rule sets sharing a common core. Content from one must never leak into the other. The game state must carry a scenario identifier (e.g., state["scenario"]) that gates every scenario-dependent behavior. Specific isolation requirements:
Pieces: Settlements, Diviciacus, and the extra 15 Germanic Warbands do not exist in base game scenarios. Vercingetorix does not exist in Ariovistus scenarios. The piece system must refuse to place, remove, or reference pieces that don't exist in the current scenario. Available Forces pools must be built per-scenario from available_forces.txt (base) or available_forces_ariovistus.txt (Ariovistus).
Map: Britannia is playable in base game, unplayable in Ariovistus (A1.3.4). Cisalpina is unplayable in base game (unless Gallia Togata Event), always playable in Ariovistus (A1.3.2). The Nori tribe replaces Catuvellauni in Ariovistus. Alps crossing rules (A3.2.2) apply only in Ariovistus. March, Rally, and any other region-targeting logic must check whether a region/tribe is valid for the current scenario before using it.
Factions: In the base game, Germans are a non-player procedure (§6.2) that activates during the Germans Phase — they do NOT take turns in the Sequence of Play and have no bot flowchart. In Ariovistus, Germans are a full player/bot faction with their own flowchart and Sequence of Play slot. Conversely, Arverni are a player/bot faction in the base game but become game-run via the Arverni Phase (A6.2) in Ariovistus — they do NOT take turns in the Sequence of Play and have no bot flowchart. The engine/dispatcher must gate faction participation on the scenario.
Victory: Arverni do not track or achieve victory in Ariovistus (A7.0). Germanic victory conditions only exist in Ariovistus (A7.2). Roman and Aedui victory formulas differ between base (§7.2) and Ariovistus (A7.2) — Roman subtracts Settlements, Aedui counts Settlements as Germanic Allies. The victory module must use the correct formula set for the scenario.
Bot flowcharts: The German bot flowchart (Chapter A8) is Ariovistus-only. The Arverni bot flowchart (§8.5) is base-game-only. Roman, Aedui, and Belgae bots use their base flowcharts in both scenarios, but with Chapter A8 modifications active only in Ariovistus. The bot event instruction files are scenario-specific: *_bot_event_instructions.txt for base game, *_bot_event_instructions_ariovistus.txt for Ariovistus.
Cards: Base game and Ariovistus use different Event card decks. Card handlers, event evaluation tables, and bot instruction lookups must load the correct card set for the scenario.
Rules: Several rules change in Ariovistus: Senate Phase max 2 Legions (A6.5.2), Arverni Home "Rally" marker, Intimidated markers, At War mechanics, Cisalpina as a full region. These must only be active when state["scenario"] is an Ariovistus scenario.
General principle: If code checks state["scenario"] to decide what to do, that branch should be tested for both base and Ariovistus scenarios to confirm isolation works in both directions.
Testing

Run pytest -q before every commit
All tests must pass
When fixing a bug, add a test that would have caught it
When implementing a flowchart branch, add a test that exercises it
Tests should verify behavior against the Reference Documents, not against assumed behavior

Commit Discipline

One logical change per commit
Commit message should reference what was changed and why (e.g., "Fix Arverni Rally: Citadel placement per §3.3.1")
Never commit with failing tests

Determinism
All randomness must go through state["rng"], a seeded random.Random instance created at game start. Never use random.random(), random.choice(), random.randint(), or any other global random function. This enables deterministic replay for testing and debugging.
Piece Operations
Never manipulate piece counts in space dictionaries directly. Always use the piece operation helpers (place, remove, move, flip). These enforce caps, update Available pools, recalculate control, and maintain state integrity.

Conventions

Python 3.10+ assumed
Imports: Always import constants from rules_consts.py rather than using string literals
State: Game state is a dictionary passed through functions. Do not use global state.
Map queries: Use map/board helper modules — do not access space dictionaries directly with string keys
Piece operations: Use the piece operations module — do not manipulate piece counts directly
Control: Use the control module for control calculations
Randomness: Use state["rng"] exclusively


How to Run
bash# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run the game
python -m fs_bot

# Run tests
pytest -q

Build Plan
See BUILD_PLAN.md for the phased implementation roadmap and lessons learned from the Liberty or Death project that inform architectural decisions.

For the Developer
This project is being built from scratch with Claude Code, informed by the mistakes of a prior COIN-series bot project (Liberty or Death) that required 9+ audit sessions and 800+ tests to reach compliance. The primary goal from the start is correctness — making the implementation faithfully match the Reference Documents. Speed, optimization, and architectural elegance are secondary to rules accuracy.
When in doubt, read the Reference Documents again. Then read them one more time.
