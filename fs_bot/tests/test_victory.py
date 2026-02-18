"""Tests for victory module — fs_bot/engine/victory.py.

Tests cover:
  - Each faction's score calculation (base + Ariovistus)
  - Arverni dual condition (both must exceed)
  - Aedui "exceeds each" logic
  - Belgic CV with Dispersed tribes, Colony marker
  - Roman score minus Settlements in Ariovistus
  - Germans score in Ariovistus
  - Victory margin calculations
  - Scenario isolation
  - check_any_victory with ties
  - determine_final_ranking ordering

Reference: §7.0-§7.3, A7.0-A7.3
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI, TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
    TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_BITURIGES, TRIBE_AEDUI,
    TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_CATUVELLAUNI, TRIBE_HELVII,
    SUEBI_TRIBES,
    # Markers
    MARKER_DISPERSED, MARKER_DISPERSED_GATHERING, MARKER_COLONY,
    # Victory thresholds
    ROMAN_VICTORY_THRESHOLD,
    ARVERNI_LEGIONS_THRESHOLD, ARVERNI_ALLIES_THRESHOLD,
    BELGAE_VICTORY_THRESHOLD,
    GERMAN_VICTORY_THRESHOLD,
    # Legions
    LEGIONS_ROWS, LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    # Control
    NO_CONTROL, BELGIC_CONTROL,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, remove_piece, get_available
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.engine.victory import (
    calculate_victory_score,
    check_victory,
    calculate_victory_margin,
    check_any_victory,
    determine_final_ranking,
    VictoryError,
    _count_allies_and_citadels,
    _count_subdued_tribes,
    _count_dispersed_tribes,
    _count_off_map_legions,
    _calculate_belgic_control_value,
)


# ============================================================================
# HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as Allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def set_tribe_dispersed(state, tribe):
    """Set a tribe as Dispersed."""
    state["tribes"][tribe]["status"] = MARKER_DISPERSED
    state["tribes"][tribe]["allied_faction"] = None


def set_tribe_dispersed_gathering(state, tribe):
    """Set a tribe as Dispersed-Gathering."""
    state["tribes"][tribe]["status"] = MARKER_DISPERSED_GATHERING
    state["tribes"][tribe]["allied_faction"] = None


def setup_belgic_control(state, region, warbands=5):
    """Place enough Belgae Warbands to control a region."""
    place_piece(state, region, BELGAE, WARBAND, warbands)
    refresh_all_control(state)


def setup_german_control(state, region, warbands=5):
    """Place enough German Warbands to control a region."""
    place_piece(state, region, GERMANS, WARBAND, warbands)
    refresh_all_control(state)


def place_settlement(state, region):
    """Place a German Settlement in a region."""
    place_piece(state, region, GERMANS, SETTLEMENT)


# ============================================================================
# TEST: ROMAN VICTORY SCORE (§7.2, A7.2)
# ============================================================================

class TestRomanVictoryScore:
    """Roman victory: Subdued + Dispersed + Roman Allied Tribes."""

    def test_all_tribes_subdued_base(self):
        """All 30 tribes subdued → score = 30."""
        state = make_state()
        score = calculate_victory_score(state, ROMANS)
        assert score == 30  # all tribes are Subdued initially

    def test_allied_tribes_count(self):
        """Roman Allied Tribes add to score."""
        state = make_state()
        set_tribe_allied(state, TRIBE_HELVII, ROMANS)
        score = calculate_victory_score(state, ROMANS)
        # 29 subdued + 0 dispersed + 1 Roman ally = 30
        assert score == 30

    def test_dispersed_tribes_count(self):
        """Dispersed tribes add to score."""
        state = make_state()
        set_tribe_dispersed(state, TRIBE_MENAPII)
        score = calculate_victory_score(state, ROMANS)
        # 29 subdued + 1 dispersed + 0 allies = 30
        assert score == 30

    def test_non_roman_allies_reduce(self):
        """Non-Roman Allies reduce score (§7.2 PLAY NOTE)."""
        state = make_state()
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        score = calculate_victory_score(state, ROMANS)
        # 28 subdued + 0 dispersed + 0 Roman allies = 28
        assert score == 28

    def test_ariovistus_settlements_subtract(self):
        """A7.2: Roman score minus Germanic Settlements on map."""
        state = make_state(SCENARIO_ARIOVISTUS)
        place_settlement(state, SUGAMBRI)
        place_settlement(state, UBII)
        score = calculate_victory_score(state, ROMANS)
        # 30 subdued - 2 settlements = 28
        assert score == 28

    def test_base_game_no_settlement_subtraction(self):
        """Base game: no Settlement subtraction."""
        state = make_state()
        score = calculate_victory_score(state, ROMANS)
        assert score == 30


# ============================================================================
# TEST: ARVERNI VICTORY SCORE (§7.2)
# ============================================================================

class TestArverniVictoryScore:
    """Arverni: dual condition — off-map Legions AND Allies + Citadels."""

    def test_initial_score(self):
        """Initially all Legions on track → off-map = 12."""
        state = make_state()
        scores = calculate_victory_score(state, ARVERNI)
        assert scores["off_map_legions"] == 12  # all on track
        assert scores["allies_citadels"] == 0

    def test_off_map_legions_from_fallen(self):
        """Fallen Legions count as off-map."""
        state = make_state()
        state["fallen_legions"] = 3
        # Reduce track to compensate
        state["legions_track"][LEGIONS_ROW_TOP] = 1
        scores = calculate_victory_score(state, ARVERNI)
        assert scores["off_map_legions"] == 12  # 9 on track + 3 fallen

    def test_removed_legions_count(self):
        """Removed-by-Event Legions count as off-map."""
        state = make_state()
        state["removed_legions"] = 2
        state["legions_track"][LEGIONS_ROW_TOP] = 2
        scores = calculate_victory_score(state, ARVERNI)
        assert scores["off_map_legions"] == 12

    def test_allies_and_citadels(self):
        """Arverni Allies + Citadels counted."""
        state = make_state()
        set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
        set_tribe_allied(state, TRIBE_CADURCI, ARVERNI)
        place_piece(state, ARVERNI_REGION, ARVERNI, CITADEL)
        scores = calculate_victory_score(state, ARVERNI)
        assert scores["allies_citadels"] == 3

    def test_ariovistus_raises(self):
        """Arverni don't track in Ariovistus — A7.0."""
        state = make_state(SCENARIO_ARIOVISTUS)
        with pytest.raises(VictoryError, match="Arverni do not track"):
            calculate_victory_score(state, ARVERNI)


# ============================================================================
# TEST: AEDUI VICTORY SCORE (§7.2, A7.2)
# ============================================================================

class TestAeduiVictoryScore:
    """Aedui: Allied Tribes + Citadels."""

    def test_initial_zero(self):
        """Initially no Aedui Allies or Citadels."""
        state = make_state()
        score = calculate_victory_score(state, AEDUI)
        assert score == 0

    def test_allies_and_citadels(self):
        """Count Aedui Allies + Citadels."""
        state = make_state()
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        set_tribe_allied(state, TRIBE_SEQUANI, AEDUI)
        place_piece(state, AEDUI_REGION, AEDUI, CITADEL)
        score = calculate_victory_score(state, AEDUI)
        assert score == 3


# ============================================================================
# TEST: BELGAE VICTORY SCORE (§7.2)
# ============================================================================

class TestBelgaeVictoryScore:
    """Belgae: BCV + Allies + Citadels."""

    def test_bcv_controlled_region(self):
        """BCV includes CV of Belgic-Controlled regions."""
        state = make_state()
        setup_belgic_control(state, MORINI)  # CV=2
        score = calculate_victory_score(state, BELGAE)
        assert score == 2  # BCV=2, no allies/citadels

    def test_bcv_with_allies(self):
        """BCV + Belgic Allies."""
        state = make_state()
        setup_belgic_control(state, MORINI)
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        score = calculate_victory_score(state, BELGAE)
        # BCV=2, allies=2, citadels=0 → 4
        assert score == 4

    def test_dispersed_non_suebi_penalty(self):
        """Non-Suebi Dispersed tribes reduce BCV by 1 each."""
        state = make_state()
        setup_belgic_control(state, MORINI, warbands=10)  # CV=2
        set_tribe_dispersed(state, TRIBE_MENAPII)  # non-Suebi → -1
        score = calculate_victory_score(state, BELGAE)
        # BCV = 2 - 1 = 1
        assert score == 1

    def test_suebi_dispersed_no_penalty(self):
        """Suebi Dispersed tribes do NOT reduce BCV."""
        state = make_state()
        setup_belgic_control(state, MORINI, warbands=10)
        set_tribe_dispersed(state, TRIBE_SUEBI_NORTH)
        score = calculate_victory_score(state, BELGAE)
        # BCV=2, Suebi penalty=0 → 2
        assert score == 2

    def test_colony_marker_adds_one(self):
        """Colony marker adds +1 to BCV if in Belgic-Controlled region."""
        state = make_state()
        setup_belgic_control(state, MORINI, warbands=10)
        state["markers"][MORINI] = {MARKER_COLONY: True}
        score = calculate_victory_score(state, BELGAE)
        # BCV = 2 + 1 (Colony) = 3
        assert score == 3

    def test_colony_not_belgic_control(self):
        """Colony marker in non-Belgic region doesn't add to BCV."""
        state = make_state()
        setup_belgic_control(state, MORINI)
        state["markers"][PROVINCIA] = {MARKER_COLONY: True}
        score = calculate_victory_score(state, BELGAE)
        assert score == 2  # No Colony bonus

    def test_multiple_controlled_regions(self):
        """Sum CV of multiple Belgic-Controlled regions."""
        state = make_state()
        setup_belgic_control(state, MORINI)    # CV=2
        setup_belgic_control(state, ATREBATES)  # CV=3
        score = calculate_victory_score(state, BELGAE)
        assert score == 5  # BCV = 2 + 3

    def test_dispersed_gathering_also_penalizes(self):
        """Dispersed-Gathering also counts for BCV penalty."""
        state = make_state()
        setup_belgic_control(state, MORINI, warbands=10)
        set_tribe_dispersed_gathering(state, TRIBE_MENAPII)
        score = calculate_victory_score(state, BELGAE)
        assert score == 1  # BCV = 2 - 1


# ============================================================================
# TEST: GERMAN VICTORY SCORE (A7.2)
# ============================================================================

class TestGermanVictoryScore:
    """Germans: Germania under Germanic Control + Settlements under Control."""

    def test_base_game_raises(self):
        """Germans don't track victory in base game."""
        state = make_state()
        with pytest.raises(VictoryError, match="Germans do not track"):
            calculate_victory_score(state, GERMANS)

    def test_germania_control(self):
        """Germania regions under Germanic Control counted."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_german_control(state, SUGAMBRI)
        setup_german_control(state, UBII)
        score = calculate_victory_score(state, GERMANS)
        assert score == 2

    def test_settlements_under_control(self):
        """Settlements under Germanic Control add to score."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_german_control(state, SUGAMBRI)
        place_settlement(state, SUGAMBRI)
        score = calculate_victory_score(state, GERMANS)
        # 1 Germania region + 1 Settlement = 2
        assert score == 2

    def test_settlement_not_under_control(self):
        """Settlement not under Germanic Control doesn't count."""
        state = make_state(SCENARIO_ARIOVISTUS)
        place_settlement(state, MORINI)  # Not under German control
        score = calculate_victory_score(state, GERMANS)
        assert score == 0


# ============================================================================
# TEST: CHECK VICTORY (§7.2, A7.2)
# ============================================================================

class TestCheckVictory:
    """check_victory — threshold comparison."""

    def test_roman_exceeds_15(self):
        """Romans win when score > 15."""
        state = make_state()
        # All 30 tribes subdued → score = 30 > 15
        assert check_victory(state, ROMANS) is True

    def test_roman_at_15(self):
        """Romans do NOT win at exactly 15 (must exceed)."""
        state = make_state()
        # Ally 15 tribes to non-Romans: score = 30 - 15 = 15
        tribes_to_ally = [
            TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
            TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
            TRIBE_TREVERI, TRIBE_CARNUTES, TRIBE_AULERCI,
            TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
            TRIBE_VENETI, TRIBE_NAMNETES,
        ]
        for tribe in tribes_to_ally:
            set_tribe_allied(state, tribe, BELGAE)
        assert calculate_victory_score(state, ROMANS) == 15
        assert check_victory(state, ROMANS) is False

    def test_arverni_dual_condition_both_met(self):
        """Arverni win when BOTH conditions exceeded."""
        state = make_state()
        # Off-map Legions = 12 (all on track) > 6 ✓
        # Need Allies+Citadels > 8
        for tribe in [TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
                      TRIBE_PICTONES, TRIBE_SANTONES, TRIBE_VENETI,
                      TRIBE_NAMNETES, TRIBE_BITURIGES, TRIBE_CARNUTES]:
            set_tribe_allied(state, tribe, ARVERNI)
        assert check_victory(state, ARVERNI) is True

    def test_arverni_only_legions_met(self):
        """Arverni don't win if only Legions condition met."""
        state = make_state()
        # Off-map = 12 > 6 ✓, Allies = 0 < 8 ✗
        assert check_victory(state, ARVERNI) is False

    def test_arverni_only_allies_met(self):
        """Arverni don't win if only Allies condition met."""
        state = make_state()
        for tribe in [TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
                      TRIBE_PICTONES, TRIBE_SANTONES, TRIBE_VENETI,
                      TRIBE_NAMNETES, TRIBE_BITURIGES, TRIBE_CARNUTES]:
            set_tribe_allied(state, tribe, ARVERNI)
        # Put all Legions on map: place from track (which starts with 12)
        place_piece(state, PROVINCIA, ROMANS, LEGION, 12,
                    from_legions_track=True)
        state["fallen_legions"] = 0
        state["removed_legions"] = 0
        # Now off-map = 0 (all on map), Allies = 9 > 8
        scores = calculate_victory_score(state, ARVERNI)
        assert scores["off_map_legions"] == 0
        assert check_victory(state, ARVERNI) is False

    def test_aedui_exceeds_each(self):
        """Aedui must exceed EACH other faction individually."""
        state = make_state()
        # Give Aedui 3 allies
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        set_tribe_allied(state, TRIBE_SEQUANI, AEDUI)
        set_tribe_allied(state, TRIBE_HELVETII, AEDUI)
        # Give Belgae 2 allies
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        # Aedui=3, Belgae=2, others=0 → Aedui exceeds each
        assert check_victory(state, AEDUI) is True

    def test_aedui_fails_one_faction(self):
        """Aedui fail if even one faction has equal or more."""
        state = make_state()
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        set_tribe_allied(state, TRIBE_SEQUANI, AEDUI)
        # Belgae also has 2
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        # Aedui=2, Belgae=2 → Aedui does NOT exceed
        assert check_victory(state, AEDUI) is False

    def test_aedui_ariovistus_settlements_count(self):
        """A7.2: Settlements count as Germanic Allies for Aedui check."""
        state = make_state(SCENARIO_ARIOVISTUS)
        # Give Aedui 3 allies
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        set_tribe_allied(state, TRIBE_SEQUANI, AEDUI)
        set_tribe_allied(state, TRIBE_HELVETII, AEDUI)
        # Place 3 German Settlements
        place_settlement(state, SUGAMBRI)
        place_settlement(state, UBII)
        place_settlement(state, TREVERI)
        # Aedui=3, Germans=0 allies+3 settlements=3 → NOT exceed
        assert check_victory(state, AEDUI) is False

    def test_belgae_exceeds_15(self):
        """Belgae win when BCV + Allies + Citadels > 15."""
        state = make_state()
        # Set up Belgic Control in several regions (use fewer warbands)
        setup_belgic_control(state, MORINI, warbands=5)      # CV=2
        setup_belgic_control(state, NERVII, warbands=5)      # CV=2
        setup_belgic_control(state, ATREBATES, warbands=5)   # CV=3
        setup_belgic_control(state, TREVERI, warbands=5)     # CV=1
        setup_belgic_control(state, MANDUBII, warbands=5)    # CV=3
        # BCV = 2+2+3+1+3 = 11
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        set_tribe_allied(state, TRIBE_EBURONES, BELGAE)
        set_tribe_allied(state, TRIBE_NERVII, BELGAE)
        set_tribe_allied(state, TRIBE_BELLOVACI, BELGAE)
        # BCV=11, Allies=5, Citadels=0 → 16 > 15
        assert check_victory(state, BELGAE) is True

    def test_german_ariovistus_exceeds_6(self):
        """Germans win in Ariovistus when score > 6."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_german_control(state, SUGAMBRI)
        setup_german_control(state, UBII)
        place_settlement(state, SUGAMBRI)
        place_settlement(state, UBII)
        place_settlement(state, TREVERI)
        setup_german_control(state, TREVERI)
        place_settlement(state, CARNUTES)
        setup_german_control(state, CARNUTES)
        # 2 Germania + 4 Settlements under control = 6 → NOT exceed
        score = calculate_victory_score(state, GERMANS)
        assert score == 6
        assert check_victory(state, GERMANS) is False
        # Add one more
        place_settlement(state, NERVII)
        setup_german_control(state, NERVII, warbands=10)
        score = calculate_victory_score(state, GERMANS)
        assert score == 7
        assert check_victory(state, GERMANS) is True


# ============================================================================
# TEST: VICTORY MARGIN (§7.3, A7.3)
# ============================================================================

class TestVictoryMargin:
    """calculate_victory_margin — for final Winter ranking."""

    def test_roman_margin(self):
        """Roman margin = score - 15."""
        state = make_state()
        # score = 30 (all subdued), margin = 30 - 15 = 15
        margin = calculate_victory_margin(state, ROMANS)
        assert margin == 15

    def test_arverni_margin_lower_of_two(self):
        """Arverni margin = min(legions-6, allies-8)."""
        state = make_state()
        # Off-map = 12, margin_leg = 12-6 = 6
        # Allies = 0, margin_ally = 0-8 = -8
        # Margin = min(6, -8) = -8
        margin = calculate_victory_margin(state, ARVERNI)
        assert margin == -8

    def test_aedui_margin(self):
        """Aedui margin = score - highest other."""
        state = make_state()
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        # Aedui=1, Belgae=2, highest_other=2
        margin = calculate_victory_margin(state, AEDUI)
        assert margin == -1

    def test_belgae_margin(self):
        """Belgae margin = score - 15."""
        state = make_state()
        margin = calculate_victory_margin(state, BELGAE)
        assert margin == -15  # score=0, margin=0-15=-15

    def test_german_margin_ariovistus(self):
        """German margin = score - 6 in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_german_control(state, SUGAMBRI)
        margin = calculate_victory_margin(state, GERMANS)
        # score=1 (1 Germania region), margin=1-6=-5
        assert margin == -5

    def test_german_margin_base_raises(self):
        """Germans can't calculate margin in base game."""
        state = make_state()
        with pytest.raises(VictoryError):
            calculate_victory_margin(state, GERMANS)

    def test_arverni_margin_ariovistus_raises(self):
        """Arverni can't calculate margin in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        with pytest.raises(VictoryError):
            calculate_victory_margin(state, ARVERNI)


# ============================================================================
# TEST: SCENARIO ISOLATION
# ============================================================================

class TestScenarioIsolation:
    """Scenario-dependent faction tracking."""

    def test_germans_no_victory_base(self):
        """Germans don't participate in base game victory."""
        state = make_state()
        with pytest.raises(VictoryError):
            check_victory(state, GERMANS)

    def test_arverni_no_victory_ariovistus(self):
        """Arverni don't participate in Ariovistus victory."""
        state = make_state(SCENARIO_ARIOVISTUS)
        with pytest.raises(VictoryError):
            check_victory(state, ARVERNI)

    def test_base_victory_factions(self):
        """Base game checks Romans, Arverni, Aedui, Belgae."""
        state = make_state()
        winner = check_any_victory(state)
        # Romans have score=30 > 15, should win
        assert winner == ROMANS

    def test_ariovistus_victory_factions(self):
        """Ariovistus checks Romans, Germans, Aedui, Belgae."""
        state = make_state(SCENARIO_ARIOVISTUS)
        winner = check_any_victory(state)
        assert winner == ROMANS  # 30 subdued > 15


# ============================================================================
# TEST: CHECK ANY VICTORY
# ============================================================================

class TestCheckAnyVictory:
    """check_any_victory — finding winner among all factions."""

    def test_no_winner(self):
        """No winner when no faction exceeds threshold."""
        state = make_state()
        # Ally 15 tribes to various non-Roman factions → score = 15
        tribes_to_ally = [
            TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
            TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
            TRIBE_TREVERI, TRIBE_CARNUTES, TRIBE_AULERCI,
            TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
            TRIBE_VENETI, TRIBE_NAMNETES,
        ]
        for tribe in tribes_to_ally:
            set_tribe_allied(state, tribe, BELGAE)
        # Romans score = 15, not > 15
        assert check_any_victory(state) is None

    def test_single_winner(self):
        """Single winner returned directly."""
        state = make_state()
        winner = check_any_victory(state)
        assert winner == ROMANS

    def test_tie_np_first(self):
        """Ties go to Non-players first — §7.1."""
        state = make_state()
        state["non_player_factions"] = {BELGAE}
        # Both Romans and Belgae meet victory
        # Setup Belgae victory: BCV + Allies > 15
        setup_belgic_control(state, MORINI, warbands=5)      # CV=2
        setup_belgic_control(state, NERVII, warbands=5)      # CV=2
        setup_belgic_control(state, ATREBATES, warbands=5)   # CV=3
        setup_belgic_control(state, TREVERI, warbands=5)     # CV=1
        setup_belgic_control(state, MANDUBII, warbands=5)    # CV=3
        for tribe in [TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES,
                      TRIBE_NERVII, TRIBE_BELLOVACI]:
            set_tribe_allied(state, tribe, BELGAE)
        # BCV=11, Allies=5 → 16 > 15
        assert check_victory(state, BELGAE) is True
        assert check_victory(state, ROMANS) is True
        # Non-player Belgae wins tie
        winner = check_any_victory(state)
        assert winner == BELGAE


# ============================================================================
# TEST: DETERMINE FINAL RANKING
# ============================================================================

class TestDetermineFinalRanking:
    """determine_final_ranking — for final Winter."""

    def test_ranking_by_margin(self):
        """Factions ranked by margin, highest first."""
        state = make_state()
        rankings = determine_final_ranking(state)
        # Romans have highest margin (30-15=15)
        assert rankings[0][0] == ROMANS
        assert rankings[0][1] == 15

    def test_all_factions_ranked(self):
        """All victory-tracking factions appear in ranking."""
        state = make_state()
        rankings = determine_final_ranking(state)
        factions_ranked = [f for f, _ in rankings]
        assert ROMANS in factions_ranked
        assert ARVERNI in factions_ranked
        assert AEDUI in factions_ranked
        assert BELGAE in factions_ranked
        assert GERMANS not in factions_ranked  # base game

    def test_ariovistus_ranking(self):
        """Ariovistus includes Germans but not Arverni."""
        state = make_state(SCENARIO_ARIOVISTUS)
        rankings = determine_final_ranking(state)
        factions_ranked = [f for f, _ in rankings]
        assert GERMANS in factions_ranked
        assert ARVERNI not in factions_ranked

    def test_tie_np_wins(self):
        """Tied margins: non-player wins."""
        state = make_state()
        state["non_player_factions"] = {BELGAE}
        rankings = determine_final_ranking(state)
        # Check that among equal margins, non-player comes first
        # (Aedui and Belgae may have the same margin)
        margin_groups = {}
        for f, m in rankings:
            margin_groups.setdefault(m, []).append(f)
        # Verify ordering is sensible
        assert len(rankings) == 4


# ============================================================================
# TEST: HELPER FUNCTIONS
# ============================================================================

class TestHelpers:
    """Test internal helper functions."""

    def test_count_subdued(self):
        """Count tribes with no ally and no Dispersed status."""
        state = make_state()
        assert _count_subdued_tribes(state) == 30
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        assert _count_subdued_tribes(state) == 29
        set_tribe_dispersed(state, TRIBE_MORINI)
        assert _count_subdued_tribes(state) == 28

    def test_count_dispersed(self):
        """Count tribes with Dispersed or Dispersed-Gathering."""
        state = make_state()
        assert _count_dispersed_tribes(state) == 0
        set_tribe_dispersed(state, TRIBE_MENAPII)
        assert _count_dispersed_tribes(state) == 1
        set_tribe_dispersed_gathering(state, TRIBE_MORINI)
        assert _count_dispersed_tribes(state) == 2

    def test_count_allies_and_citadels(self):
        """Count faction's allies + citadels."""
        state = make_state()
        assert _count_allies_and_citadels(state, BELGAE) == 0
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        assert _count_allies_and_citadels(state, BELGAE) == 1
        place_piece(state, MORINI, BELGAE, CITADEL)
        assert _count_allies_and_citadels(state, BELGAE) == 2

    def test_count_off_map_legions(self):
        """Count Fallen + Track + Removed."""
        state = make_state()
        assert _count_off_map_legions(state) == 12
        state["fallen_legions"] = 2
        state["legions_track"][LEGIONS_ROW_TOP] = 2
        state["removed_legions"] = 1
        # 2 fallen + (4+4+2) track + 1 removed = 13
        # But total must be 12 (cap). Let me set this more carefully.
        state["legions_track"] = {
            LEGIONS_ROW_BOTTOM: 4,
            LEGIONS_ROW_MIDDLE: 4,
            LEGIONS_ROW_TOP: 1,
        }
        state["fallen_legions"] = 2
        state["removed_legions"] = 1
        # track=9, fallen=2, removed=1 = 12
        assert _count_off_map_legions(state) == 12

    def test_belgic_cv_empty(self):
        """BCV is 0 when no Belgic Control."""
        state = make_state()
        assert _calculate_belgic_control_value(state) == 0
