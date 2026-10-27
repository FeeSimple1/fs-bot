"""Card 21: printed choices, partial effects, and the scoped shaded grant."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_data import get_ariovistus_event_card_ids
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.param_schema import card_param_schema, kind_values
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.menus import prompt_action, set_board_hook
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.serialize import load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def fresh():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=19)
    state['current_card'] = 21
    state['next_card'] = 11
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def event_decision(params=None, shaded=False):
    details = {'card_id': 21,
               'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}
    if params is not None:
        details['event_params'] = params
    return {'action': ACTION_EVENT, 'player_action': {
        'command': 'Event', 'regions': [], 'sa': 'No SA',
        'sa_regions': [], 'details': details}}


def snapshot(state):
    return deepcopy({k: v for k, v in state.items() if k != 'rng'}), state['rng'].getstate()


@pytest.mark.parametrize('value', [None, '', 'Resources', 'Auxilia', rc.PROVINCIA,
                                  True, False, 0, 1, 1.5, [], {}, ['resources']])
def test_explicit_invalid_benefit_is_rejected_before_mutation(value):
    state = fresh()
    state['event_params'] = {'province_choice': value}
    before = snapshot(state)
    with pytest.raises(ValueError, match='province_choice'):
        execute_event(state, 21)
    assert snapshot(state) == before


@pytest.mark.parametrize('params', [[], 'resources', 0, True])
def test_invalid_parameter_container_is_rejected(params):
    state = fresh()
    state['event_params'] = params
    before = snapshot(state)
    with pytest.raises(ValueError, match='object'):
        execute_event(state, 21)
    assert snapshot(state) == before


@pytest.mark.parametrize('params', [None, {}])
def test_omitted_choice_keeps_existing_auxilia_default(params):
    state = fresh()
    state['event_params'] = params
    execute_event(state, 21)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 5


@pytest.mark.parametrize('available', [0, 2, 5])
def test_auxilia_places_the_available_partial_pool(available):
    state = fresh()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                count=get_available(state, rc.ROMANS, rc.AUXILIA) - available)
    state['event_params'] = {'province_choice': 'auxilia'}
    execute_event(state, 21)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == available
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == 0
    assert not check_structural_integrity(state)


@pytest.mark.parametrize('resources,expected', [(0, 10), (40, 45), (45, 45)])
def test_resources_respects_the_cap_without_placing_auxilia(resources, expected):
    state = fresh()
    state['resources'][rc.ROMANS] = resources
    state['event_params'] = {'province_choice': 'resources'}
    execute_event(state, 21)
    assert state['resources'][rc.ROMANS] == expected
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('enemy', [rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS])
@pytest.mark.parametrize('choice', ['auxilia', 'resources'])
def test_nonroman_presence_blocks_both_unshaded_alternatives(enemy, choice):
    state = fresh()
    place_piece(state, rc.PROVINCIA, enemy, rc.WARBAND)
    state['event_params'] = {'province_choice': choice}
    before = snapshot(state)
    execute_event(state, 21)
    assert snapshot(state) == before


def test_generic_schema_offers_the_two_api_values_only():
    state = fresh()
    spec = card_param_schema(21, state['scenario'])['province_choice']
    assert kind_values(state, spec['kind'], spec) == ['auxilia', 'resources']
    # Ariovistus replaces this card with Vosegus, without acquiring its choice.
    assert 21 not in get_ariovistus_event_card_ids()
    assert 'province_choice' not in card_param_schema('A21', rc.SCENARIO_ARIOVISTUS)


@pytest.mark.parametrize('pick,choice', [('1', 'auxilia'), ('2', 'resources')])
def test_real_action_menu_selects_and_executes_either_benefit(pick, choice):
    state = fresh()
    state['resources'][rc.ROMANS] = 40
    before = snapshot(state)
    output = StringIO()
    board_calls = []
    set_board_hook(lambda: board_calls.append(True))
    try:
        decision = prompt_action(state, rc.ROMANS, [ACTION_EVENT], '1st_eligible',
                                 StringIO(f'1\n1\nb\n{pick}\nn\n'), output)
    finally:
        set_board_hook(None)
    assert decision['player_action']['details']['event_params'] == {'province_choice': choice}
    assert board_calls == [True]
    assert snapshot(state) == before  # Includes the real validation preview and RNG.
    text = output.getvalue()
    assert 'Current card:' in text and 'Upcoming card:' in text
    assert 'Place 5 Auxilia in Provincia' in text
    assert 'Add +10 Roman Resources (5 gained within the Resource cap)' in text
    assert 'province_choice:' not in text and '(skip)' not in text
    result = execute_decision(state, rc.ROMANS, decision)
    assert result['executed'], result
    assert state['resources'][rc.ROMANS] == (45 if choice == 'resources' else 40)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (0 if choice == 'resources' else 5)
    assert not check_structural_integrity(state)


@pytest.mark.parametrize('shaded,blocked', [(True, False), (False, True)])
def test_no_irrelevant_benefit_prompt(shaded, blocked):
    state = fresh()
    if blocked:
        place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    assert _collect_event_params(state, rc.ROMANS, 21, shaded,
                                 StringIO(''), StringIO()) == {}


def test_invalid_public_plan_is_rejected_without_board_changes():
    state = fresh()
    before = snapshot(state)
    result = execute_decision(state, rc.ROMANS,
                              event_decision({'province_choice': rc.PROVINCIA}))
    assert not result['executed']
    assert 'province_choice' in str(result)
    assert snapshot(state) == before


@pytest.mark.parametrize('position,firm,expected_position,expected_firm', [
    (rc.ADULATION, False, rc.UPROAR, False),
    (rc.ADULATION, True, rc.ADULATION, False),
    (rc.INTRIGUE, False, rc.UPROAR, True),
    (rc.INTRIGUE, True, rc.INTRIGUE, False),
    (rc.UPROAR, False, rc.UPROAR, True),
    (rc.UPROAR, True, rc.UPROAR, True),
    (None, False, None, False),
])
def test_shaded_senate_is_one_two_box_event_shift(position, firm, expected_position, expected_firm):
    state = fresh()
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, count=2)
    refresh_all_control(state)
    state['senate'] = {'position': position, 'firm': firm}
    result = execute_decision(state, rc.ARVERNI, event_decision(shaded=True))
    assert result['executed'], result
    assert state['senate'] == {'position': expected_position, 'firm': expected_firm}
    assert count_pieces(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND) == 2
    assert not state.get('event_modifiers', {}).get('card_21_no_fort')


def test_accepted_resources_plan_roundtrips_and_replays_deterministically(tmp_path):
    state = fresh()
    state['resources'][rc.ROMANS] = 38
    path = str(tmp_path / 'province.json')
    save_game(state, path)
    replay, _, _ = load_game(path, validate=True)
    decision = event_decision({'province_choice': 'resources'})
    assert execute_decision(state, rc.AEDUI, decision)['executed']
    assert execute_decision(replay, rc.AEDUI, decision)['executed']
    assert snapshot(state) == snapshot(replay)
    assert state['resources'][rc.ROMANS] == 45


@pytest.mark.parametrize('region,modifier,expected', [
    (rc.PROVINCIA, True, True),
    (rc.PROVINCIA, False, False),
    (rc.MANDUBII, True, False),
])
def test_arverni_battle_prediction_ignores_only_the_event_scoped_fort(region, modifier, expected):
    from fs_bot.bots.arverni_bot import _can_battle_in_region
    state = fresh()
    if region != rc.PROVINCIA:
        place_piece(state, region, rc.ROMANS, rc.FORT)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, count=6)
    place_piece(state, region, rc.ARVERNI, rc.WARBAND, count=10)
    state['event_modifiers'] = {'card_21_no_fort': modifier}
    # §8.7.1: 5 projected attack Losses exceed 3 counterattack Losses;
    # ordinary Fort protection instead reduces that attack to 2.
    assert _can_battle_in_region(state, region, state['scenario'], rc.ROMANS) is expected


def test_arverni_battle_prediction_retains_citadel_protection():
    from fs_bot.bots.arverni_bot import _can_battle_in_region
    state = fresh()
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.CITADEL)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, count=6)
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, count=10)
    state['event_modifiers'] = {'card_21_no_fort': True}
    assert not _can_battle_in_region(state, rc.PROVINCIA, state['scenario'], rc.AEDUI)


def test_shaded_production_bot_battles_when_fort_exception_makes_losses_favorable():
    state = fresh()
    state['non_player_factions'].add(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, count=6)
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, count=6)
    refresh_all_control(state)
    # No Arverni Control before placement, so place four then grant a
    # Command. With ten Warbands, the normal §8.7.1 Battle trigger applies.
    result = execute_decision(state, rc.ARVERNI, event_decision(shaded=True))
    assert result['executed'], result
    command = result['free_actions'][0]['result']
    assert command['executed'] and command['command'] == rc.CMD_BATTLE
    assert not command.get('errors')
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) < 6
    assert state['resources'][rc.ARVERNI] == 0
    assert 'card_21_no_fort' not in state['event_modifiers']
    assert not check_structural_integrity(state)


def test_roman_nonplayer_still_requires_full_auxilia_and_uses_default_branch():
    from fs_bot.bots.bot_common import should_decline_event
    state = fresh()
    state['non_player_factions'].add(rc.ROMANS)
    state['current_card_id'] = 21
    assert not should_decline_event(state, 21, rc.ROMANS)
    action = event_decision()['player_action']
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_EVENT, 'bot_action': action})
    assert result['executed'], result
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 5
    assert state['resources'][rc.ROMANS] == 0
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                count=get_available(state, rc.ROMANS, rc.AUXILIA) - 4)
    assert should_decline_event(state, 21, rc.ROMANS)


def test_roman_instruction_checks_provincia_without_consuming_rng_or_human_input():
    from fs_bot.bots.roman_bot import node_r4
    state = fresh()
    state['current_card_id'] = 21
    state['non_player_factions'].add(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    def unexpected(*args):
        raise AssertionError('availability preview queried a human')
    state['decision_agent'] = unexpected
    before = snapshot(state)
    assert node_r4(state) == 'Yes'
    assert snapshot(state) == before


@pytest.mark.parametrize('command,answers', [
    (rc.CMD_RAID, 'Raid\nProvincia\n1\nsteal from Romans\n'),
    (rc.CMD_BATTLE, 'Battle\nProvincia\nRomans\n'),
])
def test_shaded_production_grant_uses_real_scoped_menu_after_placement(command, answers):
    from fs_bot.cli.free_actions import collect_free_action
    state = fresh()
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['resources'][rc.ROMANS] = 10
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, count=8,
                piece_state=rc.REVEALED)
    # An unrelated eligible Region must never appear in this grant.
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, count=2)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    output = StringIO()
    requests = []
    def agent(board, faction, request):
        if request.get('kind') != 'free_action':
            return None
        requests.append(request)
        assert faction == rc.ARVERNI
        assert count_pieces(board, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND) == 4
        before = snapshot(board)
        action = collect_free_action(board, faction, request,
                                    StringIO('Plan the action\n' + answers), output)
        assert snapshot(board) == before
        return action
    state['decision_agent'] = agent
    # Aedui plays the Event; the printed grant still belongs to Arverni.
    result = execute_decision(state, rc.AEDUI, event_decision(shaded=True))
    assert result['executed'], result
    assert len(requests) == 1
    assert requests[0]['allowed_regions'] == [rc.PROVINCIA]
    assert set(requests[0]['allowed_commands']) == {rc.CMD_RAID, rc.CMD_BATTLE}
    assert requests[0]['with_sa'] is False
    grant = result['free_actions'][0]['result']
    assert grant['executed'] and grant['command'] == command
    assert 'March' not in output.getvalue() and 'Rally' not in output.getvalue()
    assert rc.MORINI not in output.getvalue()
    assert count_pieces(state, rc.MORINI, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    if command == rc.CMD_RAID:
        assert state['resources'][rc.ROMANS] == 9
        assert state['resources'][rc.ARVERNI] == 1
    else:
        assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 6
        assert state['resources'][rc.ARVERNI] == 0
    assert 'card_21_no_fort' not in state['event_modifiers']
    assert not check_structural_integrity(state)
