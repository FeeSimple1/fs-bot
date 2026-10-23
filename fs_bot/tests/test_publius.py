"""A17's bounded Roman March/Battle and its Roman 8.8.1 instructions."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.board.pieces import count_pieces, place_piece, get_leader_in_region
from fs_bot.cards.publius import default_plan, validate_march, march_routes, resolve_publius, _np_group
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.engine import execute as ex
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.engine.game_engine import get_sop_factions, _action_transaction
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def board(human=False):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    st['non_player_factions'] = set(get_sop_factions(st))
    if human:
        st['non_player_factions'].remove(rc.ROMANS)
    st['current_card'] = st['current_card_id'] = 'A17'
    st['next_card'] = 4
    return st


def force(st, region=rc.PROVINCIA, legions=4, auxilia=4):
    if legions:
        place_piece(st, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if auxilia:
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, auxilia, piece_state=rc.REVEALED)


def ally(st, region=rc.MANDUBII, tribe=rc.TRIBE_MANDUBII, faction=rc.ARVERNI):
    place_piece(st, region, faction, rc.ALLY)
    st['tribes'][tribe]['allied_faction'] = faction


def plan(origin=rc.PROVINCIA, route=None, legions=2, auxilia=3):
    return {'origin': origin, 'route': [rc.SEQUANI, rc.MANDUBII] if route is None else route,
            'legions': legions, 'auxilia': auxilia}


def battle(region=rc.MANDUBII, target=rc.ARVERNI):
    return {'command': rc.CMD_BATTLE, 'regions': [region],
            'details': {'battle_plan': [{'region': region, 'target': target}]}}


@pytest.mark.parametrize('legions,auxilia', [(0, 0), (0, 8), (4, 0)])
def test_np_requires_both_piece_classes_before_selecting_event(legions, auxilia):
    st = board()
    force(st, legions=legions, auxilia=auxilia)
    ally(st)
    called = []
    st['decision_agent'] = lambda *args: called.append(args)
    before = encode(board_copy(st))
    assert np_event_available(st, 'A17', rc.AEDUI, False) is False
    assert encode(board_copy(st)) == before and not called
    assert np_event_available(st, 'A17', rc.AEDUI, True) is None


def test_np_filters_caesar_before_destination_priority_tiers():
    st = board()
    force(st)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    ally(st, rc.SEQUANI, rc.TRIBE_SEQUANI)
    ally(st, faction=rc.BELGAE)
    refresh_all_control(st)
    chosen = default_plan(st)
    assert len(chosen['route']) == 2 and chosen['route'][-1] == rc.MANDUBII
    result = resolve_publius(st)[0]
    assert result['region'] == rc.MANDUBII
    assert get_leader_in_region(st, rc.SEQUANI, rc.ROMANS) == rc.CAESAR
    assert validate_state(st) == []


def test_np_caps_departures_before_computing_extra_auxilia_control():
    st = board()
    force(st, rc.SEQUANI, 8, 8)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 6)
    refresh_all_control(st)
    assert _np_group(st, rc.SEQUANI) == (4, 6)
    # Leaving4Legions+6Aux keeps7Romans against6Belgae. The forbidden
    # uncapped8Legions+Leader departure would incorrectly allow all8Aux.
    assert is_controlled_by(st, rc.SEQUANI, rc.ROMANS)


def test_human_in_place_march_is_legal_but_np_instructions_require_marching_out():
    st = board(True)
    force(st, rc.MANDUBII, legions=1, auxilia=1)
    ally(st)
    selected = plan(rc.MANDUBII, [], legions=1, auxilia=1)
    validate_march(st, selected)
    assert default_plan(st) is None  # only enemy base is in the origin
    st['decision_agent'] = lambda s, f, r: selected if r.get('request_type') == 'publius_march' else None
    result = resolve_publius(st)[0]
    assert result['region'] == rc.MANDUBII and result['battle']['executed']
    assert count_pieces(st, rc.MANDUBII, rc.ARVERNI, rc.ALLY) == 0


@pytest.mark.parametrize('changes', [
    {'legions': 0}, {'legions': 5}, {'auxilia': 0}, {'auxilia': 9},
    {'legions': True}, {'leader': True}, {'_harassers': {}},
    {'route': [rc.SEQUANI, rc.MANDUBII, rc.CARNUTES]},
])
def test_invalid_human_group_or_route_cannot_mutate(changes):
    st = board(True)
    force(st, legions=8, auxilia=12)
    response = dict(plan(), **changes)
    before = encode(st)
    assert validate_free_action_response(st, rc.ROMANS,
        {'request_type': 'publius_march'}, response)
    assert encode(st) == before


def test_caesar_destination_and_alps_or_abatis_continuation_are_rejected():
    st = board()
    force(st)
    place_piece(st, rc.MANDUBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    with pytest.raises(ValueError):
        validate_march(st, plan())
    routes = march_routes(st, rc.PROVINCIA, 2, 3)
    assert [rc.CISALPINA, rc.UBII] not in routes
    st['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_ABATIS] = True
    assert [rc.SEQUANI, rc.TREVERI] not in march_routes(st, rc.PROVINCIA, 2, 3)


def test_human_real_march_harassment_then_double_auxilia_battle():
    st = board(True)
    force(st)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 3)
    requests, before_battle = [], []
    def choose(live, faction, request):
        if request['kind'] != 'free_action':
            return None
        requests.append(request)
        if request['request_type'] == 'publius_march':
            return plan()
        before_battle.append(count_pieces(live, rc.MANDUBII, rc.ROMANS, rc.AUXILIA))
        return battle()
    st['decision_agent'] = choose
    result = resolve_publius(st)[0]
    assert len(requests) == 2 and result['battle']['executed']
    assert before_battle == [2]
    assert requests[1]['double_auxilia'] and requests[1]['allow_decline'] is False
    assert requests[1]['allowed_regions'] == [rc.MANDUBII]
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(st, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 0
    assert st['resources'][rc.ROMANS] == 0 and validate_state(st) == []


def test_battle_is_mandatory_after_accepting_march_but_whole_action_may_decline():
    st = board(True)
    force(st)
    st['decision_agent'] = lambda *args: {'decline': True}
    before = encode(board_copy(st))
    assert resolve_publius(st)[0]['declined_no_effect']
    assert encode(board_copy(st)) == before
    assert validate_free_action_response(st, rc.ROMANS,
        {'allow_decline': False}, {'decline': True})


def test_np_availability_accepts_possible_human_agreement_without_consuming_it():
    st = board()
    st['non_player_factions'].remove(rc.BELGAE)
    force(st)
    ally(st)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 6)
    # Close the alternative two-step route via Aedui with guaranteed
    # Arverni Harassment; only agreement in Sequani makes the route legal.
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND, 6)
    called = []
    def refuse_harassment(live, faction, request):
        if request.get('request_type') == 'harassment':
            called.append((faction, request['context']['region']))
            return False
        return None
    st['decision_agent'] = refuse_harassment
    before = encode(board_copy(st))
    assert np_event_available(st, 'A17', rc.ROMANS, False)
    assert not called and encode(board_copy(st)) == before
    result = resolve_publius(st)[0]
    assert result['region'] == rc.MANDUBII
    assert called.count((rc.BELGAE, rc.SEQUANI)) == 1


def test_availability_cannot_assume_game_run_arverni_will_refuse_harassment():
    st = board()
    force(st)
    ally(st)
    for region in (rc.SEQUANI, rc.AEDUI_REGION):
        place_piece(st, region, rc.ARVERNI, rc.WARBAND, 6)
    assert np_event_available(st, 'A17', rc.AEDUI, False) is False
    assert default_plan(st) is None


def test_human_dropoffs_may_leave_single_piece_to_continue():
    st = board(True)
    force(st)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND)
    selected = plan()
    selected['dropoffs'] = {rc.SEQUANI: {rc.LEGION: 2, rc.AUXILIA: 2}}
    st['decision_agent'] = lambda s, f, r: (selected if r.get('request_type') == 'publius_march'
        else battle() if r['kind'] == 'free_action' else None)
    result = resolve_publius(st)[0]
    assert result['battle']['executed']
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 0
    assert validate_state(st) == []


@pytest.mark.parametrize('drops', [
    {rc.SEQUANI: {rc.LEGION: 3}},
    {rc.SEQUANI: {rc.LEGION: 2, rc.AUXILIA: 3}},
    {rc.MANDUBII: {rc.LEGION: 1}},
    {rc.SEQUANI: {rc.LEADER: 1}},
    {rc.SEQUANI: {rc.AUXILIA: -1}},
])
def test_invalid_dropoffs_are_rejected_before_movement(drops):
    st = board(True)
    force(st)
    selected = plan()
    selected['dropoffs'] = drops
    with pytest.raises(ValueError):
        validate_march(st, selected)


def test_harassment_wipeout_cannot_redirect_battle_to_caesar_in_transit():
    st = board(True)
    st['rng'].seed(3)
    force(st, legions=1, auxilia=1)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 6)
    selected = plan(route=[rc.SEQUANI, rc.AEDUI_REGION], legions=1, auxilia=1)
    st['decision_agent'] = lambda s, f, r: selected if r.get('request_type') == 'publius_march' else None
    result = resolve_publius(st)[0]
    assert result['march']['region'] == rc.SEQUANI
    assert result['region'] == rc.AEDUI_REGION
    assert result['battle']['declined_no_effect']
    assert get_leader_in_region(st, rc.SEQUANI, rc.ROMANS) == rc.CAESAR
    assert count_pieces(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 6
    assert validate_state(st) == []


def test_surviving_leader_continues_after_successful_harassment_save():
    # The shared March executor must not reapply a zero-removal loss report
    # as a Leader casualty. No human loss choice is needed with Leader alone.
    st = board()
    st['rng'].seed(0)  # first die is4: Caesar survives
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    final = ex._march_with_harassment(st, rc.ROMANS, rc.PROVINCIA,
        [rc.SEQUANI, rc.AEDUI_REGION], group_cap={rc.LEADER: True})
    assert final == rc.AEDUI_REGION
    assert get_leader_in_region(st, rc.AEDUI_REGION, rc.ROMANS) == rc.CAESAR
    assert get_leader_in_region(st, rc.SEQUANI, rc.ROMANS) is None
    assert validate_state(st) == []


def test_real_menu_preserves_board_command_counts_route_and_dropoffs():
    from fs_bot.cli.free_actions import collect_free_action
    from fs_bot.cli.menus import set_board_hook
    st = board(True)
    force(st)
    output, calls = StringIO(), []
    set_board_hook(lambda: calls.append('board'))
    before = encode(st)
    try:
        response = collect_free_action(st, rc.ROMANS, {'request_type': 'publius_march'},
            StringIO('Plan the action\nboard\nProvincia\n2\n3\n'
                     'Provincia → Sequani → Mandubii\n2 Legion\n2 Auxilia\n'), output)
    finally:
        set_board_hook(None)
    assert response == dict(plan(), dropoffs={rc.SEQUANI: {rc.LEGION: 2, rc.AUXILIA: 2}})
    assert calls == ['board'] and encode(st) == before


def test_frost_battle_preview_includes_actual_doubled_auxilia():
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    st = board()
    force(st, rc.MANDUBII, legions=1, auxilia=2)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 4)
    before = encode(st)
    outcomes = list(_battle_frost_outcomes(st, rc.MANDUBII, rc.ARVERNI,
        attacker=rc.ROMANS, command=True, double_auxilia=True))
    assert outcomes and all(count_pieces(s, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 1 for s in outcomes)
    assert encode(st) == before


def test_a17_consumes_both_one_event_flags_even_when_declined():
    st = board(True)
    st['decision_agent'] = lambda *args: {'decline': True}
    result = ex._execute_event(st, rc.AEDUI, {'command': 'Event', 'details': {
        'card_id': 'A17', 'text_preference': rc.EVENT_UNSHADED}}, human=True)
    assert result['free_actions'][0]['declined_no_effect']
    assert 'card_A17_roman_march_battle' not in st['event_modifiers']
    assert 'card_A17_double_auxilia_losses' not in st['event_modifiers']
    assert ex._resolve_free_actions(st, rc.AEDUI) == []


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def test_human_pause_save_resume_shows_march_changes_and_replays_exactly(tmp_path):
    st = board(True)
    force(st)
    place_piece(st, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 3)
    output = StringIO()
    display = HumanTurnDisplay(output)
    display.remember(st, [rc.ROMANS])
    session = SeatSession(st, {'seat': rc.ROMANS}, [], display)
    st['decision_agent'] = session.reactive
    session.import_inbox([{'response': plan()}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, _driver(session)):
            resolve_publius(st)
    assert encode(board_copy(st)) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['allow_decline'] is False
    pending_board = decode(pending['board'])
    assert count_pieces(pending_board, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 2
    assert 'Publius Licinius Crassus' in output.getvalue()
    assert 'Mandubii: Romans +2 Legion' in output.getvalue()
    saved = tmp_path / 'publius.json'
    save_game(st, saved, meta=session.meta, log=session.log)
    restored, meta, log = load_game(saved)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox({'decision_id': pending['id'], 'response': battle()})
    with _action_transaction(restored, _driver(resumed)):
        result = resolve_publius(restored)
    resumed.finish()
    assert len(log) == 2 and validate_state(restored) == []
    replay = SeatSession(decode(before), {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    replay.state['decision_agent'] = replay.reactive
    replay.data['expected'] = [{'id': r['assistant_id'], 'signature': r['assistant_signature']} for r in log]
    replay.import_inbox([{'decision_id': r['assistant_id'], 'response': decode(r['assistant_response'])} for r in log])
    with _action_transaction(replay.state, _driver(replay)):
        assert resolve_publius(replay.state) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(restored))


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('seed', [73, 103, 161])
def test_captured_bot_games_no_longer_select_or_refuse_unavailable_publius(scenario, seed):
    from fs_bot.tools.run_batch import play_one
    result = play_one((scenario, seed))
    assert result['completed'] and not result['integrity_findings']
    assert not [d for d in result['diagnostics'] if d['severity'] != 'legal-decline'
                and d['example'][2] == 'A17']
