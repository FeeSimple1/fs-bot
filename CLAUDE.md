# Developer instructions — Falling Sky Bot Engine
Project Summary
This is an automation engine for the non-player bot flowcharts in Falling Sky: The Gallic Revolt Against Caesar (GMT Games, COIN Series Vol. VI, 2nd Edition) and its Ariovistus expansion. It handles 0–4 bot-controlled factions (Roman, Arverni, Aedui, Belgae, plus Germanic in Ariovistus) via an interactive CLI. The goal is faithful implementation of the published flowcharts — not a variation, not a reinterpretation, not a "simplified" version.
Language/runtime: Python 3.10+; gameplay uses the standard library.
Tests: pytest.
No external game references. Do not consult BoardGameGeek, other COIN games, other GMT titles, or any historical sources outside the Reference Documents.

## Current project orientation

Read [README.md](README.md) for entry points and
[docs/README.md](docs/README.md) for the documentation map. Current fixes,
known limits, and source questions are in
[docs/current-status.md](docs/current-status.md). The owner adopted
[PR-01 through PR-06](docs/provisional-rulings.md) on 24 October 2026 and
PR-07 through PR-09 on 29 October 2026; apply
those provisional decisions to their specified gaps, subject to possible
later correction if an authoritative source is found. The
[29 October Recruit/Rally report](docs/reviews/recruit-rally-2026-10-29.md)
tracks exact quantities, ordered placements and related source corrections.
The [29 October action-timing report](docs/reviews/action-timing-2026-10-29.md)
tracks the subsequent reclamation, mid-action Spring entry, same-Region
Rally interruption, and exact participating-piece repairs. The
[28 October Spring report](docs/reviews/spring-leaders-2026-10-28.md)
tracks Leader placement repairs and the then-remaining mid-action entry gap;
the [27 October second-batch report](docs/reviews/second-batch-2026-10-27.md)
records the preceding Event-choice repairs. The
[23 October validation report](docs/reviews/outstanding-fixes-2026-10-23.md)
remains a revision-specific checkpoint. A report is not a promise about
every future change.
[BUILD_PLAN.md](BUILD_PLAN.md) is now the maintenance roadmap; the engine,
CLI, assistant sessions, and validation tools already exist.

Project guides and historical strategy notes are implementation documentation,
not additional game-rule authorities. Preserve the provenance of earlier
owner-authorized rulings and scoped external comparisons; they do not grant
blanket permission to introduce other source material.

## Source of Truth (Strict Hierarchy)
These are read-only. Never modify them. All other code must conform to them,
with the nine expressly owner-adopted interpretations in
[docs/provisional-rulings.md](docs/provisional-rulings.md) governing only their
listed unresolved cases. These project rulings are not official errata.
1. fs_bot/rules_consts.py — Canonical Labels
Every string label for factions, pieces, markers, leaders, regions, tribes, and space IDs used anywhere in the codebase must come from this file. If a label doesn't exist here, it is wrong.
If you encounter a string literal in the code that doesn't match a constant from rules_consts.py (e.g., "warband", "legion", "auxilia" used as a piece tag, "fort", etc.), it is a bug. Replace it with the correct constant.
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
If the Reference Documents are ambiguous, contradictory, or silent on a question
and no explicit owner ruling already covers it:

STOP working on that specific issue.
Document the question in QUESTIONS.md, including:

What you were trying to implement
What the reference says (quote it)
What's ambiguous or contradictory
What options you see


Move on to other work.
Do not implement a "best guess" — wait for the user to answer. The owner has
already answered the nine cases in [the provisional ruling register](docs/provisional-rulings.md);
do not re-block those cases. Preserve their provisional status and revisit
them if an authoritative clarification appears.

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
Pieces: Default base setup excludes Settlements, Diviciacus, and the extra 15 Germanic Warbands; Ariovistus setup excludes Vercingetorix. Build the appropriate Available Forces pools from available_forces.txt or available_forces_ariovistus.txt and enforce them through piece helpers. Respect explicit exceptions: A Setup and A1.4 permit a separate optional Diviciacus rule in original scenarios, and the Gallic War Interlude has its own removal/return accounting. The current CLI's five-card edition selector does not enable that separate setup option. Do not erase a legal Interlude context merely because the current scenario has changed to a base scenario.
Map: Default base geography includes Britannia; Ariovistus excludes it (A1.3.4) and adds Cisalpina (A1.3.2), with Nori replacing Catuvellauni. Base Cisalpina access depends on Gallia Togata. Ordinary Alps stops are scenario-dependent, while the active Gallia Togata card governs its printed exceptions. Use state-aware geography and active card identity: an A5 effect can survive the Gallic War Interlude. March, Rally, stacking, and other targeting must check the actual Region/Tribe and Event context.
Factions: In the base game, Germans are a non-player procedure (§6.2) that activates during the Germans Phase — they do NOT take turns in the Sequence of Play and have no bot flowchart. In Ariovistus, Germans are a full player/bot faction with their own flowchart and Sequence of Play slot. Conversely, Arverni are a player/bot faction in the base game but become game-run via the Arverni Phase (A6.2) in Ariovistus — they do NOT take turns in the Sequence of Play and have no bot flowchart. The engine/dispatcher must gate faction participation on the scenario.
Victory: Arverni do not track or achieve victory in Ariovistus (A7.0). Germanic victory conditions only exist in Ariovistus (A7.2). Roman and Aedui victory formulas differ between base (§7.2) and Ariovistus (A7.2) — Roman subtracts Settlements, Aedui counts Settlements as Germanic Allies. The victory module must use the correct formula set for the scenario.
Bot flowcharts: The German bot flowchart (Chapter A8) is Ariovistus-only. The Arverni bot flowchart (§8.7) is base-game-only. Roman, Aedui, and Belgae bots use their base flowcharts in both scenarios, but with Chapter A8 modifications active only in Ariovistus. The bot event instruction files are scenario-specific: *_bot_event_instructions.txt for base game, *_bot_event_instructions_ariovistus.txt for Ariovistus.
Cards: Base game and Ariovistus use different Event card decks. Card handlers, event evaluation tables, and bot instruction lookups must load the correct card set for the scenario.
Rules: Several rules change in Ariovistus: Senate Phase combined maximum of 2 Legions from the Intrigue/Adulation rows, with eligible Uproar-row Legions unaffected by that cap (A6.5.2), Arverni Home "Rally" marker, Intimidated markers, At War mechanics, Cisalpina as a full region. These must only be active when state["scenario"] is an Ariovistus scenario.
General principle: Test both base and Ariovistus behavior, plus explicit Event and Interlude exceptions. The Gallic War preserves specified lingering effects and removed-piece bookkeeping while changing scenario and player seats. Consult scenario_phase and active effects where appropriate; preserve those exceptions without enabling unrelated expansion rules.
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


## Run and validate

Playing needs no third-party packages:

```sh
python -m fs_bot --save autosave.json
```

For development, create an environment and install the test dependency:

```sh
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The full-test-before-every-commit requirement above also applies to
project documentation commits. Do not change dependency requirements merely
to use an optional local test runner such as pytest-xdist.

Consult [SELFPLAY_PLAYBOOK.md](SELFPLAY_PLAYBOOK.md) for the actual batch,
strict census, replay, and balance commands. Inspect per-game records:
process exit status alone is not a sufficient acceptance check for every
historical tool. Never overwrite earlier failed runs or combine results
from different source revisions. The current balance guardrail uses seeds
1–20 in all five scenarios and a 15-percentage-point band. Refresh it only
after explaining intended changes supported by the sources or an expressly
adopted project ruling on the same seed set;
do not tune the bots or widen the threshold to obtain preferred win rates.

## Human-interface requirements

- Preserve the legal Command/Special Activity ordering choices, including
  supported interrupted Commands. Ambush and Besiege resolve within Battle.
- Show current/upcoming card text and changes before human decisions, and
  retain `board`/`b` inspection at prompts.
- Offer physical piece and beneficiary choices where the rules allow them;
  previews must not consume live human input or random state.
- Keep an invalid or missing assistant response pending. Do not silently
  substitute a bot choice for a human in the durable session frontend.
- Preserve transaction rollback, accepted choices, stable pending decision
  identifiers, save/load, and deterministic replay when adding requests.
  The raw callback's documented fallback contract is distinct from the
  human-session contract; see [AGENT_INTERFACE.md](AGENT_INTERFACE.md).

## Documentation maintenance

Update the relevant player/API guide along with changed behavior. Keep
current dispositions and links in `docs/current-status.md`, and source
questions/rulings in `QUESTIONS.md`. Historical reports and strategy samples
retain their original measurements, with dated supersession notices when
needed. Record the tested commit and digest; even Python docstring edits
change the byte-level source digest. Do not relabel old outcomes as new runs.

Rules fidelity remains the priority. Consult the supplied references before
changing behavior and leave unresolved source conflicts explicitly recorded.
For adopted provisional rulings, record both the governing project decision
and its continuing susceptibility to authoritative correction.

Card Key Suffixes: In CARD_NAMES_ARIOVISTUS, some A-prefix card keys end with "C" (e.g., "A15C"). The trailing "C" represents the carynx symbol printed on those cards in the physical game. It is part of the card's identity, not a typo or encoding artifact. Do not strip, rename, or "normalize" these suffixes.
