"""Germans Phase Battle with Ambush — §6.2.4.

Implements the final step of the base-game Germans Phase:
Battle with Ambush in each region where the Germans currently are able to
do so (only wherever Hidden Germanic Warbands are with another faction
with fewer Hidden pieces) and would cause an enemy Loss.

Battle player before Non-player factions.
Choose the order of Battles and among equal candidates randomly.

Reference:
  §6.2.4  Germanic Battle with Ambush
  §4.1    Ambush (general)
  §4.3.3  Ambush details
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    WARBAND, AUXILIA,
    # Piece states
    HIDDEN,
    # Scenarios
    BASE_SCENARIOS,
)
from fs_bot.board.pieces import count_pieces, count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.battle.losses import calculate_losses
from fs_bot.battle.resolve import resolve_battle
from fs_bot.commands.common import CommandError


def _count_hidden_pieces(state, region, faction):
    """Count Hidden pieces for a faction in a region.

    Hidden pieces include Hidden Warbands + Hidden Auxilia.

    Returns:
        Integer count of Hidden pieces.
    """
    total = 0
    total += count_pieces_by_state(state, region, faction, WARBAND, HIDDEN)
    total += count_pieces_by_state(state, region, faction, AUXILIA, HIDDEN)
    return total


def _would_cause_loss(state, region, defending_faction):
    """Check if a German Ambush in this region would cause an enemy Loss.

    Per §6.2.4: "would cause an enemy Loss" — the calculated Losses > 0.
    Since it's an Ambush, there's no counterattack; only the attack step.

    Uses calculate_losses to simulate the attack.
    """
    # Calculate losses for an Ambush attack (Germans attacking)
    losses = calculate_losses(
        state, region,
        attacking_faction=GERMANS,
        defending_faction=defending_faction,
        is_retreat=False,
        is_counterattack=False,
    )
    return losses > 0


def _get_battle_candidates(state, region):
    """Get valid Battle targets in a region for Germans Phase Battle.

    Per §6.2.4: Only where Hidden Germanic Warbands are with another
    faction with fewer Hidden pieces.

    Returns:
        List of (faction, is_player) tuples that are valid targets,
        where is_player indicates player (True) vs non-player (False).
    """
    german_hidden = _count_hidden_pieces(state, region, GERMANS)
    if german_hidden == 0:
        return []

    non_players = state.get("non_player_factions", set())
    candidates = []

    for faction in FACTIONS:
        if faction == GERMANS:
            continue
        # Must have pieces in the region
        if count_pieces(state, region, faction) == 0:
            continue
        # German Hidden must exceed enemy Hidden
        enemy_hidden = _count_hidden_pieces(state, region, faction)
        if german_hidden <= enemy_hidden:
            continue
        # Must "would cause an enemy Loss"
        if not _would_cause_loss(state, region, faction):
            continue

        is_player = faction not in non_players
        candidates.append((faction, is_player))

    return candidates


def germans_phase_battle(state):
    """Execute Germans Phase Battle with Ambush — §6.2.4.

    Battle with Ambush in each region where the Germans currently are able
    to do so and would cause an enemy Loss. Battle player before Non-player
    factions. Choose the order of Battles and among equal candidates randomly.

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with results:
            "battles": list of battle result dicts
            "regions": list of regions where battles occurred

    Raises:
        CommandError: If called in Ariovistus scenario.
    """
    scenario = state["scenario"]
    if scenario not in BASE_SCENARIOS:
        raise CommandError(
            "Germans Phase Battle is base game only (§6.2.4)"
        )

    result = {
        "battles": [],
        "regions": [],
    }
    rng = state["rng"]

    # Find all regions with valid battle candidates
    battle_regions = []
    for region in state["spaces"]:
        candidates = _get_battle_candidates(state, region)
        if candidates:
            battle_regions.append(region)

    # Choose order of Battles randomly — §6.2.4
    rng.shuffle(battle_regions)

    for region in battle_regions:
        # Re-evaluate candidates (state may have changed from prior battles)
        candidates = _get_battle_candidates(state, region)
        if not candidates:
            continue

        # Battle player before Non-player — §6.2.4
        player_candidates = [
            (f, ip) for f, ip in candidates if ip
        ]
        np_candidates = [
            (f, ip) for f, ip in candidates if not ip
        ]

        # Process players first, then non-players
        for candidate_group in [player_candidates, np_candidates]:
            if not candidate_group:
                continue
            # Choose randomly among equal candidates — §6.2.4
            factions_in_group = [f for f, _ in candidate_group]
            rng.shuffle(factions_in_group)

            for defending_faction in factions_in_group:
                # Re-verify this battle is still valid
                german_hidden = _count_hidden_pieces(state, region, GERMANS)
                if german_hidden == 0:
                    break
                enemy_hidden = _count_hidden_pieces(
                    state, region, defending_faction
                )
                if german_hidden <= enemy_hidden:
                    continue
                if count_pieces(state, region, defending_faction) == 0:
                    continue
                if not _would_cause_loss(state, region, defending_faction):
                    continue

                # Execute battle with Ambush
                battle_result = resolve_battle(
                    state, region,
                    attacking_faction=GERMANS,
                    defending_faction=defending_faction,
                    is_ambush=True,
                )
                result["battles"].append({
                    "region": region,
                    "defender": defending_faction,
                    "result": battle_result,
                })
                if region not in result["regions"]:
                    result["regions"].append(region)

    refresh_all_control(state)
    return result
