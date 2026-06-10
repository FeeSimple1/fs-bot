"""Tests for the self-play heuristic agent and the balance guardrail."""
import subprocess
import sys
from pathlib import Path

import pytest

import fs_bot.rules_consts as rc
from fs_bot.agents.heuristic import PROFILES
from fs_bot.tools.heuristic_selfplay import play_game

_BASELINE = Path(__file__).resolve().parents[1] / "tools" / "balance_baseline.json"


def test_every_profile_finishes_a_game():
    """Each heuristic profile completes a Great Revolt game and never wedges."""
    from fs_bot.agents.heuristic import plan_turn
    for name, prof in PROFILES.items():
        fac = prof["faction"]
        r = play_game(rc.SCENARIO_GREAT_REVOLT, seed=1, agent_faction=fac,
                      planner=lambda s, f, o, p, _pr=prof:
                      plan_turn(s, f, _pr, o, p))
        assert r["winner"] is not None, f"{name} produced no winner"
        assert r["cards"] >= 1


def test_random_plan_policy_finishes():
    from fs_bot.agents.heuristic import RandomPlanPolicy
    pol = RandomPlanPolicy(rc.ROMANS, seed=3)
    r = play_game(rc.SCENARIO_PAX_GALLICA, seed=3,
                  agent_faction=rc.ROMANS, planner=pol.plan_turn)
    assert r["winner"] is not None


@pytest.mark.skipif(not _BASELINE.exists(), reason="no balance baseline")
def test_bot_balance_canary():
    """Fixed-seed bot-only games must match the committed baseline. If an
    intended change moves outcomes, refresh:
    python -m fs_bot.tools.balance_smoke --update"""
    proc = subprocess.run(
        [sys.executable, "-m", "fs_bot.tools.balance_smoke",
         "--seeds", "1-3", "--band", "0.40"],
        capture_output=True, text=True, timeout=300,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode == 0, (
        "Bot balance drifted from baseline. If intended, run "
        "'python -m fs_bot.tools.balance_smoke --update' and commit it.\n\n"
        + proc.stdout[-2000:] + proc.stderr[-400:]
    )
