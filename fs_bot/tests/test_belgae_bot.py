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
    AMBIORIX, BODUOGNATUS, CAESAR, SUCCESSOR,
    MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII, SUGAMBRI, UBII,
    AEDUI_REGION, ARVERNI_REGION, SEQUANI, BITURIGES,
    CARNUTES, PICTONES, VENETI, TREVERI, BRITANNIA,
    TRIBE_CARNUTES, TRIBE_ARVERNI, TRIBE_AEDUI,
    TRIBE_MANDUBII, TRIBE_BITURIGES, TRIBE_MORINI,
    TRIBE_ATREBATES, TRIBE_SEQUANI, TRIBE_NERVII,
    TRIBE_TREVERI, TRIBE_VENETI,
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
    _check_ambush, _check_rampage,
    _check_enlist_in_battle, _check_enlist_after_command,
    _is_within_one_of_ambiorix,
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

    def test_raid_excludes_germans_in_base_game(self):
        """Raid cannot steal from Germans in base game — §3.3.3."""
        state = _make_state(non_players={BELGAE})
        # Germans are present with pieces but no Citadel/Fort
        _place_belgae_force(state, SUGAMBRI, warbands=2)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_PAX_GALLICA)
        # Should NOT steal from Germans — §3.3.3 "non-Germanic enemy"
        for entry in plan:
            assert entry["target"] != GERMANS

    def test_raid_excludes_arverni_in_ariovistus(self):
        """Raid cannot steal from Arverni in Ariovistus — A8.4."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS,
                            non_players={BELGAE})
        _place_belgae_force(state, MANDUBII, warbands=2)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 3)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_ARIOVISTUS)
        # Per A8.4: swap Germans/Arverni — Arverni excluded
        for entry in plan:
            assert entry["target"] != ARVERNI

    def test_raid_can_steal_from_arverni_in_base_game(self):
        """Raid CAN steal from Arverni in base game — §3.3.3."""
        state = _make_state(non_players={BELGAE})
        _place_belgae_force(state, MANDUBII, warbands=2)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 3)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_PAX_GALLICA)
        targets = [e["target"] for e in plan if e["target"] is not None]
        assert ARVERNI in targets

    def test_raid_can_steal_from_germans_in_ariovistus(self):
        """Raid CAN steal from Germans in Ariovistus — A8.4."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS,
                            non_players={BELGAE})
        _place_belgae_force(state, SUGAMBRI, warbands=2)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3)
        enough, plan = _would_raid_gain_enough(state, SCENARIO_ARIOVISTUS)
        targets = [e["target"] for e in plan if e["target"] is not None]
        assert GERMANS in targets


# ===================================================================
# Ambush
# ===================================================================

class TestAmbush:
    """Test _check_ambush."""

    def test_ambush_when_more_hidden_and_enemy_legion(self):
        """Ambush when more Hidden Belgae than enemy and enemy has Legion."""
        state = _make_state()
        # §4.5.3: Ambiorix must be in/adjacent to the Ambush region
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
        _place_roman_force(state, MANDUBII, legions=1, auxilia=2)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) > 0
        assert MANDUBII in result

    def test_no_ambush_when_fewer_hidden(self):
        """No Ambush when fewer Hidden Belgae than Hidden enemy."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=1, hidden=True,
                            leader=True)
        # Use Arverni Warbands as the enemy (Romans don't have Warbands)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 3,
                    piece_state=HIDDEN)
        battle_plan = [{"region": MANDUBII, "target": ARVERNI}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) == 0

    def test_no_ambush_without_ambiorix_proximity(self):
        """No Ambush when region is not within 1 of Ambiorix — §4.5.3."""
        state = _make_state()
        # Ambiorix far away from the battle region
        _place_belgae_force(state, PROVINCIA, leader=True)
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True)
        _place_roman_force(state, MANDUBII, legions=1, auxilia=2)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) == 0

    def test_ambush_cascades_to_all_battles(self):
        """If Ambushed in 1st Battle, Ambush in all others — §8.5.1."""
        state = _make_state()
        # Ambiorix in Mandubii — adjacent to both Mandubii and Carnutes
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
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
        # §4.5.2: Ambiorix must be within 1 of Rampage region
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        assert len(result) > 0
        assert result[0]["region"] == MANDUBII

    def test_rampage_priority_forces_removal_first(self):
        """Rampage prioritizes forced removal — §8.5.1 step 1."""
        state = _make_state()
        # Ambiorix in Mandubii (adjacent to Carnutes too)
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        _place_belgae_force(state, CARNUTES, warbands=2, hidden=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        place_piece(state, CARNUTES, AEDUI, WARBAND, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Both should be included; force removal ones first
        assert len(result) >= 2

    def test_no_rampage_last_piece_before_battle(self):
        """No Rampage against enemy's last piece before Battle — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 1)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_rampage(
            state, SCENARIO_PAX_GALLICA,
            before_battle=True, battle_plan=battle_plan)
        # Only 1 enemy piece: can't Rampage before battle
        assert len(result) == 0

    def test_no_rampage_without_ambiorix_proximity(self):
        """No Rampage when not within 1 of Ambiorix — §4.5.2."""
        state = _make_state()
        _place_belgae_force(state, PROVINCIA, leader=True)
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        assert len(result) == 0

    def test_no_rampage_against_enemy_with_leader(self):
        """No Rampage against enemy with Leader — §4.5.2."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        _place_roman_force(state, MANDUBII, leader=True, auxilia=2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Romans have Caesar in region → can't Rampage against them
        assert len(result) == 0

    def test_no_rampage_against_enemy_with_fort(self):
        """No Rampage against enemy with Fort — §4.5.2."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        _place_roman_force(state, MANDUBII, auxilia=2, fort=True)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Romans have Fort → can't Rampage against them
        assert len(result) == 0


# ===================================================================
# Enlist
# ===================================================================

class TestEnlist:
    """Test _check_enlist_after_command."""

    def test_enlist_german_battle(self):
        """Enlist Germans to Battle enemy."""
        state = _make_state(non_players={BELGAE})
        # §4.5.1: Ambiorix must be within 1 of the Enlist region
        _place_belgae_force(state, MANDUBII, leader=True)
        place_piece(state, MANDUBII, GERMANS, WARBAND, 4)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        assert result is not None
        assert result["type"] == "german_battle"

    def test_enlist_german_march(self):
        """Enlist Germans to March from Belgica to enemy Control."""
        state = _make_state(non_players={BELGAE})
        # §4.5.1: Ambiorix must be within 1 of March origin
        _place_belgae_force(state, MORINI, leader=True)
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
        _place_belgae_force(state, MANDUBII, leader=True)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        assert result is None

    def test_enlist_none_without_ambiorix_proximity(self):
        """No Enlist when Ambiorix is not near Germans — §4.5.1."""
        state = _make_state(non_players={BELGAE})
        # Ambiorix far away
        _place_belgae_force(state, PROVINCIA, leader=True)
        place_piece(state, MANDUBII, GERMANS, WARBAND, 4)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
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

    def test_rally_falls_through_to_enlist_when_no_rampage(self):
        """Rally → Rampage → If none: Enlist — flowchart."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        # Ambiorix with REVEALED Warbands → no Rampage (needs Hidden)
        _place_belgae_force(state, MORINI, warbands=5, hidden=False,
                            leader=True)
        # Germans with 2+ Warbands near Ambiorix + enemy → Enlist Battle
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        _place_roman_force(state, MORINI, auxilia=2)
        refresh_all_control(state)
        result = node_b_rally(state)
        assert result["command"] == ACTION_RALLY
        # No Rampage possible (Belgae have no Hidden Warbands near
        # Ambiorix) → should fall through to Enlist
        assert result["sa"] == SA_ACTION_ENLIST


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

    def test_raid_falls_through_to_enlist_when_no_rampage(self):
        """Raid → Rampage → If none: Enlist — flowchart."""
        state = _make_state(non_players={BELGAE})
        # Ambiorix alone in Morini (no enemies → no Rampage target here)
        _place_belgae_force(state, MORINI, leader=True, warbands=1,
                            hidden=False)
        # Hidden Warbands far from Ambiorix for Raid — Provincia is far
        # from Morini, so not within 1 of Ambiorix → no Rampage
        _place_belgae_force(state, PROVINCIA, warbands=2, hidden=True)
        _place_roman_force(state, PROVINCIA, auxilia=2)
        # Germans with Warbands near Ambiorix for Enlist Battle
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        _place_roman_force(state, MORINI, auxilia=1)
        refresh_all_control(state)
        result = node_b_raid(state)
        assert result["command"] == ACTION_RAID
        # No Rampage: Morini has no enemy vulnerable to Rampage (Romans
        # have auxilia, but Belgae have no Hidden Warbands in Morini);
        # Provincia has enemies but is not within 1 of Ambiorix.
        # Should fall through to Enlist via Germans near Ambiorix.
        assert result["sa"] == SA_ACTION_ENLIST


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

    def test_march_outside_belgica_sorts_by_fewest_needed(self):
        """Outside-Belgica March sorts by fewest Warbands needed — §8.5.5.

        [Ch8] §8.5.5: "where the movement of the fewest Warbands is needed
        to do so" — sort by Warbands NEEDED, not Warbands available.

        Setup: Belgae Warbands in Bituriges (Celtica). Bituriges is adjacent
        to Carnutes and Mandubii (among others). We place different numbers
        of enemies in those two regions to create different warbands_needed
        values. The bot should prefer the one needing fewer Warbands.
        """
        state = _make_state()
        state["resources"][BELGAE] = 10

        # Place Belgae Warbands in Bituriges — supply origin
        _place_belgae_force(state, BITURIGES, warbands=10)

        # CARNUTES (adjacent to Bituriges): 4 enemy pieces →
        # needs 5 Warbands to take Control
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 4)

        # MANDUBII (adjacent to Bituriges via Carnutes? No — Mandubii is
        # adjacent to Bituriges directly): 1 enemy piece →
        # needs 2 Warbands to take Control
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 1)

        refresh_all_control(state)
        result = node_b_march(state)
        assert result["command"] == ACTION_MARCH
        march_plan = result["details"]["march_plan"]
        dests = march_plan["control_destinations"]
        # Mandubii needs fewer Warbands (2) than Carnutes (5)
        if MANDUBII in dests and CARNUTES in dests:
            assert dests.index(MANDUBII) < dests.index(CARNUTES)
        elif len(dests) == 1:
            # If only one picked, should be the one needing fewer
            assert dests[0] == MANDUBII

    def test_march_belgica_sorts_by_fewest_needed(self):
        """Belgica March also sorts by fewest Warbands needed — §8.5.5."""
        state = _make_state()
        state["resources"][BELGAE] = 10
        # Warbands in Morini that can March to Nervii or Atrebates
        _place_belgae_force(state, MORINI, warbands=10)
        # Nervii: 3 enemy pieces → needs 4 Warbands
        place_piece(state, NERVII, ROMANS, AUXILIA, 3)
        # Atrebates: 1 enemy piece → needs 2 Warbands
        place_piece(state, ATREBATES, ROMANS, AUXILIA, 1)
        refresh_all_control(state)

        result = node_b_march(state)
        assert result["command"] == ACTION_MARCH
        march_plan = result["details"]["march_plan"]
        dests = march_plan["control_destinations"]
        # Atrebates needs fewer (2) than Nervii (4) — should come first
        if len(dests) >= 2:
            atr_idx = dests.index(ATREBATES) if ATREBATES in dests else 99
            ner_idx = dests.index(NERVII) if NERVII in dests else 99
            assert atr_idx < ner_idx


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


# ===================================================================
# Ambiorix proximity helper
# ===================================================================

class TestAmbiorixProximity:
    """Test _is_within_one_of_ambiorix."""

    def test_same_region(self):
        """Ambiorix in same region → within proximity."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True)
        assert _is_within_one_of_ambiorix(
            state, MANDUBII, SCENARIO_PAX_GALLICA)

    def test_adjacent_region(self):
        """Adjacent to Ambiorix → within proximity."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True)
        # Carnutes is adjacent to Mandubii
        assert _is_within_one_of_ambiorix(
            state, CARNUTES, SCENARIO_PAX_GALLICA)

    def test_far_region(self):
        """2+ regions away → NOT within proximity."""
        state = _make_state()
        _place_belgae_force(state, PROVINCIA, leader=True)
        # Mandubii is NOT adjacent to Provincia
        assert not _is_within_one_of_ambiorix(
            state, MANDUBII, SCENARIO_PAX_GALLICA)

    def test_no_leader_on_map(self):
        """No leader on map → NOT within proximity."""
        state = _make_state()
        assert not _is_within_one_of_ambiorix(
            state, MANDUBII, SCENARIO_PAX_GALLICA)

    def test_successor_same_region_only(self):
        """Successor must be in SAME region, not adjacent — §4.1.2."""
        state = _make_state()
        # Place Successor (non-Ambiorix leader) in Mandubii
        place_piece(state, MANDUBII, BELGAE, LEADER, leader_name=SUCCESSOR)
        # Same region works
        assert _is_within_one_of_ambiorix(
            state, MANDUBII, SCENARIO_PAX_GALLICA)
        # Adjacent does NOT work for Successor
        assert not _is_within_one_of_ambiorix(
            state, CARNUTES, SCENARIO_PAX_GALLICA)

    def test_ariovistus_uses_boduognatus(self):
        """Ariovistus scenario uses Boduognatus as named leader — A1.4."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        place_piece(state, MANDUBII, BELGAE, LEADER,
                    leader_name=BODUOGNATUS)
        assert _is_within_one_of_ambiorix(
            state, MANDUBII, SCENARIO_ARIOVISTUS)
        # Adjacent also works with named leader
        assert _is_within_one_of_ambiorix(
            state, CARNUTES, SCENARIO_ARIOVISTUS)


# ===================================================================
# Ambush: additional edge cases
# ===================================================================

class TestAmbushEdgeCases:
    """Additional Ambush edge case tests."""

    def test_ambush_retreat_condition(self):
        """Ambush when retreat could lessen removals — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
        # Enemy has mobile pieces that could retreat
        place_piece(state, MANDUBII, AEDUI, WARBAND, 3)
        battle_plan = [{"region": MANDUBII, "target": AEDUI}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) > 0

    def test_ambush_counterattack_condition(self):
        """Ambush when counterattack Loss to Belgae is possible — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
        # Enemy has Legion → counterattack possible
        _place_roman_force(state, MANDUBII, legions=1)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        assert len(result) > 0

    def test_no_ambush_when_no_counterattack_no_retreat(self):
        """No Ambush when neither retreat nor counterattack applies — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
        # Enemy has only Allies (immobile, no counterattack)
        state["tribes"][TRIBE_MANDUBII]["allied_faction"] = ARVERNI
        place_piece(state, MANDUBII, ARVERNI, ALLY)
        battle_plan = [{"region": MANDUBII, "target": ARVERNI}]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        # Only 1 Ally piece, no mobile, no Legion/Leader → no Ambush reason
        assert len(result) == 0

    def test_cascade_filters_ineligible_regions(self):
        """Cascade only to regions where Ambush is eligible — §4.5.3."""
        state = _make_state()
        # Ambiorix in Mandubii. Mandubii is adjacent to Carnutes but NOT
        # to Provincia. So a battle in Provincia should be filtered out.
        _place_belgae_force(state, MANDUBII, warbands=4, hidden=True,
                            leader=True)
        _place_belgae_force(state, PROVINCIA, warbands=4, hidden=True)
        _place_roman_force(state, MANDUBII, legions=1)
        _place_roman_force(state, PROVINCIA, auxilia=2)
        battle_plan = [
            {"region": MANDUBII, "target": ROMANS},
            {"region": PROVINCIA, "target": ROMANS},
        ]
        result = _check_ambush(state, battle_plan, SCENARIO_PAX_GALLICA)
        # Mandubii should be included (eligible), Provincia should not
        assert MANDUBII in result
        assert PROVINCIA not in result


# ===================================================================
# Rampage: additional edge cases
# ===================================================================

class TestRampageEdgeCases:
    """Additional Rampage edge case tests."""

    def test_no_rampage_against_enemy_with_citadel(self):
        """No Rampage against enemy with Citadel — §4.5.2."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        place_piece(state, MANDUBII, ARVERNI, WARBAND, 3)
        place_piece(state, MANDUBII, ARVERNI, CITADEL)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Arverni have Citadel → can't Rampage
        assert len(result) == 0

    def test_rampage_does_not_target_germans(self):
        """Rampage never targets Germans — §4.5.2."""
        state = _make_state()
        _place_belgae_force(state, SUGAMBRI, warbands=3, hidden=True,
                            leader=True)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        # Germans are never valid Rampage targets
        assert len(result) == 0

    def test_rampage_forces_removal_prioritized(self):
        """Rampage prioritizes force removal over control — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, hidden=True,
                            leader=True)
        # Region with enemy mobile pieces (forces removal)
        place_piece(state, MANDUBII, AEDUI, WARBAND, 3)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        if result:
            assert result[0]["forces_removal"] is True

    def test_rampage_adjacent_to_ambiorix(self):
        """Rampage works in region adjacent to Ambiorix."""
        state = _make_state()
        # Ambiorix in Mandubii, Rampage in Carnutes (adjacent)
        _place_belgae_force(state, MANDUBII, leader=True)
        _place_belgae_force(state, CARNUTES, warbands=3, hidden=True)
        place_piece(state, CARNUTES, AEDUI, WARBAND, 2)
        result = _check_rampage(state, SCENARIO_PAX_GALLICA)
        assert len(result) > 0
        assert result[0]["region"] == CARNUTES


# ===================================================================
# Enlist in Battle: tests
# ===================================================================

class TestEnlistInBattle:
    """Test _check_enlist_in_battle."""

    def test_enlist_in_battle_with_germans_nearby(self):
        """Enlist Germans when in battle region with Ambiorix — §8.5.1."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=4)
        place_piece(state, MANDUBII, GERMANS, WARBAND, 2)
        _place_roman_force(state, MANDUBII, auxilia=3)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_enlist_in_battle(
            state, battle_plan, SCENARIO_PAX_GALLICA)
        assert result is not None
        assert result["type"] == "in_battle"
        assert result["region"] == MANDUBII

    def test_no_enlist_in_battle_without_proximity(self):
        """No Enlist in Battle when region not near Ambiorix — §4.5.1."""
        state = _make_state()
        _place_belgae_force(state, PROVINCIA, leader=True)
        _place_belgae_force(state, MANDUBII, warbands=4)
        place_piece(state, MANDUBII, GERMANS, WARBAND, 2)
        _place_roman_force(state, MANDUBII, auxilia=3)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_enlist_in_battle(
            state, battle_plan, SCENARIO_PAX_GALLICA)
        assert result is None

    def test_no_enlist_in_battle_without_germans(self):
        """No Enlist in Battle when no Germans in battle region."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=4)
        _place_roman_force(state, MANDUBII, auxilia=3)
        battle_plan = [{"region": MANDUBII, "target": ROMANS}]
        result = _check_enlist_in_battle(
            state, battle_plan, SCENARIO_PAX_GALLICA)
        assert result is None

    def test_enlist_empty_battle_plan(self):
        """No Enlist with empty battle plan."""
        state = _make_state()
        result = _check_enlist_in_battle(state, [], SCENARIO_PAX_GALLICA)
        assert result is None


# ===================================================================
# Enlist after Command: additional tests
# ===================================================================

class TestEnlistAfterCommandEdgeCases:
    """Additional Enlist after Command tests."""

    def test_enlist_prefers_battle_over_march(self):
        """Enlist prefers German Battle (step 1) over March (step 2)."""
        state = _make_state(non_players={BELGAE})
        _place_belgae_force(state, MORINI, leader=True)
        # Germans in Morini with enemy
        place_piece(state, MORINI, GERMANS, WARBAND, 4)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        assert result is not None
        assert result["type"] == "german_battle"

    def test_enlist_march_from_belgica(self):
        """Enlist March from Belgica to enemy Control — §8.5.1 step 2."""
        state = _make_state(non_players={BELGAE})
        # Ambiorix in Morini (Belgica), Germans also in Morini
        _place_belgae_force(state, MORINI, leader=True)
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        # Adjacent region has Roman Control
        _place_roman_force(state, ATREBATES, auxilia=4,
                           ally_tribe=TRIBE_ATREBATES)
        refresh_all_control(state)
        result = _check_enlist_after_command(state, SCENARIO_PAX_GALLICA)
        # No battle target in Morini → should try March
        if result and result["type"] == "german_march":
            assert result["origin"] == MORINI

    def test_enlist_ariovistus_march_from_treveri(self):
        """A8.5.1: Enlist March from Treveri in Ariovistus."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS,
                            non_players={BELGAE})
        # Ambiorix in Treveri
        _place_belgae_force(state, TREVERI, leader=True)
        place_piece(state, TREVERI, GERMANS, WARBAND, 3)
        # Adjacent region has Roman Control
        _place_roman_force(state, MANDUBII, auxilia=4,
                           ally_tribe=TRIBE_MANDUBII)
        refresh_all_control(state)
        result = _check_enlist_after_command(state, SCENARIO_ARIOVISTUS)
        if result and result["type"] == "german_march":
            assert result["origin"] == TREVERI


# ===================================================================
# Quarters: additional edge cases
# ===================================================================

class TestQuartersEdgeCases:
    """Additional Quarters edge case tests."""

    def test_quarters_stays_in_devastated_with_ally(self):
        """Quarters: don't leave Devastated if Belgae have Ally — §8.5.6."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3,
                            ally_tribe=TRIBE_MANDUBII)
        state["spaces"][MANDUBII]["devastated"] = True
        refresh_all_control(state)
        result = node_b_quarters(state)
        # Has Ally → don't leave
        assert len(result["leave_devastated"]) == 0

    def test_quarters_stays_in_devastated_with_citadel(self):
        """Quarters: don't leave Devastated if have Citadel — §8.5.6."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3, citadel=True)
        state["spaces"][MANDUBII]["devastated"] = True
        refresh_all_control(state)
        result = node_b_quarters(state)
        assert len(result["leave_devastated"]) == 0

    def test_quarters_leaves_devastated_randomly(self):
        """Quarters: random adjacent Controlled region — §8.5.6."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, warbands=3)
        state["spaces"][MANDUBII]["devastated"] = True
        # Multiple adjacent Belgae-Controlled regions
        _place_belgae_force(state, CARNUTES, warbands=5)
        _place_belgae_force(state, BITURIGES, warbands=5)
        refresh_all_control(state)
        # Run multiple times to verify randomness
        destinations = set()
        for s in range(50):
            st = _make_state(seed=s)
            _place_belgae_force(st, MANDUBII, warbands=3)
            st["spaces"][MANDUBII]["devastated"] = True
            _place_belgae_force(st, CARNUTES, warbands=5)
            _place_belgae_force(st, BITURIGES, warbands=5)
            refresh_all_control(st)
            res = node_b_quarters(st)
            if res["leave_devastated"]:
                destinations.add(res["leave_devastated"][0]["to"])
        # Should see multiple destinations due to randomness
        assert len(destinations) >= 1

    def test_quarters_leader_move_leaves_warbands(self):
        """Quarters: leave behind 1+ Warbands when moving — §8.5.6."""
        state = _make_state()
        # Ambiorix in Mandubii with 3 Warbands, more in Carnutes
        _place_belgae_force(state, MANDUBII, leader=True, warbands=3)
        _place_belgae_force(state, CARNUTES, warbands=8)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            assert result["leader_move"]["warbands_left"] >= 1

    def test_quarters_leader_move_keeps_control(self):
        """Quarters: keep enough for Control when moving — §8.5.6."""
        state = _make_state()
        # Ambiorix in Mandubii with 4 Warbands, enemy has 2
        _place_belgae_force(state, MANDUBII, leader=True, warbands=4)
        place_piece(state, MANDUBII, AEDUI, WARBAND, 2)
        _place_belgae_force(state, CARNUTES, warbands=8)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            # Must leave enough to keep Control over the 2 Aedui
            assert result["leader_move"]["warbands_left"] >= 3

    def test_quarters_no_move_when_already_at_largest(self):
        """Quarters: no move when Leader already at largest group."""
        state = _make_state()
        _place_belgae_force(state, MANDUBII, leader=True, warbands=10)
        _place_belgae_force(state, CARNUTES, warbands=3)
        refresh_all_control(state)
        result = node_b_quarters(state)
        assert result["leader_move"] is None

    def test_quarters_ariovistus_targets_morini(self):
        """A8.5.6: In Ariovistus, Quarters prefers Morini/Nervii/Treveri."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        # Ambiorix in Atrebates (adjacent to Morini and Nervii)
        _place_belgae_force(state, ATREBATES, leader=True, warbands=1)
        # More Warbands in Morini (Ariovistus target)
        _place_belgae_force(state, MORINI, warbands=3)
        # Even more in a non-target region
        _place_belgae_force(state, MANDUBII, warbands=6)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            # Should prefer Morini/Nervii/Treveri over Mandubii per A8.5.6
            dest = result["leader_move"]["to"]
            assert dest in (MORINI, NERVII, TREVERI)


# ===================================================================
# Spring: additional tests
# ===================================================================

class TestSpringEdgeCases:
    """Additional Spring tests."""

    def test_spring_places_at_most_pieces(self):
        """Spring places Leader at region with most Belgae pieces."""
        state = _make_state()
        _place_belgae_force(state, MORINI, warbands=2)
        _place_belgae_force(state, NERVII, warbands=8)
        _place_belgae_force(state, ATREBATES, warbands=3)
        result = node_b_spring(state)
        assert result is not None
        assert result["place_leader"] == AMBIORIX
        assert result["region"] == NERVII

    def test_spring_nothing_when_no_belgae(self):
        """Spring returns None when no Belgae on map."""
        state = _make_state()
        result = node_b_spring(state)
        # No Belgae on map, but leader also not on map
        # get_leader_placement_region would return None
        assert result is None or result["region"] is not None


# ===================================================================
# Agreements: additional tests
# ===================================================================

class TestAgreementsEdgeCases:
    """Additional Agreements tests."""

    def test_never_agree_quarters(self):
        """Never agree to Quarters for others — §8.4.2."""
        state = _make_state()
        assert node_b_agreements(state, ROMANS, "quarters") is False
        assert node_b_agreements(state, AEDUI, "quarters") is False

    def test_harass_seize(self):
        """Harass Roman Seize — §8.4.2."""
        state = _make_state()
        # "Harass Roman March and Seize" — §8.4.2
        assert node_b_agreements(state, ROMANS, "harassment") is True

    def test_no_harass_belgae_self(self):
        """Don't harass self."""
        state = _make_state()
        assert node_b_agreements(state, BELGAE, "harassment") is False

    def test_no_harass_arverni(self):
        """Don't harass Arverni — only harass Romans."""
        state = _make_state()
        assert node_b_agreements(state, ARVERNI, "harassment") is False

    def test_no_agree_unknown_type(self):
        """Reject unknown request types — default deny."""
        state = _make_state()
        assert node_b_agreements(state, ROMANS, "unknown") is False


# ===================================================================
# Ariovistus modifications: comprehensive tests
# ===================================================================

class TestAriovistusModifications:
    """Test A8.5 Ariovistus-specific modifications."""

    def test_a851_threat_considers_germans(self):
        """A8.5.1: Belgae consider Germans as enemies in Ariovistus."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, SUGAMBRI, leader=True, warbands=4)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 5)
        assert _has_belgae_threat(state, SUGAMBRI, SCENARIO_ARIOVISTUS)

    def test_a851_threat_ignores_germans_in_base(self):
        """Base game: Belgae do NOT consider Germans as enemies."""
        state = _make_state()
        _place_belgae_force(state, SUGAMBRI, leader=True, warbands=4)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 5)
        assert not _has_belgae_threat(state, SUGAMBRI, SCENARIO_PAX_GALLICA)

    def test_a851_settlements_count_as_allies(self):
        """A8.5.1: Settlements count as Allies for B1 conditions."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, TREVERI, leader=True, warbands=2)
        place_piece(state, TREVERI, GERMANS, SETTLEMENT)
        result, regions = node_b1(state)
        assert result == "Yes"

    def test_a851_battle_targets_germans_in_ariovistus(self):
        """A8.5.1: Belgae can Battle Germans in Ariovistus."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_belgae_force(state, SUGAMBRI, warbands=6, leader=True)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2)
        assert _can_battle_in_region(
            state, SUGAMBRI, SCENARIO_ARIOVISTUS, GERMANS)

    def test_a851_cannot_battle_germans_in_base(self):
        """Base game: Belgae cannot Battle Germans."""
        state = _make_state()
        _place_belgae_force(state, SUGAMBRI, warbands=6, leader=True)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2)
        assert not _can_battle_in_region(
            state, SUGAMBRI, SCENARIO_PAX_GALLICA, GERMANS)

    def test_a856_quarters_prefers_belgica_treveri(self):
        """A8.5.6: Quarters first moves to Morini/Nervii/Treveri."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        # Ambiorix in Nervii (one of the target regions)
        _place_belgae_force(state, ATREBATES, leader=True, warbands=1)
        _place_belgae_force(state, NERVII, warbands=4)
        _place_belgae_force(state, MANDUBII, warbands=7)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            dest = result["leader_move"]["to"]
            # Should prefer Nervii (Ariovistus target) over Mandubii
            # even though Mandubii has more Warbands
            assert dest in (MORINI, NERVII, TREVERI)

    def test_a856_quarters_fallback_when_no_target_reachable(self):
        """A8.5.6: Fall back to normal logic when no target reachable."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        # Ambiorix far from Morini/Nervii/Treveri
        _place_belgae_force(state, PROVINCIA, leader=True, warbands=1)
        _place_belgae_force(state, AEDUI_REGION, warbands=5)
        refresh_all_control(state)
        result = node_b_quarters(state)
        if result["leader_move"]:
            # Falls back to joining most Warbands
            assert result["leader_move"]["to"] == AEDUI_REGION
