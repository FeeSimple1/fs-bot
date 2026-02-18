"""Engine package — Victory, Winter Round, and game-run procedures.

Modules:
  victory — Victory calculation and checking (§7.0, A7.0)
  winter — Winter Round phases (§6.0, A6.0)
  germans_battle — Germans Phase Battle with Ambush (§6.2.4)
  arverni_phase — Arverni Phase game-run procedure (A6.2)
"""

from fs_bot.engine.victory import (
    calculate_victory_score,
    check_victory,
    calculate_victory_margin,
    check_any_victory,
    determine_final_ranking,
)

from fs_bot.engine.winter import run_winter_round

__all__ = [
    "calculate_victory_score",
    "check_victory",
    "calculate_victory_margin",
    "check_any_victory",
    "determine_final_ranking",
    "run_winter_round",
]
