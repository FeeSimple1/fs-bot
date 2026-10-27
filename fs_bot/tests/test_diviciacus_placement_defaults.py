"""Card 38's converted placements retain physical colour and visibility."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces,
    count_pieces_by_state,
    get_available,
    move_piece,
    place_piece,
    remove_piece,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.engine.diviciacus import KEY, force_scope
from fs_bot.state.state_schema import build_initial_state, validate_state


@pytest.mark.parametrize("placement_kwargs", [{}, {"piece_state": None}])
@pytest.mark.parametrize("operation", ["move", "remove"])
def test_default_hidden_converted_placement_remains_in_the_borrowed_cohort(
        placement_kwargs, operation):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    state["non_player_factions"] = set()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 20)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND)
    execute_event(state, 38)
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        # No physical Auxilia remain Available. Agreement permits an Aedui
        # Warband to be placed and act as an Auxilia, without recolouring it.
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                    **placement_kwargs)
        assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 22
        assert state[KEY]["pieces"][rc.MORINI] == {
            rc.HIDDEN: 2, rc.REVEALED: 0, rc.SCOUTED: 0,
        }
        if operation == "move":
            move_piece(state, rc.MORINI, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2,
                       piece_state=rc.HIDDEN, physical_owner=rc.AEDUI)
            assert count_pieces_by_state(
                state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
            assert state["spaces"][rc.NERVII]["pieces"][rc.AEDUI][rc.HIDDEN][rc.WARBAND] == 2
        else:
            remove_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2,
                         piece_state=rc.HIDDEN, physical_owner=rc.AEDUI)
            assert get_available(state, rc.AEDUI, rc.WARBAND) == 20
        assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 20
        assert get_available(state, rc.ROMANS, rc.AUXILIA) == 0
        assert validate_state(state) == []
    assert validate_state(state) == []
