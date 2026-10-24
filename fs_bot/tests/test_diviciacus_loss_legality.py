"""A1.4/A3.2.4: Diviciacus is not eligible until the last possible piece."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import resolve_losses
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.engine.diviciacus import force_scope
from fs_bot.state.state_schema import build_initial_state, validate_state


def _state(scenario):
    state = build_initial_state(scenario, seed=11,
        diviciacus_option=scenario in rc.BASE_SCENARIOS)
    # The original-scenario option begins with the Leader out of play.
    if state['diviciacus_option']:
        state['removed_pieces'][rc.AEDUI][rc.LEADER] -= 1
        state['available'][rc.AEDUI][rc.LEADER] = 1
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER,
                leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    return state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS,
                                     rc.SCENARIO_GREAT_REVOLT])
@pytest.mark.parametrize('is_retreat', [False, True])
def test_human_cannot_assign_loss_to_diviciacus_before_other_pieces(scenario, is_retreat):
    state = _state(scenario)
    offered = []

    def choose_leader(board, faction, request):
        offered.append(request['pieces'])
        # A raw callback may attempt an unoffered choice. It must not bypass
        # the source's restriction, even though its save would be attractive.
        return [(rc.LEADER, None)]

    state['decision_agent'] = choose_leader
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 1,
                            is_retreat=is_retreat)
    assert all((rc.LEADER, None) not in choices for choices in offered)
    assert result['removed'] == [(rc.WARBAND, 1)]
    assert result['rolls'] == []
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.LEADER) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('with_fallback', [False, True])
def test_explicit_loss_priority_cannot_bypass_last_piece_restriction(with_fallback):
    state = _state(rc.SCENARIO_ARIOVISTUS)
    priorities = [(rc.LEADER, None)]
    if with_fallback:
        priorities.append((rc.WARBAND, rc.HIDDEN))
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 3,
                            loss_order=priorities)
    assert result['removed'] == [(rc.WARBAND, 1), (rc.WARBAND, 1)]
    # Seed 11's first die is 4: only the third Loss may reach Diviciacus.
    assert result['rolls'] == [(rc.LEADER, 4, False)]
    assert result['losses_absorbed'] == 1
    assert validate_state(state) == []


def test_cooperating_auxilia_are_eligible_before_diviciacus():
    state = _state(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    roman_available = get_available(state, rc.ROMANS, rc.AUXILIA)
    offered = []

    def choose_leader(board, faction, request):
        offered.append(request['pieces'])
        return [(rc.LEADER, None)]

    state['decision_agent'] = choose_leader
    with force_scope(state, rc.AEDUI, [rc.CARNUTES], 'defense'):
        result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 3)
    assert all((rc.LEADER, None) not in choices for choices in offered)
    assert result['rolls'] == []
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == roman_available + 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.LEADER) == 1
    assert validate_state(state) == []


def test_diviciacus_is_offered_when_only_piece_left():
    state = _state(rc.SCENARIO_ARIOVISTUS)
    offered = []

    def choose_leader(board, faction, request):
        offered.append(request['pieces'])
        return [(rc.LEADER, None)]

    state['decision_agent'] = choose_leader
    resolve_losses(state, rc.CARNUTES, rc.AEDUI, 3)
    assert (rc.LEADER, None) not in offered[0]
    assert (rc.LEADER, None) not in offered[1]
    assert offered[2] == [(rc.LEADER, None)]


def test_other_leaders_remain_eligible_alongside_warbands():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER,
                leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    state['decision_agent'] = lambda board, faction, request: [(rc.LEADER, None)]
    result = resolve_losses(state, rc.CARNUTES, rc.BELGAE, 1)
    assert result['rolls'] == [(rc.LEADER, 4, False)]
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 1
