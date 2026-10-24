"""Diviciacus choices remain effective from real menus through execution."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.card_effects import execute_event
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import collect_player_action
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


@pytest.mark.parametrize('order', ['command_first', 'sa_first'])
def test_sa_only_cooperation_actually_enables_selected_ambush(order):
    # A1.4 expressly includes treating the partner's pieces as one's own
    # for enabling Ambush. The menu must not promise an Ambush that the
    # executor later silently drops when only SA cooperation was requested.
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    state['non_player_factions'] = set()
    state['resources'][rc.AEDUI] = 10
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.LEADER,
                leader_name=rc.DIVICIACUS)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND, 2)
    requests = []

    def consent(board, faction, request):
        requests.append((faction, request))
        if request['kind'] == 'agreement':
            return True
        if request['kind'] == 'retreat':
            return {'retreat': False}
        return None

    state['decision_agent'] = consent
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    if order == 'command_first':
        lines = ['Battle', 'n', rc.AEDUI_REGION, rc.BELGAE, 'y', 'Ambush',
                 'y', rc.AEDUI_REGION, rc.AEDUI_REGION, 'n']
    else:
        lines = ['Special Activity first, then Command', 'Ambush', 'y',
                 rc.AEDUI_REGION, rc.AEDUI_REGION, 'Battle', 'n',
                 rc.AEDUI_REGION, rc.BELGAE, 'n']
    action = collect_player_action(state, rc.AEDUI, ACTION_COMMAND_SA,
        io.StringIO('\n'.join(lines) + '\n'), io.StringIO())
    assert requests == [], 'Planning must not consume another human’s consent'
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    assert action['details']['diviciacus_regions'] == []
    assert action['details']['diviciacus_sa_regions'] == [rc.AEDUI_REGION]
    result = execute_decision(state, rc.AEDUI, {'player_action': action})
    assert result['executed'], result
    assert result['battle_sa_executed'], result
    assert not result.get('errors'), result
    assert any(faction == rc.ROMANS and request.get('request_type') == 'diviciacus'
               for faction, request in requests)


def test_borrowed_march_owner_choice_survives_actual_pause_save_resume(tmp_path):
    # Card 38 and §3.2.2: the Roman human chooses a subset of the combined
    # group; moving blue counters must preserve their physical ownership.
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=38)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = 10
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    execute_event(state, 38)
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 38}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
    action = {'command': 'March', 'sa': 'No SA', 'details': {
        'diviciacus_regions': [rc.CARNUTES], 'origins': [rc.CARNUTES],
        'destinations': [rc.MANDUBII], 'routes': {rc.CARNUTES: [rc.MANDUBII]},
        'groups': {rc.CARNUTES: {rc.AUXILIA: 2, rc.LEADER: False}}}}

    def attach(current):
        def agent(board, faction, request):
            if faction == rc.AEDUI and request['kind'] == 'agreement':
                return True
            return current.reactive(board, faction, request)

        current.state['decision_agent'] = agent

        def driver(*args):
            pass

        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        return driver

    driver = attach(session)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            execute_decision(state, rc.ROMANS, {'player_action': action})
    assert encode(board_copy(state)) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'diviciacus_pieces'
    assert request['count'] == 2
    assert request['available'] == {rc.ROMANS: 2, rc.AEDUI: 3}
    saved = tmp_path / 'march-pending.json'
    save_game(state, saved, meta=meta, log=session.log)
    restored, restored_meta, log = load_game(saved, validate=True)
    resumed = SeatSession(restored, restored_meta, log, HumanTurnDisplay(io.StringIO()))
    resumed_driver = attach(resumed)
    resumed.import_inbox({'decision_id': pending['id'],
                         'response': {'counts': {rc.ROMANS: 0, rc.AEDUI: 2}}})
    with _action_transaction(restored, resumed_driver):
        result = execute_decision(restored, rc.ROMANS, {'player_action': action})
    assert result['executed'], result
    resumed.finish()
    assert count_pieces(restored, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(restored, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(restored, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert restored['resources'][rc.ROMANS] == 8
    assert '_diviciacus_force' not in restored
    assert resumed.data['pending'] is None
    assert len(log) == 1 and log[0]['reactive'] == 'diviciacus_pieces'
