"""Card 39 shaded: human Trade choices follow declarations and the actual board."""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_sa_details
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_trade import forecast_trade, trade, validate_trade_plan
from fs_bot.engine.execute import _execute_trade, execute_decision
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND, _action_transaction
from fs_bot.engine.moves import preview_player_action, validate_player_action
from fs_bot.map.map_data import get_playable_regions, is_adjacent
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response


def position(scenario=rc.SCENARIO_GREAT_REVOLT, edition='legacy', **kwargs):
    state = build_initial_state(scenario, seed=17, **kwargs)
    state['card_edition'] = edition
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = 0
    state['current_card'] = state['current_card_id'] = 16
    state['next_card'] = 17
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_TREVERI):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    activate_capability(state, 39, rc.EVENT_SHADED)
    return state


def answer_region(state, region=rc.TREVERI, agreed=True):
    calls = []
    def agent(board, faction, request):
        calls.append((faction, copy.deepcopy(request)))
        return agreed if request['kind'] == 'agreement' else {'region': region}
    state['decision_agent'] = agent
    return calls


def plan(timing='after', region=None):
    details = {'rally_plan': {'steps': [
        {'region': rc.AEDUI_REGION, 'action': 'place_warbands', 'count': 1}]}}
    if region is not None:
        details['trade_region'] = region
    return {'command': 'Rally', 'sa': 'Trade', 'sa_timing': timing, 'details': details}


def clean(state):
    assert '_supply_line_query' not in state
    assert '_supply_line_agreements' not in state
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('edition', CARD_EDITIONS)
def test_human_can_choose_lower_yield_region_in_every_scenario_and_edition(scenario, edition):
    state = position(scenario, edition)
    calls = answer_region(state)
    result = _execute_trade(state, rc.AEDUI)
    request = calls[-1][1]
    gains = {choice['region']: choice['resources_gained'] for choice in request['choices']}
    assert calls[0][0] == rc.ROMANS and calls[0][1]['request_type'] == 'trade_roman_agreement'
    assert calls[-1][0] == rc.AEDUI and request['kind'] == 'trade_region'
    assert gains[rc.MANDUBII] == 6 > gains[rc.TREVERI] == 2
    assert gains[rc.MORINI] == 0  # Legal optional choices are not filtered by value.
    assert request['legal_regions'] == list(get_playable_regions(scenario, state['capabilities']))
    assert result['result'] == {'resources_gained': 2,
        'per_item': [('aedui_ally', rc.TREVERI, 2)], 'trade_region': rc.TREVERI}
    assert state['resources'][rc.AEDUI] == 2
    clean(state)


@pytest.mark.parametrize('agreed,expected', [(False, 1), (True, 2)])
def test_explicit_region_uses_actual_roman_declaration_without_extra_choice(agreed, expected):
    state = position()
    calls = answer_region(state, agreed=agreed)
    result = _execute_trade(state, rc.AEDUI, action=plan(region=rc.TREVERI))
    assert result['result']['resources_gained'] == expected
    assert [request['kind'] for _, request in calls] == ['agreement']
    clean(state)


def test_roman_refusal_excludes_blocked_region_before_choice():
    state = position()
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 3)
    calls = answer_region(state, rc.MANDUBII, agreed=False)
    result = _execute_trade(state, rc.AEDUI)
    assert rc.TREVERI not in calls[-1][1]['legal_regions']
    assert result['result']['resources_gained'] == 3
    assert sum(r.get('request_type') == 'trade_roman_agreement' for _, r in calls) == 1


def test_choice_reports_actual_resource_cap_and_zero_yield_is_no_effect():
    state = position()
    state['resources'][rc.AEDUI] = rc.MAX_RESOURCES - 1
    calls = answer_region(state, rc.MORINI)
    result = _execute_trade(state, rc.AEDUI)
    gains = {entry['region']: entry['resources_gained'] for entry in calls[-1][1]['choices']}
    assert gains[rc.MANDUBII] == gains[rc.TREVERI] == 1
    assert gains[rc.MORINI] == 0
    assert result['declined_no_effect'] and not result['executed']
    assert state['resources'][rc.AEDUI] == rc.MAX_RESOURCES - 1


def test_bot_retains_legacy_first_supply_region_pending_priority_review():
    # Compatibility only: §8.3.3/8.6.3 first-Region vs income priority is
    # recorded separately for review; this human-interface repair does not
    # change that bot policy, even when its first Region yields nothing.
    state = position()
    state['non_player_factions'] = {rc.AEDUI}
    calls = answer_region(state)
    result = _execute_trade(state, rc.AEDUI)
    assert [request['kind'] for _, request in calls] == ['agreement']
    assert result['result']['trade_region'] == get_playable_regions(state['scenario'])[0]


@pytest.mark.parametrize('selection', [True, 1, [], {}, None, 'not a Region'])
def test_bad_explicit_region_cannot_award_resources(selection):
    state = position()
    before = encode(state)
    with pytest.raises(CommandError):
        trade(state, roman_agreed=True, trade_region=selection)
    assert encode(state) == before


@pytest.mark.parametrize('selection', [True, 1, [], {}, None])
def test_bad_authored_region_types_reject_entire_command(selection):
    state = position()
    state['resources'][rc.AEDUI] = 10
    action = plan()
    action['details']['trade_region'] = selection
    before = encode(state)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': action})
    assert not result['executed'] and 'must name one Region' in result['reason']
    assert encode(state) == before


def test_trade_region_schema_rejects_wrong_sa_and_conflicting_nested_choices():
    action = plan(region=rc.TREVERI)
    action['sa'] = 'No SA'
    assert 'requires a Trade' in validate_trade_plan(action)
    action['sa'] = 'Trade'
    action['details']['sa_details'] = {'trade_region': rc.MANDUBII}
    assert 'Conflicting' in validate_trade_plan(action)
    action['details'].pop('trade_region')
    assert validate_trade_plan(action) is None
    state = position()
    assert _execute_trade(state, rc.AEDUI, action=action)['result']['trade_region'] == rc.MANDUBII


def test_explicit_trade_region_requires_shaded_river_commerce():
    state = position()
    activate_capability(state, 39, rc.EVENT_UNSHADED)
    before = encode(state)
    result = _execute_trade(state, rc.AEDUI, action=plan(region=rc.TREVERI))
    assert not result['executed'] and 'shaded River Commerce' in result['error']
    assert encode(state) == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GREAT_REVOLT])
def test_diviciacus_restricts_offered_trade_regions_in_expansion_and_original_option(scenario):
    state = position(scenario, **({'diviciacus_option': True} if scenario in rc.BASE_SCENARIOS else {}))
    if scenario in rc.BASE_SCENARIOS:
        state['event_params'] = {'region': rc.MANDUBII}
        execute_event(state, rc.CARD_O38)
    else:
        place_piece(state, rc.MANDUBII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    calls = answer_region(state, rc.MANDUBII)
    _execute_trade(state, rc.AEDUI)
    regions = calls[-1][1]['legal_regions']
    assert rc.MANDUBII in regions and rc.MORINI not in regions
    assert all(r == rc.MANDUBII or is_adjacent(r, rc.MANDUBII) for r in regions)
    clean(state)


def test_a38_without_diviciacus_and_event_scope_both_limit_choices():
    state = position(rc.SCENARIO_ARIOVISTUS)
    activate_capability(state, 'A38', rc.EVENT_SHADED)
    calls = answer_region(state, rc.MANDUBII)
    grant = {'kind': 'free_action', 'request_type': 'event_sa', 'allowed_sas': ['Trade'],
             'allowed_regions': [rc.MANDUBII, rc.MORINI]}
    action = {'sa': 'Trade', 'details': {}}
    before = encode(board_copy(state))
    assert validate_free_action_response(state, rc.AEDUI, grant, action) is None
    assert calls == [] and encode(board_copy(state)) == before
    result = execute_free_action_plan(state, rc.AEDUI, grant, action)
    assert result['executed'] and calls[-1][1]['legal_regions'] == [rc.MANDUBII]
    escaped = {'sa': 'Trade', 'details': {'trade_region': rc.TREVERI}}
    assert validate_free_action_response(state, rc.AEDUI, grant, escaped)
    assert not execute_free_action_plan(state, rc.AEDUI, grant, escaped)['executed']
    clean(state)


@pytest.mark.parametrize('timing,expected', [('before', 0), ('after', 2)])
def test_region_choice_uses_actual_command_order_and_preserves_command_when_trade_has_no_effect(timing, expected):
    state = position()
    state['resources'][rc.AEDUI] = 10
    calls = answer_region(state, rc.AEDUI_REGION)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': plan(timing)})
    assert result['executed'] and count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    choice = next(c for c in calls[-1][1]['choices'] if c['region'] == rc.AEDUI_REGION)
    assert choice['resources_gained'] == expected
    assert result['sa_execution']['result']['resources_gained'] == expected
    assert state['resources'][rc.AEDUI] == 10 - 1 + expected
    assert result['sa_execution']['executed'] is bool(expected)
    clean(state)


@pytest.mark.parametrize('timing', ['before', 'after'])
def test_declining_trade_does_not_cancel_successful_command(timing):
    state = position()
    state['resources'][rc.AEDUI] = 10
    state['decision_agent'] = lambda board, faction, request: (
        True if request['kind'] == 'agreement' else {'decline': True})
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': plan(timing)})
    assert result['executed'] and result['sa_execution']['declined_no_effect']
    assert state['resources'][rc.AEDUI] == 9
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1


def test_limited_command_still_cannot_trade():
    state = position()
    state['resources'][rc.AEDUI] = 10
    before = encode(state)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_LIMITED_COMMAND, 'player_action': plan()})
    assert not result['executed'] and 'Limited Command' in result['reason']
    assert encode(state) == before


def test_forecasts_and_command_previews_neither_ask_nor_change_rng_or_board():
    state = position()
    state['resources'][rc.AEDUI] = 10
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('a preview asked a live question')
    assert forecast_trade(state) == 6
    assert preview_player_action(state, rc.AEDUI, plan())[0]
    assert validate_player_action(state, rc.AEDUI, plan())[0]
    assert encode(board_copy(state)) == before
    calls = answer_region(state)
    assert forecast_trade(state, confirm=True) == 6
    assert [request['kind'] for _, request in calls] == ['agreement']
    assert encode(board_copy(state)) == before


def test_cli_trade_planning_defers_region_choice_until_resolution():
    state = position()
    stdout = io.StringIO()
    action = _collect_sa_details(state, rc.AEDUI, plan(), io.StringIO(''), stdout, 'Trade', state)
    assert action['sa'] == 'Trade' and action['sa_regions'] == []
    assert 'at resolution' in stdout.getvalue()


def test_cli_menu_offers_all_regions_and_board_shortcuts_and_rejects_bad_input():
    state = position()
    calls = answer_region(state)
    _execute_trade(state, rc.AEDUI)
    request = calls[-1][1]
    index = request['legal_regions'].index(rc.TREVERI) + 1
    stdout = io.StringIO()
    boards = []
    set_board_hook(lambda: boards.append(True))
    try:
        agent = make_cli_reactive({rc.AEDUI}, io.StringIO(f'b\nboard\nno-such-region\n{index}\n'), stdout)
        assert agent(state, rc.AEDUI, request) == {'region': rc.TREVERI}
    finally:
        set_board_hook(None)
    text = stdout.getvalue()
    assert len(boards) == 2 and 'Please enter' in text
    assert 'Treveri (+2 Resources)' in text and 'Mandubii (+6 Resources)' in text
    assert 'Morini (+0 Resources)' in text and 'Call off Trade' in text
    eof = make_cli_reactive({rc.AEDUI}, io.StringIO(''), io.StringIO())
    with pytest.raises(EOFError):
        eof(state, rc.AEDUI, request)


@pytest.mark.parametrize('response', [None, [], True, {'region': []}, {'region': rc.CISALPINA},
    {'region': rc.TREVERI, 'decline': True}, {'decline': 1}, {'use_default': 1}])
def test_durable_response_rejects_malformed_trade_choice(response):
    with pytest.raises(ValueError):
        validate_response(position(), {'kind': 'trade_region', 'legal_regions': [rc.TREVERI]}, response)


def session(state=None, meta=None, log=None):
    state = position() if state is None else state
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.AEDUI, rc.ROMANS])
    meta = {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 17} if meta is None else meta
    seat = SeatSession(state, meta, [] if log is None else log, display)
    state['decision_agent'] = lambda board, faction, request: seat.ask(board, faction, request)
    return seat


def run_session(seat):
    def driver(*_):
        pass
    driver.transaction_checkpoint, driver.transaction_restore = seat.checkpoint, seat.restore
    with _action_transaction(seat.state, driver):
        result = _execute_trade(seat.state, rc.AEDUI)
    seat.finish()
    return result


def test_trade_choice_save_resume_and_replay_retains_agreement_and_validates_pending(tmp_path):
    seat = session()
    initial = encode(board_copy(seat.state))
    seat.import_inbox([{'response': True}])
    with pytest.raises(DecisionPending):
        run_session(seat)
    pending = copy.deepcopy(seat.data['pending'])
    assert decode(pending['request'])['kind'] == 'trade_region'
    assert pending['id'] == 'd000002' and len(seat.data['journal']) == 1
    assert encode(board_copy(seat.state)) == initial
    seat.import_inbox({'decision_id': pending['id'], 'response': {'region': rc.CISALPINA}})
    with pytest.raises(DecisionPending):
        run_session(seat)
    assert seat.data['pending'] == pending and len(seat.data['journal']) == 1
    seat.data['queue'] = []
    save_game(seat.state, tmp_path / 'trade.json', meta=seat.meta, log=seat.log)
    state, meta, log = load_game(tmp_path / 'trade.json')
    resumed = session(state, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'region': rc.TREVERI}})
    result = run_session(resumed)
    assert result['result']['resources_gained'] == 2 and len(resumed.log) == 2
    assert not resumed.data['journal'] and not resumed.data['queue']
    replay = session(decode(initial))
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']} for e in resumed.log]
    replay.import_inbox([replay._inbox_entry(e) for e in resumed.log])
    assert run_session(replay) == result and replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(state))
    clean(state)


def test_trade_before_command_can_finance_it_and_during_uses_only_first_portion():
    state = position()
    answer_region(state)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA,
                                               'player_action': plan('before')})
    assert result['executed'] and state['resources'][rc.AEDUI] == 1
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1

    state = position()
    state['resources'][rc.AEDUI] = 10
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.AEDUI)
    action = plan('during')
    first = plan()
    first['sa'] = 'No SA'
    second = copy.deepcopy(first)
    second['details']['rally_plan']['steps'][0]['region'] = rc.SEQUANI
    action['details']['command_parts'] = [first, second]
    observed = []
    def agent(board, faction, request):
        if request['kind'] == 'agreement':
            return True
        observed.append((count_pieces(board, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND),
                         count_pieces(board, rc.SEQUANI, rc.AEDUI, rc.WARBAND)))
        return {'region': rc.AEDUI_REGION}
    state['decision_agent'] = agent
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and observed == [(1, 0)]
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == 10  # Two paid Rally Regions and +2 Trade.


def test_event_granted_command_and_trade_keep_reactive_choice_and_free_cost():
    state = position()
    calls = answer_region(state, rc.TREVERI)
    grant = {'kind': 'free_action', 'request_type': 'event_rally',
             'allowed_commands': ['Rally'], 'with_sa': True, 'max_regions': 1,
             'allowed_regions': [rc.AEDUI_REGION, rc.TREVERI]}
    before = encode(board_copy(state))
    assert validate_free_action_response(state, rc.AEDUI, grant, plan()) is None
    assert calls == [] and encode(board_copy(state)) == before
    result = execute_free_action_plan(state, rc.AEDUI, grant, plan())
    assert result['executed'] and result['sa_execution']['result']['trade_region'] == rc.TREVERI
    assert set(calls[-1][1]['legal_regions']) == {rc.AEDUI_REGION, rc.TREVERI}
    assert state['resources'][rc.AEDUI] == 2  # The granted Rally costs nothing.


def _decline_file_timing(args):
    """Submit actual no-removal replies without bypassing durable decisions."""
    import json
    from pathlib import Path
    from fs_bot.tools import llm_seat
    old_id = getattr(args, 'decision_id', None)
    had_id = hasattr(args, 'decision_id')
    try:
        seen = set()
        while True:
            _, meta, _ = load_game(Path(args.dir) / 'save.json')
            pending = meta['assistant_session']['pending']
            if not pending or decode(pending['request'])['kind'] != 'voluntary_removal':
                return
            identity = (pending['id'], repr(pending['request']))
            assert identity not in seen, 'A declined timing window did not advance.'
            seen.add(identity)
            args.decision_id = pending['id']
            args.response = json.dumps({'done': True})
            assert llm_seat.cmd_submit(args) == 0
    finally:
        if had_id:
            args.decision_id = old_id
        elif hasattr(args, 'decision_id'):
            del args.decision_id


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_file_session_shows_card_and_delta_before_region_choice_then_resumes_and_replays(tmp_path, capsys, scenario):
    import json
    from types import SimpleNamespace
    from fs_bot.tools import llm_seat

    state = position(scenario)
    state['resources'][rc.AEDUI] = 10
    state['non_player_factions'] = set(rc.FACTIONS) - {rc.AEDUI}
    state['played_cards'], state['deck'], state['next_card'] = [16], [], None
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.AEDUI else rc.INELIGIBLE
    path = tmp_path / 'live'
    path.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.AEDUI])
    meta = {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 17,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, path / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(path))
    assert llm_seat.cmd_play(args) == 0
    initial, _, _ = load_game(path / 'save.json')
    capsys.readouterr()
    args.response = json.dumps({'action': ACTION_COMMAND_SA, 'player_action': plan()})
    assert llm_seat.cmd_submit(args) == 0
    _decline_file_timing(args)
    paused, paused_meta, log = load_game(path / 'save.json')
    pending = paused_meta['assistant_session']['pending']
    request = decode(pending['request'])
    live_board = decode(pending['board'])
    assert request['kind'] == 'trade_region' and request['faction'] == rc.AEDUI
    assert count_pieces(live_board, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert live_board['resources'][rc.AEDUI] == 9
    assert encode(paused) == encode(initial)  # Pending action retains transactional start.
    accepted = copy.deepcopy(paused_meta['assistant_session']['journal'])
    assert len(accepted) > 1 and log == []
    assert all(entry.get('reactive') == 'voluntary_removal' for entry in accepted[1:])
    output = capsys.readouterr().out
    assert 'Current card:' in output and 'Ambacti' in output
    assert 'River Commerce' in output and 'changes since' in output
    assert 'Warband' in output and '10 -> 9' in output
    args.response = json.dumps({'region': 'not a Region'})
    assert llm_seat.cmd_submit(args) == 0
    rejected, rejected_meta, _ = load_game(path / 'save.json')
    assert encode(rejected) == encode(initial)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_meta['assistant_session']['journal'] == accepted
    args.response = json.dumps({'region': rc.TREVERI})
    assert llm_seat.cmd_submit(args) == 0
    _decline_file_timing(args)
    final, final_meta, final_log = load_game(path / 'save.json')
    assert count_pieces(final, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert final['resources'][rc.AEDUI] == 10  # NP Romans refuse: +1 on Treveri.
    trade_choices = [entry for entry in final_log if entry.get('reactive') == 'trade_region']
    assert len(trade_choices) == 1
    assert decode(trade_choices[0]['assistant_response']) == {'region': rc.TREVERI}
    assert final_log[:len(accepted)] == accepted
    assert not final_meta['assistant_session']['pending'] and not final_meta['assistant_session']['journal']
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replay' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out


def income_without_blue_allies():
    """Mandubii has three taxable Subdued Tribes; Treveri has one blue Ally."""
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=17)
    state['non_player_factions'] = set(rc.FACTIONS) - {rc.AEDUI}
    state['resources'][rc.AEDUI] = 0
    assert _ally_tribe(state, rc.TRIBE_TREVERI, rc.AEDUI)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    activate_capability(state, 39, rc.EVENT_SHADED)
    action = plan('before')
    action['details']['rally_plan']['steps'] = [
        {'region': rc.MANDUBII, 'action': 'place_ally', 'tribe': rc.TRIBE_MANDUBII},
        {'region': rc.TREVERI, 'action': 'place_warbands', 'count': 1},
        {'region': rc.AEDUI_REGION, 'action': 'place_warbands', 'count': 1}]
    return state, action


def test_pure_preview_counts_subdued_tribes_to_allow_every_affordable_following_command():
    state, action = income_without_blue_allies()
    state['decision_agent'] = lambda *_: pytest.fail('pure preview requested human input')
    before = encode(board_copy(state))
    assert forecast_trade(state) == 3
    ok, result, preview = preview_player_action(state, rc.AEDUI, action)
    assert ok and result['sa_execution']['result']['trade_region'] == rc.MANDUBII
    assert result['sa_execution']['result']['resources_gained'] == 3
    assert preview['resources'][rc.AEDUI] == 0
    assert count_pieces(preview, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert encode(board_copy(state)) == before
    answer_region(state, rc.TREVERI)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': action})
    assert not result['executed']
    assert result['sa_execution']['result']['trade_region'] == rc.TREVERI
    assert result['sa_execution']['result']['resources_gained'] == 1
    assert encode(board_copy(state)) == before  # Actual choice cannot secretly change to the forecast.


def test_lower_yield_choice_that_cannot_finance_command_returns_file_turn_to_pending(tmp_path, capsys):
    import json
    from types import SimpleNamespace
    from fs_bot.tools import llm_seat

    state, action = income_without_blue_allies()
    state['current_card'] = state['current_card_id'] = 16
    state['played_cards'], state['deck'], state['next_card'] = [16], [], None
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.AEDUI else rc.INELIGIBLE
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.AEDUI])
    meta = {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 17,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, tmp_path / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(tmp_path))
    assert llm_seat.cmd_play(args) == 0
    initial, initial_meta, _ = load_game(tmp_path / 'save.json')
    turn = initial_meta['assistant_session']['pending']
    args.response = json.dumps({'action': ACTION_COMMAND_SA, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_file_timing(args)
    _, trade_meta, _ = load_game(tmp_path / 'save.json')
    assert decode(trade_meta['assistant_session']['pending']['request'])['kind'] == 'trade_region'
    args.response = json.dumps({'region': rc.TREVERI})
    assert llm_seat.cmd_submit(args) == 0
    _decline_file_timing(args)
    rejected, rejected_meta, rejected_log = load_game(tmp_path / 'save.json')
    assert encode(rejected) == encode(initial)
    assert rejected_meta['assistant_session']['pending'] == turn
    assert not rejected_meta['assistant_session']['journal'] and rejected_log == []
    assert 'Decision rejected' in capsys.readouterr().out
    action['details']['trade_region'] = rc.MANDUBII
    args.response = json.dumps({'action': ACTION_COMMAND_SA, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_file_timing(args)
    final, final_meta, _ = load_game(tmp_path / 'save.json')
    assert count_pieces(final, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert final['resources'][rc.AEDUI] == 0 and not final_meta['assistant_session']['pending']
