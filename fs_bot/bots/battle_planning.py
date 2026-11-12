"""Command-wide Ambush planning for Belgae, Arverni, and Germans."""

from fs_bot.battle import retreat
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.bots.bot_common import (
    command_region_candidates, command_sa_allowed, np_agrees_to_retreat,
    predict_battle, random_select,
)
from fs_bot.commands.common import battle_cost
from fs_bot.commands.sa_ambush import validate_ambush_region
from fs_bot.map.map_data import get_adjacent_for_state
from fs_bot.rules_consts import ARIOVISTUS_SCENARIOS, ARVERNI, FACTIONS, GERMANS, LEGION


def _has_possible_retreat_destination(state, region, defender):
    expansion = state['scenario'] in ARIOVISTUS_SCENARIOS
    game_run = ARVERNI if expansion else GERMANS
    non_players = state.get('non_player_factions', ())
    for destination in get_adjacent_for_state(state, region, defender):
        if is_controlled_by(state, destination, defender):
            return True
        for host in FACTIONS:
            if host in (defender, game_run) or not is_controlled_by(state, destination, host):
                continue
            # A player could agree when asked at Battle resolution.
            if host not in non_players or np_agrees_to_retreat(host, defender, state):
                return True
    return False


def _ambush_helps_first_battle(state, region, faction, defender):
    # §§8.5.1, 8.7.1, A8.7.1 expressly count a defending Legion or Leader.
    if count_pieces(state, region, defender, LEGION) or get_leader_in_region(
            state, region, defender) is not None:
        return True
    standing = predict_battle(state, region, faction, defender)
    if standing is None:
        return False
    if standing['taken']:
        return True
    if (not standing['defender_removed']
            or not retreat.can_declare(state, region, faction, defender, False)
            or not _has_possible_retreat_destination(state, region, defender)):
        return False
    withdrawn = predict_battle(state, region, faction, defender, is_retreat=True)
    return withdrawn is not None and withdrawn['defender_removed'] < standing['defender_removed']


def _can_ambush(state, region, faction, defender, *, first):
    return (command_sa_allowed(state)
            and validate_ambush_region(state, region, faction, defender)[0]
            and (not first or _ambush_helps_first_battle(state, region, faction, defender)))


def ambush_regions_for_plan(state, faction, battle_plan):
    """Ambush every eligible Battle if the first Battle qualifies."""
    battles = [entry for entry in battle_plan
               if command_region_candidates(state, [entry['region']])]
    if not battles:
        return []
    first, *later = battles
    if not _can_ambush(state, first['region'], faction, first['target'], first=True):
        return []
    return [first['region']] + [
        entry['region'] for entry in later
        if _can_ambush(state, entry['region'], faction, entry['target'], first=False)]


def select_battle_plan(state, faction, priorities, qualifies, *,
                       required=None, random_ties=False):
    """Select affordable Battles in priority order with one SA for the Command.

    Each priority supplies a Region, ordered enemy candidates, and whether it
    meets the Battle trigger. A threatened Leader's Region can be required.
    """
    budget = state['resources'].get(faction, 0)
    plan = []
    selected = set()
    ambushing = False

    def eligible_targets(region, enemies, *, first):
        for enemy in enemies:
            if not count_pieces(state, region, enemy):
                continue
            is_ambush = (first or ambushing) and _can_ambush(
                state, region, faction, enemy, first=first)
            if qualifies(region, enemy, is_ambush=is_ambush):
                yield enemy, is_ambush

    if required:
        leader_region, enemies = required
        if (battle_cost(state, leader_region, faction) > budget
                or next(eligible_targets(leader_region, enemies, first=True), None) is None):
            return []

    for region, enemies, is_trigger in priorities:
        if region in selected:
            continue
        cost = battle_cost(state, region, faction)
        if cost > budget:
            continue
        candidates = eligible_targets(region, enemies, first=not plan)
        if random_ties:
            targets = list(candidates)
            choice = random_select(state, targets) if targets else None
        else:
            choice = next(candidates, None)
        if choice is None:
            continue
        target, is_ambush = choice
        if not plan:
            ambushing = is_ambush
        plan.append(dict(region=region, target=target, is_trigger=is_trigger))
        selected.add(region)
        budget -= cost

    if required and leader_region not in selected:
        return []
    return plan
