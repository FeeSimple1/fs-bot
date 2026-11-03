"""NPC67 prospective Battles retain completed-Region forecast boundaries."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.board.control import is_controlled_by
from fs_bot.cards.capabilities import activate_capability
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.execute import _execute_battle
from fs_bot.state.state_schema import build_initial_state, validate_state


@pytest.mark.parametrize('prospective', [False, True])
def test_card27_prefire_wipe_completes_private_observer_boundary(prospective):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=27)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 7)
    assert not is_controlled_by(state, rc.NERVII, rc.BELGAE)
    activate_capability(state, 27, rc.EVENT_SHADED)
    observed = []

    def observe(stage, board, region, defender, result):
        observed.append((stage, region, defender, result))
        assert count_pieces(board, region, defender) == 0
        assert is_controlled_by(board, region, rc.BELGAE)

    action = {'command': rc.CMD_BATTLE, 'regions': [rc.NERVII],
              'sa': 'No SA', 'sa_regions': [], 'details': {
                  'battle_plan': [{'region': rc.NERVII, 'target': rc.ROMANS}]}}
    with free_action_scope(state, rc.ARVERNI):
        result = _execute_battle(state, rc.ARVERNI, action,
                                _battle_observer=observe,
                                _skip_absent_targets=prospective)
    assert result['executed'] and result['count'] == 1 and not result['errors']
    assert is_controlled_by(state, rc.NERVII, rc.BELGAE)
    assert observed == ([('before', rc.NERVII, rc.ROMANS, {'is_ambush': False}),
                         ('after', rc.NERVII, rc.ROMANS, {'card27_wiped': True})]
                        if prospective else [('before', rc.NERVII, rc.ROMANS, {'is_ambush': False})])
    assert validate_state(state) == []
