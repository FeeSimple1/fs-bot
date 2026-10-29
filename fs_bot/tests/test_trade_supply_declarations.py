"""§§4.4.1/8.6.3/8.8.6: Trade uses Aedui routes and actual declarations."""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.sa_trade import trade, forecast_trade
from fs_bot.engine.execute import _execute_sa, _execute_trade
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy
from fs_bot.cli.display import HumanTurnDisplay


def position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=17)
    state['non_player_factions'] = {rc.AEDUI}
    state['resources'][rc.AEDUI] = 0
    state['is_second_eligible'] = False
    for tribe in (rc.TRIBE_BITURIGES, rc.TRIBE_TREVERI):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    assert check_structural_integrity(state) == []
    return state


def clean(state):
    assert '_supply_line_query' not in state
    assert '_supply_line_agreements' not in state
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('accepted', [False, True])
def test_roman_declaration_controls_both_trade_rate_and_roman_routes(scenario, accepted):
    state = position(scenario)
    endpoints = ((rc.UBII, rc.SEQUANI, rc.PROVINCIA)
                 if scenario in rc.BASE_SCENARIOS else (rc.PROVINCIA, rc.CISALPINA))
    for region in endpoints:
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    calls = []
    def agent(board, faction, request):
        assert board is state and faction == rc.ROMANS
        assert request['request_type'] == 'trade_roman_agreement'
        assert request['requesting_faction'] == rc.AEDUI
        calls.append(request)
        return accepted if len(calls) == 1 else not accepted
    state['decision_agent'] = agent
    result = _execute_trade(state, rc.AEDUI)
    assert result['result']['resources_gained'] == (4 if accepted else 0)
    assert len(calls) == 1  # No contradictory second Roman Supply declaration.
    clean(state)


@pytest.mark.parametrize('np_aedui,expected', [(False, 2), (True, 4)])
def test_nonplayer_rome_uses_actual_aedui_seat_even_without_roman_control(np_aedui, expected):
    state = position()
    state['non_player_factions'] = {rc.ROMANS} | ({rc.AEDUI} if np_aedui else set())
    state['decision_agent'] = lambda *_: pytest.fail('NP Rome must use §8.8.6')
    result = _execute_trade(state, rc.AEDUI)
    assert result['result']['resources_gained'] == expected
    assert state['non_player_factions'] == ({rc.ROMANS, rc.AEDUI} if np_aedui else {rc.ROMANS})
    clean(state)


def test_roman_consent_cannot_override_other_nonplayer_supply_refusal():
    state = position()
    state['non_player_factions'].add(rc.BELGAE)
    for region in (rc.UBII, rc.SEQUANI, rc.PROVINCIA):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    calls = []
    state['decision_agent'] = lambda board, faction, request: calls.append(faction) or True
    result = _execute_trade(state, rc.AEDUI)
    assert result['result']['resources_gained'] == 0
    assert calls == [rc.ROMANS]
    clean(state)


@pytest.mark.parametrize('accepted,second,expected', [
    (False, False, 0), (True, False, 4), (False, True, 2)])
def test_actual_np_trade_threshold_uses_declarations_before_selecting_sa(accepted, second, expected):
    state = position()
    state['is_second_eligible'] = second
    calls = []
    state['decision_agent'] = lambda board, faction, request: calls.append(request) or accepted
    result = _execute_sa(state, rc.AEDUI, {'command': rc.CMD_RALLY, 'sa': rc.SA_TRADE})
    assert state['resources'][rc.AEDUI] == expected
    assert result['executed'] is bool(expected)
    assert len(calls) == 1
    if not expected:
        assert result['declined_no_effect']  # No affordable Suborn at zero Resources.
    clean(state)


def test_trade_preview_does_not_copy_live_agent_consume_input_or_rng():
    state = position()
    before = encode(state)
    class LiveAgent:
        def __call__(self, *_):
            pytest.fail('preview consumed live input')
        def __deepcopy__(self, _):
            pytest.fail('preview copied a live agent')
    agent = LiveAgent()
    state['decision_agent'] = agent
    assert forecast_trade(state) == 4
    assert state['decision_agent'] is agent
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('marker', [rc.DISPERSED, rc.DISPERSED_GATHERING, rc.MARKER_RAZED])
def test_trade_does_not_count_marked_tribes_as_subdued(marker):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=17)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    state['tribes'][rc.TRIBE_SENONES]['status'] = marker
    state['tribes'][rc.TRIBE_LINGONES]['status'] = marker
    result = trade(state, roman_agreed=False, allowed_regions={rc.MANDUBII})
    assert result['resources_gained'] == 1
    assert result['per_item'] == [('subdued_tribe', rc.TRIBE_MANDUBII, 1)]


def session(state=None, meta=None, log=None):
    state = position() if state is None else state
    saved = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 17} if meta is None else meta
    result = SeatSession(state, saved, [] if log is None else log, HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = result.reactive
    return result


def run_session(seat):
    def driver(*_):
        pass
    driver.transaction_checkpoint = seat.checkpoint
    driver.transaction_restore = seat.restore
    with _action_transaction(seat.state, driver):
        result = _execute_sa(seat.state, rc.AEDUI, {'command': rc.CMD_RALLY, 'sa': rc.SA_TRADE})
    seat.finish()
    return result


@pytest.mark.parametrize('accepted', [False, True])
def test_trade_declaration_save_resume_and_replay_before_any_yield(tmp_path, accepted):
    seat = session()
    initial = encode(board_copy(seat.state))
    with pytest.raises(DecisionPending):
        run_session(seat)
    pending = copy.deepcopy(seat.data['pending'])
    assert encode(board_copy(seat.state)) == initial
    assert decode(pending['request'])['request_type'] == 'trade_roman_agreement'
    seat.import_inbox({'decision_id': pending['id'], 'response': 1})
    with pytest.raises(DecisionPending):
        run_session(seat)
    assert seat.data['pending'] == pending and seat.data['journal'] == []
    seat.data['queue'] = []
    save_game(seat.state, tmp_path / 'trade.json', meta=seat.meta, log=seat.log)
    state, meta, log = load_game(tmp_path / 'trade.json')
    resumed = session(state, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': accepted})
    result = run_session(resumed)
    assert result['executed'] is accepted
    assert len(resumed.log) == 1 and not resumed.data['queue']
    clean(state)
    replay = session(decode(initial))
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']}
                               for e in resumed.log]
    replay.import_inbox([replay._inbox_entry(e) for e in resumed.log])
    assert run_session(replay) == result
    assert replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(state))


def test_first_trade_agreement_survives_second_owner_pending(tmp_path):
    state = position()
    for region in (rc.UBII, rc.SEQUANI):
        place_piece(state, region, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND)
    seat = session(state)
    # Route both human owners into the same durable journal for this
    # engine-level test; SeatSession.reactive normally controls one seat.
    state['decision_agent'] = lambda board, faction, request: seat.ask(board, faction, request)
    initial = encode(board_copy(state))
    seat.import_inbox([{'response': True}])
    with pytest.raises(DecisionPending):
        run_session(seat)
    pending = copy.deepcopy(seat.data['pending'])
    assert decode(pending['request'])['faction'] == rc.BELGAE
    assert pending['id'] == 'd000002' and len(seat.data['journal']) == 1
    assert encode(board_copy(state)) == initial
    save_game(state, tmp_path / 'second-owner.json', meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(tmp_path / 'second-owner.json')
    resumed = session(restored, meta, log)
    restored['decision_agent'] = lambda board, faction, request: resumed.ask(board, faction, request)
    resumed.import_inbox({'decision_id': pending['id'], 'response': True})
    assert run_session(resumed)['executed']
    assert restored['resources'][rc.AEDUI] == 4
    assert len(resumed.log) == 2 and not resumed.data['journal']
    clean(restored)
