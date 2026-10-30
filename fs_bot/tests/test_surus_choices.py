"""Surus shaded: the executor guides only its replacement Warbands (§8.2.3)."""
from copy import deepcopy
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.action_windows import scope
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(count=2):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    state['non_player_factions'] = set()
    pieces.place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, count)
    pieces.place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 5)
    pieces.place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4)
    return state


def event(count=2):
    return {'command': rc.FIRST_DID_EVENT, 'details': {
        'card_id': 51, 'text_preference': rc.EVENT_SHADED,
        'event_params': {'region': rc.TREVERI, 'count': count}}}


def execute(state, action, grant):
    asked = []
    def agent(live, faction, request):
        if request['kind'] == 'free_action':
            asked.append((faction, deepcopy(request)))
            return grant
        return None
    state['decision_agent'] = agent
    result = _execute_event(state, rc.BELGAE, action, human=True)
    return result, asked


def test_human_selects_raid_and_only_new_hidden_warbands_flip():
    state = position()
    state['resources'][rc.ROMANS] = 7
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    result, asked = execute(state, event(), {'command': rc.CMD_RAID, 'sa': 'No SA',
        'details': {'raid_plan': [{'region': rc.TREVERI, 'target': rc.ROMANS}]}})
    assert result['executed'], result
    assert asked[0][0] == rc.BELGAE
    assert set(asked[0][1]['allowed_commands']) == {rc.CMD_MARCH, rc.CMD_RAID, rc.CMD_BATTLE}
    assert state['resources'][rc.ROMANS] == 6
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 6
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert pieces.count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_human_selects_march_and_cannot_take_preexisting_residents():
    state = position()
    result, _ = execute(state, event(), {'command': rc.CMD_MARCH, 'sa': 'No SA',
        'details': {'origins': [rc.TREVERI], 'destinations': [rc.MANDUBII],
                    'routes': {rc.TREVERI: [rc.MANDUBII]},
                    'groups': {rc.TREVERI: {rc.WARBAND: 2}}}})
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 5
    assert pieces.count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 2
    assert pieces.count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_scouted_aedui_warbands_can_be_replaced_and_receive_the_grant():
    state = position(0)
    pieces.place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 2,
                       piece_state=rc.SCOUTED)
    result, _ = execute(state, event(), {'command': rc.CMD_MARCH, 'sa': 'No SA',
        'details': {'origins': [rc.TREVERI], 'destinations': [rc.MANDUBII],
                    'routes': {rc.TREVERI: [rc.MANDUBII]},
                    'groups': {rc.TREVERI: {rc.WARBAND: 2}}}})
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert pieces.count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_march_group_cap_cannot_include_preexisting_residents():
    state = position()
    result, _ = execute(state, event(), {'command': rc.CMD_MARCH, 'sa': 'No SA',
        'details': {'origins': [rc.TREVERI], 'destinations': [rc.MANDUBII],
                    'routes': {rc.TREVERI: [rc.MANDUBII]},
                    'groups': {rc.TREVERI: {rc.WARBAND: 3}}}})
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 5
    assert pieces.count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 2


@pytest.mark.parametrize('invalid', ['extra_origin', 'rally', 'sa'])
def test_out_of_grant_actions_rollback_replacements(invalid):
    state = position()
    action = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [rc.TREVERI], 'destinations': [rc.MANDUBII],
        'routes': {rc.TREVERI: [rc.MANDUBII]},
        'groups': {rc.TREVERI: {rc.WARBAND: 2}}}}
    if invalid == 'extra_origin':
        action['details'] = {'origins': [rc.NERVII], 'destinations': [rc.TREVERI],
                             'routes': {rc.NERVII: [rc.TREVERI]},
                             'groups': {rc.NERVII: {rc.WARBAND: 1}}}
    elif invalid == 'rally':
        action = {'command': rc.CMD_RALLY, 'details': {'rally_plan': {'warbands': [rc.TREVERI]}}}
    else:
        action['sa'] = rc.SA_AMBUSH
    before = deepcopy(state['spaces'])
    result, _ = execute(state, event(), action)
    assert not result['executed'], result
    assert state['spaces'] == before


def test_only_newly_placed_warbands_count_for_intrinsic_german_ambush():
    state = position(1)
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    # Five resident Hidden Germans must not make the one selected Warband
    # outnumber the one Hidden Roman defender.
    before = deepcopy(state['spaces'])
    result, _ = execute(state, event(1), {'command': rc.CMD_BATTLE, 'sa': 'No SA',
        'details': {'battle_plan': [{'region': rc.TREVERI, 'target': rc.ROMANS}]}})
    assert not result['executed'], result
    assert state['spaces'] == before


def test_legal_german_battle_auto_ambushes_only_at_the_replacement_region():
    state = position()
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    pieces.place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    result, _ = execute(state, event(), {'command': rc.CMD_BATTLE, 'sa': 'No SA',
        'details': {'battle_plan': [{'region': rc.TREVERI, 'target': rc.ROMANS}]}})
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.ROMANS, rc.LEGION) == 0
    assert pieces.count_pieces(state, rc.NERVII, rc.ROMANS, rc.LEGION) == 1
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 5
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2


def test_no_replacement_discards_the_action_without_using_existing_germans():
    state = position()
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND,
                       pieces.get_available(state, rc.GERMANS, rc.WARBAND))
    result, asked = execute(state, event(), {'command': rc.CMD_MARCH})
    assert result['executed'] and asked == []
    assert pieces.count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 5
    assert result['free_actions'][0]['declined_no_effect']


@pytest.mark.parametrize('chooser,command', [
    (rc.ROMANS, rc.CMD_MARCH), (rc.ARVERNI, rc.CMD_MARCH),
    (rc.AEDUI, rc.CMD_MARCH), (rc.BELGAE, rc.CMD_BATTLE),
])
def test_nonplayer_guiding_chart_executes_only_newly_placed_germans(chooser, command):
    state = position(4)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['resources'][chooser] = 10
    pieces.place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    from fs_bot.cards.card_effects import _ally_tribe
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.ARVERNI)
    result = _execute_event(state, chooser, event(4))
    assert result['executed'], result
    granted = result['free_actions'][0]
    assert granted['chooser'] == chooser and granted['acting_faction'] == rc.GERMANS
    assert granted['result']['executed'], granted
    assert granted['result']['command'] == command
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS,
                                       rc.WARBAND, rc.HIDDEN) >= 5
    assert pieces.count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_nonplayer_maximizes_replacements_even_without_available_germans():
    state = position(4)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    pieces.place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 1)
    pieces.place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 3)
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND,
                       pieces.get_available(state, rc.GERMANS, rc.WARBAND))
    result = _execute_event(state, rc.BELGAE, event())
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 1
    assert pieces.count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 3
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 5
    assert result['free_actions'][0]['declined_no_effect']
    assert validate_state(state) == []


def test_unshaded_nonplayer_replaces_most_enemies_using_visibility_then_faction():
    from fs_bot.cards.surus import derive_params
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['resources'][rc.AEDUI] = 10
    pieces.place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, 3,
                       piece_state=rc.REVEALED)
    pieces.place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 1)
    pieces.place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 1)
    pieces.place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 3)
    params = derive_params(state, rc.AEDUI, False)
    assert params == {'region': rc.TREVERI, 'replacements': [
        {'from_faction': rc.BELGAE, 'piece_state': rc.HIDDEN},
        {'from_faction': rc.GERMANS, 'piece_state': rc.HIDDEN},
        {'from_faction': rc.ARVERNI, 'piece_state': rc.REVEALED},
        {'from_faction': rc.ARVERNI, 'piece_state': rc.REVEALED},
    ]}
    result = _execute_event(state, rc.AEDUI, {'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': 51, 'text_preference': rc.EVENT_UNSHADED}})
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 1
    assert pieces.count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 0
    assert pieces.count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 0
    assert pieces.count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 3
    assert validate_state(state) == []


def test_unshaded_nonplayer_removes_enemies_even_with_empty_aedui_pool():
    from fs_bot.cards.surus import derive_params
    from fs_bot.cards.card_effects import execute_event
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    pieces.place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND,
                       pieces.get_available(state, rc.AEDUI, rc.WARBAND))
    pieces.place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 4)
    state['executing_faction'] = rc.AEDUI
    state['event_params'] = derive_params(state, rc.AEDUI, False)
    execute_event(state, 51)
    assert pieces.count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 0
    assert pieces.count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert validate_state(state) == []


def test_unshaded_nonplayer_completes_four_with_own_pieces_in_reverse_loss_order():
    from fs_bot.cards.surus import derive_params
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    pieces.place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 1)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        pieces.place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 1,
                           piece_state=visibility)
    params = derive_params(state, rc.AEDUI, False)
    assert params == {'region': rc.TREVERI, 'replacements': [
        {'from_faction': rc.BELGAE, 'piece_state': rc.HIDDEN},
        {'from_faction': rc.AEDUI, 'piece_state': rc.SCOUTED},
        {'from_faction': rc.AEDUI, 'piece_state': rc.REVEALED},
        {'from_faction': rc.AEDUI, 'piece_state': rc.HIDDEN},
    ]}
