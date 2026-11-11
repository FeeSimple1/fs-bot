"""Round-four Interlude deck and Tribe regressions."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_on_map, count_pieces, get_available
from fs_bot.cards.capabilities import activate_capability, is_capability_active
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_PASS, advance_to_next_card
from fs_bot.engine.interlude import _build_pax_gallica_deck_for_interlude, run_interlude
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.engine.winter import harvest_phase
from fs_bot.map.map_data import get_gallia_togata_card, get_tribes_in_region_for_state
from fs_bot.state.serialize import load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state
from fs_bot.tools.seat_session import SeatSession


def _first_half():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=21)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.GERMANS, rc.BELGAE}
    return state


def _play(state, card, faction, **params):
    result = _execute_event(state, faction, {'details': {
        'card_id': card, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': params}}, human=True)
    assert result['executed'] and not result.get('errors'), result


def _assert_integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def test_inactive_events_and_vergobret_can_be_dealt():
    state = _first_half()
    result = run_interlude(state, britannia_decision=False)['step10_deck']
    assert result == dict(deck_size=75, events_used=70, events_excluded=0, winters_in_piles=5)
    assert {5, 71, 'A38'} <= set(state['deck'])
    assert not {38, rc.CARD_O38} & set(state['deck'])
    _assert_integrity(state)


@pytest.mark.parametrize('legacy', [False, True])
def test_active_vergobret_stays_out_of_the_substituted_deck(legacy):
    state = _first_half()
    _play(state, 'A38', rc.AEDUI)
    if legacy:
        del state['capabilities']['A38']
    result = run_interlude(state, britannia_decision=False)['step10_deck']
    assert is_capability_active(state, 'A38', rc.EVENT_UNSHADED)
    assert not {38, 'A38', rc.CARD_O38} & set(state['deck'])
    assert result['events_excluded'] == 1
    _assert_integrity(state)


@pytest.mark.parametrize('exclude', [6, 7])
def test_short_deck_places_the_fifth_winter_even_without_the_last_pile(exclude):
    state = _first_half()
    active = [8, 10, 12, 13, 15, 39, 55][:exclude]
    for card in [*active, 'A33']:
        activate_capability(state, card, rc.EVENT_SHADED)

    result = _build_pax_gallica_deck_for_interlude(state)

    candidates = set(rc.CARD_NAMES_BASE) - {38} | {'A38'}
    assert set(state['deck']) - {rc.WINTER_CARD} == candidates - set(active)
    assert result['events_excluded'] == exclude
    assert result['events_used'] == 72 - exclude
    assert state['deck'].count(rc.WINTER_CARD) == 5
    assert result['winters_in_piles'] == (5 if exclude == 6 else 4)
    assert rc.WINTER_CARD in state['deck'][-(2 if exclude == 6 else 1):]


@pytest.mark.parametrize('colony_name', [None, 'Settlers', rc.TRIBE_CATUVELLAUNI])
def test_interlude_restores_printed_tribes_and_roman_harvest(colony_name):
    state = _first_half()
    assert rc.TRIBE_NORI in state['tribes'] and rc.TRIBE_CATUVELLAUNI not in state['tribes']
    if colony_name is not None:
        _play(state, 71, rc.AEDUI, region=rc.MANDUBII, colony_tribe_name=colony_name)
    _assert_integrity(state)

    run_interlude(state, britannia_decision=False)

    assert set(rc.BASE_TRIBES) <= set(state['tribes'])
    assert rc.TRIBE_NORI not in state['tribes']
    assert state['tribes'][rc.TRIBE_CATUVELLAUNI]['allied_faction'] == rc.BELGAE
    circles = 30 + int(colony_name is not None)
    assert len(state['tribes']) == circles
    if colony_name is not None:
        assert 71 not in state['deck'] and rc.MARKER_COLONY in state['markers'][rc.MANDUBII]
        extra = set(state['tribes']) - set(rc.BASE_TRIBES)
        assert len(extra) == 1
        assert extra <= set(get_tribes_in_region_for_state(state, rc.MANDUBII))
    enemy_structures = sum(count_on_map(state, faction, piece)
        for faction in (rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS)
        for piece in (rc.ALLY, rc.CITADEL))
    assert calculate_victory_score(state, rc.ROMANS) == circles - enemy_structures
    state['resources'][rc.ROMANS] = 0
    assert harvest_phase(state)[rc.ROMANS] == circles - enemy_structures
    _assert_integrity(state)


def test_nori_disc_leaves_when_gallia_togata_keeps_cisalpina_open():
    from fs_bot.engine.interlude import _step4_markers_cleanup
    state = _first_half()
    _play(state, 'A5', rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_NORI, rc.ROMANS)
    _play(state, 71, rc.ROMANS, region=rc.CISALPINA)
    state['markers'][rc.CISALPINA][rc.MARKER_NORI] = True
    avail = get_available(state, rc.ROMANS, rc.ALLY)

    assert _step4_markers_cleanup(state)['nori_marker_removed']

    assert rc.TRIBE_NORI not in state['tribes']
    assert get_gallia_togata_card(state) == 'A5'
    assert state['tribes'][f'Colony_{rc.CISALPINA}']['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.ALLY) == 1
    assert get_available(state, rc.ROMANS, rc.ALLY) == avail + 1
    _assert_integrity(state)


def test_in_effect_gallia_togata_is_retained_and_card_five_is_held_out():
    state = _first_half()
    _play(state, 'A5', rc.ROMANS)
    result = run_interlude(state, britannia_decision=False)
    assert result['step2_cisalpina']['skipped']
    assert get_gallia_togata_card(state) == 'A5'
    assert 5 not in state['deck'] and result['step10_deck']['events_excluded'] == 1
    _assert_integrity(state)


@pytest.mark.parametrize('journal', [False, True])
def test_old_post_interlude_save_retires_nori_without_redealing(tmp_path, journal):
    state = _first_half()
    run_interlude(state, britannia_decision=False)
    advance_to_next_card(state)
    state['tribes'][rc.TRIBE_NORI] = {'status': None, 'allied_faction': None}
    meta, log = {'seat': rc.ROMANS}, []
    display = HumanTurnDisplay(StringIO())
    request = {'kind': 'turn', 'options': [ACTION_PASS], 'position': rc.FIRST_ELIGIBLE}
    response = {'action': ACTION_PASS}
    if journal:
        session = SeatSession(state, meta, log, display)
        session.import_inbox([{'response': response}])
        assert session.ask(state, rc.ROMANS, request) == response
    path = tmp_path / 'legacy-interlude.json'
    save_game(state, path, meta=meta, log=log)

    loaded, meta, log = load_game(path, validate=True)

    assert loaded['deck'] == state['deck']
    assert loaded['rng'].getstate() == state['rng'].getstate()
    if journal:
        assert SeatSession(loaded, meta, log, display).ask(loaded, rc.ROMANS, request) == response
        assert advance_to_next_card(loaded) == state['deck'][0]
    assert rc.TRIBE_NORI not in loaded['tribes']
    _assert_integrity(loaded)
