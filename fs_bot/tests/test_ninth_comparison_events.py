"""Alpine Tribes placement and Lost Eagle applicability from the ninth audit."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece, remove_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_sop_factions
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)
from fs_bot.tools.seat_session import board_copy


def ready(state, card):
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set(get_sop_factions(state)))
    return state


def position(card, scenario=rc.SCENARIO_ARIOVISTUS):
    state = ready(build_initial_state(scenario, seed=1), card)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['resources'].update({faction: 10 for faction in get_sop_factions(state)})
    return state


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1


def event_plan(card, params, *, shaded=False):
    return {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'event_params': params,
            'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
        },
    }}


def play(state, faction, params, *, shaded=False):
    check(state)
    result = execute_decision(state, faction, event_plan(state['current_card'], params,
                                                       shaded=shaded))
    assert result['executed'] and not result.get('errors'), result
    check(state)


def bot_event(state, faction):
    check(state)
    before = encode(state)
    assert not should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before
    action = dispatch_bot_turn(state, faction)
    assert action['command'] == rc.FIRST_DID_EVENT, action
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    check(state)


def declines(state, faction):
    check(state)
    before = encode(state)
    assert should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before
    control = deepcopy(state)
    control['can_play_event'] = False
    actual = dispatch_bot_turn(state, faction)
    assert actual['command'] != rc.FIRST_DID_EVENT
    assert actual == dispatch_bot_turn(control, faction)


def own_allies(state, faction):
    return {tribe for tribe, info in state['tribes'].items()
            if info['allied_faction'] == faction}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('faction,troop', [(rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)])
@pytest.mark.parametrize('troops_available', [True, False])
def test_alpine_tribes_bot_places_own_allies_first(scenario, faction, troop, troops_available):
    state = position('A40', scenario)
    if not troops_available:
        place_piece(state, rc.CARNUTES, faction, troop, get_available(state, faction, troop))
    initial_troops = get_available(state, faction, troop)
    initial_allies = get_available(state, faction, rc.ALLY)
    bot_event(state, faction)
    allies = own_allies(state, faction)
    assert len(allies) == 3
    assert len({rc.TRIBE_TO_REGION[tribe] for tribe in allies}) == 3
    assert allies <= {rc.TRIBE_NORI, rc.TRIBE_UBII, rc.TRIBE_SEQUANI, rc.TRIBE_HELVII}
    assert get_available(state, faction, rc.ALLY) == initial_allies - 3
    assert get_available(state, faction, troop) == initial_troops


def test_alpine_tribes_prefers_city_in_selected_region_and_fills_other_regions():
    state = position('A40')
    for tribe in (rc.TRIBE_NORI, rc.TRIBE_UBII, rc.TRIBE_HELVII):
        assert _ally_tribe(state, tribe, rc.GERMANS)
    # Sequani offers two Subdued circles. Ubii's other circle is Germans-only.
    bot_event(state, rc.AEDUI)
    assert own_allies(state, rc.AEDUI) == {rc.TRIBE_SEQUANI}
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 0
    assert sorted(count_pieces(state, region, rc.AEDUI, rc.WARBAND)
                  for region in (rc.CISALPINA, rc.UBII, rc.PROVINCIA)) == [0, 3, 3]


def togata_position():
    state = position('A5')
    play(state, rc.ROMANS, {})
    assert rc.MARKER_GALLIA_TOGATA in state['markers'][rc.CISALPINA]
    return ready(state, 'A40')


def occupy_other_alpine_tribes(state):
    for tribe in (rc.TRIBE_UBII, rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII, rc.TRIBE_HELVII):
        assert _ally_tribe(state, tribe, rc.GERMANS)


def test_alpine_tribes_bot_uses_troops_in_three_legal_regions_after_togata():
    state = togata_position()
    occupy_other_alpine_tribes(state)
    # Nori is still Subdued, but Aedui may not place any pieces in Cisalpina.
    bot_event(state, rc.AEDUI)
    assert not own_allies(state, rc.AEDUI)
    assert count_pieces(state, rc.CISALPINA, rc.AEDUI) == 0
    assert all(count_pieces(state, region, rc.AEDUI, rc.WARBAND) == 3
               for region in (rc.UBII, rc.SEQUANI, rc.PROVINCIA))


def test_alpine_tribes_bot_declines_when_only_forbidden_ally_and_other_stock_remain():
    state = togata_position()
    occupy_other_alpine_tribes(state)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND,
                get_available(state, rc.AEDUI, rc.WARBAND))
    declines(state, rc.AEDUI)


def placement(region, faction, piece_type, count=1, **fields):
    return {'region': region, 'faction': faction, 'piece_type': piece_type,
            'count': count, **fields}


@pytest.mark.parametrize('entry', [
    placement(rc.CISALPINA, rc.AEDUI, rc.WARBAND, 3),
    placement(rc.CISALPINA, rc.GERMANS, rc.ALLY, tribe=rc.TRIBE_NORI),
])
def test_authored_alpine_tribes_rejects_illegal_recipient_and_rolls_back(tmp_path, entry):
    state = togata_position()
    state['non_player_factions'].remove(rc.ROMANS)
    path = tmp_path / 'gallia-togata.json'
    save_game(state, path)
    state, _, _ = load_game(path, validate=True)
    plan = event_plan('A40', {'placements': [
        placement(rc.UBII, rc.ROMANS, rc.AUXILIA, 2), entry,
    ]})
    before = encode(board_copy(state))
    ok, preview = validate_player_action(state, rc.ROMANS, plan['player_action'])
    assert not ok and 'stacking' in preview['reason'], preview
    assert encode(board_copy(state)) == before
    result = execute_decision(state, rc.ROMANS, plan)
    assert result['rejected'] and not result['executed'] and 'stacking' in result['reason']
    assert encode(board_copy(state)) == before
    check(state)


def test_authored_alpine_tribes_allows_cisalpina_before_togata_and_roman_recipient_after():
    unrestricted = position('A40')
    play(unrestricted, rc.ROMANS, {'placements': [placement(rc.CISALPINA, rc.AEDUI, rc.WARBAND, 3)]})
    assert count_pieces(unrestricted, rc.CISALPINA, rc.AEDUI, rc.WARBAND) == 3
    restricted = togata_position()
    play(restricted, rc.AEDUI, {'placements': [
        placement(rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 2),
        placement(rc.UBII, rc.AEDUI, rc.ALLY, tribe=rc.TRIBE_UBII),
        placement(rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2),
    ]})
    assert count_pieces(restricted, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 5
    assert own_allies(restricted, rc.AEDUI) == {rc.TRIBE_UBII}
    assert count_pieces(restricted, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2
    play(restricted, rc.AEDUI, {'placements': []})


def fallen_legion(state):
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_fallen=True)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_RECONQUEST])
@pytest.mark.parametrize('missing', ['fallen', 'warband', 'non_aedui_warband'])
def test_lost_eagle_bot_requires_fallen_supply_and_qualifying_region(scenario, missing):
    state = position(33, scenario)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    if missing != 'fallen':
        fallen_legion(state)
    if missing == 'non_aedui_warband':
        place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    if missing == 'fallen':
        place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND)
    else:
        # A nearby Warband does not qualify unless it shares the Legion's Region.
        place_piece(state, rc.UBII, rc.ARVERNI, rc.WARBAND)

    assert not is_event_effective(state, 33)
    declines(state, rc.ROMANS)
    if missing == 'fallen':
        fallen_legion(state)
    else:
        place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND)
    track = deepcopy(state['legions_track'])
    assert is_event_effective(state, 33)
    bot_event(state, rc.ROMANS)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert state['fallen_legions'] == 0
    assert state['legions_track'] == track


def test_lost_eagle_is_ineffective_on_untouched_pax_setup():
    state = ready(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 33)
    assert state['fallen_legions'] == 0
    declines(state, rc.ROMANS)


def test_lost_eagle_preserves_authored_destination_and_shaded_senate_effect():
    state = position(33, rc.SCENARIO_GREAT_REVOLT)
    for region, enemy in [(rc.SEQUANI, rc.GERMANS), (rc.MANDUBII, rc.BELGAE)]:
        place_piece(state, region, rc.ROMANS, rc.LEGION, from_legions_track=True)
        place_piece(state, region, enemy, rc.WARBAND)
    fallen_legion(state)
    before = encode(state)
    assert _collect_event_params(state, rc.AEDUI, 33, False,
                                 StringIO(f'{rc.MANDUBII}\n'), StringIO()) == {
                                     'target_region': rc.MANDUBII}
    assert encode(state) == before
    play(state, rc.AEDUI, {'target_region': rc.MANDUBII})
    assert state['fallen_legions'] == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 2
    play(state, rc.AEDUI, {}, shaded=True)
    assert state['event_modifiers']['lost_eagle_no_shift_down'] is True


def test_lost_eagle_bot_rolls_between_equal_destinations_only_at_execution():
    state = position(33, rc.SCENARIO_GREAT_REVOLT)
    regions = [region for region in rc.ALL_REGIONS if region in (rc.SEQUANI, rc.MANDUBII)]
    for region in regions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, from_legions_track=True)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    fallen_legion(state)
    expected_rng = deepcopy(state['rng'])
    target = regions[expected_rng.randint(0, 1)]
    bot_event(state, rc.ROMANS)
    assert count_pieces(state, target, rc.ROMANS, rc.LEGION) == 2
    assert state['rng'].getstate() == expected_rng.getstate()
