"""Independent A6.2 boundary regressions, derived from the supplied rules.

These use ordinary Phase helpers, not the provisional Event-command adapter.
Both expansion scenarios share A6.2 before the Gallic War Interlude.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.arverni_phase import (
    _arverni_phase_march,
    _arverni_phase_raid,
    _arverni_phase_rally,
    _warbands_available_for_raid,
    check_arverni_at_war,
)
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


@pytest.fixture(params=[rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
def board(request):
    state = build_initial_state(request.param, seed=17)
    state['resources'].update({rc.ROMANS: 10, rc.AEDUI: 10, rc.GERMANS: 10})
    yield state
    assert validate_state(state) == []


def test_city_upgrade_requires_an_ally_but_not_control_and_excludes_warbands(board):
    """3.3.1 permits the upgrade without Control; A6.2.1 allows one category."""
    _ally_tribe(board, rc.TRIBE_ARVERNI, rc.ARVERNI)
    place_piece(board, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 3)
    assert calculate_control(board, rc.ARVERNI_REGION) == rc.ROMAN_CONTROL

    result = _arverni_phase_rally(board, [rc.ARVERNI_REGION])

    assert result['citadels_placed'] == [(rc.ARVERNI_REGION, rc.TRIBE_ARVERNI)]
    assert result['warbands_placed'] == {}
    assert count_pieces(board, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(board, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 0


def test_controlled_suebi_region_cannot_gain_a_non_german_suebi_ally(board):
    """1.4.2/3.3.1 reserve Suebi Tribes for Germans, even when At War."""
    _ally_tribe(board, rc.TRIBE_UBII, rc.ARVERNI)
    place_piece(board, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(board, rc.UBII, rc.ROMANS, rc.AUXILIA)
    assert check_arverni_at_war(board) == (True, [rc.UBII])

    result = _arverni_phase_rally(board, [rc.UBII])

    assert result['allies_placed'] == []
    assert board['tribes'][rc.TRIBE_SUEBI_SOUTH]['allied_faction'] is None
    assert result['warbands_placed'] == {rc.UBII: 2}


def test_secondary_destination_can_lose_control_to_two_combined_groups(board):
    """A6.2.2 assesses combined remaining groups; a tie removes Control."""
    place_piece(board, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(board, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(board, rc.TREVERI, rc.AEDUI, rc.WARBAND, 4)

    result = _arverni_phase_march(board, rc.VENETI)

    assert len(result['marches']) == 2
    assert {entry['to'] for entry in result['marches']} == {rc.TREVERI}
    assert count_pieces(board, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 4
    assert calculate_control(board, rc.TREVERI) == rc.NO_CONTROL
    for origin in (rc.UBII, rc.SEQUANI):
        assert count_pieces(board, origin, rc.ARVERNI, rc.WARBAND) == 1
        assert calculate_control(board, origin) == rc.ARVERNI_CONTROL


def test_secondary_destination_ignores_unremovable_aedui_control(board):
    """Aedui's priority applies only to destinations that can lose Control."""
    place_piece(board, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(board, rc.TREVERI, rc.AEDUI, rc.WARBAND, 5)
    place_piece(board, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 2)

    result = _arverni_phase_march(board, rc.VENETI)

    assert result['marches'] == [{'from': rc.UBII, 'to': rc.SUGAMBRI, 'warbands': 2}]
    assert calculate_control(board, rc.SUGAMBRI) == rc.NO_CONTROL
    assert calculate_control(board, rc.TREVERI) == rc.AEDUI_CONTROL


def test_march_surplus_counts_immobile_ally_and_enemy_pieces(board):
    """A6.2.2 leaves enough total Forces for Control, moving only Warbands."""
    _ally_tribe(board, rc.TRIBE_UBII, rc.ARVERNI)
    place_piece(board, rc.UBII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(board, rc.TREVERI, rc.AEDUI, rc.WARBAND, 2)

    result = _arverni_phase_march(board, rc.VENETI)

    assert result['marches'] == [{'from': rc.UBII, 'to': rc.TREVERI, 'warbands': 2}]
    assert count_pieces(board, rc.UBII, rc.ARVERNI, rc.ALLY) == 1
    assert count_pieces(board, rc.UBII, rc.ARVERNI, rc.WARBAND) == 2
    assert calculate_control(board, rc.UBII) == rc.ARVERNI_CONTROL


def test_frost_skips_hiding_as_well_as_movement(board):
    """A6.2.2 skips the entire March step at Frost, including in-place hiding."""
    place_piece(board, rc.UBII, rc.ARVERNI, rc.WARBAND, 3,
                piece_state=rc.SCOUTED)
    before = deepcopy(board['spaces'])

    result = _arverni_phase_march(board, rc.VENETI, is_frost=True)

    assert result['skipped_frost'] and result['marches'] == []
    assert board['spaces'] == before


def test_raid_in_devastated_region_steals_only_until_target_zero(board):
    """3.3.3 permits stealing while Devastated; A6.2.3 stops at zero."""
    board.setdefault('markers', {}).setdefault(rc.CARNUTES, {})[rc.MARKER_DEVASTATED] = True
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.REVEALED)
    board['resources'][rc.ROMANS] = 1
    untracked_before = board['resources'].get(rc.ARVERNI)

    result = _arverni_phase_raid(board, rc.ROMANS)

    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 1}]
    assert board['resources'][rc.ROMANS] == 0
    # A1.5.2/A1.8: these Resources are removed, never credited to Arverni.
    assert board['resources'].get(rc.ARVERNI) == untracked_before
    assert count_pieces_by_state(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 5


def test_raid_reserves_for_one_legal_enemy_not_all_enemies(board):
    """A6.2.3 requires enough Hidden pieces to Ambush an enemy, not every enemy."""
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND,
                piece_state=rc.REVEALED)

    result = _arverni_phase_raid(board, rc.ROMANS)

    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 2}]
    assert count_pieces_by_state(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1
    assert board['resources'][rc.ROMANS] == 8


@pytest.mark.parametrize('leader_region,used', [(rc.CARNUTES, 1), (rc.UBII, 2)])
def test_raid_reserves_for_diviciacus_only_within_his_range_without_consent(board, leader_region, used):
    """A1.4/A6.2.3 cover possible combined defense within one Region of Leader."""
    place_piece(board, leader_region, rc.AEDUI, rc.LEADER,
                leader_name=rc.DIVICIACUS)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    seen = []
    board['decision_agent'] = lambda *args: seen.append(args) or False

    result = _arverni_phase_raid(board, rc.ROMANS)

    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': used}]
    assert count_pieces_by_state(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 4 - used
    assert board['resources'][rc.ROMANS] == 10 - used
    assert not seen
    assert '_diviciacus_force' not in board


def test_raid_may_use_last_hidden_warband_if_no_ambush_can_cause_losses(board):
    """A6.2.3 does not reserve merely for superiority when damage rounds to zero."""
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.REVEALED)

    result = _arverni_phase_raid(board, rc.ROMANS)

    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 1}]
    assert count_pieces_by_state(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0


def test_diviciacus_reserve_is_read_only_for_physical_board_and_rng(board):
    """A hypothetical agreement changes neither ownership, visibility nor RNG."""
    place_piece(board, rc.CARNUTES, rc.AEDUI, rc.LEADER,
                leader_name=rc.DIVICIACUS)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    before = encode(board)

    assert _warbands_available_for_raid(board, rc.CARNUTES) == 1

    assert encode(board) == before
