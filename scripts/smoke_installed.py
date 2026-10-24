"""Exercise an installed distribution from a directory outside its checkout.

Usage: /path/to/clean/venv/python -I /checkout/scripts/smoke_installed.py
Build/install the wheel first. This script uses only the standard library.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import fs_bot
from fs_bot import rules_consts as rc
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import get_all_card_ids
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.game_engine import ACTION_EVENT, get_sop_factions, run_game
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.tools.rules_trace import parse_sections
from fs_bot.version import engine_identity


def decide(state, faction, options, position):
    state["current_card_id"] = state.get("current_card")
    state["is_second_eligible"] = position == "2nd_eligible"
    state["can_play_event"] = ACTION_EVENT in options
    action = dispatch_bot_turn(state, faction)
    return {"action": _translate_bot_action(action, options), "bot_action": action}


def main():
    checkout = Path(__file__).resolve().parents[1]
    assert checkout not in Path(fs_bot.__file__).resolve().parents, (
        "Smoke test imported the checkout instead of the installed package")
    assert len(parse_sections()) > 250
    for card_id in get_all_card_ids():
        assert get_card_text(card_id), f"Installed card text missing: {card_id}"
    for edition in ("original", "second-edition", "legacy"):
        for scenario in rc.ALL_SCENARIOS:
            for card in (11, 30, 39, 44, 54):
                assert get_card_text(card, scenario, edition)
    with tempfile.TemporaryDirectory(prefix="fsbot-installed-") as directory:
        path = Path(directory) / "game.json"
        for scenario in rc.ALL_SCENARIOS:
            state = setup_scenario(scenario, seed=501)
            save_game(state, path)
            loaded, _, _ = load_game(path, validate=True)
            assert encode(loaded) == encode(state)
        for scenario in (rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS):
            state = setup_scenario(scenario, seed=501)
            state["non_player_factions"] = set(get_sop_factions(state))
            with contextlib.redirect_stdout(io.StringIO()):
                result = run_game(state, decide, execute=True)
            assert result["card_results"][-1].get("winner")
        subprocess.run([sys.executable, "-I", "-m", "fs_bot", "--help"],
                       cwd=directory, check=True, stdout=subprocess.PIPE)
        executable = Path(sys.executable).parent / (
            "fs-bot.exe" if sys.platform == "win32" else "fs-bot")
        subprocess.run([str(executable), "--help"], cwd=directory,
                       check=True, stdout=subprocess.PIPE)
    print(json.dumps({"installed": str(Path(fs_bot.__file__).resolve()),
                      "engine": engine_identity(), "smoke": "passed"}))


if __name__ == "__main__":
    main()
