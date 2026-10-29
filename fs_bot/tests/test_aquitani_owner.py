"""Card 25's "Your Rally" capability retains the actual Event owner."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.capabilities import (
    deactivate_capability, get_capability_owner, is_capability_active,
)
from fs_bot.cards.card_effects import execute_card_25
from fs_bot.engine.execute import _execute_event
from fs_bot.state.serialize import decode, encode
from fs_bot.state.state_schema import build_initial_state


def _state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=23)
    state["current_card"] = state["current_card_id"] = 25
    return state


@pytest.mark.parametrize("faction", [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
@pytest.mark.parametrize("human", [False, True])
def test_event_executor_records_actor_instead_of_previous_context(faction, human):
    # Card Reference 25: "Your Rally"; Chapter 5.1: the Event executor.
    state = _state()
    state["executing_faction"] = rc.GERMANS
    state["capability_owners"] = {25: rc.GERMANS}
    rng = state["rng"].getstate()

    result = _execute_event(state, faction, {
        "command": "Event",
        "details": {"card_id": 25, "text_preference": rc.EVENT_SHADED},
    }, human=human)

    assert result["executed"]
    assert is_capability_active(state, 25, rc.EVENT_SHADED)
    assert get_capability_owner(state, 25) == faction
    assert state["executing_faction"] == rc.GERMANS
    assert state["rng"].getstate() == rng


@pytest.mark.parametrize("stale_owner", [None, rc.ARVERNI])
def test_raw_activation_without_actor_does_not_invent_or_reuse_owner(stale_owner):
    state = _state()
    if stale_owner is not None:
        state["capability_owners"] = {25: stale_owner}

    execute_card_25(state, shaded=True)

    assert is_capability_active(state, 25, rc.EVENT_SHADED)
    assert get_capability_owner(state, 25) is None


def test_owner_survives_saved_state_encoding_and_leaves_with_capability():
    state = _state()
    state["executing_faction"] = rc.BELGAE
    execute_card_25(state, shaded=True)

    restored = decode(encode(state))
    assert get_capability_owner(restored, 25) == rc.BELGAE
    assert is_capability_active(restored, 25, rc.EVENT_SHADED)

    deactivate_capability(restored, 25)
    assert not is_capability_active(restored, 25)
    assert get_capability_owner(restored, 25) is None
