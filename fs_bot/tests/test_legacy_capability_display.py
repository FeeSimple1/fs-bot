"""Legacy Vergobret saves expose the same active card to humans as the engine."""
import io
import random

from fs_bot import rules_consts as rc
from fs_bot.cards.capabilities import get_active_capabilities
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.param_schema import card_param_schema, generate_params, kind_values
from fs_bot.cli.display import format_board, format_state_delta, snapshot_state
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario


def legacy_state():
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=17)
    state.setdefault("event_modifiers", {})["card_A38_suborn_enhanced"] = True
    return state


def test_legacy_capability_has_full_board_text_and_removal_delta_without_mutation():
    state = legacy_state()
    before = encode(state)
    text = format_board(state)
    snapshot = snapshot_state(state)
    assert "#A38 Vergobret (unshaded)" in text
    assert f"Card A38: {rc.EVENT_UNSHADED}" in text
    assert all(line in text for line in get_card_text("A38").splitlines())
    assert snapshot["capabilities"] == {"A38": rc.EVENT_UNSHADED}
    assert encode(state) == before

    state["event_params"] = {"target_capability": "A38"}
    execute_event(state, 50)
    assert get_active_capabilities(state) == {}
    delta = format_state_delta(snapshot, snapshot_state(state))
    assert f"Capability card A38: {rc.EVENT_UNSHADED} -> (none)" in [line.strip() for line in delta]


def test_event50_human_picker_offers_active_cards_including_legacy_vergobret():
    state = legacy_state()
    state["capabilities"][8] = rc.EVENT_SHADED
    before = encode(state)
    out = io.StringIO()
    params = _collect_event_params(state, rc.AEDUI, 50, False,
                                   io.StringIO("2\n"), out)
    assert params == {"target_capability": "A38"}
    assert "Vergobret" in out.getvalue()
    assert rc.PROVINCIA not in out.getvalue()
    assert encode(state) == before
    state["event_params"] = params
    execute_event(state, 50)
    assert get_active_capabilities(state) == {8: rc.EVENT_SHADED}


def test_event50_generated_targets_are_actual_active_capabilities():
    state = legacy_state()
    assert card_param_schema(50, state["scenario"])["target_capability"]["kind"] == "capability"
    assert kind_values(state, "capability") == ["A38"]
    assert generate_params(state, 50, random.Random(1), include_p=1) == {
        "target_capability": "A38"}
    state["event_modifiers"].clear()
    assert generate_params(state, 50, random.Random(1), include_p=1) == {}


def test_explicit_shaded_side_takes_precedence_over_stale_legacy_flag():
    state = legacy_state()
    state["capabilities"]["A38"] = rc.EVENT_SHADED
    text = format_board(state)
    assert "#A38 Vergobret (shaded)" in text
    assert snapshot_state(state)["capabilities"]["A38"] == rc.EVENT_SHADED
