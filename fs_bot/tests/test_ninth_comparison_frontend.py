"""UI9-01 and UI9-02 through public turns, terminal menus, and saved decisions."""

from copy import deepcopy
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.morbihan_display import PROJECTION_KEY
from fs_bot.cli.display import HumanTurnDisplay, format_board, format_state_delta, snapshot_state
from fs_bot.cli.human_plan import collect_player_action
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND_SA, ACTION_EVENT, _action_transaction, get_sop_factions,
)
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.llm_seat import cmd_board
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def execute_event(state, card, actor, side=rc.EVENT_UNSHADED):
    state['current_card'] = card
    result = execute_decision(state, actor, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'text_preference': side,
        },
    }})
    assert result['executed'] and not result.get('errors')
    return result


def enlist_position(scenario, owner, side, hidden):
    state = build_initial_state(scenario, seed=19)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.BELGAE}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.SUGAMBRI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, hidden)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    state['resources'][rc.GERMANS] = 10
    if owner:
        execute_event(state, 8, owner, side)
    state['current_card'] = 8
    check(state)
    return state


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_german_baggage_trains_accepts_compact_and_explicit_enlist_raids(scenario):
    state = enlist_position(scenario, rc.GERMANS, rc.EVENT_SHADED, hidden=3)
    compact = {'count': 3}
    explicit = {'actions': [{'type': 'gain'} for _ in range(3)]}
    resolved = []
    for selection in (compact, explicit):
        board = deepcopy(state)
        result = submit_enlist_raid(board, selection)
        assert result['sa_execution']['executed']
        assert board['resources'][rc.GERMANS] == 13
        assert count_pieces_by_state(board, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3
        check(board)
        resolved.append((result, encode(board_copy(board))))
    assert resolved[0] == resolved[1]


def submit_enlist_raid(state, selection):
    plan = {'command': rc.CMD_RAID, 'sa': rc.SA_ENLIST, 'sa_regions': [rc.SUGAMBRI],
            'details': {'raid_plan': [{'region': rc.CARNUTES}],
                        'enlist': {'type': 'german_raid', 'region': rc.SUGAMBRI, **selection}}}
    result = execute_decision(state, rc.BELGAE, {
        'action': ACTION_COMMAND_SA, 'player_action': plan,
    })
    assert result['executed'] and not result.get('errors')
    return result


@pytest.mark.parametrize('owner,side,hidden,count', [
    (None, rc.EVENT_SHADED, 3, 3),
    (rc.BELGAE, rc.EVENT_SHADED, 3, 3),
    (rc.GERMANS, rc.EVENT_UNSHADED, 3, 3),
    (rc.GERMANS, rc.EVENT_SHADED, 2, 3),
    (rc.GERMANS, rc.EVENT_SHADED, 4, 4),
])
def test_enlist_raid_respects_german_ownership_visibility_and_raid_limit(owner, side, hidden, count):
    state = enlist_position(rc.SCENARIO_ARIOVISTUS, owner, side, hidden)
    if hidden == 2:
        place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, piece_state=rc.REVEALED)
    for selection in ({'count': count}, {'actions': [{'type': 'gain'} for _ in range(count)]}):
        board = deepcopy(state)
        result = submit_enlist_raid(board, selection)
        assert not result['sa_execution']['executed']
        assert board['resources'][rc.GERMANS] == 10
        assert count_pieces_by_state(board, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == hidden
        check(board)


class TerminalInput:
    def __init__(self, output, answers):
        self.output = output
        self.answers = iter(answers)
        self.offset = 0

    def readline(self):
        text = self.output.getvalue()
        prompt = text[self.offset:]
        self.offset = len(text)
        if 'Voluntary removal?' in prompt:
            return 'Finish voluntary removal\n'
        return next(self.answers) + '\n'


@pytest.mark.parametrize('devastated', [False, True])
def test_enlist_terminal_collects_three_legal_raids_without_applying_them(devastated):
    state = enlist_position(rc.SCENARIO_ARIOVISTUS, rc.GERMANS, rc.EVENT_SHADED, hidden=3)
    if devastated:
        state['markers'].setdefault(rc.SUGAMBRI, {})[rc.MARKER_DEVASTATED] = True
        place_piece(state, rc.SUGAMBRI, rc.ROMANS, rc.FORT)
        place_piece(state, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND)
        state['resources'].update({rc.ROMANS: 1, rc.AEDUI: 2})
        targets = [rc.ROMANS, rc.AEDUI, rc.AEDUI]
        expected = [{'type': 'steal', 'target': target} for target in targets]
    else:
        targets = ['(just gain 1 Resource)'] * 3
        expected = [{'type': 'gain'} for _ in targets]
    output = StringIO()
    source = TerminalInput(output, [
        'Special Activity first, then Command', 'Enlist', 'Raid', rc.SUGAMBRI, '1',
        *targets, 'Raid', rc.CARNUTES, 'gain 1 Resource', '(done)',
    ])
    state['decision_agent'] = make_cli_reactive([rc.BELGAE], source, output)
    before = encode(board_copy(state))
    plan = collect_player_action(state, rc.BELGAE, ACTION_COMMAND_SA, source, output)
    assert encode(board_copy(state)) == before
    assert 'Raid with how many Hidden German Warbands?\n  1) 3\n' in output.getvalue()
    assert plan['details']['enlist']['actions'] == expected
    if devastated:
        second_menu = output.getvalue().split(f'Raid 2 target in {rc.SUGAMBRI}?\n', 1)[1]
        assert second_menu.startswith(f'  1) {rc.AEDUI}\nEnter 1-1')
    result = execute_decision(state, rc.BELGAE, {'action': ACTION_COMMAND_SA, 'player_action': plan})
    assert result['sa_execution']['executed']
    assert state['resources'][rc.GERMANS] == 13
    assert count_pieces_by_state(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
    if devastated:
        assert state['resources'][rc.ROMANS] == state['resources'][rc.AEDUI] == 0
    check(state)


def morbihan_position(slingers):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.ROMANS}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.ARVERNI)
    for region in (rc.VENETI, rc.PICTONES):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2)
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2 if region == rc.VENETI else 1)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    if slingers:
        execute_event(state, 13, rc.ROMANS)
    state['current_card'] = 'A20'
    check(state)
    return state


def resume_morbihan(session):
    session.state['decision_agent'] = session.reactive
    driver = SimpleNamespace(transaction_checkpoint=session.checkpoint,
                             transaction_restore=session.restore,
                             transaction_complete=session.transaction_complete)
    with _action_transaction(session.state, driver):
        result = execute_event(session.state, 'A20', rc.GERMANS, rc.EVENT_SHADED)
    session.finish()
    return result


def answer_pending(session, response):
    pending = session.data['pending']
    session.import_inbox({'decision_id': pending['id'], 'response': response})


@pytest.mark.parametrize('slingers', [False, True])
def test_morbihan_saved_pending_board_shows_survivors_and_physical_control(slingers, tmp_path, capsys):
    state = morbihan_position(slingers)
    before = board_copy(state)
    baseline = deepcopy(state)
    baseline['decision_agent'] = lambda board, faction, request: (
        {'region': rc.CARNUTES} if request['kind'] == 'slingers_region' else None)
    expected = execute_event(baseline, 'A20', rc.GERMANS, rc.EVENT_SHADED)
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    if slingers:
        with pytest.raises(DecisionPending):
            resume_morbihan(session)
        assert decode(session.data['pending']['request'])['kind'] == 'slingers_region'
        answer_pending(session, {'region': rc.CARNUTES})
    with pytest.raises(DecisionPending):
        resume_morbihan(session)
    assert encode(board_copy(state)) == encode(before)

    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'loss_order'
    board = decode(pending['board'])
    remaining_veneti = 1 if slingers else 2
    assert board[PROJECTION_KEY]['survivors'][rc.VENETI][rc.HIDDEN] == remaining_veneti
    assert count_pieces(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 2 + remaining_veneti
    snapshot = snapshot_state(board)
    assert snapshot['pieces'][rc.VENETI, rc.ARVERNI, rc.WARBAND] == remaining_veneti
    assert snapshot['piece_states'][rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.HIDDEN] == remaining_veneti
    assert snapshot['pieces'][rc.PICTONES, rc.ARVERNI, rc.WARBAND] == 2
    assert (rc.CARNUTES, rc.ARVERNI, rc.WARBAND) not in snapshot['pieces']
    assert snapshot['controls'][rc.CARNUTES] == rc.ROMAN_CONTROL
    assert snapshot['controls'][rc.PICTONES] == rc.ARVERNI_CONTROL
    assert snapshot['controls'][rc.VENETI] == (rc.NO_CONTROL if slingers else rc.ARVERNI_CONTROL)
    assert get_available(board, rc.ARVERNI, rc.WARBAND) == 33 - remaining_veneti
    changes = format_state_delta(snapshot_state(before), snapshot)
    assert not any(rc.CARNUTES in line for line in changes)
    if slingers:
        assert '  Veneti: Arverni Hidden Warband: 2 -> 1' in changes

    text = format_board(board)
    lines = text.splitlines()
    assert any(line.startswith('Carnutes      Rom') and 'A:2[H0/R2/S0]' in line for line in lines)
    assert any(line.startswith('Pictones      Arv') and 'W:2[H2/R0/S0]' in line for line in lines)
    assert any(line.startswith('Veneti        ' + ('-' if slingers else 'Arv'))
               and f'W:{remaining_veneti}[H{remaining_veneti}/R0/S0]' in line for line in lines)
    context = next(line for line in lines if 'Morbihan: Arverni' in line)
    assert 'fight Romans in Carnutes as if there' in context
    assert f'Veneti: {remaining_veneti} Warband [H{remaining_veneti}/R0/S0]' in context
    assert encode(board) == pending['board']

    save_game(state, tmp_path / 'save.json', meta=session.meta, log=session.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    assert text in capsys.readouterr().out
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    with pytest.raises(DecisionPending):
        resume_morbihan(resumed)
    assert resumed.data['pending'] == pending
    if not slingers:
        answer_pending(resumed, [[rc.AUXILIA, rc.REVEALED]])
        with pytest.raises(DecisionPending):
            resume_morbihan(resumed)
        second = decode(resumed.data['pending']['board'])
        assert 'Carnutes: Romans Revealed Auxilia: 2 -> 1' in '\n'.join(
            format_state_delta(snapshot, snapshot_state(second)))
        assert resumed.data['pending']['id'] != pending['id']
    answer_pending(resumed, [[rc.AUXILIA, rc.REVEALED]])
    assert resume_morbihan(resumed) == expected
    assert encode(board_copy(restored)) == encode(board_copy(baseline))
    assert PROJECTION_KEY not in restored and resumed.data['pending'] is None
    check(restored)
