"""§8.7.1: Battles are paid before Devastate or Entreat resolves."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.engine.execute import execute_decision
from fs_bot.bots.arverni_bot import _determine_battle_sa
from fs_bot.state.state_schema import build_initial_state


def board(auxilia, resources):
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=91)
    st['non_player_factions'] = {rc.ARVERNI}
    st['resources'][rc.ARVERNI] = resources
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 3,
                piece_state=rc.REVEALED)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, auxilia)
    refresh_all_control(st)
    return st


def action(sa):
    return {'command': 'Battle', 'sa': sa, 'sa_regions': [],
            'details': {'battle_plan': [{'region': rc.MANDUBII, 'target': rc.ROMANS}]}}


def test_entreat_planner_reserves_battle_cost():
    st = board(1, 1)
    sa, _ = _determine_battle_sa(st, action('Entreat')['details']['battle_plan'],
                                st['scenario'])
    assert sa == 'No SA'
    assert st['resources'][rc.ARVERNI] == 1


def test_entreat_cannot_spend_battle_resources_before_resolution():
    st = board(1, 1)
    result = execute_decision(st, rc.ARVERNI, {'bot_action': action('Entreat')})
    assert result['executed'] and result['errors'] == []
    assert result['sa_execution']['executed'] is False
    assert result['total_cost'] == 1
    assert st['resources'][rc.ARVERNI] == 0
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0


def test_before_battle_devastation_does_not_raise_already_paid_price():
    st = board(2, 1)
    result = execute_decision(st, rc.ARVERNI, {'bot_action': action('Devastate')})
    assert result['executed'] and result['errors'] == []
    assert result['sa_execution']['executed']
    assert result['total_cost'] == 1
    assert st['resources'][rc.ARVERNI] == 0
    assert rc.MARKER_DEVASTATED in st['markers'][rc.MANDUBII]


def test_entreat_itself_remains_paid_after_battle_payment():
    st = board(1, 2)
    # A separate adjacent Region offers Entreat without removing the battle target.
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND)
    place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    # The planner normally avoids Entreat removing a lone target. Explicit
    # plan with two Romans also makes Devastate eligible, so make this Region
    # already Devastated: it still costs two to Battle and Entreat is paid.
    st['markers'].setdefault(rc.MANDUBII, {})[rc.MARKER_DEVASTATED] = True
    st['resources'][rc.ARVERNI] = 3
    # Keep the enemy in the Battle Region out of Entreat by revealing the
    # lone Hidden Arverni Warband; the adjacent Aedui target remains eligible.
    from fs_bot.board.pieces import flip_piece
    flip_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 1,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    result = execute_decision(st, rc.ARVERNI, {'bot_action': action('Entreat')})
    assert result['executed'] and result['errors'] == []
    assert result['total_cost'] == 2
    assert result['sa_execution']['executed']
    assert st['resources'][rc.ARVERNI] == 0
    assert count_pieces(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 0
