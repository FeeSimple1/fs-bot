"""Trade's visible earnings breakdown must survive cross-process replay."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_trade_details_are_identical_across_python_hash_seeds():
    script = """
import json
from fs_bot import rules_consts as rc
from fs_bot.engine.game_engine import run_game
from fs_bot.commands.sa_trade import trade
from fs_bot.state.setup import setup_scenario
state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=42)
before = state['rng'].getstate()
result = trade(state, agreements={f: True for f in rc.FACTIONS}, roman_agreed=True)
assert state['rng'].getstate() == before
print(json.dumps(result, sort_keys=True))
"""
    outputs = []
    for seed in ("0", "7"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                cwd=Path(__file__).resolve().parents[2],
                                check=True, capture_output=True, text=True)
        outputs.append(result.stdout)
    details = json.loads(outputs[0])
    assert len(details["per_item"]) > 1
    assert details["resources_gained"] > 0
    assert outputs[0] == outputs[1]
