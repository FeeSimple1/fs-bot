"""A submitted human plan must execute within its Sequence-of-Play scope."""

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.engine import game_engine as ge
from fs_bot.engine import spring
from fs_bot.engine.execute import execute_decision
from fs_bot.state.serialize import decode, encode, load_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import validate_response


def position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=2)
    state['resources'].update({rc.ROMANS: 20, rc.AEDUI: 20, rc.ARVERNI: 20})
    return state


def decision(action_type, command, details=None, **plan):
    return {'action': action_type, 'player_action': {
        'command': command, 'details': details or {}, **plan}}


def assert_rejected(state, faction, submitted, reason):
    before = encode(state)
    request = {'kind': 'turn', 'faction': faction, 'options': [submitted['action']]}
    with pytest.raises(ValueError, match=reason):
        validate_response(state, request, submitted)
    result = execute_decision(state, faction, submitted)
    assert result['rejected'] and not result['executed']
    assert reason in result['reason']
    assert encode(state) == before


def event(action_type=ge.ACTION_EVENT, **details):
    return decision(action_type, rc.FIRST_DID_EVENT, details)


def submit(args, pending, response):
    submission = SimpleNamespace(dir=args.dir, decision_id=pending['id'],
                                 response=json.dumps(response))
    assert llm_seat.cmd_submit(submission) == 0


def advance_to_turn(args, path):
    for _ in range(30):
        state, meta, log = load_game(path, validate=True)
        pending = meta['assistant_session']['pending']
        if decode(pending['request'])['kind'] == 'turn':
            return state, meta['assistant_session'], log
        submit(args, pending, {'use_default': True})
    pytest.fail('The assistant did not reach a turn.')


@pytest.mark.parametrize('seat,invalid,reason', [
    (rc.BELGAE, event(ge.ACTION_LIMITED_COMMAND, event_params={'target_region': rc.PROVINCIA}),
     'match the chosen Command or Event'),
    (rc.ROMANS, event(card_id=13), 'current Event card'),
])
def test_normal_assistant_rejects_wrong_action_or_card_and_replays_correction(
        tmp_path, capsys, seat, invalid, reason):
    args = SimpleNamespace(dir=str(tmp_path / 'game'), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seed=46, seat=seat, output_dir=str(tmp_path / 'replay'))
    path = tmp_path / 'game' / 'save.json'
    llm_seat.cmd_init(args)
    assert llm_seat.cmd_play(args) == 0
    state, session, log = advance_to_turn(args, path)
    pending = session['pending']
    assert state['current_card'] == 16
    assert invalid['action'] in decode(pending['request'])['options']

    capsys.readouterr()
    submit(args, pending, invalid)
    assert reason in capsys.readouterr().out
    rejected, meta, rejected_log = load_game(path, validate=True)
    assert encode(rejected) == encode(state)
    assert meta['assistant_session']['pending'] == pending
    assert meta['assistant_session']['journal'] == session['journal']
    assert rejected_log == log

    correction = event(event_params={'target_region': rc.PROVINCIA}) if seat == rc.ROMANS else {
        'action': ge.ACTION_PASS}
    submit(args, pending, correction)
    final, _, final_log = advance_to_turn(args, path)
    accepted = next(entry for entry in final_log if entry.get('assistant_id') == pending['id'])
    assert decode(accepted['assistant_response']) == correction
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, replayed_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(final) and replayed_log == final_log


def test_card_turn_rejects_a_well_formed_event_when_only_limited_command_is_offered():
    state = position()
    state['current_card'] = 16
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['eligibility'] = {faction: (rc.ELIGIBLE if faction in (rc.ROMANS, rc.BELGAE)
                                    else rc.INELIGIBLE) for faction in state['eligibility']}
    checkpoint = None

    def choose(board, faction, options, slot):
        nonlocal checkpoint
        if faction == rc.ROMANS:
            return decision(ge.ACTION_COMMAND, rc.CMD_SEIZE,
                            {'disperse_tribes': {rc.PROVINCIA: []}}, regions=[rc.PROVINCIA])
        assert options == [ge.ACTION_LIMITED_COMMAND, ge.ACTION_PASS]
        checkpoint = encode(board)
        return event(card_id=16, event_params={'target_region': rc.PROVINCIA})

    with pytest.raises(ge.ActionRejected, match='offered actions'):
        ge.resolve_card_turn(state, choose, execute=True)
    assert encode(state) == checkpoint
    assert list(state['_card_turn']['actions_taken']) == [rc.ROMANS]


def test_event_and_command_labels_cannot_attach_an_extra_special_ability():
    state = position()
    state['current_card'] = 16
    assert_rejected(state, rc.ROMANS, decision(ge.ACTION_EVENT, rc.FIRST_DID_EVENT,
                    sa=rc.SA_SCOUT), 'through that Event')
    assert_rejected(state, rc.AEDUI, decision(ge.ACTION_COMMAND, rc.CMD_RALLY,
                    {'rally_plan': {'warbands': [rc.AEDUI_REGION]}}, sa=rc.SA_TRADE),
                    'include a Special Ability')
    assert_rejected(state, rc.AEDUI, decision(ge.ACTION_EVENT, rc.CMD_RALLY,
                    {'rally_plan': {'warbands': [rc.AEDUI_REGION]}}),
                    'match the chosen Command or Event')


@pytest.mark.parametrize('scenario,current,submitted', [
    (rc.SCENARIO_GREAT_REVOLT, 'O38', 38),
    (rc.SCENARIO_ARIOVISTUS, 'A38', 38),
    (rc.SCENARIO_GREAT_REVOLT, 1, True),
])
def test_event_requires_the_exact_current_card_id(scenario, current, submitted):
    state = position(scenario)
    state['current_card'] = current
    assert_rejected(state, rc.AEDUI, event(card_id=submitted), 'current Event card')
    request = {'kind': 'turn', 'faction': rc.AEDUI, 'options': [ge.ACTION_EVENT]}
    matching = event(card_id=current)
    assert validate_response(state, request, matching) == matching


def test_limited_recruit_rejects_an_inactive_command_parts_list():
    state = position()
    for region in (rc.PROVINCIA, rc.SEQUANI):
        place_piece(state, region, rc.ROMANS, rc.FORT)
    placements = [{'region': region, 'action': 'place_auxilia', 'count': 1}
                  for region in (rc.PROVINCIA, rc.SEQUANI)]
    one_region = {'command': rc.CMD_RECRUIT, 'details': {'recruit_plan': placements[:1]}}
    limited = ge.ACTION_LIMITED_COMMAND
    assert_rejected(state, rc.ROMANS, decision(limited, rc.CMD_RECRUIT, {
        'recruit_plan': placements, 'command_parts': [one_region]}), 'exactly two portions')
    legal = decision(limited, rc.CMD_RECRUIT, {'recruit_plan': placements[:1]})
    assert execute_decision(state, rc.ROMANS, legal)['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('entries,reason', [
    ([{'region': rc.CARNUTES, 'target': rc.ARVERNI},
      {'region': rc.CARNUTES, 'target': rc.AEDUI}], 'Battle Region only once'),
    ([{'region': rc.CARNUTES, 'target': rc.ROMANS}], 'opposing Faction'),
    ([{'region': rc.CARNUTES, 'targets': [rc.ROMANS, rc.ARVERNI]}], 'opposing Faction'),
])
def test_battle_requires_one_opposing_defender_in_each_distinct_region(entries, reason):
    state = position()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    for enemy in (rc.ARVERNI, rc.AEDUI):
        place_piece(state, rc.CARNUTES, enemy, rc.WARBAND)
    assert validate_state(state) == []
    assert_rejected(state, rc.ROMANS, decision(ge.ACTION_LIMITED_COMMAND, rc.CMD_BATTLE,
                    {'battle_plan': entries}), reason)
    legal = decision(ge.ACTION_LIMITED_COMMAND, rc.CMD_BATTLE, {'battle_plan': [
        {'region': rc.CARNUTES, 'targets': [rc.ARVERNI, rc.AEDUI]}]})
    result = execute_decision(state, rc.ROMANS, legal)
    assert result['battles_resolved'] == [(rc.CARNUTES, rc.ARVERNI)]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI) == 1


@pytest.mark.parametrize('plan,reason', [
    ({'explicit_moves': [{'origin': rc.CARNUTES, 'path': [rc.VENETI]},
                         {'origin': rc.MANDUBII, 'path': [rc.TREVERI]}]}, 'at most one Region'),
    ({'origins': [rc.CARNUTES], 'destinations': [rc.VENETI], 'routes': {rc.CARNUTES: [rc.VENETI]},
      'extra_groups': [{'origin': rc.MANDUBII, 'route': [rc.TREVERI], 'group': {rc.WARBAND: 1}}]},
     'must use selected origins'),
    ({'origins': [rc.MANDUBII], 'leader_destination': rc.VENETI, 'control_destination': rc.TREVERI},
     'at most one Region'),
])
def test_limited_march_checks_origins_in_each_plan_shape(plan, reason):
    state = position()
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    assert_rejected(state, rc.ARVERNI, decision(ge.ACTION_LIMITED_COMMAND, rc.CMD_MARCH,
                    {'march_plan': plan}), reason)


def test_limited_march_can_move_two_groups_from_one_origin():
    state = position()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    legal = decision(ge.ACTION_LIMITED_COMMAND, rc.CMD_MARCH, {'explicit_moves': [
        {'origin': rc.CARNUTES, 'path': [destination], 'group': {rc.WARBAND: 1}}
        for destination in (rc.VENETI, rc.MANDUBII)]})
    result = execute_decision(state, rc.AEDUI, legal)
    assert result['executed'] and result['origin_costs'] == {rc.CARNUTES: 1}
    assert len(result['marches']) == 2


def test_limited_march_rechecks_origins_after_live_leader_entry():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=2)
    spring.unlock_spring_box_entry(state)
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 3)
    limited = ge.ACTION_LIMITED_COMMAND
    action = decision(limited, rc.CMD_MARCH, {
        'origins': [rc.MANDUBII], 'leader_destination': rc.VENETI,
        'control_destination': rc.TREVERI, 'timing_actions': [
            {'kind': spring.KIND, 'response': {'region': rc.CARNUTES}}]})
    request = {'kind': 'turn', 'faction': rc.ARVERNI, 'options': [limited]}
    before = encode(state)
    # The initial plan can move only from Mandubii. Spring entry adds a
    # second group before the March chooses and pays for its actual origins.
    assert validate_response(state, request, action) == action
    result = execute_decision(state, rc.ARVERNI, action)
    assert result['rejected'] and result['rolled_back']
    assert 'at most one Region' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('timing', ['before', 'after'])
@pytest.mark.parametrize('origin,destination', [(rc.BRITANNIA, rc.MORINI), (rc.MORINI, rc.BRITANNIA)])
def test_explicit_march_cannot_cross_britannia_with_a_special_ability(origin, destination, timing):
    state = position()
    place_piece(state, origin, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    action = decision(ge.ACTION_COMMAND_SA, rc.CMD_MARCH, {
        'explicit_moves': [{'origin': origin, 'path': [destination]}]},
        sa=rc.SA_TRADE, sa_timing=timing)
    assert_rejected(state, rc.AEDUI, action, 'Britannia')


@pytest.mark.parametrize('timing', ['before', 'after', 'during'])
def test_repeated_devastate_is_rejected_before_any_casualties(timing):
    state = position()
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 12)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 9)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    details = {'raid_plan': [{'region': rc.VENETI, 'target': None}]}
    if timing == 'during':
        details['raid_plan'].append({'region': rc.VENETI, 'target': None})
        details['sa_after_step'] = 1
    action = decision(ge.ACTION_COMMAND_SA, rc.CMD_RAID, details, sa=rc.SA_DEVASTATE,
                      sa_timing=timing, sa_regions=[rc.CARNUTES, rc.CARNUTES])
    assert_rejected(state, rc.ARVERNI, action, 'only once for Devastate')
    legal = deepcopy(action)
    legal['player_action']['sa_regions'].pop()
    result = execute_decision(state, rc.ARVERNI, legal)
    assert result['executed'] and result['sa_execution']['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 9
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 6
    assert validate_state(state) == []
