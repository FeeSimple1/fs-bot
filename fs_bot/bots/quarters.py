"""Non-player relocation priorities for §8.5.6, §8.6.7, §8.7.7 and A8.7.6."""

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, find_leader
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.common import _is_devastated
from fs_bot.engine.quarters import (
    _bot_host_agrees, _controller, _host_agrees, eligible_quarters_host,
    preview_relocations, quarters_factions,
)
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state


def _host_options(state, faction, regions):
    """Identify legal destinations before asking any human hosts."""
    options = {}
    for region in regions:
        host = _controller(state, region)
        if _is_devastated(state, region) or not eligible_quarters_host(state, faction, host):
            continue
        if (host != faction and host in state.get('non_player_factions', ())
                and not _bot_host_agrees(state, faction, host, 'quarters')):
            continue
        options[region] = host
    return options


def _evacuations(state, faction, regions, adjacent, hosts):
    """Leave unprotected Devastated Regions for a legal adjacent refuge."""
    protection = (rc.ALLY, rc.SETTLEMENT if faction == rc.GERMANS else rc.CITADEL)
    moves = []
    for origin in regions:
        if (not _is_devastated(state, origin)
                or any(count_pieces(state, origin, faction, piece) for piece in protection)):
            continue
        warbands = count_pieces(state, origin, faction, rc.WARBAND)
        leader = count_pieces(state, origin, faction, rc.LEADER)
        if not (warbands or leader):
            continue
        choices = [region for region in adjacent[origin] if region in hosts
                   and (faction == rc.AEDUI or hosts[region] == faction)]
        while choices:
            destination = random_select(state, choices)
            if _host_agrees(state, faction, hosts[destination], destination, 'quarters'):
                if leader:
                    moves.append((rc.LEADER, origin, destination, 1))
                if warbands:
                    moves.append((rc.WARBAND, origin, destination, warbands))
                break
            choices.remove(destination)
    return moves


def _consolidation(state, faction, regions, adjacent, hosts, evacuations):
    """Join the largest reachable Warband stack with the Leader and/or one group."""
    board = preview_relocations(state, faction, evacuations) if evacuations else state
    leader = find_leader(board, faction)
    if leader not in adjacent:
        return []

    # The original cohorts each have one adjacent move. Use the projected
    # board for ranking and Control, but never send an evacuated piece twice.
    original = {r: count_pieces(state, r, faction, rc.WARBAND) for r in regions}
    for piece, origin, _, count in evacuations:
        if piece == rc.WARBAND:
            original[origin] -= count
    warbands = {r: count_pieces(board, r, faction, rc.WARBAND) for r in regions}
    forces = {r: count_pieces(board, r, faction) for r in regions}
    spare = {r: forces[r] for r in regions}
    for region in regions:
        if is_controlled_by(board, region, faction):
            opponents = count_pieces(board, region) - forces[region]
            spare[region] -= opponents + 1

    destinations = [leader]
    if leader == find_leader(state, faction) and spare[leader] >= 1:
        destinations.extend(r for r in adjacent[leader] if r in hosts)

    candidates = []
    for destination in destinations:
        leader_moves = destination != leader
        leader_plan = [(rc.LEADER, leader, destination, 1)] if leader_moves else []
        groups = [(None, 0)]
        if destination in hosts:
            for origin in regions:
                if destination not in adjacent[origin]:
                    continue
                available = min(original[origin], warbands[origin] - 1,
                                spare[origin] - int(leader_moves and origin == leader))
                if available > 0:
                    groups.append((origin, available))
        for origin, number in groups:
            # Count the actual ending presence within one Region, including
            # the Leader's destination and any origin whose Leader departs.
            nearby = sum(forces[r] - int(leader_moves and r == leader)
                         - (number if r == origin else 0) > 0
                         for r in adjacent[destination]) + 1
            size = warbands[destination] + number
            preferred = (faction == rc.BELGAE and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                         and size > warbands[leader]
                         and destination in (rc.MORINI, rc.NERVII, rc.TREVERI))
            # A8.5.6 replaces proximity with the preferred Regions when
            # joining more Warbands there. Largest group remains primary.
            rank = (size, preferred, 0 if preferred else nearby)
            group_plan = [(rc.WARBAND, origin, destination, number)] if number else []
            candidates.append((rank, destination, leader_plan + group_plan))

    # Rank legal Regions first, then any tied origin choices within the
    # selected Region. Reconsider if its controller refuses Quarters.
    while candidates:
        best = max(rank for rank, _, _ in candidates)
        tied = sorted({region for rank, region, _ in candidates if rank == best})
        region = random_select(state, tied)
        plans = [moves for rank, dest, moves in candidates if dest == region and rank == best]
        if not any(plans) or _host_agrees(state, faction, hosts[region], region, 'quarters'):
            return random_select(state, plans)
        candidates = [row for row in candidates if row[1] != region or not row[2]]
    return []


def plan_relocations(state, faction):
    """Return one faction's executable adjacent relocation plan."""
    if faction == rc.ROMANS or faction not in quarters_factions(state):
        return []
    regions = sorted(get_playable_regions_for_state(state, faction))
    adjacent = {r: sorted(get_adjacent_for_state(state, r, faction)) for r in regions}
    hosts = _host_options(state, faction, regions)
    moves = _evacuations(state, faction, regions, adjacent, hosts)
    if faction != rc.AEDUI:
        moves.extend(_consolidation(state, faction, regions, adjacent, hosts, moves))
    return moves
