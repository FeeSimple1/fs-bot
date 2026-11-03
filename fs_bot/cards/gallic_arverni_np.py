"""PR-10: one Event-granted Command for automatic Ariovistus Arverni.

Owner-adopted provisional ruling, subject to authoritative correction.
Actual At War and A6.2 target rolls precede the first possible permitted
Command in Rally/March/Raid/Battle order. A Battle has inherent Ambush;
ordinary optional Special Activities are never granted. A6.2.1–A6.2.4,
§§3.3.1–3.3.4, 5.1.1, 5.4 and Event Limited-Command restrictions apply.
"""
from copy import deepcopy
from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state, is_city_tribe

ORDER = (rc.CMD_RALLY, rc.CMD_MARCH, rc.CMD_RAID, rc.CMD_BATTLE)


@contextmanager
def _automatic_actor(state):
    """A1.5/A6: Arverni are game-run, while other actors keep their choices."""
    missing = object()
    original_nps = state.get('non_player_factions', missing)
    original_agent = state.get('decision_agent', missing)

    class OtherActors:
        def __call__(self, board, faction, question):
            if faction == rc.ARVERNI:
                return None
            return original_agent(board, faction, question)

        def __getattr__(self, name):
            return getattr(original_agent, name)

    state['non_player_factions'] = set(() if original_nps is missing else original_nps) | {rc.ARVERNI}
    if original_agent is not missing and original_agent is not None:
        state['decision_agent'] = OtherActors()
    try:
        yield
    finally:
        for key, value in (('non_player_factions', original_nps), ('decision_agent', original_agent)):
            if value is missing:
                state.pop(key, None)
            else:
                state[key] = value


def _copy(state):
    trial = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    trial['_diviciacus_preview'] = True
    return trial


def _regions(state, request):
    allowed = request.get('allowed_regions')
    return sorted(r for r in get_playable_regions_for_state(state, rc.ARVERNI)
                  if allowed is None or r in allowed)


def _limit(request, regions):
    return len(regions) if request.get('max_regions') is None else request['max_regions']


def _action(command, entries, key):
    return {'command': command, 'sa': 'No SA', 'sa_regions': [],
            'regions': list(dict.fromkeys(e['region'] for e in entries)),
            'details': {key: {'steps': entries} if key == 'rally_plan' else entries}}


def _rally(state, request, triggering):
    from fs_bot.cli.recruit_rally import _options
    from fs_bot.commands.rally import rally_in_region
    remaining = set(_regions(state, request)) & set(triggering)
    steps = []
    maximum = _limit(request, remaining)
    while remaining and len(steps) < maximum:
        candidates = []
        for region in sorted(remaining):
            for _, action, values, _ in _options(state, rc.ARVERNI, region, rally=True):
                if action == 'place_warbands':
                    if values[0] > 0:
                        candidates.append((4, region, action, values[0]))
                else:
                    for tribe in values:
                        priority = (0 if action == 'place_citadel' else 1 if is_city_tribe(tribe)
                            else 2 if region in rc.ARVERNI_HOME_REGIONS_ARIOVISTUS else 3)
                        candidates.append((priority, region, action, tribe))
        if not candidates:
            break
        priority = min(c[0] for c in candidates)
        best = [c for c in candidates if c[0] == priority]
        region = random_select(state, sorted({c[1] for c in best}))
        _, _, action, value = random_select(state, [c for c in best if c[1] == region])
        entry = {'region': region, 'action': action,
                 'count' if action == 'place_warbands' else 'tribe': value}
        rally_in_region(state, region, rc.ARVERNI, action, tribe=entry.get('tribe'),
                        count=entry.get('count'), free=True, include_home_bonus=True)
        steps.append(entry)
        remaining.remove(region)
    return _action(rc.CMD_RALLY, steps, 'rally_plan') if steps else None


def _surplus(state, region):
    from fs_bot.board.control import is_controlled_by
    if not is_controlled_by(state, region, rc.ARVERNI):
        return 0
    own = count_pieces(state, region, rc.ARVERNI)
    others = sum(count_pieces(state, region, f) for f in rc.FACTIONS if f != rc.ARVERNI)
    return min(count_pieces(state, region, rc.ARVERNI, rc.WARBAND), max(0, own - others - 1))


def _largest_first(state, groups):
    result = []
    remaining = list(groups)
    while remaining:
        largest = max(n for _, n in remaining)
        selected = random_select(state, sorted(g for g in remaining if g[1] == largest))
        result.append(selected)
        remaining.remove(selected)
    return result


def _march(state, request, target_region):
    from fs_bot.board.control import is_controlled_by
    from fs_bot.commands.march import march_group
    regions = _regions(state, request)
    maximum = _limit(request, regions)
    initial_hiding = [r for r in regions if any(count_pieces_by_state(
        state, r, rc.ARVERNI, rc.WARBAND, visibility) for visibility in (rc.REVEALED, rc.SCOUTED))]
    groups = [(r, _surplus(state, r)) for r in regions if r != target_region]
    groups = [(r, n) for r, n in groups if n > 0]
    moves = []
    # Keep initial groups; neither target arrivals nor a changed Control flag
    # can create another origin during the same March Command.
    def take(destination, candidates):
        for origin, number in _largest_first(state, candidates):
            if len(moves) >= maximum:
                break
            march_group(state, rc.ARVERNI, origin, [destination], {rc.WARBAND: number}, free=True)
            moves.append((origin, destination, number))
            groups.remove((origin, number))
    adjacent = [(r, n) for r, n in groups if target_region in get_adjacent_for_state(state, r, rc.ARVERNI)]
    take(target_region, adjacent)
    if len(moves) < maximum:
        for defender in (rc.AEDUI, rc.ROMANS):
            choices = []
            for destination in sorted(get_playable_regions_for_state(state, rc.ARVERNI)):
                if destination == target_region or not is_controlled_by(state, destination, defender):
                    continue
                adjacent = [(r, n) for r, n in groups
                            if destination in get_adjacent_for_state(state, r, rc.ARVERNI)]
                if not adjacent:
                    continue
                capacity = sum(sorted((n for _, n in adjacent), reverse=True)[:maximum - len(moves)])
                defending = count_pieces(state, destination, defender)
                other = sum(count_pieces(state, destination, f) for f in rc.FACTIONS if f != defender)
                if other + capacity >= defending:
                    choices.append((destination, adjacent))
            if choices:
                destination, adjacent = random_select(state, choices)
                take(destination, adjacent)
                break
    moving_origins = {r for r, _, _ in moves}
    # Original residents at a destination hide before any arrivals.
    stationary = [r for r in initial_hiding if r not in moving_origins]
    if maximum == 1:
        stationary = [] if moves else ([random_select(state, stationary)] if stationary else [])
    else:
        if len(stationary) > maximum - len(moving_origins):
            selected = []
            while len(selected) < maximum - len(moving_origins):
                chosen = random_select(state, stationary)
                selected.append(chosen)
                stationary.remove(chosen)
            stationary = selected
    if not moves and not stationary:
        return None
    origins = [r for r, _, _ in moves]
    action = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [], 'regions': origins,
              'details': {'march_plan': {'origins': origins,
                  'destinations': list(dict.fromkeys(d for _, d, _ in moves)),
                  'routes': {r: [d] for r, d, _ in moves},
                  'groups': {r: {rc.WARBAND: n} for r, _, n in moves}}}}
    return {'moving': action if moves else None, 'in_place': stationary}


def _raid_capacity(state, region):
    """Reserve enough Hidden Warbands for any possible Ambush (A6.2.3).

    The explicit Diviciacus clause protects against eligible combined Hidden
    defenses without asking players to promise a future agreement.
    """
    from fs_bot.engine.diviciacus import eligible_regions, force_scope
    from fs_bot.battle.losses import calculate_losses
    hidden = count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, rc.HIDDEN)
    requirements = []
    for enemy in rc.FACTIONS:
        if enemy == rc.ARVERNI or not count_pieces(state, region, enemy):
            continue
        cooperation = ([region] if enemy in (rc.ROMANS, rc.AEDUI)
                       and region in eligible_regions(state, enemy, 'defense') else [])
        with force_scope(state, enemy, cooperation, phase='defense'):
            enemy_hidden = sum(count_pieces_by_state(state, region, enemy, p, rc.HIDDEN)
                               for p in (rc.WARBAND, rc.AUXILIA))
            if hidden > enemy_hidden and calculate_losses(state, region, rc.ARVERNI, enemy) > 0:
                requirements.append(enemy_hidden + 1)
    return max(0, hidden - min(requirements, default=0))


def _raid(state, request, target_faction):
    from fs_bot.engine.arverni_phase import _get_raid_targets
    from fs_bot.commands.raid import max_raiders_per_region, raid_in_region
    regions = _regions(state, request)
    remaining, entries, selected = set(regions), [], set()
    while remaining and len(selected) < _limit(request, regions):
        candidates = []
        for region in sorted(remaining):
            if _raid_capacity(state, region) <= 0:
                continue
            # Determine the best target tier without drawing speculative ties.
            targets = [f for f in rc.FACTIONS if f != rc.ARVERNI
                       and count_pieces(state, region, f) and state['resources'].get(f, 0) > 0
                       and not count_pieces(state, region, f, rc.FORT)
                       and not count_pieces(state, region, f, rc.CITADEL)]
            if targets:
                tier = min(0 if f == target_faction else 1 if f not in state.get('non_player_factions', ())
                           else 2 for f in targets)
                candidates.append((tier, region))
        if not candidates:
            break
        tier = min(t for t, _ in candidates)
        region = random_select(state, [r for t, r in candidates if t == tier])
        remaining.remove(region)
        number = min(_raid_capacity(state, region), max_raiders_per_region(state, rc.ARVERNI))
        actions = []
        for target in _get_raid_targets(state, region, target_faction):
            count = min(number - len(actions), state['resources'].get(target, 0))
            actions.extend({'type': 'steal', 'target': target} for _ in range(count))
            if len(actions) == number:
                break
        if actions:
            raid_in_region(state, region, rc.ARVERNI, actions)
            entries.extend({'region': region, 'target': e['target']} for e in actions)
            selected.add(region)
    return _action(rc.CMD_RAID, entries, 'raid_plan') if entries else None


def _battle(state, request, target_region, target_faction):
    from fs_bot.engine.arverni_phase import _get_battle_targets
    regions = _regions(state, request)
    others = [r for r in regions if r != target_region]
    state['rng'].shuffle(others)
    order = ([target_region] if target_region in regions else []) + others
    entries = []
    for region in order:
        hidden = count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, rc.HIDDEN)
        if not hidden:
            continue
        targets = _get_battle_targets(state, region, target_faction, hidden)
        if targets:
            entries.append({'region': region, 'target': targets[0]})
            if len(entries) >= _limit(request, regions):
                break
    if not entries:
        return None
    action = _action(rc.CMD_BATTLE, entries, 'battle_plan')
    action.update(sa=rc.SA_AMBUSH, sa_regions=list(action['regions']))
    return action


def _execute(state, command, plan, request):
    from fs_bot.engine.execute import _execute_battle
    from fs_bot.engine.free_actions import execute_free_action_plan
    if command == rc.CMD_BATTLE:
        # A6.2.4's Ambush is intrinsic, not a user-selected optional SA.
        result = _execute_battle(state, rc.ARVERNI, plan, _require_ambush=True)
        result['intrinsic_special_activity'] = rc.SA_AMBUSH
        return result
    if command == rc.CMD_MARCH:
        from fs_bot.commands.march import _flip_origin_pieces
        from fs_bot.engine.action_windows import window
        flipped = {}
        for region in plan['in_place']:
            window(state, 'arverni_event_march_in_place', author=rc.ARVERNI, region=region)
            flipped[region] = _flip_origin_pieces(state, region, rc.ARVERNI)
        result = (execute_free_action_plan(state, rc.ARVERNI, request, plan['moving'])
                  if plan['moving'] is not None else {'executed': False, 'command': rc.CMD_MARCH})
        result['in_place'] = flipped
        result['executed'] = result['executed'] or any(any(v.values()) for v in flipped.values())
        return result
    if command == rc.CMD_RAID:
        # Ariovistus Arverni Resources are not tracked (A1.8/A6.4.2).
        existed, value = rc.ARVERNI in state['resources'], state['resources'].get(rc.ARVERNI)
        try:
            result = execute_free_action_plan(state, rc.ARVERNI, request, plan)
        finally:
            if existed:
                state['resources'][rc.ARVERNI] = value
            else:
                state['resources'].pop(rc.ARVERNI, None)
        result['resources_gained_total'] = 0
        for raid in result.get('raids', []):
            raid['resources_gained'] = 0
        return result
    return execute_free_action_plan(state, rc.ARVERNI, request, plan)


def resolve_command(state, request):
    """Resolve only one automatic Command, recomputing At War/targets each call."""
    from fs_bot.engine.arverni_phase import check_arverni_at_war, select_arverni_targets
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        raise ValueError('PR-10 automatic Arverni Commands apply only in Ariovistus scenarios.')
    at_war, triggering = check_arverni_at_war(state)
    if not at_war:
        return {'executed': False, 'command': None, 'declined_no_effect': True,
                'reason': 'Automatic Arverni are At Peace.', 'at_war': False, 'provisional_ruling': 'PR-10'}
    target_region, target_faction = select_arverni_targets(state, triggering)
    with _automatic_actor(state), free_action_scope(state, rc.ARVERNI):
        for command in ORDER:
            if command not in request['allowed_commands']:
                continue
            trial = _copy(state)
            if command == rc.CMD_RALLY:
                plan = _rally(trial, request, triggering)
            elif command == rc.CMD_MARCH:
                plan = _march(trial, request, target_region)
            elif command == rc.CMD_RAID:
                plan = _raid(trial, request, target_faction)
            else:
                plan = _battle(trial, request, target_region, target_faction)
            if plan is None:
                continue
            state['rng'].setstate(trial['rng'].getstate())
            result = _execute(state, command, plan, request)
            return {**result, 'at_war': True, 'target_region': target_region,
                    'target_faction': target_faction, 'provisional_ruling': 'PR-10'}
    return {'executed': False, 'command': None, 'declined_no_effect': True,
            'reason': 'No permitted Arverni Command can have an effect.',
            'at_war': True, 'target_region': target_region, 'target_faction': target_faction,
            'provisional_ruling': 'PR-10'}
