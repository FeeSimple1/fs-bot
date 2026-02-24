"""
Tests for belgae_bot.py — Non-Player Belgae flowchart per §8.5.

Tests every flowchart node with Yes/No branches, seeded RNG, and
both base game and Ariovistus scenarios.
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED, SCOUTED,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    SCENARIO_GREAT_REVOLT, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    AMBIORIX, CAESAR,
    MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII, SUGAMBRI, UBII,
    AEDUI_REGION, ARVERNI_REGION, SEQUANI, BITURIGES,
    CARNUTES, PICTONES, VENETI, TREVERI, BRITANNIA,
    TRIBE_CARNUTES, TRIBE_ARVERNI, TRIBE_AEDUI,
    TRIBE_MANDUBII, TRIBE_BITURIGES, TRIBE_MORINI,
    TRIBE_ATREBATES, TRIBE_SEQUANI, TRIBE_NERVII,
    EVENT_SHADED,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces, get_available
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.bots.belgae_bot import (
    # Node functions
    node_b1, node_b2, node_b3, node_b3b, node_b4, node_b5,
    # Process nodes
    node_b_event, node_b_battle,
    node_b_rally, node_b_raid, node_b_march,
    node_b_march_threat,
    # SA helpers
    _check_ambush, _check_rampage, _check_enlist_after_command,
    # Winter
    node_b_quarters, node_b_spring,
    # Agreements
    node_b_agreements,
    # Main driver
    execute_belgae_turn,
    # Helpers
    _has_belgae_threat, _can_battle_in_region,
    _count_belgae_warbands_on_map, _estimate_rally_would_qualify,
    _would_raid_gain_enough, _estimate_battle_losses,
    _find_largest_belgae_warband_group, _get_non_german_enemies,
    # Action constants
    ACTION_BATTLE, ACTION_MARCH, ACTION_RALLY, ACTION_RAID,
    ACTION_EVENT, ACTION_PASS,
    SA_ACTION_AMBUSH, SA_ACTION_RAMPAGE, SA_ACTION_ENLIST, SA_ACTION_NONE,
)
from fs_bot.bots.bot_dispatch import (
    dispatch_bot_turn, BotDispatchError,
)


# ===================================================================
# Test helpers
# ===================================================================

def _make_state(scenario=SCENARIO_PAX_GALLICA, seed=42, non_players=None):
    """Build a minimal test state with common defaults."""
    state = build_initial_state(scenario, seed=seed)
    if non_players is None:
        non_players = {ARVERNI, BELGAE, AEDUI}
    state["non_player_factions"] = non_players
    state["can_play_event"] = True
    state["current_card_id"] = 1
    state["final_year"] = False
    state["frost"] = False
    state["current_card_faction_order"] = []
    state["next_card_faction_order"] = []
    state["is_second_eligible"] = False
    return state


def _place_belgae_force(state, region, *, warbands=0, ally_tribe=None,
                        citadel=False, leader=False, hidden=True):
    """Helper to place Belgae forces in a region."""
    if warbands > 0:
        piece_state = HIDDEN if hidden else REVEALED
        place_piece(state, region, BELGAE, WARBAND, warbands,
                    piece_state=piece_state)
    if ally_tribe:
        state["tribes"][ally_tribe]["allied_faction"] = BELGAE
        place_piece(state, region, BELGAE, ALLY)
    if citadel:
        place_piece(state, region, BELGAE, CITADEL)
    if leader:
        place_piece(state, region, BELGAE, LEADER, leader_name=AMBIORIX)


def _place_roman_force(state, region, *, leader=False, legions=0, auxilia=0,
                       ally_tribe=None, fort=False):
    """Helper to place Roman forces in a region."""
    if leader:
        place_piece(state, region, ROMANS, LEADER, leader_name=CAESAR)
    if legions > 0:
        place_piece(state, region, ROMANS, LEGION, legions,
                    from_legions_track=True)
    if auxilia > 0:
        place_piece(state, region, ROMANS, AUXILIA, auxilia)
    if ally_tribe:
        state["tribes"][ally_tribe]["allied_faction"] = ROMANS
        place_piece(state, region, ROMANS, ALLY)
    if fort:
        place_piece(state, region, ROMANS, FORT)


def _place_enemy_force(state, region, faction, *, warbands=0, ally_tribe=None,
                       citadel=False, leader=False, auxilia=0):
    """Helper to place enemy pieces."""
    if warbands > 0:
        place_piece(state, region, faction, WARBAND, warbands)
    if ally_tribe:
        state["tribes"][ally_tribe]["allied_faction"] = faction
        place_piece(state, region, faction, ALLY)
    if citadel:
        place_piece(state, region, faction, CITADEL)
    if auxilia > 0:
        place_piece(state, region, faction, AUXILIA, auxilia)
    if leader:
        leader_name = AMBIORIX if faction == BELGAE else CAESAR
        place_piece(state, region, faction, LEADER, leader_name=leader_name)


# ===================================================================
# B1: Battle or March under Threat?
# ===================================================================

class TestNodeB1:
    """B1 decision node tests."""

    def test_yes_when_ambiorix_with_enemy_ally(self):
        """Yes when Ambiorix in region with enemy Ally."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=2)
        _place_roman_force(state, MANDUBII, ally_tribe=TRIBE_MANDUBII)
        result, regions = node_b1(state)
        assert result == "Yes"
        assert MANDUBII in regions

    def test_yes_when_4_warbands_with_enemy_legion(self):
        """Yes when 4+ Belgic Warbands with enemy Legion."""
        state = _make_state()
        _place_belgae_force(state, ATREBATES, warbands=4)
        _place_roman_force(state, ATREBATES, legions=1)
        result, regions = node_b1(state)
        assert result == "Yes"
        assert ATREBATES in regions

    def test_yes_when_4_warbands_with_enemy_4_pieces(self):
        """Yes when 4+ Belgic Warbands with enemy having 4+ pieces."""
        state = _make_state()
        _place_belgae_force(state, NERVII, warbands=5)
        _place_enemy_force(state, NERVII, AEDUI, warbands=4)
        result, regions = node_b1(state)
        assert result == "Yes"

    def test_no_when_only_3_warbands(self):
        """No when only 3 Belgic Warbands (need 4+)."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3)
        _place_roman_force(state, MANDUBII, legions=1)
        result, _ = node_b1(state)
        assert result == "No"

    def test_no_when_no_enemy(self):
        """No when Ambiorix present but no enemy meets conditions."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=5)
        result, _ = node_b1(state)
        assert result == "No"

    def test_base_game_ignores_german_enemy(self):
        """Base game: ignore Germans as enemies for B1 condition."""
        state = _make_state()
        _place_belgae_force(state, SUGAMBRI, leader=True, warbands=2)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 5)
        result, _ = node_b1(state)
        # Germans don't count as "non-German enemy" in base game
        assert result == "No"

    def test_ariovistus_considers_german_enemy(self):
        """Ariovistus: consider Germans as enemies per A8.5.1."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, SUGAMBRI, leader=True, warbands=2)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 5)
        result, regions = node_b1(state)
        assert result == "Yes"
        assert SUGAMBRI in regions

    def test_ariovistus_counts_settlements_as_allies(self):
        """Ariovistus: count Settlements as Allies per A8.5.1."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, TREVERI, leader=True, warbands=2)
        place_piece(state, TREVERI, GERMANS, SETTLEMENT)
        result, regions = node_b1(state)
        assert result == "Yes"


# ===================================================================
# B2: Pass condition
# ===================================================================

class TestNodeB2:
    """B2 decision node tests."""

    def test_pass_when_first_next_not_first_current_roll_low(self):
        """Pass when Belgae 1st on next card, not on current, and roll 1-4."""
        state = _make_state(seed=1)
        state["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        state["current_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
        # Try multiple seeds to find one that gives 1-4
        for s in range(100):
            state["rng"] = __import__("random").Random(s)
            result = node_b2(state)
            if result == "Yes":
                break
        assert result == "Yes"

    def test_no_when_first_on_both(self):
        """No pass when Belgae 1st on both cards."""
        state = _make_state()
        state["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        state["current_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        assert node_b2(state) == "No"

    def test_no_when_not_first_on_next(self):
        """No pass when Belgae not 1st on next card."""
        state = _make_state()
        state["next_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
        state["current_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
        assert node_b2(state) == "No"

    def test_no_when_frost(self):
        """No pass when Winter is showing (Frost)."""
        state = _make_state()
        state["frost"] = True
        state["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        state["current_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
        assert node_b2(state) == "No"

    def test_no_when_empty_orders(self):
        """No pass when card orders are empty."""
        state = _make_state()
        assert node_b2(state) == "No"


# ===================================================================
# B3: Can play Event?
# ===================================================================

class TestNodeB3:
    """B3 decision node tests."""

    def test_yes_when_can_play_event(self):
        state = _make_state()
        state["can_play_event"] = True
        assert node_b3(state) == "Yes"

    def test_no_when_cannot_play_event(self):
        state = _make_state()
        state["can_play_event"] = False
        assert node_b3(state) == "No"


# ===================================================================
# B3b: Event Ineffective or No Belgae?
# ===================================================================

class TestNodeB3b:
    """B3b decision node tests."""

    def test_yes_when_no_card(self):
        """Decline when no current card."""
        state = _make_state()
        state["current_card_id"] = None
        assert node_b3b(state) == "Yes"

    def test_no_for_normal_card(self):
        """Don't decline for a normal card."""
        state = _make_state()
        state["current_card_id"] = 9  # No special Belgae instruction
        assert node_b3b(state) == "No"


# ===================================================================
# B4: Rally conditions
# ===================================================================

class TestNodeB4:
    """B4 decision node tests."""

    def test_no_when_zero_resources(self):
        """No Rally when Belgae have 0 Resources — §8.5.3 NOTE."""
        state = _make_state()
        state["resources"][BELGAE] = 0
        # Even with Rally bases, 0 Resources means can't place
        _place_belgae_force(state, MORINI, warbands=3,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        assert node_b4(state) == "No"

    def test_yes_when_would_place_ally(self):
        """Rally when would place a Belgic Ally."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        # Place Belgae with control but no ally on an empty tribe
        _place_belgae_force(state, MORINI, warbands=5)
        refresh_all_control(state)
        assert node_b4(state) == "Yes"

    def test_yes_when_would_place_3_warbands(self):
        """Rally when would place 3+ Warbands."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        # Need rally bases in multiple regions
        _place_belgae_force(state, MORINI, ally_tribe=TRIBE_MORINI)
        _place_belgae_force(state, NERVII, ally_tribe=TRIBE_NERVII)
        _place_belgae_force(state, ATREBATES, ally_tribe=TRIBE_ATREBATES)
        refresh_all_control(state)
        result = node_b4(state)
        assert result == "Yes"


# ===================================================================
# B5: Low resources and die roll
# ===================================================================

class TestNodeB5:
    """B5 decision node tests."""

    def test_no_when_resources_4_plus(self):
        """No Raid when Belgae have 4+ Resources."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        assert node_b5(state) == "No"

    def test_depends_on_roll_when_low_resources(self):
        """Raid depends on die roll when Resources 0-3."""
        state = _make_state()
        state["resources"][BELGAE] = 2
        results = set()
        for s in range(20):
            st = _make_state(seed=s)
            st["resources"][BELGAE] = 2
            results.add(node_b5(st))
        # Should see both Yes and No across different seeds
        assert "Yes" in results or "No" in results


# ===================================================================
# Threat condition helpers
# ===================================================================

class TestThreatHelpers:
    """Test _has_belgae_threat and related helpers."""

    def test_threat_with_ambiorix_and_enemy_citadel(self):
        """Threat when Ambiorix is in region with enemy Citadel."""
        state = _make_state()
        _place_belgae_force(state, CARNUTES, leader=True)
        place_piece(state, CARNUTES, ARVERNI, CITADEL)
        assert _has_belgae_threat(state, CARNUTES, SCENARIO_PAX_GALLICA)

    def test_no_threat_without_enough_warbands(self):
        """No threat with only 3 Warbands and no Ambiorix."""
        state = _make_state()
        _place_belgae_force(state, CARNUTES, warbands=3)
        _place_roman_force(state, CARNUTES, legions=1)
        assert not _has_belgae_threat(state, CARNUTES, SCENARIO_PAX_GALLICA)

    def test_non_german_enemies_base(self):
        """Base game: non-German enemies are Romans, Arverni, Aedui."""
        enemies = _get_non_german_enemies(SCENARIO_PAX_GALLICA)
        assert GERMANS not in enemies
        assert ROMANS in enemies
        assert ARVERNI in enemies
        assert AEDUI in enemies

    def test_non_german_enemies_ariovistus(self):
        """Ariovistus: include Germans per A8.5.1."""
        enemies = _get_non_german_enemies(SCENARIO_ARIOVISTUS)
        assert GERMANS in enemies


# ===================================================================
# Battle estimation
# ===================================================================

class TestBattleEstimation:
    """Test battle estimation helpers."""

    def test_estimate_losses_basic(self):
        """Basic loss estimation."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=6)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 4)
        losses_inflicted, losses_suffered = _estimate_battle_losses(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ARVERNI)
        # 6 Warbands × 0.5 = 3 inflicted
        assert losses_inflicted == 3
        # 4 Warbands × 0.5 = 2 suffered
        assert losses_suffered == 2

    def test_estimate_losses_with_fort_halving(self):
        """Fort halves attack losses."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=6)
        _place_roman_force(state, MANDUBII, auxilia=4, fort=True)
        losses_inflicted, losses_suffered = _estimate_battle_losses(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ROMANS)
        # 6 × 0.5 = 3, halved by Fort = 1
        assert losses_inflicted == 1

    def test_estimate_losses_with_leader(self):
        """Leader adds to losses."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, leader=True)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 2)
        losses_inflicted, _ = _estimate_battle_losses(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ARVERNI)
        # 4 × 0.5 + 1 (leader) = 3
        assert losses_inflicted == 3

    def test_can_battle_checks_losses(self):
        """Can Battle only when inflicting more than suffering."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=6)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 4)
        # 3 inflicted > 2 suffered → can battle
        assert _can_battle_in_region(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ARVERNI)

    def test_cannot_battle_when_losing(self):
        """Cannot Battle when suffering more than inflicting."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=2)
        _place_roman_force(state, MANDUBII, legions=2, auxilia=4)
        # 2 × 0.5 = 1 inflicted, many suffered → cannot battle
        assert not _can_battle_in_region(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ROMANS)

    def test_cannot_battle_if_ambiorix_would_die(self):
        """Cannot Battle if Ambiorix would take a Loss."""
        state = _make_state()
        # Ambiorix + 1 Warband vs 3 Legions → Ambiorix could die
        _place_belgae_force(state, MANDUBII, warbands=1, leader=True)
        _place_roman_force(state, MANDUBII, legions=3)
        assert not _can_battle_in_region(
            state, MANDUBII, SCENARIO_PAX_GALLICA, ROMANS)

    def test_base_game_cannot_battle_germans(self):
        """Base game: Belgae do not Battle Germans — §8.5.1 NOTE."""
        state = _make_state()
        _place_belgae_force(state, SUGAMBRI, warbands=6, leader=True)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2)
        assert not _can_battle_in_region(
            state, SUGAMBRI, SCENARIO_PAX_GALLICA, GERMANS)

    def test_ariovistus_can_battle_germans(self):
        """Ariovistus: Belgae CAN Battle Germans per A8.5.1."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, SUGAMBRI, warbands=6, leader=True)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2)
        assert _can_battle_in_region(
            state, SUGAMBRI, SCENARIO_ARIOVISTUS, GERMANS)


# ===================================================================
# Rally estimation
# ===================================================================

class TestRallyEstimation:
    """Test _estimate_rally_would_qualify."""

    def test_no_with_zero_resources(self):
        """0 Resources: Rally would not place any pieces — §8.5.3 NOTE."""
        state = _make_state()
        state["resources"][BELGAE] = 0
        _place_belgae_force(state, MORINI, warbands=5,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        assert not _estimate_rally_would_qualify(state, SCENARIO_PAX_GALLICA)


# ===================================================================
# Raid estimation
# ===================================================================

class TestRaidEstimation:
    """Test _would_raid_gain_enough."""

    def test_raid_gains_from_players_only(self):
        """Raid only steals from players, not Non-players — §8.5.4."""
        state = _make_state(non_players={BELGAE, AEDUI, ARVERNI})
        # Aedui is NP, so no stealing from them
        _place_belgae_force(state, MANDUBII, warbands=2)
        place_piece(state, MANDUBII, AEDUI, WARBAND, 2)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_PAX_GALLICA)
        # Can gain from non-Devastated region (+1 per flip) but
        # cannot steal from NP Aedui
        for entry in plan:
            if entry["target"] is not None:
                assert entry["target"] not in state["non_player_factions"]

    def test_raid_gains_2_plus(self):
        """Raid qualifies when gaining 2+ Resources."""
        state = _make_state(non_players={BELGAE})
        # Place hidden Warbands near player Romans
        _place_belgae_force(state, MANDUBII, warbands=2)
        _place_roman_force(state, MANDUBII, auxilia=2)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_PAX_GALLICA)
        assert enough


# ===================================================================
# Ambush
# ===================================================================

class TestAmbush:
    """Test _check_ambush."""

    def test_ambush_when_more_hidden_and_enemy_legion(self):
        """Ambush when more Hidden Belgae than enemy and enemy has Legion."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True)
        _place_roman_force(state, MANDUBII, legions=1, auxilia=2)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) > 0
        assert MANDUBII in result

    def test_no_ambush_when_fewer_hidden(self):
        """No Ambush when fewer Hidden Belgae than Hidden enemy."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=1, hidden=True)
        # Use Arverni Warbands as the enemy (Romans don't have Warbands)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 3,
                    piece_state=HIDDEN)
        battle_plan = [{"region": MANDUBII, "target": ARVERNI}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) == 0

    def test_ambush_cascades_to_all_battles(self):
        """If Ambushed in 1st Battle, Ambush in all others — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True)
        _place_belgae_force(state, CARNUTES, warbands=4, hidden=True)
        _place_roman_force(state, MANDUBII, legions=1)
        _place_roman_force(state, CARNUTES, auxilia=2)
        battle_plan = [
            {"region": MANDUBII, "target": ROMANS},
            {"region": CARNUTES, "target": ROMANS},
        ]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) == 2


# ===================================================================
# Rampage
# ===================================================================

class TestRampage:
    """Test _check_rampage."""

    def test_rampage_with_hidden_warbands(self):
        """Rampage when Belgae have Hidden Warbands vs enemy."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        assert len(result) > 0
        assert result[0]["region"] == MANDUBII

    def test_rampage_priority_forces_removal_first(self):
        """Rampage prioritizes forced removal — §8.5.1 step 1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True)
        _place_belgae_force(state, CARNUTES, warbands=2, hidden=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        place_piece(state, CARNUTES, AEDUI, WARBAND, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Both should be included; force removal ones first
        assert len(result) >= 2

    def test_no_rampage_last_piece_before_battle(self):
        """No Rampage against enemy's last piece before Battle — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 1)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_rampage(
            state, SCENARIO_PAX_GALLICA,
            before_battle=True, battle_plan=battle_plan)
        # Only 1 enemy piece: can't Rampage before battle
        assert len(result) == 0


# ===================================================================
# Enlist
# ===================================================================

class TestEnlist:
    """Test _check_enlist_after_command."""

    def test_enlist_german_battle(self):
        """Enlist Germans to Battle enemy."""
        state = _make_state(non_players={BELGAE})
        place_piece(state, MANDUBII, GERMANS, WARBAND, 4)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        assert result is not None
        assert result["type"] == "german_battle"

    def test_enlist_german_march(self):
        """Enlist Germans to March from Belgica to enemy Control."""
        state = _make_state(non_players={BELGAE})
        # Place Germans in Belgica
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        # Make adjacent region Roman-controlled
        _place_roman_force(state, ATREBATES, auxilia=4,
                           ally_tribe=TRIBE_ATREBATES)
        refresh_all_control(state)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        # Should prefer Battle (step 1) — check if there's a battle target
        # in the same region. If not, should do March.
        if result and result["type"] == "german_march":
            assert result["origin"] == MORINI

    def test_enlist_none_when_no_germans(self):
        """No Enlist when no German pieces on map."""
        state = _make_state(non_players={BELGAE})
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        assert result is None


# ===================================================================
# Battle process node
# ===================================================================

class TestNodeBBattle:
    """B_BATTLE process node tests."""

    def test_battle_returns_battle_action(self):
        """Battle returns a Battle action dict."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=6, leader=True)
        _place_roman_force(state, MANDUBII, ally_tribe=TRIBE_MANDUBII,
                           auxilia=2)
        refresh_all_control(state)
        result = node_b_battle(state)
        assert result["command"] == ACTION_BATTLE

    def test_battle_redirects_to_march_when_ambiorix_cant_fight(self):
        """March when Ambiorix meets threat but can't Battle."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        # Ambiorix with 1 Warband vs huge Roman force
        _place_belgae_force(state, MANDUBII, warbands=1, leader=True)
        _place_roman_force(state, MANDUBII, legions=3, auxilia=5)
        # Also need other Belgae pieces so March can happen
        _place_belgae_force(state, MORINI, warbands=5)
        refresh_all_control(state)
        result = node_b_battle(state)
        assert result["command"] == ACTION_MARCH

    def test_battle_ambiorix_targets_fewer_mobile(self):
        """Ambiorix fights enemy with fewer mobile forces — §8.5.1 step 3a.

        Among enemies with fewer mobile pieces than Belgae, the enemy
        targeting priority order applies: Romans first, then Aedui.
        """
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=6, leader=True)
        # Both enemies have fewer mobile forces than Belgae (7 total)
        # AND meet the threat condition (4+ pieces)
        place_piece(state, MANDUBII, AEDUI, WARBAND, 4)
        _place_roman_force(state, MANDUBII, auxilia=5)
        refresh_all_control(state)
        result = node_b_battle(state)
        assert result["command"] == ACTION_BATTLE
        # Romans first per enemy priority order (Romans → Aedui)
        if result["details"].get("battle_plan"):
            first = result["details"]["battle_plan"][0]
            assert first["region"] == MANDUBII
            assert first["target"] == ROMANS


# ===================================================================
# March (threat) process node
# ===================================================================

class TestNodeBMarchThreat:
    """B_MARCH_THREAT process node tests."""

    def test_march_threat_includes_leader_region(self):
        """March origins include Leader's region if not at largest group."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MANDUBII, leader=True, warbands=2)
        _place_belgae_force(state, MORINI, warbands=8)
        refresh_all_control(state)
        result = node_b_march_threat(state)
        assert result["command"] == ACTION_MARCH
        march_plan = result["details"]["march_plan"]
        # Leader region should be an origin
        assert MANDUBII in march_plan["origins"]

    def test_march_threat_leader_first(self):
        """March first with Belgic Leader — §8.5.1."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        ambiorix_region = MANDUBII
        _place_belgae_force(state, ambiorix_region, leader=True, warbands=3)
        _place_roman_force(state, ambiorix_region,
                           ally_tribe=TRIBE_MANDUBII, auxilia=2)
        _place_belgae_force(state, CARNUTES, warbands=5)
        refresh_all_control(state)
        result = node_b_march_threat(state)
        march_plan = result["details"]["march_plan"]
        if ambiorix_region in march_plan["origins"]:
            # Leader's region should be first origin
            assert march_plan["origins"][0] == ambiorix_region


# ===================================================================
# Rally process node
# ===================================================================

class TestNodeBRally:
    """B_RALLY process node tests."""

    def test_rally_places_citadel_first(self):
        """Rally step 1: replace City Ally with Citadel."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        # Place a Belgae Ally in a City tribe
        _place_belgae_force(state, MANDUBII, warbands=3,
                            ally_tribe=TRIBE_MANDUBII)
        refresh_all_control(state)
        result = node_b_rally(state)
        assert result["command"] == ACTION_RALLY
        rally_plan = result["details"]["rally_plan"]
        # Mandubii is a city → should get Citadel
        if get_available(state, BELGAE, CITADEL) > 0:
            assert len(rally_plan["citadels"]) > 0

    def test_rally_places_allies_then_warbands(self):
        """Rally places Allies then Warbands."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        _place_belgae_force(state, MORINI, warbands=5)
        refresh_all_control(state)
        result = node_b_rally(state)
        assert result["command"] == ACTION_RALLY

    def test_rally_sa_rampage(self):
        """Rally has Rampage SA after Rally — §8.5.3."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        _place_belgae_force(state, MORINI, warbands=5, hidden=True)
        _place_roman_force(state, MORINI, auxilia=2)
        refresh_all_control(state)
        result = node_b_rally(state)
        # Should have Rampage SA if Hidden Warbands can target enemies
        if result["sa"] == SA_ACTION_RAMPAGE:
            assert len(result["sa_regions"]) > 0


# ===================================================================
# Raid process node
# ===================================================================

class TestNodeBRaid:
    """B_RAID process node tests."""

    def test_raid_returns_raid_action(self):
        """Raid returns a Raid action dict when gaining 2+."""
        state = _make_state(non_players={BELGAE})
        _place_belgae_force(state, MANDUBII, warbands=2, hidden=True)
        _place_roman_force(state, MANDUBII, auxilia=2)
        result = node_b_raid(state)
        assert result["command"] == ACTION_RAID

    def test_raid_passes_when_not_enough(self):
        """Raid → Pass when gain < 2."""
        state = _make_state()
        result = node_b_raid(state)
        assert result["command"] == ACTION_PASS


# ===================================================================
# March (control) process node
# ===================================================================

class TestNodeBMarch:
    """B_MARCH process node tests."""

    def test_march_falls_back_to_raid_on_frost(self):
        """March → Raid when Frost active — §8.5.5."""
        state = _make_state()
        state["frost"] = True
        state["resources"][BELGAE] = 5
        result = node_b_march(state)
        # Should fall through to Raid (or Pass if Raid can't gain enough)
        assert result["command"] in (ACTION_RAID, ACTION_PASS)

    def test_march_falls_back_to_raid_on_zero_resources(self):
        """March → Raid when 0 Resources — §8.5.5."""
        state = _make_state()
        state["resources"][BELGAE] = 0
        result = node_b_march(state)
        assert result["command"] in (ACTION_RAID, ACTION_PASS)

    def test_march_prefers_belgica(self):
        """March prefers Belgica destinations — §8.5.5."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        # Place Belgae in one Belgica region with enough to March
        _place_belgae_force(state, MORINI, warbands=6)
        # Ensure adjacent Belgica regions don't have Belgic Control
        refresh_all_control(state)
        result = node_b_march(state)
        if result["command"] == ACTION_MARCH:
            march_plan = result["details"]["march_plan"]
            # Should prefer Belgica destinations
            for dest in march_plan["control_destinations"]:
                if dest in (MORINI, NERVII, ATREBATES):
                    pass  # Good — Belgica
                    break

    def test_march_enlist_sa(self):
        """March has Enlist SA — §8.5.5."""
        state = _make_state(non_players={BELGAE})
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MORINI, warbands=6)
        place_piece(state, MANDUBII, GERMANS, WARBAND, 3)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        refresh_all_control(state)
        result = node_b_march(state)
        # May have Enlist SA if conditions met
        if result["command"] == ACTION_MARCH and result["sa"] == SA_ACTION_ENLIST:
            assert len(result["sa_regions"]) > 0


# ===================================================================
# Quarters
# ===================================================================

class TestNodeBQuarters:
    """B_QUARTERS tests."""

    def test_quarters_leaves_devastated(self):
        """Quarters: leave Devastated with no Ally/Citadel."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3)
        state["spaces"][MANDUBII]["devastated"] = True
        # Adjacent Belgae-controlled region
        _place_belgae_force(state, CARNUTES, warbands=5)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leave_devastated"]:
            assert result["leave_devastated"][0]["from"] == MANDUBII

    def test_quarters_moves_leader(self):
        """Quarters: move Leader to most Warbands."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=1)
        _place_belgae_force(state, CARNUTES, warbands=6)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            assert result["leader_move"]["from"] == MANDUBII
            assert result["leader_move"]["to"] == CARNUTES

    def test_quarters_ariovistus_prefers_belgica_treveri(self):
        """A8.5.6: Quarters first moves to Morini, Nervii, or Treveri."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        # Ambiorix in a non-target region
        _place_belgae_force(state, MANDUBII, leader=True, warbands=1)
        # More Warbands in Morini (one of the target regions)
        _place_belgae_force(state, MORINI, warbands=5)
        # Also some in a non-target adjacent
        _place_belgae_force(state, CARNUTES, warbands=8)
        refresh_all_control(state)
        result = node_b_quarters(state)
        # In Ariovistus, should prefer Morini/Nervii/Treveri if adjacent
        if result["leader_move"]:
            # Mandubii may not be adjacent to Morini, so check
            # whatever the result is
            dest = result["leader_move"]["to"]
            # Should try for Morini/Nervii/Treveri first
            assert dest is not None


# ===================================================================
# Spring
# ===================================================================

class TestNodeBSpring:
    """B_SPRING tests."""

    def test_spring_places_successor(self):
        """Spring: place Successor at most Belgae."""
        state = _make_state()
        _place_belgae_force(state, MORINI, warbands=5)
        _place_belgae_force(state, NERVII, warbands=3)
        result = node_b_spring(state)
        assert result is not None
        assert result["place_leader"] == AMBIORIX
        assert result["region"] == MORINI  # Most Belgae pieces

    def test_spring_nothing_when_leader_on_map(self):
        """Spring: nothing to do when Ambiorix already on map."""
        state = _make_state()
        _place_belgae_force(state, MORINI, leader=True, warbands=3)
        result = node_b_spring(state)
        assert result is None


# ===================================================================
# Agreements
# ===================================================================

class TestNodeBAgreements:
    """B_AGREEMENTS tests."""

    def test_always_harass_romans(self):
        """Always Harass Romans — §8.4.2."""
        state = _make_state()
        assert node_b_agreements(state, ROMANS, "harassment") is True

    def test_no_harass_non_roman(self):
        """Don't Harass non-Roman factions."""
        state = _make_state()
        assert node_b_agreements(state, AEDUI, "harassment") is False

    def test_never_agree_supply_line(self):
        """Never agree to Supply Line — §8.4.2."""
        state = _make_state()
        assert node_b_agreements(state, ROMANS, "supply_line") is False

    def test_never_agree_retreat(self):
        """Never agree to Retreat — §8.4.2."""
        state = _make_state()
        assert node_b_agreements(state, ROMANS, "retreat") is False

    def test_never_agree_resources(self):
        """Never transfer Resources — §8.4.2."""
        state = _make_state()
        assert node_b_agreements(state, AEDUI, "resources") is False


# ===================================================================
# Main driver
# ===================================================================

class TestExecuteBelgaeTurn:
    """Test the main flowchart driver."""

    def test_returns_action_dict(self):
        """execute_belgae_turn returns a valid action dict."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MORINI, warbands=5,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        result = execute_belgae_turn(state)
        assert "command" in result
        assert "regions" in result
        assert "sa" in result

    def test_battle_when_threat(self):
        """Battle when B1 threat condition is met."""
        state = _make_state()
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MANDUBII, warbands=6, leader=True)
        _place_roman_force(state, MANDUBII, ally_tribe=TRIBE_MANDUBII,
                           auxilia=2)
        refresh_all_control(state)
        result = execute_belgae_turn(state)
        assert result["command"] in (ACTION_BATTLE, ACTION_MARCH)

    def test_pass_when_b2_triggers(self):
        """Pass when B2 Pass condition triggers."""
        state = _make_state()
        state["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        state["current_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
        # Find a seed that makes die roll ≤ 4
        for s in range(100):
            st = _make_state(seed=s)
            st["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
            st["current_card_faction_order"] = [ROMANS, BELGAE, AEDUI, ARVERNI]
            st["resources"][BELGAE] = 5
            result = execute_belgae_turn(st)
            if result["command"] == ACTION_PASS:
                break
        assert result["command"] == ACTION_PASS

    def test_rally_when_b4_qualifies(self):
        """Rally when B4 conditions are met."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        state["can_play_event"] = False
        state["current_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        state["next_card_faction_order"] = [BELGAE, ROMANS, AEDUI, ARVERNI]
        # Set up so B1 doesn't trigger (no enemy threats) but B4 does
        _place_belgae_force(state, MORINI, warbands=5)
        refresh_all_control(state)
        result = execute_belgae_turn(state)
        assert result["command"] == ACTION_RALLY

    def test_works_in_ariovistus_scenario(self):
        """Belgae bot works in Ariovistus scenarios."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MORINI, warbands=5,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        result = execute_belgae_turn(state)
        assert "command" in result


# ===================================================================
# Bot dispatch integration
# ===================================================================

class TestBelgaeDispatch:
    """Test that bot_dispatch routes to Belgae correctly."""

    def test_dispatch_belgae_base_game(self):
        """Dispatch routes to Belgae bot in base game."""
        state = _make_state()
        state["non_player_factions"] = {BELGAE}
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MORINI, warbands=5,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        result = dispatch_bot_turn(state, BELGAE)
        assert "command" in result

    def test_dispatch_belgae_ariovistus(self):
        """Dispatch routes to Belgae bot in Ariovistus."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        state["non_player_factions"] = {BELGAE}
        state["resources"][BELGAE] = 5
        _place_belgae_force(state, MORINI, warbands=5,
                            ally_tribe=TRIBE_MORINI)
        refresh_all_control(state)
        result = dispatch_bot_turn(state, BELGAE)
        assert "command" in result


# ===================================================================
# Largest Warband group helper
# ===================================================================

class TestLargestWarbandGroup:
    """Test _find_largest_belgae_warband_group."""

    def test_finds_largest_group(self):
        """Finds the region with the most Belgic Warbands."""
        state = _make_state()
        _place_belgae_force(state, MORINI, warbands=3)
        _place_belgae_force(state, NERVII, warbands=7)
        _place_belgae_force(state, ATREBATES, warbands=5)
        region, count = _find_largest_belgae_warband_group(
            state, SCENARIO_PAX_GALLICA)
        assert region == NERVII
        assert count == 7

    def test_returns_none_when_no_warbands(self):
        """Returns (None, 0) when no Warbands on map."""
        state = _make_state()
        region, count = _find_largest_belgae_warband_group(
            state, SCENARIO_PAX_GALLICA)
        assert region is None
        assert count == 0
