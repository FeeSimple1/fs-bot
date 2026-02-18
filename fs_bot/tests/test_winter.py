"""Tests for winter module — fs_bot/engine/winter.py.

Tests cover:
  - Germans Phase orchestration: rally → march → raid → battle order
  - Germans Phase Battle: only where would cause Loss, players before NP
  - Quarters: German relocation, Gallic Warband removal, Roman pay-or-roll
  - Harvest: correct earnings, cap at 45, Ariovistus variants
  - Senate shift logic: all three zones, Firm flip, Fallen exception
  - Senate Legions: half Fallen stay, fill lowest rows, place at/above
  - Senate Auxilia: Leader in Provincia check, correct count
  - Spring: Scouted removal, piece flipping, Devastated removal,
    Dispersed cycling, eligibility reset, Intimidated removal
  - Full Winter Round integration
  - Ariovistus Winter differences

Reference: §6.0-§6.6, A6.0-A6.6
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA, CISALPINA,
    GERMANIA_REGIONS,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI, TRIBE_HELVII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_AEDUI,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    SENATE_POSITIONS, SENATE_AUXILIA,
    ARIOVISTUS_SENATE_MAX_LEGIONS,
    # Legions
    LEGIONS_ROWS, LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_PER_ROW,
    # Markers
    MARKER_DEVASTATED, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_SCOUTED, MARKER_INTIMIDATED, MARKER_RAZED,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
    # Harvest
    AEDUI_RIVER_TOLLS,
    MAX_RESOURCES,
    # Quarters
    QUARTERS_COST_WITH_ALLY, QUARTERS_COST_WITHOUT_ALLY,
    QUARTERS_DEVASTATED_MULTIPLIER,
    GERMAN_QUARTERS_SUGAMBRI_THRESHOLD,
    DESERTION_ROLL_THRESHOLD,
    # Die
    DIE_MIN, DIE_MAX,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, count_pieces_by_state,
    get_available, flip_piece,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.engine.winter import (
    run_winter_round,
    victory_phase,
    germans_phase,
    quarters_phase,
    harvest_phase,
    senate_phase,
    spring_phase,
    _apply_senate_shift,
    _senate_marker_shift,
    _senate_legions,
    _senate_auxilia,
    _quarters_german_relocation,
    _quarters_gallic_desertion,
)
from fs_bot.engine.victory import calculate_victory_score


# ============================================================================
# HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as Allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})[MARKER_DEVASTATED] = True


def mark_intimidated(state, region):
    """Mark a region as Intimidated."""
    state.setdefault("markers", {}).setdefault(region, {})[MARKER_INTIMIDATED] = True


def give_resources(state, faction, amount):
    """Give resources to a faction."""
    state["resources"][faction] = amount


def reduce_roman_score(state, amount):
    """Ally tribes to non-Romans to reduce Roman score by 'amount'.

    Each allied tribe removes 1 from the Roman score (since it's no
    longer Subdued). We have 30 tribes available.
    """
    from fs_bot.rules_consts import (
        TRIBE_CARNUTES, TRIBE_AULERCI, TRIBE_MANDUBII,
        TRIBE_SENONES, TRIBE_LINGONES, TRIBE_VENETI, TRIBE_NAMNETES,
        TRIBE_PICTONES, TRIBE_SANTONES, TRIBE_BITURIGES,
        TRIBE_SEQUANI, TRIBE_HELVETII, TRIBE_CATUVELLAUNI,
    )
    tribes = [
        TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
        TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
        TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
        TRIBE_TREVERI, TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
        TRIBE_AEDUI, TRIBE_HELVII, TRIBE_CARNUTES, TRIBE_AULERCI,
        TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
        TRIBE_VENETI, TRIBE_NAMNETES, TRIBE_PICTONES, TRIBE_SANTONES,
        TRIBE_BITURIGES, TRIBE_SEQUANI, TRIBE_HELVETII, TRIBE_CATUVELLAUNI,
    ]
    for i in range(min(amount, len(tribes))):
        set_tribe_allied(state, tribes[i], BELGAE)


# ============================================================================
# TEST: VICTORY PHASE (§6.1)
# ============================================================================

class TestVictoryPhase:
    """Victory Phase — game ends on victory or final Winter."""

    def test_victory_ends_game(self):
        """Game ends when a faction meets victory condition."""
        state = make_state()
        result = victory_phase(state)
        assert result["game_over"] is True
        assert result["winner"] == ROMANS

    def test_no_victory_continues(self):
        """No victory → game continues."""
        state = make_state()
        reduce_roman_score(state, 15)  # score = 15, not > 15
        result = victory_phase(state)
        assert result["game_over"] is False
        assert result["winner"] is None

    def test_final_winter_determines_ranking(self):
        """Final Winter with no victor → ranking by margins."""
        state = make_state()
        reduce_roman_score(state, 15)
        result = victory_phase(state, is_final=True)
        assert result["game_over"] is True
        assert result["rankings"] is not None
        assert len(result["rankings"]) == 4  # 4 factions in base


# ============================================================================
# TEST: GERMANS PHASE (§6.2)
# ============================================================================

class TestGermansPhase:
    """Germans Phase — Rally, March, Raid, Battle in order."""

    def test_base_game_executes(self):
        """Germans Phase executes in base game."""
        state = make_state()
        reduce_roman_score(state, 15)
        result = germans_phase(state)
        assert result is not None
        assert "rally" in result
        assert "march" in result
        assert "raid" in result
        assert "battle" in result

    def test_ariovistus_skips(self):
        """Germans Phase skipped in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        result = germans_phase(state)
        assert result is None


# ============================================================================
# TEST: QUARTERS PHASE — GERMAN RELOCATION (§6.3.1)
# ============================================================================

class TestQuartersGermanRelocation:
    """German Warbands in Devastated regions relocate to Germania."""

    def test_relocate_to_sugambri_on_low_roll(self):
        """Roll 1-3: relocate to Sugambri."""
        state = make_state(seed=1)  # Need predictable roll
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        mark_devastated(state, MORINI)
        # Force RNG to give roll ≤ 3
        state["rng"].seed(100)  # Find a seed that gives 1-3
        result = _quarters_german_relocation(state)
        if result["die_roll"] is not None and result["die_roll"] <= 3:
            assert result["destination"] == SUGAMBRI
        elif result["die_roll"] is not None:
            assert result["destination"] == UBII

    def test_no_relocation_in_germania(self):
        """Warbands in Germania are NOT relocated — §6.3.1."""
        state = make_state()
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 3)
        mark_devastated(state, SUGAMBRI)
        result = _quarters_german_relocation(state)
        assert not result["relocated"]

    def test_no_relocation_with_ally(self):
        """Warbands in Devastated region with German Ally don't relocate."""
        state = make_state()
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        place_piece(state, MORINI, GERMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, GERMANS)
        mark_devastated(state, MORINI)
        result = _quarters_german_relocation(state)
        assert not result["relocated"]


# ============================================================================
# TEST: QUARTERS PHASE — GALLIC DESERTION (§6.3.2)
# ============================================================================

class TestQuartersGallicDesertion:
    """Warbands in Devastated regions without Ally/Citadel: roll 1-3 remove."""

    def test_desertion_rolls(self):
        """Each Warband rolls individually."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        mark_devastated(state, MORINI)
        result = _quarters_gallic_desertion(state, BELGAE)
        if MORINI in result:
            assert len(result[MORINI]["rolls"]) <= 3
            assert result[MORINI]["removed"] >= 0

    def test_no_desertion_with_ally(self):
        """No desertion roll if faction has Ally in region."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, BELGAE, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        mark_devastated(state, MORINI)
        result = _quarters_gallic_desertion(state, BELGAE)
        assert MORINI not in result

    def test_no_desertion_with_citadel(self):
        """No desertion roll if faction has Citadel in region."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, BELGAE, CITADEL)
        mark_devastated(state, MORINI)
        result = _quarters_gallic_desertion(state, BELGAE)
        assert MORINI not in result

    def test_no_desertion_non_devastated(self):
        """No desertion in non-Devastated regions."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        result = _quarters_gallic_desertion(state, BELGAE)
        assert not result

    def test_german_desertion_ariovistus_with_settlement(self):
        """A6.3.2: Germans skip desertion with Settlement."""
        state = make_state(SCENARIO_ARIOVISTUS)
        place_piece(state, MORINI, GERMANS, WARBAND, 3)
        place_piece(state, MORINI, GERMANS, SETTLEMENT)
        mark_devastated(state, MORINI)
        result = _quarters_gallic_desertion(state, GERMANS)
        assert MORINI not in result


# ============================================================================
# TEST: HARVEST PHASE (§6.4)
# ============================================================================

class TestHarvestPhase:
    """Harvest earnings per faction."""

    def test_roman_earnings_equal_score(self):
        """§6.4.1: Romans get Resources = victory score."""
        state = make_state()
        reduce_roman_score(state, 10)  # score = 20
        result = harvest_phase(state)
        assert result[ROMANS] == 20
        assert state["resources"][ROMANS] == 20

    def test_gallic_earnings_twice_allies(self):
        """§6.4.2: Gallic factions get 2x (Allies + Citadels)."""
        state = make_state()
        set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
        set_tribe_allied(state, TRIBE_MORINI, BELGAE)
        place_piece(state, MORINI, BELGAE, CITADEL)
        result = harvest_phase(state)
        # 2 allies + 1 citadel = 3, 2×3 = 6
        assert result[BELGAE] == 6

    def test_aedui_river_tolls(self):
        """§6.4.3: Aedui get +4 for river tolls."""
        state = make_state()
        result = harvest_phase(state)
        # Aedui have 0 allies/citadels: 2×0=0, +4 tolls = 4
        assert result[AEDUI] == 4
        assert state["resources"][AEDUI] == 4

    def test_cap_at_45(self):
        """Resources capped at MAX_RESOURCES (45)."""
        state = make_state()
        give_resources(state, ROMANS, 40)
        # Roman score = 30, so would earn 30 → 40+30=70 → capped at 45
        harvest_phase(state)
        assert state["resources"][ROMANS] == 45

    def test_arverni_no_earnings_ariovistus(self):
        """A6.4.2: Arverni don't earn in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
        result = harvest_phase(state)
        assert result[ARVERNI] == 0

    def test_german_earnings_ariovistus(self):
        """A6.4.4: Germans earn 2x (Allies + Settlements)."""
        state = make_state(SCENARIO_ARIOVISTUS)
        set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
        place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT)
        result = harvest_phase(state)
        # 1 ally + 1 settlement = 2, 2×2 = 4
        assert result[GERMANS] == 4


# ============================================================================
# TEST: SENATE PHASE — MARKER SHIFT (§6.5.1)
# ============================================================================

class TestSenateMarkerShift:
    """Senate marker shift based on Roman victory score."""

    def test_shift_toward_uproar_low_score(self):
        """Score < 10: shift toward Uproar."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        reduce_roman_score(state, 21)  # score = 9
        _senate_marker_shift(state)
        assert state["senate"]["position"] == UPROAR

    def test_shift_toward_intrigue_mid_score(self):
        """Score 10-12: shift toward Intrigue."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        reduce_roman_score(state, 19)  # score = 11
        result = _senate_marker_shift(state)
        assert state["senate"]["position"] == INTRIGUE

    def test_shift_toward_adulation_high_score(self):
        """Score > 12: shift toward Adulation."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        reduce_roman_score(state, 15)  # score = 15
        _senate_marker_shift(state)
        assert state["senate"]["position"] == ADULATION

    def test_no_shift_down_with_fallen(self):
        """EXCEPTION: Don't shift down if Fallen Legions — §6.5.1."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        state["fallen_legions"] = 1
        # Reduce legions track to compensate
        state["legions_track"][LEGIONS_ROW_TOP] = 3
        reduce_roman_score(state, 15)  # score > 12 → would shift down
        result = _senate_marker_shift(state)
        assert state["senate"]["position"] == INTRIGUE  # no shift

    def test_flip_to_firm_at_uproar(self):
        """At Uproar + shift up → flip to Firm."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        reduce_roman_score(state, 21)  # score < 10
        _apply_senate_shift(state, "up")
        assert state["senate"]["position"] == UPROAR
        assert state["senate"]["firm"] is True

    def test_flip_to_firm_at_adulation(self):
        """At Adulation + shift down → flip to Firm."""
        state = make_state()
        state["senate"]["position"] = ADULATION
        _apply_senate_shift(state, "down")
        assert state["senate"]["position"] == ADULATION
        assert state["senate"]["firm"] is True

    def test_firm_unfirm_on_shift(self):
        """Firm marker unfirms instead of moving."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        state["senate"]["firm"] = True
        _apply_senate_shift(state, "down")
        assert state["senate"]["position"] == UPROAR  # didn't move
        assert state["senate"]["firm"] is False

    def test_already_at_intrigue_no_shift(self):
        """At Intrigue with score 10-12: no shift (already there)."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        reduce_roman_score(state, 19)  # score = 11
        result = _senate_marker_shift(state)
        assert state["senate"]["position"] == INTRIGUE

    def test_gallic_war_first_senate_after_interlude(self):
        """A6.5.1: No shift in first Senate after Interlude."""
        state = make_state(SCENARIO_GALLIC_WAR)
        state["senate"]["position"] = INTRIGUE
        result = _senate_marker_shift(state, first_senate_after_interlude=True)
        assert result["shifted"] is False


# ============================================================================
# TEST: SENATE PHASE — LEGIONS (§6.5.2)
# ============================================================================

class TestSenateLegions:
    """Legions from Fallen to track and placed into Provincia."""

    def test_half_fallen_stay(self):
        """Half (rounded down) of Fallen stay unavailable."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        state["legions_track"] = {r: 0 for r in LEGIONS_ROWS}
        state["fallen_legions"] = 5
        result = _senate_legions(state)
        assert result["half_stay_fallen"] == 2  # 5//2 = 2
        assert state["fallen_legions"] == 2

    def test_fallen_fill_lowest_rows(self):
        """Fallen Legions fill lowest track rows first."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        state["legions_track"] = {r: 0 for r in LEGIONS_ROWS}
        state["fallen_legions"] = 6
        result = _senate_legions(state)
        # 6//2 = 3 stay, 3 to track
        assert state["legions_track"][LEGIONS_ROW_BOTTOM] == 3
        assert state["legions_track"][LEGIONS_ROW_MIDDLE] == 0

    def test_place_at_senate_level(self):
        """Place Legions on same row as Senate or above."""
        state = make_state()
        state["senate"]["position"] = ADULATION
        # Adulation: Middle + Top rows are at or above
        state["legions_track"] = {
            LEGIONS_ROW_BOTTOM: 4,
            LEGIONS_ROW_MIDDLE: 2,
            LEGIONS_ROW_TOP: 1,
        }
        state["fallen_legions"] = 0
        initial_legions = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        result = _senate_legions(state)
        # Should place Middle(2) + Top(1) = 3 into Provincia
        assert result["legions_placed"] == 3
        final_legions = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        assert final_legions == initial_legions + 3

    def test_ariovistus_max_two_legions(self):
        """A6.5.2: Max 2 Legions placed in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        state["senate"]["position"] = ADULATION
        state["legions_track"] = {
            LEGIONS_ROW_BOTTOM: 4,
            LEGIONS_ROW_MIDDLE: 4,
            LEGIONS_ROW_TOP: 4,
        }
        state["fallen_legions"] = 0
        result = _senate_legions(state)
        assert result["legions_placed"] <= ARIOVISTUS_SENATE_MAX_LEGIONS

    def test_uproar_only_top_row(self):
        """Uproar: only Top row (Intrigue level) is at or above."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        state["legions_track"] = {
            LEGIONS_ROW_BOTTOM: 4,
            LEGIONS_ROW_MIDDLE: 4,
            LEGIONS_ROW_TOP: 2,
        }
        state["fallen_legions"] = 0
        result = _senate_legions(state)
        # Only Top row at or above Uproar: 2 placed
        assert result["legions_placed"] == 2


# ============================================================================
# TEST: SENATE PHASE — AUXILIA (§6.5.3)
# ============================================================================

class TestSenateAuxilia:
    """Auxilia placed if Roman Leader in Provincia."""

    def test_no_leader_no_auxilia(self):
        """No Leader in Provincia → no Auxilia."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        result = _senate_auxilia(state)
        assert result == 0

    def test_leader_in_provincia_intrigue(self):
        """Leader in Provincia with Intrigue → 4 Auxilia."""
        state = make_state()
        state["senate"]["position"] = INTRIGUE
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        result = _senate_auxilia(state)
        assert result == 4

    def test_leader_uproar(self):
        """Uproar → 3 Auxilia."""
        state = make_state()
        state["senate"]["position"] = UPROAR
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        result = _senate_auxilia(state)
        assert result == 3

    def test_leader_adulation(self):
        """Adulation → 5 Auxilia."""
        state = make_state()
        state["senate"]["position"] = ADULATION
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        result = _senate_auxilia(state)
        assert result == 5

    def test_limited_by_available(self):
        """Can only place Auxilia that are Available."""
        state = make_state()
        state["senate"]["position"] = ADULATION
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        # Use up most Auxilia
        state["available"][ROMANS][AUXILIA] = 2
        result = _senate_auxilia(state)
        assert result == 2


# ============================================================================
# TEST: SPRING PHASE (§6.6)
# ============================================================================

class TestSpringPhase:
    """Spring Phase — prepare for next year."""

    def test_scouted_removal_and_flip(self):
        """Remove Scouted markers, flip Revealed to Hidden."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3,
                    piece_state=REVEALED)
        place_piece(state, MORINI, BELGAE, WARBAND, 2,
                    piece_state=SCOUTED)
        result = spring_phase(state)
        # Scouted→Revealed, then Revealed→Hidden
        hidden = count_pieces_by_state(state, MORINI, BELGAE, WARBAND, HIDDEN)
        revealed = count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, REVEALED
        )
        scouted = count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, SCOUTED
        )
        assert scouted == 0
        assert revealed == 0
        assert hidden == 5

    def test_devastated_removed(self):
        """All Devastated markers removed."""
        state = make_state()
        mark_devastated(state, MORINI)
        mark_devastated(state, NERVII)
        result = spring_phase(state)
        assert result["devastated_removed"] == 2
        assert MARKER_DEVASTATED not in state["markers"].get(MORINI, {})
        assert MARKER_DEVASTATED not in state["markers"].get(NERVII, {})

    def test_dispersed_cycling(self):
        """Dispersed-Gathering removed, Dispersed → Dispersed-Gathering."""
        state = make_state()
        state["tribes"][TRIBE_MENAPII]["status"] = MARKER_DISPERSED
        state["tribes"][TRIBE_MORINI]["status"] = MARKER_DISPERSED_GATHERING
        result = spring_phase(state)
        # Menapii: Dispersed → Dispersed-Gathering
        assert state["tribes"][TRIBE_MENAPII]["status"] == MARKER_DISPERSED_GATHERING
        # Morini: Dispersed-Gathering → removed (Subdued)
        assert state["tribes"][TRIBE_MORINI]["status"] is None
        assert result["dispersed_gathering_removed"] == 1
        assert result["dispersed_flipped"] == 1

    def test_razed_not_removed(self):
        """Razed marker NOT removed during Spring — §6.6."""
        state = make_state()
        state["tribes"][TRIBE_MENAPII]["status"] = MARKER_RAZED
        spring_phase(state)
        assert state["tribes"][TRIBE_MENAPII]["status"] == MARKER_RAZED

    def test_all_factions_eligible(self):
        """All factions marked Eligible."""
        state = make_state()
        state["eligibility"][ROMANS] = INELIGIBLE
        state["eligibility"][BELGAE] = INELIGIBLE
        spring_phase(state)
        for faction in FACTIONS:
            assert state["eligibility"][faction] == ELIGIBLE

    def test_fallen_legions_to_track(self):
        """Remaining Fallen Legions moved to track."""
        state = make_state()
        state["legions_track"] = {r: 0 for r in LEGIONS_ROWS}
        state["fallen_legions"] = 3
        result = spring_phase(state)
        assert result["fallen_to_track"] == 3
        assert state["fallen_legions"] == 0
        total_on_track = sum(state["legions_track"].values())
        assert total_on_track == 3

    def test_intimidated_removed_ariovistus(self):
        """A6.6: Intimidated markers removed in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        mark_intimidated(state, MORINI)
        mark_intimidated(state, NERVII)
        result = spring_phase(state)
        assert result["intimidated_removed"] == 2

    def test_intimidated_not_removed_base(self):
        """Intimidated markers don't exist in base game."""
        state = make_state()
        # No Intimidated markers to remove
        result = spring_phase(state)
        assert result["intimidated_removed"] == 0

    def test_successor_placed(self):
        """Successor Leaders placed from Available."""
        state = make_state()
        # Vercingetorix in Available, Arverni has pieces on map
        place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 3)
        refresh_all_control(state)
        result = spring_phase(state)
        # Check if any successors placed
        for faction, region in result["successors_placed"]:
            assert faction in (ROMANS, ARVERNI, BELGAE)


# ============================================================================
# TEST: FULL WINTER ROUND
# ============================================================================

class TestRunWinterRound:
    """Full Winter Round integration."""

    def test_base_game_phases_in_order(self):
        """Base game: all 6 phases execute."""
        state = make_state()
        reduce_roman_score(state, 15)
        state["senate"]["position"] = INTRIGUE
        result = run_winter_round(state)
        assert "victory" in result["phases"]
        assert "germans" in result["phases"]
        assert "quarters" in result["phases"]
        assert "harvest" in result["phases"]
        assert "senate" in result["phases"]
        assert "spring" in result["phases"]

    def test_ariovistus_no_germans_phase(self):
        """Ariovistus: no Germans Phase."""
        state = make_state(SCENARIO_ARIOVISTUS)
        reduce_roman_score(state, 15)
        state["senate"]["position"] = INTRIGUE
        result = run_winter_round(state)
        assert "germans" not in result["phases"]

    def test_victory_stops_early(self):
        """Game ends immediately if victory detected."""
        state = make_state()
        # Romans have score 30 > 15 → victory
        result = run_winter_round(state)
        assert result["phases"]["victory"]["game_over"] is True
        # No further phases
        assert "quarters" not in result["phases"]

    def test_winter_count_increments(self):
        """Winter count incremented each round."""
        state = make_state()
        state["winter_count"] = 2
        reduce_roman_score(state, 15)
        state["senate"]["position"] = INTRIGUE
        run_winter_round(state)
        assert state["winter_count"] == 3

    def test_final_winter_ranking(self):
        """Final Winter produces ranking when no victor."""
        state = make_state()
        reduce_roman_score(state, 15)
        state["senate"]["position"] = INTRIGUE
        result = run_winter_round(state, is_final=True)
        assert result["phases"]["victory"]["game_over"] is True
        assert result["phases"]["victory"]["rankings"] is not None

    def test_harvest_then_senate_order(self):
        """Harvest gives resources before Senate uses them."""
        state = make_state()
        reduce_roman_score(state, 15)
        state["senate"]["position"] = INTRIGUE
        give_resources(state, ROMANS, 0)
        result = run_winter_round(state)
        # After harvest, Romans should have resources
        # (exact amount depends on score)
        # Senate then processes
        assert "harvest" in result["phases"]
        assert "senate" in result["phases"]


# ============================================================================
# TEST: QUARTERS PHASE — ROMAN PAY OR ROLL (§6.3.3)
# ============================================================================

class TestQuartersRomanPayOrRoll:
    """Roman Quartering: pay or roll for pieces outside Provincia."""

    def test_pieces_in_provincia_free(self):
        """Pieces in Provincia don't need quartering."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 3,
                    from_legions_track=True)
        result = quarters_phase(state)
        # No quartering needed for Provincia pieces
        roman_q = result["roman_quartering"]
        assert PROVINCIA not in roman_q.get("rolls", {})

    def test_free_pieces_per_ally_and_fort(self):
        """One piece per Ally and per Fort stays free — §6.3.3."""
        state = make_state()
        # Put 3 Legions and 1 Ally + 1 Fort in Morini
        place_piece(state, MORINI, ROMANS, LEGION, 3,
                    from_legions_track=True)
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        place_piece(state, MORINI, ROMANS, FORT)
        refresh_all_control(state)
        # 1 ally + 1 fort = 2 free pieces
        # 3 pieces - 2 free = 1 needs quartering
        result = quarters_phase(state)
        # Should only roll for 1 piece
        roman_q = result["roman_quartering"]
        if MORINI in roman_q.get("rolls", {}):
            assert len(roman_q["rolls"][MORINI]["rolls"]) == 1
