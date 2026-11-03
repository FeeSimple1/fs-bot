"""Source regressions for ordinary A6.2 Rally, March and Raid.

These exercise the full Phase helpers in both expansion scenarios; Event
Command policy and the base game's Arverni flowchart are separate callers.
"""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.engine.arverni_phase import (
    _arverni_phase_march, _arverni_phase_raid, _arverni_phase_rally,
    _warbands_available_for_raid,
)
from fs_bot.state.state_schema import build_initial_state


@pytest.fixture(params=[rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
def state(request):
    game = build_initial_state(request.param, seed=12)
    game['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    return game


def test_rally_places_no_warbands_after_ally(state):
    """A6.2.1: Warbands only in Regions where no Ally/Citadel placed."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    result = _arverni_phase_rally(state, [rc.CARNUTES])
    assert len(result['allies_placed']) == 1
    assert result['warbands_placed'] == {}
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 3


def test_rally_places_no_warbands_after_citadel(state):
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    result = _arverni_phase_rally(state, [rc.ARVERNI_REGION])
    assert result['citadels_placed'] == [(rc.ARVERNI_REGION, rc.TRIBE_ARVERNI)]
    assert result['warbands_placed'] == {}
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1


def test_rally_without_control_uses_only_home_warband(state):
    """3.3.1 permits a Home Warband, but no Ally without own Control."""
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    result = _arverni_phase_rally(state, [rc.CARNUTES])
    assert result['allies_placed'] == []
    assert result['warbands_placed'] == {rc.CARNUTES: 1}


@pytest.mark.parametrize('region,protected,existing', [
    (rc.UBII, rc.TRIBE_SUEBI_SOUTH, rc.TRIBE_UBII),
])
def test_rally_respects_tribe_restrictions(state, region, protected, existing):
    """3.3.1/1.4.2: Aedui and Suebi cannot take an Arverni Ally."""
    place_piece(state, region, rc.ARVERNI, rc.ALLY)
    state['tribes'][existing]['allied_faction'] = rc.ARVERNI
    place_piece(state, region, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    result = _arverni_phase_rally(state, [region])
    assert result['allies_placed'] == []
    assert state['tribes'][protected]['allied_faction'] is None
    assert result['warbands_placed'] == {region: 2}


def test_secondary_march_does_not_enter_if_control_survives(state):
    """A6.2.2 requires removal of Control, not merely an enemy destination."""
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 10)
    result = _arverni_phase_march(state, rc.VENETI)
    assert result['marches'] == []
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 2
    assert calculate_control(state, rc.AEDUI_REGION) == rc.AEDUI_CONTROL


def test_secondary_march_combines_groups_and_tie_removes_control(state):
    place_piece(state, rc.UBII, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 4)
    result = _arverni_phase_march(state, rc.VENETI)
    assert {m['from'] for m in result['marches']} == {rc.UBII, rc.SEQUANI}
    assert {m['to'] for m in result['marches']} == {rc.TREVERI}
    assert count_pieces(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 4
    assert calculate_control(state, rc.TREVERI) == rc.NO_CONTROL
    assert calculate_control(state, rc.UBII) == rc.ARVERNI_CONTROL
    assert calculate_control(state, rc.SEQUANI) == rc.ARVERNI_CONTROL


def test_raid_uses_at_most_two_warbands_per_region(state):
    """A6.2.3 incorporates 3.3.3's one or two Warbands per Region."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    state['resources'][rc.ROMANS] = 10
    result = _arverni_phase_raid(state, rc.ROMANS)
    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 2}]
    assert state['resources'][rc.ROMANS] == 8
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 4


def test_raid_does_not_award_resources_to_arverni(state):
    """A1.5.2: Arverni never receive Resources, including those stolen."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    state['resources'][rc.ROMANS] = 10
    before = state['resources'].get(rc.ARVERNI)
    result = _arverni_phase_raid(state, rc.ROMANS)
    assert result['total_stolen'] == {rc.ROMANS: 1}
    assert state['resources'].get(rc.ARVERNI) == before


def test_raid_reserves_nothing_for_impossible_hidden_superiority(state):
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    state['resources'][rc.ROMANS] = 10
    result = _arverni_phase_raid(state, rc.ROMANS)
    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 1}]
    assert state['resources'][rc.ROMANS] == 9


def test_raid_preserves_an_ambush_not_every_possible_ambush(state):
    """A6.2.3 says enough other Hidden Warbands to Ambush an enemy."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    assert _warbands_available_for_raid(state, rc.CARNUTES) == 2


def test_raid_reserves_nothing_when_ambush_cannot_cause_loss(state):
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    # One Warband causes floor(1/2) = zero Losses, despite Hidden superiority.
    assert _warbands_available_for_raid(state, rc.CARNUTES) == 1


@pytest.mark.parametrize('leader_region,expected', [(rc.CARNUTES, 0), (rc.UBII, 1)])
def test_raid_accounts_for_eligible_diviciacus_without_asking(state, leader_region, expected):
    """A6.2.3: preserve an Ambush even if eligible Romans/Aedui combine."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, leader_region, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    state['non_player_factions'] = set()
    def reject_prompt(*args, **kwargs):
        pytest.fail('A6.2.3 reserve must not solicit a future agreement')
    state['decision_agent'] = reject_prompt
    before_rng = state['rng'].getstate()
    assert _warbands_available_for_raid(state, rc.CARNUTES) == expected
    assert state['rng'].getstate() == before_rng
    assert '_diviciacus_force' not in state


def test_raid_region_cap_spans_targets_in_target_then_player_order(state):
    """A6.2.3 priority and target depletion do not restart 3.3.3's cap."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    for faction in (rc.AEDUI, rc.GERMANS):
        place_piece(state, rc.CARNUTES, faction, rc.WARBAND, piece_state=rc.REVEALED)
    state['resources'].update({rc.ROMANS: 1, rc.AEDUI: 1, rc.GERMANS: 10})
    state['non_player_factions'] = {rc.ROMANS, rc.GERMANS}
    result = _arverni_phase_raid(state, rc.ROMANS)
    assert result['total_stolen'] == {rc.ROMANS: 1, rc.AEDUI: 1}
    assert result['raids'] == [{'region': rc.CARNUTES, 'warbands_used': 2}]
    assert state['resources'][rc.ROMANS] == state['resources'][rc.AEDUI] == 0
    assert state['resources'][rc.GERMANS] == 10


@pytest.mark.parametrize('target,fortification', [(rc.ROMANS, rc.FORT), (rc.AEDUI, rc.CITADEL)])
def test_raid_skips_fortified_target_and_uses_other_enemy(state, target, fortification):
    """A6.2.3 restricts theft to enemies without a Fort or Citadel."""
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
    if fortification == rc.CITADEL:
        # Carnutes is a City, so the fortified target is a legal board state.
        place_piece(state, rc.CARNUTES, target, rc.CITADEL)
        state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = target
    else:
        place_piece(state, rc.CARNUTES, target, fortification)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    state['resources'].update({target: 10, rc.BELGAE: 10})
    result = _arverni_phase_raid(state, target)
    assert result['total_stolen'] == {rc.BELGAE: 2}
    assert state['resources'][target] == 10
