"""Battle module — Full Battle procedure per §3.2.4, §3.3.4, §3.4.4.

This module implements the Battle resolution procedure as a standalone
system. It accepts parameters (attacker, defender, region, modifiers)
and resolves the battle. The caller decides who fights whom and where.

Sub-modules:
    losses: Losses calculation and resolution.
    resolve: Full battle procedure (Steps 1-6).

Reference: §3.2.4, §3.3.4, §3.4.4, §4.2.3, §4.3.3, §4.4.3, §4.5.3,
           battle_procedure_flowchart.txt, A3.2.4, A3.3.4, A3.4.4
"""

from fs_bot.battle.resolve import resolve_battle  # noqa: F401
from fs_bot.battle.losses import (  # noqa: F401
    calculate_losses,
    resolve_losses,
)
