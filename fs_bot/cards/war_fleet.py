"""Card 62: coastal relocation and faction-specific Non-player continuation.

The printed movement is an Event relocation, not a March. Preserve visibility
and physical ownership, and apply each faction's separate Event instruction.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
    get_leader_in_region, move_piece)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def coastal_regions(state, faction=None):
    return sorted(set(get_playable_regions_for_state(state, faction)) & {
        rc.ARVERNI_REGION, rc.PICTONES, rc.BRITANNIA,
        *get_adjacent(rc.BRITANNIA, state['scenario'])})


def _group(state, faction, origin):
    group = {pt: count_pieces(state, origin, faction, pt)
             for pt in (rc.WARBAND, rc.AUXILIA, rc.LEGION)}
    group[rc.LEADER] = bool(get_leader_in_region(state, origin, faction))
    return group


def _entries(state, faction, origin, destination, group):
    """Freeze original counters by visibility, so arrivals never move twice."""
    result = []
    if origin == destination:
        return result
    for piece in (rc.LEADER, rc.LEGION, rc.AUXILIA, rc.WARBAND):
        remaining = int(group.get(piece, 0))
        if piece in (rc.AUXILIA, rc.WARBAND):
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                take = min(remaining, count_pieces_by_state(
                    state, origin, faction, piece, visibility))
                if take:
                    result.append({'from_region': origin, 'to_region': destination,
                                   'piece_type': piece, 'piece_state': visibility, 'count': take})
                    remaining -= take
            if remaining:
                raise ValueError(f'War Fleet requests unavailable {faction} {piece} in {origin}')
        elif remaining:
            result.append({'from_region': origin, 'to_region': destination,
                           'piece_type': piece, 'count': remaining})
    return result


def _apply(state, faction, moves):
    for move in moves:
        move_piece(state, move['from_region'], move['to_region'], faction,
                   move['piece_type'], count=move.get('count', 1),
                   piece_state=move.get('piece_state'))
    refresh_all_control(state)


def _frost_ok(before, after):
    from fs_bot.cards.migration import _frost_ok as permitted
    return permitted(before, after)


def _battle_frost_ok(before, after_moves, region, enemy):
    from fs_bot.engine.game_engine import is_frost
    if not before.get('frost') and not is_frost(before):
        return True
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    return all(_frost_ok(before, outcome) for outcome in _battle_frost_outcomes(
        after_moves, region, enemy, attacker=rc.ARVERNI, command=True))


def _arverni(state, regions):
    # Printed instruction: player Romans, then Aedui, then Belgae; move
    # as many Warbands and the Leader as possible to take Control, then
    # Battle THAT player there. A different NP target is not a fallback.
    for enemy in (rc.ROMANS, rc.AEDUI, rc.BELGAE):
        if enemy in state.get('non_player_factions', set()):
            continue
        candidates = []
        for destination in regions:
            if not count_pieces(state, destination, enemy):
                continue
            moves = []
            for origin in regions:
                group = _group(state, rc.ARVERNI, origin)
                moves.extend(_entries(state, rc.ARVERNI, origin, destination, group))
            sim = _copy(state)
            _apply(sim, rc.ARVERNI, moves)
            if (is_controlled_by(sim, destination, rc.ARVERNI)
                    and (count_pieces(sim, destination, rc.ARVERNI, rc.WARBAND)
                         or get_leader_in_region(sim, destination, rc.ARVERNI))
                    and _frost_ok(state, sim)
                    and _battle_frost_ok(state, sim, destination, enemy)):
                candidates.append((destination, moves))
        if candidates:
            destination, moves = random_select(state, candidates)
            return {'moves': moves, '_war_fleet_battle': {
                'region': destination, 'target': enemy}}
    return {'moves': []}


def _aedui(state, regions):
    candidates = []
    for origin in regions:
        group = _group(state, rc.AEDUI, origin)
        size = sum(group.values())
        if not size:
            continue
        destinations = []
        for destination in regions:
            if destination == origin:
                continue
            moves = _entries(state, rc.AEDUI, origin, destination, group)
            sim = _copy(state)
            _apply(sim, rc.AEDUI, moves)
            if _frost_ok(state, sim):
                destinations.append((destination, moves))
        if destinations:
            candidates.append((size, origin, destinations))
    if not candidates:
        return {'moves': []}
    largest = max(candidate[0] for candidate in candidates)
    _, _, destinations = random_select(state, [candidate for candidate in candidates
                                               if candidate[0] == largest])
    _, moves = random_select(state, destinations)
    return {'moves': moves}


def _belgic_transfers(before, board, destination, needed, sources):
    """Find a minimum-size legal allocation, including the final Frost result."""
    def search(current, left, index, moves):
        if not left:
            return moves if _frost_ok(before, current) else None
        if index == len(sources) or sum(n for _, n in sources[index:]) < left:
            return None
        origin, available = sources[index]
        for take in range(min(left, available), -1, -1):
            after = _copy(current)
            batch = _entries(after, rc.BELGAE, origin, destination, {rc.WARBAND: take})
            _apply(after, rc.BELGAE, batch)
            result = search(after, left - take, index + 1, moves + batch)
            if result is not None:
                return result
        return None
    return search(board, needed, 0, [])


def _choose_belgic_transfers(state, board, destination, needed, sources):
    """Roll for each supplying Region actually used, not unused candidates."""
    after, moves, remaining = _copy(board), [], list(sources)
    while needed:
        choices = []
        for source in remaining:
            ordered = [source] + [other for other in remaining if other != source]
            completion = _belgic_transfers(state, after, destination, needed, ordered)
            batch = [move for move in completion or [] if move['from_region'] == source[0]]
            if batch:
                choices.append((source, batch))
        source, batch = random_select(state, choices)
        remaining.remove(source)
        _apply(after, rc.BELGAE, batch)
        moves.extend(batch)
        needed -= sum(move['count'] for move in batch)
    return moves


def _belgae(state, regions):
    from fs_bot.commands.rally import _find_subdued_tribe_for_ally
    sim, moves = _copy(state), []
    remaining = {region: count_pieces(state, region, rc.BELGAE, rc.WARBAND)
                 for region in regions}
    while True:
        candidates = []
        for destination in regions:
            if (is_controlled_by(sim, destination, rc.BELGAE)
                    or not _find_subdued_tribe_for_ally(sim, destination, rc.BELGAE)):
                continue
            others = sum(count_pieces(sim, destination, faction)
                         for faction in rc.FACTIONS if faction != rc.BELGAE)
            needed = others + 1 - count_pieces(sim, destination, rc.BELGAE)
            sources = []
            for origin in regions:
                if origin == destination:
                    continue
                available = min(remaining[origin], count_pieces(sim, origin, rc.BELGAE, rc.WARBAND))
                if is_controlled_by(sim, origin, rc.BELGAE):
                    enemies = sum(count_pieces(sim, origin, faction)
                                  for faction in rc.FACTIONS if faction != rc.BELGAE)
                    available = min(available, count_pieces(sim, origin, rc.BELGAE) - enemies - 1)
                # §8.4.1: leave four with the stationary Leader as able.
                if get_leader_in_region(sim, origin, rc.BELGAE):
                    available = min(available, max(0, count_pieces(
                        sim, origin, rc.BELGAE, rc.WARBAND) - 4))
                if available > 0:
                    sources.append((origin, available))
            if (sum(n for _, n in sources) >= needed
                    and _belgic_transfers(state, sim, destination, needed, sources) is not None):
                candidates.append((destination, needed, sources))
        if not candidates:
            break
        destination, needed, sources = random_select(state, candidates)
        # Equal supplying Regions are selected by §8.3.4. Complete the
        # chosen Region before selecting another, within the minimum needed.
        proposed = _choose_belgic_transfers(state, sim, destination, needed, sources)
        for move in proposed:
            remaining[move['from_region']] -= move['count']
        moves.extend(proposed)
        _apply(sim, rc.BELGAE, proposed)
    return {'moves': moves}


def _roman(state, regions):
    from fs_bot.cards.war_fleet_roman import roman_moves
    return {'moves': roman_moves(state, regions)}


def derive_war_fleet(state, faction, shaded=False):
    """Derive actual relocations; only accepted tie choices advance live RNG."""
    planning = _copy(state)
    regions = coastal_regions(planning, faction)
    planner = {rc.ARVERNI: _arverni, rc.AEDUI: _aedui,
               rc.BELGAE: _belgae, rc.ROMANS: _roman}.get(faction)
    result = planner(planning, regions) if planner else {'moves': []}
    state['rng'].setstate(planning['rng'].getstate())
    return result


def resolve_war_fleet_follow_on(state, faction):
    """Card instructions govern the one free Command after relocation."""
    from fs_bot.engine import execute as ex
    allowed = set(coastal_regions(state, faction))
    nps = state.get('non_player_factions', set())
    planner = None
    if faction in nps and faction == rc.ARVERNI:
        battle = (state.get('event_params') or {}).get('_war_fleet_battle')
        if not battle:
            result = {'executed': False, 'command': None, 'declined_no_effect': True,
                      'reason': 'no player target under the Arverni War Fleet instruction'}
        else:
            with free_action_scope(state, faction):
                result = ex._execute_battle(state, faction, {
                    'command': rc.CMD_BATTLE, 'sa': 'No SA', 'sa_regions': [],
                    'details': {'battle_plan': [battle]}})
        return [{'free_action': 'free_command', 'flag': 'card_62', 'result': result}]
    if faction in nps and faction == rc.BELGAE:
        result = ex._resolve_free_rally(state, faction, allowed_regions=allowed, max_regions=1)
    else:
        if faction in nps and faction == rc.AEDUI:
            from fs_bot.bots.aedui_bot import node_a_rally
            planner = node_a_rally
        result = ex._resolve_free_command(state, faction, allowed_regions=allowed,
                                          limited=True, _planner=planner)
    return [{'free_action': 'free_command', 'flag': 'card_62', 'result': result}]


def np_war_fleet_available(state, faction):
    """Compare the entire allowed Event on detached state; never query humans."""
    from fs_bot.cards.card_effects import execute_card_62
    if faction == rc.GERMANS:  # Printed instruction: No Germans.
        return False
    sim = _copy(state)
    params = derive_war_fleet(sim, faction)
    if faction == rc.ARVERNI and not params.get('_war_fleet_battle'):
        return False
    before = deepcopy({key: sim[key] for key in ('spaces', 'tribes', 'available', 'resources')})
    sim['event_params'], sim['executing_faction'] = params, faction
    with free_action_scope(sim, faction):
        execute_card_62(sim)
        results = resolve_war_fleet_follow_on(sim, faction)
    from fs_bot.engine.free_actions import _result_error
    if _result_error(results):
        raise ValueError(f'War Fleet planner produced an invalid plan: {results}')
    return (any(sim[key] != before[key] for key in before)
            or any(item['result'].get('executed') for item in results))
