"""The printed O38 boundary label makes both versions Capabilities (§5.3).

Card 50 removes the Capability; it does not undo a completed piece placement.
A Setup and A1.4 independently retain the physical Leader's rules.
"""

import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import find_leader, place_piece, remove_piece
from fs_bot.cards.capabilities import (
    activate_capability, get_active_capabilities, is_capability_active,
    is_valid_capability,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.commands.common import CommandError
from fs_bot.commands.transfer import transfer_resources
from fs_bot.engine.diviciacus import eligible_regions
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state


def option():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=31, diviciacus_option=True)
    state['resources'][rc.ROMANS] = state['resources'][rc.AEDUI] = 10
    return state


def place_leader(state):
    state['event_params'] = {'region': rc.CARNUTES}
    execute_event(state, rc.CARD_O38)


def test_o38_capability_is_recorded_saved_and_removable_without_removing_leader(tmp_path):
    state = option()
    place_leader(state)
    for region in (rc.CARNUTES, rc.MORINI):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    assert is_valid_capability(rc.CARD_O38, state['scenario'])
    assert get_active_capabilities(state) == {rc.CARD_O38: rc.EVENT_UNSHADED}
    assert eligible_regions(state, rc.ROMANS) == [rc.CARNUTES]
    assert eligible_regions(state, rc.ROMANS, 'special_ability') == [rc.CARNUTES]
    path = tmp_path / 'o38.json'
    save_game(state, path)
    restored, _, _ = load_game(path, validate=True)
    assert encode(restored) == encode(state)

    restored['event_params'] = {'target_capability': rc.CARD_O38}
    execute_event(restored, 50)
    assert get_active_capabilities(restored) == {}
    assert find_leader(restored, rc.AEDUI) == rc.CARNUTES
    assert restored['diviciacus_in_play']
    assert eligible_regions(restored, rc.ROMANS) == [rc.CARNUTES]
    assert eligible_regions(restored, rc.ROMANS, 'special_ability') == [rc.CARNUTES]
    save_game(restored, path)
    resumed, _, _ = load_game(path, validate=True)
    assert encode(resumed) == encode(restored)
    assert get_active_capabilities(resumed) == {}
    assert validate_state(resumed) == []


def test_o38_shaded_replaces_unshaded_registry_and_keeps_legacy_transfer_key():
    state = option()
    place_leader(state)
    execute_event(state, rc.CARD_O38, shaded=True)
    assert get_active_capabilities(state) == {38: rc.EVENT_SHADED}
    assert find_leader(state, rc.AEDUI) == rc.CARNUTES
    with pytest.raises(CommandError, match='Diviciacus'):
        transfer_resources(state, rc.ROMANS, rc.AEDUI, 1)
    remove_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER)
    place_leader(state)
    assert get_active_capabilities(state) == {rc.CARD_O38: rc.EVENT_UNSHADED}
    assert transfer_resources(state, rc.ROMANS, rc.AEDUI, 1)['given'] == 1
    assert validate_state(state) == []


def test_o38_is_visible_to_human_card50_picker_and_capability_delta():
    from fs_bot.cli.display import format_board, format_state_delta, snapshot_state
    from fs_bot.cli.human_plan import _collect_event_params
    state = option()
    place_leader(state)
    before = encode(state)
    snapshot = snapshot_state(state)
    assert '#O38 Diviciacus (unshaded)' in format_board(state)
    out = io.StringIO()
    params = _collect_event_params(state, rc.AEDUI, 50, False,
                                   io.StringIO('1\n'), out)
    assert params == {'target_capability': rc.CARD_O38}
    assert 'O38: Diviciacus (Unshaded)' in out.getvalue()
    assert encode(state) == before
    state['event_params'] = params
    execute_event(state, 50)
    delta = format_state_delta(snapshot, snapshot_state(state))
    assert 'Capability card O38: Unshaded -> (none)' in [line.strip() for line in delta]
    assert find_leader(state, rc.AEDUI) == rc.CARNUTES


def test_original_diviciacus_capability_still_operates_without_optional_leader():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=31)
    for region in (rc.CARNUTES, rc.MORINI):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    activate_capability(state, 38, rc.EVENT_UNSHADED)
    assert eligible_regions(state, rc.ROMANS) == sorted([rc.CARNUTES, rc.MORINI])
    assert eligible_regions(state, rc.ROMANS, 'special_ability') == []
    assert is_capability_active(state, 38, rc.EVENT_UNSHADED)
    assert not is_capability_active(state, rc.CARD_O38)
