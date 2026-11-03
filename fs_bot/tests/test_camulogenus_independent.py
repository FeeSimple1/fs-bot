"""Independent checks of numeric70's Roman-owned March-and-Battle grant.

Card Reference 70 and its Tips; §§3.2.2, 5.1.3 and 5.4. These use the
existing Event executor and physical board, so failures on the parent
demonstrate behavior rather than the absence of a newly introduced API.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region, place_piece,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=17)
    state['non_player_factions'] = set()
    state['current_card'] = 70
    state['event_params'] = {}
    state['executing_faction'] = None
    state['resources'][rc.ROMANS] = 9
    return state


def snapshot(state):
    return encode({key: value for key, value in state.items()
                   if key != 'decision_agent'})


def troops(state, region, *, legions=0, auxilia=0, visibility=rc.HIDDEN):
    if legions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, legions,
                    from_legions_track=True)
    if auxilia:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia,
                    piece_state=visibility)


def group(origin, route, *, legions=0, auxilia=0, caesar=False):
    return {'origin': origin, 'route': route, 'legions': legions,
            'auxilia': auxilia, 'caesar': caesar}


def plan(destination, *marches):
    return {'destination': destination, 'marches': list(marches)}


def install_agent(state, march, *, accept=True, defender=None, hook=None):
    requests = []

    def agent(current, actor, request):
        requests.append((actor, deepcopy(request)))
        if hook is not None:
            handled, response = hook(current, actor, request)
            if handled:
                return response
        kind = request.get('request_type')
        if kind == 'roman_event_accept':
            return {'accept': True} if accept else {'decline': True}
        if kind == 'camulogenus_march':
            return deepcopy(march)
        if kind == 'fixed_event_battle' and defender is not None:
            return {'region': march['destination'], 'defender': defender}
        if request.get('kind') == 'retreat':
            return {'retreat': False, 'region': None}
        return None

    state['decision_agent'] = agent
    return requests


def apply(state, actor=rc.BELGAE):
    return ex._execute_event(state, actor, {
        'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': 70, 'text_preference': rc.EVENT_UNSHADED,
                    'event_params': {}}}, human=True)


def test_foreign_executor_cannot_force_declined_roman_march_or_battle():
    state = board()
    troops(state, rc.MORINI, legions=2, auxilia=3)
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 4)
    march = plan(rc.ATREBATES, group(rc.MORINI, [rc.ATREBATES], legions=2, auxilia=3))
    seen = install_agent(state, march, accept=False, defender=rc.ARVERNI)
    before = deepcopy((state['spaces'], state['available'], state['resources'], state['rng'].getstate()))

    assert apply(state)['executed']

    assert [(actor, req['request_type']) for actor, req in seen
            if req.get('kind') == 'free_action'] == [(rc.ROMANS, 'roman_event_accept')]
    assert (state['spaces'], state['available'], state['resources'], state['rng'].getstate()) == before


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
def test_two_origins_share_four_legion_budget_and_keep_unchosen_auxilia(edition):
    state = board()
    state['card_edition'] = edition
    troops(state, rc.MORINI, legions=3, auxilia=3)
    troops(state, rc.CARNUTES, legions=3, auxilia=4)
    march = plan(rc.ATREBATES,
                 group(rc.MORINI, [rc.ATREBATES], legions=2, auxilia=1),
                 group(rc.CARNUTES, [rc.ATREBATES], legions=2, auxilia=2))
    seen = install_agent(state, march)

    result = apply(state)

    assert result['executed'] and not result.get('rejected')
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.LEGION) == 4
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert all(actor == rc.ROMANS for actor, req in seen if req.get('kind') == 'free_action')
    assert state['resources'][rc.ROMANS] == 9
    assert validate_state(state) == []


def test_human_can_split_same_origin_groups_between_legal_routes():
    state = board()
    troops(state, rc.MANDUBII, auxilia=4)
    march = plan(rc.ATREBATES,
                 group(rc.MANDUBII, [rc.ATREBATES], auxilia=1),
                 group(rc.MANDUBII, [rc.CARNUTES, rc.ATREBATES], auxilia=2))
    install_agent(state, march)

    assert apply(state)['executed']

    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_selected_revealed_auxilia_flip_but_unchosen_origin_and_transit_pieces_do_not():
    state = board()
    troops(state, rc.MORINI, auxilia=2)
    troops(state, rc.MORINI, auxilia=3, visibility=rc.REVEALED)
    troops(state, rc.ATREBATES, auxilia=1, visibility=rc.REVEALED)
    march = plan(rc.CARNUTES, group(rc.MORINI, [rc.ATREBATES, rc.CARNUTES], auxilia=2))

    def pick_revealed(current, actor, request):
        if request.get('kind') == 'march_cohort':
            return True, {'counts': {rc.REVEALED: 2}}
        return False, None

    seen = install_agent(state, march, hook=pick_revealed)
    assert apply(state)['executed']
    assert len([req for _, req in seen if req.get('kind') == 'march_cohort']) == 1
    assert count_pieces_by_state(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2


def test_empty_march_keeps_stationary_auxilia_revealed_when_no_battle_exists():
    state = board()
    troops(state, rc.CARNUTES, auxilia=3, visibility=rc.REVEALED)
    seen = install_agent(state, plan(rc.CARNUTES))

    assert apply(state)['executed']

    assert any(req.get('request_type') == 'camulogenus_march' for _, req in seen)
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 3
    assert not any(req.get('request_type') == 'fixed_event_battle' for _, req in seen)


def test_empty_march_can_battle_with_residents_at_the_chosen_destination():
    state = board()
    troops(state, rc.CARNUTES, legions=2, auxilia=2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    seen = install_agent(state, plan(rc.CARNUTES), defender=rc.BELGAE)

    assert apply(state, rc.ARVERNI)['executed']

    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 0
    battles = [req for _, req in seen if req.get('request_type') == 'fixed_event_battle']
    assert len(battles) == 1 and not battles[0]['allow_decline']
    assert state['resources'][rc.ROMANS] == 9


def test_caesar_can_accompany_the_selected_force_into_a_third_region():
    state = board()
    troops(state, rc.PROVINCIA, legions=2, auxilia=3)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    march = plan(rc.CARNUTES, group(rc.PROVINCIA,
                 [rc.AEDUI_REGION, rc.BITURIGES, rc.CARNUTES], legions=1, auxilia=1, caesar=True))
    install_agent(state, march)

    assert apply(state)['executed']

    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('bad', [
    plan(rc.ATREBATES, group(rc.MORINI, [rc.ATREBATES], legions=3),
         group(rc.CARNUTES, [rc.ATREBATES], legions=2)),
    plan(rc.ATREBATES, group(rc.MORINI, [rc.ATREBATES], legions=True)),
    plan(rc.ATREBATES, group(rc.MORINI, [rc.ATREBATES], auxilia=-1)),
    plan(rc.CARNUTES, group(rc.MORINI, [rc.ATREBATES], auxilia=1)),
    plan(rc.CARNUTES, group(rc.MORINI, [rc.CARNUTES], auxilia=1)),
    plan(rc.PICTONES, group(rc.CARNUTES, [rc.PICTONES], auxilia=1)),
    plan(rc.CARNUTES, dict(group(rc.MORINI, [rc.ATREBATES, rc.CARNUTES], auxilia=2),
                          dropoffs={rc.ATREBATES: {rc.AUXILIA: 1}})),
    dict(plan(rc.CARNUTES), extra_losses=99),
])
def test_invalid_march_plans_reject_before_any_board_or_random_change(bad):
    state = board()
    troops(state, rc.MORINI, legions=3, auxilia=3)
    troops(state, rc.CARNUTES, legions=3, auxilia=3)
    install_agent(state, bad)
    before = snapshot(state)

    result = apply(state)

    assert result.get('rejected') and not result['executed']
    assert snapshot(state) == before


@pytest.mark.parametrize('leader,caesar', [(None, False), (rc.CAESAR, False), (rc.SUCCESSOR, True)])
def test_third_step_requires_caesar_in_the_actual_moving_group(leader, caesar):
    state = board()
    troops(state, rc.PROVINCIA, auxilia=2)
    if leader:
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=leader)
    march = plan(rc.CARNUTES, group(rc.PROVINCIA,
                 [rc.AEDUI_REGION, rc.BITURIGES, rc.CARNUTES], auxilia=1, caesar=caesar))
    install_agent(state, march)
    before = snapshot(state)

    assert apply(state).get('rejected')
    assert snapshot(state) == before


def test_diviciacus_loan_moves_only_the_selected_count_with_physical_ownership():
    state = board()
    troops(state, rc.CARNUTES, auxilia=2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    execute_event(state, 38)
    march = plan(rc.MANDUBII, group(rc.CARNUTES, [rc.MANDUBII], auxilia=1))
    march['diviciacus_regions'] = [rc.CARNUTES]

    def consent_and_owner(current, actor, request):
        if request.get('kind') == 'agreement':
            return True, True
        if request.get('kind') == 'diviciacus_pieces':
            return True, {'counts': {rc.AEDUI: 1}}
        return False, None

    seen = install_agent(state, march, hook=consent_and_owner)
    result = apply(state)

    assert result['executed'] and not result.get('rejected')
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert any(req.get('kind') == 'diviciacus_pieces' for _, req in seen)
    assert validate_state(state) == []


def test_optional_diviciacus_stays_put_and_only_selected_scouted_loan_loses_marker():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=17, diviciacus_option=True)
    state['non_player_factions'] = set()
    state['current_card'] = 70
    troops(state, rc.CARNUTES, auxilia=1)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    state['event_params'] = {'region': rc.CARNUTES}
    execute_event(state, rc.CARD_O38)
    state['event_params'] = {}
    march = plan(rc.MANDUBII, group(rc.CARNUTES, [rc.MANDUBII], auxilia=1))
    march['diviciacus_regions'] = [rc.CARNUTES]

    def consent_and_owner(current, actor, request):
        if request.get('kind') == 'agreement':
            return True, True
        if request.get('kind') == 'diviciacus_pieces':
            return True, {'counts': {rc.AEDUI: 1}}
        return False, None

    install_agent(state, march, hook=consent_and_owner)
    assert apply(state)['executed']

    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces_by_state(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_resident_force_still_battles_after_marching_group_is_destroyed_in_transit():
    state = board()
    troops(state, rc.MORINI, auxilia=1)
    troops(state, rc.CARNUTES, legions=2)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    march = plan(rc.CARNUTES, group(rc.MORINI, [rc.ATREBATES, rc.CARNUTES], auxilia=1))
    seen = install_agent(state, march, defender=rc.BELGAE)

    assert apply(state)['executed']

    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 0
    assert any(req.get('request_type') == 'fixed_event_battle' for _, req in seen)
    assert validate_state(state) == []


def test_march_validation_does_not_consume_live_decisions_or_randomness():
    from fs_bot.engine.free_actions import validate_free_action_response
    state = board()
    troops(state, rc.MORINI, auxilia=3)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 3)
    march = plan(rc.CARNUTES, group(rc.MORINI, [rc.ATREBATES, rc.CARNUTES], auxilia=2))
    trial = deepcopy(state)
    seen = install_agent(trial, march)
    assert apply(trial)['executed']
    request = next(req for _, req in seen if req.get('request_type') == 'camulogenus_march')
    state['decision_agent'] = lambda *_: pytest.fail('Validation consumed a live decision')
    before = snapshot(state)

    assert validate_free_action_response(state, rc.ROMANS, request, march) is None
    assert snapshot(state) == before


def test_refused_loan_requires_new_march_without_silently_changing_the_requested_count():
    state = board()
    troops(state, rc.CARNUTES, auxilia=1)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    execute_event(state, 38)
    borrowed = plan(rc.MANDUBII, group(rc.CARNUTES, [rc.MANDUBII], auxilia=2))
    borrowed['diviciacus_regions'] = [rc.CARNUTES]
    replacement = plan(rc.MANDUBII, group(rc.CARNUTES, [rc.MANDUBII], auxilia=1))
    attempts = []

    def refuse_and_replan(current, actor, request):
        if request.get('kind') == 'agreement':
            return True, False
        if request.get('request_type') == 'camulogenus_march':
            attempts.append(deepcopy(request))
            if len(attempts) == 2:
                assert count_pieces(current, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
                assert count_pieces(current, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
            return True, borrowed if len(attempts) == 1 else replacement
        return False, None

    install_agent(state, borrowed, hook=refuse_and_replan)
    assert apply(state)['executed']

    assert len(attempts) == 2 and attempts[1].get('previous_error')
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 0
    assert validate_state(state) == []


def test_reclaiming_later_frozen_group_cannot_replace_it_with_residents_or_arrivals():
    from fs_bot.engine import action_windows, voluntary_removal
    state = board()
    troops(state, rc.MORINI, auxilia=1)
    troops(state, rc.ATREBATES, auxilia=2)
    march = plan(rc.CARNUTES,
                 group(rc.MORINI, [rc.ATREBATES, rc.CARNUTES], auxilia=1),
                 group(rc.ATREBATES, [rc.CARNUTES], auxilia=1))
    removed = []

    def reclaim(current, actor, request):
        if request.get('kind') == 'voluntary_removal':
            if not removed and request.get('window', {}).get('stage') == 'march_arrival':
                choice = next(item for item in request['options']
                              if item.get('cohort') == '70.group.2')
                removed.append(choice)
                return True, {'operations': [voluntary_removal.operation(choice)]}
            return True, {'done': True}
        if request.get('kind') == 'spring_leader':
            return True, {'defer': True}
        return False, None

    install_agent(state, march, hook=reclaim)
    state['decision_agent'].supports_action_windows = True
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        result = apply(state, rc.ROMANS)

    assert result['executed'] and removed
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0
    assert '_action_window_cohorts' not in state
    assert validate_state(state) == []

