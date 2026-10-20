"""Physical ownership stays visible during §4.5.1, A4.5.1 and A28 forces."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.combined import combined_force
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import (
    count_pieces, flip_piece, place_piece, remove_piece,
)
from fs_bot.cli.display import (
    HumanTurnDisplay, format_board, format_region_table, format_victory_state,
    snapshot_state,
)
from fs_bot.commands.sa_enlist import begin_borrow, end_borrow, scoped_free_force
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _output(display, state, faction):
    display.stdout.seek(0)
    display.stdout.truncate()
    display.before_decision(state, faction, show_context=False)
    return display.stdout.getvalue()


@pytest.mark.parametrize('scenario,leader', [
    (rc.SCENARIO_PAX_GALLICA, rc.AMBIORIX),
    (rc.SCENARIO_ARIOVISTUS, rc.BODUOGNATUS),
])
def test_enlist_board_and_each_seat_keep_physical_owner_through_losses(scenario, leader):
    state = build_initial_state(scenario, seed=5)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=leader)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    refresh_all_control(state)
    initial = snapshot_state(state)
    physical_row = next(line for line in format_region_table(state).splitlines()
                        if line.startswith(rc.NERVII + ' '))
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.BELGAE, rc.GERMANS))
    begin_borrow(state, {'command': 'Battle', 'sa': 'Enlist',
                        'sa_regions': [rc.NERVII], 'details': {
                            'enlist': {'type': 'borrow', 'regions': [rc.NERVII]}}})
    try:
        assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 3
        before_display = encode(state)
        board = format_board(state)
        during = snapshot_state(state)
        assert encode(state) == before_display
        assert during['pieces'] == initial['pieces']
        assert during['piece_states'] == initial['piece_states']
        assert during['controls'][rc.NERVII] == rc.BELGIC_CONTROL
        row = next(line for line in board.splitlines() if line.startswith(rc.NERVII + ' '))
        # Only the six-character Control column changes during Enlist.
        assert row[:14] + row[20:] == physical_row[:14] + physical_row[20:]
        assert "Enlist in Nervii: Belgae use Germans' 3 Warband" in board
        assert 'including Control' in board
        assert 'Warband:' not in _output(display, state, rc.BELGAE)

        remove_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND,
                     piece_state=rc.HIDDEN, physical_owner=rc.GERMANS)
        delta = _output(display, state, rc.BELGAE)
        assert 'Nervii: Germans Hidden Warband: 3 -> 2' in delta
        assert 'Belgae Hidden Warband' not in delta
    finally:
        end_borrow(state)
    # The seat that saw the loss already must not see a fictitious return.
    assert 'Warband:' not in _output(display, state, rc.BELGAE)
    # Another seat retains its independent earlier baseline.
    delta = _output(display, state, rc.GERMANS)
    assert 'Nervii: Germans Hidden Warband: 3 -> 2' in delta
    assert 'Belgae Hidden Warband' not in delta
    assert 'ACTIVE FORCES' not in format_board(state)


def test_admagetobriga_board_and_deltas_keep_both_auxilia_and_warband_owners():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=28)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2,
                piece_state=rc.REVEALED)
    refresh_all_control(state)
    table, initial = format_region_table(state), snapshot_state(state)
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.AEDUI, rc.ROMANS))
    with combined_force(state, rc.AEDUI, {rc.SEQUANI: [rc.ROMANS, rc.ARVERNI]}):
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
        before_display = encode(state)
        assert format_region_table(state) == table
        assert snapshot_state(state) == initial
        board = format_board(state)
        assert 'Admagetobriga in Sequani: Aedui use lent forces:' in board
        assert 'Romans Auxilia:3[H3/R0/S0]' in board
        assert 'Arverni Warband:2[H0/R2/S0]' in board
        assert 'No board changes.' in _output(display, state, rc.AEDUI)
        assert encode(state) == before_display

        remove_piece(state, rc.SEQUANI, rc.AEDUI, rc.AUXILIA,
                     piece_state=rc.HIDDEN, physical_owner=rc.ROMANS)
        flip_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND,
                   from_state=rc.REVEALED, to_state=rc.HIDDEN,
                   physical_owner=rc.ARVERNI)
        delta = _output(display, state, rc.AEDUI)
        assert 'Sequani: Romans Hidden Auxilia: 3 -> 2' in delta
        assert 'Sequani: Arverni Hidden Warband: 0 -> 1' in delta
        assert 'Sequani: Arverni Revealed Warband: 2 -> 1' in delta
        assert 'Aedui Hidden Warband' not in delta
    assert 'No board changes.' in _output(display, state, rc.AEDUI)
    assert 'Sequani: Romans Hidden Auxilia: 3 -> 2' in _output(display, state, rc.ROMANS)


def test_enlist_free_force_does_not_hide_unselected_pieces_or_change_displayed_victory():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=4)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.ALLY)
    refresh_all_control(state)
    initial = snapshot_state(state)
    table, victory = format_region_table(state), format_victory_state(state)
    display = HumanTurnDisplay(StringIO())
    display.remember(state, (rc.GERMANS,))
    with scoped_free_force(state, rc.SUGAMBRI, {rc.HIDDEN: 2, rc.REVEALED: 1}):
        assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 3
        assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT) == 0
        before_display = encode(state)
        assert format_region_table(state) == table
        assert format_victory_state(state) == victory
        assert snapshot_state(state) == initial
        board = format_board(state)
        assert "Enlist free Battle in Sugambri: Germans' 3 Warband [H2/R1/S0]" in board
        assert 'W:8[H5/R3/S0]' in board
        assert 'No board changes.' in _output(display, state, rc.GERMANS)
        assert encode(state) == before_display
        flip_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND,
                   from_state=rc.HIDDEN, to_state=rc.REVEALED)
        delta = _output(display, state, rc.GERMANS)
        assert 'Sugambri: Germans Hidden Warband: 5 -> 4' in delta
        assert 'Sugambri: Germans Revealed Warband: 3 -> 4' in delta
    assert 'No board changes.' in _output(display, state, rc.GERMANS)
