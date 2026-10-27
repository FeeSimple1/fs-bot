"""A66 held-card choices are durable across timing, placement, and Command.

The printed card gives Belgae/Germans 2 Allies and 4 Warbands within one
Region, or Arverni 4 and 8. The Gallic War's Winter Events step requires
activation; ordinary Quarters windows leave the holder's timing choice open.
"""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe, execute_card_A66
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.winter_uprising_resolution import (
    PLACEMENT, TIMING, active, placement_request, validate_response,
)
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import _resolve_winter_uprising
from fs_bot.engine.game_engine import _action_transaction, get_sop_factions
from fs_bot.engine.interlude import _step1_winter_events
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state(region=rc.MORINI, holder=rc.ROMANS, humans=(rc.ROMANS, rc.BELGAE),
           scenario=rc.SCENARIO_ARIOVISTUS):
    state = build_initial_state(scenario, seed=66)
    state['non_player_factions'] = set(get_sop_factions(state)) - set(humans)
    state['current_card'] = state['current_card_id'] = rc.WINTER_CARD
    state['played_cards'] = ['A66', rc.WINTER_CARD]
    state['deck'], state['next_card'] = [1, rc.WINTER_CARD], 1
    state['executing_faction'], state['event_params'] = holder, {'region': region}
    execute_card_A66(state)
    state.pop('executing_faction')
    state.pop('event_params')
    return state


def _placement(request):
    return {'allies': request['tribes'][:request['allies']],
            'warbands': ([{'region': request['region'], 'count': request['warbands']}]
                         if request['warbands'] else [])}


def _session(state=None, seat=rc.BELGAE, meta=None, log=None):
    state = state if state is not None else _state(humans=(seat,))
    meta = meta if meta is not None else {'seat': seat, 'scenario': state['scenario'], 'seed': 66}
    session = SeatSession(state, meta, log if log is not None else [],
                          HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _run(session, forced=False):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _resolve_winter_uprising(session.state, forced=forced)


def _assert_pending_unchanged(session, before, pending, response):
    session.import_inbox({'decision_id': pending['id'], 'response': response})
    queue = copy.deepcopy(session.data['queue'])
    journal = copy.deepcopy(session.data['journal'])
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.error and session.data['pending'] == pending
    assert session.data['queue'] == queue and session.data['journal'] == journal
    assert encode(board_copy(session.state)) == before


def test_holder_can_keep_the_card_and_marker_for_a_later_quarters_window():
    session = _session(_state(), seat=rc.ROMANS)
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session)
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == TIMING and request['faction'] == rc.ROMANS
    assert request['holder'] == rc.ROMANS and request['forced'] is False
    assert request['card_text'] == get_card_text('A66', session.state['scenario'])
    assert encode(board_copy(session.state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': {'activate': False}})
    result = _run(session)
    session.finish()
    assert result[0]['deferred'] and active(session.state)
    assert encode(board_copy(session.state)) == before
    assert [entry['reactive'] for entry in session.log] == [TIMING]


@pytest.mark.parametrize('response', [None, {}, {'activate': 1}, {'activate': 1.0},
                                     {'activate': True, 'extra': False},
                                     {'decline': True}, {'use_default': 1},
                                     {'use_default': 1.0}])
def test_invalid_timing_keeps_input_pending_and_preserves_board_rng(response):
    session = _session(_state(), seat=rc.ROMANS)
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session)
    _assert_pending_unchanged(session, before, copy.deepcopy(session.data['pending']), response)


@pytest.mark.parametrize('region,beneficiary', [(rc.MORINI, rc.BELGAE),
                                              (rc.SUGAMBRI, rc.GERMANS)])
def test_holder_timing_then_beneficiary_placement_and_complete_free_command(region, beneficiary):
    state = _state(region, humans=(rc.ROMANS, beneficiary))
    state['resources'][beneficiary] = 0
    requests = []

    def agent(board, faction, request):
        requests.append((faction, copy.deepcopy(request)))
        if request['kind'] == TIMING:
            return {'activate': True}
        if request['kind'] == PLACEMENT:
            return _placement(request)
        if request['kind'] == 'free_action':
            return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'regions': [region],
                    'sa_regions': [], 'details': {
                        'origins': [region], 'destinations': [rc.NERVII],
                        'routes': {region: [rc.NERVII]},
                        'groups': {region: {rc.WARBAND: 4, rc.LEADER: False}}}}
        return None

    state['decision_agent'] = agent
    results = _resolve_winter_uprising(state)
    primary = [(faction, request) for faction, request in requests
               if request['kind'] in (TIMING, PLACEMENT, 'free_action')]
    assert [(faction, request['kind']) for faction, request in primary] == [
        (rc.ROMANS, TIMING), (beneficiary, PLACEMENT), (beneficiary, 'free_action')]
    assert all(request['card_text'] == get_card_text('A66', state['scenario'])
               for _, request in primary[:2])
    grant = primary[-1][1]
    assert grant['with_sa'] is True and grant['allow_decline'] is False
    assert set(grant['allowed_regions']) == set(primary[1][1]['regions'])
    assert results[0]['allies'] == 2 and results[0]['warbands'] == 4
    assert results[-1]['executed']
    assert count_pieces(state, region, beneficiary, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, beneficiary, rc.WARBAND) == 4
    assert state['resources'][beneficiary] == 0 and not active(state)


def test_accepted_timing_waits_for_same_holders_arverni_placement():
    session = _session(_state(rc.CISALPINA, humans=(rc.ROMANS,)), seat=rc.ROMANS)
    before = encode(board_copy(session.state))
    session.import_inbox([{'response': {'activate': True}}])
    with pytest.raises(DecisionPending):
        _run(session)
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == PLACEMENT and request['faction'] == rc.ROMANS
    assert request['beneficiary'] == rc.ARVERNI and request['holder'] == rc.ROMANS
    assert request['allies'] == 4 and request['warbands'] == 8
    assert request['regions'] == [rc.CISALPINA, rc.PROVINCIA, rc.SEQUANI, rc.UBII]
    assert len(session.data['journal']) == 1
    assert active(decode(pending['board'])) and encode(board_copy(session.state)) == before


def test_placement_default_then_command_pending_survives_save_and_exact_replay(tmp_path):
    session = _session()
    origin = copy.deepcopy(board_copy(session.state))
    session.import_inbox([{'response': {'use_default': True}}])
    with pytest.raises(DecisionPending):
        _run(session)
    pending = copy.deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['kind'] == 'free_action' and request['faction'] == rc.BELGAE
    assert request['with_sa'] and request['allow_decline'] is False
    midboard = decode(pending['board'])
    assert not active(midboard)
    assert sum(count_pieces(midboard, region, rc.BELGAE, rc.WARBAND)
               for region in midboard['spaces']) == 4
    assert midboard['rng'].getstate() != origin['rng'].getstate()
    assert encode(board_copy(session.state)) == encode(origin)
    assert len(session.data['journal']) == 1 and session.log == []

    save_game(session.state, tmp_path / 'uprising.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'uprising.json')
    resumed = _session(restored, meta=meta, log=log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'use_default': True}})
    result = _run(resumed)
    resumed.finish()
    assert result[0]['executed'] and result[-1]['executed'] and not active(restored)
    assert [entry['reactive'] for entry in resumed.log] == [PLACEMENT, 'free_action']
    assert not resumed.data['pending'] and not resumed.data['journal']

    replay = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature']}
                               for entry in resumed.log]
    assert _run(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(restored))
    assert replay.log == resumed.log


@pytest.mark.parametrize('response', [None, {'decline': True}, {'use_default': 1},
                                     {'use_default': 1.0}])
def test_mandatory_command_cannot_decline_or_silently_default_durable_input(response):
    session = _session()
    before = encode(board_copy(session.state))
    request = placement_request(session.state, rc.MORINI, rc.ROMANS)
    session.import_inbox([{'response': _placement(request)}])
    with pytest.raises(DecisionPending):
        _run(session)
    assert decode(session.data['pending']['request'])['kind'] == 'free_action'
    _assert_pending_unchanged(session, before, copy.deepcopy(session.data['pending']), response)


@pytest.mark.parametrize('fault', ['missing_allies', 'duplicate_ally', 'outside_ally',
                                  'too_few_warbands', 'too_many_warbands',
                                  'outside_region', 'zero_count', 'negative_count',
                                  'boolean_count', 'float_count', 'extra_key',
                                  'numeric_default'])
def test_invalid_physical_placements_keep_marker_and_durable_decision_pending(fault):
    session = _session()
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session)
    pending = copy.deepcopy(session.data['pending'])
    request = decode(pending['request'])
    response = _placement(request)
    if fault == 'missing_allies':
        response['allies'].pop()
    elif fault == 'duplicate_ally':
        response['allies'][1] = response['allies'][0]
    elif fault == 'outside_ally':
        response['allies'][0] = rc.TRIBE_ARVERNI
    elif fault == 'outside_region':
        response['warbands'][0]['region'] = rc.CISALPINA
    elif fault == 'extra_key':
        response['free'] = True
    elif fault == 'numeric_default':
        response = {'use_default': 1}
    else:
        response['warbands'][0]['count'] = {
            'too_few_warbands': 3, 'too_many_warbands': 5, 'zero_count': 0,
            'negative_count': -1, 'boolean_count': True, 'float_count': 4.0}[fault]
    _assert_pending_unchanged(session, before, pending, response)
    assert active(session.state) and session.state['decision_agent'] == session.reactive


def test_placement_counts_are_bounded_by_physical_available_and_allow_split_regions():
    state = _state()
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND) - 3)
    request = placement_request(state, rc.MORINI, rc.ROMANS)
    assert request['allies'] == 2 and request['warbands'] == 3
    response = {'allies': [rc.TRIBE_MORINI, rc.TRIBE_MENAPII],
                'warbands': [{'region': rc.MORINI, 'count': 1},
                             {'region': rc.NERVII, 'count': 2}]}
    before = encode(board_copy(state))
    assert validate_response(state, request, response) == response
    assert encode(board_copy(state)) == before


def test_allies_use_only_available_discs_and_still_require_every_placeable_one():
    state = _state()
    offered = placement_request(state, rc.MORINI, rc.ROMANS)
    # Keep all printed-neighbourhood choices open while spending the remaining
    # physical discs elsewhere through the normal Ally operation.
    for tribe in state['tribes']:
        if get_available(state, rc.BELGAE, rc.ALLY) <= 1:
            break
        if tribe not in offered['tribes'] and tribe not in rc.TRIBE_FACTION_RESTRICTION:
            assert _ally_tribe(state, tribe, rc.BELGAE)
    assert get_available(state, rc.BELGAE, rc.ALLY) == 1
    request = placement_request(state, rc.MORINI, rc.ROMANS)
    assert request['allies'] == 1 and request['warbands'] == 4
    response = _placement(request)
    before = encode(board_copy(state))
    assert validate_response(state, request, response) == response
    response['allies'] = []
    with pytest.raises(ValueError, match='required Available Allies'):
        validate_response(state, request, response)
    assert encode(board_copy(state)) == before


def test_gallic_war_interlude_requires_placement_without_optional_timing():
    session = _session(_state(humans=(rc.ROMANS, rc.BELGAE),
                             scenario=rc.SCENARIO_GALLIC_WAR))
    before = encode(board_copy(session.state))
    observed = []

    def agent(board, faction, request):
        observed.append((faction, request['kind']))
        return session.reactive(board, faction, request)

    session.state['decision_agent'] = agent
    with pytest.raises(DecisionPending):
        _step1_winter_events(session.state)
    assert observed == [(rc.BELGAE, PLACEMENT)]
    request = decode(session.data['pending']['request'])
    assert request['forced'] is True and request['holder'] == rc.ROMANS
    assert encode(board_copy(session.state)) == before

    session.import_inbox([{'decision_id': session.data['pending']['id'],
                          'response': _placement(request)},
                         {'response': {'use_default': True}}])
    result = _step1_winter_events(session.state)
    session.finish()
    assert result['events_resolved'] == ['Winter Uprising!']
    assert result['winter_uprising'][0]['forced'] is True
    assert result['winter_uprising'][-1]['executed'] and not active(session.state)
    assert all(kind != TIMING for _, kind in observed)


def test_terminal_timing_and_physical_choices_show_full_card_and_support_board():
    state = _state()
    request = placement_request(state, rc.MORINI, rc.ROMANS)
    output, inspected = io.StringIO(), []
    # Timing activation; explicit placements; two distinct Allies; split 1+3.
    stream = io.StringIO('board\n1\n1\n1\n1\n1\n1\n2\n3\nuntouched\n')
    agent = make_cli_reactive([rc.ROMANS, rc.BELGAE], stream, output)
    before = encode(board_copy(state))
    set_board_hook(lambda: inspected.append(format_board(state)))
    try:
        timing = agent(state, rc.ROMANS, dict(request, kind=TIMING))
        placement = agent(state, rc.BELGAE, request)
    finally:
        set_board_hook(None)
    assert timing == {'activate': True}
    assert placement['allies'] == request['tribes'][:2]
    assert placement['warbands'] == [{'region': request['regions'][0], 'count': 1},
                                     {'region': request['regions'][1], 'count': 3}]
    assert validate_response(state, request, placement) == placement
    assert stream.readline() == 'untouched\n' and len(inspected) == 1
    assert encode(board_copy(state)) == before
    shown = output.getvalue()
    assert rc.ROMANS in shown and rc.BELGAE in shown
    assert shown.count(get_card_text('A66', state['scenario'])) == 2


@pytest.mark.parametrize('stream', ['', '1\n', '1\n1\n1\n'])
def test_terminal_eof_during_timing_or_placement_rolls_back_card_and_rng(stream):
    state = _state()
    output = io.StringIO()
    agent = make_cli_reactive([rc.ROMANS, rc.BELGAE], io.StringIO(stream), output)
    state['decision_agent'] = agent
    before = encode(board_copy(state))
    with pytest.raises(EOFError):
        _resolve_winter_uprising(state)
    assert encode(board_copy(state)) == before and active(state)
    assert state['decision_agent'] is agent
    assert get_card_text('A66', state['scenario']) in output.getvalue()
