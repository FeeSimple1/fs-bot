"""§1.5.2 donor choices through the live Sequence of Play."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.menus import prompt_action
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_EVENT, ACTION_PASS, resolve_card_turn
from fs_bot.engine.resource_transfers import FRAME, KIND
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession


def rally_position():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=41)
    state['current_card'] = 49
    state['eligibility'][rc.AEDUI] = rc.ELIGIBLE
    for faction in (rc.ROMANS, rc.ARVERNI, rc.BELGAE):
        state['eligibility'][faction] = rc.INELIGIBLE
    state['resources'].update({rc.ROMANS: 30, rc.AEDUI: 0, rc.BELGAE: 44})
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    for region, tribe in ((rc.AEDUI_REGION, rc.TRIBE_AEDUI), (rc.MANDUBII, rc.TRIBE_MANDUBII)):
        place_piece(state, region, rc.AEDUI, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    return state


def play_only(state, actor, decision):
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == actor else rc.INELIGIBLE
    turn = resolve_card_turn(state, lambda *_: decision, execute=True)
    return turn['actions_taken'][actor]['execution']


def rally_plan(regions=(rc.AEDUI_REGION, rc.MANDUBII)):
    return {'command': rc.CMD_RALLY, 'sa': 'No SA', 'details': {'rally_plan': {
        'steps': [dict(region=region, action='place_warbands', count=1) for region in regions]}}}


def give(recipient, amount, *, defer=False):
    return {'transfers': [dict(to=recipient, amount=amount)], **({'defer': True} if defer else {})}


@pytest.mark.parametrize('actor_is_bot', [False, True])
def test_nonacting_donor_funds_first_and_later_regions(actor_is_bot):
    state = rally_position()
    if actor_is_bot:
        state['non_player_factions'].add(rc.AEDUI)
    offers = []

    def agent(board, faction, request):
        if request['kind'] != KIND:
            return None
        window = request['window']
        assert window['actor'] == rc.AEDUI and window['action'] == 'Command'
        if faction == rc.ROMANS:
            assert set(request['recipients']) == {rc.AEDUI}
            offers.append((window['stage'], window.get('index'), board['resources'][rc.AEDUI]))
            if window['stage'] == 'action_start':
                return give(rc.AEDUI, 1, defer=True)
            if window['stage'] == 'rally_option' and window.get('index') == 1:
                assert count_pieces(board, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
                return give(rc.AEDUI, 2)
            return {'transfers': [], 'defer': True}
        assert not actor_is_bot and faction == rc.AEDUI
        assert set(request['recipients']) == {rc.ROMANS, rc.ARVERNI, rc.BELGAE}
        return {'transfers': []}

    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    plan_key = 'bot_action' if actor_is_bot else 'player_action'
    result = play_only(state, rc.AEDUI, {'action': ACTION_COMMAND, plan_key: rally_plan()})
    assert result['executed'] and not result['errors']
    assert offers == [('action_start', None, 0), ('rally_option', 0, 1), ('rally_option', 1, 0)]
    assert result['transfers'] == [
        {'from': rc.ROMANS, 'to': rc.AEDUI, 'given': 1, 'stage': 'action_start'},
        {'from': rc.ROMANS, 'to': rc.AEDUI, 'given': 2, 'stage': 'rally_option'},
    ]
    assert state['resources'][rc.AEDUI] == 1 and state['resources'][rc.ROMANS] == 27
    assert FRAME not in state


def test_terminal_opens_donor_menu_before_collecting_and_validating_the_plan(monkeypatch):
    state = rally_position()
    stdin = StringIO('1\nGive to Aedui (up to 30)\n16\n1\n1\n')
    stdout = StringIO()
    agent = make_cli_reactive({rc.ROMANS, rc.AEDUI}, stdin, stdout)
    # Keep the fixture focused on the real gift menus and the plan boundary.
    agent.supports_action_windows = False
    state['decision_agent'] = agent
    from fs_bot.cli import human_plan

    def collect(board, faction, action, *_):
        assert board['resources'][rc.AEDUI] == 16
        return rally_plan((rc.AEDUI_REGION,))

    monkeypatch.setattr(human_plan, 'collect_player_action', collect)
    turn = resolve_card_turn(state, lambda board, faction, options, position:
        prompt_action(board, faction, [ACTION_COMMAND], position, stdin, stdout), execute=True)
    assert stdout.getvalue().count('Command, action start.') == 3
    assert turn['actions_taken'][rc.AEDUI]['execution']['transfers'][0]['given'] == 16
    assert state['resources'][rc.AEDUI] == 15 and state['resources'][rc.ROMANS] == 14


def test_bot_raid_reports_gift_even_when_the_donor_has_nothing_left_to_steal():
    state = rally_position()
    state['non_player_factions'].add(rc.AEDUI)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)

    def agent(board, faction, request):
        if request['kind'] == KIND:
            return give(rc.AEDUI, 30)
        return None

    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    result = play_only(state, rc.AEDUI, {'action': ACTION_COMMAND, 'bot_action': {
        'command': rc.CMD_RAID, 'details': {'raid_plan': [
            {'region': rc.MANDUBII, 'target': rc.ROMANS}]}}})
    assert not result['executed'] and '0 Resources' in result['errors'][0]['error']
    assert result['transfers'] == [
        {'from': rc.ROMANS, 'to': rc.AEDUI, 'given': 30, 'stage': 'action_start'}]
    assert state['resources'][rc.ROMANS] == 0 and state['resources'][rc.AEDUI] == 30


def test_frumentum_gift_changes_public_treasury_without_financing_the_grant():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=41)
    state.update(current_card='A53', non_player_factions={rc.BELGAE, rc.GERMANS})
    state['resources'].update({rc.ROMANS: 7, rc.AEDUI: 20})
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 1)
    march = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [rc.CARNUTES], 'destinations': [rc.MANDUBII],
        'routes': {rc.CARNUTES: [rc.MANDUBII]},
        'groups': {rc.CARNUTES: {rc.AUXILIA: 1, rc.LEADER: False}}}}
    funding = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            window = request['window']
            assert window['actor'] == rc.AEDUI and window['action'] == 'Event'
            assert not board.get('_frumentum_budget', {}).get('paying')
            if faction == rc.ROMANS:
                assert set(request['recipients']) == {rc.AEDUI}
            elif window.get('step') == 'A53.action':
                return give(rc.ROMANS, 4)
            if window['stage'] != 'action_end':
                return {'transfers': [], 'defer': True}
        elif request['kind'] == 'frumentum_amount':
            return {'amount': 6}
        elif request['kind'] == 'frumentum_action':
            funding.append((request['remaining_resources'], request['reserved_roman_resources']))
            return march if len(funding) == 1 else {'decline': True}
        return None

    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    result = play_only(state, rc.AEDUI, {'action': ACTION_EVENT, 'player_action': {
        'command': 'Event', 'details': {'card_id': 'A53', 'text_preference': rc.EVENT_UNSHADED}}})
    assert result['executed']
    assert funding == [(6, 11), (4, 11)]
    assert state['resources'][rc.ROMANS] == 15 and state['resources'][rc.AEDUI] == 10
    assert result['transfers'] == [{'from': rc.AEDUI, 'to': rc.ROMANS, 'given': 4, 'stage': 'event_step'}]


def test_durable_opening_gift_replays_once_after_a_later_window_pauses(tmp_path):
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, log or [],
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session

    def attempt(session):
        def choose(*_):
            return {'action': ACTION_COMMAND, 'bot_action': rally_plan()}

        choose.transaction_checkpoint = session.checkpoint
        choose.transaction_restore = session.restore
        return resolve_card_turn(session.state, choose, execute=True)

    def pending(session, stage):
        with pytest.raises(DecisionPending):
            attempt(session)
        current = deepcopy(session.data['pending'])
        assert decode(current['request'])['window']['stage'] == stage
        return current

    def submit(session, current, response):
        session.import_inbox({'decision_id': current['id'], 'response': response})

    state = rally_position()
    state['non_player_factions'].add(rc.AEDUI)
    session = session_for(state)
    opening = pending(session, 'action_start')
    submit(session, opening, give(rc.AEDUI, 1, defer=True))
    middle = pending(session, 'rally_option')
    assert state['resources'][rc.ROMANS] == 30
    assert decode(middle['board'])['resources'][rc.ROMANS] == 29
    path = tmp_path / 'gift.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path)
    session = session_for(restored, meta, log)
    assert pending(session, 'rally_option') == middle
    submit(session, middle, give(rc.BELGAE, 1))
    assert pending(session, 'rally_option') == middle
    assert 'offered recipient' in session.error
    submit(session, middle, {'transfers': [], 'defer': True})
    later = pending(session, 'rally_option')
    assert decode(later['request'])['window']['index'] == 1
    submit(session, later, give(rc.AEDUI, 2))
    turn = attempt(session)
    session.finish()
    assert restored['resources'][rc.ROMANS] == 27 and FRAME not in restored
    assert [row['given'] for row in turn['actions_taken'][rc.AEDUI]['execution']['transfers']] == [1, 2]
    assert [decode(row['assistant_response']) for row in session.log] == [
        give(rc.AEDUI, 1, defer=True), {'transfers': [], 'defer': True}, give(rc.AEDUI, 2)]


def test_pass_never_opens_a_gift_window():
    state = rally_position()
    before = encode(state['resources'])

    def agent(board, faction, request):
        if request['kind'] == KIND:
            pytest.fail('Pass offered Resource transfers')

    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    result = resolve_card_turn(state, lambda *_: {'action': ACTION_PASS}, execute=True)
    assert result['passes'] == [rc.AEDUI]
    assert encode(state['resources']) == dict(before, **{rc.AEDUI: before[rc.AEDUI] + 1})
    assert FRAME not in state
