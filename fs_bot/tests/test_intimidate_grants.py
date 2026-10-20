"""A45's selection exception and A3.4.3's actual Raiding-Warband credit."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_intimidate import intimidate
from fs_bot.engine.execute import _execute_intimidate, _resolve_card_A45_intimidate
from fs_bot.state.state_schema import build_initial_state


def position():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=9)
    st['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    return st


def plan(target=rc.ROMANS, piece=rc.AUXILIA, count=1, free=False):
    return {'details': {'intimidate_plan': [
        {'region': rc.MORINI, 'target_faction': target, 'target_piece': piece,
         'target_state': None, 'free': free} for _ in range(count)]}}


def test_savage_dictates_waives_selection_but_normal_intimidate_does_not():
    st = position()
    before = deepcopy(st['spaces'])
    assert _execute_intimidate(st, rc.GERMANS, plan())['errors']
    assert st['spaces'] == before
    result = _resolve_card_A45_intimidate(st)[0]['result']
    assert result['executed'] and not result['errors']
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(st, rc.MORINI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
    assert rc.MARKER_INTIMIDATED in st['markers'][rc.MORINI]
    # The exception belongs only to this grant; it cannot leak to another SA.
    assert not st.get('_intimidate_anywhere')


def test_savage_dictates_never_removes_legions_or_a_faction_with_a_leader():
    st = position()
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.LEGION, 1, from_legions_track=True)
    before = deepcopy(st['spaces'])
    result = _resolve_card_A45_intimidate(st)[0]['result']
    assert result['declined'] and not result['executed']
    assert st['spaces'] == before


def test_after_removing_pieces_np_places_markers_elsewhere_under_event_waiver():
    st = position()
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 1)
    result = _resolve_card_A45_intimidate(st)[0]['result']
    assert result['executed'] and not result['errors']
    assert rc.MARKER_INTIMIDATED in st['markers'][rc.MORINI]
    assert rc.MARKER_INTIMIDATED in st['markers'][rc.NERVII]
    assert count_pieces_by_state(st, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0


def test_savage_dictates_preserves_explicit_human_choice():
    st = position()
    st['non_player_factions'].remove(rc.GERMANS)
    class Human:
        def __call__(self, state, faction, request):
            assert faction == rc.GERMANS and request['card_id'] == 'A45'
            return {'command': None, 'sa': 'Intimidate', 'sa_regions': [rc.MORINI],
                    **plan(count=1)}
    st['decision_agent'] = Human()
    result = _resolve_card_A45_intimidate(st)[0]['result']
    assert result['executed']
    assert count_pieces(st, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 2


def test_target_selector_keeps_one_faction_and_exhausts_same_faction_allies():
    from fs_bot.bots.german_bot import _select_intimidate_targets
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    st['non_player_factions'] = {rc.GERMANS}
    place_piece(st, rc.AEDUI_REGION, rc.ROMANS, rc.ALLY, 2)
    place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY, 1)
    targets = _select_intimidate_targets(st, rc.AEDUI_REGION, 2)
    assert [(t['target_faction'], t['target_piece']) for t in targets] == [
        (rc.ROMANS, rc.ALLY), (rc.ROMANS, rc.ALLY)]


def test_mixed_faction_or_excessive_plan_is_rejected_before_mutation():
    st = position()
    place_piece(st, rc.MORINI, rc.AEDUI, rc.WARBAND, 1)
    mixed = plan()
    mixed['details']['intimidate_plan'] += plan(rc.AEDUI, rc.WARBAND)['details']['intimidate_plan']
    before = deepcopy(st['spaces'])
    assert _execute_intimidate(st, rc.GERMANS, mixed, ignore_selection=True)['errors']
    assert _execute_intimidate(st, rc.GERMANS, plan(count=3), ignore_selection=True)['errors']
    assert st['spaces'] == before


def test_bot_limits_intimidate_to_two_even_with_a_large_hidden_force():
    from fs_bot.bots.german_bot import _select_intimidate_targets
    st = position()
    assert len(_select_intimidate_targets(st, rc.MORINI, 10)) == 2
    assert _select_intimidate_targets(st, rc.MORINI, 0) == []


def test_overdrawn_removals_do_not_flip_warbands_or_place_markers():
    st = position()
    before = deepcopy(st['spaces'])
    with pytest.raises(CommandError):
        intimidate(st, rc.MORINI, 2, rc.AEDUI,
                   [(rc.WARBAND, None), (rc.WARBAND, None)])
    assert st['spaces'] == before
    assert rc.MARKER_INTIMIDATED not in st.get('markers', {}).get(rc.MORINI, {})


def test_actual_raid_credit_uses_revealed_warbands_once_and_can_place_only_marker():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=2)
    place_piece(st, rc.MORINI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.REVEALED)
    result = _execute_intimidate(st, rc.GERMANS, plan(None, None, free=True),
                                 raid_credits={rc.MORINI: 1})
    assert result['executed'] and not result['errors']
    assert result['intimidations'][0]['warbands_flipped'] == 0
    assert rc.MARKER_INTIMIDATED in st['markers'][rc.MORINI]
    # A free flag alone cannot claim that a newly Revealed Warband Raided.
    assert _execute_intimidate(st, rc.GERMANS, plan(None, None, free=True))['errors']


def test_raid_credit_cannot_remove_more_pieces_than_raided():
    st = position()
    from fs_bot.board.pieces import flip_piece
    flip_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 1,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    before = deepcopy(st['spaces'])
    result = _execute_intimidate(st, rc.GERMANS, plan(count=2, free=True),
                                 ignore_selection=True, raid_credits={rc.MORINI: 1})
    assert result['errors'] and st['spaces'] == before
