"""CM3-01/03: playable Scout Regions and own Forces for Battle (§§1.4.2, 3, 4.2.2)."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import execute_event
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_scout import scout_move
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA
from fs_bot.state.serialize import decode, encode, load_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import validate_response


def movement(origin=rc.PROVINCIA, target=rc.CISALPINA):
    return {'from_region': origin, 'to_region': target, 'count': 1, 'piece_state': rc.HIDDEN}


def scout_action(moves=None, nested=False):
    plan = {'scout_plan': {'auxilia_moves': moves or [movement()], 'scout_targets': []}}
    return {'command': rc.CMD_SEIZE, 'regions': [rc.PROVINCIA], 'sa': rc.SA_SCOUT,
            'sa_timing': 'before', 'details': {
                'disperse_tribes': {rc.PROVINCIA: []},
                **({'sa_details': plan} if nested else plan)}}


@pytest.mark.parametrize('nested', [False, True])
def test_authored_scout_into_nonplayable_cisalpina_rejects_before_command(nested):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    before = encode(state)
    submitted = {'action': ACTION_COMMAND_SA, 'player_action': scout_action(nested=nested)}
    with pytest.raises(ValueError, match='playable'):
        validate_response(state, {'kind': 'turn', 'faction': rc.ROMANS,
                                 'options': [ACTION_COMMAND_SA]}, submitted)
    result = execute_decision(state, rc.ROMANS, submitted)
    assert not result['executed'] and result['rejected']
    assert encode(state) == before


@pytest.mark.parametrize('origin,target', [
    (rc.PROVINCIA, rc.CISALPINA), (rc.CISALPINA, rc.PROVINCIA),
])
def test_native_scout_rejects_nonplayable_endpoints_atomically(origin, target):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    before = encode(state)
    with pytest.raises(CommandError, match='playable'):
        scout_move(state, [movement(origin, target)])
    assert encode(state) == before


def test_native_scout_rolls_back_an_earlier_move_when_later_region_is_illegal():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    before = encode(state)
    with pytest.raises(CommandError, match='playable'):
        scout_move(state, [movement(target=rc.SEQUANI), movement()])
    assert encode(state) == before


@pytest.mark.parametrize('context', ['ordinary', 'ariovistus', 'gallia', 'lingering_a5'])
@pytest.mark.parametrize('reverse', [False, True])
def test_scout_keeps_legal_scenario_and_gallia_movement(context, reverse):
    scenario = rc.SCENARIO_ARIOVISTUS if context == 'ariovistus' else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=1)
    if context == 'gallia':
        execute_event(state, 5)
    elif context == 'lingering_a5':
        # Saved second-half context: the actual A5 marker survives Interlude.
        state['scenario'] = rc.SCENARIO_PAX_GALLICA
        state['interlude_completed'] = True
        state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    target = rc.SEQUANI if context == 'ordinary' else rc.CISALPINA
    origin = rc.PROVINCIA
    if reverse:
        origin, target = target, origin
    place_piece(state, origin, rc.ROMANS, rc.AUXILIA)
    before = count_pieces(state, target, rc.ROMANS, rc.AUXILIA)
    result = scout_move(state, [movement(origin, target)])
    assert result['moved'] == [(origin, target, 1, rc.HIDDEN)]
    assert count_pieces(state, target, rc.ROMANS, rc.AUXILIA) == before + 1
    assert validate_state(state) == []


def battle(region=rc.MORINI, defender=rc.BELGAE):
    return {'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [region],
            'details': {'battle_plan': [{'region': region, 'target': defender}]}}


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_battle_without_attacker_cannot_charge_or_reveal(faction):
    scenario = rc.SCENARIO_ARIOVISTUS if faction == rc.GERMANS else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = set()
    state['resources'][faction] = 20
    defender = rc.AEDUI if faction == rc.BELGAE else rc.BELGAE
    place_piece(state, rc.MORINI, defender, rc.WARBAND, 4)
    before = encode(state)
    result = execute_decision(state, faction, {'player_action': battle(defender=defender)})
    assert not result['executed']
    assert any('attacker not present' in error['error'] for error in result['errors'])
    assert encode(state) == before
    assert count_pieces_by_state(state, rc.MORINI, defender, rc.WARBAND, rc.HIDDEN) == 4


@pytest.mark.parametrize('piece', [rc.AUXILIA, rc.FORT, rc.LEADER])
def test_own_force_presence_is_not_a_minimum_attack_strength_requirement(piece):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = 20
    place_piece(state, rc.MORINI, rc.ROMANS, piece,
                **({'leader_name': rc.CAESAR} if piece == rc.LEADER else {}))
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    result = execute_decision(state, rc.ROMANS, {'player_action': battle()})
    assert result['executed'] and not result.get('errors')
    assert state['resources'][rc.ROMANS] == 18


def test_scout_before_battle_can_supply_the_initially_absent_attacker():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = 20
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND)
    action = battle(rc.SEQUANI)
    action.update(sa=rc.SA_SCOUT, sa_timing='before')
    action['details']['scout_plan'] = {
        'auxilia_moves': [movement(target=rc.SEQUANI)], 'scout_targets': []}
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'] and not result.get('errors')
    assert result['sa_execution']['executed']
    assert state['resources'][rc.ROMANS] == 18


@pytest.mark.parametrize('invalid', ['scout', 'battle'])
def test_invalid_boundary_keeps_initialized_durable_turn_pending(tmp_path, capsys, invalid):
    args = SimpleNamespace(dir=str(tmp_path / 'game'), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seed=46, seat=rc.ROMANS)
    llm_seat.cmd_init(args)
    assert llm_seat.cmd_play(args) == 0
    path = tmp_path / 'game' / 'save.json'
    state, meta, log = load_game(path, validate=True)
    pending = deepcopy(meta['assistant_session']['pending'])
    assert decode(pending['request'])['kind'] == 'turn'
    assert decode(pending['request'])['faction'] == rc.ROMANS
    before = encode(state)
    response = ({'action': ACTION_COMMAND_SA, 'player_action': scout_action()}
                if invalid == 'scout' else {'action': ACTION_COMMAND, 'player_action': battle()})
    assert llm_seat.cmd_submit(SimpleNamespace(
        dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    # Battle eligibility is checked on the actual board after preceding
    # Special Ability movement and optional timing windows, not a stale preview.
    for _ in range(20):
        after, after_meta, after_log = load_game(path, validate=True)
        next_pending = after_meta['assistant_session']['pending']
        if decode(next_pending['request'])['kind'] == 'turn':
            break
        assert llm_seat.cmd_submit(SimpleNamespace(
            dir=args.dir, decision_id=next_pending['id'],
            response=json.dumps({'use_default': True}))) == 0
    else:
        pytest.fail('Invalid Battle did not return to its pending turn.')
    assert after_meta['assistant_session']['pending']['id'] == pending['id']
    assert after_meta['assistant_session']['journal'] == meta['assistant_session']['journal']
    assert encode(after) == before and after_log == log
    assert validate_state(after) == check_structural_integrity(after) == []
