"""Physical inventory and rejection safety for §1.4.1–1.4.3/A1.4 helpers.

These exercise the public helpers without the higher-level action transaction:
a rejected operation must preserve the entire board, pools, controls and RNG.
"""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.state.state_schema import build_initial_state


def _snapshot(state):
    result = deepcopy({key: value for key, value in state.items() if key != "rng"})
    result["rng"] = state["rng"].getstate()
    return result


def _operation(state, operation, count, **kwargs):
    if operation == "place":
        pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, count, **kwargs)
    elif operation == "remove":
        pieces.remove_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, count, **kwargs)
    elif operation == "move":
        pieces.move_piece(state, rc.MORINI, rc.NERVII, rc.BELGAE, rc.WARBAND,
                          count, **kwargs)
    else:
        pieces.flip_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, count,
                          from_state=rc.HIDDEN, to_state=rc.REVEALED, **kwargs)


@pytest.mark.parametrize("operation", ["place", "remove", "move", "flip"])
@pytest.mark.parametrize("count", [-1, 1.5, 1.0, True, False, "1", None])
def test_invalid_count_is_rejected_without_changing_state(operation, count):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 3)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="nonnegative integer"):
        _operation(state, operation, count)
    assert _snapshot(state) == before


@pytest.mark.parametrize("operation", ["place", "remove", "move", "flip"])
def test_zero_count_is_an_exact_noop_even_with_empty_source(operation):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    before = _snapshot(state)
    _operation(state, operation, 0)
    assert _snapshot(state) == before


@pytest.mark.parametrize("kwargs", [{}, {"leader_name": rc.VERCINGETORIX}])
def test_invalid_leader_identity_does_not_consume_available(kwargs):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError):
        pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, **kwargs)
    assert _snapshot(state) == before


def test_excess_legion_placement_does_not_drain_track():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="Not enough Legions"):
        pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 13,
                           from_legions_track=True)
    assert _snapshot(state) == before


@pytest.mark.parametrize("visibility", [None, rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_excess_removal_does_not_partially_remove_pieces(visibility):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 1,
                           piece_state=ps)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError):
        pieces.remove_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                            4 if visibility is None else 2, piece_state=visibility)
    assert _snapshot(state) == before


def test_successful_mixed_visibility_removal_preserves_inventory():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    available = pieces.get_available(state, rc.BELGAE, rc.WARBAND)
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 1,
                           piece_state=ps)
    pieces.remove_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    assert pieces.count_pieces_by_state(
        state, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 1
    assert pieces.get_available(state, rc.BELGAE, rc.WARBAND) == available - 1


@pytest.mark.parametrize("operation", ["place", "remove", "move", "flip"])
def test_invalid_visibility_is_rejected_before_inventory_changes(operation):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 1)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="Unknown piece state"):
        if operation == "flip":
            pieces.flip_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                              from_state=rc.HIDDEN, to_state="invalid")
        else:
            _operation(state, operation, 1, piece_state="invalid")
    assert _snapshot(state) == before


def test_exhausted_available_does_not_create_destination_structure():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                       pieces.get_available(state, rc.BELGAE, rc.WARBAND))
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError):
        pieces.place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    assert _snapshot(state) == before


def test_leader_move_rejects_multiple_count_before_removing_source():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER,
                       leader_name=rc.CAESAR)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="1 Leader"):
        pieces.move_piece(state, rc.PROVINCIA, rc.MORINI, rc.ROMANS, rc.LEADER, 2)
    assert _snapshot(state) == before


def test_leader_move_rejects_occupied_destination_before_removing_source():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER,
                       leader_name=rc.CAESAR)
    # Fault injection: the helper must not erase either Leader when it detects
    # this already-invalid duplicate destination.
    state["spaces"][rc.MORINI]["pieces"][rc.ROMANS] = {rc.LEADER: rc.SUCCESSOR}
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="already has a Leader"):
        pieces.move_piece(state, rc.PROVINCIA, rc.MORINI, rc.ROMANS, rc.LEADER)
    assert _snapshot(state) == before


def test_same_region_leader_move_preserves_identity():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER,
                       leader_name=rc.CAESAR)
    before = _snapshot(state)
    pieces.move_piece(state, rc.PROVINCIA, rc.PROVINCIA, rc.ROMANS, rc.LEADER)
    assert _snapshot(state) == before


@pytest.mark.parametrize("operation", ["place", "move"])
def test_unknown_destination_does_not_create_a_region(operation):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    pieces.place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="Unknown Region"):
        if operation == "place":
            pieces.place_piece(state, "invalid", rc.BELGAE, rc.WARBAND)
        else:
            pieces.move_piece(state, rc.MORINI, "invalid", rc.BELGAE, rc.WARBAND)
    assert _snapshot(state) == before


@pytest.mark.parametrize("faction,piece", [
    (rc.ROMANS, rc.FORT), (rc.AEDUI, rc.CITADEL), (rc.GERMANS, rc.SETTLEMENT),
])
def test_move_cannot_exceed_static_piece_destination_limit(faction, piece):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(state, rc.MANDUBII, faction, piece)
    pieces.place_piece(state, rc.AEDUI_REGION, faction, piece)
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="Too many"):
        pieces.move_piece(state, rc.MANDUBII, rc.AEDUI_REGION, faction, piece)
    assert _snapshot(state) == before


def test_full_legion_track_does_not_silently_discard_returned_legions():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA)
    # Fault injection: an overfull inventory used to lose this map Legion
    # silently when the destination track could not accept it.
    state["spaces"][rc.PROVINCIA]["pieces"][rc.ROMANS] = {rc.LEGION: 1}
    before = _snapshot(state)
    with pytest.raises(pieces.PieceError, match="Not enough room"):
        pieces.remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_track=True)
    assert _snapshot(state) == before


def test_invalid_placement_does_not_reach_converted_force_selection(monkeypatch):
    from fs_bot.engine import diviciacus

    state = build_initial_state(rc.SCENARIO_ARIOVISTUS)
    before = _snapshot(state)

    def unexpected_selection(*args, **kwargs):
        pytest.fail("Invalid count reached Diviciacus placement choices")

    monkeypatch.setattr(diviciacus, "place_converted", unexpected_selection)
    with pytest.raises(pieces.PieceError, match="nonnegative integer"):
        pieces.place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, -1)
    assert _snapshot(state) == before
