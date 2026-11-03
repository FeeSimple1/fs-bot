"""Card Reference 35S, 46S, 67: beneficiary-owned mandatory actions/order."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.gallic_event_grants import (beneficiary_request, order_request,
    command_request, command_witness)
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy


def board(card=35, scenario=rc.SCENARIO_GREAT_REVOLT):
    st = build_initial_state(scenario, seed=35046)
    st.update(current_card=card, next_card=47, executing_faction=rc.ROMANS, event_params=None)
    st['non_player_factions'] = set()
    st['resources'][rc.AEDUI] = 0
    _ally_tribe(st, rc.TRIBE_AEDUI, rc.AEDUI)
    _ally_tribe(st, rc.TRIBE_SEQUANI, rc.AEDUI)
    return st


def event(st, card=35, params=None, side=rc.EVENT_SHADED, executor=rc.ROMANS):
    return _execute_event(st, executor, {'command': 'Event', 'details': {
        'card_id': card, 'text_preference': side,
        'event_params': {} if params is None else params}}, human=True)


def rally(*regions):
    return {'command': rc.CMD_RALLY, 'regions': list(regions), 'sa': 'No SA', 'sa_regions': [],
            'details': {'rally_plan': {'steps': [{'region': r, 'action': 'place_warbands', 'count': 1}
                                              for r in regions]}}}


@pytest.mark.parametrize('order', [['command', 'limited_command'], ['limited_command', 'command']])
def test_executor_selects_gallic_recipient_who_selects_each_order_and_commands(order):
    st = board(); seen = []
    def agent(state, actor, request):
        seen.append((actor, request['request_type'], request.get('max_regions')))
        if request['request_type'] == 'gallic_event_beneficiary':
            assert actor == rc.ROMANS
            return {'faction': rc.AEDUI}
        assert actor == rc.AEDUI
        if request['request_type'] == 'gallic_command_order':
            return {'order': order}
        assert rc.CMD_BATTLE not in request['allowed_commands']
        assert request['with_sa'] is False and request['allow_decline'] is False
        return rally(rc.AEDUI_REGION) if request['max_regions'] == 1 else rally(rc.AEDUI_REGION, rc.SEQUANI)
    st['decision_agent'] = agent
    result = event(st)
    assert result['executed'], result.get('reason', result)
    assert [r['kind'] for r in result['free_actions']] == order
    assert [row[2] for row in seen[-2:]] == [1 if kind == 'limited_command' else None for kind in order]
    assert count_pieces(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert st['resources'][rc.AEDUI] == 0 and validate_state(st) == []


def test_celtic_rites_gives_full_command_to_recipient_but_eligibility_to_executor():
    st = board(46); st['eligibility'][rc.AEDUI] = rc.INELIGIBLE
    st['eligibility'][rc.ROMANS] = rc.INELIGIBLE
    def agent(state, actor, request):
        assert actor == rc.AEDUI and request['max_regions'] is None
        assert rc.CMD_BATTLE in request['allowed_commands']
        return rally(rc.AEDUI_REGION, rc.SEQUANI)
    st['decision_agent'] = agent
    result = event(st, 46, {'faction': rc.AEDUI})
    assert result['executed'], result.get('reason', result)
    assert st['eligibility'][rc.ROMANS] == rc.ELIGIBLE
    assert st['eligibility'][rc.AEDUI] == rc.INELIGIBLE
    assert st['stay_eligible'] == [rc.ROMANS]
    assert count_pieces(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1


@pytest.mark.parametrize('response', [{'decline': True}, {'use_default': 1}, {'faction': rc.ROMANS},
                                     {'faction': rc.GERMANS}, {'faction': rc.AEDUI, 'order': []}])
def test_beneficiary_validation_is_strict_and_preserves_board_rng(response):
    st = board(); before = encode(st)
    assert validate_free_action_response(st, rc.ROMANS, beneficiary_request(35), response)
    assert encode(st) == before


@pytest.mark.parametrize('response', [{'decline': True}, {'order': ['command', 'command']},
                                     {'order': ('command', 'limited_command')}, {'order': []}])
def test_order_validation_requires_exact_two_different_command_grants(response):
    st = board()
    assert validate_free_action_response(st, rc.AEDUI, order_request(), response)


@pytest.mark.parametrize('change', ['battle', 'sa', 'parts', 'two_regions', 'decline'])
def test_limited_gallic_command_cannot_escape_card_restrictions(change):
    st = board(); action = rally(rc.AEDUI_REGION)
    if change == 'battle': action['command'] = rc.CMD_BATTLE
    elif change == 'sa': action['sa'] = rc.SA_TRADE
    elif change == 'parts': action['details']['command_parts'] = [rally(rc.SEQUANI)]
    elif change == 'two_regions': action = rally(rc.AEDUI_REGION, rc.SEQUANI)
    else: action = {'decline': True}
    before = encode(st)
    assert validate_free_action_response(st, rc.AEDUI, command_request(rc.AEDUI, 35, limited=True), action)
    assert encode(st) == before


@pytest.mark.parametrize('card', [35, 46, 67])
@pytest.mark.parametrize('params', [{'faction': rc.GERMANS}, {'order': ['command','limited_command']},
                                    {'flip_hidden_regions': [rc.TREVERI]},
                                    {'stage_timing_actions': {'unknown.stage': []}}])
def test_executor_cannot_pre_author_recipient_decisions(card, params):
    st = board(card); before = encode(st)
    result = event(st, card, params)
    assert result['rejected'] and encode(st) == before


@pytest.mark.parametrize('card', [35, 46])
def test_game_run_arverni_at_peace_skips_commands_without_owner_prompts(card):
    st = board(card, rc.SCENARIO_ARIOVISTUS); seen = []
    st['decision_agent'] = lambda *args: seen.append(args[-1])
    before = deepcopy((st['spaces'], st['resources']))
    result = event(st, card, {'faction': rc.ARVERNI})
    assert result['executed'], result
    assert not seen and (st['spaces'], st['resources']) == before
    assert all(not entry['result']['executed'] and entry['result']['provisional_ruling'] == 'PR-10'
               for entry in result['free_actions'])


def test_ordinary_celtic_command_witness_does_not_require_bot_preference():
    st = board(46); before = encode(st)
    request = command_request(rc.AEDUI, 46)
    witness = command_witness(st, rc.AEDUI, request)
    assert witness and validate_free_action_response(st, rc.AEDUI, request, witness) is None
    assert encode(st) == before


def test_no_force_battle_cannot_discharge_mandatory_command():
    st = board(46); place_piece(st, rc.TREVERI, rc.AEDUI, rc.WARBAND)
    request = command_request(rc.ROMANS, 46)
    action = {'command': rc.CMD_BATTLE, 'regions': [rc.TREVERI], 'sa': 'No SA',
              'details': {'battle_plan': [{'region': rc.TREVERI, 'target': rc.AEDUI}]}}
    assert validate_free_action_response(st, rc.ROMANS, request, action)


def test_arduenna_explicit_default_contains_only_public_march_groups():
    from fs_bot.cards.arduenna import default_march, march_request
    st = board(67); place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
    action = default_march(st, rc.AEDUI)
    assert action and validate_free_action_response(st, rc.AEDUI, march_request(67), action) is None
    group = action['details']['march_plan']['groups'][rc.ATREBATES]
    assert not any(key.startswith('_') for key in group)


def test_no_forces_cannot_create_arduenna_battle_witness():
    from fs_bot.cards.arduenna import command_witness
    st = board(67); place_piece(st, rc.TREVERI, rc.AEDUI, rc.WARBAND)
    assert command_witness(st, rc.ROMANS) is None


def test_arduenna_equal_strength_origins_use_seeded_choice_and_default_preview_is_pure():
    from fs_bot.cards.arduenna import default_march, march_request
    import random
    selected = set()
    for seed in range(12):
        st = board(67)
        # Both origins adjoin Nervii; its residents prevent a second march
        # from obscuring which equal-strength origin was selected first.
        place_piece(st, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
        place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 2)
        place_piece(st, rc.TREVERI, rc.AEDUI, rc.WARBAND)
        st['rng'] = random.Random(seed)
        twin = deepcopy(st); before = encode(st)
        assert validate_free_action_response(st, rc.AEDUI, march_request(67), {'use_default': True}) is None
        assert encode(st) == before
        action = default_march(st, rc.AEDUI)
        assert action == default_march(twin, rc.AEDUI)
        assert st['rng'].getstate() == twin['rng'].getstate()
        selected.add(action['regions'][0])
    assert selected == {rc.MORINI, rc.ATREBATES}


@pytest.mark.parametrize('card,step', [(46, '46.command'), (67, '67.hide')])
def test_foreign_executor_retains_authored_reclamation_at_outer_event_steps(card, step):
    from fs_bot.engine.action_windows import scope
    st = board(card)
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    if card == 67:
        place_piece(st, rc.TREVERI, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    def agent(state, actor, request):
        if request['request_type'] == 'arduenna_accept': return {'accept': True}
        if request['request_type'] == 'arduenna_march':
            return {'command': rc.CMD_MARCH, 'regions': [rc.TREVERI], 'sa': 'No SA',
                    'details': {'march_plan': {'origins': [rc.TREVERI], 'destinations': [rc.NERVII],
                                              'routes': {rc.TREVERI: [rc.NERVII]}}}}
        if request['request_type'] == 'arduenna_command':
            return {'command': rc.CMD_RAID, 'regions': [rc.NERVII], 'sa': 'No SA',
                    'details': {'raid_plan': [{'region': rc.NERVII, 'target': None}]}}
        return rally(rc.AEDUI_REGION)
    st['decision_agent'] = agent
    from fs_bot.engine.voluntary_removal import options, operation
    choice = next(c for c in options(st, rc.ROMANS) if c['region'] == rc.PROVINCIA)
    params = {'faction': rc.AEDUI, 'stage_timing_actions': {step: [
        {'kind': 'voluntary_removal', 'response': {'operations': [operation(choice)]}}]}}
    with scope(st, actor=rc.ROMANS, plan=params, force=True):
        result = event(st, card, params)
    assert result['executed'], result.get('reason', result)
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert validate_state(st) == []


def test_recipient_cannot_reclaim_its_own_pieces_during_another_factions_event():
    from fs_bot.engine.action_windows import scope
    st = board(46); place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    action = rally(rc.AEDUI_REGION)
    action['details']['rally_plan']['steps'][0]['timing_actions'] = [
        {'kind': 'voluntary_removal', 'response': {'pieces': [
            {'region': rc.SEQUANI, 'piece_type': rc.WARBAND, 'count': 1, 'piece_state': rc.HIDDEN}]}}]
    with scope(st, actor=rc.ROMANS, force=True):
        before = encode(st)
        error = validate_free_action_response(st, rc.AEDUI, command_request(rc.AEDUI, 46), action)
        assert error and 'Only the executing player' in error
        assert encode(st) == before


def test_arverni_np_arduenna_without_possible_legion_loss_declines_without_hiding():
    from fs_bot.cards.gallic_event_grants import default_arduenna
    st = board(67)
    st['non_player_factions'] = {rc.ARVERNI}
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND)
    place_piece(st, rc.TREVERI, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(st, rc.TREVERI, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    result = default_arduenna(st, rc.ARVERNI)
    assert result == []
    assert count_pieces_by_state(st, rc.TREVERI, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces_by_state(st, rc.TREVERI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(st, rc.TREVERI, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0
    assert validate_state(st) == []
