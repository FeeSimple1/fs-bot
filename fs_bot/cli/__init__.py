"""Interactive CLI for Falling Sky Bot — Phase 6.

Provides a terminal-based interface for 0-4 human players alongside bot
factions. The CLI is the decision-and-display layer only; it does NOT
execute command mechanics. The engine's resolve_card_turn records what
each faction decided; actual command/event execution is a separate
workstream (see resolve_card_turn docstring in
fs_bot.engine.game_engine).

Reference: BUILD_PLAN.md Phase 6.
"""
