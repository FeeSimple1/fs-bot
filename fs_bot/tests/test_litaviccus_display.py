"""Card 45's full Aedui force remains identifiable at human decisions."""
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, flip_piece, get_available, place_piece,
    remove_piece,
)
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import (
    HumanTurnDisplay, format_board, format_region_table, format_victory_state,
    snapshot_state,
)
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(scenario):
    state = build_initial_state(scenario, seed=45)
    state.update(current_card=45, next_card=35, non_player_factions=set())
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    leader = rc.BODUOGNATUS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.AMBIORIX
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.LEADER, leader_name=leader)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    remove_piece(state, rc.MANDUBII, rc.AEDUI, rc.ALLY)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL)
    assert _ally_tribe(state, rc.TRIBE_SENONES, rc.AEDUI)
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        place_piece(state, rc.MANDUBII, rc.AEDUI, rc.LEADER,
                    leader_name=rc.DIVICIACUS)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 3)
    assert validate_state(state) == []
    return state


def output(display, state, faction):
    display.stdout.seek(0)
    display.stdout.truncate()
    display.before_decision(state, faction)
    return display.stdout.getvalue()


@pytest.mark.parametrize('scenario', [
    rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR,
])
def test_litaviccus_full_force_display_preserves_physical_owners_and_changes(scenario):
    from fs_bot.battle.combined import litaviccus_force

    state = position(scenario)
    initial = snapshot_state(state)
    table, victory = format_region_table(state), format_victory_state(state)
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.BELGAE, rc.AEDUI))
    with litaviccus_force(state, rc.BELGAE, rc.MANDUBII):
        assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.CITADEL) == 1
        assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 0
        before_inspection = encode(state)
        assert format_region_table(state) == table
        assert format_victory_state(state) == victory
        assert snapshot_state(state) == initial
        shown = format_board(state)
        assert 'Litaviccus in Mandubii: Belgae use lent forces:' in shown
        assert 'Aedui Warband:3[H2/R1/S0]' in shown
        assert 'Aedui Ally:1' in shown
        assert 'Aedui Citadel:1' in shown
        assert 'Admagetobriga' not in shown
        if scenario in rc.ARIOVISTUS_SCENARIOS:
            assert 'Aedui Leader:Diviciacus' in shown
            assert 'L(Diviciacus)' in shown and 'L(Boduognatus)' in shown
        assert 'No board changes.' in output(display, state, rc.BELGAE)
        assert encode(state) == before_inspection

        remove_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND,
                     piece_state=rc.HIDDEN, physical_owner=rc.AEDUI)
        flip_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND,
                   from_state=rc.REVEALED, to_state=rc.HIDDEN,
                   physical_owner=rc.AEDUI)
        changes = output(display, state, rc.BELGAE)
        assert 'Mandubii: Aedui Revealed Warband: 1 -> 0' in changes
        assert 'Belgae Hidden Warband:' not in changes
        assert 'Aedui Warband:2[H2/R0/S0]' in changes
    assert 'No board changes.' in output(display, state, rc.BELGAE)
    assert 'Mandubii: Aedui Revealed Warband: 1 -> 0' in output(display, state, rc.AEDUI)
    assert 'ACTIVE FORCES' not in format_board(state)
    assert validate_state(state) == []


def test_saved_pending_litaviccus_board_shows_full_borrowed_force_and_actual_owners(tmp_path, capsys):
    from fs_bot.battle.combined import COMBINED_KEY, litaviccus_force
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.llm_seat import cmd_board
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

    state = position(rc.SCENARIO_ARIOVISTUS)
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.BELGAE,))
    session = SeatSession(state, {'seat': rc.BELGAE}, [], display)
    state['decision_agent'] = session.reactive
    physical_table = format_region_table(state)
    before = encode(board_copy(state))

    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            with litaviccus_force(state, rc.BELGAE, rc.MANDUBII):
                session.reactive(state, rc.BELGAE, {
                    'kind': 'loss_order', 'region': rc.MANDUBII, 'losses': 1,
                    'pieces': [(rc.WARBAND, rc.HIDDEN, rc.AEDUI),
                               (rc.WARBAND, rc.HIDDEN, rc.BELGAE)],
                })
    assert COMBINED_KEY not in state
    assert encode(board_copy(state)) == before
    pending = decode(session.data['pending']['board'])
    assert pending[COMBINED_KEY]['source'] == 'Litaviccus'
    assert format_region_table(pending) == physical_table
    save_game(state, tmp_path / 'save.json', meta=session.meta, log=session.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    shown = capsys.readouterr().out
    assert physical_table in shown
    assert 'Litaviccus in Mandubii: Belgae use lent forces:' in shown
    assert 'Aedui Ally:1' in shown and 'Aedui Citadel:1' in shown
    assert 'Aedui Leader:Diviciacus' in shown
    assert 'Admagetobriga' not in shown
    restored, meta, _ = load_game(tmp_path / 'save.json', validate=True)
    assert meta['assistant_session']['pending'] == session.data['pending']
    assert encode(board_copy(restored)) == before


def test_full_litaviccus_counterattack_owner_choice_survives_save_resume_and_replay(tmp_path, capsys):
    from fs_bot.tests.test_event_battle_choices_sessions import (
        event, pending, session, step, submit,
    )
    from fs_bot.tools.llm_seat import cmd_board
    from fs_bot.tools.seat_session import board_copy

    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=45)
    state.update(current_card=45, next_card=35, executing_faction=rc.BELGAE,
                 non_player_factions={rc.ROMANS, rc.ARVERNI, rc.AEDUI})
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    initial = deepcopy(state)
    available = get_available(state, rc.AEDUI, rc.WARBAND)
    ses = session(state, rc.BELGAE)
    before = encode(board_copy(state))
    assert pending(ses, 45)['request_type'] == 'fixed_event_battle'
    submit(ses, {'region': rc.CARNUTES, 'defender': rc.ROMANS})
    request = pending(ses, 45)
    casualty = [rc.WARBAND, rc.HIDDEN, rc.AEDUI]
    assert request['kind'] == 'loss_order' and request['faction'] == rc.BELGAE
    assert casualty in [list(piece) for piece in request['pieces']]
    assert [rc.WARBAND, rc.HIDDEN, rc.BELGAE] in [list(piece) for piece in request['pieces']]
    assert encode(board_copy(state)) == before
    intermediate = decode(ses.data['pending']['board'])
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    shown = capsys.readouterr().out
    assert format_region_table(intermediate) in shown
    assert 'Litaviccus in Carnutes: Belgae use lent forces: Aedui Warband:2' in shown

    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, rc.BELGAE, meta, log)
    assert resumed.data['pending'] == ses.data['pending']
    submit(resumed, [casualty])
    result = step(resumed, 45)
    resumed.finish()
    assert result['executed'] and len(log) == 2
    assert decode(log[1]['assistant_response']) == [casualty]
    assert count_pieces(restored, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces_by_state(restored, rc.CARNUTES, rc.BELGAE,
                                 rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces_by_state(restored, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.REVEALED) == 1
    assert get_available(restored, rc.AEDUI, rc.WARBAND) == available + 1
    records, replay_requests = iter(log), []

    def recorded(_state, faction, request):
        # Match SeatSession's seat filter: bot loss choices are not human
        # journal entries and must not consume the accepted Aedui choice.
        if faction != rc.BELGAE:
            return None
        entry = next(records)
        replay_requests.append((dict(request, faction=faction),
                                decode(entry['assistant_request'])))
        return decode(entry['assistant_response'])

    initial['decision_agent'] = recorded
    assert event(initial, 45) == result
    assert len(replay_requests) == len(log)
    assert all(actual == recorded for actual, recorded in replay_requests)
    assert next(records, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    assert validate_state(restored) == []
