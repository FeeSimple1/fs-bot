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

from importlib import import_module

__all__ = ["resolve_battle", "calculate_losses", "resolve_losses"]


def __getattr__(name):
    # Piece helpers also import small battle submodules during setup. Loading
    # the entire battle/engine graph here makes those imports order-dependent.
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = "resolve" if name == "resolve_battle" else "losses"
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
