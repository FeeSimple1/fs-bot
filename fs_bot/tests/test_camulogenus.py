"""Card70's printed single destination, exact pieces, and moving-only flips."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.camulogenus import make_request, validate_response, march_routes
from fs_bot.engine.execute import _resolve_card70_march_battle
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=70)
    state['non_player_factions'] = set()
    return state


def group(origin=rc.SEQUANI, route=None, legions=0, auxilia=1, caesar=False):
    return {'origin': origin, 'route': route if route is not None else [rc.MANDUBII],
            'legions': legions, 'auxilia': auxilia, 'caesar': caesar}


def plan(*groups, destination=rc.MANDUBII, cooperation=()):
    return {'destination': destination, 'marches': list(groups),
            'diviciacus_regions': list(cooperation)}


def choose_plan(response, extra=None):
    def choose(state, faction, request):
        kind = request.get('request_type')
        if kind == 'roman_event_accept':
            return {'accept': True}
        if kind == 'camulogenus_march':
            return response
        return extra(state, faction, request) if extra else None
    return choose


def test_split_groups_flip_each_selected_auxilia_once_and_leave_residents_unchanged():
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    seen = []
    def visibility(state, owner, request):
        if request['kind'] == 'march_cohort':
            seen.append(deepcopy(request))
            return {'counts': {rc.REVEALED: 1}}
    state['decision_agent'] = choose_plan(plan(group(), group()), visibility)
    result = _resolve_card70_march_battle(state, [rc.MANDUBII], 4)[0]
    assert len(result['march_result']['marches']) == 2
    assert len(seen) == 2
    assert [r['available'][rc.REVEALED] for r in seen] == [3, 2]
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert not state.get('_action_window_cohorts')
    assert validate_state(state) == []


def test_march_cooperation_keeps_authored_quantity_and_physical_owner():
    from fs_bot.cards.card_effects import execute_event
    state = board()
    execute_event(state, 38)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 3, piece_state=rc.REVEALED)
    def choices(state, faction, request):
        if request['kind'] == 'agreement':
            return True
        if request['kind'] == 'diviciacus_pieces':
            return {'counts': {rc.ROMANS: 0, rc.AEDUI: 1}}
    state['decision_agent'] = choose_plan(plan(group(), cooperation=[rc.SEQUANI]), choices)
    _resolve_card70_march_battle(state, [rc.MANDUBII], 4)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces_by_state(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert not state.get('_diviciacus_force')
    assert validate_state(state) == []


def test_refused_march_loan_reoffers_same_stage_without_accepting_again():
    from fs_bot.cards.card_effects import execute_event
    state = board()
    execute_event(state, 38)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    seen = []
    def choose(state, faction, request):
        seen.append(request.get('request_type'))
        if request.get('request_type') == 'roman_event_accept':
            return {'accept': True}
        if request.get('request_type') == 'camulogenus_march':
            return plan(group(), cooperation=[rc.SEQUANI] if request['attempt'] == 1 else [])
        if request['kind'] == 'agreement':
            return False
    state['decision_agent'] = choose
    _resolve_card70_march_battle(state, [rc.MANDUBII], 4)
    assert seen.count('roman_event_accept') == 1
    assert seen.count('camulogenus_march') == 2
    assert seen.count('diviciacus') == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2


def test_explicit_default_with_refused_loan_reoffers_march():
    from fs_bot.cards.card_effects import execute_event
    state = board()
    execute_event(state, 38)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    attempts = []
    def choose(state, faction, request):
        if request.get('request_type') == 'roman_event_accept':
            return {'accept': True}
        if request.get('request_type') == 'camulogenus_march':
            attempts.append(request['attempt'])
            return {'use_default': True} if request['attempt'] == 1 else plan(group())
        if request.get('request_type') == 'diviciacus_command':
            return True
        if request.get('request_type') == 'diviciacus':
            return False
    state['decision_agent'] = choose
    _resolve_card70_march_battle(state, [rc.MANDUBII], 4)
    assert attempts == [1, 2]
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2


def test_invalid_later_battle_rolls_back_march_and_rng():
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    def later(state, faction, request):
        if request.get('request_type') == 'fixed_event_battle':
            assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
            return {'region': rc.SEQUANI, 'defender': rc.BELGAE}
    state['decision_agent'] = choose_plan(plan(group()), later)
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    with pytest.raises(ValueError):
        _resolve_card70_march_battle(state, [rc.MANDUBII], 4)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_validation_routes_are_pure_and_allow_caesar_third_region():
    state = board()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    state['decision_agent'] = lambda *args: pytest.fail('Route preview consumed a live choice')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    response = plan(group(rc.PROVINCIA, [rc.SEQUANI, rc.MANDUBII, rc.CARNUTES], caesar=True),
                    destination=rc.CARNUTES)
    assert validate_response(state, make_request(state), response) is None
    response['marches'][0]['caesar'] = False
    assert validate_response(state, make_request(state), response)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('mutate', [
    lambda p: p.update(destination=rc.SEQUANI),
    lambda p: p.update(dropoffs={}),
    lambda p: p['marches'][0].update(auxilia=True),
    lambda p: p['marches'][0].update(caesar=1),
    lambda p: p['marches'][0].update(route=[]),
    lambda p: p['marches'][0].update(route=[rc.CARNUTES]),
    lambda p: p['marches'][0].update(auxilia=3),
    lambda p: p['marches'].append(group(auxilia=2)),
    lambda p: p.update(diviciacus_regions=[rc.SEQUANI]),
    lambda p: p['marches'][0].update(leader=rc.SUCCESSOR),
])
def test_invalid_typed_selection_never_mutates_live_board_or_rng(mutate):
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    response = plan(group())
    mutate(response)
    before = encode(state)
    assert validate_response(state, make_request(state), response)
    assert encode(state) == before


def test_total_four_legions_spans_multiple_origins():
    state = board()
    for origin in (rc.SEQUANI, rc.AEDUI_REGION):
        place_piece(state, origin, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
    response = plan(group(legions=2, auxilia=0), group(rc.AEDUI_REGION, legions=2, auxilia=0))
    assert validate_response(state, make_request(state), response) is None
    response['marches'][1]['legions'] = 3
    assert 'four Legions' in validate_response(state, make_request(state), response)


@pytest.mark.parametrize('human_default', [False, True])
@pytest.mark.parametrize('resident_piece', [rc.LEGION, rc.FORT])
def test_default_still_battles_residents_when_harassment_destroys_moving_group(human_default, resident_piece):
    state = board()
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    if not human_default:
        state['non_player_factions'].add(rc.ROMANS)
    else:
        state['decision_agent'] = lambda s, f, r: (
            {'use_default': True} if r['kind'] == 'free_action' else None)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, resident_piece,
                **({'from_legions_track': True} if resident_piece == rc.LEGION else {}))
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    result = _resolve_card70_march_battle(state, [rc.CARNUTES], 4)[0]
    # The March is partial; the independently granted Battle remains legal
    # with the Roman Legion already at the chosen destination (§5.1.3).
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert result['free_action'] == 'march_battle'
    assert result['region'] == rc.CARNUTES and result['defender'] == rc.BELGAE
    assert validate_state(state) == []


def test_default_still_battles_residents_when_mover_removed_before_first_step():
    from fs_bot.engine import action_windows, voluntary_removal
    from fs_bot.tests.test_march_action_windows import Agent
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    def choose(agent, state, faction, request):
        if request['kind'] == 'free_action':
            return {'use_default': True}
        if (request['kind'] == 'voluntary_removal' and not agent.did
                and request.get('window', {}).get('stage') == 'march_before_plan'):
            selected = next(c for c in request['options']
                            if c['region'] == rc.SEQUANI and c['piece_type'] == rc.AUXILIA)
            agent.did = True
            return {'operations': [voluntary_removal.operation(selected)]}
    state['decision_agent'] = Agent(choose)
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        result = _resolve_card70_march_battle(state, [rc.CARNUTES], 4)[0]
    assert state['decision_agent'].did
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert result['free_action'] == 'march_battle'
    assert result['defender'] == rc.BELGAE
    assert validate_state(state) == []


def test_human_default_recognizes_static_only_battle_without_any_march_group():
    state = board()
    state['decision_agent'] = lambda s, f, r: (
        {'use_default': True} if r['kind'] == 'free_action' else None)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    result = _resolve_card70_march_battle(state, [rc.CARNUTES], 4)[0]
    assert result['free_action'] == 'march_battle'
    assert result['region'] == rc.CARNUTES and result['defender'] == rc.BELGAE
    assert result['moved'] == {'legions': 0, 'auxilia': 0}
    assert validate_state(state) == []
