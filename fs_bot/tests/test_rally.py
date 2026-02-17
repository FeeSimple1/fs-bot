"""
Tests for the Rally and Recruit commands.

Covers all factions, both base game and Ariovistus scenarios,
including edge cases and scenario isolation.

Reference: §3.2.1 (Recruit), §3.3.1 (Rally), §3.4.1 (Germanic Rally),
           §3.1.2 (Free Actions), §6.2.1 (Germans Phase Rally),
           A3.2.1, A3.3.1, A3.4.1
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS, SCENARIO_RECONQUEST,
    # Regions
    MORINI, NERVII, ATREBATES, TREVERI, CARNUTES, MANDUBII,
    VENETI, PICTONES, BITURIGES, AEDUI_REGION, SEQUANI,
    ARVERNI_REGION, SUGAMBRI, UBII, PROVINCIA, CISALPINA,
    BRITANNIA,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Control
    ROMAN_CONTROL, NO_CONTROL, ARVERNI_CONTROL,
    GERMANIC_CONTROL, BELGIC_CONTROL, AEDUI_CONTROL,
    FACTION_CONTROL,
    # Costs
    RECRUIT_COST, RALLY_COST, BELGAE_RALLY_OUTSIDE_BELGICA,
    ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX,
    GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT,
    GERMAN_RALLY_COST_AT_SETTLEMENT, GERMAN_RALLY_COST_IN_GERMANIA,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI, TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
    TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_BITURIGES,
    TRIBE_AEDUI, TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_HELVII, TRIBE_NORI,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED,
    # Senate
    ADULATION,
    # Misc
    DISPERSED,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, get_available,
    get_leader_in_region, PieceError,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.commands.rally import (
    recruit_in_region,
    rally_in_region,
    has_supply_line,
    recruit_cost,
    rally_cost,
    validate_recruit_region,
    validate_rally_region,
    germans_phase_rally,
    german_rally_home_bonus,
    CommandError,
)


# ============================================================================
# TEST HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def give_resources(state, faction, amount):
    """Give a faction some resources for testing."""
    state["resources"][faction] = amount


def setup_roman_presence(state, region, *, control=False, leader=None,
                         allies=0, forts=0, legions=0, auxilia=0):
    """Set up Roman pieces in a region for testing."""
    if leader:
        place_piece(state, region, ROMANS, LEADER, leader_name=leader)
    if legions > 0:
        place_piece(state, region, ROMANS, LEGION, legions,
                    from_legions_track=True)
    if auxilia > 0:
        place_piece(state, region, ROMANS, AUXILIA, auxilia)
    if forts > 0:
        place_piece(state, region, ROMANS, FORT, forts)
    if allies > 0:
        place_piece(state, region, ROMANS, ALLY, allies)
    if control:
        # May need extra pieces to ensure control
        refresh_all_control(state)
        if not is_controlled_by(state, region, ROMANS):
            # Place enough auxilia to control
            place_piece(state, region, ROMANS, AUXILIA, 5)
    refresh_all_control(state)


def setup_gallic_presence(state, region, faction, *, allies=0,
                          warbands=0, citadels=0, leader=None):
    """Set up Gallic pieces in a region."""
    if leader:
        place_piece(state, region, faction, LEADER, leader_name=leader)
    if allies > 0:
        place_piece(state, region, faction, ALLY, allies)
    if citadels > 0:
        place_piece(state, region, faction, CITADEL, citadels)
    if warbands > 0:
        place_piece(state, region, faction, WARBAND, warbands)
    refresh_all_control(state)


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_DEVASTATED] = True


def mark_intimidated(state, region):
    """Mark a region as Intimidated (Ariovistus only)."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_INTIMIDATED] = True


# ============================================================================
# ROMAN RECRUIT TESTS — §3.2.1
# ============================================================================

class TestRomanRecruitValidation:
    """Test Recruit region validation — §3.2.1."""

    def test_devastated_region_rejected(self):
        """Cannot Recruit in a Devastated Region — §3.2.1."""
        state = make_state()
        setup_roman_presence(state, MORINI, allies=1)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        mark_devastated(state, MORINI)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="Devastated"):
            recruit_in_region(state, MORINI, "place_auxilia")

    def test_no_roman_presence_rejected(self):
        """Cannot Recruit in region without Roman Control/Leader/Ally/Fort."""
        state = make_state()
        give_resources(state, ROMANS, 10)

        valid, reason = validate_recruit_region(state, MORINI)
        assert valid is False
        assert "no Roman Control" in reason

    def test_roman_control_accepted(self):
        """Recruit valid if region has Roman Control — §3.2.1."""
        state = make_state()
        # Place enough Romans for control
        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)

        valid, _ = validate_recruit_region(state, MORINI)
        assert valid is True

    def test_roman_leader_accepted(self):
        """Recruit valid if region has Roman Leader — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=CAESAR)
        refresh_all_control(state)

        valid, _ = validate_recruit_region(state, MORINI)
        assert valid is True

    def test_roman_ally_accepted(self):
        """Recruit valid if region has Roman Ally — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY)
        refresh_all_control(state)

        valid, _ = validate_recruit_region(state, MORINI)
        assert valid is True

    def test_roman_fort_accepted(self):
        """Recruit valid if region has Roman Fort — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, FORT)
        refresh_all_control(state)

        valid, _ = validate_recruit_region(state, MORINI)
        assert valid is True


class TestRomanRecruitAuxilia:
    """Test Auxilia placement via Recruit — §3.2.1."""

    def test_auxilia_cap_allies_plus_leader_plus_fort(self):
        """Auxilia cap = Roman Allies + Leaders + Forts — §3.2.1."""
        state = make_state()
        # 2 allies + 1 leader + 1 fort = cap of 4
        place_piece(state, MORINI, ROMANS, ALLY, 2)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        set_tribe_allied(state, TRIBE_MORINI, ROMANS)
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=CAESAR)
        place_piece(state, MORINI, ROMANS, FORT)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(state, MORINI, "place_auxilia")
        assert result["pieces_placed"][AUXILIA] == 4

    def test_auxilia_cap_limited_by_available(self):
        """Auxilia placement capped by Available pool — §3.2.1."""
        state = make_state()
        # Use up most Auxilia from Available (20 total)
        for region in [NERVII, ATREBATES, TREVERI, CARNUTES]:
            place_piece(state, region, ROMANS, AUXILIA, 5)

        # Only 0 left in Available, place some presence
        place_piece(state, MORINI, ROMANS, ALLY, 2)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        set_tribe_allied(state, TRIBE_MORINI, ROMANS)
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=CAESAR)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(state, MORINI, "place_auxilia")
        assert result["pieces_placed"][AUXILIA] == 0

    def test_provincia_home_bonus(self):
        """Provincia gets +1 extra Auxilia — §3.2.1 HOME REGION."""
        state = make_state()
        # Provincia has permanent fort already conceptually, place one
        place_piece(state, PROVINCIA, ROMANS, FORT)
        place_piece(state, PROVINCIA, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_HELVII, ROMANS)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        # cap = 1 ally + 1 fort + 1 home bonus = 3
        result = recruit_in_region(state, PROVINCIA, "place_auxilia")
        assert result["pieces_placed"][AUXILIA] == 3

    def test_auxilia_placed_hidden(self):
        """Auxilia placed Hidden per §1.4.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        recruit_in_region(state, MORINI, "place_auxilia")
        # Check pieces are Hidden
        from fs_bot.board.pieces import count_pieces_by_state
        hidden = count_pieces_by_state(
            state, MORINI, ROMANS, AUXILIA, HIDDEN)
        assert hidden == 1

    def test_requires_leader_ally_or_fort(self):
        """Place Auxilia requires Roman Leader, Ally, or Fort — §3.2.1."""
        state = make_state()
        # Only Roman Control via Auxilia, no leader/ally/fort
        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="Leader, Ally, or Fort"):
            recruit_in_region(state, MORINI, "place_auxilia")


class TestRomanRecruitAlly:
    """Test Ally placement via Recruit — §3.2.1."""

    def test_place_ally_with_roman_control(self):
        """Place Ally with Roman Control — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(
            state, MORINI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1
        assert result["tribe_allied"] == TRIBE_MENAPII
        assert state["tribes"][TRIBE_MENAPII]["allied_faction"] == ROMANS

    def test_place_ally_with_caesar(self):
        """Place Ally with Caesar even without Roman Control — §3.2.1."""
        state = make_state()
        # Just Caesar, no control
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=CAESAR)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(
            state, MORINI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1

    def test_cannot_place_ally_without_control_or_caesar(self):
        """Cannot place Ally without Roman Control or Caesar — §3.2.1."""
        state = make_state()
        # Successor + Roman Ally (so region is valid for Recruit), but
        # enemy presence prevents Roman Control
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=SUCCESSOR)
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="Roman Control or Caesar"):
            recruit_in_region(
                state, MORINI, "place_ally", tribe=TRIBE_MORINI)

    def test_cannot_place_at_aedui_tribe(self):
        """Cannot place Roman Ally at Aedui [Bibracte] — §1.4.2."""
        state = make_state()
        place_piece(state, AEDUI_REGION, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="not eligible"):
            recruit_in_region(
                state, AEDUI_REGION, "place_ally", tribe=TRIBE_AEDUI)

    def test_cannot_place_at_arverni_tribe(self):
        """Cannot place Roman Ally at Arverni [Gergovia] — §1.4.2."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="not eligible"):
            recruit_in_region(
                state, ARVERNI_REGION, "place_ally", tribe=TRIBE_ARVERNI)

    def test_cannot_place_at_suebi(self):
        """Cannot place Roman Ally at Suebi — §1.4.2."""
        state = make_state()
        place_piece(state, SUGAMBRI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="not eligible"):
            recruit_in_region(
                state, SUGAMBRI, "place_ally", tribe=TRIBE_SUEBI_NORTH)

    def test_no_allies_available(self):
        """Cannot place Ally when none Available — §3.2.1."""
        state = make_state()
        # Use all Roman Allies (6 total)
        for tribe, region in [
            (TRIBE_MENAPII, MORINI), (TRIBE_MORINI, MORINI),
            (TRIBE_EBURONES, NERVII), (TRIBE_NERVII, NERVII),
            (TRIBE_BELLOVACI, ATREBATES), (TRIBE_REMI, ATREBATES),
        ]:
            place_piece(state, region, ROMANS, ALLY)
            set_tribe_allied(state, tribe, ROMANS)

        place_piece(state, TREVERI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="No Roman Allies Available"):
            recruit_in_region(
                state, TREVERI, "place_ally", tribe=TRIBE_TREVERI)


class TestSupplyLine:
    """Test Supply Line mechanics — §3.2.1, A3.2.1."""

    def test_provincia_alone_qualifies(self):
        """Provincia alone under No Control qualifies — §3.2.1 NOTE."""
        state = make_state()
        # Provincia borders Cisalpina and is under No Control by default
        # Test from Aedui region (adjacent to Provincia)
        assert has_supply_line(state, PROVINCIA) is True

    def test_sequani_alone_qualifies(self):
        """Sequani borders Cisalpina — §3.2.1 NOTE."""
        state = make_state()
        assert has_supply_line(state, SEQUANI) is True

    def test_chain_through_no_control(self):
        """Supply Line chain through No Control regions — §3.2.1."""
        state = make_state()
        # Aedui → Provincia → Cisalpina (all No Control)
        assert has_supply_line(state, AEDUI_REGION) is True

    def test_supply_line_cost_zero(self):
        """Supply Line reduces Recruit cost to 0 — §3.2.1."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, FORT)
        refresh_all_control(state)

        cost = recruit_cost(state, PROVINCIA)
        assert cost == 0

    def test_no_supply_line_cost_two(self):
        """Without Supply Line, Recruit costs 2 — §3.2.1.

        Block the supply line by placing Germans in ALL regions bordering
        Cisalpina (Ubii, Sequani, Provincia). Germans never agree to
        Supply Lines (§3.4.5), so no path can reach the border.
        """
        state = make_state()
        # Germans never agree — §3.4.5. Block all Cisalpina-bordering regions.
        place_piece(state, UBII, GERMANS, WARBAND, 5)
        place_piece(state, SEQUANI, GERMANS, WARBAND, 5)
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 5)
        refresh_all_control(state)

        cost = recruit_cost(state, MORINI)
        assert cost == RECRUIT_COST  # 2

    def test_germans_never_agree(self):
        """Germans never agree to Supply Lines — §3.4.5."""
        state = make_state()
        # German-controlled regions block supply line since they never agree.
        # From Aedui Region, paths to Cisalpina border go through:
        #   Sequani (borders Cisalpina)
        #   Provincia (borders Cisalpina)
        #   Arverni → Provincia (borders Cisalpina)
        #   Mandubii → Treveri → Ubii (borders Cisalpina)
        # Block all Cisalpina-bordering regions with German control.
        # Use 3 per region (15 total = German base game pool).
        place_piece(state, UBII, GERMANS, WARBAND, 3)
        place_piece(state, SEQUANI, GERMANS, WARBAND, 3)
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 3)
        place_piece(state, ARVERNI_REGION, GERMANS, WARBAND, 3)
        refresh_all_control(state)

        # Now check — should have no supply line from Aedui
        result = has_supply_line(state, AEDUI_REGION)
        assert result is False

    def test_supply_line_chain_two_regions(self):
        """Test Supply Line through chain of 2+ Regions — §3.2.1."""
        state = make_state()
        # Bituriges → Aedui → Provincia → Cisalpina (all No Control)
        assert has_supply_line(state, BITURIGES) is True

    def test_ubii_borders_cisalpina_alone(self):
        """Ubii borders Cisalpina per §3.2.1 NOTE.

        Even if Sequani and Provincia are both under hostile control,
        Ubii alone under No Control qualifies as a Supply Line endpoint.
        """
        state = make_state()
        # Block Sequani and Provincia with Arverni (who don't agree)
        place_piece(state, SEQUANI, ARVERNI, WARBAND, 5)
        place_piece(state, PROVINCIA, ARVERNI, WARBAND, 5)
        refresh_all_control(state)

        assert has_supply_line(
            state, UBII, agreements={ARVERNI: False}) is True

    def test_sequani_borders_cisalpina_alone(self):
        """Sequani borders Cisalpina per §3.2.1 NOTE.

        Even if Ubii and Provincia are both under hostile control,
        Sequani alone under No Control qualifies as a Supply Line endpoint.
        """
        state = make_state()
        # Block Ubii and Provincia with Arverni (who don't agree)
        place_piece(state, UBII, ARVERNI, WARBAND, 5)
        place_piece(state, PROVINCIA, ARVERNI, WARBAND, 5)
        refresh_all_control(state)

        assert has_supply_line(
            state, SEQUANI, agreements={ARVERNI: False}) is True

    def test_germans_may_agree_ariovistus(self):
        """Germans may agree to Supply Lines in Ariovistus — A3.2.1.

        In Ariovistus, Germans are a full player faction that can choose
        to agree or not. Their agreement should be checked via the
        agreements dict, same as any other faction.
        """
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        # Put Germans in Provincia so the only path goes through them
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 5)
        refresh_all_control(state)

        # Germans agree → supply line works
        assert has_supply_line(
            state, PROVINCIA, agreements={GERMANS: True}) is True
        # Germans don't agree → supply line blocked
        assert has_supply_line(
            state, PROVINCIA, agreements={GERMANS: False}) is False

    def test_germans_never_agree_base_game(self):
        """Germans never agree to Supply Lines in base game — §3.4.5.

        Regardless of the agreements dict, German-controlled regions
        always block the Supply Line in base game.
        """
        state = make_state()
        # Put Germans in Provincia so the only path goes through them
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 5)
        refresh_all_control(state)

        # Even with explicit agreement=True, Germans block in base game
        assert has_supply_line(
            state, PROVINCIA, agreements={GERMANS: True}) is False
        assert has_supply_line(
            state, PROVINCIA, agreements={GERMANS: False}) is False


class TestRecruitCost:
    """Test Recruit cost accounting — §3.2.1."""

    def test_resources_deducted(self):
        """Resources properly deducted — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        # Block supply line with Germans (who never agree — §3.4.5)
        place_piece(state, UBII, GERMANS, WARBAND, 5)
        place_piece(state, SEQUANI, GERMANS, WARBAND, 5)
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(state, MORINI, "place_auxilia")
        assert result["cost"] == RECRUIT_COST
        assert state["resources"][ROMANS] == 10 - RECRUIT_COST

    def test_insufficient_resources_rejected(self):
        """Cannot Recruit with insufficient Resources — §3.2.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        # Block supply line with Germans (who never agree — §3.4.5)
        place_piece(state, UBII, GERMANS, WARBAND, 5)
        place_piece(state, SEQUANI, GERMANS, WARBAND, 5)
        place_piece(state, PROVINCIA, GERMANS, WARBAND, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 1)  # Not enough (need 2)

        with pytest.raises(CommandError, match="Resources"):
            recruit_in_region(state, MORINI, "place_auxilia")

    def test_free_recruit_no_cost(self):
        """Free Recruit costs nothing — §3.1.2."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        refresh_all_control(state)
        give_resources(state, ROMANS, 0)  # Zero resources

        result = recruit_in_region(
            state, MORINI, "place_auxilia", free=True)
        assert result["cost"] == 0
        assert state["resources"][ROMANS] == 0


# ============================================================================
# GALLIC RALLY TESTS — §3.3.1
# ============================================================================

class TestGallicRallyValidation:
    """Test Rally region validation — §3.3.1."""

    def test_devastated_region_rejected(self):
        """Cannot Rally in a Devastated Region — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        mark_devastated(state, MORINI)
        give_resources(state, ARVERNI, 10)

        with pytest.raises(CommandError, match="Devastated"):
            rally_in_region(
                state, MORINI, ARVERNI, "place_warbands")

    def test_no_faction_presence_rejected(self):
        """Cannot Rally in region without faction presence — §3.3.1."""
        state = make_state()
        give_resources(state, ARVERNI, 10)

        valid, reason = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is False

    def test_faction_control_accepted(self):
        """Rally valid with faction Control — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 10)
        refresh_all_control(state)

        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is True

    def test_faction_ally_accepted(self):
        """Rally valid with faction Ally — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)

        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is True

    def test_faction_citadel_accepted(self):
        """Rally valid with faction Citadel — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, CITADEL)
        refresh_all_control(state)

        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is True

    def test_rally_symbol_accepted(self):
        """Rally valid with Rally symbol (home region) — §3.3.1."""
        state = make_state()
        # Arverni home is Arverni Region
        valid, _ = validate_rally_region(
            state, ARVERNI_REGION, ARVERNI)
        assert valid is True

    def test_vercingetorix_allows_devastated(self):
        """Arverni can Rally in Devastated with Vercingetorix — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, LEADER,
                    leader_name=VERCINGETORIX)
        mark_devastated(state, MORINI)
        refresh_all_control(state)

        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is True


class TestGallicRallyAlly:
    """Test Gallic Ally placement via Rally — §3.3.1."""

    def test_place_ally_with_control(self):
        """Place Ally when faction Controls the region — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        result = rally_in_region(
            state, MORINI, ARVERNI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1
        assert state["tribes"][TRIBE_MENAPII]["allied_faction"] == ARVERNI

    def test_non_aedui_cannot_place_at_bibracte(self):
        """Non-Aedui cannot place Ally at Aedui [Bibracte] — §1.4.2.

        The rule 'only Aedui at Aedui [Bibracte]' means the Aedui tribe
        has a faction restriction: only Aedui faction can place there.
        Other factions placing at Bibracte are rejected.
        """
        state = make_state()
        place_piece(state, AEDUI_REGION, ARVERNI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        with pytest.raises(CommandError, match="not eligible"):
            rally_in_region(
                state, AEDUI_REGION, ARVERNI, "place_ally",
                tribe=TRIBE_AEDUI)

    def test_aedui_can_place_at_non_restricted_tribes(self):
        """Aedui CAN place Allies at non-restricted tribes — §3.3.1.

        The restriction is on TRIBES, not on the FACTION. Aedui can
        place at any Subdued tribe where there's no faction restriction
        excluding them.
        """
        state = make_state()
        place_piece(state, MORINI, AEDUI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, AEDUI, 10)

        result = rally_in_region(
            state, MORINI, AEDUI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1

    def test_arverni_only_at_gergovia(self):
        """Arverni can only place Ally at Arverni [Gergovia] — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        # Menapii is not faction-restricted, so Arverni CAN place there
        result = rally_in_region(
            state, MORINI, ARVERNI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1

    def test_vercingetorix_ally_without_control(self):
        """Arverni with Vercingetorix may place Ally without Control."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, LEADER,
                    leader_name=VERCINGETORIX)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        result = rally_in_region(
            state, MORINI, ARVERNI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1


class TestGallicRallyWarbands:
    """Test Warband placement via Rally — §3.3.1."""

    def test_warbands_equal_allies_plus_citadels_aedui(self):
        """Aedui/Belgae: Warbands = Allies + Citadels — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, AEDUI, ALLY, 2)
        set_tribe_allied(state, TRIBE_MENAPII, AEDUI)
        set_tribe_allied(state, TRIBE_MORINI, AEDUI)
        refresh_all_control(state)
        give_resources(state, AEDUI, 10)

        result = rally_in_region(
            state, MORINI, AEDUI, "place_warbands")
        assert result["pieces_placed"][WARBAND] == 2

    def test_arverni_warbands_extra_one(self):
        """Arverni: Warbands = Allies + Citadels + Leaders + 1 — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY, 2)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        set_tribe_allied(state, TRIBE_MORINI, ARVERNI)
        place_piece(state, MORINI, ARVERNI, LEADER,
                    leader_name=VERCINGETORIX)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        # 2 allies + 1 leader + 1 = 4
        result = rally_in_region(
            state, MORINI, ARVERNI, "place_warbands")
        assert result["pieces_placed"][WARBAND] == 4

    def test_home_region_minimum_one_warband(self):
        """Home region places at least 1 Warband — §3.3.1 HOME REGION."""
        state = make_state()
        # Arverni home region with no allies/citadels/leader
        give_resources(state, ARVERNI, 10)

        result = rally_in_region(
            state, ARVERNI_REGION, ARVERNI, "place_warbands")
        assert result["pieces_placed"][WARBAND] == 1

    def test_belgae_home_region_belgica(self):
        """Belgae home region is any Belgica Region — §3.3.1."""
        state = make_state()
        give_resources(state, BELGAE, 10)

        for belgica_region in BELGICA_REGIONS:
            state2 = make_state()
            give_resources(state2, BELGAE, 10)
            result = rally_in_region(
                state2, belgica_region, BELGAE, "place_warbands")
            assert result["pieces_placed"][WARBAND] >= 1

    def test_warbands_capped_by_available(self):
        """Warband placement stops when pool is empty — cap enforcement."""
        state = make_state()
        # Use up most Arverni Warbands (35 total)
        for region in [MORINI, NERVII, ATREBATES, TREVERI,
                       CARNUTES, MANDUBII, VENETI]:
            place_piece(state, region, ARVERNI, WARBAND, 5)

        # 35 available = 35 placed. Now no more.
        place_piece(state, PICTONES, ARVERNI, ALLY, 3)
        set_tribe_allied(state, TRIBE_PICTONES, ARVERNI)
        set_tribe_allied(state, TRIBE_SANTONES, ARVERNI)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        available = get_available(state, ARVERNI, WARBAND)
        result = rally_in_region(
            state, PICTONES, ARVERNI, "place_warbands")
        assert result["pieces_placed"][WARBAND] == available

    def test_no_ally_or_citadel_rejected_non_home(self):
        """Rejected if no Ally/Citadel in non-home region — §3.3.1."""
        state = make_state()
        # Aedui in Morini (not home) with no Ally/Citadel
        place_piece(state, MORINI, AEDUI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, AEDUI, 10)

        with pytest.raises(CommandError, match="Ally or Citadel"):
            rally_in_region(
                state, MORINI, AEDUI, "place_warbands")


class TestGallicRallyCitadel:
    """Test Citadel placement via Rally — §3.3.1."""

    def test_citadel_replaces_ally_at_city(self):
        """Replace Ally with Citadel at a City — §3.3.1."""
        state = make_state()
        # Place Arverni Ally at Carnutes (city: Cenabum)
        place_piece(state, CARNUTES, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_CARNUTES, ARVERNI)
        place_piece(state, CARNUTES, ARVERNI, WARBAND, 5)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        ally_before = count_pieces(state, CARNUTES, ARVERNI, ALLY)
        citadel_before = count_pieces(state, CARNUTES, ARVERNI, CITADEL)

        result = rally_in_region(
            state, CARNUTES, ARVERNI, "place_citadel",
            tribe=TRIBE_CARNUTES)

        assert result["pieces_placed"][CITADEL] == 1
        assert result["pieces_removed"][ALLY] == 1
        assert count_pieces(state, CARNUTES, ARVERNI, CITADEL) == (
            citadel_before + 1)
        assert count_pieces(state, CARNUTES, ARVERNI, ALLY) == (
            ally_before - 1)

    def test_citadel_not_at_non_city(self):
        """Cannot place Citadel at non-City tribe — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        with pytest.raises(CommandError, match="does not have a City"):
            rally_in_region(
                state, MORINI, ARVERNI, "place_citadel",
                tribe=TRIBE_MENAPII)

    def test_citadel_requires_faction_ally(self):
        """Cannot replace another faction's Ally with Citadel — §3.3.1."""
        state = make_state()
        # Place Roman Ally at Carnutes
        place_piece(state, CARNUTES, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_CARNUTES, ROMANS)
        place_piece(state, CARNUTES, ARVERNI, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        with pytest.raises(CommandError, match="does not have a Arverni"):
            rally_in_region(
                state, CARNUTES, ARVERNI, "place_citadel",
                tribe=TRIBE_CARNUTES)

    def test_no_citadels_available(self):
        """Cannot place Citadel when none Available."""
        state = make_state()
        # Belgae have only 1 Citadel — use it up
        place_piece(state, MORINI, BELGAE, CITADEL)
        # Now place an Ally at a City
        place_piece(state, CARNUTES, BELGAE, ALLY)
        set_tribe_allied(state, TRIBE_CARNUTES, BELGAE)
        place_piece(state, CARNUTES, BELGAE, WARBAND, 10)
        refresh_all_control(state)
        give_resources(state, BELGAE, 10)

        with pytest.raises(CommandError, match="Citadels Available"):
            rally_in_region(
                state, CARNUTES, BELGAE, "place_citadel",
                tribe=TRIBE_CARNUTES)


class TestGallicRallyCost:
    """Test Rally cost accounting — §3.3.1."""

    def test_standard_cost_one(self):
        """Standard Rally cost is 1 Resource — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        result = rally_in_region(
            state, MORINI, ARVERNI, "place_warbands")
        assert result["cost"] == RALLY_COST
        assert state["resources"][ARVERNI] == 10 - RALLY_COST

    def test_belgae_outside_belgica_cost_two(self):
        """Belgae outside Belgica pay 2 Resources — §3.3.1."""
        state = make_state()
        place_piece(state, CARNUTES, BELGAE, ALLY)
        set_tribe_allied(state, TRIBE_CARNUTES, BELGAE)
        refresh_all_control(state)
        give_resources(state, BELGAE, 10)

        cost = rally_cost(state, CARNUTES, BELGAE)
        assert cost == BELGAE_RALLY_OUTSIDE_BELGICA

    def test_belgae_inside_belgica_cost_one(self):
        """Belgae in Belgica pay 1 Resource — §3.3.1."""
        state = make_state()
        cost = rally_cost(state, MORINI, BELGAE)
        assert cost == RALLY_COST

    def test_arverni_devastated_vercingetorix_cost_two(self):
        """Arverni in Devastated with Vercingetorix pay 2 — §3.3.1."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, LEADER,
                    leader_name=VERCINGETORIX)
        mark_devastated(state, MORINI)
        refresh_all_control(state)

        cost = rally_cost(state, MORINI, ARVERNI)
        assert cost == ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX

    def test_free_rally_no_cost(self):
        """Free Rally costs nothing — §3.1.2."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 0)

        result = rally_in_region(
            state, MORINI, ARVERNI, "place_warbands", free=True)
        assert result["cost"] == 0
        assert state["resources"][ARVERNI] == 0


# ============================================================================
# GERMANIC RALLY TESTS — §3.4.1, A3.4.1
# ============================================================================

class TestGermanicRallyBase:
    """Test Germanic Rally in base game — §3.4.1."""

    def test_place_ally_with_germanic_control(self):
        """Place Germanic Ally with Germanic Control — §3.4.1."""
        state = make_state()
        place_piece(state, MORINI, GERMANS, WARBAND, 10)
        refresh_all_control(state)

        result = rally_in_region(
            state, MORINI, GERMANS, "place_ally", tribe=TRIBE_MENAPII)
        assert result["pieces_placed"][ALLY] == 1

    def test_cannot_place_ally_without_control(self):
        """Cannot place Germanic Ally without Germanic Control — §3.4.1."""
        state = make_state()
        # No German control
        refresh_all_control(state)

        valid, _ = validate_rally_region(state, MORINI, GERMANS)
        # Morini is not a German home region, no presence → invalid
        assert valid is False

    def test_warbands_up_to_allies(self):
        """Germanic Warbands up to Allied Tribes — §3.4.1."""
        state = make_state()
        place_piece(state, MORINI, GERMANS, ALLY, 2)
        set_tribe_allied(state, TRIBE_MENAPII, GERMANS)
        set_tribe_allied(state, TRIBE_MORINI, GERMANS)
        refresh_all_control(state)

        result = rally_in_region(
            state, MORINI, GERMANS, "place_warbands")
        assert result["pieces_placed"][WARBAND] == 2

    def test_home_region_minimum_warband(self):
        """Germania regions: at least 1 Warband even without Ally — §3.4.1."""
        state = make_state()

        result = rally_in_region(
            state, SUGAMBRI, GERMANS, "place_warbands")
        assert result["pieces_placed"][WARBAND] >= 1

    def test_free_cost_base_game(self):
        """Germanic Rally is free in base game — §3.4."""
        state = make_state()
        cost = rally_cost(state, MORINI, GERMANS)
        assert cost == 0

    def test_cannot_rally_devastated(self):
        """Germans cannot Rally in Devastated regions — §3.4.1 NOTE."""
        state = make_state()
        mark_devastated(state, SUGAMBRI)

        with pytest.raises(CommandError, match="Devastated"):
            rally_in_region(
                state, SUGAMBRI, GERMANS, "place_warbands")


class TestGermanicRallyAriovistus:
    """Test Germanic Rally in Ariovistus — A3.4.1."""

    def test_cost_in_germania_zero(self):
        """0 Resources in Germania — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        cost = rally_cost(state, SUGAMBRI, GERMANS)
        assert cost == GERMAN_RALLY_COST_IN_GERMANIA

    def test_cost_at_settlement_one(self):
        """1 Resource at Settlement — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_piece(state, MORINI, GERMANS, SETTLEMENT)
        refresh_all_control(state)

        cost = rally_cost(state, MORINI, GERMANS)
        assert cost == GERMAN_RALLY_COST_AT_SETTLEMENT

    def test_cost_outside_germania_no_settlement_two(self):
        """2 Resources outside Germania without Settlement — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        cost = rally_cost(state, MORINI, GERMANS)
        assert cost == GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT

    def test_warbands_include_settlements(self):
        """Warbands up to Allies + Settlements — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_piece(state, MORINI, GERMANS, ALLY, 1)
        set_tribe_allied(state, TRIBE_MENAPII, GERMANS)
        place_piece(state, MORINI, GERMANS, SETTLEMENT)
        refresh_all_control(state)
        give_resources(state, GERMANS, 10)

        # 1 ally + 1 settlement = cap of 2
        result = rally_in_region(
            state, MORINI, GERMANS, "place_warbands")
        assert result["pieces_placed"][WARBAND] == 2

    def test_home_bonus_warband(self):
        """Additional Warband in Settlement/Germania regions — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_piece(state, MORINI, GERMANS, SETTLEMENT)
        place_piece(state, MORINI, GERMANS, ALLY, 1)
        set_tribe_allied(state, TRIBE_MENAPII, GERMANS)
        refresh_all_control(state)
        give_resources(state, GERMANS, 10)

        rally_in_region(state, MORINI, GERMANS, "place_warbands")
        bonus = german_rally_home_bonus(state, MORINI)
        assert bonus == 1

    def test_home_bonus_not_outside_home(self):
        """No bonus in non-home/non-Settlement region — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        bonus = german_rally_home_bonus(state, MORINI)
        assert bonus == 0

    def test_immune_to_intimidation(self):
        """Germans immune to Intimidation for Rally — A3.4.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        mark_intimidated(state, SUGAMBRI)

        valid, _ = validate_rally_region(state, SUGAMBRI, GERMANS)
        assert valid is True


class TestScenarioIsolation:
    """Test that Rally rules are properly gated by scenario."""

    def test_german_rally_base_uses_3_4_1(self):
        """Base game Germans use §3.4.1 rules (free, no settlements)."""
        state = make_state(scenario=SCENARIO_PAX_GALLICA)
        cost = rally_cost(state, SUGAMBRI, GERMANS)
        assert cost == 0

    def test_german_rally_ariovistus_uses_a3_4_1(self):
        """Ariovistus Germans use A3.4.1 rules (paid, settlements)."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        cost = rally_cost(state, MORINI, GERMANS)
        assert cost == 2  # Outside Germania, no settlement

    def test_vercingetorix_not_in_ariovistus(self):
        """Vercingetorix exception doesn't apply in Ariovistus — A1.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        # Arverni have no leader in Ariovistus (cap is 0)
        mark_devastated(state, MORINI)
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)

        valid, reason = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is False
        assert "Devastated" in reason

    def test_intimidation_only_in_ariovistus(self):
        """Intimidation check only applies in Ariovistus — A3.3.1."""
        state = make_state(scenario=SCENARIO_PAX_GALLICA)
        mark_intimidated(state, MORINI)
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)

        # Base game: Intimidation marker is irrelevant
        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is True

    def test_gallic_blocked_by_intimidation_ariovistus(self):
        """Gallic Rally blocked by Intimidation in Ariovistus — A3.3.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        mark_intimidated(state, MORINI)
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)

        valid, reason = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is False
        assert "Intimidated" in reason

    def test_roman_blocked_by_intimidation_ariovistus(self):
        """Roman Recruit blocked by Intimidation in Ariovistus — A3.2.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        mark_intimidated(state, MORINI)
        place_piece(state, MORINI, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        refresh_all_control(state)

        valid, reason = validate_recruit_region(state, MORINI)
        assert valid is False
        assert "Intimidated" in reason

    def test_roman_leader_bypasses_intimidation(self):
        """Roman Leader bypasses Intimidation — A3.2.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        mark_intimidated(state, MORINI)
        place_piece(state, MORINI, ROMANS, LEADER, leader_name=CAESAR)
        refresh_all_control(state)

        valid, _ = validate_recruit_region(state, MORINI)
        assert valid is True


# ============================================================================
# GERMANS PHASE RALLY TESTS — §6.2.1
# ============================================================================

class TestGermansPhaseRally:
    """Test the base-game Germans Phase Rally procedure — §6.2.1."""

    def test_only_base_game(self):
        """Germans Phase Rally is base game only — §6.2.1."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        with pytest.raises(CommandError, match="base game only"):
            germans_phase_rally(state)

    def test_places_allies_with_control(self):
        """Places Germanic Allies in controlled regions — §6.2.1."""
        state = make_state()
        # Give Germans control of Morini
        place_piece(state, MORINI, GERMANS, WARBAND, 10)
        refresh_all_control(state)

        result = germans_phase_rally(state)
        # Should place at least one Ally somewhere
        assert len(result["allies_placed"]) > 0

    def test_places_warbands(self):
        """Places Warbands in regions with Allies — §6.2.1."""
        state = make_state()
        # Pre-place some Allies
        place_piece(state, SUGAMBRI, GERMANS, ALLY)
        set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
        refresh_all_control(state)

        result = germans_phase_rally(state)
        # Should have placed warbands
        total_warbands = sum(result["warbands_placed"].values())
        assert total_warbands > 0

    def test_germania_home_warbands(self):
        """Warbands in Germania even without Allies — §6.2.1."""
        state = make_state()
        result = germans_phase_rally(state)

        # Should place at least 1 warband in each Germania region
        germania_warbands = sum(
            result["warbands_placed"].get(r, 0)
            for r in GERMANIA_REGIONS
        )
        assert germania_warbands >= len(GERMANIA_REGIONS)

    def test_deterministic_with_seed(self):
        """Same seed produces same result — determinism."""
        result1 = germans_phase_rally(make_state(seed=123))
        result2 = germans_phase_rally(make_state(seed=123))
        assert result1["allies_placed"] == result2["allies_placed"]
        assert result1["warbands_placed"] == result2["warbands_placed"]


# ============================================================================
# ARIOVISTUS ARVERNI HOME REGIONS — A1.3.1
# ============================================================================

class TestArverniHomeAriovistus:
    """Test Arverni home regions in Ariovistus — A1.3.1."""

    def test_arverni_home_regions_ariovistus(self):
        """Arverni home in Ariovistus: Veneti, Carnutes, Pictones, Arverni."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)

        for region in [VENETI, CARNUTES, PICTONES, ARVERNI_REGION]:
            valid, _ = validate_rally_region(state, region, ARVERNI)
            assert valid is True, f"Should be valid in {region}"

    def test_arverni_non_home_invalid(self):
        """Non-home region without presence is invalid for Arverni."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)

        valid, _ = validate_rally_region(state, MORINI, ARVERNI)
        assert valid is False


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_dispersed_tribe_not_eligible(self):
        """Cannot place Ally at a Dispersed tribe — §3.2.3."""
        state = make_state()
        # Mark Menapii as Dispersed
        state["tribes"][TRIBE_MENAPII]["status"] = DISPERSED

        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="not eligible"):
            recruit_in_region(
                state, MORINI, "place_ally", tribe=TRIBE_MENAPII)

    def test_already_allied_tribe_not_eligible(self):
        """Cannot place Ally at a tribe that already has an Ally."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="not eligible"):
            recruit_in_region(
                state, MORINI, "place_ally", tribe=TRIBE_MENAPII)

    def test_control_refreshed_after_placement(self):
        """Control is recalculated after piece placement."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        refresh_all_control(state)
        give_resources(state, ARVERNI, 10)

        # After placing warbands, Arverni should control
        rally_in_region(state, MORINI, ARVERNI, "place_warbands")
        assert is_controlled_by(state, MORINI, ARVERNI)

    def test_multiple_tribes_in_region(self):
        """Can choose among multiple Subdued tribes in a region."""
        state = make_state()
        # Mandubii has 3 tribes: Mandubii, Senones, Lingones
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        # Place at Senones (first)
        result1 = recruit_in_region(
            state, MANDUBII, "place_ally", tribe=TRIBE_SENONES)
        assert result1["tribe_allied"] == TRIBE_SENONES

    def test_aedui_home_region(self):
        """Aedui home is Aedui Region — §3.3.1."""
        state = make_state()
        give_resources(state, AEDUI, 10)

        result = rally_in_region(
            state, AEDUI_REGION, AEDUI, "place_warbands")
        assert result["pieces_placed"][WARBAND] >= 1

    def test_recruit_place_ally_returns_tribe_name(self):
        """Recruit returns the tribe name that was allied."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 5)
        refresh_all_control(state)
        give_resources(state, ROMANS, 10)

        result = recruit_in_region(
            state, MORINI, "place_ally", tribe=TRIBE_MENAPII)
        assert result["tribe_allied"] == TRIBE_MENAPII

    def test_rally_cost_deducted_even_zero_warbands(self):
        """Cost is deducted even if 0 warbands placed (pool empty)."""
        state = make_state()
        # Use up all Belgae warbands (25)
        for region in [MORINI, NERVII, ATREBATES, TREVERI, CARNUTES]:
            place_piece(state, region, BELGAE, WARBAND, 5)

        place_piece(state, MANDUBII, BELGAE, ALLY)
        set_tribe_allied(state, TRIBE_MANDUBII, BELGAE)
        refresh_all_control(state)
        give_resources(state, BELGAE, 10)

        result = rally_in_region(
            state, MANDUBII, BELGAE, "place_warbands")
        assert result["cost"] == BELGAE_RALLY_OUTSIDE_BELGICA
        assert result["pieces_placed"][WARBAND] == 0

    def test_german_ally_not_at_bibracte(self):
        """Germans cannot place Ally at Aedui [Bibracte] — §3.4.1."""
        state = make_state()
        place_piece(state, AEDUI_REGION, GERMANS, WARBAND, 10)
        refresh_all_control(state)

        with pytest.raises(CommandError, match="not eligible"):
            rally_in_region(
                state, AEDUI_REGION, GERMANS, "place_ally",
                tribe=TRIBE_AEDUI)

    def test_german_ally_not_at_gergovia(self):
        """Germans cannot place Ally at Arverni [Gergovia] — §3.4.1."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, GERMANS, WARBAND, 10)
        refresh_all_control(state)

        with pytest.raises(CommandError, match="not eligible"):
            rally_in_region(
                state, ARVERNI_REGION, GERMANS, "place_ally",
                tribe=TRIBE_ARVERNI)
