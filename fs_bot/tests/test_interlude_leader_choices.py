"""Named Leader placement in The Gallic War's Adjust Forces step.

The scenario places Ambiorix with most *other* Belgic pieces, even from
Available. Available Caesar goes to Roman-Controlled Provincia, otherwise
where most Romans. These are mandatory named placements, before the later
ordinary Spring; they do not inherit its own-piece/Home eligibility limit.
"""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, get_leader_in_region, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.interlude import (
    _adjust_belgae_forces, _adjust_roman_forces, _choose_interlude_leader_region,
)
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state(seed=1, human=None):
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.GERMANS, rc.AEDUI, rc.BELGAE} - {human}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


@pytest.mark.parametrize('incumbent', [None, rc.BODUOGNATUS, rc.SUCCESSOR])
def test_interlude_places_named_ambiorix_even_without_other_belgic_pieces(incumbent):
    state = _state()
    if incumbent:
        place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=incumbent)
    result = _adjust_belgae_forces(state)
    region = result['ambiorix_placed']
    assert region in get_playable_regions_for_state(state, rc.BELGAE)
    assert region != rc.BRITANNIA
    assert get_leader_in_region(state, region, rc.BELGAE) == rc.AMBIORIX
    assert get_available(state, rc.BELGAE, rc.LEADER) == 0
    assert sum(count_pieces(state, r, rc.BELGAE, rc.LEADER) for r in state['spaces']) == 1


def test_zero_other_piece_np_ties_are_seeded_and_do_not_favor_incumbent():
    chosen = set()
    for seed in range(20):
        state = _state(seed)
        place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
        replay = copy.deepcopy(state)
        before_rng = state['rng'].getstate()
        result = _adjust_belgae_forces(state)
        assert _adjust_belgae_forces(replay) == result
        assert encode(replay) == encode(state)
        assert state['rng'].getstate() != before_rng
        chosen.add(result['ambiorix_placed'])
    assert len(chosen) > 1
    assert chosen - set(rc.BELGAE_HOME_REGIONS)
    assert rc.BRITANNIA not in chosen


def test_human_ambiorix_tie_is_between_most_other_pieces_not_leader_biased():
    state = _state(human=rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
    requests = []

    def agent(board, faction, request):
        requests.append((faction, request))
        assert get_leader_in_region(board, rc.MORINI, rc.BELGAE) == rc.SUCCESSOR
        return {'region': rc.NERVII}

    state['decision_agent'] = agent
    before = encode(board_copy(state))
    assert _choose_interlude_leader_region(
        state, rc.BELGAE, rc.AMBIORIX, exclude_leader=True) == rc.NERVII
    assert len(requests) == 1 and requests[0][0] == rc.BELGAE
    request = requests[0][1]
    assert request['kind'] == 'spring_leader' and request['source'] == 'interlude'
    assert request['leader'] == rc.AMBIORIX and request['can_defer'] is False
    assert set(request['legal_regions']) == {rc.MORINI, rc.NERVII}
    assert encode(board_copy(state)) == before


def test_named_ambiorix_uses_post_adjustment_counts_and_can_leave_belgica():
    state = _state()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    # The scenario removes half of Warbands before placing Ambiorix. A single
    # occupied non-Home Region still contains the surviving half afterwards.
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 6)
    result = _adjust_belgae_forces(state)
    assert result['warbands_to_available'] == 3
    assert result['ambiorix_placed'] == rc.CARNUTES
    assert get_leader_in_region(state, rc.CARNUTES, rc.BELGAE) == rc.AMBIORIX


def test_available_caesar_prefers_roman_controlled_provincia_over_larger_army():
    state = _state(human=rc.ROMANS)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    refresh_all_control(state)
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args)
    result = _adjust_roman_forces(state)
    assert result['caesar_placed'] == rc.PROVINCIA and not calls
    assert get_leader_in_region(state, rc.PROVINCIA, rc.ROMANS) == rc.CAESAR


def _tied_roman_state(human=None, seed=1):
    state = _state(seed, human)
    # Provincia's permanent Fort remains, but is outnumbered. Legions are
    # untouched by this adjustment, leaving an exact two-way placement tie.
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 2)
    for region in (rc.MANDUBII, rc.CARNUTES):
        place_piece(state, region, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    refresh_all_control(state)
    return state


def test_human_available_caesar_chooses_tied_maximum_when_no_provincia_control():
    state = _tied_roman_state(human=rc.ROMANS)
    requests = []

    def agent(board, faction, request):
        requests.append((faction, request))
        return {'region': rc.MANDUBII}

    state['decision_agent'] = agent
    result = _adjust_roman_forces(state)
    assert result['caesar_placed'] == rc.MANDUBII
    assert get_leader_in_region(state, rc.MANDUBII, rc.ROMANS) == rc.CAESAR
    assert len(requests) == 1 and requests[0][0] == rc.ROMANS
    assert requests[0][1]['leader'] == rc.CAESAR
    assert set(requests[0][1]['legal_regions']) == {rc.MANDUBII, rc.CARNUTES}


def test_np_caesar_ties_are_seeded_and_never_choose_lower_count_provincia():
    selected = set()
    for seed in range(12):
        state = _tied_roman_state(seed=seed)
        replay = copy.deepcopy(state)
        result = _adjust_roman_forces(state)
        assert _adjust_roman_forces(replay) == result
        assert encode(state) == encode(replay)
        selected.add(result['caesar_placed'])
    assert selected == {rc.MANDUBII, rc.CARNUTES}


@pytest.mark.parametrize('leader', [rc.CAESAR, rc.SUCCESSOR])
def test_on_map_roman_leader_is_neither_relocated_nor_renamed(leader):
    state = _state(human=rc.ROMANS)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=leader)
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args)
    result = _adjust_roman_forces(state)
    assert result['caesar_placed'] is None and not calls
    assert get_leader_in_region(state, rc.MORINI, rc.ROMANS) == leader


def _session(state=None, meta=None, log=None):
    state = state if state is not None else _state(human=rc.BELGAE)
    meta = meta if meta is not None else {'seat': rc.BELGAE, 'scenario': state['scenario'], 'seed': 1}
    session = SeatSession(state, meta, log if log is not None else [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _run(session):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _adjust_belgae_forces(session.state)


@pytest.mark.parametrize('response', [None, {}, {'defer': True}, {'region': rc.BRITANNIA},
                                     {'region': rc.MORINI, 'defer': False},
                                     {'use_default': 1}, {'use_default': 1.0}])
def test_invalid_interlude_tie_remains_pending_without_losing_incumbent_or_rng(response):
    state = _state(human=rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    session = _session(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        _run(session)
    pending = copy.deepcopy(session.data['pending'])
    assert get_leader_in_region(decode(pending['board']), rc.MORINI, rc.BELGAE) == rc.SUCCESSOR
    session.import_inbox({'decision_id': pending['id'], 'response': response})
    queue = copy.deepcopy(session.data['queue'])
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.error and session.data['pending'] == pending
    assert session.data['queue'] == queue and not session.data['journal']
    assert encode(board_copy(state)) == before


def test_human_interlude_choice_survives_save_resume_and_replay(tmp_path):
    state = _state(human=rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    session = _session(state)
    origin = copy.deepcopy(board_copy(state))
    with pytest.raises(DecisionPending):
        _run(session)
    pending = copy.deepcopy(session.data['pending'])
    save_game(state, tmp_path / 'interlude.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'interlude.json')
    resumed = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'region': rc.CISALPINA}})
    result = _run(resumed)
    resumed.finish()
    assert result['ambiorix_placed'] == rc.CISALPINA
    assert get_leader_in_region(restored, rc.CISALPINA, rc.BELGAE) == rc.AMBIORIX
    assert len(resumed.log) == 1 and resumed.log[0]['reactive'] == 'spring_leader'

    replay = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature']}
                               for entry in resumed.log]
    assert _run(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(restored))
    assert replay.log == resumed.log
