"""Tests for game_engine.py — Sequence of Play orchestrator.

Verifies:
- Deck management: draw_card, start_game, advance_to_next_card
- Winter card detection
- Frost detection (§2.3.8)
- Faction order with A2.3.2 mapping
- Eligibility tracking (§2.3.1, §2.3.2)
- Turn options (§2.3.4)
- Pass mechanics (§2.3.3)
- Eligibility adjustment (§2.3.6)
- Card turn resolution with cascading passes
- Winter card handling (§2.4)
- Scenario isolation: Germans not in SoP for base, Arverni not for Ariovistus
- Carnyx trigger detection (A2.3.9)
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST, SCENARIO_GREAT_REVOLT,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
    # Pass resources
    PASS_RESOURCES_GALLIC, PASS_RESOURCES_ROMAN,
    PASS_RESOURCES_GERMAN_ARIOVISTUS,
    # Winter
    WINTER_CARD,
    # Resources
    MAX_RESOURCES,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (
    # Deck management
    draw_card,
    start_game,
    advance_to_next_card,
    is_winter_card,
    is_frost,
    # SoP
    get_sop_factions,
    get_faction_order,
    get_eligible_factions,
    determine_eligible_order,
    # Turn options
    get_first_eligible_options,
    get_second_eligible_options,
    # Pass
    execute_pass,
    # Eligibility
    adjust_eligibility,
    # Resolution
    resolve_card_turn,
    resolve_winter_card,
    play_card,
    # Actions
    ACTION_COMMAND,
    ACTION_COMMAND_SA,
    ACTION_LIMITED_COMMAND,
    ACTION_EVENT,
    ACTION_PASS,
)
from fs_bot.cards.card_data import card_has_carnyx_trigger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_base_state(seed=42):
    """Create a base game state with Pax Gallica scenario."""
    return setup_scenario(SCENARIO_PAX_GALLICA, seed=seed)


def _make_ario_state(seed=42):
    """Create an Ariovistus game state."""
    return setup_scenario(SCENARIO_ARIOVISTUS, seed=seed)


def _simple_decision(action):
    """Return a decision_func that always returns the given action."""
    def func(state, faction, options, position):
        return {"action": action}
    return func


def _action_map_decision(faction_actions):
    """Return a decision_func that maps factions to specific actions.

    faction_actions: dict {faction: action_string}
    Falls back to ACTION_PASS for unlisted factions.
    """
    def func(state, faction, options, position):
        action = faction_actions.get(faction, ACTION_PASS)
        return {"action": action}
    return func


# ============================================================================
# WINTER CARD DETECTION
# ============================================================================

class TestIsWinterCard:
    """Tests for is_winter_card()."""

    def test_winter_card_string(self):
        assert is_winter_card(WINTER_CARD) is True

    def test_event_card_int(self):
        assert is_winter_card(1) is False

    def test_event_card_a_prefix(self):
        assert is_winter_card("A5") is False

    def test_none(self):
        assert is_winter_card(None) is False


# ============================================================================
# DECK MANAGEMENT
# ============================================================================

class TestDrawCard:
    """Tests for draw_card()."""

    def test_draw_moves_card_to_played(self):
        state = _make_base_state()
        top = state["deck"][0]
        card = draw_card(state)
        assert card == top
        assert card in state["played_cards"]
        assert card == state["current_card"]

    def test_draw_removes_from_deck(self):
        state = _make_base_state()
        initial_len = len(state["deck"])
        draw_card(state)
        assert len(state["deck"]) == initial_len - 1

    def test_draw_sets_next_card(self):
        state = _make_base_state()
        expected_next = state["deck"][1]
        draw_card(state)
        assert state["next_card"] == expected_next

    def test_draw_last_card_sets_next_none(self):
        state = _make_base_state()
        state["deck"] = [42]
        draw_card(state)
        assert state["next_card"] is None

    def test_draw_empty_deck_raises(self):
        state = _make_base_state()
        state["deck"] = []
        with pytest.raises(IndexError):
            draw_card(state)


class TestStartGame:
    """Tests for start_game() — §2.2."""

    def test_sets_current_card(self):
        state = _make_base_state()
        first_card = state["deck"][0]
        result = start_game(state)
        assert result == first_card
        assert state["current_card"] == first_card

    def test_sets_next_card(self):
        state = _make_base_state()
        second_card = state["deck"][1]
        start_game(state)
        assert state["next_card"] == second_card

    def test_first_card_in_played_pile(self):
        state = _make_base_state()
        first_card = state["deck"][0]
        start_game(state)
        assert first_card in state["played_cards"]

    def test_all_factions_eligible(self):
        """§2.3.1: All factions start the game Eligible."""
        state = _make_base_state()
        start_game(state)
        for faction in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            assert state["eligibility"][faction] == ELIGIBLE

    def test_all_factions_eligible_ariovistus(self):
        state = _make_ario_state()
        start_game(state)
        for faction in [ROMANS, GERMANS, AEDUI, BELGAE]:
            assert state["eligibility"][faction] == ELIGIBLE


class TestAdvanceToNextCard:
    """Tests for advance_to_next_card() — §2.3.7."""

    def test_advances_card(self):
        state = _make_base_state()
        start_game(state)
        old_next = state["next_card"]
        new_current = advance_to_next_card(state)
        assert new_current == old_next
        assert state["current_card"] == old_next

    def test_empty_deck_returns_none(self):
        state = _make_base_state()
        state["deck"] = []
        result = advance_to_next_card(state)
        assert result is None


# ============================================================================
# FROST — §2.3.8
# ============================================================================

class TestFrost:
    """Tests for is_frost() — §2.3.8."""

    def test_frost_when_next_is_winter(self):
        """Frost applies when the upcoming card is a Winter card."""
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = WINTER_CARD
        assert is_frost(state) is True

    def test_no_frost_when_next_is_event(self):
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = 2
        assert is_frost(state) is False

    def test_no_frost_when_current_is_winter(self):
        """Winter cards themselves don't have Frost."""
        state = _make_base_state()
        state["current_card"] = WINTER_CARD
        state["next_card"] = WINTER_CARD
        assert is_frost(state) is False

    def test_no_frost_when_next_is_none(self):
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = None
        assert is_frost(state) is False

    def test_no_frost_when_current_is_none(self):
        state = _make_base_state()
        state["current_card"] = None
        state["next_card"] = WINTER_CARD
        assert is_frost(state) is False


# ============================================================================
# SOP FACTIONS — SCENARIO ISOLATION
# ============================================================================

class TestGetSopFactions:
    """Tests for get_sop_factions() — scenario-dependent SoP participation."""

    @pytest.mark.parametrize("scenario", BASE_SCENARIOS)
    def test_base_game_excludes_germans(self, scenario):
        """§6.2: Germans are NOT in the SoP in base game."""
        state = setup_scenario(scenario, seed=42)
        sop = get_sop_factions(state)
        assert GERMANS not in sop
        assert ARVERNI in sop
        assert set(sop) == {ROMANS, ARVERNI, AEDUI, BELGAE}

    @pytest.mark.parametrize("scenario", ARIOVISTUS_SCENARIOS)
    def test_ariovistus_excludes_arverni(self, scenario):
        """A6.2: Arverni are NOT in the SoP in Ariovistus."""
        state = setup_scenario(scenario, seed=42)
        sop = get_sop_factions(state)
        assert ARVERNI not in sop
        assert GERMANS in sop
        assert set(sop) == {ROMANS, GERMANS, AEDUI, BELGAE}


# ============================================================================
# FACTION ORDER — §2.3.2, A2.3.2
# ============================================================================

class TestGetFactionOrder:
    """Tests for get_faction_order()."""

    def test_base_game_returns_four_factions(self):
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        order = get_faction_order(state)
        assert len(order) == 4
        assert set(order) == {ROMANS, ARVERNI, AEDUI, BELGAE}

    def test_base_game_card_1_order(self):
        """Card 1: Ro Ar Ae Be."""
        state = _make_base_state()
        state["current_card"] = 1
        order = get_faction_order(state)
        assert order == (ROMANS, ARVERNI, AEDUI, BELGAE)

    def test_base_game_card_19_order(self):
        """Card 19: Ar Ro Ae Be — Arverni is first."""
        state = _make_base_state()
        state["current_card"] = 19
        order = get_faction_order(state)
        assert order[0] == ARVERNI
        assert order == (ARVERNI, ROMANS, AEDUI, BELGAE)

    def test_base_game_excludes_germans(self):
        """Germans should never appear in base game faction order."""
        state = _make_base_state()
        for card_id in range(1, 73):
            state["current_card"] = card_id
            order = get_faction_order(state)
            assert GERMANS not in order, f"Germans in card {card_id} order"

    def test_ariovistus_maps_arverni_to_germans(self):
        """A2.3.2: On base cards in Ariovistus, ARVERNI → GERMANS."""
        state = _make_ario_state()
        # Card 1: base card with Ro Ar Ae Be → Ro Ge Ae Be in Ariovistus
        state["current_card"] = 1
        order = get_faction_order(state)
        assert GERMANS in order
        assert ARVERNI not in order
        assert order == (ROMANS, GERMANS, AEDUI, BELGAE)

    def test_ariovistus_a_prefix_card_has_germans(self):
        """A2.3.2: A-prefix cards already have GERMANS in their order."""
        state = _make_ario_state()
        state["current_card"] = "A5"  # Ro Ge Be Ae
        order = get_faction_order(state)
        assert GERMANS in order
        assert ARVERNI not in order

    def test_ariovistus_excludes_arverni(self):
        """Arverni should never appear in Ariovistus faction order."""
        state = _make_ario_state()
        # Test a base card
        state["current_card"] = 1
        order = get_faction_order(state)
        assert ARVERNI not in order
        # Test an A-prefix card
        state["current_card"] = "A19"
        order = get_faction_order(state)
        assert ARVERNI not in order


# ============================================================================
# ELIGIBILITY — §2.3.1, §2.3.2
# ============================================================================

class TestGetEligibleFactions:
    """Tests for get_eligible_factions()."""

    def test_all_eligible_returns_card_order(self):
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        # All eligible
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        result = get_eligible_factions(state)
        assert result == [ROMANS, ARVERNI, AEDUI, BELGAE]

    def test_ineligible_skipped(self):
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        state["eligibility"][ARVERNI] = INELIGIBLE
        result = get_eligible_factions(state)
        assert ARVERNI not in result
        assert result == [ROMANS, AEDUI, BELGAE]

    def test_none_eligible(self):
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = INELIGIBLE
        result = get_eligible_factions(state)
        assert result == []


class TestDetermineEligibleOrder:
    """Tests for determine_eligible_order() — §2.3.2."""

    def test_all_eligible(self):
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        first, second, remaining = determine_eligible_order(state)
        assert first == ROMANS
        assert second == ARVERNI
        assert remaining == [AEDUI, BELGAE]

    def test_first_ineligible(self):
        """If leftmost is Ineligible, next becomes 1st."""
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        state["eligibility"][ROMANS] = INELIGIBLE
        first, second, remaining = determine_eligible_order(state)
        assert first == ARVERNI
        assert second == AEDUI
        assert remaining == [BELGAE]

    def test_only_one_eligible(self):
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = INELIGIBLE
        state["eligibility"][BELGAE] = ELIGIBLE
        first, second, remaining = determine_eligible_order(state)
        assert first == BELGAE
        assert second is None
        assert remaining == []

    def test_none_eligible(self):
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = INELIGIBLE
        first, second, remaining = determine_eligible_order(state)
        assert first is None
        assert second is None
        assert remaining == []


# ============================================================================
# TURN OPTIONS — §2.3.4
# ============================================================================

class TestTurnOptions:
    """Tests for get_first_eligible_options and get_second_eligible_options."""

    def test_first_eligible_options(self):
        options = get_first_eligible_options()
        assert ACTION_COMMAND in options
        assert ACTION_COMMAND_SA in options
        assert ACTION_EVENT in options
        assert ACTION_PASS in options

    def test_second_after_command_only(self):
        """§2.3.4: If 1st did Command only → 2nd: Limited Command or Pass."""
        options = get_second_eligible_options(ACTION_COMMAND)
        assert ACTION_LIMITED_COMMAND in options
        assert ACTION_PASS in options
        assert ACTION_COMMAND not in options
        assert ACTION_EVENT not in options

    def test_second_after_command_sa(self):
        """§2.3.4: If 1st did Command+SA → 2nd: Limited, Event, or Pass."""
        options = get_second_eligible_options(ACTION_COMMAND_SA)
        assert ACTION_LIMITED_COMMAND in options
        assert ACTION_EVENT in options
        assert ACTION_PASS in options
        assert ACTION_COMMAND not in options

    def test_second_after_event(self):
        """§2.3.4: If 1st did Event → 2nd: Command, Command+SA, or Pass."""
        options = get_second_eligible_options(ACTION_EVENT)
        assert ACTION_COMMAND in options
        assert ACTION_COMMAND_SA in options
        assert ACTION_PASS in options
        assert ACTION_LIMITED_COMMAND not in options
        assert ACTION_EVENT not in options

    def test_second_invalid_first_raises(self):
        with pytest.raises(ValueError):
            get_second_eligible_options(ACTION_PASS)


# ============================================================================
# PASS MECHANICS — §2.3.3
# ============================================================================

class TestExecutePass:
    """Tests for execute_pass() — §2.3.3."""

    def test_gallic_faction_gains_1(self):
        """§2.3.3: Gallic factions receive +1 Resource."""
        state = _make_base_state()
        state["resources"][ARVERNI] = 10
        result = execute_pass(state, ARVERNI)
        assert state["resources"][ARVERNI] == 11
        assert result["resources_gained"] == 1

    def test_roman_gains_2(self):
        """§2.3.3: Romans receive +2 Resources."""
        state = _make_base_state()
        state["resources"][ROMANS] = 10
        result = execute_pass(state, ROMANS)
        assert state["resources"][ROMANS] == 12
        assert result["resources_gained"] == 2

    def test_belgae_gallic_gains_1(self):
        """Belgae are Gallic, so +1."""
        state = _make_base_state()
        state["resources"][BELGAE] = 5
        result = execute_pass(state, BELGAE)
        assert state["resources"][BELGAE] == 6
        assert result["resources_gained"] == 1

    def test_aedui_gallic_gains_1(self):
        state = _make_base_state()
        state["resources"][AEDUI] = 5
        result = execute_pass(state, AEDUI)
        assert state["resources"][AEDUI] == 6
        assert result["resources_gained"] == 1

    def test_german_ariovistus_gains_1(self):
        """A2.3.3: Germans receive +1 Resource in Ariovistus."""
        state = _make_ario_state()
        state["resources"][GERMANS] = 5
        result = execute_pass(state, GERMANS)
        assert state["resources"][GERMANS] == 6
        assert result["resources_gained"] == 1

    def test_capped_at_max_resources(self):
        """Resources capped at MAX_RESOURCES (45) — §1.8."""
        state = _make_base_state()
        state["resources"][ROMANS] = 44
        result = execute_pass(state, ROMANS)
        assert state["resources"][ROMANS] == MAX_RESOURCES
        assert result["resources_gained"] == 1  # Only gained 1, not 2

    def test_already_at_max(self):
        state = _make_base_state()
        state["resources"][ROMANS] = MAX_RESOURCES
        result = execute_pass(state, ROMANS)
        assert state["resources"][ROMANS] == MAX_RESOURCES
        assert result["resources_gained"] == 0


# ============================================================================
# ELIGIBILITY ADJUSTMENT — §2.3.6
# ============================================================================

class TestAdjustEligibility:
    """Tests for adjust_eligibility() — §2.3.6."""

    def test_command_makes_ineligible(self):
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {ROMANS: {"action": ACTION_COMMAND}}
        adjust_eligibility(state, actions)
        assert state["eligibility"][ROMANS] == INELIGIBLE

    def test_command_sa_makes_ineligible(self):
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {ARVERNI: {"action": ACTION_COMMAND_SA}}
        adjust_eligibility(state, actions)
        assert state["eligibility"][ARVERNI] == INELIGIBLE

    def test_limited_command_makes_ineligible(self):
        """§2.3.5: A Limited Command counts as a Command → Ineligible."""
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {AEDUI: {"action": ACTION_LIMITED_COMMAND}}
        adjust_eligibility(state, actions)
        assert state["eligibility"][AEDUI] == INELIGIBLE

    def test_event_makes_ineligible(self):
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {BELGAE: {"action": ACTION_EVENT}}
        adjust_eligibility(state, actions)
        assert state["eligibility"][BELGAE] == INELIGIBLE

    def test_pass_stays_eligible(self):
        """§2.3.3: Passing faction remains Eligible."""
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {ROMANS: {"action": ACTION_PASS}}
        adjust_eligibility(state, actions)
        assert state["eligibility"][ROMANS] == ELIGIBLE

    def test_no_action_stays_eligible(self):
        """Factions that did not act remain Eligible."""
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {ROMANS: {"action": ACTION_COMMAND}}
        adjust_eligibility(state, actions)
        # Arverni, Aedui, Belgae did not act → Eligible
        assert state["eligibility"][ARVERNI] == ELIGIBLE
        assert state["eligibility"][AEDUI] == ELIGIBLE
        assert state["eligibility"][BELGAE] == ELIGIBLE

    def test_free_action_exception(self):
        """§2.3.6 EXCEPTION: free Actions don't cause Ineligibility."""
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {
            ROMANS: {"action": ACTION_COMMAND, "free_action": True},
        }
        adjust_eligibility(state, actions)
        assert state["eligibility"][ROMANS] == ELIGIBLE

    def test_two_factions_acted(self):
        state = _make_base_state()
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE
        actions = {
            ROMANS: {"action": ACTION_COMMAND},
            ARVERNI: {"action": ACTION_LIMITED_COMMAND},
        }
        adjust_eligibility(state, actions)
        assert state["eligibility"][ROMANS] == INELIGIBLE
        assert state["eligibility"][ARVERNI] == INELIGIBLE
        assert state["eligibility"][AEDUI] == ELIGIBLE
        assert state["eligibility"][BELGAE] == ELIGIBLE


# ============================================================================
# CARD TURN RESOLUTION — §2.3
# ============================================================================

class TestResolveCardTurn:
    """Tests for resolve_card_turn()."""

    def test_basic_turn_both_act(self):
        """1st does Command, 2nd does Limited Command."""
        state = _make_base_state()
        start_game(state)
        card_order = get_faction_order(state)
        first_f = card_order[0]
        second_f = card_order[1]

        def decision(st, faction, options, position):
            if faction == first_f:
                return {"action": ACTION_COMMAND}
            return {"action": ACTION_LIMITED_COMMAND}

        result = resolve_card_turn(state, decision)
        assert result["card"] == state["current_card"]
        assert first_f in result["actions_taken"]
        assert second_f in result["actions_taken"]
        # Acting factions should be Ineligible
        assert state["eligibility"][first_f] == INELIGIBLE
        assert state["eligibility"][second_f] == INELIGIBLE

    def test_first_passes_cascading(self):
        """§2.3.3: If 1st passes, next eligible becomes new 1st."""
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        calls = []

        def decision(st, faction, options, position):
            calls.append((faction, position))
            if faction == ROMANS:
                return {"action": ACTION_PASS}
            if faction == ARVERNI:
                return {"action": ACTION_COMMAND}
            return {"action": ACTION_LIMITED_COMMAND}

        result = resolve_card_turn(state, decision)
        # Romans passed, Arverni became 1st, Aedui became 2nd
        assert ROMANS in result["passes"]
        assert result["actions_taken"][ARVERNI]["action"] == ACTION_COMMAND
        assert result["actions_taken"][AEDUI]["action"] == ACTION_LIMITED_COMMAND
        # Romans passed → stays Eligible; Arverni/Aedui acted → Ineligible
        assert state["eligibility"][ROMANS] == ELIGIBLE
        assert state["eligibility"][ARVERNI] == INELIGIBLE
        assert state["eligibility"][AEDUI] == INELIGIBLE

    def test_all_pass(self):
        """§2.3.3: If all eligible pass, adjust and move on."""
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        result = resolve_card_turn(state, _simple_decision(ACTION_PASS))
        assert len(result["passes"]) == 4
        # All should remain Eligible
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            assert state["eligibility"][f] == ELIGIBLE

    def test_second_passes_cascading(self):
        """If 2nd passes, next eligible becomes new 2nd."""
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        def decision(st, faction, options, position):
            if faction == ROMANS:
                return {"action": ACTION_COMMAND}
            if faction == ARVERNI:
                return {"action": ACTION_PASS}  # 2nd passes
            if faction == AEDUI:
                return {"action": ACTION_LIMITED_COMMAND}  # becomes 2nd
            return {"action": ACTION_PASS}

        result = resolve_card_turn(state, decision)
        assert ARVERNI in result["passes"]
        assert result["actions_taken"][AEDUI]["action"] == ACTION_LIMITED_COMMAND

    def test_frost_flag_set(self):
        """Frost flag should be set when upcoming card is Winter."""
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = WINTER_CARD
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        result = resolve_card_turn(state, _simple_decision(ACTION_PASS))
        assert result["frost"] is True

    def test_no_frost_flag(self):
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = 2
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        result = resolve_card_turn(state, _simple_decision(ACTION_PASS))
        assert result["frost"] is False

    def test_event_then_command_sa(self):
        """§2.3.4: 1st does Event → 2nd may do Command+SA."""
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        def decision(st, faction, options, position):
            if faction == ROMANS:
                return {"action": ACTION_EVENT}
            if faction == ARVERNI:
                assert ACTION_COMMAND in options
                assert ACTION_COMMAND_SA in options
                return {"action": ACTION_COMMAND_SA}
            return {"action": ACTION_PASS}

        result = resolve_card_turn(state, decision)
        assert result["actions_taken"][ROMANS]["action"] == ACTION_EVENT
        assert result["actions_taken"][ARVERNI]["action"] == ACTION_COMMAND_SA

    def test_only_two_eligible(self):
        """When only 2 factions are eligible, they are 1st and 2nd."""
        state = _make_base_state()
        state["current_card"] = 1  # Ro Ar Ae Be
        state["eligibility"][ROMANS] = ELIGIBLE
        state["eligibility"][ARVERNI] = INELIGIBLE
        state["eligibility"][AEDUI] = INELIGIBLE
        state["eligibility"][BELGAE] = ELIGIBLE

        def decision(st, faction, options, position):
            if position == "1st_eligible":
                return {"action": ACTION_COMMAND}
            return {"action": ACTION_LIMITED_COMMAND}

        result = resolve_card_turn(state, decision)
        assert ROMANS in result["actions_taken"]
        assert BELGAE in result["actions_taken"]

    def test_one_eligible_acts_alone(self):
        """With only 1 eligible, they are 1st, no 2nd."""
        state = _make_base_state()
        state["current_card"] = 1
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = INELIGIBLE
        state["eligibility"][ROMANS] = ELIGIBLE

        def decision(st, faction, options, position):
            return {"action": ACTION_COMMAND}

        result = resolve_card_turn(state, decision)
        assert result["actions_taken"][ROMANS]["action"] == ACTION_COMMAND
        assert len(result["actions_taken"]) == 1


# ============================================================================
# CARNYX TRIGGER — A2.3.9
# ============================================================================

class TestCarnyxTrigger:
    """Tests for Arverni Phase trigger via carnyx symbol — A2.3.9."""

    def test_carnyx_count(self):
        """A2.3.9: 24 cards have the carnyx trigger."""
        from fs_bot.cards.card_data import get_all_ariovistus_cards
        cards = get_all_ariovistus_cards()
        count = sum(1 for c in cards.values() if c.has_carnyx_trigger)
        assert count == 24

    def test_base_cards_no_carnyx(self):
        """Base game cards should never have a carnyx trigger."""
        from fs_bot.cards.card_data import get_all_base_cards
        cards = get_all_base_cards()
        for card_id, card in cards.items():
            assert card.has_carnyx_trigger is False, (
                f"Base card {card_id} has carnyx trigger"
            )

    def test_carnyx_only_on_a_prefix(self):
        """Only A-prefix cards should have the carnyx trigger."""
        from fs_bot.cards.card_data import get_all_ariovistus_cards
        cards = get_all_ariovistus_cards()
        for card_id, card in cards.items():
            if card.has_carnyx_trigger:
                assert isinstance(card_id, str) and card_id.startswith("A"), (
                    f"Non-A-prefix card {card_id} has carnyx trigger"
                )


# ============================================================================
# SCENARIO ISOLATION
# ============================================================================

class TestScenarioIsolation:
    """Verify scenario isolation in the game engine."""

    def test_base_game_no_german_turns(self):
        """Germans should not participate in SoP in base game."""
        state = _make_base_state()
        start_game(state)
        eligible = get_eligible_factions(state)
        assert GERMANS not in eligible

    def test_ariovistus_no_arverni_turns(self):
        """Arverni should not participate in SoP in Ariovistus."""
        state = _make_ario_state()
        start_game(state)
        eligible = get_eligible_factions(state)
        assert ARVERNI not in eligible

    def test_ariovistus_faction_order_no_arverni(self):
        """In Ariovistus, faction_order should never contain Arverni."""
        state = _make_ario_state()
        # Test multiple cards
        for card_id in [1, 2, 10, 19, "A5", "A19"]:
            state["current_card"] = card_id
            order = get_faction_order(state)
            assert ARVERNI not in order, (
                f"Arverni in order for card {card_id}"
            )

    def test_base_faction_order_no_germans(self):
        """In base game, faction_order should never contain Germans."""
        state = _make_base_state()
        for card_id in range(1, 73):
            state["current_card"] = card_id
            order = get_faction_order(state)
            assert GERMANS not in order, (
                f"Germans in order for card {card_id}"
            )

    def test_base_game_no_arverni_phase(self):
        """Base game resolve_card_turn should not trigger Arverni Phase."""
        state = _make_base_state()
        state["current_card"] = 1
        state["next_card"] = 2
        for f in [ROMANS, ARVERNI, AEDUI, BELGAE]:
            state["eligibility"][f] = ELIGIBLE

        result = resolve_card_turn(state, _simple_decision(ACTION_PASS))
        assert result["arverni_phase"] is None


# ============================================================================
# PASS RESOURCES — FULL MATRIX
# ============================================================================

class TestPassResourcesMatrix:
    """Test pass resources for all factions across scenarios."""

    @pytest.mark.parametrize("faction,expected", [
        (ROMANS, PASS_RESOURCES_ROMAN),
        (ARVERNI, PASS_RESOURCES_GALLIC),
        (AEDUI, PASS_RESOURCES_GALLIC),
        (BELGAE, PASS_RESOURCES_GALLIC),
    ])
    def test_base_game_pass_resources(self, faction, expected):
        state = _make_base_state()
        state["resources"][faction] = 0
        result = execute_pass(state, faction)
        assert result["resources_gained"] == expected

    def test_german_ariovistus_pass_resources(self):
        state = _make_ario_state()
        state["resources"][GERMANS] = 0
        result = execute_pass(state, GERMANS)
        assert result["resources_gained"] == PASS_RESOURCES_GERMAN_ARIOVISTUS


# ============================================================================
# INTEGRATION: MULTI-CARD SEQUENCE
# ============================================================================

class TestMultiCardSequence:
    """Integration tests for multi-card game flow."""

    def test_eligibility_carries_between_cards(self):
        """Factions that acted become Ineligible for the next card."""
        state = _make_base_state()
        start_game(state)

        card_order = get_faction_order(state)
        first_f = card_order[0]
        second_f = card_order[1]

        # First card: 1st and 2nd act
        def first_turn(st, faction, options, position):
            if faction == first_f:
                return {"action": ACTION_COMMAND}
            return {"action": ACTION_LIMITED_COMMAND}

        resolve_card_turn(state, first_turn)
        assert state["eligibility"][first_f] == INELIGIBLE
        assert state["eligibility"][second_f] == INELIGIBLE

        # Advance to next card
        advance_to_next_card(state)
        new_eligible = get_eligible_factions(state)
        assert first_f not in new_eligible
        assert second_f not in new_eligible

    def test_pass_keeps_eligible_for_next_card(self):
        """§2.3.3: Passing factions stay Eligible for the next card."""
        state = _make_base_state()
        start_game(state)

        # All pass
        resolve_card_turn(state, _simple_decision(ACTION_PASS))
        advance_to_next_card(state)

        # All should still be Eligible
        eligible = get_eligible_factions(state)
        sop = get_sop_factions(state)
        assert set(eligible) == set(sop)
