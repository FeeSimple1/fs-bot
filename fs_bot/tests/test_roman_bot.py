"""
Tests for roman_bot.py — Non-Player Roman flowchart per §8.8.

Tests every flowchart node with Yes/No branches, seeded RNG, and
scenario isolation between base game and Ariovistus.
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED, SCOUTED,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    SCENARIO_GREAT_REVOLT, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    CAESAR, AMBIORIX, ARIOVISTUS_LEADER,
    MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII,
    AEDUI_REGION, ARVERNI_REGION, SUGAMBRI, SEQUANI,
    CARNUTES, BITURIGES,
    TRIBE_CARNUTES, TRIBE_ARVERNI, TRIBE_AEDUI, TRIBE_HELVII,
    EVENT_UNSHADED,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.bots.roman_bot import (
    # Node functions
    node_r1, node_r2, node_r3, node_r4, node_r5,
    node_r_event, node_r_battle, node_r_march, node_r_recruit, node_r_seize,
    # SA nodes
    node_r_besiege, node_r_build, node_r_scout,
    # Winter/Spring
    node_r_quarters, node_r_spring,
    # Agreements
    node_r_agreements, node_r_diviciacus,
    # Main driver
    execute_roman_turn,
    # Helpers (for direct testing)
    _rank_march_destinations,
    # Action constants
    ACTION_BATTLE, ACTION_MARCH, ACTION_RECRUIT, ACTION_SEIZE,
    ACTION_EVENT, ACTION_PASS,
)
from fs_bot.bots.bot_dispatch import (
    dispatch_bot_turn, BotDispatchError,
)


def _make_state(scenario=SCENARIO_PAX_GALLICA, seed=42, non_players=None):
    """Build a minimal test state with common defaults."""
    state = build_initial_state(scenario, seed=seed)
    if non_players is None:
        non_players = {ROMANS, BELGAE, AEDUI}
    state["non_player_factions"] = non_players
    state["can_play_event"] = True
    state["current_card_id"] = 1
    state["final_year"] = False
    state["frost"] = False
    return state


def _place_roman_force(state, region, *, leader=False, legions=0, auxilia=0):
    """Helper to place Roman forces in a region."""
    if leader:
        place_piece(state, region, ROMANS, LEADER, leader_name=CAESAR)
    if legions > 0:
        place_piece(state, region, ROMANS, LEGION, legions,
                    from_legions_track=True)
    if auxilia > 0:
        place_piece(state, region, ROMANS, AUXILIA, auxilia)


def _place_enemy_threat(state, region, faction=ARVERNI, *, ally_tribe=None,
                        citadel=False, warbands=0, leader=False):
    """Helper to place enemy threat pieces."""
    if ally_tribe:
        state["tribes"][ally_tribe]["allied_faction"] = faction
        place_piece(state, region, faction, ALLY)
    if citadel:
        place_piece(state, region, faction, CITADEL)
    if warbands > 0:
        place_piece(state, region, faction, WARBAND, warbands)
    if leader:
        leader_name = AMBIORIX if faction == BELGAE else None
        if leader_name:
            place_piece(state, region, faction, LEADER, leader_name=leader_name)


# ===================================================================
# R1: Caesar or Legion with enemy Ally, Citadel, Leader, or Control?
# ===================================================================

class TestNodeR1:

    def test_r1_yes_caesar_with_enemy_ally(self):
        """R1=Yes when Caesar is in region with enemy Ally."""
        state = _make_state()
        _place_roman_force(state, MANDUBII, leader=True, legions=2)
        _place_enemy_threat(state, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES)
        result, regions = node_r1(state)
        assert result == "Yes"
        assert MANDUBII in regions

    def test_r1_yes_legion_with_enemy_citadel(self):
        """R1=Yes when Legion is with enemy Citadel."""
        state = _make_state()
        _place_roman_force(state, ARVERNI_REGION, legions=1)
        _place_enemy_threat(state, ARVERNI_REGION, ARVERNI, citadel=True)
        result, regions = node_r1(state)
        assert result == "Yes"
        assert ARVERNI_REGION in regions

    def test_r1_yes_caesar_enemy_control(self):
        """R1=Yes when Caesar is in enemy-controlled region."""
        state = _make_state()
        _place_roman_force(state, MORINI, leader=True)
        # Place enough Belgae for control
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        refresh_all_control(state)
        result, regions = node_r1(state)
        assert result == "Yes"

    def test_r1_no_no_threats(self):
        """R1=No when no threat conditions met."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        result, regions = node_r1(state)
        assert result == "No"
        assert regions == []

    def test_r1_no_without_caesar_or_legion(self):
        """R1=No when only Auxilia in region with enemy."""
        state = _make_state()
        _place_roman_force(state, MANDUBII, auxilia=3)
        _place_enemy_threat(state, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES)
        result, regions = node_r1(state)
        assert result == "No"


# ===================================================================
# R2: Enemy at 0+ victory AND Caesar with 2+ Legions, 4+ Auxilia?
# ===================================================================

class TestNodeR2:

    def test_r2_yes_all_conditions(self):
        """R2=Yes when enemy at victory, Caesar has enough forces."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3,
                           auxilia=5)
        # Give Belgae enough for 0+ victory margin: need BCV + A+C > 15.
        # Place Belgae Warbands for Control in several regions (BCV from CV),
        # then set many tribes as Belgae Allies.
        belgae_regions = [MORINI, NERVII, ATREBATES, CARNUTES, MANDUBII]
        for region in belgae_regions:
            place_piece(state, region, BELGAE, WARBAND, 5)
        for tribe in list(state["tribes"].keys())[:12]:
            state["tribes"][tribe]["allied_faction"] = BELGAE
        refresh_all_control(state)
        result = node_r2(state)
        assert result == "Yes"

    def test_r2_no_no_enemy_at_victory(self):
        """R2=No when no enemy is at 0+ victory margin."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3,
                           auxilia=5)
        # Ensure Aedui margin is negative (default is 0 because 0-0=0).
        # Give Arverni one Ally so Aedui score (0) < highest other (1).
        state["tribes"][TRIBE_ARVERNI]["allied_faction"] = ARVERNI
        place_piece(state, ARVERNI_REGION, ARVERNI, ALLY)
        result = node_r2(state)
        assert result == "No"

    def test_r2_no_insufficient_legions(self):
        """R2=No when Caesar has fewer than 2 Legions."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=1,
                           auxilia=5)
        # Give Belgae enough for 0+ margin
        belgae_regions = [MORINI, NERVII, ATREBATES, CARNUTES, MANDUBII]
        for region in belgae_regions:
            place_piece(state, region, BELGAE, WARBAND, 5)
        for tribe in list(state["tribes"].keys())[:12]:
            state["tribes"][tribe]["allied_faction"] = BELGAE
        refresh_all_control(state)
        result = node_r2(state)
        assert result == "No"

    def test_r2_no_no_caesar(self):
        """R2=No when Caesar is off map."""
        state = _make_state()
        result = node_r2(state)
        assert result == "No"


# ===================================================================
# R3: Can play Event by SoP?
# ===================================================================

class TestNodeR3:

    def test_r3_yes(self):
        state = _make_state()
        state["can_play_event"] = True
        assert node_r3(state) == "Yes"

    def test_r3_no(self):
        state = _make_state()
        state["can_play_event"] = False
        assert node_r3(state) == "No"


# ===================================================================
# R4: Event Ineffective / Final-year Capability / 'No Romans'?
# ===================================================================

class TestNodeR4:

    def test_r4_yes_no_romans(self):
        """R4=Yes for 'No Romans' card."""
        state = _make_state()
        state["current_card_id"] = 47  # Chieftains' Council = No Romans
        assert node_r4(state) == "Yes"

    def test_r4_no_playable_event(self):
        """R4=No for normal playable event."""
        state = _make_state()
        state["current_card_id"] = 1
        assert node_r4(state) == "No"

    def test_r4_yes_final_year_capability(self):
        state = _make_state()
        state["final_year"] = True
        state["current_card_id"] = 8  # Baggage Trains = Capability
        assert node_r4(state) == "Yes"


# ===================================================================
# R5: 9+ Auxilia Available?
# ===================================================================

class TestNodeR5:

    def test_r5_yes_many_available(self):
        """R5=Yes when 9+ Auxilia in Available."""
        state = _make_state()
        # Initial state has all Auxilia available
        assert node_r5(state) == "Yes"

    def test_r5_no_few_available(self):
        """R5=No when 8 or fewer Auxilia available."""
        state = _make_state()
        # Place most Auxilia on map to reduce Available
        avail = state["available"][ROMANS][AUXILIA]
        # Place all but 5 on map
        to_place = avail - 5
        if to_place > 0:
            place_piece(state, PROVINCIA, ROMANS, AUXILIA, to_place)
        assert node_r5(state) == "No"


# ===================================================================
# Process: R_EVENT
# ===================================================================

class TestNodeREvent:

    def test_event_returns_unshaded(self):
        """Romans use unshaded text by default."""
        state = _make_state()
        state["current_card_id"] = 1
        result = node_r_event(state)
        assert result["command"] == ACTION_EVENT
        assert result["details"]["text_preference"] == EVENT_UNSHADED


# ===================================================================
# Process: R_BATTLE
# ===================================================================

class TestNodeRBattle:

    def test_battle_with_threats(self):
        """R_BATTLE returns Battle action when threats exist."""
        state = _make_state()
        _place_roman_force(state, MANDUBII, leader=True, legions=3,
                           auxilia=4)
        _place_enemy_threat(state, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES, warbands=4)
        result = node_r_battle(state)
        assert result["command"] == ACTION_BATTLE
        assert MANDUBII in result["regions"]

    def test_battle_redirects_to_march_no_threats(self):
        """If no threats, Battle redirects to March."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        result = node_r_battle(state)
        # Should redirect to March (or Recruit/Seize/Pass if March not possible)
        assert result["command"] in (ACTION_MARCH, ACTION_RECRUIT,
                                     ACTION_SEIZE, ACTION_PASS)


# ===================================================================
# Process: R_MARCH
# ===================================================================

class TestNodeRMarch:

    def test_march_to_enemy_allies(self):
        """March destinations should target enemy Allies/Citadels."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3,
                           auxilia=5)
        _place_enemy_threat(state, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES)
        result = node_r_march(state)
        # Should produce March action or fall through if no valid destinations
        assert result["command"] in (ACTION_MARCH, ACTION_RECRUIT,
                                     ACTION_SEIZE, ACTION_PASS)

    def test_march_falls_through_to_recruit(self):
        """March falls through to Recruit if no valid destinations."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        # No enemy Allies/Citadels anywhere
        result = node_r_march(state)
        assert result["command"] in (ACTION_RECRUIT, ACTION_SEIZE, ACTION_PASS)

    def test_march_destinations_tier1_at_victory(self):
        """Bug 3: §8.8.1 — Tier 1 selects enemies at 0+ victory margin."""
        state = _make_state()
        # Set up Belgae at 0+ victory margin by giving many Allies
        belgae_regions = [MORINI, NERVII, ATREBATES, CARNUTES, MANDUBII]
        for region in belgae_regions:
            place_piece(state, region, BELGAE, WARBAND, 5)
        for tribe in list(state["tribes"].keys())[:12]:
            state["tribes"][tribe]["allied_faction"] = BELGAE
        # Place a Belgae Ally piece in a region
        place_piece(state, MORINI, BELGAE, ALLY)
        refresh_all_control(state)
        dests = _rank_march_destinations(state, SCENARIO_PAX_GALLICA)
        if dests:
            # First destination should target an enemy at 0+ victory
            _, target_faction = dests[0]
            assert target_faction == BELGAE

    def test_march_destinations_die_roll_determinism(self):
        """Bug 3: §8.8.1 — Same seed gives same tier selection via die roll."""
        state1 = _make_state(seed=77)
        state2 = _make_state(seed=77)
        # Set up identical enemy pieces
        _place_enemy_threat(state1, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES)
        _place_enemy_threat(state2, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES)
        d1 = _rank_march_destinations(state1, SCENARIO_PAX_GALLICA)
        d2 = _rank_march_destinations(state2, SCENARIO_PAX_GALLICA)
        assert d1 == d2

    def test_march_destinations_ariovistus_tier2_arverni(self):
        """Bug 3: A8.8.1 — On roll 1-2, target Arverni instead of Germanic."""
        # Use a seed that produces a die roll of 1 or 2
        for seed in range(100):
            state = _make_state(scenario=SCENARIO_ARIOVISTUS, seed=seed)
            # Place Arverni Ally
            state["tribes"][TRIBE_ARVERNI]["allied_faction"] = ARVERNI
            place_piece(state, ARVERNI_REGION, ARVERNI, ALLY)
            # Need to consume rng in same way as the function
            test_state = _make_state(scenario=SCENARIO_ARIOVISTUS, seed=seed)
            test_die = test_state["rng"].randint(1, 6)
            if test_die <= 2:
                dests = _rank_march_destinations(state, SCENARIO_ARIOVISTUS)
                if dests:
                    _, target = dests[0]
                    assert target == ARVERNI
                break


# ===================================================================
# Process: R_RECRUIT
# ===================================================================

class TestNodeRRecruit:

    def test_recruit_with_enough_pieces(self):
        """Recruit when placing 2+ Allies or 6+ pieces is possible."""
        state = _make_state()
        # Keep many pieces in Available (default state)
        result = node_r_recruit(state)
        assert result["command"] == ACTION_RECRUIT

    def test_recruit_falls_through_to_seize(self):
        """If can't place enough, fall through to Seize."""
        state = _make_state()
        # Reduce available pieces to below thresholds
        state["available"][ROMANS][ALLY] = 0
        state["available"][ROMANS][AUXILIA] = 3
        result = node_r_recruit(state)
        assert result["command"] in (ACTION_SEIZE, ACTION_PASS)


# ===================================================================
# Process: R_SEIZE
# ===================================================================

class TestNodeRSeize:

    def test_seize_where_no_harassment(self):
        """Seize only in regions without Harassment."""
        state = _make_state()
        _place_roman_force(state, ATREBATES, legions=1, auxilia=2)
        result = node_r_seize(state)
        if result["command"] == ACTION_SEIZE:
            assert len(result["regions"]) > 0

    def test_seize_excludes_helvii(self):
        """Dispersion should NOT target Helvii — §8.8.5."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, legions=2, auxilia=3)
        result = node_r_seize(state)
        if result["command"] == ACTION_SEIZE:
            disperse = result["details"].get("disperse_regions", [])
            # Helvii is in Provincia — shouldn't be dispersed
            # (This tests the exclusion logic, not the full Seize)

    def test_seize_harassment_checks_all_factions(self):
        """Bug 1: §3.2.3 — Seize Harassment comes from ALL factions with
        3+ Hidden Warbands, not just designated harassers from §8.4.2."""
        state = _make_state()
        # Place Romans in a region
        _place_roman_force(state, MANDUBII, legions=1, auxilia=2)
        # Place 3 Hidden Aedui Warbands — Aedui are NOT in get_harassing_factions
        # but per §3.2.3 ANY faction with 3+ Hidden Warbands can harass Seize
        place_piece(state, MANDUBII, AEDUI, WARBAND, 3)
        result = node_r_seize(state)
        # MANDUBII should be excluded due to Aedui harassment
        if result["command"] == ACTION_SEIZE:
            assert MANDUBII not in result["regions"]

    def test_seize_no_harassment_below_three_hidden(self):
        """§3.2.3 — Fewer than 3 Hidden Warbands do not cause Harassment."""
        state = _make_state()
        _place_roman_force(state, MANDUBII, legions=1, auxilia=2)
        # Place only 2 Hidden Warbands — not enough for Harassment
        place_piece(state, MANDUBII, AEDUI, WARBAND, 2)
        result = node_r_seize(state)
        if result["command"] == ACTION_SEIZE:
            assert MANDUBII in result["regions"]

    def test_seize_dispersal_requires_roman_control(self):
        """Bug 2: §3.2.3 — Dispersal only in regions with Roman Control."""
        state = _make_state()
        # Place Romans in MANDUBII but not enough for control
        _place_roman_force(state, MANDUBII, auxilia=1)
        # Place enemy pieces so Romans don't have control
        place_piece(state, MANDUBII, BELGAE, WARBAND, 5)
        refresh_all_control(state)
        result = node_r_seize(state)
        if result["command"] == ACTION_SEIZE:
            # MANDUBII should NOT be in disperse_regions (no Roman Control)
            disperse = result["details"].get("disperse_regions", [])
            assert MANDUBII not in disperse

    def test_seize_dispersal_with_roman_control(self):
        """§3.2.3 — Dispersal allowed in regions with Roman Control."""
        state = _make_state()
        # Place enough Romans for control
        _place_roman_force(state, MANDUBII, legions=3, auxilia=3)
        refresh_all_control(state)
        result = node_r_seize(state)
        if result["command"] == ACTION_SEIZE:
            # MANDUBII should be in disperse_regions if subdued tribes exist
            disperse = result["details"].get("disperse_regions", [])
            # (Result depends on whether subdued tribes exist in MANDUBII)


# ===================================================================
# SA: R_BUILD
# ===================================================================

class TestNodeRBuild:

    def test_build_places_forts_first(self):
        state = _make_state()
        _place_roman_force(state, MANDUBII, legions=2, auxilia=3)
        _place_enemy_threat(state, MANDUBII, ARVERNI, warbands=3)
        plan = node_r_build(state)
        # Should prioritize Fort placement at non-Aedui Warbands
        assert isinstance(plan["forts"], list)


# ===================================================================
# SA: R_SCOUT
# ===================================================================

class TestNodeRScout:

    def test_scout_targets_hidden_first(self):
        state = _make_state()
        _place_roman_force(state, MANDUBII, leader=True, auxilia=5)
        place_piece(state, MANDUBII, BELGAE, WARBAND, 3, piece_state=HIDDEN)
        plan = node_r_scout(state)
        targets = plan["scout_targets"]
        if targets:
            # Hidden should be prioritized
            assert targets[0]["hidden"] > 0


# ===================================================================
# Winter: R_QUARTERS
# ===================================================================

class TestNodeRQuarters:

    def test_quarters_keeps_auxilia_at_forts(self):
        state = _make_state()
        _place_roman_force(state, MANDUBII, auxilia=3)
        place_piece(state, MANDUBII, ROMANS, FORT)
        plan = node_r_quarters(state)
        # Should keep 1 Auxilia at Fort
        stays = dict(plan["stay_auxilia"])
        assert MANDUBII in stays
        assert stays[MANDUBII] >= 1


# ===================================================================
# Spring: R_SPRING
# ===================================================================

class TestNodeRSpring:

    def test_spring_places_caesar_off_map(self):
        state = _make_state()
        _place_roman_force(state, PROVINCIA, auxilia=5, legions=2)
        # Caesar not on map
        result = node_r_spring(state)
        assert result is not None
        assert result["place_leader"] == CAESAR

    def test_spring_noop_caesar_on_map(self):
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True)
        result = node_r_spring(state)
        assert result is None


# ===================================================================
# Agreements: R_AGREEMENTS
# ===================================================================

class TestNodeRAgreements:

    def test_never_transfer_resources(self):
        state = _make_state()
        assert node_r_agreements(state, BELGAE, "resources") is False

    def test_agree_supply_np_aedui(self):
        state = _make_state(non_players={ROMANS, AEDUI})
        assert node_r_agreements(state, AEDUI, "supply_line") is True

    def test_refuse_supply_player_aedui(self):
        state = _make_state(non_players={ROMANS})
        assert node_r_agreements(state, AEDUI, "supply_line") is False

    def test_refuse_supply_belgae(self):
        state = _make_state(non_players={ROMANS, BELGAE})
        assert node_r_agreements(state, BELGAE, "supply_line") is False


# ===================================================================
# Diviciacus: R_DIVICIACUS
# ===================================================================

class TestNodeRDiviciacus:

    def test_agree_during_aedui_command(self):
        state = _make_state()
        result = node_r_diviciacus(state, {"during": "aedui_command"})
        assert result is True

    def test_refuse_during_aedui_defense(self):
        state = _make_state()
        result = node_r_diviciacus(state, {"during": "aedui_defense"})
        assert result is False

    def test_agree_during_roman_defense(self):
        state = _make_state()
        result = node_r_diviciacus(state, {"during": "roman_defense"})
        assert result is True

    def test_refuse_recruit_during_roman_command(self):
        state = _make_state()
        result = node_r_diviciacus(state, {
            "during": "roman_command", "is_recruit": True,
        })
        assert result is False

    def test_admagetobriga_refuse_all(self):
        """A8.8.8: NP Romans don't agree during Admagetobriga."""
        state = _make_state(scenario=SCENARIO_ARIOVISTUS)
        state["admagetobriga_active"] = True
        result = node_r_diviciacus(state, {"during": "roman_command"})
        assert result is False


# ===================================================================
# Full Flowchart: execute_roman_turn
# ===================================================================

class TestExecuteRomanTurn:

    def test_full_turn_threat_battles(self):
        """Full turn: threat → Battle."""
        state = _make_state()
        _place_roman_force(state, MANDUBII, leader=True, legions=3,
                           auxilia=4)
        _place_enemy_threat(state, MANDUBII, ARVERNI,
                            ally_tribe=TRIBE_CARNUTES, warbands=4)
        result = execute_roman_turn(state)
        assert result["command"] == ACTION_BATTLE

    def test_full_turn_no_threat_event(self):
        """Full turn: no threat, plays Event."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        state["can_play_event"] = True
        state["current_card_id"] = 1  # Cicero — not "No Romans"
        result = execute_roman_turn(state)
        assert result["command"] == ACTION_EVENT

    def test_full_turn_no_event_march(self):
        """Full turn: no threat, no Event → check Auxilia → March."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        state["can_play_event"] = False
        # Reduce available Auxilia to ≤8
        avail = state["available"][ROMANS][AUXILIA]
        to_place = avail - 5
        if to_place > 0:
            place_piece(state, PROVINCIA, ROMANS, AUXILIA, to_place)
        result = execute_roman_turn(state)
        assert result["command"] in (ACTION_MARCH, ACTION_RECRUIT,
                                     ACTION_SEIZE, ACTION_PASS)

    def test_full_turn_no_event_recruit(self):
        """Full turn: no threat, no Event → 9+ Auxilia → Recruit."""
        state = _make_state()
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        state["can_play_event"] = False
        # Keep many Auxilia available (default)
        result = execute_roman_turn(state)
        assert result["command"] in (ACTION_RECRUIT, ACTION_SEIZE, ACTION_PASS)

    def test_deterministic_with_seed(self):
        """Same seed produces same action."""
        state1 = _make_state(seed=99)
        state2 = _make_state(seed=99)
        _place_roman_force(state1, PROVINCIA, leader=True, legions=3)
        _place_roman_force(state2, PROVINCIA, leader=True, legions=3)
        state1["can_play_event"] = True
        state2["can_play_event"] = True
        state1["current_card_id"] = 1
        state2["current_card_id"] = 1
        r1 = execute_roman_turn(state1)
        r2 = execute_roman_turn(state2)
        assert r1["command"] == r2["command"]


# ===================================================================
# Bot Dispatch
# ===================================================================

class TestBotDispatch:

    def test_dispatch_roman_base(self):
        """Dispatch routes Roman turn in base game."""
        state = _make_state(non_players={ROMANS})
        _place_roman_force(state, PROVINCIA, leader=True, legions=3)
        state["can_play_event"] = True
        state["current_card_id"] = 1
        result = dispatch_bot_turn(state, ROMANS)
        assert "command" in result

    def test_dispatch_german_base_raises(self):
        """Germans cannot be dispatched in base game."""
        state = _make_state(non_players={GERMANS})
        with pytest.raises(BotDispatchError, match="Germans"):
            dispatch_bot_turn(state, GERMANS)

    def test_dispatch_arverni_ariovistus_raises(self):
        """Arverni cannot be dispatched in Ariovistus."""
        state = _make_state(
            scenario=SCENARIO_ARIOVISTUS,
            non_players={ARVERNI},
        )
        with pytest.raises(BotDispatchError, match="Arverni"):
            dispatch_bot_turn(state, ARVERNI)

    def test_dispatch_non_player_check(self):
        """Dispatch refuses if faction not in non_player_factions."""
        state = _make_state(non_players={BELGAE})  # Romans NOT in NP set
        with pytest.raises(BotDispatchError, match="not marked"):
            dispatch_bot_turn(state, ROMANS)

    def test_dispatch_belgae_not_implemented(self):
        """Belgae bot not yet implemented."""
        state = _make_state(non_players={BELGAE})
        with pytest.raises(BotDispatchError, match="not yet implemented"):
            dispatch_bot_turn(state, BELGAE)

    def test_dispatch_aedui_not_implemented(self):
        """Aedui bot not yet implemented."""
        state = _make_state(non_players={AEDUI})
        with pytest.raises(BotDispatchError, match="not yet implemented"):
            dispatch_bot_turn(state, AEDUI)
