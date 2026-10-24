"""NP Suborn priorities and expanded limits from §8.6.3 and card A38."""

import pytest

from fs_bot.board.pieces import place_piece
from fs_bot.bots.aedui_bot import _determine_suborn_sa, SA_ACTION_SUBORN
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine.execute import _execute_suborn
from fs_bot.rules_consts import (
    AEDUI, ARVERNI, ROMANS, ALLY, WARBAND, HIDDEN, EVENT_UNSHADED,
    SCENARIO_PAX_GALLICA, CARNUTES, MANDUBII, TRIBE_CARNUTES,
    TRIBE_AULERCI, TRIBE_MANDUBII,
)
from fs_bot.state.state_schema import build_initial_state


def _state(enhanced=False, resources=10):
    state = build_initial_state(SCENARIO_PAX_GALLICA, seed=42)
    state["non_player_factions"] = {AEDUI, ROMANS, ARVERNI}
    state["resources"][AEDUI] = resources
    place_piece(state, CARNUTES, AEDUI, WARBAND, piece_state=HIDDEN)
    if enhanced:
        activate_capability(state, "A38", EVENT_UNSHADED)
    return state


def _plan(state):
    sa, regions, details = _determine_suborn_sa(
        state, state["scenario"], allowed_regions={CARNUTES})
    assert sa == SA_ACTION_SUBORN
    assert regions == [CARNUTES]
    return details, details["suborn_plan"][0]["actions"]


def _ally(state, faction, tribe, region=CARNUTES):
    place_piece(state, region, faction, ALLY)
    state["tribes"][tribe]["allied_faction"] = faction


@pytest.mark.parametrize("enhanced,pieces,allies", [(False, 3, 1), (True, 4, 2)])
def test_suborn_uses_printed_piece_and_ally_limits(enhanced, pieces, allies):
    state = _state(enhanced)
    details, actions = _plan(state)
    assert len(actions) == pieces
    assert sum(a["action"] == "place_ally" for a in actions) == allies
    result = _execute_suborn(state, AEDUI, {"details": details})
    assert result["executed"] and not result["errors"]
    assert state["resources"][AEDUI] == 10 - pieces - allies


def test_enhanced_suborn_removes_two_distinct_allies_before_warbands():
    state = _state(True)
    _ally(state, ARVERNI, TRIBE_CARNUTES)
    _ally(state, ARVERNI, TRIBE_AULERCI)
    details, actions = _plan(state)
    assert [a["action"] for a in actions] == [
        "remove_ally", "remove_ally", "place_warband", "place_warband"]
    assert {a["tribe"] for a in actions[:2]} == {TRIBE_CARNUTES, TRIBE_AULERCI}
    assert _execute_suborn(state, AEDUI, {"details": details})["executed"]


def test_enhanced_suborn_preserves_none_placed_branch_and_resource_budget():
    state = _state(True, resources=3)
    _ally(state, ARVERNI, TRIBE_CARNUTES)
    _, actions = _plan(state)
    assert [a["action"] for a in actions] == ["place_ally", "place_warband"]


@pytest.mark.parametrize("extra_roman,expected", [(False, ARVERNI), (True, ROMANS)])
def test_suborn_most_allies_first_then_np_roman_tiebreak(extra_roman, expected):
    state = _state()
    _ally(state, ROMANS, TRIBE_CARNUTES)
    _ally(state, ARVERNI, TRIBE_AULERCI)
    if extra_roman:
        _ally(state, ROMANS, TRIBE_MANDUBII, MANDUBII)
    _, actions = _plan(state)
    assert actions[0]["action"] == "remove_ally"
    assert actions[0]["target_faction"] == expected


def test_suborn_can_remove_np_roman_ally_when_only_enemy():
    state = _state()
    _ally(state, ROMANS, TRIBE_CARNUTES)
    _ally(state, AEDUI, TRIBE_AULERCI)
    _, actions = _plan(state)
    assert actions[0]["action"] == "remove_ally"
    assert actions[0]["target_faction"] == ROMANS
