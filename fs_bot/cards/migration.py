"""Card 66 Migration: the Event's chooser commands real German pieces."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import rally_in_region, _find_subdued_tribe_for_ally
from fs_bot.engine.free_actions import (consult_free_action, execute_free_action_plan,
                                        validate_free_action_response)
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})


def _request(command):
    return {'kind': 'free_action', 'request_type': 'event_command',
            'card_id': 66, 'acting_faction': rc.GERMANS,
            'allowed_commands': [command], 'max_regions': 2,
            'with_sa': False, 'free': True}


def _action(command, plan):
    return {'command': command, 'sa': 'No SA', 'sa_regions': [],
            'details': {f'{command.lower()}_plan': plan}}


def _frost_ok(before, after):
    """§8.4.4 remains in force during free Event actions (§5.4)."""
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    from fs_bot.engine.victory import calculate_victory_margin
    if not before.get('frost') and not is_frost(before):
        return True
    for faction in get_sop_factions(before):
        if faction in before.get('non_player_factions', set()):
            continue
        start = calculate_victory_margin(before, faction)
        if calculate_victory_margin(after, faction) > max(0, start):
            return False
    return True


def _rally_candidates(state, chooser, excluded=()):
    """Legal German Rally options; Roman instruction forbids placing Allies.

    Base §3.4.1 permits an Ally followed by Warbands in the same Region.
    These are actual German operations, without a German bot or Germans Phase.
    """
    candidates = []
    for region in sorted(get_playable_regions_for_state(state, rc.GERMANS)):
        if region in excluded:
            continue
        sim = _copy(state)
        plan = {'allies': [], 'warbands': []}
        if chooser != rc.ROMANS and get_available(sim, rc.GERMANS, rc.ALLY):
            tribes = _find_subdued_tribe_for_ally(sim, region, rc.GERMANS)
            for tribe in tribes:
                try:
                    rally_in_region(sim, region, rc.GERMANS, 'place_ally',
                                    tribe=tribe, free=True)
                except CommandError:
                    continue
                plan['allies'].append({'region': region, 'tribe': tribe})
                break
        try:
            result = rally_in_region(sim, region, rc.GERMANS, 'place_warbands',
                                     free=True, include_home_bonus=True)
            if result.get('pieces_placed'):
                plan['warbands'].append(region)
        except CommandError:
            pass
        if any(plan.values()) and _frost_ok(state, sim):
            candidates.append((region, plan, sim))
    return candidates


def _default_rally(state, chooser):
    sim = _copy(state)
    selected, plan = [], {'allies': [], 'warbands': []}
    for _ in range(2):
        candidates = _rally_candidates(sim, chooser, selected)
        if chooser == rc.ROMANS and not _march_choices(sim, chooser):
            # If Rally must create the group required by the Roman March
            # instruction, select such an origin before optional other Rally.
            candidates = [candidate for candidate in candidates
                          if _march_choices(candidate[2], chooser)]
        if not candidates:
            break
        # §8.2.3 places the most Allies, then other pieces, within the
        # Event instruction (Romans never place German Allies). Only equal
        # candidates go to the §8.3.4 random selection.
        def placed(candidate):
            after = candidate[2]
            return tuple(get_available(sim, rc.GERMANS, piece)
                         - get_available(after, rc.GERMANS, piece)
                         for piece in (rc.ALLY, rc.WARBAND))
        best = max(map(placed, candidates))
        candidates = [candidate for candidate in candidates if placed(candidate) == best]
        region, chosen, after = random_select(state, candidates)
        selected.append(region)
        for key in plan:
            plan[key].extend(chosen[key])
        sim = after
    return _action(rc.CMD_RALLY, plan) if selected else None


def _march_choices(state, chooser, excluded=(), original=None):
    playable = set(get_playable_regions_for_state(state, rc.GERMANS))
    candidates = []
    for origin in sorted(playable - set(excluded)):
        n = count_pieces(state, origin, rc.GERMANS, rc.WARBAND)
        if original is not None:
            n = min(n, original.get(origin, 0))
        if not n:
            continue
        if chooser == rc.ROMANS and not count_pieces(state, origin, rc.ROMANS):
            continue
        destinations = []
        for dest in sorted(get_adjacent(origin, state['scenario'])):
            if dest not in playable:
                continue
            if chooser == rc.ROMANS and count_pieces(state, dest, rc.ROMANS):
                continue
            action = _march_action([(origin, dest, n)])
            sim = _copy(state)
            result = execute_free_action_plan(sim, chooser, _request(rc.CMD_MARCH), action)
            if result.get('executed') and not result.get('errors') and _frost_ok(state, sim):
                destinations.append(dest)
        if destinations:
            candidates.append((origin, destinations, n))
    return candidates


def _march_action(moves):
    return _action(rc.CMD_MARCH, {
        'origins': [origin for origin, _, _ in moves],
        'destinations': list(dict.fromkeys(dest for _, dest, _ in moves)),
        'routes': {origin: [dest] for origin, dest, _ in moves},
        'groups': {origin: {rc.WARBAND: n} for origin, _, n in moves}})


def _default_march(state, chooser):
    sim, moves, used = _copy(state), [], []
    # Freeze original groups so arrivals cannot March again from a later origin.
    original = {r: count_pieces(state, r, rc.GERMANS, rc.WARBAND)
                for r in get_playable_regions_for_state(state, rc.GERMANS)}
    for _ in range(2):
        choices = _march_choices(sim, chooser, used, original)
        if not choices:
            break
        origin, destinations, _ = random_select(state, choices)
        dest = random_select(state, destinations)
        move = (origin, dest, original[origin])
        moves.append(move)
        used.append(origin)
        execute_free_action_plan(sim, chooser, _request(rc.CMD_MARCH), _march_action([move]))
    return _march_action(moves) if moves else None


def can_roman_migrate(state):
    """Printed 'No Romans' fallback when no from-Romans/to-no-Romans move exists.

    Rally precedes March, so an otherwise empty origin may gain Warbands from
    its existing German Ally or the Germania home minimum. No live RNG changes.
    """
    sim = _copy(state)
    if _march_choices(sim, rc.ROMANS):
        return True
    return any(_march_choices(after, rc.ROMANS)
               for _, _, after in _rally_candidates(sim, rc.ROMANS))


def _freeze_march_groups(state, action):
    """Base §3.4.2 allows one moving group per origin, only original pieces."""
    from fs_bot.engine.execute import _collect_march_moves, _mobile_march_group
    moves, _ = _collect_march_moves(_copy(state), rc.GERMANS, action)
    origins = [move['origin'] for move in moves]
    if len(origins) != len(set(origins)):
        raise ValueError('Germanic March permits only one moving group per origin (§3.4.2)')
    result = deepcopy(action)
    result['details'] = {'march_plan': {
        'origins': origins,
        'destinations': list(dict.fromkeys(move['path'][-1] for move in moves)),
        'routes': {move['origin']: move['path'] for move in moves},
        'groups': {move['origin']: (move.get('group') if move.get('group') is not None
                   else _mobile_march_group(state, rc.GERMANS, move['origin'])) for move in moves}}}
    return result


def resolve_migration(state, chooser):
    """Rally in up to two Regions, then March from up to two, chosen separately."""
    if state['scenario'] not in rc.BASE_SCENARIOS:
        raise ValueError('Migration is a base-game Event; Ariovistus uses Winter Uprising')
    results = {}
    for command, default in ((rc.CMD_RALLY, _default_rally),
                             (rc.CMD_MARCH, _default_march)):
        from fs_bot.cards.card_effects import _event_step
        _event_step(state, "66.german_grant")
        request = _request(command)
        action = consult_free_action(state, chooser, request)
        if action is None:
            action = default(state, chooser)
        if action is None or action.get('decline'):
            results[command.lower()] = {'executed': False, 'command': command,
                'declined_no_effect': True, 'reason': f'Migration {command} declined'}
            continue
        if command == rc.CMD_MARCH:
            action = _freeze_march_groups(state, action)
        error = validate_free_action_response(state, chooser, request, action)
        if error:
            raise ValueError(error)
        results[command.lower()] = execute_free_action_plan(state, chooser, request, action)
    return [{'free_action': 'german_rally_march', 'flag': 'card_66',
             'chooser': chooser, 'faction': rc.GERMANS, **results,
             'executed': any(result.get('executed') for result in results.values())}]
