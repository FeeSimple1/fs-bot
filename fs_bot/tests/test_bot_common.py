"""
Tests for bot_common.py — Shared NP behaviors per §8.1–8.4.

Tests cover every shared behavior with base and Ariovistus scenarios
using seeded RNG for determinism.
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED, SCOUTED,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    EVENT_UNSHADED, EVENT_SHADED,
    CAESAR, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    TRIBE_REMI, TRIBE_CARNUTES, TRIBE_AEDUI, TRIBE_ARVERNI,
    MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII,
    AEDUI_REGION, ARVERNI_REGION, SUGAMBRI,
    CAPABILITY_CARDS,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.bots.bot_common import (
    # Limited Command
    upgrade_limited_command,
    # Dual Use
    get_dual_use_preference,
    # Event decisions
    is_no_faction_event, is_final_year_capability, should_decline_event,
    get_event_instruction,
    # Random
    random_select, random_select_multiple, roll_die,
    # Frost
    is_frost_active, check_frost_restriction,
    # Place/Remove ordering
    get_enemy_piece_target_order, get_own_loss_order,
    get_flippable_target_order, get_own_flippable_loss_order,
    is_ally_in_city_or_remi,
    # Faction targeting
    get_faction_targeting_order,
    # Harassment
    get_harassing_factions, get_vercingetorix_harassers, np_will_harass,
    # Retreat
    should_retreat, get_retreat_preferences,
    # Event locations
    rank_regions_for_event_placement,
    # Leader placement
    get_leader_placement_region,
    # Leader escort
    leader_escort_needed,
    # Agreements
    np_agrees_to_supply_line, np_agrees_to_retreat,
    # Helpers
    has_enemy_threat_in_region, count_mobile_pieces,
    count_faction_allies_and_citadels,
)


def _make_state(scenario=SCENARIO_PAX_GALLICA, seed=42, non_players=None):
    """Build a minimal test state."""
    state = build_initial_state(scenario, seed=seed)
    if non_players is None:
        non_players = {BELGAE, AEDUI}
    state["non_player_factions"] = non_players
    return state


# ===================================================================
# §8.1.2 — Limited Command Upgrade
# ===================================================================

class TestLimitedCommandUpgrade:

    def test_upgrade_from_sop(self):
        assert upgrade_limited_command(True) is True

    def test_no_upgrade_from_event(self):
        assert upgrade_limited_command(False) is False


# ===================================================================
# §8.2.2 — Dual Use Preference
# ===================================================================

class TestDualUsePreference:

    def test_romans_unshaded(self):
        assert get_dual_use_preference(ROMANS, SCENARIO_PAX_GALLICA) == EVENT_UNSHADED

    def test_aedui_unshaded(self):
        assert get_dual_use_preference(AEDUI, SCENARIO_PAX_GALLICA) == EVENT_UNSHADED

    def test_belgae_shaded(self):
        assert get_dual_use_preference(BELGAE, SCENARIO_PAX_GALLICA) == EVENT_SHADED

    def test_arverni_shaded(self):
        assert get_dual_use_preference(ARVERNI, SCENARIO_PAX_GALLICA) == EVENT_SHADED

    def test_germans_shaded_ariovistus(self):
        """A8.2.2: Germans use shaded text in Ariovistus."""
        assert get_dual_use_preference(GERMANS, SCENARIO_ARIOVISTUS) == EVENT_SHADED

    def test_romans_unshaded_ariovistus(self):
        assert get_dual_use_preference(ROMANS, SCENARIO_ARIOVISTUS) == EVENT_UNSHADED


# ===================================================================
# §8.1.1 — Event Decision Checks
# ===================================================================

class TestEventDecisions:

    def test_no_faction_event_swords(self):
        """'No Romans' cards should be detected."""
        # Card 47 = Chieftains' Council = No Romans
        assert is_no_faction_event(47, ROMANS, SCENARIO_PAX_GALLICA) is True

    def test_no_faction_event_non_swords(self):
        """Card 1 (Cicero) has laurels for Romans, not swords."""
        assert is_no_faction_event(1, ROMANS, SCENARIO_PAX_GALLICA) is False

    def test_final_year_capability(self):
        state = _make_state()
        state["final_year"] = True
        # Card 8 = Baggage Trains (Capability)
        assert is_final_year_capability(state, 8) is True

    def test_not_final_year(self):
        state = _make_state()
        state["final_year"] = False
        assert is_final_year_capability(state, 8) is False

    def test_non_capability_in_final_year(self):
        state = _make_state()
        state["final_year"] = True
        # Card 1 = Cicero — not a Capability
        assert is_final_year_capability(state, 1) is False

    def test_should_decline_swords(self):
        state = _make_state()
        # Card 47 = Chieftains' Council = No Romans
        assert should_decline_event(state, 47, ROMANS) is True

    def test_should_decline_final_year_capability(self):
        state = _make_state()
        state["final_year"] = True
        assert should_decline_event(state, 8, ROMANS) is True

    def test_should_not_decline_normal(self):
        state = _make_state()
        state["final_year"] = False
        assert should_decline_event(state, 1, ROMANS) is False


# ===================================================================
# §8.3.4 — Random Selection
# ===================================================================

class TestRandomSelection:

    def test_single_candidate(self):
        state = _make_state()
        assert random_select(state, ["a"]) == "a"

    def test_deterministic_with_seed(self):
        """Same seed produces same selection."""
        state1 = _make_state(seed=123)
        state2 = _make_state(seed=123)
        candidates = [MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII]
        result1 = random_select(state1, candidates)
        result2 = random_select(state2, candidates)
        assert result1 == result2

    def test_empty_raises(self):
        state = _make_state()
        with pytest.raises(ValueError):
            random_select(state, [])

    def test_multiple_selection(self):
        state = _make_state()
        candidates = [MORINI, NERVII, ATREBATES, PROVINCIA, MANDUBII]
        result = random_select_multiple(state, candidates, 3)
        assert len(result) == 3
        assert len(set(result)) == 3  # No duplicates

    def test_roll_die_range(self):
        state = _make_state()
        for _ in range(20):
            result = roll_die(state)
            assert 1 <= result <= 6


# ===================================================================
# §8.4.4 — Frost Restriction
# ===================================================================

class TestFrostRestriction:

    def test_frost_active(self):
        state = _make_state()
        state["frost"] = True
        assert is_frost_active(state) is True

    def test_frost_inactive(self):
        state = _make_state()
        state["frost"] = False
        assert is_frost_active(state) is False

    def test_frost_default(self):
        state = _make_state()
        assert is_frost_active(state) is False


# ===================================================================
# §8.4.1 — Place/Remove Priority Ordering
# ===================================================================

class TestPieceTargetOrder:

    def test_enemy_target_order_base(self):
        order = get_enemy_piece_target_order(SCENARIO_PAX_GALLICA)
        assert order[0] == LEADER
        assert order[1] == LEGION
        assert CITADEL in order
        assert FORT in order
        assert ALLY in order

    def test_enemy_target_order_ariovistus_has_settlement(self):
        """A8.4.1: Settlements alongside Citadels/Forts."""
        order = get_enemy_piece_target_order(SCENARIO_ARIOVISTUS)
        assert SETTLEMENT in order
        assert order[0] == LEADER
        assert order[1] == LEGION

    def test_own_loss_order_reverse(self):
        """Own losses reverse of enemy targeting."""
        order = get_own_loss_order(SCENARIO_PAX_GALLICA)
        # Ally should be removed first (lowest priority to place)
        assert order[0] == ALLY
        # Leader should be last
        assert order[-1] == LEADER

    def test_flippable_target_hidden_first(self):
        order = get_flippable_target_order()
        # First entry should be Hidden
        assert order[0][0] == HIDDEN

    def test_own_flippable_scouted_first(self):
        order = get_own_flippable_loss_order()
        assert order[0][0] == SCOUTED

    def test_ally_in_city(self):
        assert is_ally_in_city_or_remi(TRIBE_CARNUTES, SCENARIO_PAX_GALLICA) is True

    def test_non_city_tribe(self):
        assert is_ally_in_city_or_remi(TRIBE_REMI, SCENARIO_PAX_GALLICA) is False

    def test_remi_in_ariovistus(self):
        """A8.4.1: Remi counts as City in Ariovistus."""
        assert is_ally_in_city_or_remi(TRIBE_REMI, SCENARIO_ARIOVISTUS) is True


# ===================================================================
# §8.4.1 — Faction Targeting Order
# ===================================================================

class TestFactionTargeting:

    def test_belgae_targets_base(self):
        """Base: Belgae → Romans, Aedui, Arverni, Germans."""
        order = get_faction_targeting_order(BELGAE, SCENARIO_PAX_GALLICA)
        assert order == (ROMANS, AEDUI, ARVERNI, GERMANS)

    def test_arverni_targets_base(self):
        """Base: Arverni → Romans, Aedui, Belgae, Germans."""
        order = get_faction_targeting_order(ARVERNI, SCENARIO_PAX_GALLICA)
        assert order == (ROMANS, AEDUI, BELGAE, GERMANS)

    def test_romans_targets_base(self):
        """Base: Romans → Arverni, Belgae, Germans, Aedui."""
        order = get_faction_targeting_order(ROMANS, SCENARIO_PAX_GALLICA)
        assert order == (ARVERNI, BELGAE, GERMANS, AEDUI)

    def test_aedui_targets_base(self):
        """Base: Aedui → Arverni, Belgae, Germans, Romans."""
        order = get_faction_targeting_order(AEDUI, SCENARIO_PAX_GALLICA)
        assert order == (ARVERNI, BELGAE, GERMANS, ROMANS)

    def test_belgae_targets_ariovistus(self):
        """Ariovistus (A8.4): Belgae → Romans, Aedui, Germans, Arverni."""
        order = get_faction_targeting_order(BELGAE, SCENARIO_ARIOVISTUS)
        assert order == (ROMANS, AEDUI, GERMANS, ARVERNI)

    def test_germans_targets_ariovistus(self):
        """Ariovistus (A8.4): Germans → Romans, Aedui, Belgae, Arverni."""
        order = get_faction_targeting_order(GERMANS, SCENARIO_ARIOVISTUS)
        assert order == (ROMANS, AEDUI, BELGAE, ARVERNI)

    def test_romans_targets_ariovistus(self):
        """Ariovistus (A8.4): Romans → Germans, Belgae, Arverni, Aedui."""
        order = get_faction_targeting_order(ROMANS, SCENARIO_ARIOVISTUS)
        assert order == (GERMANS, BELGAE, ARVERNI, AEDUI)


# ===================================================================
# §8.4.2 — Harassment
# ===================================================================

class TestHarassment:

    def test_roman_harassed_by_belgae_arverni_base(self):
        """Base: Belgae and Arverni harass Roman March/Seize."""
        harassers = get_harassing_factions(ROMANS, SCENARIO_PAX_GALLICA)
        assert set(harassers) == {BELGAE, ARVERNI}

    def test_roman_harassed_by_belgae_germans_ariovistus(self):
        """Ariovistus: Belgae and Germans harass Roman March/Seize."""
        harassers = get_harassing_factions(ROMANS, SCENARIO_ARIOVISTUS)
        assert set(harassers) == {BELGAE, GERMANS}

    def test_non_roman_not_harassed(self):
        harassers = get_harassing_factions(BELGAE, SCENARIO_PAX_GALLICA)
        assert harassers == ()

    def test_vercingetorix_harassers_base(self):
        """Base: Aedui and Romans harass Vercingetorix March."""
        harassers = get_vercingetorix_harassers(SCENARIO_PAX_GALLICA)
        assert set(harassers) == {AEDUI, ROMANS}

    def test_no_vercingetorix_harassers_ariovistus(self):
        """Ariovistus: No Vercingetorix, no harassment."""
        harassers = get_vercingetorix_harassers(SCENARIO_ARIOVISTUS)
        assert harassers == ()

    def test_np_will_harass_belgae_roman(self):
        assert np_will_harass(BELGAE, ROMANS, SCENARIO_PAX_GALLICA) is True

    def test_np_will_not_harass_belgae_arverni(self):
        assert np_will_harass(BELGAE, ARVERNI, SCENARIO_PAX_GALLICA) is False

    def test_np_harass_vercingetorix(self):
        assert np_will_harass(
            ROMANS, ARVERNI, SCENARIO_PAX_GALLICA,
            vercingetorix_marching=True) is True


# ===================================================================
# §8.4.3 — Retreat
# ===================================================================

class TestRetreat:

    def test_retreat_last_piece(self):
        state = _make_state()
        assert should_retreat(
            state, BELGAE, MORINI, ROMANS,
            own_losses=1, enemy_losses=0,
            last_piece_threatened=True,
        ) is True

    def test_retreat_roman_legion_loss(self):
        state = _make_state()
        assert should_retreat(
            state, ROMANS, MORINI, BELGAE,
            own_losses=2, enemy_losses=1,
            legion_loss_rolls=1,
        ) is True

    def test_retreat_unfavorable_no_fort(self):
        """Retreat if no Fort/Citadel AND < 1/2 Losses AND safe Retreat."""
        state = _make_state()
        assert should_retreat(
            state, BELGAE, MORINI, ROMANS,
            own_losses=4, enemy_losses=1,
            has_fort_or_citadel=False,
            retreat_removes_pieces=False,
        ) is True

    def test_no_retreat_with_fort(self):
        """Don't retreat if have Fort/Citadel."""
        state = _make_state()
        assert should_retreat(
            state, BELGAE, MORINI, ROMANS,
            own_losses=4, enemy_losses=1,
            has_fort_or_citadel=True,
        ) is False

    def test_no_retreat_favorable(self):
        """Don't retreat if inflicting >= 1/2 Losses."""
        state = _make_state()
        assert should_retreat(
            state, BELGAE, MORINI, ROMANS,
            own_losses=4, enemy_losses=2,
            has_fort_or_citadel=False,
        ) is False

    def test_no_retreat_if_retreat_removes(self):
        """Don't retreat if Retreat itself removes pieces."""
        state = _make_state()
        assert should_retreat(
            state, BELGAE, MORINI, ROMANS,
            own_losses=4, enemy_losses=1,
            has_fort_or_citadel=False,
            retreat_removes_pieces=True,
        ) is False


# ===================================================================
# §8.3.1 — Event Location Selection
# ===================================================================

class TestEventLocationSelection:

    def test_rank_by_legions(self):
        state = _make_state()
        # Place Legions in Provincia
        place_piece(state, PROVINCIA, ROMANS, LEGION, 2,
                    from_legions_track=True)
        regions = [MORINI, PROVINCIA, MANDUBII]
        ranked = rank_regions_for_event_placement(state, regions,
                                                  SCENARIO_PAX_GALLICA)
        assert ranked[0] == PROVINCIA


# ===================================================================
# §8.3.2 — Leader Placement
# ===================================================================

class TestLeaderPlacement:

    def test_place_where_most_pieces(self):
        state = _make_state()
        # Place some Auxilia in Mandubii
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 5)
        # Place fewer in Provincia
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2)
        best = get_leader_placement_region(state, ROMANS)
        assert best == MANDUBII


# ===================================================================
# §8.4.1 — Leader Escort
# ===================================================================

class TestLeaderEscort:

    def test_no_leader_on_map(self):
        state = _make_state()
        region, shortfall = leader_escort_needed(state, ROMANS,
                                                 SCENARIO_PAX_GALLICA)
        assert region is None
        assert shortfall == 0

    def test_leader_with_enough_escort(self):
        state = _make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 5)
        region, shortfall = leader_escort_needed(state, ROMANS,
                                                 SCENARIO_PAX_GALLICA)
        assert region == PROVINCIA
        assert shortfall == 0

    def test_leader_needs_escort(self):
        state = _make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2)
        region, shortfall = leader_escort_needed(state, ROMANS,
                                                 SCENARIO_PAX_GALLICA)
        assert region == PROVINCIA
        assert shortfall == 2


# ===================================================================
# §8.4.2 — Supply Line / Retreat Agreements
# ===================================================================

class TestAgreements:

    def test_romans_agree_for_np_aedui(self):
        state = _make_state(non_players={ROMANS, AEDUI})
        assert np_agrees_to_supply_line(ROMANS, AEDUI, state) is True

    def test_romans_refuse_player_aedui(self):
        """Romans refuse if Aedui is a player."""
        state = _make_state(non_players={ROMANS})
        assert np_agrees_to_supply_line(ROMANS, AEDUI, state) is False

    def test_romans_refuse_belgae(self):
        state = _make_state(non_players={ROMANS, BELGAE})
        assert np_agrees_to_supply_line(ROMANS, BELGAE, state) is False

    def test_belgae_refuse_all(self):
        state = _make_state(non_players={BELGAE, ARVERNI})
        assert np_agrees_to_supply_line(BELGAE, ROMANS, state) is False

    def test_retreat_same_as_supply_line(self):
        state = _make_state(non_players={ROMANS, AEDUI})
        assert np_agrees_to_retreat(ROMANS, AEDUI, state) is True


# ===================================================================
# Helpers
# ===================================================================

class TestHelpers:

    def test_count_mobile_pieces(self):
        state = _make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        place_piece(state, PROVINCIA, ROMANS, LEGION, 3,
                    from_legions_track=True)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 4)
        total = count_mobile_pieces(state, PROVINCIA, ROMANS)
        assert total == 8  # 1 Leader + 3 Legions + 4 Auxilia

    def test_has_enemy_threat_ally(self):
        state = _make_state()
        # Place Arverni Ally at a tribe in Mandubii
        tribe = TRIBE_CARNUTES
        state["tribes"][tribe]["allied_faction"] = ARVERNI
        place_piece(state, MANDUBII, ARVERNI, ALLY)
        # Need Roman presence to check threat
        place_piece(state, MANDUBII, ROMANS, LEADER, leader_name=CAESAR)
        assert has_enemy_threat_in_region(
            state, MANDUBII, ROMANS, SCENARIO_PAX_GALLICA) is True

    def test_no_threat_empty_region(self):
        state = _make_state()
        assert has_enemy_threat_in_region(
            state, MORINI, ROMANS, SCENARIO_PAX_GALLICA) is False

    def test_count_allies_and_citadels(self):
        state = _make_state()
        state["tribes"][TRIBE_CARNUTES]["allied_faction"] = ARVERNI
        state["tribes"][TRIBE_AEDUI]["allied_faction"] = ARVERNI
        place_piece(state, ARVERNI_REGION, ARVERNI, CITADEL)
        total = count_faction_allies_and_citadels(state, ARVERNI)
        assert total == 3  # 2 allies + 1 citadel


# ===================================================================
# Scenario Isolation
# ===================================================================

class TestScenarioIsolation:

    def test_targeting_differs_by_scenario(self):
        """Base and Ariovistus targeting orders differ per A8.4."""
        base = get_faction_targeting_order(ROMANS, SCENARIO_PAX_GALLICA)
        ario = get_faction_targeting_order(ROMANS, SCENARIO_ARIOVISTUS)
        assert base != ario
        assert base[0] == ARVERNI  # Base: Arverni first
        assert ario[0] == GERMANS  # Ariovistus: Germans first

    def test_harassment_differs_by_scenario(self):
        base = get_harassing_factions(ROMANS, SCENARIO_PAX_GALLICA)
        ario = get_harassing_factions(ROMANS, SCENARIO_ARIOVISTUS)
        assert set(base) != set(ario)
        assert ARVERNI in base and ARVERNI not in ario
        assert GERMANS in ario and GERMANS not in base

    def test_piece_target_order_settlement_ariovistus_only(self):
        base_order = get_enemy_piece_target_order(SCENARIO_PAX_GALLICA)
        ario_order = get_enemy_piece_target_order(SCENARIO_ARIOVISTUS)
        assert SETTLEMENT not in base_order
        assert SETTLEMENT in ario_order
