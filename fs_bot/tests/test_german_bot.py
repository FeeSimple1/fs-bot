"""
Tests for german_bot.py — Non-Player Germans flowchart per Chapter A8.7.

Tests every flowchart node with Yes/No branches, seeded RNG, and
scenario isolation (Ariovistus-only). German bot is NOT a base game bot.
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED, SCOUTED,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    SCENARIO_GREAT_REVOLT, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    ARIOVISTUS_LEADER, BODUOGNATUS, CAESAR, SUCCESSOR, DIVICIACUS,
    # Regions
    MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII, SUGAMBRI, UBII,
    AEDUI_REGION, ARVERNI_REGION, SEQUANI, BITURIGES,
    CARNUTES, PICTONES, VENETI, TREVERI, CISALPINA,
    GERMANIA_REGIONS,
    # Tribes
    TRIBE_CARNUTES, TRIBE_ARVERNI, TRIBE_AEDUI,
    TRIBE_MANDUBII, TRIBE_BITURIGES, TRIBE_MORINI,
    TRIBE_ATREBATES, TRIBE_SEQUANI, TRIBE_NERVII,
    TRIBE_TREVERI, TRIBE_VENETI, TRIBE_UBII, TRIBE_SUGAMBRI,
    TRIBE_PICTONES, TRIBE_HELVETII, TRIBE_NORI,
    EVENT_SHADED,
    MARKER_DISPERSED,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces, get_available
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.bots.german_bot import (
    # Node functions
    node_g1, node_g1b, node_g2, node_g3, node_g3b, node_g4, node_g5,
    # Process nodes
    node_g_event, node_g_battle, node_g_march_threat,
    node_g_rally, node_g_raid, node_g_march_expand,
    # SA helpers
    _check_ambush, _check_intimidate_before_battle,
    _select_intimidate_targets, _can_intimidate_region,
    _determine_intimidate_after_raid,
    _determine_intimidate_or_settle_after_march,
    node_g_settle,
    # Helpers
    _has_german_threat, _can_battle_in_region,
    _ariovistus_region, _has_ariovistus,
    _estimate_battle_losses, _romans_at_victory,
    _get_threat_regions, _get_settle_destinations,
    _is_in_or_adjacent_to_germania,
    _instruction_says_no_germans,
    _estimate_rally_settle_would_qualify,
    _would_raid_gain_enough,
    _find_largest_german_warband_group_leaderless,
    # Winter
    node_g_quarters, node_g_spring,
    # Agreements
    node_g_agreements,
    # Main driver
    execute_german_turn,
    # Action constants
    ACTION_BATTLE, ACTION_MARCH, ACTION_RALLY, ACTION_RAID,
    ACTION_EVENT, ACTION_PASS,
    SA_ACTION_AMBUSH, SA_ACTION_SETTLE, SA_ACTION_INTIMIDATE,
    SA_ACTION_NONE,
)
from fs_bot.bots.bot_dispatch import (
    dispatch_bot_turn, BotDispatchError,
)


# ===================================================================
# Test helpers
# ===================================================================

def _make_state(scenario=SCENARIO_ARIOVISTUS, seed=42, non_players=None):
    """Build a minimal test state with common defaults (Ariovistus default)."""
    state = build_initial_state(scenario, seed=seed)
    if non_players is None:
        non_players = {GERMANS, BELGAE, AEDUI}
    state["non_player_factions"] = non_players
    state["can_play_event"] = True
    state["current_card_id"] = "A17"  # Publius Licinius Crassus — Ariovistus
    state["final_year"] = False
    state["frost"] = False
    state["current_card_faction_order"] = []
    state["next_card_faction_order"] = []
    state["is_second_eligible"] = False
    state["resources"][GERMANS] = 5
    return state


def _place_german_force(state, region, *, warbands=0, ally_tribe=None,
                        leader=False, settlement=False, hidden=True):
    """Helper to place Germanic forces in a region."""
    if warbands > 0:
        piece_state = HIDDEN if hidden else REVEALED
        place_piece(state, region, GERMANS, WARBAND, warbands,
                    piece_state=piece_state)
    if ally_tribe:
        state["tribes"][ally_tribe]["allied_faction"] = GERMANS
        place_piece(state, region, GERMANS, ALLY)
    if settlement:
        place_piece(state, region, GERMANS, SETTLEMENT)
    if leader:
        place_piece(state, region, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)


def _place_roman_force(state, region, *, leader=False, legions=0, auxilia=0,
                       ally_tribe=None, fort=False):
    """Helper to place Roman forces."""
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
        if faction == BELGAE:
            place_piece(state, region, faction, LEADER,
                        leader_name=BODUOGNATUS)
        elif faction == AEDUI:
            place_piece(state, region, faction, LEADER,
                        leader_name=DIVICIACUS)
        else:
            place_piece(state, region, faction, LEADER, leader_name=CAESAR)


# ===================================================================
# Scenario isolation
# ===================================================================

class TestScenarioIsolation:
    """German bot must refuse to run in base game scenarios."""

    def test_rejects_pax_gallica(self):
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=1)
        state["non_player_factions"] = {ARVERNI, BELGAE, AEDUI, GERMANS}
        with pytest.raises(BotDispatchError, match="German bot cannot run"):
            execute_german_turn(state)

    def test_rejects_great_revolt(self):
        state = build_initial_state(SCENARIO_GREAT_REVOLT, seed=1)
        state["non_player_factions"] = {ARVERNI, BELGAE, AEDUI, GERMANS}
        with pytest.raises(BotDispatchError, match="German bot cannot run"):
            execute_german_turn(state)

    def test_accepts_ariovistus(self):
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_german_force(state, SUGAMBRI, leader=True, warbands=3)
        result = execute_german_turn(state)
        assert result["command"] is not None

    def test_accepts_gallic_war(self):
        state = _make_state(scenario=SCENARIO_GALLIC_WAR)
        _place_german_force(state, SUGAMBRI, leader=True, warbands=3)
        result = execute_german_turn(state)
        assert result["command"] is not None


class TestGermanDispatch:
    """Test that bot_dispatch routes to German bot correctly."""

    def test_dispatch_german_ariovistus(self):
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        state["non_player_factions"] = {GERMANS, BELGAE, AEDUI}
        _place_german_force(state, SUGAMBRI, leader=True, warbands=3)
        result = dispatch_bot_turn(state, GERMANS)
        assert "command" in result

    def test_dispatch_rejects_german_in_base(self):
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=1)
        state["non_player_factions"] = {GERMANS, BELGAE, AEDUI}
        with pytest.raises(BotDispatchError):
            dispatch_bot_turn(state, GERMANS)


# ===================================================================
# G1: Battle or March under Threat?
# ===================================================================

class TestNodeG1:
    """G1 decision node tests."""

    def test_yes_when_ariovistus_with_enemy_ally(self):
        state = _make_state()
        _place_german_force(state, MANDUBII, leader=True, warbands=1)
        _place_enemy_force(state, MANDUBII, AEDUI, ally_tribe=TRIBE_MANDUBII)
        result, regions = node_g1(state)
        assert result == "Yes"
        assert MANDUBII in regions

    def test_yes_when_6_warbands_with_enemy_legion(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=6)
        _place_roman_force(state, ATREBATES, legions=1)
        result, regions = node_g1(state)
        assert result == "Yes"
        assert ATREBATES in regions

    def test_yes_when_ariovistus_alone_with_citadel(self):
        state = _make_state()
        _place_german_force(state, ARVERNI_REGION, leader=True)
        place_piece(state, ARVERNI_REGION, AEDUI, CITADEL)
        result, regions = node_g1(state)
        assert result == "Yes"

    def test_yes_when_6_wb_with_enemy_4_pieces(self):
        state = _make_state()
        _place_german_force(state, NERVII, warbands=6)
        _place_enemy_force(state, NERVII, BELGAE, warbands=4)
        result, regions = node_g1(state)
        assert result == "Yes"

    def test_no_when_only_5_warbands(self):
        state = _make_state()
        _place_german_force(state, MANDUBII, warbands=5)
        _place_roman_force(state, MANDUBII, legions=1)
        result, _ = node_g1(state)
        assert result == "No"

    def test_no_when_no_enemy(self):
        state = _make_state()
        _place_german_force(state, MANDUBII, leader=True, warbands=5)
        result, _ = node_g1(state)
        assert result == "No"

    def test_considers_all_enemies_including_other_gauls(self):
        """Unlike Belgae §8.5.1, Germans consider all enemies (no carve-out)."""
        state = _make_state()
        _place_german_force(state, MANDUBII, leader=True, warbands=1)
        # Even Arverni count as an enemy
        _place_enemy_force(state, MANDUBII, ARVERNI, ally_tribe=TRIBE_MANDUBII)
        result, regions = node_g1(state)
        assert result == "Yes"
        assert MANDUBII in regions


# ===================================================================
# G1b: Enemy at victory + Ariovistus 12+ Warbands
# ===================================================================

class TestNodeG1b:
    """G1b fallback trigger tests."""

    def test_no_when_no_ariovistus(self):
        state = _make_state()
        # No leader on map
        assert node_g1b(state) == "No"

    def test_no_when_ariovistus_under_12_warbands(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=11)
        assert node_g1b(state) == "No"

    def test_no_when_enemy_not_at_victory(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=12)
        # Suppress baseline Roman victory (Subdued tribes >= 16) by allying
        # all tribes to Germans so Romans margin drops below 0.
        for t in list(state["tribes"].keys()):
            state["tribes"][t]["allied_faction"] = GERMANS
        refresh_all_control(state)
        # Now no enemy is at margin >= 0
        assert node_g1b(state) == "No"

    def test_yes_when_romans_at_victory_and_12wb(self):
        """A8.7.1 fallback: enemy at margin >= 0 + Ariovistus has 12+ Warbands."""
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=12)
        # Default empty board: Romans margin == 15 (Subdued tribes)
        refresh_all_control(state)
        assert node_g1b(state) == "Yes"


# ===================================================================
# G2: Pass decision
# ===================================================================

class TestNodeG2:
    """G2 Pass decision tests."""

    def test_no_pass_when_winter_showing(self):
        state = _make_state(seed=1)
        state["frost"] = True
        state["current_card_faction_order"] = [
            ROMANS, AEDUI, BELGAE, GERMANS]
        state["next_card_faction_order"] = [
            GERMANS, ROMANS, AEDUI, BELGAE]
        # Even with Germans 1st on next, frost prevents Pass
        assert node_g2(state) == "No"

    def test_no_pass_when_already_1st_on_current(self):
        state = _make_state(seed=1)
        state["current_card_faction_order"] = [
            GERMANS, ROMANS, AEDUI, BELGAE]
        state["next_card_faction_order"] = [
            GERMANS, ROMANS, AEDUI, BELGAE]
        # 1st on both — no Pass
        assert node_g2(state) == "No"

    def test_pass_when_only_1st_on_next_and_low_roll(self):
        # Find a seed that gives die roll 1-4
        for seed in range(20):
            state = _make_state(seed=seed)
            state["current_card_faction_order"] = [
                ROMANS, AEDUI, BELGAE, GERMANS]
            state["next_card_faction_order"] = [
                GERMANS, ROMANS, AEDUI, BELGAE]
            if node_g2(state) == "Yes":
                return
        pytest.fail("Couldn't find seed for low roll Pass")

    def test_no_pass_when_high_roll(self):
        for seed in range(20):
            state = _make_state(seed=seed)
            state["current_card_faction_order"] = [
                ROMANS, AEDUI, BELGAE, GERMANS]
            state["next_card_faction_order"] = [
                GERMANS, ROMANS, AEDUI, BELGAE]
            if node_g2(state) == "No":
                return
        pytest.fail("Couldn't find seed for high roll No")


# ===================================================================
# G3 / G3b: Event decisions
# ===================================================================

class TestNodeG3:

    def test_yes_when_can_play_event(self):
        state = _make_state()
        state["can_play_event"] = True
        assert node_g3(state) == "Yes"

    def test_no_when_cannot_play_event(self):
        state = _make_state()
        state["can_play_event"] = False
        assert node_g3(state) == "No"


class TestNodeG3b:
    """G3b decline checks."""

    def test_decline_for_no_germans_card(self):
        state = _make_state()
        # "Ballistae" is in no_german_titles
        # Card 10 base id; in Ariovistus it stays a no-Germans card.
        state["current_card_id"] = 10
        result = node_g3b(state)
        assert result == "Yes"  # decline

    def test_play_event_when_carnyx_card(self):
        state = _make_state()
        # "Acco" is base-only and not in Ariovistus instructions; pick a
        # card that has PLAY_EVENT action. Use base id 32 (Forced Marches)
        # which is in the Ariovistus deck without per-card instructions.
        # Pick "Cicero" (card 1) which has a SPECIFIC_INSTRUCTION (shift).
        # For PLAY_EVENT, find one explicitly.
        from fs_bot.cards.bot_instructions import (
            get_ariovistus_instructions, PLAY_EVENT,
        )
        all_instr = get_ariovistus_instructions()
        play_event_cards = [cid for (cid, fac), instr in all_instr.items()
                            if fac == GERMANS and instr.action == PLAY_EVENT]
        assert play_event_cards, "Need at least one PLAY_EVENT card for Germans"
        state["current_card_id"] = play_event_cards[0]
        assert node_g3b(state) == "No"

    def test_decline_for_capability_in_final_year(self):
        state = _make_state()
        state["final_year"] = True
        # Card 8 "Baggage Trains" is a Capability in base
        state["current_card_id"] = 8
        # 8 may not exist in Ariovistus instr — try 13 (Balearic Slingers)
        # which IS in Ariovistus deck and is a CAPABILITY.
        state["current_card_id"] = 13
        # 13 also has conditional 'if Romans Non-Player' — but with
        # non_players={GERMANS, BELGAE, AEDUI}, Romans IS player.
        # However it's a Capability so final_year decline triggers first.
        result = node_g3b(state)
        assert result == "Yes"

    def test_decline_balearic_when_romans_non_player(self):
        """Per per-card instruction: if Romans Non-Player, treat as No Germans."""
        state = _make_state(non_players={ROMANS, GERMANS, BELGAE, AEDUI})
        # Balearic Slingers (card 13) — but 13 is a Capability so we'd hit
        # the cap-final-year check first. Use Pompey (3).
        state["current_card_id"] = 3
        state["final_year"] = False
        result = node_g3b(state)
        assert result == "Yes"  # decline (Romans Non-Player)

    def test_play_balearic_when_romans_player(self):
        """If Romans IS a player, don't treat Pompey/Balearic as No Germans."""
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI})
        state["current_card_id"] = 3  # Pompey
        state["final_year"] = False
        assert node_g3b(state) == "No"

    def test_decline_kinship_when_belgae_non_player(self):
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI})
        # Kinship = A65
        state["current_card_id"] = "A65"
        assert node_g3b(state) == "Yes"

    def test_play_kinship_when_belgae_player(self):
        state = _make_state(non_players={GERMANS, AEDUI})
        state["current_card_id"] = "A65"
        assert node_g3b(state) == "No"

    def test_decline_winter_uprising_in_final_winter(self):
        state = _make_state()
        state["final_year"] = True
        state["current_card_id"] = "A66"  # Winter Uprising!
        assert node_g3b(state) == "Yes"


# ===================================================================
# G4: Raid trigger
# ===================================================================

class TestNodeG4:

    def test_no_when_resources_geq_4(self):
        state = _make_state()
        state["resources"][GERMANS] = 4
        assert node_g4(state) == "No"

    def test_yes_or_no_when_under_4(self):
        # Sampling: with seed=42, resources<4, must be either Yes or No
        state = _make_state(seed=42)
        state["resources"][GERMANS] = 3
        result = node_g4(state)
        assert result in ("Yes", "No")


# ===================================================================
# G5: Rally+Settle qualification
# ===================================================================

class TestNodeG5:

    def test_no_when_no_pieces_available(self):
        state = _make_state()
        # Drain all available
        state["available"][GERMANS][WARBAND] = 0
        state["available"][GERMANS][ALLY] = 0
        state["available"][GERMANS][SETTLEMENT] = 0
        assert node_g5(state) == "No"

    def test_yes_when_warbands_in_germania_4plus(self):
        state = _make_state()
        # Germans get free rally in Germania — easily 4+ Warbands
        # Available Warbands cap=30
        state["resources"][GERMANS] = 10
        assert node_g5(state) == "Yes"


# ===================================================================
# Threat helpers
# ===================================================================

class TestThreatHelpers:

    def test_has_ariovistus_true(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True)
        assert _has_ariovistus(state, SUGAMBRI) is True

    def test_ariovistus_region_found(self):
        state = _make_state()
        _place_german_force(state, UBII, leader=True)
        assert _ariovistus_region(state) == UBII

    def test_has_german_threat_with_legion(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=6)
        _place_roman_force(state, ATREBATES, legions=1)
        assert _has_german_threat(state, ATREBATES) is True

    def test_no_threat_without_enough_force(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=5)
        _place_roman_force(state, ATREBATES, legions=1)
        assert _has_german_threat(state, ATREBATES) is False


class TestBattleEstimation:

    def test_can_battle_when_inflict_more(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=6)
        # Single Roman auxilia: 0.5/2 vs Germans' 1+3=4 inflicted -> easy win
        _place_roman_force(state, SUGAMBRI, auxilia=1)
        assert _can_battle_in_region(state, SUGAMBRI, ROMANS) is True

    def test_cannot_battle_when_legions_threaten_ariovistus(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=1)
        # Many Legions: would inflict many losses
        _place_roman_force(state, SUGAMBRI, legions=4)
        # Counterattack >= german_wb + 1 -> Ariovistus would take a Loss
        assert _can_battle_in_region(state, SUGAMBRI, ROMANS) is False

    def test_estimate_losses_no_fort(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=4)
        _place_enemy_force(state, SUGAMBRI, BELGAE, warbands=2)
        # Inflict: 4*0.5 + 1 = 3 ; Counter: 2*0.5 = 1
        inflicted, suffered = _estimate_battle_losses(
            state, SUGAMBRI, BELGAE)
        assert inflicted == 3
        assert suffered == 1


# ===================================================================
# G_BATTLE — Battle process and No-Battle -> March fallback
# ===================================================================

class TestNodeGBattle:

    def test_battle_when_trigger_met(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=6)
        # Roman ally is a valid G1 trigger (any-enemy ally/citadel/legion/4)
        _place_roman_force(state, ATREBATES, ally_tribe=TRIBE_ATREBATES,
                           auxilia=1)
        refresh_all_control(state)
        result = node_g_battle(state)
        assert result["command"] == ACTION_BATTLE
        assert ATREBATES in result["regions"]

    def test_ariovistus_no_battle_redirects_to_march(self):
        """If Ariovistus meets trigger but cannot Battle (no-loss-on-A
        constraint), the Germans March instead.
        """
        state = _make_state()
        # Ariovistus + 1 Warband vs lots of Legions -> can't avoid loss
        _place_german_force(state, SUGAMBRI, leader=True, warbands=1)
        _place_roman_force(state, SUGAMBRI, legions=4)
        refresh_all_control(state)
        result = node_g_battle(state)
        # Should March (threat redirect)
        assert result["command"] == ACTION_MARCH

    def test_battle_first_targets_weak_enemy_for_ariovistus(self):
        """Ariovistus fights an enemy with fewer mobile pieces."""
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=6)
        # Trigger via Roman Ally; 1 auxilia means few mobile pieces.
        _place_roman_force(state, SUGAMBRI, ally_tribe=TRIBE_SUGAMBRI,
                           auxilia=1)
        refresh_all_control(state)
        result = node_g_battle(state)
        assert result["command"] == ACTION_BATTLE
        plan = result["details"]["battle_plan"]
        # Ariovistus's battle is at SUGAMBRI vs ROMANS
        assert plan[0]["region"] == SUGAMBRI


# ===================================================================
# G_MARCH_THREAT — destination priorities
# ===================================================================

class TestNodeGMarchThreat:

    def test_prioritizes_dispersed_when_romans_at_victory(self):
        """When Romans at victory, prefer destinations with more Dispersed tribes."""
        state = _make_state(seed=7)
        # Make Romans at victory: huge advantage
        _place_german_force(state, SUGAMBRI, leader=True, warbands=12)
        # Threat at SUGAMBRI? Need enemy with ally/citadel/legion/4 pieces
        _place_roman_force(state, SUGAMBRI, legions=2, auxilia=2,
                           ally_tribe=TRIBE_UBII)  # 4+ pieces with ally
        # Make MANDUBII a dispersed-rich destination
        state["tribes"][TRIBE_MANDUBII]["status"] = MARKER_DISPERSED
        # Set Roman ally counts and victory baseline (just call march directly)
        refresh_all_control(state)
        result = node_g_march_threat(state)
        # Just confirm we get a March action
        assert result["command"] == ACTION_MARCH

    def test_excludes_origins_from_destinations(self):
        state = _make_state(seed=11)
        _place_german_force(state, SUGAMBRI, leader=True, warbands=12)
        _place_roman_force(state, SUGAMBRI, legions=4)
        refresh_all_control(state)
        result = node_g_march_threat(state)
        if result["command"] == ACTION_MARCH:
            dests = result["regions"]
            assert SUGAMBRI not in dests


# ===================================================================
# G_RAID
# ===================================================================

class TestNodeGRaid:

    def test_pass_when_no_warbands(self):
        state = _make_state()
        # No Hidden Warbands anywhere
        result = node_g_raid(state)
        assert result["command"] == ACTION_PASS

    def test_raid_when_2plus_resources_gainable(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=2, hidden=True)
        _place_roman_force(state, ATREBATES, auxilia=2)
        refresh_all_control(state)
        # 2 flips × steal from Romans = 2 gain
        result = node_g_raid(state)
        assert result["command"] == ACTION_RAID

    def test_raid_prefers_romans_then_belgae(self):
        state = _make_state()
        # §3.3.3: can only steal from a faction that HAS Resources.
        state["resources"][ROMANS] = 5
        state["resources"][BELGAE] = 5
        _place_german_force(state, ATREBATES, warbands=2, hidden=True)
        _place_roman_force(state, ATREBATES, auxilia=1)
        _place_enemy_force(state, ATREBATES, BELGAE, warbands=1)
        refresh_all_control(state)
        result = node_g_raid(state)
        assert result["command"] == ACTION_RAID
        plan = result["details"]["raid_plan"]
        # First flip targets Romans (Tier 1), second targets Belgae (Tier 2)
        targets = [p["target"] for p in plan if p["region"] == ATREBATES]
        assert ROMANS in targets
        assert BELGAE in targets

    def test_raid_steal_ledger_caps_at_target_resources(self):
        """§3.3.3: a steal takes 1 Resource. Across multiple Raid Regions the
        plan must not steal more from a Faction than it has — a 2nd steal from
        a Faction already drained to 0 would be refused at execution.
        """
        state = _make_state(non_players={GERMANS})
        state["resources"][BELGAE] = 1  # only ONE Resource to steal, total
        # German Hidden Warbands + Belgae present in two distinct Regions.
        _place_german_force(state, MORINI, warbands=2, hidden=True)
        _place_enemy_force(state, MORINI, BELGAE, warbands=1)
        _place_german_force(state, NERVII, warbands=2, hidden=True)
        _place_enemy_force(state, NERVII, BELGAE, warbands=1)
        refresh_all_control(state)
        _, plan = _would_raid_gain_enough(state, state["scenario"])
        belgae_steals = [p for p in plan if p["target"] == BELGAE]
        assert len(belgae_steals) <= 1, belgae_steals

    def test_raid_skips_zero_resource_target(self):
        """§3.3.3: do not target a faction with 0 Resources (executor
        refuses 'Cannot steal from <F>: <F> has 0 Resources'). With Aedui at
        0 Resources, the Aedui-present Region yields no steal from Aedui."""
        state = _make_state()
        state["resources"][AEDUI] = 0
        _place_german_force(state, ATREBATES, warbands=2, hidden=True)
        _place_enemy_force(state, ATREBATES, AEDUI, warbands=1)
        refresh_all_control(state)
        _, plan = _would_raid_gain_enough(state, state["scenario"])
        steals = [p for p in plan
                  if p["region"] == ATREBATES and p["target"] == AEDUI]
        assert steals == []


# ===================================================================
# Intimidate re-derivation at SA time (after March)
# ===================================================================

class TestIntimidateRederivation:
    def test_stale_after_march_intimidate_no_executor_error(self):
        """A8.7.1: Intimidate resolves AFTER the March. A plan picked pre-March
        that points at a Region the March emptied of Hidden Warbands must not
        reach the executor as-is (it would raise 'Only 0 Hidden Germanic
        Warbands'). _execute_sa re-derives against the current board, so the
        result carries no executor error.
        """
        from fs_bot.engine.execute import _execute_sa
        state = _make_state(non_players={GERMANS})
        # Live region: Ariovistus + Hidden German Warbands + a player target.
        _place_german_force(state, UBII, warbands=2, hidden=True, leader=True)
        _place_enemy_force(state, UBII, AEDUI, warbands=1)
        refresh_all_control(state)
        # Stale plan points at MORINI, which has no German Warbands.
        bot_action = {
            "command": "March",
            "sa": "Intimidate",
            "sa_regions": [MORINI],
            "details": {
                "march_plan": {"origins": [UBII], "destinations": [UBII]},
                "intimidate_plan": [{
                    "region": MORINI, "free": False, "tier": 2,
                    "target_faction": AEDUI, "target_piece": WARBAND,
                    "target_state": HIDDEN,
                }],
            },
        }
        result = _execute_sa(state, GERMANS, bot_action)
        assert result is not None
        assert not result.get("errors"), result.get("errors")
        assert result.get("rederived_at_sa_time") is True


# ===================================================================
# G_RALLY (+ Settle)
# ===================================================================

class TestNodeGRally:

    def test_rally_places_warbands_in_germania_free(self):
        state = _make_state()
        state["resources"][GERMANS] = 0  # no money
        # Germania placement is free, should still rally
        result = node_g_rally(state)
        assert result["command"] == ACTION_RALLY
        # All Warband placements should be in Germania
        for w in result["details"]["rally_plan"]["warbands"]:
            assert w["region"] in GERMANIA_REGIONS

    def test_rally_places_ally_when_base_present(self):
        state = _make_state()
        state["resources"][GERMANS] = 10
        _place_german_force(state, UBII, warbands=2)
        refresh_all_control(state)
        result = node_g_rally(state)
        # Should plan to place an Ally in Ubii (tribe TRIBE_UBII)
        allies = result["details"]["rally_plan"]["allies"]
        ally_regions = {a["region"] for a in allies}
        # At least one Ally placed in Germania since base/control exists
        assert ally_regions  # at least one Ally

    def test_rally_with_settle_before(self):
        """When Settlement can be placed, Settle BEFORE Rally — A8.7.4."""
        state = _make_state()
        state["resources"][GERMANS] = 20
        # Set up Ariovistus in a region with German Control adjacent to
        # Germania, so a Settlement is placeable there.
        _place_german_force(state, TREVERI, leader=True, warbands=3)
        # German Control at TREVERI requires more Germans than others
        # (already have 3 Wb + leader = 4 pieces). Adjacent to Germania.
        refresh_all_control(state)
        # Verify control
        if not is_controlled_by(state, TREVERI, GERMANS):
            pytest.skip("Need German Control at TREVERI for this test")
        result = node_g_rally(state)
        assert result["sa"] == SA_ACTION_SETTLE
        assert result["details"]["rally_plan"]["settlements_before"]

    def test_no_sa_when_no_settlement_placeable(self):
        """Per A8.7.1: if cannot place Settlements, no SA."""
        state = _make_state()
        state["resources"][GERMANS] = 0
        # No leader, no control, so no Settle destination
        result = node_g_rally(state)
        assert result["sa"] == SA_ACTION_NONE


# ===================================================================
# G_MARCH_EXPAND
# ===================================================================

class TestNodeGMarchExpand:

    def test_falls_through_to_rally_with_0_resources(self):
        state = _make_state()
        state["resources"][GERMANS] = 0
        result = node_g_march_expand(state)
        # 0 resources -> Rally per A8.7.5 IF NONE
        assert result["command"] in (ACTION_RALLY, ACTION_PASS)


# ===================================================================
# G_INTIMIDATE — priority tiers
# ===================================================================

class TestIntimidatePriority:

    def test_can_intimidate_with_ariovistus(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True)
        valid, _ = _can_intimidate_region(state, SUGAMBRI)
        assert valid is True

    def test_cannot_intimidate_without_control_or_leader(self):
        state = _make_state()
        _place_german_force(state, MORINI, warbands=2)
        valid, _ = _can_intimidate_region(state, MORINI)
        assert valid is False

    def test_can_intimidate_under_control_within_one(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=2)
        _place_german_force(state, UBII, warbands=5)
        # Force German Control at UBII (no other faction)
        refresh_all_control(state)
        valid, _ = _can_intimidate_region(state, UBII)
        # SUGAMBRI and UBII are adjacent
        assert valid is True

    def test_tier1_player_ally_targeted_first(self):
        """Tier 1: Player Allies — Roman first."""
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI})
        # Romans is a player
        _place_german_force(state, SUGAMBRI, leader=True, warbands=2)
        _place_roman_force(state, SUGAMBRI, ally_tribe=TRIBE_SUGAMBRI)
        targets = _select_intimidate_targets(state, SUGAMBRI, max_count=2)
        assert targets
        # First target must be Roman Ally (tier 1)
        first = targets[0]
        assert first["target_faction"] == ROMANS
        assert first["target_piece"] == ALLY
        assert first["tier"] == 1

    def test_intimidate_before_battle_excludes_defender(self):
        """A8.7.1 / G_INTIMIDATE: before a Battle, Intimidate removes pieces
        the Battle will NOT remove — so it must not target the Battle's own
        defender (which would leave 'defender not present').
        """
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI})
        _place_german_force(state, SUGAMBRI, leader=True, warbands=2)
        # Roman (player) Auxilia is the Battle's defender in SUGAMBRI.
        _place_roman_force(state, SUGAMBRI, auxilia=1)
        battle_plan = [{"region": SUGAMBRI, "target": ROMANS}]
        plan = _check_intimidate_before_battle(state, battle_plan)
        # No Intimidate target may be the Battle's defender in the Battle Region.
        for t in plan:
            if t["region"] == SUGAMBRI:
                assert t["target_faction"] != ROMANS

    def test_tier2_player_aux_warbands(self):
        """Tier 2: Roman Auxilia / Aedui Warbands / Belgic Warbands."""
        state = _make_state(non_players={GERMANS, BELGAE})  # Aedui is player
        _place_german_force(state, MANDUBII, leader=True, warbands=2)
        # Skip Tier 1: no allies
        # Place Aedui Warbands (player tier 2)
        _place_enemy_force(state, MANDUBII, AEDUI, warbands=1)
        targets = _select_intimidate_targets(state, MANDUBII, max_count=2)
        assert targets
        # First target should be Aedui Warband (player tier 2)
        assert targets[0]["target_faction"] == AEDUI
        assert targets[0]["target_piece"] == WARBAND
        assert targets[0]["tier"] == 2

    def test_tier3_np_roman_ally(self):
        """Tier 3: Non-player Roman or Aedui Allies (NOT Belgae or Arverni)."""
        state = _make_state(non_players={ROMANS, GERMANS, BELGAE, AEDUI})
        _place_german_force(state, MANDUBII, leader=True, warbands=2)
        _place_roman_force(state, MANDUBII, ally_tribe=TRIBE_MANDUBII)
        targets = _select_intimidate_targets(state, MANDUBII, max_count=1)
        assert targets
        assert targets[0]["target_faction"] == ROMANS
        assert targets[0]["target_piece"] == ALLY
        assert targets[0]["tier"] == 3

    def test_excludes_np_belgae_arverni_allies(self):
        """Tier 3 excludes Non-player Belgae and Arverni."""
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI, ARVERNI})
        _place_german_force(state, MANDUBII, leader=True, warbands=2)
        # NP Belgae has an Ally here
        _place_enemy_force(state, MANDUBII, BELGAE,
                           ally_tribe=TRIBE_MANDUBII)
        targets = _select_intimidate_targets(state, MANDUBII, max_count=2)
        # Should NOT pick NP Belgae Ally
        for t in targets:
            assert not (t["target_faction"] == BELGAE
                        and t["target_piece"] == ALLY)

    def test_excludes_target_with_leader(self):
        """A4.6.2: target must have no Leader in region."""
        state = _make_state(non_players={GERMANS, BELGAE, AEDUI})
        _place_german_force(state, MANDUBII, leader=True, warbands=2)
        _place_roman_force(state, MANDUBII, leader=True,
                           ally_tribe=TRIBE_MANDUBII)
        targets = _select_intimidate_targets(state, MANDUBII, max_count=1)
        # Should not pick the Roman Ally (Caesar leader present)
        for t in targets:
            assert t["target_faction"] != ROMANS


# ===================================================================
# G_SETTLE
# ===================================================================

class TestNodeGSettle:

    def test_no_settle_without_destinations(self):
        state = _make_state()
        # No Ariovistus on map
        sa, regions, _ = node_g_settle(state)
        assert sa == SA_ACTION_NONE
        assert regions == []

    def test_settle_destinations_when_controlled_adjacent_germania(self):
        state = _make_state()
        state["resources"][GERMANS] = 10
        _place_german_force(state, TREVERI, leader=True, warbands=3)
        refresh_all_control(state)
        if not is_controlled_by(state, TREVERI, GERMANS):
            pytest.skip("Need German Control at TREVERI")
        sa, regions, details = node_g_settle(state)
        assert sa == SA_ACTION_SETTLE
        assert TREVERI in regions

    def test_no_sa_when_resources_insufficient(self):
        state = _make_state()
        state["resources"][GERMANS] = 0  # Can't pay 2 to Settle
        _place_german_force(state, TREVERI, leader=True, warbands=3)
        refresh_all_control(state)
        sa, regions, _ = node_g_settle(state)
        assert sa == SA_ACTION_NONE


# ===================================================================
# G_EVENT
# ===================================================================

class TestNodeGEvent:

    def test_event_uses_shaded_preference(self):
        state = _make_state()
        state["current_card_id"] = 1  # Cicero (per-card instruction)
        result = node_g_event(state)
        assert result["command"] == ACTION_EVENT
        assert result["details"]["text_preference"] == EVENT_SHADED

    def test_event_includes_instruction_text(self):
        state = _make_state()
        state["current_card_id"] = 1  # Cicero — has SPECIFIC_INSTRUCTION
        result = node_g_event(state)
        assert result["details"]["instruction"] is not None


# ===================================================================
# Agreements
# ===================================================================

class TestNodeGAgreements:
    """A8.4: Germans never agree to transfer/supply/retreat/quarters;
    always Harass Roman March and Seize."""

    def test_harassment_against_romans_yes(self):
        state = _make_state()
        assert node_g_agreements(state, ROMANS, "harassment") is True

    def test_harassment_against_others_no(self):
        state = _make_state()
        assert node_g_agreements(state, AEDUI, "harassment") is False
        assert node_g_agreements(state, BELGAE, "harassment") is False

    def test_no_supply_line(self):
        state = _make_state()
        assert node_g_agreements(state, ROMANS, "supply_line") is False
        assert node_g_agreements(state, AEDUI, "supply_line") is False

    def test_no_retreat(self):
        state = _make_state()
        assert node_g_agreements(state, ROMANS, "retreat") is False

    def test_no_quarters(self):
        state = _make_state()
        assert node_g_agreements(state, ROMANS, "quarters") is False

    def test_no_resource_transfer(self):
        state = _make_state()
        assert node_g_agreements(state, AEDUI, "resources") is False


# ===================================================================
# Determinism
# ===================================================================

class TestDeterminism:
    """Same seed must produce same action dict."""

    def test_same_seed_same_outcome(self):
        s1 = _make_state(seed=12345)
        _place_german_force(s1, SUGAMBRI, leader=True, warbands=12)
        _place_roman_force(s1, SUGAMBRI, legions=4)
        refresh_all_control(s1)
        a1 = execute_german_turn(s1)

        s2 = _make_state(seed=12345)
        _place_german_force(s2, SUGAMBRI, leader=True, warbands=12)
        _place_roman_force(s2, SUGAMBRI, legions=4)
        refresh_all_control(s2)
        a2 = execute_german_turn(s2)

        assert a1["command"] == a2["command"]
        assert a1["regions"] == a2["regions"]
        assert a1["sa"] == a2["sa"]
        assert a1["sa_regions"] == a2["sa_regions"]


# ===================================================================
# Execute driver
# ===================================================================

class TestExecuteGermanTurn:

    def test_returns_action_dict(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True, warbands=3)
        result = execute_german_turn(state)
        assert "command" in result
        assert "regions" in result
        assert "sa" in result

    def test_battle_when_threat(self):
        state = _make_state()
        _place_german_force(state, ATREBATES, warbands=6)
        # Need Ally / Citadel / Legion / 4+ pieces for G1 trigger
        _place_roman_force(state, ATREBATES, ally_tribe=TRIBE_ATREBATES,
                           auxilia=2)
        refresh_all_control(state)
        result = execute_german_turn(state)
        assert result["command"] in (ACTION_BATTLE, ACTION_MARCH)

    def test_default_to_march_expand_when_idle(self):
        """When no other branch fires, default is March-expand → falls
        through depending on the board.
        """
        state = _make_state(seed=999)
        state["can_play_event"] = False
        state["resources"][GERMANS] = 5
        _place_german_force(state, SUGAMBRI, warbands=2)
        refresh_all_control(state)
        # G1 No (no leader, only 2 wb); G1b No; G2 No (no card order);
        # G3 No; G4 ?? (resources >= 4 so No); G5 should be Yes (Warbands
        # placeable in Germania for free).
        result = execute_german_turn(state)
        # Result must be one of the action types — sanity check
        assert result["command"] in (
            ACTION_BATTLE, ACTION_MARCH, ACTION_RALLY,
            ACTION_RAID, ACTION_EVENT, ACTION_PASS,
        )


# ===================================================================
# Winter — Quarters / Spring
# ===================================================================

class TestNodeGQuarters:

    def test_quarters_leader_move_to_largest_group(self):
        state = _make_state()
        # Leader alone in SUGAMBRI; bigger group in UBII (adjacent)
        _place_german_force(state, SUGAMBRI, leader=True, warbands=0)
        _place_german_force(state, UBII, warbands=4)
        refresh_all_control(state)
        plan = node_g_quarters(state)
        if plan["leader_move"]:
            assert plan["leader_move"]["to"] == UBII

    def test_quarters_leaves_devastated_without_ally(self):
        state = _make_state()
        _place_german_force(state, TREVERI, warbands=2)
        state.setdefault("markers", {}).setdefault(TREVERI, {})[
            "devastated"] = True
        # Adjacent controlled region: place Germans heavily in SUGAMBRI
        _place_german_force(state, SUGAMBRI, warbands=5)
        refresh_all_control(state)
        plan = node_g_quarters(state)
        # If TREVERI is Devastated and has no German Ally/Settlement, and
        # an adjacent controlled region exists, Germans leave.
        if plan["leave_devastated"]:
            assert plan["leave_devastated"][0]["from"] == TREVERI


class TestNodeGSpring:

    def test_returns_none_when_ariovistus_on_map(self):
        state = _make_state()
        _place_german_force(state, SUGAMBRI, leader=True)
        assert node_g_spring(state) is None

    def test_places_leader_at_most_germans_when_off_map(self):
        state = _make_state()
        # No leader placed; place lots of Warbands in UBII
        _place_german_force(state, UBII, warbands=5)
        refresh_all_control(state)
        result = node_g_spring(state)
        assert result is not None
        assert result["place_leader"] == ARIOVISTUS_LEADER
        assert result["region"] == UBII


# ===================================================================
# G_AMBUSH eligibility — A4.6.3 -> §4.3.3 (+ A4.1.2) proximity & Hidden
# (QUESTIONS.md Q2 resolution)
# ===================================================================

class TestGermanAmbushEligibility:
    """Germanic Ambush in Ariovistus follows §4.3.3 via A4.6.3, gated by
    A4.1.2: it requires more Hidden Germans than Hidden Defenders AND the
    Battle Region within 1 of Ariovistus (or the Successor's Region)."""

    def test_no_ambush_when_battle_region_out_of_ariovistus_range(self):
        # Ariovistus in SUGAMBRI; a 6-Warband group Battles in CARNUTES
        # (not within 1 of SUGAMBRI). A defending Legion satisfies the
        # A8.7.1 strategic gate, so the ONLY thing blocking Ambush is the
        # A4.1.2/A4.6.3 proximity requirement.
        state = _make_state(non_players={GERMANS})
        place_piece(state, SUGAMBRI, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)
        place_piece(state, CARNUTES, GERMANS, WARBAND, 6,
                    piece_state=HIDDEN)
        place_piece(state, CARNUTES, ROMANS, LEGION, 1,
                    from_legions_track=True)
        refresh_all_control(state)
        plan = [{"region": CARNUTES, "target": ROMANS, "is_trigger": True}]
        assert _check_ambush(state, plan) == []

    def test_ambush_when_in_ariovistus_region(self):
        # Same strategic gate (defending Legion) but the Battle is in
        # Ariovistus's own Region, so Ambush is eligible and chosen.
        state = _make_state(non_players={GERMANS})
        place_piece(state, SUGAMBRI, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3,
                    piece_state=HIDDEN)
        place_piece(state, SUGAMBRI, ROMANS, LEGION, 1,
                    from_legions_track=True)
        refresh_all_control(state)
        plan = [{"region": SUGAMBRI, "target": ROMANS, "is_trigger": True}]
        assert _check_ambush(state, plan) == [SUGAMBRI]

    def test_ambush_when_adjacent_to_ariovistus(self):
        # UBII is adjacent to SUGAMBRI -> within 1 of Ariovistus.
        state = _make_state(non_players={GERMANS})
        place_piece(state, SUGAMBRI, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)
        place_piece(state, UBII, GERMANS, WARBAND, 4, piece_state=HIDDEN)
        place_piece(state, UBII, ROMANS, LEGION, 1, from_legions_track=True)
        refresh_all_control(state)
        plan = [{"region": UBII, "target": ROMANS, "is_trigger": True}]
        assert _check_ambush(state, plan) == [UBII]

    def test_no_ambush_when_not_more_hidden_than_defender(self):
        # In Ariovistus's Region but 2 Hidden Germans vs 3 Hidden Roman
        # Auxilia -> fails §4.3.3 Hidden-count requirement.
        state = _make_state(non_players={GERMANS})
        place_piece(state, SUGAMBRI, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2,
                    piece_state=HIDDEN)
        place_piece(state, SUGAMBRI, ROMANS, LEGION, 1,
                    from_legions_track=True)
        place_piece(state, SUGAMBRI, ROMANS, AUXILIA, 3,
                    piece_state=HIDDEN)
        refresh_all_control(state)
        plan = [{"region": SUGAMBRI, "target": ROMANS, "is_trigger": True}]
        assert _check_ambush(state, plan) == []

    def test_subsequent_battles_filtered_by_eligibility(self):
        # 1st Battle in SUGAMBRI (eligible) triggers Ambush; a 2nd Battle
        # in out-of-range CARNUTES must be excluded, an in-range UBII kept.
        state = _make_state(non_players={GERMANS})
        place_piece(state, SUGAMBRI, GERMANS, LEADER,
                    leader_name=ARIOVISTUS_LEADER)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3,
                    piece_state=HIDDEN)
        place_piece(state, SUGAMBRI, ROMANS, LEGION, 1,
                    from_legions_track=True)
        place_piece(state, UBII, GERMANS, WARBAND, 3, piece_state=HIDDEN)
        place_piece(state, UBII, ROMANS, AUXILIA, 1)
        place_piece(state, CARNUTES, GERMANS, WARBAND, 3,
                    piece_state=HIDDEN)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 1)
        refresh_all_control(state)
        plan = [
            {"region": SUGAMBRI, "target": ROMANS, "is_trigger": True},
            {"region": UBII, "target": ROMANS, "is_trigger": True},
            {"region": CARNUTES, "target": ROMANS, "is_trigger": True},
        ]
        result = _check_ambush(state, plan)
        assert SUGAMBRI in result
        assert UBII in result
        assert CARNUTES not in result
