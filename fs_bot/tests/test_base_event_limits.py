"""Card Reference 40/41/42/51 contracts and §5.1.1 partial execution."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.boii import eligible_allies
from fs_bot.cards.card_effects import execute_event, _ally_tribe, _tribe_region
from fs_bot.cards.base_event_limits import avaricum_regions, derive_avaricum, derive_wine, wine_regions
from fs_bot.cards.event_preview import preview_event_prefix
from fs_bot.cli import human_plan
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode
from fs_bot.tools.seat_session import board_copy


def board(card=40, actor=rc.AEDUI):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=44)
    state.update(current_card=card, next_card=43, executing_faction=actor,
                 non_player_factions=set())
    return state


def run(state, card, params, shaded=False):
    state['event_params'] = params
    execute_event(state, card, shaded)


def ally(state, region, faction):
    tribe = eligible_allies(state, [region], faction)[0]
    assert _ally_tribe(state, tribe, faction)
    return tribe


def avaricum(actor=rc.AEDUI):
    state = board(41, actor)
    assert _ally_tribe(state, rc.CITY_TO_TRIBE[rc.CITY_AVARICUM], actor)
    return state


def placement(region=rc.SEQUANI, kind=rc.WARBAND, count=1, faction=rc.AEDUI, **kw):
    return {'region': region, 'piece_type': kind, 'count': count, 'faction': faction, **kw}


@pytest.mark.parametrize('params', [
    {'placements': [placement(count=3), placement(kind=rc.AUXILIA, count=2, faction=rc.ROMANS)]},
    {'placements': [placement(count=2), placement(count=2, faction=rc.BELGAE)]},
    {'placements': [placement(count=4)]}, {'placements': [placement(count=True)]},
    {'placements': [placement(count=-1)]}, {'placements': [placement(region=rc.MORINI)]},
    {'placements': [placement(faction=rc.ROMANS)]},
    {'placements': [placement(kind=rc.AUXILIA)]}, {'placements': {}},
])
def test_alpine_rejects_invalid_whole_plan_atomically(params):
    state = board(); state['event_params'] = params
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 40)
    assert encode(state) == before


def test_alpine_different_regions_different_types_and_mixed_owners_same_type():
    state = board()
    tribe = eligible_allies(state, [rc.UBII], rc.GERMANS)[0]
    run(state, 40, {'placements': [placement(count=2), placement(faction=rc.BELGAE),
        placement(rc.PROVINCIA, rc.AUXILIA, 2, rc.ROMANS),
        placement(rc.UBII, rc.ALLY, 1, rc.GERMANS, tribe=tribe)]})
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert state['tribes'][tribe]['allied_faction'] == rc.GERMANS
    assert state['resources'][rc.AEDUI] == 4 and validate_state(state) == []


def test_alpine_zero_selection_and_short_available_pool():
    state = board()
    run(state, 40, {'placements': []})
    assert state['resources'][rc.AEDUI] == 4
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND) - 1)
    run(state, 40, {'placements': [placement(count=3)]})
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_avaricum_rejects_three_allies_and_wrong_owner_or_range():
    state = avaricum()
    targets = eligible_allies(state, avaricum_regions(state), rc.AEDUI)
    for params in ({'ally_placements': [{'tribe': t} for t in targets[:3]]},
                   {'ally_placements': [{'tribe': targets[0], 'faction': rc.BELGAE}]},
                   {'ally_placements': [{'tribe': eligible_allies(state, [rc.MORINI], rc.AEDUI)[0]}]},
                   {'citadel_upgrade_tribe': eligible_allies(state, [rc.MORINI], rc.AEDUI)[0]}):
        state['event_params'] = params; before = encode(state)
        with pytest.raises(ValueError):
            execute_event(state, 41)
        assert encode(state) == before


def test_avaricum_optional_placements_upgrade_new_city_and_then_resources():
    state = avaricum()
    targets = eligible_allies(state, avaricum_regions(state), rc.AEDUI)
    city = next(t for t in targets if t in rc.TRIBE_TO_CITY)
    other = next(t for t in targets if t != city)
    run(state, 41, {'ally_placements': [{'tribe': city}, {'tribe': other}], 'citadel_upgrade_tribe': city})
    assert count_pieces(state, _tribe_region(state, city), rc.AEDUI, rc.CITADEL) == 1
    assert state['tribes'][city]['allied_faction'] == rc.AEDUI
    assert state['resources'][rc.AEDUI] == 3
    assert validate_state(state) == []


@pytest.mark.parametrize('actor', [rc.AEDUI, rc.ROMANS, rc.GERMANS])
def test_avaricum_unavailable_citadel_removes_exact_own_city_ally(actor):
    state = avaricum(actor)
    if get_available(state, actor, rc.CITADEL):
        # Exhaust a Gallic pool legally at its three other City Tribes.
        for tribe in eligible_allies(state, state['spaces'], actor):
            if tribe in rc.TRIBE_TO_CITY and get_available(state, actor, rc.CITADEL):
                region = _tribe_region(state, tribe)
                place_piece(state, region, actor, rc.CITADEL)
                state['tribes'][tribe]['allied_faction'] = actor
    tribe = rc.CITY_TO_TRIBE[rc.CITY_AVARICUM]
    assert get_available(state, actor, rc.CITADEL) == 0
    run(state, 41, {'citadel_upgrade_tribe': tribe})
    assert state['tribes'][tribe]['allied_faction'] is None
    assert count_pieces(state, rc.BITURIGES, actor, rc.ALLY) == 0
    assert count_pieces(state, rc.BITURIGES, actor, rc.CITADEL) == 0
    assert validate_state(state) == []


def test_avaricum_noncity_replacement_removes_instead_of_violating_stacking():
    state = avaricum()
    tribe = next(t for t in eligible_allies(state, avaricum_regions(state), rc.AEDUI) if t not in rc.TRIBE_TO_CITY)
    _ally_tribe(state, tribe, rc.AEDUI)
    available = get_available(state, rc.AEDUI, rc.CITADEL)
    run(state, 41, {'citadel_upgrade_tribe': tribe})
    assert state['tribes'][tribe]['allied_faction'] is None
    assert get_available(state, rc.AEDUI, rc.CITADEL) == available
    assert validate_state(state) == []


def test_avaricum_restricted_city_ally_is_removed_without_illegal_citadel():
    state = avaricum(rc.ARVERNI)
    # A43/A30 can leave this exceptional Arverni Ally at Bibracte through
    # Interlude. Avaricum does not inherit those Events' stacking override.
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.ARVERNI)
    available = get_available(state, rc.ARVERNI, rc.CITADEL)
    run(state, 41, {'citadel_upgrade_tribe': rc.TRIBE_AEDUI})
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] is None
    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, rc.CITADEL) == 0
    assert get_available(state, rc.ARVERNI, rc.CITADEL) == available


def test_avaricum_missing_gate_or_foreign_ally_rejected_and_none_choices_legal():
    state = board(41)
    tribe = eligible_allies(state, [rc.BITURIGES], rc.AEDUI)[0]
    with pytest.raises(ValueError):
        run(state, 41, {'ally_placements': [{'tribe': tribe}]})
    state = avaricum()
    run(state, 41, {})
    assert state['resources'][rc.AEDUI] == 1
    foreign = ally(state, rc.PICTONES, rc.ARVERNI)
    with pytest.raises(ValueError):
        run(state, 41, {'citadel_upgrade_tribe': foreign})


def wine_board():
    state = board(42)
    controlled = []
    for region in (rc.SEQUANI, rc.PROVINCIA, rc.AEDUI_REGION, rc.BITURIGES):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 4)
        for tribe in eligible_allies(state, [region], rc.AEDUI):
            _ally_tribe(state, tribe, rc.AEDUI)
            controlled.append(tribe)
    adjacent = [ally(state, rc.TREVERI, rc.BELGAE), ally(state, rc.MANDUBII, rc.BELGAE)]
    return state, controlled, adjacent


@pytest.mark.parametrize('case', ['five', 'mixed', 'three_adjacent', 'distant', 'duplicate', 'wrong_owner'])
def test_wine_unshaded_rejects_wrong_quota_mode_geography_and_identity(case):
    state, controlled, adjacent = wine_board()
    if case == 'five':
        chosen = controlled[:5]
    elif case == 'mixed':
        chosen = controlled[:2] + adjacent[:1]
    elif case == 'three_adjacent':
        adjacent.append(ally(state, rc.PICTONES, rc.BELGAE))
        chosen = adjacent
    elif case == 'distant':
        chosen = [ally(state, rc.MORINI, rc.BELGAE)]
    elif case == 'duplicate':
        chosen = controlled[:1] * 2
    else:
        chosen = controlled[:1]
    params = {'removals': [{'tribe': t} for t in chosen]}
    if case == 'wrong_owner':
        params['removals'][0]['faction'] = rc.ROMANS
    state['event_params'] = params; before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 42)
    assert encode(state) == before


def test_wine_all_four_controlled_and_two_adjacent_and_explicit_zero_are_legal():
    for mode in ('controlled', 'adjacent'):
        state, controlled, adjacent = wine_board()
        chosen = controlled[:4] if mode == 'controlled' else adjacent
        run(state, 42, {'mode': mode, 'removals': [{'tribe': t} for t in chosen]})
        assert all(state['tribes'][t]['allied_faction'] is None for t in chosen)
        assert validate_state(state) == []
    state, _, _ = wine_board()
    run(state, 42, {'removals': []})


def test_wine_shaded_checks_supply_and_one_to_three_and_excludes_citadels():
    state = board(42)
    own = ally(state, rc.PROVINCIA, rc.ROMANS)
    far = ally(state, rc.MORINI, rc.ROMANS)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 3)
    for params in ({'removals': []}, {'removals': [{'tribe': far}]},
                   {'removals': [{'tribe': own, 'faction': rc.AEDUI}]}):
        state['event_params'] = params; before = encode(state)
        with pytest.raises(ValueError):
            execute_event(state, 42, True)
        assert encode(state) == before
    run(state, 42, {'removals': [{'tribe': own}]}, True)
    assert state['tribes'][own]['allied_faction'] is None


@pytest.mark.parametrize('case', ['outside', 'two_regions', 'five', 'too_few', 'repeat_new', 'wrong_type', 'missing_region'])
def test_surus_rejects_illegal_whole_selections(case):
    state = board(51)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 5)
    params = {'region': rc.TREVERI, 'replacements': [{'from_faction': rc.BELGAE, 'count': 4}]}
    if case == 'outside': params['region'] = rc.PROVINCIA
    elif case == 'two_regions': params['replacements'] = [{'from_faction': rc.BELGAE, 'region': rc.NERVII}]
    elif case == 'five': params['replacements'][0]['count'] = 5
    elif case == 'too_few': params['replacements'][0]['count'] = 3
    elif case == 'repeat_new': params['replacements'].append({'from_faction': rc.AEDUI})
    elif case == 'wrong_type': params['replacements'][0]['from_faction'] = rc.ROMANS
    else: params.pop('region')
    state['event_params'] = params; before = encode(state)
    with pytest.raises(ValueError): execute_event(state, 51)
    assert encode(state) == before


def test_surus_scouted_exact_originals_and_missing_replacements_still_remove():
    state = board(51)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    run(state, 51, {'region': rc.TREVERI, 'replacements': [
        {'from_faction': rc.BELGAE, 'piece_state': rc.SCOUTED, 'count': 2}]})
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 0
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert state['event_modifiers']['card_51_aedui_free_command']
    assert validate_state(state) == []


def test_surus_empty_selected_region_still_grants_command_and_prefix_is_not_final_quota():
    state = board(51)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 4)
    params = {'region': rc.TREVERI, 'replacements': [{'from_faction': rc.BELGAE}]}
    before = encode(state)
    preview = preview_event_prefix(state, rc.AEDUI, 51, False, params, step='51.replacements', index=1)
    assert count_pieces(preview, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 1
    assert encode(state) == before
    run(state, 51, {'region': rc.UBII, 'replacements': []})
    assert state['event_modifiers']['card_51_aedui_free_command']


@pytest.mark.parametrize('card', [40, 41, 42, 51, 'A29', 'A36', 65])
@pytest.mark.parametrize('params', [None, False, 0, [], '', [1]])
def test_explicit_human_event_params_must_be_an_object(card, params):
    state = board(card); before = encode(state)
    action = {'command': 'Event', 'details': {'card_id': card, 'event_params': params}}
    result = _execute_event(state, rc.AEDUI, action, human=True)
    assert not result['executed'] and result['rejected'] and 'object' in result['reason']
    assert encode(state) == before


def test_npc_avaricum_only_legal_targets_and_no_own_removal_default():
    state = avaricum(rc.ROMANS)
    params = derive_avaricum(state, rc.ROMANS, False)
    assert 'citadel_upgrade_tribe' not in params
    run(state, 41, params)
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.ALLY) >= 1
    assert sum(count_pieces(state, r, rc.ROMANS, rc.FORT) for r in avaricum_regions(state)) == 1
    assert validate_state(state) == []


def test_npc_wine_chooses_legal_alternative_and_aedui_player_targets():
    state = board(42)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    target = ally(state, rc.SEQUANI, rc.ARVERNI)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE}
    params = derive_wine(state, rc.AEDUI, False)
    assert params['mode'] == 'adjacent' and params['removals'] == [{'tribe': target, 'faction': rc.ARVERNI}]
    run(state, 42, params)
    assert state['tribes'][target]['allied_faction'] is None


def test_belgic_wine_specific_belgica_priority_precedes_larger_other_mode():
    state = board(42, rc.BELGAE)
    # Four controlled targets in the south; Treveri itself has no Ally but
    # supplies Roman Control next to two distinct Belgica targets.
    for region in (rc.PROVINCIA, rc.ARVERNI_REGION, rc.PICTONES, rc.TREVERI):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 4)
    targets = []
    southern = 0
    for region in (rc.PROVINCIA, rc.ARVERNI_REGION, rc.PICTONES):
        for tribe in eligible_allies(state, [region], rc.AEDUI):
            if southern < 4:
                assert _ally_tribe(state, tribe, rc.AEDUI)
                southern += 1
    for region in (rc.ATREBATES, rc.NERVII):
        targets.append(ally(state, region, rc.AEDUI))
    params = derive_wine(state, rc.BELGAE, False)
    assert params['mode'] == 'adjacent'
    assert {e['tribe'] for e in params['removals']} == set(targets)
    run(state, 42, params)


def test_expansion_wine_npc_target_order_swaps_germans_and_arverni():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=42)
    state['non_player_factions'] = {rc.AEDUI}
    # Equal non-City/Remi targets isolate the faction-order priority.
    for region in (rc.NERVII, rc.MORINI):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 4)
    german = ally(state, rc.NERVII, rc.GERMANS)
    belgic = ally(state, rc.MORINI, rc.BELGAE)
    params = derive_wine(state, rc.AEDUI, False)
    assert [e['tribe'] for e in params['removals']] == [german, belgic]


def test_cli_wine_and_surus_offer_only_selected_scope_and_exact_state(monkeypatch):
    state, controlled, adjacent = wine_board()
    before = encode(board_copy(state))
    count = 0
    def choose(stdin, stdout, prompt, choices):
        nonlocal count
        values = [value for _, value in choices]
        if prompt.startswith('Roman Wine: removal area'): return 'adjacent'
        assert prompt.startswith('Roman Wine: remove')
        assert set(values) <= {None, *adjacent, *controlled}
        count += 1
        return adjacent[0] if count == 1 else None
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    params = human_plan._collect_event_params(state, rc.AEDUI, 42, False, StringIO(), StringIO())
    assert params == {'mode': 'adjacent', 'removals': [{'tribe': adjacent[0]}]}
    assert encode(board_copy(state)) == before


def test_cli_board_and_eof_preserve_live_board():
    state = board(51)
    before = encode(state); output = StringIO()
    with pytest.raises(EOFError):
        human_plan._collect_event_params(state, rc.AEDUI, 51, False, StringIO('board\n'), output)
    assert rc.TREVERI in output.getvalue() and 'Resources' in output.getvalue()
    assert encode(state) == before
