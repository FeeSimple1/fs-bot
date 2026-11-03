"""A21/A57, §5.1/5.1.3/5.4 and §3.2.4/3.3.4: human Battle choices."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.card_effects import execute_card_A21, execute_card_A57
from fs_bot.engine.execute import _resolve_free_actions
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(card='A57', faction=rc.BELGAE):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=12)
    state['current_card'] = state['current_card_id'] = card
    state['next_card'] = 4
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS} - {faction}
    state['resources'][faction] = 0
    (execute_card_A21 if card == 'A21' else execute_card_A57)(state)
    return state


def recorder(state, choices, retreats=None):
    requests = []
    answers = iter(choices)
    def agent(current, faction, request):
        requests.append((faction, deepcopy(request)))
        if request.get('request_type') == 'decisive_battle':
            return next(answers)
        if request['kind'] == 'retreat':
            return retreats or {'retreat': False, 'region': None}
        return None
    state['decision_agent'] = agent
    return requests


@pytest.mark.parametrize('card,region', [('A21', rc.SEQUANI), ('A57', rc.NERVII)])
def test_human_belgae_choose_non_roman_defender_without_np_legion_restriction(card, region):
    state = board(card)
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    requests = recorder(state, [{'region': region, 'defender': rc.GERMANS}])
    result = _resolve_free_actions(state, rc.BELGAE)
    assert count_pieces(state, region, rc.GERMANS) == 0
    grants = [r for _, r in requests if r.get('request_type') == 'decisive_battle']
    assert len(grants) == 1 and grants[0]['phase'] == 'first'
    assert grants[0]['no_retreat'] and not grants[0]['allow_decline']
    assert result[0]['defender'] == rc.GERMANS and result[0]['result']['executed']
    assert state['resources'][rc.BELGAE] == 0 and validate_state(state) == []


def test_second_battle_is_human_optional_and_cannot_be_decided_by_np_worthwhile():
    state = board(faction=rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    requests = recorder(state, [{'region': rc.NERVII, 'defender': rc.BELGAE}, {'decline': True}])
    result = _resolve_free_actions(state, rc.ROMANS)
    grants = [r for _, r in requests if r.get('request_type') == 'decisive_battle']
    assert [r['phase'] for r in grants] == ['first', 'second']
    assert grants[1]['allowed_regions'] == [rc.NERVII]
    assert grants[1]['allow_decline'] and not grants[1]['no_retreat']
    assert sum(bool(r.get('result', {}).get('executed')) for r in result) == 1
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 2


def test_first_suppresses_retreat_but_second_honors_human_retreat():
    state = board(faction=rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 1)
    from fs_bot.board.control import refresh_all_control
    refresh_all_control(state)
    requests = recorder(state, [{'region': rc.NERVII, 'defender': rc.BELGAE}] * 2,
                        {'retreat': True, 'region': rc.MORINI})
    result = _resolve_free_actions(state, rc.ROMANS)
    phases = [r.get('phase', r['kind']) for _, r in requests
              if r.get('request_type') == 'decisive_battle' or r['kind'] == 'retreat']
    assert phases == ['first', 'second', 'retreat']
    assert result[1]['result']['executed']
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 3
    assert validate_state(state) == []


@pytest.mark.parametrize('card,region', [('A21', rc.SEQUANI), ('A57', rc.NERVII)])
def test_human_germans_ignore_np_ariovistus_warband_floor(card, region):
    state = board(card, rc.GERMANS)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, region, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 2)
    requests = recorder(state, [{'region': region, 'defender': rc.BELGAE}])
    result = _resolve_free_actions(state, rc.GERMANS)
    grant = next(r for _, r in requests if r.get('request_type') == 'decisive_battle')
    assert not grant['default_available']
    assert result[0]['defender'] == rc.BELGAE and result[0]['result']['executed']
    assert count_pieces(state, region, rc.BELGAE) == 0
    assert validate_state(state) == []


def test_second_rebuilds_options_can_choose_different_static_defender():
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    requests = recorder(state, [{'region': rc.NERVII, 'defender': rc.GERMANS},
                                {'region': rc.NERVII, 'defender': rc.ROMANS}])
    result = _resolve_free_actions(state, rc.BELGAE)
    grants = [r for _, r in requests if r.get('request_type') == 'decisive_battle']
    assert grants[0]['defenders_by_region'][rc.NERVII] == [rc.ROMANS, rc.GERMANS]
    assert grants[1]['defenders_by_region'] == {rc.NERVII: [rc.ROMANS]}
    assert not grants[1]['default_available']  # NP worthwhile requires enemy mobile pieces.
    assert [(r['region'], r['defender']) for r in result] == [
        (rc.NERVII, rc.GERMANS), (rc.NERVII, rc.ROMANS)]
    assert result[1]['result']['executed'] and validate_state(state) == []


def test_human_selects_any_legal_region_instead_of_largest_np_target():
    state = board(faction=rc.AEDUI)
    for region in (rc.MORINI, rc.NERVII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 6)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 10)
    requests = recorder(state, [{'region': rc.MORINI, 'defender': rc.GERMANS}])
    result = _resolve_free_actions(state, rc.AEDUI)
    assert result[0]['region'] == rc.MORINI
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 10
    assert len([r for _, r in requests if r.get('request_type') == 'decisive_battle']) == 1


def test_static_own_forces_are_legal_even_with_no_np_attacking_force():
    state = board(faction=rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 1)
    recorder(state, [{'region': rc.NERVII, 'defender': rc.GERMANS}, {'decline': True}])
    result = _resolve_free_actions(state, rc.ROMANS)
    assert result[0]['result']['executed']
    assert validate_state(state) == []


def test_no_second_request_when_first_removes_all_own_forces():
    state = board(faction=rc.AEDUI)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4)
    requests = recorder(state, [{'region': rc.NERVII, 'defender': rc.GERMANS}])
    result = _resolve_free_actions(state, rc.AEDUI)
    assert len(result) == 1 and count_pieces(state, rc.NERVII, rc.AEDUI) == 0
    assert len([r for _, r in requests if r.get('request_type') == 'decisive_battle']) == 1


def request_for(state, faction=rc.BELGAE, *, second=False, region=rc.NERVII):
    from fs_bot.cards.decisive_battle import legal_defenders
    return {'kind': 'free_action', 'request_type': 'decisive_battle',
            'card_id': state['current_card'], 'faction': faction,
            'phase': 'second' if second else 'first', 'allowed_regions': [region],
            'defenders_by_region': legal_defenders(state, faction, [region]),
            'allow_decline': second, 'no_retreat': not second,
            'free': True, 'with_sa': False, 'default_available': False,
            'validate_default_response': True}


@pytest.mark.parametrize('response', [
    None, {}, [], {'region': []}, {'region': rc.NERVII, 'defender': []},
    {'region': rc.NERVII, 'defender': rc.BELGAE},
    {'region': rc.CARNUTES, 'defender': rc.GERMANS},
    {'region': rc.NERVII, 'defender': rc.AEDUI},
    {'region': rc.NERVII, 'defender': rc.GERMANS, 'no_retreat': False},
    {'region': rc.NERVII, 'defender': rc.GERMANS, 'force_retreat': True},
    {'region': rc.NERVII, 'defender': rc.GERMANS, 'allied_factions': [rc.AEDUI]},
    {'region': rc.NERVII, 'defender': rc.GERMANS, 'warband_full_loss': True},
    {'region': rc.NERVII, 'defender': rc.GERMANS, 'sa': rc.SA_AMBUSH},
    {'decline': True}, {'decline': 1}, {'use_default': 1}, {'use_default': True},
    {'use_default': True, 'region': rc.NERVII},
])
def test_invalid_response_never_mutates_board_rng_or_consults_live_human(response):
    from fs_bot.engine.free_actions import validate_free_action_response
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('Validation asked a live human')
    assert validate_free_action_response(state, rc.BELGAE, request_for(state), response)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_second_validation_requires_current_enemy_in_same_region():
    from fs_bot.engine.free_actions import validate_free_action_response
    from fs_bot.board.pieces import remove_piece
    state = board()
    for region in (rc.NERVII, rc.MORINI):
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    request = request_for(state, second=True)
    assert validate_free_action_response(state, rc.BELGAE, request,
        {'region': rc.MORINI, 'defender': rc.GERMANS})
    remove_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.HIDDEN)
    assert validate_free_action_response(state, rc.BELGAE, request,
        {'region': rc.NERVII, 'defender': rc.GERMANS})
    assert validate_free_action_response(state, rc.BELGAE, request, {'decline': True}) is None
    assert validate_free_action_response(state, rc.BELGAE, request, {'use_default': True}) is None


@pytest.mark.parametrize('card,region', [('A21', rc.NERVII), ('A57', rc.SEQUANI)])
def test_out_of_theatre_and_empty_events_need_no_input_or_rng(card, region):
    state = board(card)
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    rng = state['rng'].getstate()
    state['decision_agent'] = lambda *_: pytest.fail('No legal Battle should ask no question')
    result = _resolve_free_actions(state, rc.BELGAE)
    assert not result[0]['executed']
    assert state['rng'].getstate() == rng
    assert count_pieces(state, region, rc.GERMANS, rc.WARBAND) == 2
    assert not any(key.startswith('card_' + card) for key in state['event_modifiers'])


@pytest.mark.parametrize('faction,own,enemy', [
    (rc.BELGAE, 6, rc.GERMANS), (rc.GERMANS, 3, rc.BELGAE)])
def test_np_restrictions_still_apply_without_human_request(faction, own, enemy):
    state = board(faction=faction)
    state['non_player_factions'].add(faction)
    place_piece(state, rc.NERVII, faction, rc.WARBAND, own)
    place_piece(state, rc.NERVII, enemy, rc.WARBAND, 2)
    if faction == rc.GERMANS:
        place_piece(state, rc.NERVII, faction, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    requests = recorder(state, [])
    assert not _resolve_free_actions(state, faction)[0]['executed']
    assert not requests


@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_available_explicit_default_and_raw_defer_keep_np_planner(response):
    state = board(faction=rc.AEDUI)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    recorder(state, [response])
    result = _resolve_free_actions(state, rc.AEDUI)
    assert result[0]['result']['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0


def test_raw_none_can_retain_historical_no_target_fallback():
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    recorder(state, [None])
    assert not _resolve_free_actions(state, rc.BELGAE)[0]['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 2


def test_terminal_choices_board_inspection_and_eof_are_pure():
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.cli.menus import set_board_hook
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    request = request_for(state)
    before = encode(state)
    output = io.StringIO()
    inspected = []
    set_board_hook(lambda: inspected.append(True))
    try:
        agent = make_cli_reactive([rc.BELGAE], io.StringIO(
            'b\nDecline\n1\n' + rc.NERVII + '\n' + rc.GERMANS + '\n'), output)
        assert agent(state, rc.BELGAE, request) == {'region': rc.NERVII, 'defender': rc.GERMANS}
    finally:
        set_board_hook(None)
    assert inspected == [True] and 'No Retreat' in output.getvalue()
    assert 'Use bot default' not in output.getvalue()
    assert 'Decline second Battle' not in output.getvalue()
    agent = make_cli_reactive([rc.BELGAE], io.StringIO(''), io.StringIO())
    with pytest.raises(EOFError):
        agent(state, rc.BELGAE, request)
    request = request_for(state, second=True)
    agent = make_cli_reactive([rc.BELGAE], io.StringIO('Decline second Battle\n'), output)
    assert agent(state, rc.BELGAE, request) == {'decline': True}
    assert 'Retreat allowed' in output.getvalue()
    assert encode(state) == before


def make_session(state, faction=rc.BELGAE, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    output = io.StringIO()
    view = HumanTurnDisplay(output)
    view.remember(state, [faction])
    seat = SeatSession(state, meta if meta is not None else {'seat': faction},
                       log if log is not None else [], view)
    state['decision_agent'] = seat.reactive
    return seat, output


def resolve_session(seat):
    from fs_bot.engine.game_engine import _action_transaction
    def callback(*args):
        pass
    callback.transaction_checkpoint = seat.checkpoint
    callback.transaction_restore = seat.restore
    with _action_transaction(seat.state, callback):
        return _resolve_free_actions(seat.state, seat.seat)


def to_next_grant(seat):
    """Answer only unrelated optional/removal/loss windows, never a grant."""
    from fs_bot.state.serialize import decode
    from fs_bot.tools.seat_session import DecisionPending
    for _ in range(30):
        try:
            return resolve_session(seat)
        except DecisionPending:
            pending = seat.data['pending']
            request = decode(pending['request'])
            if request.get('request_type') == 'decisive_battle':
                return request
            if request['kind'] == 'voluntary_removal':
                response = {'done': True}
            elif request['kind'] == 'loss_order':
                response = request['pieces']
            elif request['kind'] == 'retreat':
                response = {'retreat': False, 'region': None}
            elif request['kind'] == 'agreement':
                response = False
            else:
                pytest.fail(f'Unexpected request: {request}')
            seat.import_inbox({'decision_id': pending['id'], 'response': response})
    pytest.fail('Grant did not settle')


@pytest.mark.parametrize('response', [None, {'decline': True}, {'use_default': True},
    {'region': rc.CARNUTES, 'defender': rc.GERMANS},
    {'region': [], 'defender': rc.GERMANS}])
def test_durable_missing_invalid_and_unavailable_default_keep_same_pending_id(response):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    before = encode(state)
    seat, _ = make_session(state)
    assert to_next_grant(seat)['phase'] == 'first'
    pending = deepcopy(seat.data['pending'])
    if response is not None:
        seat.import_inbox({'decision_id': pending['id'], 'response': response})
    with pytest.raises(DecisionPending):
        resolve_session(seat)
    assert seat.data['pending'] == pending
    assert encode(board_copy(state)) == before
    assert not seat.log
    if response is not None:
        assert seat.error and seat.data['queue'][0]['response'] == response
    if response == {'use_default': True}:
        assert 'No bot default' in seat.error


@pytest.mark.parametrize('card,region', [('A21', rc.SEQUANI), ('A57', rc.NERVII)])
@pytest.mark.parametrize('finish_second', ['decline', 'different_defender'])
def test_durable_second_choice_save_load_and_verified_replay(card, region, finish_second, tmp_path):
    from fs_bot.state.serialize import decode, save_game, load_game
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = board(card)
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, region, rc.ROMANS, rc.FORT)
    before = encode(state)
    seat, output = make_session(state)
    first = to_next_grant(seat)
    assert first['phase'] == 'first' and not first['default_available']
    first_id = seat.data['pending']['id']
    seat.import_inbox({'decision_id': first_id,
                       'response': {'region': region, 'defender': rc.GERMANS}})
    second = to_next_grant(seat)
    assert second['phase'] == 'second' and not second['default_available']
    pending = deepcopy(seat.data['pending'])
    assert pending['id'] != first_id
    live = decode(pending['board'])
    assert count_pieces(live, region, rc.GERMANS) == 0
    assert second['defenders_by_region'] == {region: [rc.ROMANS]}
    assert encode(board_copy(state)) == before  # entire unfinished Event rolled back
    assert 'Current card:' in output.getvalue() and 'Upcoming card:' in output.getvalue()
    assert 'changes since your last decision' in output.getvalue()
    seat.import_inbox({'decision_id': pending['id'],
                       'response': {'region': region, 'defender': rc.GERMANS}})
    with pytest.raises(DecisionPending):
        resolve_session(seat)
    assert seat.data['pending'] == pending
    assert encode(board_copy(state)) == before
    assert any(e['assistant_id'] == first_id for e in seat.data['journal'])
    save = tmp_path / 'decisive_battle.json'
    save_game(state, save, meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(save)
    resumed, _ = make_session(restored, meta=meta, log=log)
    response = ({'decline': True} if finish_second == 'decline'
                else {'region': region, 'defender': rc.ROMANS})
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = to_next_grant(resumed)
    assert isinstance(result, list) and len(result) == (1 if finish_second == 'decline' else 2)
    resumed.finish()
    assert resumed.data['pending'] is None and not resumed.data['journal']
    assert not resumed.data['queue'] and validate_state(restored) == []
    committed = encode(board_copy(restored))
    replay, _ = make_session(decode(before))
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']}
                               for e in resumed.log]
    replay.import_inbox([{'decision_id': e['assistant_id'], 'response': decode(e['assistant_response'])}
                        for e in resumed.log])
    assert resolve_session(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == committed
    assert replay.log == resumed.log


def test_durable_explicit_default_is_validated_and_preserved_before_delegating():
    from fs_bot.state.serialize import decode
    state = board(faction=rc.AEDUI)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    seat, _ = make_session(state, rc.AEDUI)
    request = to_next_grant(seat)
    assert request['default_available']
    decision_id = seat.data['pending']['id']
    seat.import_inbox({'decision_id': decision_id, 'response': {'use_default': True}})
    result = to_next_grant(seat)
    assert isinstance(result, list) and result[0]['result']['executed']
    seat.finish()
    entry = next(e for e in seat.log if e['assistant_id'] == decision_id)
    assert decode(entry['assistant_response']) == {'use_default': True}


def test_new_session_default_gate_is_opt_in_for_existing_free_action_protocol():
    from fs_bot.tools.seat_session import validate_response
    state = board()
    request = {'kind': 'free_action', 'faction': rc.BELGAE, 'request_type': 'legacy_unknown'}
    assert validate_response(state, request, {'use_default': True}) is None


@pytest.mark.parametrize('delegate', [False, True])
def test_refused_optional_diviciacus_loan_reopens_required_first_battle(delegate):
    state = board(faction=rc.ROMANS)
    state['non_player_factions'].discard(rc.AEDUI)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    requests = []
    rng = state['rng'].getstate()
    def choose(current, faction, request):
        if request.get('request_type') == 'decisive_battle':
            requests.append(deepcopy(request))
            if request['phase'] == 'second':
                return {'decline': True}
            if len(requests) == 2:
                assert request['attempt'] == 2 and 'refused' in request['previous_error']
                assert count_pieces(current, rc.NERVII, rc.GERMANS, rc.WARBAND) == 2
                assert current['rng'].getstate() == rng
            if delegate and len(requests) == 1:
                return {'use_default': True}
            return {'region': rc.NERVII, 'defender': rc.GERMANS}
        if request.get('request_type') == 'diviciacus_command':
            return len(requests) == 1
        if request.get('request_type') == 'diviciacus':
            return False
        return None
    state['decision_agent'] = choose
    result = _resolve_free_actions(state, rc.ROMANS)
    assert [r['phase'] for r in requests] == ['first', 'first', 'second']
    assert result[0]['result']['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_diviciacus_requires_auxilia_and_warbands_together_before_roman_option():
    """A1.4 'Warbands and Auxilia together'; the Leader alone cannot lend."""
    from fs_bot.cards.decisive_battle import legal_defenders
    from fs_bot.engine.diviciacus import eligible_regions
    state = board('A21', rc.ROMANS)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 2)
    assert eligible_regions(state, rc.ROMANS) == []
    assert legal_defenders(state, rc.ROMANS, [rc.SEQUANI]) == {}
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1)
    assert eligible_regions(state, rc.ROMANS) == [rc.SEQUANI]
    assert legal_defenders(state, rc.ROMANS, [rc.SEQUANI]) == {
        rc.SEQUANI: [rc.AEDUI, rc.GERMANS]}


@pytest.mark.parametrize('card,region', [('A21', rc.SEQUANI), ('A57', rc.NERVII)])
@pytest.mark.parametrize('text', [rc.EVENT_UNSHADED, rc.EVENT_SHADED])
def test_full_event_dispatch_uses_same_single_text_human_contract(card, region, text):
    from fs_bot.engine.execute import execute_decision, _CMD_EVENT
    state = board(card)
    state['event_modifiers'].clear()
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    recorder(state, [{'region': region, 'defender': rc.GERMANS}])
    result = execute_decision(state, rc.BELGAE, {'player_action': {
        'command': _CMD_EVENT, 'details': {'card_id': card, 'text_preference': text}}})
    assert result['executed'] and result['free_actions'][0]['result']['executed']
    assert count_pieces(state, region, rc.GERMANS) == 0
    assert not any(key.startswith('card_' + card) for key in state['event_modifiers'])
    assert validate_state(state) == []


def test_second_battle_retains_a70_normal_no_retreat_capability():
    from fs_bot.cards.card_effects import execute_card_A70
    state = board(faction=rc.ROMANS)
    execute_card_A70(state, shaded=False)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    requests = recorder(state, [{'region': rc.NERVII, 'defender': rc.BELGAE}] * 2)
    result = _resolve_free_actions(state, rc.ROMANS)
    assert len(result) == 2 and result[1]['result']['executed']
    assert not any(r['kind'] == 'retreat' for _, r in requests)


def test_refused_loan_retry_is_pending_saveable_and_deterministically_replayed(tmp_path):
    from fs_bot.state.serialize import decode, save_game, load_game
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = board(faction=rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 1)
    before = encode(state)
    seat, _ = make_session(state, rc.ROMANS)
    assert to_next_grant(seat)['attempt'] == 1
    seat.import_inbox({'decision_id': seat.data['pending']['id'],
                       'response': {'region': rc.NERVII, 'defender': rc.AEDUI}})
    with pytest.raises(DecisionPending):
        resolve_session(seat)
    request = decode(seat.data['pending']['request'])
    assert request['request_type'] == 'diviciacus_command'
    seat.import_inbox({'decision_id': seat.data['pending']['id'], 'response': True})
    retry = to_next_grant(seat)  # NP Aedui may not lend against themselves (§8.6.8).
    assert retry['phase'] == 'first' and retry['attempt'] == 2
    assert 'refused' in retry['previous_error']
    assert encode(board_copy(state)) == before
    pending_id = seat.data['pending']['id']
    save = tmp_path / 'decisive_loan_retry.json'
    save_game(state, save, meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(save)
    resumed, _ = make_session(restored, rc.ROMANS, meta, log)
    resumed.import_inbox({'decision_id': pending_id,
                          'response': {'region': rc.NERVII, 'defender': rc.GERMANS}})
    assert to_next_grant(resumed)['phase'] == 'second'  # helper declines the second loan opt-in.
    resumed.import_inbox({'decision_id': resumed.data['pending']['id'],
                          'response': {'decline': True}})
    result = to_next_grant(resumed)
    resumed.finish()
    assert len(result) == 1 and result[0]['result']['executed']
    assert count_pieces(restored, rc.NERVII, rc.GERMANS) == 0
    assert count_pieces(restored, rc.NERVII, rc.AEDUI, rc.WARBAND) == 2
    committed = encode(board_copy(restored))
    replay, _ = make_session(decode(before), rc.ROMANS)
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']}
                               for e in resumed.log]
    replay.import_inbox([{'decision_id': e['assistant_id'], 'response': decode(e['assistant_response'])}
                        for e in resumed.log])
    assert resolve_session(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == committed
    assert replay.log == resumed.log


def test_raw_callback_loan_refusal_retains_legacy_single_attempt():
    state = board(faction=rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    requests = []
    def choose(current, faction, request):
        requests.append(request)
        if request.get('request_type') == 'diviciacus_command':
            return True
        return None
    state['decision_agent'] = choose
    result = _resolve_free_actions(state, rc.ROMANS)
    assert not result[0]['result']['executed']
    assert len([r for r in requests if r.get('request_type') == 'decisive_battle']) == 1


def test_refused_second_loan_replans_only_second_and_still_allows_decline():
    state = board(faction=rc.ROMANS)
    state['non_player_factions'].discard(rc.AEDUI)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    grants = []
    def choose(current, faction, request):
        if request.get('request_type') == 'decisive_battle':
            grants.append(deepcopy(request))
            if len(grants) == 3:
                assert request['phase'] == 'second' and request['attempt'] == 2
                assert count_pieces(current, rc.NERVII, rc.GERMANS, rc.WARBAND) == 1
                return {'decline': True}
            return {'region': rc.NERVII, 'defender': rc.GERMANS}
        if request.get('request_type') == 'diviciacus_command':
            return len(grants) == 2
        if request.get('request_type') == 'diviciacus':
            return False
        return None
    state['decision_agent'] = choose
    result = _resolve_free_actions(state, rc.ROMANS)
    assert [r['phase'] for r in grants] == ['first', 'second', 'second']
    assert len(result) == 1 and result[0]['result']['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 1
    assert validate_state(state) == []
