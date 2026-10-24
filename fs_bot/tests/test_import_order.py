"""Public imports must work without pytest's earlier imports warming caches."""
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("imports", [
    "from fs_bot.state.setup import setup_scenario",
    "from fs_bot.commands.sa_trade import trade\nfrom fs_bot.state.setup import setup_scenario",
    "from fs_bot.battle.resolve import resolve_battle\nfrom fs_bot.state.setup import setup_scenario",
    "from fs_bot.engine.diviciacus import defensive_battle\nfrom fs_bot.state.setup import setup_scenario",
    "from fs_bot.engine import *\nfrom fs_bot.battle import *\nfrom fs_bot.state.setup import setup_scenario",
    "from fs_bot.battle import *\nfrom fs_bot.engine import *\nfrom fs_bot.state.setup import setup_scenario",
])
def test_setup_and_public_exports_in_fresh_process(imports):
    script = imports + """
from fs_bot import rules_consts as rc
from fs_bot.battle import resolve_battle
from fs_bot.battle.resolve import resolve_battle as direct_battle
from fs_bot.engine import run_game
from fs_bot.engine.game_engine import run_game as direct_game
assert resolve_battle is direct_battle
assert run_game is direct_game
for scenario in rc.ALL_SCENARIOS:
    state = setup_scenario(scenario, seed=23)
    assert state['scenario'] == scenario
"""
    result = subprocess.run([sys.executable, "-c", script],
                            cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
