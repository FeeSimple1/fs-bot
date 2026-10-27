"""A23's printed meeting, NP restrictions, and next-card eligibility."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, find_leader, count_pieces,
    count_pieces_by_state,
)
from fs_bot.cards.parley import meeting_choices, np_choices, derive_params
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import (
    ACTION_EVENT, ACTION_PASS, resolve_card_turn, adjust_eligibility,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=23)
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    st['current_card'] = 'A23'
    st['event_params'] = None
    st['executing_faction'] = None
    return st


def event(st, target=rc.SEQUANI, who='both', *, human=True, faction=rc.BELGAE):
    return _execute_event(st, faction, {'details': {'card_id': 'A23',
        'event_params': {'meeting_region': target, 'who_moves': who}}}, human=human)


def test_two_regions_apart_moves_entire_named_groups_including_scouted():
    st = state()
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    for ps in (rc.HIDDEN, rc.REVEALED):
        place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=ps)
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND, 2, piece_state=ps)
    before_pools = deepcopy(st['available'])
    assert event(st)['executed']
    assert find_leader(st, rc.ROMANS) == find_leader(st, rc.GERMANS) == rc.SEQUANI
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    for ps in (rc.HIDDEN, rc.REVEALED):
        assert count_pieces_by_state(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, ps) == 2
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, ps) == 2
        assert count_pieces_by_state(st, rc.UBII, rc.GERMANS, rc.WARBAND, ps) == 0
    assert st['available'] == before_pools
    assert check_structural_integrity(st) == []


@pytest.mark.parametrize('choice', [1, 2])
def test_adjacent_menu_offers_both_legal_directions(choice):
    st = state()
    move_piece(st, rc.UBII, rc.SEQUANI, rc.GERMANS, rc.LEADER)
    out = StringIO()
    params = _collect_event_params(st, rc.BELGAE, 'A23', False,
                                   StringIO(f'{choice}\n'), out)
    assert 'Caesar to Sequani' in out.getvalue()
    assert 'Ariovistus to Provincia' in out.getvalue()
    assert (params['meeting_region'], params['who_moves']) in meeting_choices(st)
    assert event(st, params['meeting_region'], params['who_moves'])['executed']
    assert find_leader(st, rc.ROMANS) == find_leader(st, rc.GERMANS) == params['meeting_region']


def test_gallia_togata_keeps_only_the_legal_meeting_direction():
    """A5's Roman-only stacking still applies to A23 (§5.1.1)."""
    st = state()
    assert _execute_event(st, rc.ROMANS, {'details': {
        'card_id': 'A5', 'text_preference': rc.EVENT_UNSHADED,
        'event_params': {},
    }}, human=True)['executed']
    move_piece(st, rc.PROVINCIA, rc.CISALPINA, rc.ROMANS, rc.LEADER)
    move_piece(st, rc.UBII, rc.PROVINCIA, rc.GERMANS, rc.LEADER)
    place_piece(st, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, count=2)
    assert meeting_choices(st) == [(rc.PROVINCIA, 'caesar')]
    assert all(region != rc.CISALPINA for region, _ in np_choices(st, rc.GERMANS))
    out = StringIO()
    params = _collect_event_params(st, rc.BELGAE, 'A23', False,
                                   StringIO('1\n'), out)
    assert params == {'meeting_region': rc.PROVINCIA, 'who_moves': 'caesar'}
    assert 'Ariovistus to Cisalpina' not in out.getvalue()
    before = deepcopy(st)
    result = event(st, rc.CISALPINA, 'ariovistus')
    assert not result['executed']
    for key in ('spaces', 'available', 'resources', 'eligibility'):
        assert st[key] == before[key]
    assert event(st, rc.PROVINCIA, 'caesar')['executed']
    assert find_leader(st, rc.ROMANS) == find_leader(st, rc.GERMANS) == rc.PROVINCIA
    assert count_pieces(st, rc.CISALPINA, rc.GERMANS) == 0
    assert check_structural_integrity(st) == []


@pytest.mark.parametrize('target,who', [(rc.MORINI, 'both'), (rc.SEQUANI, 'caesar'),
                                      (rc.SEQUANI, 'invalid'), (None, None)])
def test_invalid_or_missing_plan_does_not_move_or_change_eligibility(target, who):
    st = state()
    before = deepcopy(st)
    result = event(st, target, who)
    assert not result['executed']
    assert 'legal meeting_region' in result['reason']
    for key in ('spaces', 'available', 'eligibility', 'resources'):
        assert st[key] == before[key]
    assert st['rng'].getstate() == before['rng'].getstate()
    assert not st.get('forced_ineligible')


@pytest.mark.parametrize('case', ['absent', 'successor', 'same', 'distant'])
def test_impossible_meeting_still_applies_independent_eligibility(case):
    st = state()
    if case in ('absent', 'successor'):
        remove_piece(st, rc.UBII, rc.GERMANS, rc.LEADER)
        if case == 'successor':
            place_piece(st, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    else:
        move_piece(st, rc.UBII, rc.PROVINCIA if case == 'same' else rc.MORINI,
                   rc.GERMANS, rc.LEADER)
    assert meeting_choices(st) == []
    before = deepcopy(st['spaces'])
    assert event(st, None, None)['executed']
    assert st['spaces'] == before
    adjust_eligibility(st, {rc.BELGAE: {'action': ACTION_EVENT}})
    assert st['eligibility'][rc.ROMANS] == st['eligibility'][rc.GERMANS] == rc.INELIGIBLE


def test_production_turn_retains_ineligibility_through_next_card_only():
    st = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=21)
    st['current_card'], st['next_card'] = 'A23', 1
    st['non_player_factions'] = {rc.ROMANS, rc.GERMANS, rc.AEDUI}
    def choose(board, faction, options, position):
        if faction != rc.BELGAE:
            return {'action': ACTION_PASS}
        return {'action': ACTION_EVENT, 'player_action': {
            'command': 'Event', 'sa': 'No SA', 'sa_regions': [], 'details': {
                'card_id': 'A23', 'event_params': {
                    'meeting_region': rc.SEQUANI, 'who_moves': 'both'}}}}
    result = resolve_card_turn(st, choose, execute=True)
    assert result['actions_taken'][rc.BELGAE]['execution']['executed']
    assert st['eligibility'][rc.ROMANS] == st['eligibility'][rc.GERMANS] == rc.INELIGIBLE
    assert check_structural_integrity(st) == []
    adjust_eligibility(st, {})
    assert st['eligibility'][rc.ROMANS] == st['eligibility'][rc.GERMANS] == rc.ELIGIBLE


def test_roman_np_requires_fort_and_strict_superiority_after_meeting():
    st = state()
    move_piece(st, rc.UBII, rc.SEQUANI, rc.GERMANS, rc.LEADER)
    # Provincia's permanent Fort already makes 2 Roman pieces vs 1 German.
    assert np_choices(st, rc.ROMANS) == [(rc.PROVINCIA, 'ariovistus')]
    assert event(st, human=False, faction=rc.ROMANS)['executed']
    assert find_leader(st, rc.GERMANS) == rc.PROVINCIA
    assert np_choices(st, rc.ROMANS) == []
    assert np_event_available(st, 'A23', rc.ROMANS, False) is False


def test_german_np_requires_no_fort_and_strict_superiority():
    st = state()
    assert np_choices(st, rc.GERMANS) == []  # one Leader each is a tie
    place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND)
    assert np_event_available(st, 'A23', rc.GERMANS, False)
    assert event(st, human=False, faction=rc.GERMANS)['executed']
    assert find_leader(st, rc.GERMANS) == find_leader(st, rc.ROMANS) == rc.SEQUANI


def test_unprioritized_np_choices_use_seeded_rng_and_preview_is_read_only():
    st = state()
    move_piece(st, rc.UBII, rc.SEQUANI, rc.GERMANS, rc.LEADER)
    duplicate = deepcopy(st)
    before_rng = st['rng'].getstate()
    assert np_choices(st, rc.BELGAE) == [(rc.SEQUANI, 'caesar'), (rc.PROVINCIA, 'ariovistus')]
    assert st['rng'].getstate() == before_rng
    assert derive_params(st, rc.BELGAE) == derive_params(duplicate, rc.BELGAE)
    assert st['rng'].getstate() != before_rng
