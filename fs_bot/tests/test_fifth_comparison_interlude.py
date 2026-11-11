"""WS5-01: Gallic War Interlude home-City restoration is limited to the City."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_on_map, count_pieces, move_piece, tribe_has_ally_disc
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.interlude import _adjust_aedui_forces
from fs_bot.engine.victory import check_any_victory
from fs_bot.engine.winter import run_winter_round
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state


@pytest.mark.parametrize('region,tribe,owner,step,restored', [
    (rc.AEDUI_REGION, rc.TRIBE_AEDUI, rc.AEDUI, 'step2_aedui', 'bibracte_replaced'),
    (rc.ARVERNI_REGION, rc.TRIBE_ARVERNI, rc.ARVERNI, 'step2_arverni', 'gergovia_replaced'),
])
@pytest.mark.parametrize('occupant', [rc.ALLY, None, rc.MARKER_DISPERSED])
def test_third_winter_keeps_a_legion_in_the_home_city_region(region, tribe, owner, step, restored,
                                                           occupant):
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=21)
    state['non_player_factions'] = {rc.AEDUI, rc.GERMANS, rc.BELGAE}
    move_piece(state, rc.PROVINCIA, region, rc.ROMANS, rc.LEGION)
    # Keep Rome below its victory threshold when the City is empty.
    assert _ally_tribe(state, rc.TRIBE_NAMNETES, rc.BELGAE)
    if occupant != rc.ALLY:
        _unally_tribe(state, tribe)
    if occupant == rc.MARKER_DISPERSED:
        state['tribes'][tribe]['status'] = occupant
        state['markers'].setdefault(tribe, {})[occupant] = True
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    assert check_any_victory(state) is None
    assert validate_state(state) == check_structural_integrity(state) == []
    track_before = dict(state['legions_track'])

    result = run_winter_round(state, britannia_decision=False)

    interlude = result['interlude']
    assert result['winter_count'] == 3 and state['scenario'] == rc.SCENARIO_PAX_GALLICA
    assert interlude[step][restored] == (occupant != rc.ALLY)
    assert not interlude['step3_britannia']['conducted']
    assert tribe_has_ally_disc(state, region, tribe, owner)
    assert count_pieces(state, region, rc.ROMANS, rc.LEGION) == 1
    assert count_on_map(state, rc.ROMANS, rc.LEGION) == 6
    assert state['legions_track'] == track_before
    assert state['tribes'][tribe]['status'] is None
    assert rc.MARKER_DISPERSED not in state['markers'].get(tribe, {})
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('card,piece,params', [
    ('A43', rc.ALLY, {}),  # Dumnorix's shaded stacking exception.
    ('A30', rc.CITADEL, {'placements': [
        {'region': rc.AEDUI_REGION, 'piece_type': rc.CITADEL},
        {'region': rc.AEDUI_REGION, 'piece_type': rc.WARBAND, 'count': 8},
    ]}),  # Orgetorix's shaded stacking exception.
])
def test_bibracte_restoration_replaces_the_event_occupant_only(card, piece, params):
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=21)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.GERMANS, rc.BELGAE}
    result = _execute_event(state, rc.GERMANS, {'details': {
        'card_id': card, 'text_preference': rc.EVENT_SHADED, 'event_params': params}}, human=True)
    assert result['executed'] and not result.get('errors'), result
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] == rc.ARVERNI
    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, piece) == 1
    warbands = count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND)
    assert warbands > 0
    assert validate_state(state) == check_structural_integrity(state) == []

    result = _adjust_aedui_forces(state)

    assert result['bibracte_replaced']
    assert tribe_has_ally_disc(state, rc.AEDUI_REGION, rc.TRIBE_AEDUI, rc.AEDUI)
    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, piece) == 0
    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND) == warbands
    assert validate_state(state) == check_structural_integrity(state) == []
