"""Engine package — Victory, Winter Round, game-run procedures, game loop.

Modules:
  victory — Victory calculation and checking (§7.0, A7.0)
  winter — Winter Round phases (§6.0, A6.0)
  germans_battle — Germans Phase Battle with Ambush (§6.2.4)
  arverni_phase — Arverni Phase game-run procedure (A6.2)
  game_engine — Sequence of Play orchestrator (§2.0-§2.4, A2.0-A2.3.9)
"""

from importlib import import_module

__all__ = [
    "calculate_victory_score",
    "check_victory",
    "calculate_victory_margin",
    "check_any_victory",
    "determine_final_ranking",
    "run_winter_round",
    "start_game",
    "draw_card",
    "advance_to_next_card",
    "is_winter_card",
    "is_frost",
    "get_sop_factions",
    "get_faction_order",
    "get_eligible_factions",
    "determine_eligible_order",
    "get_first_eligible_options",
    "get_second_eligible_options",
    "execute_pass",
    "adjust_eligibility",
    "resolve_card_turn",
    "resolve_winter_card",
    "play_card",
    "run_game",
]


def __getattr__(name):
    # Preserve convenience exports without loading Winter/Battle while one
    # of their dependencies is only partially initialized.
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name in {"calculate_victory_score", "check_victory",
                "calculate_victory_margin", "check_any_victory",
                "determine_final_ranking"}:
        module = "victory"
    elif name == "run_winter_round":
        module = "winter"
    else:
        module = "game_engine"
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
