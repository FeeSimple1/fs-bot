"""Card Reference 37: bounded, same-owner placements and legal partial execution."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.boii import eligible_allies, eligible_regions
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.cards.param_schema import card_param_schema, kind_values
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.state.serialize import save_game, load_game


def fresh(scenario=rc.SCENARIO_PAX_GALLICA):
    state = build_initial_state(scenario, seed=17)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    state['current_card'] = 37
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE, rc.AEDUI}
    return state


def full_plan(state, faction=rc.ROMANS):
    targets = eligible_allies(state, eligible_regions(state, rc.AEDUI), faction)[:2]
    return {'place_faction': faction, 'placements': [
        {'region': rc.TRIBE_TO_REGION[t], 'piece_type': rc.ALLY, 'tribe': t, 'count': 1}
        for t in targets] + [{'region': rc.AEDUI_REGION,
                             'piece_type': rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND,
                             'count': 2}]}


def board_snapshot(state):
    return deepcopy({k: v for k, v in state.items() if k != 'rng'}), state['rng'].getstate()


@pytest.mark.parametrize('count', [-1, 0, 3, True, False, 1.5, '2', None])
def test_boii_rejects_illegal_counts_before_any_placement(count):
    state = fresh()
    state['event_params'] = full_plan(state)
    state['event_params']['placements'][-1]['count'] = count
    before = board_snapshot(state)
    with pytest.raises(ValueError):
        execute_event(state, 37)
    assert board_snapshot(state) == before


def test_boii_aggregate_limit_applies_across_entries_and_regions():
    state = fresh()
    state['event_params'] = full_plan(state)
    state['event_params']['placements'] += [
        {'region': rc.SEQUANI, 'piece_type': rc.AUXILIA, 'count': 1}]
    before = board_snapshot(state)
    with pytest.raises(ValueError, match='at most two'):
        execute_event(state, 37)
    assert board_snapshot(state) == before


@pytest.mark.parametrize('change', [
    {'place_faction': rc.BELGAE},
    {'piece_type': rc.WARBAND},
    {'faction': rc.AEDUI},
    {'region': rc.MORINI},
])
def test_boii_rejects_wrong_beneficiary_piece_owner_and_scope(change):
    state = fresh()
    params = full_plan(state)
    if 'place_faction' in change:
        params.update(change)
    else:
        params['placements'][-1].update(change)
    state['event_params'] = params
    before = board_snapshot(state)
    with pytest.raises(ValueError):
        execute_event(state, 37)
    assert board_snapshot(state) == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_boii_places_two_allies_and_native_troops_and_roundtrips(tmp_path, scenario, faction):
    state = fresh(scenario)
    state['event_params'] = full_plan(state, faction)
    initial = get_available(state, faction, rc.ALLY)
    troop = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    before_troops = count_pieces(state, rc.AEDUI_REGION, faction, troop)
    execute_event(state, 37)
    assert get_available(state, faction, rc.ALLY) == initial - 2
    assert count_pieces(state, rc.AEDUI_REGION, faction, troop) == before_troops + 2
    assert not check_structural_integrity(state)
    path = str(tmp_path / 'boii.json')
    save_game(state, path)
    loaded, _, _ = load_game(path, validate=True)
    assert loaded['spaces'] == state['spaces']


def test_boii_scope_does_not_shrink_when_roman_placements_remove_aedui_control():
    state = fresh()
    params = full_plan(state)
    # All three Regions qualify before Roman placements change Aedui Control.
    params['placements'][-1:] = [
        {'region': rc.AEDUI_REGION, 'piece_type': rc.AUXILIA, 'count': 1},
        {'region': rc.SEQUANI, 'piece_type': rc.AUXILIA, 'count': 1}]
    state['event_params'] = params
    execute_event(state, 37)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1


def test_boii_places_one_available_troop_instead_of_skipping_two_requested():
    state = fresh()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 19)
    state['event_params'] = full_plan(state)
    execute_event(state, 37)
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == 0
    assert not check_structural_integrity(state)


def test_boii_requires_all_legal_available_placements():
    state = fresh()
    state['event_params'] = full_plan(state)
    state['event_params']['placements'][-1]['count'] = 1
    with pytest.raises(ValueError, match='must place all'):
        execute_event(state, 37)


def test_rejected_boii_action_cannot_create_an_unloadable_save(tmp_path):
    state = fresh()
    params = full_plan(state)
    params['placements'][-1]['count'] = -1
    old_spaces = deepcopy(state['spaces'])
    result = execute_decision(state, rc.ROMANS, {'action': ACTION_EVENT,
        'player_action': {'command': 'Event', 'sa': 'No SA', 'details': {
            'card_id': 37, 'text_preference': rc.EVENT_UNSHADED,
            'event_params': params}}})
    assert result['executed'] is False
    assert state['spaces'] == old_spaces
    assert not check_structural_integrity(state)
    path = str(tmp_path / 'rejected.json')
    save_game(state, path)
    load_game(path, validate=True)


def shaded_state():
    state = fresh()
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 6)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    return state


@pytest.mark.parametrize('tribes', [
    [rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES],
    [rc.TRIBE_MANDUBII, rc.TRIBE_MANDUBII],
    [],
])
def test_shaded_rejects_bad_replacement_counts_atomically(tribes):
    state = shaded_state()
    state['event_params'] = {'replacements': [{'tribe': t} for t in tribes]}
    before = board_snapshot(state)
    with pytest.raises(ValueError):
        execute_event(state, 37, shaded=True)
    assert board_snapshot(state) == before


def test_shaded_removes_aedui_home_ally_without_illegal_arverni_replacement():
    state = fresh()
    place_piece(state, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    state['event_params'] = {'replacements': [{'tribe': rc.TRIBE_AEDUI}]}
    execute_event(state, 37, shaded=True)
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] is None
    assert not check_structural_integrity(state)


def test_boii_real_menu_completes_a_legal_plan_without_generic_counts():
    state = fresh()
    output = StringIO()
    params = _collect_event_params(state, rc.ROMANS, 37, False,
                                  StringIO('2\n1\n1\n1\n2\n'), output)
    state['event_params'] = params
    execute_event(state, 37)
    assert params['place_faction'] == rc.ROMANS
    assert sum(p['count'] for p in params['placements'] if p['piece_type'] == rc.AUXILIA) == 2
    assert 'Boii: place an Ally at which Tribe?' in output.getvalue()
    assert '  3) 3\n' not in output.getvalue()
    assert not check_structural_integrity(state)


def test_boii_real_shaded_menu_can_choose_one_or_two():
    for answers, number in [('1\n3\n', 1), ('1\n1\n', 2)]:
        state = shaded_state()
        params = _collect_event_params(state, rc.ARVERNI, 37, True,
                                      StringIO(answers), StringIO())
        assert len(params['replacements']) == number
        state['event_params'] = params
        execute_event(state, 37, shaded=True)
        assert not check_structural_integrity(state)


def test_boii_schema_limits_counts_even_for_generic_consumers():
    state = fresh()
    schema = card_param_schema(37, state['scenario'])
    assert kind_values(state, 'count', schema['placements']) == [1, 2]
    assert kind_values(state, 'faction', schema['place_faction']) == [rc.AEDUI, rc.ROMANS]


def test_nonplayer_boii_executes_through_the_public_event_path():
    state = fresh()
    state['non_player_factions'].add(rc.ROMANS)
    state['event_params'] = None
    before = get_available(state, rc.ROMANS, rc.ALLY)
    result = execute_decision(state, rc.ROMANS, {'action': ACTION_EVENT,
        'bot_action': {'command': 'Event', 'sa': 'No SA', 'details': {
            'card_id': 37, 'text_preference': rc.EVENT_UNSHADED}}})
    assert result['executed'] is True
    assert get_available(state, rc.ROMANS, rc.ALLY) == before - 2
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == 18
    assert not check_structural_integrity(state)
