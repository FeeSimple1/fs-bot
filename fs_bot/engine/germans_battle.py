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
    ARVERNI, GERMANS, FACTIONS,
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
from fs_bot.engine import action_windows, slingers_choice
from fs_bot.engine.diviciacus import defense_scope


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


def _get_battle_candidates(state, region, *, force_ambush=False):
    """Get valid Battle targets in a region for Germans Phase Battle.

    Per §6.2.4: Only where Hidden Germanic Warbands are with another
    faction with fewer Hidden pieces.

    Returns:
        List of (faction, is_player) tuples that are valid targets,
        where is_player indicates player (True) vs non-player (False).
    """
    german_hidden = _count_hidden_pieces(state, region, GERMANS)
    if german_hidden == 0 and not force_ambush:
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
        if german_hidden <= enemy_hidden and not force_ambush:
            continue
        # Must "would cause an enemy Loss"
        if not _would_cause_loss(state, region, faction):
            continue

        is_player = faction not in non_players
        candidates.append((faction, is_player))

    return candidates


def _choose_defender(state, region, *, force_ambush):
    candidates = _get_battle_candidates(state, region, force_ambush=force_ambush)
    scheduled = {faction for faction, _ in candidates}
    for player in (True, False):
        targets = [faction for faction, is_player in candidates if is_player == player]
        state['rng'].shuffle(targets)
        for index, defender in enumerate(targets):
            action_windows.window(state, 'germans_battle_target', region=region, defender=defender)
            live = {faction for faction, _ in
                    _get_battle_candidates(state, region, force_ambush=force_ambush)}
            if defender in live:
                return defender
            # If this selection became illegal, a newly entered Arverni
            # Leader can provide a fallback target at the same window.
            if ARVERNI in live and ARVERNI not in scheduled:
                targets.insert(index + 1, ARVERNI)
                scheduled.add(ARVERNI)
    return None


def germans_phase_battle(state, *, force_ambush=False):
    """Run the game procedure with optional human timing windows."""
    with action_windows.scope(state, phase='germans_battle'):
        return _germans_phase_battle(state, force_ambush=force_ambush)


def _germans_phase_battle(state, *, force_ambush=False):
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

    action_windows.window(state, 'germans_battle_setup')
    # Find all regions with valid battle candidates
    battle_regions = []
    for region in state["spaces"]:
        candidates = _get_battle_candidates(state, region, force_ambush=force_ambush)
        if candidates:
            battle_regions.append(region)

    # Choose order of Battles randomly — §6.2.4
    rng.shuffle(battle_regions)
    scheduled_regions = set(battle_regions)
    slingers_used = False

    def new_regions():
        # A newly entering Leader can supply an enemy where none existed
        # when the original order was chosen. Completed Regions stay done.
        return [r for r in state['spaces'] if r not in scheduled_regions
                and _get_battle_candidates(state, r, force_ambush=force_ambush)]

    def include_new_regions():
        added = new_regions()
        if added:
            rng.shuffle(added)
            battle_regions.extend(added)
            scheduled_regions.update(added)

    for index, region in enumerate(battle_regions):
        action_windows.window(state, 'germans_battle_region', region=region)
        include_new_regions()
        defender = _choose_defender(state, region, force_ambush=force_ambush)
        if defender is None:
            include_new_regions()
            continue

        # §3.4.4 selects a single defender in each applicable Region.
        with defense_scope(state, region, GERMANS, defender):
            if not slingers_used and slingers_choice.is_active_for(state, GERMANS):
                potential = battle_regions[index + 1:] + new_regions()
                if slingers_choice.choose_for_queue(state, region, GERMANS, defender, potential):
                    slingers_choice.fire(state, region, GERMANS)
                    slingers_used = True
            battle_result = resolve_battle(state, region, GERMANS, defender, is_ambush=True)
        result['battles'].append({'region': region, 'defender': defender, 'result': battle_result})
        result['regions'].append(region)
        include_new_regions()

    refresh_all_control(state)
    return result
