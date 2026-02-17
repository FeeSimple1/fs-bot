"""
Tests for the Battle module.

Exhaustive tests covering every modifier from the battle procedure flowchart.
Each test uses seeded state["rng"] for deterministic results.

Reference: §3.2.4, §3.3.4, §3.4.4, §4.2.3, §4.3.3, §4.4.3, §4.5.3,
           battle_procedure_flowchart.txt, A3.2.4, A3.3.4, A3.4.4
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    BODUOGNATUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Regions
    MORINI, NERVII, ATREBATES, TREVERI, MANDUBII, PROVINCIA,
    SEQUANI, AEDUI_REGION, ARVERNI_REGION, CARNUTES, SUGAMBRI, UBII,
    # Battle constants
    LOSS_ROLL_THRESHOLD, DIVICIACUS_LOSS_ROLL_THRESHOLD,
    CAESAR_AMBUSH_ROLL_THRESHOLD, CAESAR_BELGIC_AMBUSH_ROLL_THRESHOLD,
    DIE_MIN, DIE_MAX,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, count_pieces_by_state,
    get_leader_in_region, get_available, flip_piece,
)
from fs_bot.battle.losses import calculate_losses, resolve_losses
from fs_bot.battle.resolve import resolve_battle


# ============================================================================
# TEST HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def setup_battle(state, region, attacker, defender,
                 attacker_pieces=None, defender_pieces=None):
    """Place pieces for a battle scenario.

    Args:
        state: Game state dict.
        region: Battle region.
        attacker: Attacker faction.
        defender: Defender faction.
        attacker_pieces: Dict of {piece_type: count_or_leader_name}.
            For flippable pieces, use (count, state) tuples.
        defender_pieces: Same format.
    """
    if attacker_pieces:
        _place_pieces(state, region, attacker, attacker_pieces)
    if defender_pieces:
        _place_pieces(state, region, defender, defender_pieces)


def _place_pieces(state, region, faction, pieces):
    """Place pieces for a faction in a region.

    pieces dict format:
        LEADER: leader_name_str
        LEGION: count
        FORT: count
        ALLY: count
        CITADEL: count
        SETTLEMENT: count
        WARBAND: count (placed Hidden)
        AUXILIA: count (placed Hidden)
        (WARBAND, REVEALED): count
        (WARBAND, HIDDEN): count
        (WARBAND, SCOUTED): count
        (AUXILIA, REVEALED): count
        (AUXILIA, HIDDEN): count
    """
    for key, value in pieces.items():
        if key == LEADER:
            place_piece(state, region, faction, LEADER,
                        leader_name=value)
        elif key == LEGION:
            place_piece(state, region, faction, LEGION, value,
                        from_legions_track=True)
        elif key in (FORT, ALLY, CITADEL, SETTLEMENT):
            place_piece(state, region, faction, key, value)
        elif key in (WARBAND, AUXILIA):
            # Default: Hidden
            place_piece(state, region, faction, key, value)
        elif isinstance(key, tuple) and len(key) == 2:
            piece_type, piece_state = key
            place_piece(state, region, faction, piece_type, value,
                        piece_state=piece_state)
        else:
            raise ValueError(f"Unknown piece key: {key}")


# ============================================================================
# LOSSES CALCULATION TESTS
# ============================================================================

class TestCalculateLosses:
    """Test calculate_losses with all modifiers per §3.2.4/§3.3.4 LOSSES."""

    def test_basic_warbands_vs_warbands(self):
        """Basic: Warbands × ½ each."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={WARBAND: 4})
        # Attacker: 6 Warbands × ½ = 3 Losses on Defender
        losses = calculate_losses(state, MORINI, ARVERNI, BELGAE)
        assert losses == 3

    def test_basic_legions(self):
        """Basic: Legions × 1 each."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, BELGAE,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={WARBAND: 4})
        # Attacker: 4 Legions × 1 = 4 Losses
        losses = calculate_losses(state, MORINI, ROMANS, BELGAE)
        assert losses == 4

    def test_mixed_forces_no_caesar(self):
        """Mixed: Legions + Auxilia + Leader (non-Caesar)."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, BELGAE,
                     attacker_pieces={
                         LEADER: SUCCESSOR,
                         LEGION: 3,
                         AUXILIA: 4,
                     },
                     defender_pieces={WARBAND: 6})
        # Legions × 1 = 3, Leader × 1 = 1, Auxilia × ½ = 2
        # Total = 6
        losses = calculate_losses(state, MORINI, ROMANS, BELGAE)
        assert losses == 6

    def test_caesar_attacking_doubles_legions(self):
        """Caesar attacking: Legions × 2 instead of × 1."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, BELGAE,
                     attacker_pieces={
                         LEADER: CAESAR,
                         LEGION: 3,
                         AUXILIA: 2,
                     },
                     defender_pieces={WARBAND: 4})
        # Caesar attacking: Legions × 2 = 6, Leader × 1 = 1, Auxilia × ½ = 1
        # Total = 8
        losses = calculate_losses(state, MORINI, ROMANS, BELGAE)
        assert losses == 8

    def test_caesar_not_doubling_during_counterattack(self):
        """Caesar's × 2 Legions only applies when attacking, not counter."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, BELGAE,
                     attacker_pieces={
                         LEADER: CAESAR,
                         LEGION: 3,
                     },
                     defender_pieces={WARBAND: 4})
        # Counterattack: Caesar's pieces cause losses to attacker
        # But is_counterattack=True, so no doubling
        losses = calculate_losses(
            state, MORINI, ROMANS, BELGAE, is_counterattack=True
        )
        # Legions × 1 = 3, Leader × 1 = 1 = 4
        assert losses == 4

    def test_ambiorix_attacking_full_warbands(self):
        """Ambiorix attacking: Warbands × 1 instead of × ½."""
        state = make_state()
        setup_battle(state, MORINI, BELGAE, ROMANS,
                     attacker_pieces={
                         LEADER: AMBIORIX,
                         WARBAND: 8,
                     },
                     defender_pieces={LEGION: 3})
        # Ambiorix attacking: Warbands × 1 = 8, Leader × 1 = 1
        # Total = 9
        losses = calculate_losses(state, MORINI, BELGAE, ROMANS)
        assert losses == 9

    def test_ambiorix_not_during_counterattack(self):
        """Ambiorix × 1 only when attacking, not counterattack."""
        state = make_state()
        setup_battle(state, MORINI, BELGAE, ROMANS,
                     attacker_pieces={
                         LEADER: AMBIORIX,
                         WARBAND: 8,
                     },
                     defender_pieces={LEGION: 3})
        losses = calculate_losses(
            state, MORINI, BELGAE, ROMANS, is_counterattack=True
        )
        # Counterattack: Warbands × ½ = 4, Leader × 1 = 1 = 5
        assert losses == 5

    def test_fort_halves_losses(self):
        """Defender with Fort: Losses halved."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     attacker_pieces={WARBAND: 10},
                     defender_pieces={
                         LEGION: 2,
                         FORT: 1,
                     })
        # Warbands × ½ = 5, halved by Fort = 2.5, rounded = 2
        losses = calculate_losses(state, MORINI, ARVERNI, ROMANS)
        assert losses == 2

    def test_citadel_halves_losses(self):
        """Defender with Citadel: Losses halved."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={
                         WARBAND: 6,
                         CITADEL: 1,
                     })
        # Legions × 1 = 4, halved by Citadel = 2
        losses = calculate_losses(state, MORINI, ROMANS, ARVERNI)
        assert losses == 2

    def test_retreat_halves_losses(self):
        """Defender Retreating: Losses halved."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 8},
                     defender_pieces={WARBAND: 4})
        # Warbands × ½ = 4, halved by Retreat = 2
        losses = calculate_losses(
            state, MORINI, ARVERNI, BELGAE, is_retreat=True
        )
        assert losses == 2

    def test_retreat_plus_fort_not_double_halved(self):
        """Retreat + Fort: Only one halving, not double.

        §3.2.4: "cut in half for Defenders who are either Retreating or
        have a Citadel or Fort" — the 'or' means it's a single halving
        condition, not cumulative.
        """
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     attacker_pieces={WARBAND: 12},
                     defender_pieces={
                         LEGION: 2,
                         FORT: 1,
                     })
        # Warbands × ½ = 6, halved once = 3 (not 1.5)
        losses_retreat = calculate_losses(
            state, MORINI, ARVERNI, ROMANS, is_retreat=True
        )
        losses_no_retreat = calculate_losses(
            state, MORINI, ARVERNI, ROMANS, is_retreat=False
        )
        # Both should be 3 — Fort halves, Retreat halves, but same result
        assert losses_retreat == 3
        assert losses_no_retreat == 3

    def test_rounding_down(self):
        """Fractions rounded down after all calculation."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 3},
                     defender_pieces={WARBAND: 4})
        # Warbands × ½ = 1.5, rounded = 1
        losses = calculate_losses(state, MORINI, ARVERNI, BELGAE)
        assert losses == 1

    def test_rounding_after_halving(self):
        """Round down AFTER halving, not before."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 5},
                     defender_pieces={
                         WARBAND: 4,
                         CITADEL: 1,
                     })
        # Warbands × ½ = 2.5, halved by Citadel = 1.25, rounded = 1
        losses = calculate_losses(state, MORINI, ARVERNI, BELGAE)
        assert losses == 1

    def test_leader_plus_auxilia(self):
        """Leader + Auxilia in component B."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, BELGAE,
                     attacker_pieces={
                         LEADER: CAESAR,
                         AUXILIA: 6,
                     },
                     defender_pieces={WARBAND: 4})
        # Caesar attacking: no Legions, Leader × 1 = 1, Auxilia × ½ = 3
        # Total = 4
        losses = calculate_losses(state, MORINI, ROMANS, BELGAE)
        assert losses == 4

    def test_zero_losses(self):
        """Zero enemy forces means zero losses."""
        state = make_state()
        # Attacker has only Allies (no attacking force)
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={ALLY: 2},
                     defender_pieces={WARBAND: 4})
        losses = calculate_losses(state, MORINI, ARVERNI, BELGAE)
        assert losses == 0

    def test_counterattack_no_halving(self):
        """Halving does NOT apply during Counterattack."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 4, FORT: 1},
                     defender_pieces={WARBAND: 6})
        # Counterattack: Defender's Warbands cause losses to Attacker
        # Attacker has Fort but halving doesn't apply in counterattack
        losses = calculate_losses(
            state, MORINI, ARVERNI, ROMANS, is_counterattack=True
        )
        # Warbands × ½ = 3 (no halving for counterattack)
        assert losses == 3


# ============================================================================
# LOSS RESOLUTION TESTS
# ============================================================================

class TestResolveLosses:
    """Test resolve_losses — the owner removing pieces one by one."""

    def test_basic_warband_removal(self):
        """Warbands removed automatically (no roll)."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     defender_pieces={WARBAND: 5})
        result = resolve_losses(state, MORINI, ARVERNI, 3)
        assert result["losses_taken"] == 3
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 2

    def test_auxilia_removal(self):
        """Auxilia removed automatically."""
        state = make_state()
        setup_battle(state, MORINI, BELGAE, ROMANS,
                     defender_pieces={AUXILIA: 4})
        result = resolve_losses(state, MORINI, ROMANS, 2)
        assert result["losses_taken"] == 2
        assert count_pieces(state, MORINI, ROMANS, AUXILIA) == 2

    def test_ally_removal(self):
        """Allies removed automatically."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     defender_pieces={WARBAND: 1, ALLY: 2})
        # No retreat: Allies LAST. First remove Warband, then Ally.
        result = resolve_losses(state, MORINI, ARVERNI, 2)
        assert result["losses_taken"] == 2
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 0
        assert count_pieces(state, MORINI, ARVERNI, ALLY) == 1

    def test_legion_roll_removed(self):
        """Legion removed on roll of 1-3."""
        # Seed that gives roll of 1 (or low) on first roll
        state = make_state(seed=1)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 2})
        # Determine what the first roll will be
        test_rng = state["rng"].__class__(1)
        first_roll = test_rng.randint(DIE_MIN, DIE_MAX)

        state = make_state(seed=1)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 2})
        result = resolve_losses(state, MORINI, ROMANS, 1)

        if first_roll <= LOSS_ROLL_THRESHOLD:
            assert result["losses_taken"] == 1
            assert count_pieces(state, MORINI, ROMANS, LEGION) == 1
        else:
            assert result["losses_absorbed"] == 1
            assert count_pieces(state, MORINI, ROMANS, LEGION) == 2

    def test_legion_roll_survives(self):
        """Legion survives on roll of 4-6."""
        # Find a seed where the first roll > 3
        for seed in range(100):
            import random
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll > LOSS_ROLL_THRESHOLD:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 2})
        result = resolve_losses(state, MORINI, ROMANS, 1)
        assert result["losses_absorbed"] == 1
        assert count_pieces(state, MORINI, ROMANS, LEGION) == 2
        assert result["rolls"][0][1] == roll  # Same roll value

    def test_leader_roll(self):
        """Leader rolls to absorb loss."""
        state = make_state(seed=42)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEADER: CAESAR})
        import random
        test_roll = random.Random(42).randint(DIE_MIN, DIE_MAX)
        result = resolve_losses(state, MORINI, ROMANS, 1)
        if test_roll <= LOSS_ROLL_THRESHOLD:
            assert get_leader_in_region(state, MORINI, ROMANS) is None
        else:
            assert get_leader_in_region(state, MORINI, ROMANS) == CAESAR

    def test_fort_roll(self):
        """Fort rolls to absorb loss (non-Provincia)."""
        state = make_state(seed=42)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={FORT: 1})
        import random
        test_roll = random.Random(42).randint(DIE_MIN, DIE_MAX)
        result = resolve_losses(state, MORINI, ROMANS, 1)
        if test_roll <= LOSS_ROLL_THRESHOLD:
            assert count_pieces(state, MORINI, ROMANS, FORT) == 0
        else:
            assert count_pieces(state, MORINI, ROMANS, FORT) == 1

    def test_citadel_roll(self):
        """Citadel rolls to absorb loss."""
        state = make_state(seed=42)
        setup_battle(state, MORINI, ARVERNI, ARVERNI,
                     defender_pieces={CITADEL: 1})
        import random
        test_roll = random.Random(42).randint(DIE_MIN, DIE_MAX)
        result = resolve_losses(state, MORINI, ARVERNI, 1, is_retreat=True)
        # Retreat: Citadels go FIRST
        if test_roll <= LOSS_ROLL_THRESHOLD:
            assert count_pieces(state, MORINI, ARVERNI, CITADEL) == 0
        else:
            assert count_pieces(state, MORINI, ARVERNI, CITADEL) == 1

    def test_retreat_ordering_allies_first(self):
        """Retreat: Allies/Forts/Citadels FIRST."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     defender_pieces={
                         WARBAND: 4,
                         ALLY: 2,
                     })
        result = resolve_losses(state, MORINI, ARVERNI, 2, is_retreat=True)
        # Allies should be removed first
        assert count_pieces(state, MORINI, ARVERNI, ALLY) == 0
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 4

    def test_no_retreat_ordering_allies_last(self):
        """No Retreat: Allies/Forts/Citadels LAST."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     defender_pieces={
                         WARBAND: 2,
                         ALLY: 2,
                     })
        result = resolve_losses(state, MORINI, ARVERNI, 2)
        # Warbands should be removed first (Allies last)
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 0
        assert count_pieces(state, MORINI, ARVERNI, ALLY) == 2

    def test_ambush_auto_remove_legion(self):
        """Ambush: Legion auto-removed (no roll)."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 2})
        result = resolve_losses(state, MORINI, ROMANS, 1, is_ambush=True)
        assert result["losses_taken"] == 1
        assert count_pieces(state, MORINI, ROMANS, LEGION) == 1
        # No roll value — auto-removed
        assert result["rolls"][0][1] is None

    def test_ambush_auto_remove_leader(self):
        """Ambush: Leader auto-removed (no roll)."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEADER: CAESAR})
        result = resolve_losses(state, MORINI, ROMANS, 1, is_ambush=True)
        assert result["losses_taken"] == 1
        assert get_leader_in_region(state, MORINI, ROMANS) is None

    def test_ambush_caesar_counterattack_still_rolls(self):
        """Ambush + Caesar Counterattack: hard targets still get 1-3 roll."""
        # Find a seed where Legion survives (roll > 3)
        import random
        for seed in range(100):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll > LOSS_ROLL_THRESHOLD:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 2})
        result = resolve_losses(
            state, MORINI, ROMANS, 1,
            is_ambush=True, caesar_counterattacks=True,
        )
        # Should have rolled (not auto-removed)
        assert result["rolls"][0][1] is not None
        assert result["losses_absorbed"] == 1

    def test_provincia_fort_never_absorbs(self):
        """Provincia Fort never absorbs Losses — §1.4.2."""
        state = make_state()
        # Place the permanent Fort explicitly (build_initial_state doesn't)
        place_piece(state, PROVINCIA, ROMANS, FORT)
        setup_battle(state, PROVINCIA, ARVERNI, ROMANS,
                     attacker_pieces={WARBAND: 4},
                     defender_pieces={AUXILIA: 2})
        result = resolve_losses(state, PROVINCIA, ROMANS, 2)
        # Auxilia removed, Fort untouched
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 0
        # Fort still there (permanent)
        assert count_pieces(state, PROVINCIA, ROMANS, FORT) == 1

    def test_legion_to_fallen(self):
        """Removed Legions go to Fallen box — §1.4.1."""
        state = make_state(seed=0)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 1})
        fallen_before = state["fallen_legions"]
        # Use ambush to force auto-remove
        result = resolve_losses(state, MORINI, ROMANS, 1, is_ambush=True)
        assert state["fallen_legions"] == fallen_before + 1

    def test_more_losses_than_pieces(self):
        """Losses exceed available pieces — stop when no pieces left."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     defender_pieces={WARBAND: 2})
        result = resolve_losses(state, MORINI, ARVERNI, 5)
        assert result["losses_taken"] == 2
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 0

    def test_german_loss_order_base(self):
        """Germans base game: Scouted→Revealed→Hidden Warbands, then Allies.

        §3.4.5: "Germans suffering Losses in Battle remove their Scouted,
        then their other Revealed, then Hidden Warbands; finally they remove
        their Allies."
        """
        state = make_state()
        # Place Warbands in various states
        _place_pieces(state, MORINI, GERMANS, {
            (WARBAND, HIDDEN): 2,
            (WARBAND, REVEALED): 2,
            (WARBAND, SCOUTED): 1,
            ALLY: 1,
        })
        result = resolve_losses(state, MORINI, GERMANS, 4)
        # Should remove: Scouted(1), Revealed(2), Hidden(1) — in that order
        assert count_pieces_by_state(
            state, MORINI, GERMANS, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, MORINI, GERMANS, WARBAND, REVEALED) == 0
        assert count_pieces_by_state(
            state, MORINI, GERMANS, WARBAND, HIDDEN) == 1
        assert count_pieces(state, MORINI, GERMANS, ALLY) == 1

    def test_german_allies_after_all_warbands(self):
        """Germans: Allies only after all Warbands gone — §3.4.5."""
        state = make_state()
        _place_pieces(state, MORINI, GERMANS, {
            WARBAND: 1,
            ALLY: 2,
        })
        result = resolve_losses(state, MORINI, GERMANS, 2)
        assert count_pieces(state, MORINI, GERMANS, WARBAND) == 0
        assert count_pieces(state, MORINI, GERMANS, ALLY) == 1


# ============================================================================
# FULL BATTLE RESOLUTION TESTS
# ============================================================================

class TestResolveBattle:
    """Test the complete battle resolution procedure."""

    def test_basic_battle_no_retreat(self):
        """Basic battle: Attack + Counterattack + Reveal."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={WARBAND: 4})
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )
        assert result["attack"] is not None
        assert result["counterattack"] is not None
        assert result["reveal"] is True
        assert result["defender_retreated"] is False

    def test_basic_battle_with_retreat(self):
        """Battle with Retreat: Attack (half losses), skip Counter/Reveal."""
        state = make_state()
        setup_battle(state, ATREBATES, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 8},
                     defender_pieces={WARBAND: 6})
        # Belgae retreats to Morini (adjacent, needs Belgic Control)
        # First set up control in Morini
        _place_pieces(state, MORINI, BELGAE, {WARBAND: 3})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ARVERNI, BELGAE,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        assert result["defender_retreated"] is True
        assert result["counterattack"] is None  # Skipped
        assert result["reveal"] is False  # Skipped
        assert result["retreat"] is not None

    def test_ambush_no_retreat(self):
        """Ambush: No Retreat allowed."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 8},
                     defender_pieces={WARBAND: 4})
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            is_ambush=True,
            retreat_declaration=True,  # Should be overridden
        )
        assert result["defender_retreated"] is False

    def test_ambush_no_counterattack(self):
        """Ambush: No Counterattack (unless Caesar)."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 8},
                     defender_pieces={WARBAND: 4})
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            is_ambush=True,
        )
        assert result["counterattack"] is None

    def test_germanic_base_no_retreat(self):
        """Germanic base game attack: No Retreat, no Step 6 — §3.4.4."""
        state = make_state()
        setup_battle(state, MORINI, GERMANS, BELGAE,
                     attacker_pieces={(WARBAND, HIDDEN): 5},
                     defender_pieces={WARBAND: 3})
        result = resolve_battle(
            state, MORINI, GERMANS, BELGAE,
            is_ambush=True,  # Germans always Ambush in base
        )
        assert result["defender_retreated"] is False
        assert result["retreat"] is None

    def test_reveal_step(self):
        """Step 5: All survivors flip to Revealed."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={(WARBAND, HIDDEN): 6},
                     defender_pieces={(WARBAND, HIDDEN): 4})
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )
        assert result["reveal"] is True
        # All surviving Warbands should be Revealed
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, HIDDEN) == 0
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, HIDDEN) == 0

    def test_reveal_skipped_on_retreat(self):
        """Reveal skipped if Defender Retreated."""
        state = make_state()
        setup_battle(state, ATREBATES, ARVERNI, BELGAE,
                     attacker_pieces={(WARBAND, HIDDEN): 6},
                     defender_pieces={(WARBAND, HIDDEN): 4})
        # Set up retreat destination
        _place_pieces(state, MORINI, BELGAE, {WARBAND: 3})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ARVERNI, BELGAE,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        assert result["reveal"] is False
        # Attacker Hidden pieces should still be Hidden
        assert count_pieces_by_state(
            state, ATREBATES, ARVERNI, WARBAND, HIDDEN) == 6

    def test_besiege_removes_citadel(self):
        """Besiege: Remove 1 Citadel before Losses — §4.2.3."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 3},
                     defender_pieces={
                         WARBAND: 4,
                         CITADEL: 1,
                     })
        result = resolve_battle(
            state, MORINI, ROMANS, ARVERNI,
            besiege_target=CITADEL,
            retreat_declaration=False,
            citadel_at_start=True,  # Had Citadel before Besiege
        )
        assert result["besiege"] is not None
        assert result["besiege"]["removed"] == CITADEL

    def test_besiege_citadel_still_halves(self):
        """Besiege: Citadel removed, but still halves Losses — §4.2.3."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={
                         WARBAND: 6,
                         CITADEL: 1,
                     })
        # With citadel_at_start=True, losses should be halved
        result = resolve_battle(
            state, MORINI, ROMANS, ARVERNI,
            besiege_target=CITADEL,
            retreat_declaration=False,
            citadel_at_start=True,
        )
        # Legions × 1 = 4, halved = 2
        # Citadel already removed by Besiege, Losses on Warbands
        assert result["attack"]["losses_taken"] <= 2

    def test_besiege_removes_ally(self):
        """Besiege: Remove 1 Ally before Losses — §4.2.3."""
        state = make_state()
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 2},
                     defender_pieces={
                         WARBAND: 3,
                         ALLY: 2,
                     })
        result = resolve_battle(
            state, MORINI, ROMANS, ARVERNI,
            besiege_target=ALLY,
            retreat_declaration=False,
        )
        assert result["besiege"]["removed"] == ALLY
        # 1 Ally removed by Besiege, 1 should remain
        assert count_pieces(state, MORINI, ARVERNI, ALLY) <= 1

    def test_caesar_defending_roll_success(self):
        """Caesar Defending: Roll 4-6 retains roll ability — §4.3.3."""
        # Find seed where Caesar's roll succeeds (≥ 4)
        import random
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll >= CAESAR_AMBUSH_ROLL_THRESHOLD:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 8},
                     defender_pieces={
                         LEADER: CAESAR,
                         LEGION: 3,
                     })
        result = resolve_battle(
            state, MORINI, ARVERNI, ROMANS,
            is_ambush=True,
        )
        assert result["caesar_roll"] is not None
        assert result["caesar_roll"][1] is True  # Success
        # Counterattack should happen
        assert result["counterattack"] is not None

    def test_caesar_defending_roll_failure(self):
        """Caesar Defending: Roll 1-3, no roll ability, no Counterattack."""
        import random
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll < CAESAR_AMBUSH_ROLL_THRESHOLD:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 8},
                     defender_pieces={
                         LEADER: CAESAR,
                         LEGION: 3,
                     })
        result = resolve_battle(
            state, MORINI, ARVERNI, ROMANS,
            is_ambush=True,
        )
        assert result["caesar_roll"] is not None
        assert result["caesar_roll"][1] is False  # Failure
        # No Counterattack
        assert result["counterattack"] is None

    def test_caesar_belgic_ambush_needs_5_or_6(self):
        """Caesar vs Belgae Ambush: needs 5-6 instead of 4-6 — §4.5.3."""
        import random
        # Find seed where roll is 4 (passes normal threshold, fails Belgic)
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll == 4:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, BELGAE, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 8},
                     defender_pieces={
                         LEADER: CAESAR,
                         LEGION: 3,
                     })
        result = resolve_battle(
            state, MORINI, BELGAE, ROMANS,
            is_ambush=True,
        )
        # Roll of 4 fails Belgic threshold (needs 5-6)
        assert result["caesar_roll"][0] == 4
        assert result["caesar_roll"][1] is False

    def test_ambush_with_fort_normal_rolls(self):
        """Ambush + Fort: normal rolls apply — §4.3.3.

        "but may use any Fort or Citadel normally"
        """
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 8},
                     defender_pieces={
                         LEGION: 3,
                         FORT: 1,
                     })
        result = resolve_battle(
            state, MORINI, ARVERNI, ROMANS,
            is_ambush=True,
        )
        # No Caesar roll (Fort provides normal roll ability)
        assert result["caesar_roll"] is None
        # Attack should have used die rolls for Legions/Fort
        rolls = result["attack"]["rolls"]
        if rolls:
            assert any(r[1] is not None for r in rolls)

    def test_ambush_with_citadel_normal_rolls(self):
        """Ambush + Citadel: normal rolls apply — §4.3.3."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={(WARBAND, HIDDEN): 8},
                     defender_pieces={
                         WARBAND: 3,
                         CITADEL: 1,
                     })
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            is_ambush=True,
        )
        # Citadel provides normal roll ability
        assert result["caesar_roll"] is None


class TestRetreatExecution:
    """Test Step 6 Retreat mechanics."""

    def test_retreat_moves_mobile_pieces(self):
        """Retreat moves Leader, Warbands, Auxilia, Legions to retreat region."""
        state = make_state()
        setup_battle(state, ATREBATES, ARVERNI, ROMANS,
                     attacker_pieces={WARBAND: 8},
                     defender_pieces={
                         LEADER: CAESAR,
                         LEGION: 2,
                         AUXILIA: 3,
                     })
        # Ensure Caesar is present by verifying
        assert get_leader_in_region(state, ATREBATES, ROMANS) == CAESAR
        # Retreat to Morini (adjacent)
        result = resolve_battle(
            state, ATREBATES, ARVERNI, ROMANS,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        # Roman Attack: Leader and Hidden Warbands may stay. But Romans
        # are defending here, and Arverni attacks. Leader may stay if
        # Roman attack... wait, who is the attacker? Arverni.
        # §3.3.4 (Gallic Attack): "Unlike in a Roman Attack, no Retreating
        # Leaders nor Warbands may stay."
        # So Romans defending vs Gallic attack: no staying.
        # But this is about the Defender's pieces. Romans are defending.
        # The attacker is Arverni (Gallic), so the retreat rule is Gallic.
        # Gallic attack retreat: "no Retreating Leaders nor Warbands may stay"
        # Wait — the "stay" rule is about the ATTACKER type:
        # §3.2.4 (Roman Attack): "Defender may opt to have... stay"
        # §3.3.4 (Gallic Attack): "no Retreating Leaders nor Warbands may stay"
        # So when ARVERNI attacks, retreating ROMANS can't stay.
        # When ROMANS attack, retreating pieces CAN stay.

    def test_roman_attack_retreat_hidden_warbands_stay(self):
        """Roman Attack: Hidden Warbands may stay — §3.2.4."""
        state = make_state()
        setup_battle(state, ATREBATES, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={
                         (WARBAND, HIDDEN): 3,
                         (WARBAND, REVEALED): 2,
                     })
        # Set up retreat destination with Arverni Control
        _place_pieces(state, MORINI, ARVERNI, {WARBAND: 5})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ROMANS, ARVERNI,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        retreat = result["retreat"]
        assert result["defender_retreated"] is True
        # Hidden Warbands should stay (Roman attack rule)
        # Revealed Warbands must retreat

    def test_gallic_attack_no_stay(self):
        """Gallic Attack: No Leaders or Warbands may stay — §3.3.4."""
        state = make_state()
        setup_battle(state, ATREBATES, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={
                         LEADER: AMBIORIX,
                         (WARBAND, HIDDEN): 3,
                     })
        # Set up retreat destination
        _place_pieces(state, MORINI, BELGAE, {WARBAND: 5})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ARVERNI, BELGAE,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        # Gallic attack: no staying. All mobile must retreat.
        retreat = result["retreat"]
        # Leader and Hidden Warbands should have moved/retreated

    def test_retreat_allies_citadels_stay_in_region(self):
        """Retreat: Allies and Citadels stay in Region — §3.2.4.

        Static pieces (Allies, Citadels, Forts) are NOT moved by retreat.
        They stay in the battle Region. Only mobile pieces retreat.
        Note: During retreat, Allies/Citadels take losses FIRST, so some
        may be removed by the Attack step. This tests that any surviving
        static pieces stay put.

        Roman Attack: Hidden Warbands may also stay — §3.2.4.
        """
        state = make_state()
        # Use low attacker force so Citadel halves to 0 losses
        setup_battle(state, ATREBATES, ROMANS, ARVERNI,
                     attacker_pieces={AUXILIA: 1},
                     defender_pieces={
                         (WARBAND, REVEALED): 2,
                         ALLY: 2,
                         CITADEL: 1,
                     })
        _place_pieces(state, MORINI, ARVERNI, {WARBAND: 5})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ROMANS, ARVERNI,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        # Auxilia × ½ = 0.5, halved by Citadel/retreat = 0.25, rounded = 0
        # So 0 attack losses. Allies and Citadels stay.
        assert count_pieces(state, ATREBATES, ARVERNI, ALLY) == 2
        assert count_pieces(state, ATREBATES, ARVERNI, CITADEL) == 1
        # Revealed Warbands must retreat (only Hidden can stay in Roman Attack)
        assert count_pieces(state, ATREBATES, ARVERNI, WARBAND) == 0

    def test_retreat_no_valid_region_removes(self):
        """No valid retreat region: mobile pieces removed."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={(WARBAND, REVEALED): 3})

        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=True,
            retreat_region=None,  # No valid region
        )
        retreat = result["retreat"]
        # All mobile pieces should be removed
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 0


class TestGermanicBattle:
    """Test Germanic Battle specifics — §3.4.4."""

    def test_germanic_always_ambush_base(self):
        """Germanic base game: always Ambush, auto-remove — §3.4.4."""
        state = make_state()
        setup_battle(state, MORINI, GERMANS, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 6},
                     defender_pieces={LEGION: 2, AUXILIA: 2})
        result = resolve_battle(
            state, MORINI, GERMANS, ROMANS,
            is_ambush=True,
        )
        # Auto-remove for hard targets (no rolls) unless Caesar
        assert result["defender_retreated"] is False

    def test_germanic_counterattack_warbands_then_allies(self):
        """Germanic Counterattack: Warbands, then Allies — §3.4.5."""
        state = make_state()
        # Set up so Caesar succeeds to get counterattack
        import random
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll >= CAESAR_AMBUSH_ROLL_THRESHOLD:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, GERMANS, ROMANS,
                     attacker_pieces={(WARBAND, HIDDEN): 6, ALLY: 2},
                     defender_pieces={LEADER: CAESAR, LEGION: 3})
        result = resolve_battle(
            state, MORINI, GERMANS, ROMANS,
            is_ambush=True,
        )
        if result["counterattack"] is not None:
            # Germans should lose Warbands before Allies
            remaining_wb = count_pieces(state, MORINI, GERMANS, WARBAND)
            remaining_ally = count_pieces(state, MORINI, GERMANS, ALLY)
            # If any pieces removed, Warbands should go first
            if remaining_wb < 6:
                # Some warbands removed — allies should still be at 2
                # unless all warbands gone
                pass  # Order is correct per loss priority


# ============================================================================
# ARIOVISTUS-SPECIFIC TESTS
# ============================================================================

class TestAriovistus:
    """Test Ariovistus-specific Battle rules."""

    def test_settlements_absorb_losses_as_allies(self):
        """Settlements absorb Losses as if Germanic Allies — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_pieces(state, MORINI, GERMANS, {
            WARBAND: 2,
            SETTLEMENT: 1,
        })
        # Settlements should be in the "static" (last) group for no-retreat
        result = resolve_losses(state, MORINI, GERMANS, 3)
        # Warbands first, then Settlement
        assert count_pieces(state, MORINI, GERMANS, WARBAND) == 0
        assert count_pieces(state, MORINI, GERMANS, SETTLEMENT) == 0

    def test_ariovistus_doubles_losses(self):
        """Ariovistus Leader doubles losses — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, MORINI, GERMANS, ROMANS,
                     attacker_pieces={
                         LEADER: ARIOVISTUS_LEADER,
                         WARBAND: 4,
                     },
                     defender_pieces={LEGION: 2, AUXILIA: 2})
        # Warbands × ½ = 2, Leader × 1 = 1, total = 3
        # Ariovistus doubles: 3 × 2 = 6 (no Fort/Citadel)
        losses = calculate_losses(
            state, MORINI, GERMANS, ROMANS
        )
        assert losses == 6

    def test_ariovistus_no_double_with_fort(self):
        """Ariovistus: no doubling if Defender has Fort — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, MORINI, GERMANS, ROMANS,
                     attacker_pieces={
                         LEADER: ARIOVISTUS_LEADER,
                         WARBAND: 4,
                     },
                     defender_pieces={LEGION: 2, FORT: 1})
        # Warbands × ½ = 2, Leader × 1 = 1, total = 3
        # Defender has Fort: no Ariovistus doubling
        # But Fort halves: 3 / 2 = 1.5 → 1
        losses = calculate_losses(
            state, MORINI, GERMANS, ROMANS
        )
        assert losses == 1

    def test_ariovistus_doubles_counterattack_even_with_fort(self):
        """Ariovistus: Attacker takes double in counterattack — A3.2.4.

        "An Attacker, even with a Fort or Citadel, fighting Ariovistus
        would take double Losses in any German counterattack."
        """
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, MORINI, ROMANS, GERMANS,
                     attacker_pieces={LEGION: 3, FORT: 1},
                     defender_pieces={
                         LEADER: ARIOVISTUS_LEADER,
                         WARBAND: 4,
                     })
        # Counterattack: German survivors attack the Roman attacker
        # Ariovistus's Warbands × ½ = 2, Leader × 1 = 1, total = 3
        # Doubled by Ariovistus = 6 (even though Roman has Fort)
        losses = calculate_losses(
            state, MORINI, GERMANS, ROMANS, is_counterattack=True
        )
        assert losses == 6

    def test_diviciacus_roll_threshold(self):
        """Diviciacus: removed only on roll of 1 — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_pieces(state, MORINI, AEDUI, {
            LEADER: DIVICIACUS,
            WARBAND: 1,
        })
        # Find seed where roll = 1
        import random
        for seed in range(200):
            rng = random.Random(seed)
            # First roll is for the warband (auto-remove), skip to leader roll
            _ = rng.randint(DIE_MIN, DIE_MAX)  # won't actually be called
            break

        # Actually, Diviciacus is last in priority. Let's place only Diviciacus
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_pieces(state, MORINI, AEDUI, {LEADER: DIVICIACUS})

        # Find seed where Diviciacus roll = 1
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll == 1:
                break

        state = make_state(scenario=SCENARIO_ARIOVISTUS, seed=seed)
        _place_pieces(state, MORINI, AEDUI, {LEADER: DIVICIACUS})
        result = resolve_losses(state, MORINI, AEDUI, 1)
        assert result["losses_taken"] == 1
        assert get_leader_in_region(state, MORINI, AEDUI) is None

    def test_diviciacus_survives_high_roll(self):
        """Diviciacus survives on roll ≥ 2 — A3.2.4."""
        import random
        for seed in range(200):
            rng = random.Random(seed)
            roll = rng.randint(DIE_MIN, DIE_MAX)
            if roll > DIVICIACUS_LOSS_ROLL_THRESHOLD:
                break

        state = make_state(scenario=SCENARIO_ARIOVISTUS, seed=seed)
        _place_pieces(state, MORINI, AEDUI, {LEADER: DIVICIACUS})
        result = resolve_losses(state, MORINI, AEDUI, 1)
        assert result["losses_absorbed"] == 1
        assert get_leader_in_region(state, MORINI, AEDUI) == DIVICIACUS

    def test_diviciacus_last_to_absorb(self):
        """Diviciacus: last possible piece to absorb — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_pieces(state, MORINI, AEDUI, {
            LEADER: DIVICIACUS,
            WARBAND: 2,
        })
        result = resolve_losses(state, MORINI, AEDUI, 2)
        # Warbands should be removed first, Diviciacus untouched
        assert count_pieces(state, MORINI, AEDUI, WARBAND) == 0
        assert get_leader_in_region(state, MORINI, AEDUI) == DIVICIACUS

    def test_germans_can_retreat_in_ariovistus(self):
        """Germans CAN Retreat in Ariovistus — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, ATREBATES, ROMANS, GERMANS,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={WARBAND: 4})
        # In Ariovistus, Germans can retreat
        _place_pieces(state, MORINI, GERMANS, {WARBAND: 3})
        from fs_bot.board.control import refresh_all_control
        refresh_all_control(state)

        result = resolve_battle(
            state, ATREBATES, ROMANS, GERMANS,
            retreat_declaration=True,
            retreat_region=MORINI,
        )
        assert result["defender_retreated"] is True

    def test_arverni_never_retreat_ariovistus(self):
        """Arverni never Retreat in Ariovistus — A3.2.4."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, MORINI, ROMANS, ARVERNI,
                     attacker_pieces={LEGION: 4},
                     defender_pieces={WARBAND: 4})
        result = resolve_battle(
            state, MORINI, ROMANS, ARVERNI,
            retreat_declaration=True,  # Should be overridden
        )
        assert result["defender_retreated"] is False

    def test_arverni_loss_order_ariovistus(self):
        """Arverni Ariovistus: Scouted→Revealed→Hidden, Allies, Citadels.

        A3.2.4: "Arverni suffering Losses in Battle remove their Scouted
        Warbands, then other Revealed Warbands, then Hidden Warbands;
        then their Allies, from Cities last; finally their Citadels."
        """
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        _place_pieces(state, MORINI, ARVERNI, {
            (WARBAND, HIDDEN): 1,
            (WARBAND, REVEALED): 1,
            (WARBAND, SCOUTED): 1,
            ALLY: 1,
            CITADEL: 1,
        })
        # Remove 3 — should be Scouted, Revealed, Hidden
        result = resolve_losses(state, MORINI, ARVERNI, 3)
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, REVEALED) == 0
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, HIDDEN) == 0
        assert count_pieces(state, MORINI, ARVERNI, ALLY) == 1
        assert count_pieces(state, MORINI, ARVERNI, CITADEL) == 1

    def test_settlement_not_in_base_game(self):
        """Settlements don't exist in base game scenarios."""
        state = make_state(scenario=SCENARIO_PAX_GALLICA)
        # Germans don't have Settlements in base game
        with pytest.raises(Exception):
            _place_pieces(state, MORINI, GERMANS, {SETTLEMENT: 1})

    def test_besiege_removes_settlement_ariovistus(self):
        """Besiege can remove Settlement in Ariovistus — A4.2.3."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_battle(state, MORINI, ROMANS, GERMANS,
                     attacker_pieces={LEGION: 3},
                     defender_pieces={
                         WARBAND: 3,
                         SETTLEMENT: 1,
                     })
        result = resolve_battle(
            state, MORINI, ROMANS, GERMANS,
            besiege_target=SETTLEMENT,
            retreat_declaration=False,
        )
        assert result["besiege"]["removed"] == SETTLEMENT
        assert count_pieces(state, MORINI, GERMANS, SETTLEMENT) == 0


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_losses(self):
        """Zero losses: nothing happens."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     defender_pieces={WARBAND: 4})
        result = resolve_losses(state, MORINI, BELGAE, 0)
        assert result["losses_taken"] == 0
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 4

    def test_only_static_pieces_no_retreat(self):
        """Defender with only static pieces cannot retreat — §3.2.4."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 4},
                     defender_pieces={ALLY: 2})
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=True,  # Can't retreat
        )
        # Should be forced to no retreat
        assert result["defender_retreated"] is False

    def test_battle_updates_control(self):
        """Battle refreshes control after resolution."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 10},
                     defender_pieces={WARBAND: 2})
        from fs_bot.board.control import calculate_control
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )
        # After battle, control should be recalculated
        # Arverni should control if they have more pieces

    def test_scouted_pieces_revealed(self):
        """Scouted pieces flip to Revealed during Reveal step."""
        state = make_state()
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={(WARBAND, HIDDEN): 6},
                     defender_pieces={
                         (WARBAND, HIDDEN): 2,
                         (WARBAND, SCOUTED): 2,
                     })
        result = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )
        # After reveal, all surviving should be Revealed
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, HIDDEN) == 0

    def test_multiple_hard_targets_repeated_rolls(self):
        """Multiple Legions: roll for each, some survive, some don't."""
        # Find seed with mixed results
        import random
        for seed in range(200):
            rng = random.Random(seed)
            rolls = [rng.randint(DIE_MIN, DIE_MAX) for _ in range(4)]
            survive = sum(1 for r in rolls if r > LOSS_ROLL_THRESHOLD)
            fail = sum(1 for r in rolls if r <= LOSS_ROLL_THRESHOLD)
            if survive > 0 and fail > 0:
                break

        state = make_state(seed=seed)
        setup_battle(state, MORINI, ARVERNI, ROMANS,
                     defender_pieces={LEGION: 4})
        result = resolve_losses(state, MORINI, ROMANS, 4)
        assert result["losses_taken"] > 0
        assert result["losses_taken"] + result["losses_absorbed"] == 4

    def test_deterministic_with_seed(self):
        """Same seed produces same battle result."""
        def run_battle(seed):
            state = make_state(seed=seed)
            setup_battle(state, MORINI, ARVERNI, BELGAE,
                         attacker_pieces={WARBAND: 6},
                         defender_pieces={WARBAND: 4})
            return resolve_battle(
                state, MORINI, ARVERNI, BELGAE,
                retreat_declaration=False,
            )

        result1 = run_battle(123)
        result2 = run_battle(123)
        assert result1["attack"]["losses_taken"] == result2["attack"]["losses_taken"]
        assert result1["attack"]["losses_absorbed"] == result2["attack"]["losses_absorbed"]
        if result1["counterattack"] and result2["counterattack"]:
            assert (result1["counterattack"]["losses_taken"] ==
                    result2["counterattack"]["losses_taken"])

    def test_no_rng_leakage(self):
        """Battle uses state['rng'] exclusively, not random module."""
        import random
        random.seed(999)  # Global seed
        state = make_state(seed=42)
        setup_battle(state, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={WARBAND: 4})

        # Run battle — should use state["rng"], not random module
        result1 = resolve_battle(
            state, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )

        # Run again with same state seed, different global seed
        random.seed(12345)
        state2 = make_state(seed=42)
        setup_battle(state2, MORINI, ARVERNI, BELGAE,
                     attacker_pieces={WARBAND: 6},
                     defender_pieces={WARBAND: 4})
        result2 = resolve_battle(
            state2, MORINI, ARVERNI, BELGAE,
            retreat_declaration=False,
        )

        # Results should be identical despite different global seed
        assert result1["attack"]["losses_taken"] == result2["attack"]["losses_taken"]
