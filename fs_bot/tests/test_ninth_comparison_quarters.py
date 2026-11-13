"""LC9-01: Roman Quarters pays for the troops left after relocation."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.rally import has_supply_line
from fs_bot.engine.quarters import quarters_factions
from fs_bot.engine.winter import quarters_phase
from fs_bot.state.serialize import load_game, save_game
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def position(scenario, funds):
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = set(quarters_factions(state))
    state['resources'][rc.ROMANS] = funds
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def devastate(state, region):
    state['markers'].setdefault(region, {})[rc.MARKER_DEVASTATED] = True


def block_supply(state, regions):
    for region in regions:
        place_piece(state, region, rc.BELGAE, rc.WARBAND)


def evacuation_position(scenario, origin, refuge, funds):
    state = position(scenario, funds)
    place_piece(state, origin, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, refuge, rc.ROMANS, rc.AUXILIA)
    devastate(state, origin)
    blockers = [rc.ATREBATES, rc.SUGAMBRI, rc.TREVERI]
    if scenario in rc.BASE_SCENARIOS:
        blockers.append(rc.BRITANNIA)
    block_supply(state, blockers)
    assert not has_supply_line(state, origin, rc.ROMANS)
    assert not has_supply_line(state, refuge, rc.ROMANS)
    check(state)
    return state


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_roman_quarters_pays_for_resident_and_arriving_auxilia(scenario, tmp_path):
    state = evacuation_position(scenario, rc.MORINI, rc.NERVII, funds=20)
    path = tmp_path / 'before-quarters.json'
    save_game(state, path)
    restored, _, _ = load_game(path, validate=True)
    rng = state['rng'].getstate()

    result = quarters_phase(state)
    assert result == quarters_phase(restored)
    assert result['roman_relocation'] == [(rc.AUXILIA, rc.MORINI, rc.NERVII, 2)]
    quartering = result['roman_quartering']
    assert quartering['payments'] == {rc.NERVII: {'count': 3, 'cost': 6}}
    assert quartering['rolls'] == {}
    assert state['resources'][rc.ROMANS] == restored['resources'][rc.ROMANS] == 14
    assert state['rng'].getstate() == restored['rng'].getstate() == rng
    for board in (state, restored):
        assert count_pieces(board, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0
        assert count_pieces_by_state(board, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
        assert count_pieces_by_state(board, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
        check(board)


@pytest.mark.parametrize('funds,paid,rolls', [(20, 3, []), (2, 1, [2, 5])])
def test_roman_quarters_reverse_relocation_respects_affordability(funds, paid, rolls):
    state = evacuation_position(rc.SCENARIO_RECONQUEST, rc.NERVII, rc.MORINI, funds)
    result = quarters_phase(state)
    assert result['roman_relocation'] == [(rc.AUXILIA, rc.NERVII, rc.MORINI, 2)]
    quartering = result['roman_quartering']
    assert quartering['payments'] == {rc.MORINI: {'count': paid, 'cost': 2 * paid}}
    assert quartering['rolls'].get(rc.MORINI, {}).get('rolls', []) == rolls
    assert state['resources'][rc.ROMANS] == funds - 2 * paid
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == (2 if rolls else 3)
    check(state)


@pytest.mark.parametrize('resident_legions,funds', [(0, 20), (1, 20), (0, 4)])
def test_roman_quarters_combines_two_arrivals_and_keeps_free_garrison(resident_legions, funds):
    state = position(rc.SCENARIO_RECONQUEST, funds)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.ROMANS)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    if resident_legions:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    for origin in (rc.MORINI, rc.ATREBATES):
        devastate(state, origin)
    block_supply(state, (rc.SUGAMBRI, rc.TREVERI, rc.CARNUTES, rc.MANDUBII, rc.VENETI))
    place_piece(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.BRITANNIA):
        assert not has_supply_line(state, region, rc.ROMANS)
    check(state)

    result = quarters_phase(state)

    assert result['roman_relocation'] == [
        (rc.AUXILIA, rc.MORINI, rc.NERVII, 2),
        (rc.LEGION, rc.ATREBATES, rc.NERVII, 1),
        (rc.AUXILIA, rc.ATREBATES, rc.NERVII, 1),
    ]
    quartering = result['roman_quartering']
    # Two Auxilia stay free at the Fort and Ally. The Ally Region is paid
    # first, even when the budget cannot also cover the troop in Britannia.
    paid = 4 + resident_legions
    britain_cost = 2 if funds > paid else 0
    assert quartering['payments'] == {
        rc.NERVII: {'count': paid, 'cost': paid},
        rc.BRITANNIA: {'count': britain_cost // 2, 'cost': britain_cost},
    }
    assert quartering['total_cost'] == paid + britain_cost
    assert set(quartering['rolls']) == (set() if britain_cost else {rc.BRITANNIA})
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.LEGION) == 1 + resident_legions
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    check(state)
