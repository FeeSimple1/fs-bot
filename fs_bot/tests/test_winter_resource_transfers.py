"""§1.5.2/A1.5.2 Resource gifts during Quarters and Harvest."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.resource_transfers import KIND, request_for
from fs_bot.engine.winter import harvest_phase, quarters_phase, run_winter_round
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response


def position(scenario=rc.SCENARIO_PAX_GALLICA):
    state = build_initial_state(scenario, seed=41)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def use_agent(state, callback):
    callback.supports_resource_transfers = True
    state['decision_agent'] = callback


def gift(receiver, amount):
    return {'to': receiver, 'amount': amount}


def test_donor_limits_use_current_scenario_capability_and_recipient_room():
    state = position()
    state['resources'].update({rc.ROMANS: 40, rc.AEDUI: 30, rc.BELGAE: rc.MAX_RESOURCES})
    request = request_for(state, rc.AEDUI, 'quarters', 'before_relocations')
    assert request['recipients'] == {rc.ROMANS: 5, rc.ARVERNI: 30}
    activate_capability(state, 38, rc.EVENT_SHADED)
    assert request_for(state, rc.AEDUI, 'quarters', 'before_relocations')['recipients'] == {rc.ARVERNI: 30}

    expansion = position(rc.SCENARIO_ARIOVISTUS)
    expansion['resources'].update({rc.GERMANS: 20, rc.AEDUI: 20})
    request = request_for(expansion, rc.GERMANS, 'harvest', 'after_earnings')
    assert set(request['recipients']) == {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    assert rc.GERMANS in request_for(expansion, rc.AEDUI, 'harvest', 'after_earnings')['recipients']
    assert request_for(expansion, rc.ARVERNI, 'harvest', 'after_earnings') is None


def test_quarters_gifts_fund_exact_roman_payments_and_can_follow_them():
    state = position()
    state['resources'].update({rc.ROMANS: 0, rc.AEDUI: 30, rc.BELGAE: 44})
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    seen = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            stage = request['window']['stage']
            seen.append((faction, stage, board['resources'][rc.ROMANS]))
            if faction == rc.AEDUI and stage == 'before_relocations':
                return {'transfers': [gift(rc.ROMANS, 15), gift(rc.BELGAE, 1), gift(rc.ROMANS, 1)]}
            if faction == rc.ROMANS and stage == 'after_payments':
                return {'transfers': [gift(rc.AEDUI, 3)]}
        if request['kind'] == 'quarters_plan' and faction == rc.ROMANS:
            return {rc.ROMANS: [], rc.ROMANS + '_quartering': {
                rc.MORINI: {'pay_pieces': [(rc.AUXILIA, rc.HIDDEN, 2)]}}}
        return None

    use_agent(state, agent)
    result = quarters_phase(state)
    assert result['roman_quartering']['total_cost'] == 4
    assert not result['roman_quartering']['rolls']
    assert seen == [(rc.AEDUI, 'before_relocations', 0),
                    (rc.ROMANS, 'after_payments', 12), (rc.AEDUI, 'after_payments', 9)]
    assert [(row['from'], row['to'], row['given']) for row in result['transfers']] == [
        (rc.AEDUI, rc.ROMANS, 15), (rc.AEDUI, rc.BELGAE, 1),
        (rc.AEDUI, rc.ROMANS, 1), (rc.ROMANS, rc.AEDUI, 3),
    ]
    assert {f: state['resources'][f] for f in (rc.ROMANS, rc.AEDUI, rc.BELGAE)} == {
        rc.ROMANS: 9, rc.AEDUI: 16, rc.BELGAE: 45,
    }
    assert validate_state(state) == []


def test_harvest_allows_making_room_and_gifting_new_earnings():
    state = position()
    state['resources'][rc.ROMANS] = rc.MAX_RESOURCES
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    offers = []

    def agent(board, faction, request):
        stage = request['window']['stage']
        offers.append((faction, stage, request['available'], request['recipients'].get(rc.ROMANS)))
        if faction == rc.ROMANS:
            return {'transfers': [gift(rc.BELGAE, 18 if stage == 'before_earnings' else 2)]}
        return {'transfers': [gift(rc.ROMANS, 2), gift(rc.BELGAE, 2)]}

    use_agent(state, agent)
    result = harvest_phase(state)
    assert offers == [(rc.ROMANS, 'before_earnings', 45, None),
                      (rc.ROMANS, 'after_earnings', 45, None), (rc.AEDUI, 'after_earnings', 4, 2)]
    assert result[rc.ROMANS] == 30 and result[rc.AEDUI] == 4
    assert [row['stage'] for row in result['transfers']] == ['before_earnings'] + ['after_earnings'] * 3
    assert state['resources'][rc.ROMANS] == 45
    assert state['resources'][rc.AEDUI] == 0 and state['resources'][rc.BELGAE] == 22


def test_bad_or_stale_plan_cannot_move_any_resources():
    state = position()
    state['resources'].update({rc.AEDUI: 16, rc.ROMANS: 43})
    request = request_for(state, rc.AEDUI, 'harvest', 'before_earnings')
    before = encode(state)
    for response in (
        {'transfers': [gift(rc.ROMANS, 1), gift(rc.ROMANS, 2)]},
        {'transfers': [gift(rc.ROMANS, 2), gift(rc.BELGAE, 15)]},
        {'transfers': [gift(rc.ROMANS, True)]},
        {'transfers': [gift(rc.GERMANS, 1)]},
        {'transfers': [dict(gift(rc.BELGAE, 1), giver=rc.ROMANS)]},
        {'use_default': 1},
    ):
        with pytest.raises(ValueError):
            validate_response(state, request, response)
    assert encode(state) == before
    state['resources'][rc.ROMANS] = 44
    with pytest.raises(ValueError, match='have changed'):
        validate_response(state, request, {'transfers': []})


def test_cli_accepts_large_exact_gifts_and_inspects_the_board():
    state = position()
    state['resources'].update({rc.AEDUI: 30, rc.ROMANS: 15, rc.BELGAE: 44})
    request = request_for(state, rc.AEDUI, 'harvest', 'before_earnings')
    output = StringIO()
    input_ = StringIO('board\nGive to Romans (up to 30)\n31\nboard\n16\n'
                      'Give to Belgae (up to 1)\n1\nFinish Resource transfers\n')
    agent = make_cli_reactive({rc.AEDUI}, input_, output)
    before = encode(state)
    assert agent(state, rc.ROMANS, request) is None
    assert agent(state, rc.AEDUI, request) == {'transfers': [gift(rc.ROMANS, 16), gift(rc.BELGAE, 1)]}
    assert format_board(state) in output.getvalue() and encode(state) == before
    assert 'Enter a whole number from 1 to 30.' in output.getvalue()


def winter_position():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=41)
    state['current_card'] = rc.WINTER_CARD
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.BELGAE}
    state['resources'][rc.AEDUI] = 34
    return state


def session_for(state, meta=None, log=None, *, legacy=False):
    session = SeatSession(state, meta if meta is not None else {'seat': rc.AEDUI},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    if legacy:
        session.supports_resource_transfers = False
    state['decision_agent'] = session.reactive
    return session


def attempt(session):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return run_winter_round(session.state)


def pending_after_attempt(session, kind, stage=None):
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['kind'] == kind and request['faction'] == rc.AEDUI
    if stage is not None:
        assert request['window']['stage'] == stage
    return pending


def submit(session, pending, response):
    session.import_inbox({'decision_id': pending['id'], 'response': response})


def finish_quarters(session, pending):
    submit(session, pending, {rc.AEDUI: []})
    while True:
        with pytest.raises(DecisionPending):
            attempt(session)
        pending = deepcopy(session.data['pending'])
        request = decode(pending['request'])
        if request['kind'] != 'agreement':
            assert request['kind'] == KIND and request['window']['stage'] == 'after_payments'
            return pending
        assert request['faction'] == rc.AEDUI
        submit(session, pending, False)


def test_winter_gift_is_atomic_and_survives_later_save_resume_and_replay(tmp_path):
    session = session_for(winter_position())
    before = encode(board_copy(session.state))
    opening = pending_after_attempt(session, KIND, 'before_relocations')
    submit(session, opening, {'transfers': [gift(rc.BELGAE, 16), gift(rc.ROMANS, 20)]})
    assert pending_after_attempt(session, KIND, 'before_relocations') == opening
    assert session.error and not session.data['journal'] and encode(board_copy(session.state)) == before
    submit(session, opening, {'transfers': [gift(rc.BELGAE, 16)]})
    quarters = pending_after_attempt(session, 'quarters_plan')
    assert decode(quarters['board'])['resources'][rc.AEDUI] == 18
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before

    path = tmp_path / 'winter-gifts.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta, log)
    submit(resumed, finish_quarters(resumed, quarters), {'transfers': []})
    for stage in ('before_earnings', 'after_earnings'):
        pending = pending_after_attempt(resumed, KIND, stage)
        submit(resumed, pending, {'transfers': []})
    result = attempt(resumed)
    resumed.finish()
    assert sum(entry['reactive'] == KIND for entry in log) == 4
    assert result['phases']['quarters']['transfers'] == [
        {'from': rc.AEDUI, 'to': rc.BELGAE, 'given': 16, 'stage': 'before_relocations'},
    ]
    assert validate_state(state) == []

    replay = session_for(winter_position())
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in log]
    replay.data['expected'] = [
        {'id': entry['assistant_id'], 'signature': entry['assistant_signature'],
         'request': entry['assistant_request'],
         'action_windows_version': entry.get('assistant_action_windows_version', 0)}
        for entry in log
    ]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == log and encode(board_copy(replay.state)) == encode(board_copy(state))


def test_legacy_save_already_at_quarters_keeps_its_pending_request(tmp_path):
    session = session_for(winter_position(), legacy=True)
    pending = pending_after_attempt(session, 'quarters_plan')
    path = tmp_path / 'legacy-quarters.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta, log)
    assert pending_after_attempt(resumed, 'quarters_plan') == pending
    assert decode(finish_quarters(resumed, pending)['board'])['resources'][rc.AEDUI] == 34
