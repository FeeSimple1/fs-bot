"""WS7-01 through the real Quarters and Winter entry points."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, find_leader, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.quarters import quarters_factions, validate_quarters_plan
from fs_bot.engine.winter import quarters_phase, run_winter_round
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


SEATS = (rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.GERMANS)
LEADERS = {rc.BELGAE: rc.AMBIORIX, rc.ARVERNI: rc.VERCINGETORIX,
           rc.GERMANS: rc.ARIOVISTUS_LEADER}


def check(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def position(faction=rc.BELGAE, scenario=None):
    if scenario is None:
        scenario = rc.SCENARIO_ARIOVISTUS if faction == rc.GERMANS else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=1)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['non_player_factions'] = set(quarters_factions(state))
    return state


def devastate(state, region):
    state['markers'].setdefault(region, {})[rc.MARKER_DEVASTATED] = True


def warbands(state, region, faction, number, visibility=rc.HIDDEN):
    place_piece(state, region, faction, rc.WARBAND, number, piece_state=visibility)


@pytest.mark.parametrize('faction', SEATS)
def test_bot_evacuates_unprotected_warbands_before_desertion(faction):
    state = position(faction)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        warbands(state, rc.CARNUTES, faction, 1, visibility)
    warbands(state, rc.BITURIGES, faction, 1)
    devastate(state, rc.CARNUTES)
    check(state)

    result = quarters_phase(state)

    assert result['gallic_relocations'][faction] == [(rc.WARBAND, rc.CARNUTES, rc.BITURIGES, 3)]
    assert result['gallic_desertion'][faction] == {}
    assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == 0
    assert [count_pieces_by_state(state, rc.BITURIGES, faction, rc.WARBAND, vis)
            for vis in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)] == [2, 1, 1]
    check(state)


@pytest.mark.parametrize('faction,piece', [
    (rc.BELGAE, rc.ALLY), (rc.AEDUI, rc.CITADEL),
    (rc.ARVERNI, rc.CITADEL), (rc.GERMANS, rc.SETTLEMENT),
])
def test_own_ally_citadel_or_settlement_protects_devastated_region(faction, piece):
    state = position(faction)
    warbands(state, rc.CARNUTES, faction, 3)
    warbands(state, rc.BITURIGES, faction, 1)
    if piece == rc.SETTLEMENT:
        place_piece(state, rc.CARNUTES, faction, piece)
    else:
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, faction, citadel=piece == rc.CITADEL)
    devastate(state, rc.CARNUTES)
    check(state)

    result = quarters_phase(state)

    assert result['gallic_relocations'][faction] == []
    assert result['gallic_desertion'][faction] == {}
    assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == 3
    check(state)


@pytest.mark.parametrize('faction', tuple(LEADERS))
def test_leader_moves_with_escort_and_keeps_a_warband_at_origin(faction):
    state = position(faction)
    place_piece(state, rc.CARNUTES, faction, rc.LEADER, leader_name=LEADERS[faction])
    warbands(state, rc.CARNUTES, faction, 3)
    warbands(state, rc.BITURIGES, faction, 8)
    check(state)

    result = quarters_phase(state)

    assert result['gallic_relocations'][faction] == [
        (rc.LEADER, rc.CARNUTES, rc.BITURIGES, 1),
        (rc.WARBAND, rc.CARNUTES, rc.BITURIGES, 2),
    ]
    assert find_leader(state, faction) == rc.BITURIGES
    assert count_pieces(state, rc.BITURIGES, faction, rc.WARBAND) == 10
    assert is_controlled_by(state, rc.CARNUTES, faction)
    check(state)


def test_leader_and_only_one_group_can_join_from_different_origins():
    state = position()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    warbands(state, rc.CARNUTES, rc.BELGAE, 1)
    warbands(state, rc.BITURIGES, rc.BELGAE, 8)
    warbands(state, rc.BITURIGES, rc.AEDUI, 4)
    warbands(state, rc.MANDUBII, rc.BELGAE, 6)
    warbands(state, rc.PICTONES, rc.BELGAE, 3)
    check(state)

    result = quarters_phase(state)

    assert result['gallic_relocations'][rc.BELGAE] == [
        (rc.LEADER, rc.CARNUTES, rc.BITURIGES, 1),
        (rc.WARBAND, rc.MANDUBII, rc.BITURIGES, 5),
    ]
    assert count_pieces(state, rc.BITURIGES, rc.BELGAE, rc.WARBAND) == 13
    assert count_pieces(state, rc.PICTONES, rc.BELGAE, rc.WARBAND) == 3
    check(state)


def test_control_reserve_counts_all_opponents_and_the_departing_leader():
    state = position()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    warbands(state, rc.CARNUTES, rc.BELGAE, 5)
    warbands(state, rc.CARNUTES, rc.ARVERNI, 2)
    warbands(state, rc.CARNUTES, rc.AEDUI, 2)
    warbands(state, rc.BITURIGES, rc.BELGAE, 8)
    warbands(state, rc.BITURIGES, rc.AEDUI, 6)
    check(state)

    result = quarters_phase(state)

    assert result['gallic_relocations'][rc.BELGAE] == [(rc.LEADER, rc.CARNUTES, rc.BITURIGES, 1)]
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 5
    assert is_controlled_by(state, rc.CARNUTES, rc.BELGAE)
    check(state)


def test_arrivals_cannot_follow_leader_out_of_the_refuge_in_the_same_phase():
    state = position()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    warbands(state, rc.CARNUTES, rc.BELGAE, 6)
    warbands(state, rc.BITURIGES, rc.BELGAE, 2)
    warbands(state, rc.AEDUI_REGION, rc.BELGAE, 8)
    devastate(state, rc.CARNUTES)
    original = deepcopy(state)
    check(state)

    result = quarters_phase(state)

    moves = result['gallic_relocations'][rc.BELGAE]
    assert moves == [(rc.LEADER, rc.CARNUTES, rc.BITURIGES, 1),
                     (rc.WARBAND, rc.CARNUTES, rc.BITURIGES, 6),
                     (rc.WARBAND, rc.AEDUI_REGION, rc.BITURIGES, 7)]
    assert validate_quarters_plan(original, {rc.BELGAE: moves}) == []
    assert find_leader(state, rc.BELGAE) == rc.BITURIGES
    assert count_pieces(state, rc.BITURIGES, rc.BELGAE, rc.WARBAND) == 15
    assert result['gallic_desertion'][rc.BELGAE] == {}
    check(state)


@pytest.mark.parametrize('scenario,destination', [
    (rc.SCENARIO_GREAT_REVOLT, rc.MANDUBII), (rc.SCENARIO_ARIOVISTUS, rc.MORINI),
])
def test_belgic_geographic_priority_substitutes_for_proximity(scenario, destination):
    state = position(scenario=scenario)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    warbands(state, rc.ATREBATES, rc.BELGAE, 1)
    for region in (rc.MANDUBII, rc.MORINI):
        warbands(state, region, rc.BELGAE, 3)
    for region in (rc.BITURIGES, rc.AEDUI_REGION):
        warbands(state, region, rc.BELGAE, 1)

    result = quarters_phase(state)

    assert result['gallic_relocations'][rc.BELGAE] == [(rc.LEADER, rc.ATREBATES, destination, 1)]
    assert find_leader(state, rc.BELGAE) == destination
    check(state)


def test_bot_aedui_may_evacuate_into_non_player_roman_control():
    state = position(rc.AEDUI, rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    warbands(state, rc.CARNUTES, rc.AEDUI, 3)
    place_piece(state, rc.BITURIGES, rc.ROMANS, rc.FORT)
    devastate(state, rc.CARNUTES)
    warbands(state, rc.PICTONES, rc.ARVERNI, 2)
    devastate(state, rc.PICTONES)

    result = quarters_phase(state)

    assert result['gallic_relocations'][rc.AEDUI] == [
        (rc.LEADER, rc.CARNUTES, rc.BITURIGES, 1),
        (rc.WARBAND, rc.CARNUTES, rc.BITURIGES, 3),
    ]
    assert rc.ARVERNI not in result['gallic_relocations']
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 2
    check(state)


def test_bot_aedui_stay_if_only_refuge_is_devastated():
    state = position(rc.AEDUI)
    warbands(state, rc.CARNUTES, rc.AEDUI, 3)
    devastate(state, rc.CARNUTES)
    warbands(state, rc.BITURIGES, rc.AEDUI, 1)
    devastate(state, rc.BITURIGES)

    result = quarters_phase(state)

    assert result['gallic_relocations'][rc.AEDUI] == []
    assert result['gallic_desertion'][rc.AEDUI][rc.CARNUTES] == {
        'rolls': [2, 5, 1], 'removed': 2,
    }
    check(state)


def test_pax_first_winter_uses_bot_quarters_after_the_germans_phase_skip():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    state['non_player_factions'] = set(quarters_factions(state))
    warbands(state, rc.CARNUTES, rc.AEDUI, 3)
    warbands(state, rc.BITURIGES, rc.AEDUI, 1)
    devastate(state, rc.CARNUTES)
    check(state)

    result = run_winter_round(state)

    phases = result['phases']
    assert phases['germans'] == {'skipped': '1st Winter special rule'}
    assert sum(move[3] for move in phases['quarters']['gallic_relocations'][rc.AEDUI]
               if move[1] == rc.CARNUTES and move[0] == rc.WARBAND) == 3
    assert rc.CARNUTES not in phases['quarters']['gallic_desertion'][rc.AEDUI]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    check(state)


@pytest.mark.parametrize('agree,destination', [(True, rc.BITURIGES), (False, rc.MANDUBII)])
def test_aedui_host_agreement_resumes_and_replays_without_a_second_request(
        tmp_path, agree, destination):
    state = position(rc.AEDUI)
    state['non_player_factions'].remove(rc.BELGAE)
    warbands(state, rc.CARNUTES, rc.AEDUI, 3)
    devastate(state, rc.CARNUTES)
    warbands(state, rc.BITURIGES, rc.BELGAE, 5)
    warbands(state, rc.MANDUBII, rc.AEDUI, 1)
    initial = deepcopy(state)

    def is_host_request(owner, request):
        return (owner == rc.BELGAE and request['kind'] == 'agreement'
                and request['request_type'] == 'quarters')

    def session(board, meta=None, log=None):
        result = SeatSession(board, {'seat': rc.BELGAE} if meta is None else meta,
                             [] if log is None else log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda live, owner, request: (
            result.reactive(live, owner, request) if is_host_request(owner, request) else None)
        return result

    def step(current):
        def driver(*_args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            return quarters_phase(current.state)

    active = session(state)
    with pytest.raises(DecisionPending):
        step(active)
    pending = deepcopy(active.data['pending'])
    request = decode(pending['request'])
    assert request['context']['region'] == rc.BITURIGES
    assert request['requesting_faction'] == rc.AEDUI
    assert encode(board_copy(state)) == encode(initial)
    active.import_inbox({'decision_id': pending['id'], 'response': {'agree': agree}})
    with pytest.raises(DecisionPending):
        step(active)
    assert active.error and active.data['pending'] == pending
    assert encode(board_copy(state)) == encode(initial)
    path = tmp_path / 'quarters.json'
    save_game(state, path, meta=active.meta, log=active.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session(restored, meta, log)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': agree})
    result = step(resumed)
    resumed.finish()
    assert len(log) == 1
    assert result['gallic_relocations'][rc.AEDUI] == [(rc.WARBAND, rc.CARNUTES, destination, 3)]

    offered = []
    def replay_agent(_state, owner, request):
        if is_host_request(owner, request):
            offered.append(dict(request, faction=owner))
            return decode(log[0]['assistant_response'])

    initial['decision_agent'] = replay_agent
    assert quarters_phase(initial) == result
    assert offered == [decode(log[0]['assistant_request'])]
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    check(restored)
