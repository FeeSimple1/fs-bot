"""§6.3.2-.3: Control qualifies the complete adjacent relocation step."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.engine.quarters import apply_relocations, validate_quarters_plan
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.tools.run_batch import play_one


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('faction,pieces,leader', [
    (rc.ROMANS, (rc.LEGION, rc.AUXILIA), None),
    (rc.BELGAE, (rc.LEADER, rc.WARBAND), rc.AMBIORIX),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_mixed_group_does_not_lose_destination_when_first_piece_removes_host_control(
        scenario, faction, pieces, leader, reverse):
    state = build_initial_state(scenario, seed=29)
    if leader and scenario in rc.ARIOVISTUS_SCENARIOS:
        leader = rc.BODUOGNATUS
    # The first arriving piece ties the host, temporarily causing No Control.
    # This must not forbid the other piece in the same relocation step.
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    for piece in pieces:
        kwargs = ({'from_legions_track': True} if piece == rc.LEGION
                  else {'leader_name': leader} if piece == rc.LEADER else {})
        place_piece(state, rc.MORINI, faction, piece, **kwargs)
    calls = []
    def agree(board, host, request):
        calls.append((host, request['request_type'],
                      calculate_control(board, rc.ATREBATES)))
        return True
    state['decision_agent'] = agree
    moves = [(piece, rc.MORINI, rc.ATREBATES, 1) for piece in pieces]
    if reverse:
        moves.reverse()
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    assert validate_quarters_plan(state, {faction: moves}) == []
    assert calls == []
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    apply_relocations(state, faction, moves)
    assert calls == [(rc.AEDUI, 'quarters', rc.AEDUI_CONTROL)]
    assert calculate_control(state, rc.ATREBATES) == rc.FACTION_CONTROL[faction]
    assert all(count_pieces(state, rc.ATREBATES, faction, piece) == 1 for piece in pieces)
    assert check_structural_integrity(state) == []


def test_multiple_origins_can_share_a_destination_that_their_arrivals_uncontrol():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=95)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    state['decision_agent'] = lambda *_: True
    moves = [(rc.AUXILIA, rc.MORINI, rc.ATREBATES, 2),
             (rc.AUXILIA, rc.NERVII, rc.ATREBATES, 1)]
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    apply_relocations(state, rc.ROMANS, moves)
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 3
    assert calculate_control(state, rc.ATREBATES) == rc.ROMAN_CONTROL


def test_original_revealed_piece_moves_instead_of_hidden_arrival():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=29)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    moves = [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1),
             (rc.WARBAND, rc.ATREBATES, rc.MANDUBII, 1)]
    apply_relocations(state, rc.BELGAE, moves)
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1


@pytest.mark.parametrize('scenario,seed', [
    (rc.SCENARIO_RECONQUEST, 29), (rc.SCENARIO_GREAT_REVOLT, 166),
    (rc.SCENARIO_ARIOVISTUS, 34), (rc.SCENARIO_ARIOVISTUS, 95),
    (rc.SCENARIO_GALLIC_WAR, 34), (rc.SCENARIO_GALLIC_WAR, 71),
    (rc.SCENARIO_GALLIC_WAR, 95),
])
def test_captured_quarters_crash_games_complete_with_valid_board_and_ranking(scenario, seed):
    result = play_one((scenario, seed))
    assert result['completed'], result.get('errors')
    assert result['game_completed'] and result['audit_completed']
    assert result['errors'] == []
    assert result['integrity_findings'] == []
    assert len(result['final_ranking']) == 4
    assert result['winner'] == result['final_ranking'][0][0]
