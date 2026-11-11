"""Roman Special Activity planning at each complete operation boundary."""

from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import planning_copy, prepare, inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.commands.common import CommandError


def collect_build(state, faction, stdin, stdout, *, pending=None):
    """Preview each selected Region completely in player order (§4.1)."""
    from fs_bot.cli.human_plan import _regions_with_pieces, _pick_regions
    from fs_bot.commands.sa_build import (
        validate_build_region, build_fort, build_subdue, build_place_ally,
    )
    from fs_bot.engine.action_validation import command_parts, command_regions
    from fs_bot.map.map_data import get_tribes_in_region_for_state
    from fs_bot.cards.capabilities import is_capability_active
    sim = planning_copy(state)
    view = HumanTurnDisplay(stdout)
    view.remember(state, (faction,))
    candidates = [r for r in _regions_with_pieces(sim, faction)
                  if validate_build_region(sim, r)[0]]
    if not candidates:
        return None, None
    picked = _pick_regions(stdin, stdout, 'Build in which Region(s)?', candidates,
                           single=is_capability_active(sim, 12, rc.EVENT_SHADED))
    if not picked:
        return None, None
    seized = {r for part in command_parts(pending or {})
              if part.get('command') == 'Seize' for r in command_regions(part)}
    plan = {'forts': [], 'subdue': [], 'allies': []}
    stages, carried, tribe_regions = {}, [], set()

    def legal(operation, region, *args):
        if not validate_build_region(sim, region)[0]:
            return False
        trial = planning_copy(sim)
        try:
            operation(trial, region, *args)
        except (CommandError, ValueError, KeyError):
            return False
        return True

    for region in picked:
        for stage, key in (('build_fort', 'forts'), ('build_subdue', 'subdue'),
                           ('build_ally', 'allies')):
            if key != 'forts' and (region in seized or region in tribe_regions):
                continue
            sim, timing = prepare(sim, faction, stdin, stdout, stage=stage,
                                  index=len(plan[key]), region=region)
            carried.extend(timing)
            view.before_decision(sim, faction)
            options = [('Skip this Build option', None)]
            if key == 'forts':
                if legal(build_fort, region):
                    options.append(('Place a Fort', region))
            else:
                for tribe in get_tribes_in_region_for_state(sim, region):
                    owner = sim['tribes'][tribe].get('allied_faction')
                    if key == 'subdue' and owner not in (None, faction):
                        if legal(build_subdue, region, tribe, owner):
                            options.append((f'Subdue {tribe} ({owner})', tribe))
                    elif key == 'allies' and legal(build_place_ally, region, tribe):
                        options.append((f'Place a Roman Ally at {tribe}', tribe))
            if len(options) == 1:
                continue
            with inspect_board(sim, stdout):
                selected = prompt_choice(stdin, stdout, f'{region}: {stage.replace("_", " ")}?', options)
            if selected is None:
                continue
            if key == 'forts':
                if carried:
                    stages[f'{stage}:{len(plan[key])}'] = carried
                plan[key].append(region)
                build_fort(sim, region)
            else:
                entry = {'region': region, 'tribe': selected}
                if carried:
                    entry['timing_actions'] = carried
                plan[key].append(entry)
                if key == 'subdue':
                    build_subdue(sim, region, selected, sim['tribes'][selected]['allied_faction'])
                else:
                    build_place_ally(sim, region, selected)
                tribe_regions.add(region)
            carried = []
    plan['region_order'] = [r for r in picked if r in plan['forts'] or any(
        e['region'] == r for key in ('subdue', 'allies') for e in plan[key])]
    extra = {'build_plan': plan}
    if stages or carried:
        extra['sa_details'] = {}
        if stages:
            extra['sa_details']['stage_timing_actions'] = stages
        if carried:
            extra['sa_details']['after_sa_timing_actions'] = carried
    if not plan['region_order']:
        # No operation was authored. The outer collector can keep explicitly
        # selected timing actions rather than silently turning them into Pass.
        return (picked, extra) if carried else (None, None)
    return picked, extra


def collect_scout(state, faction, stdin, stdout, *, pending=None):
    """Choose from the evolving board without moving any counter twice."""
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.cli.human_plan import _playable_regions
    from fs_bot.commands.common import check_leader_proximity
    from fs_bot.commands.sa_scout import (
        scout_movement_step, scout_moved_count, clear_scout_cohorts, scout_reveal,
    )
    from fs_bot.map.map_data import get_adjacent_for_state
    from fs_bot.cards.capabilities import is_capability_active
    sim = planning_copy(state)
    clear_scout_cohorts(sim)
    view = HumanTurnDisplay(stdout)
    view.remember(state, (faction,))
    moves, targets, carried = [], [], []
    while True:
        sim, timing = prepare(sim, faction, stdin, stdout, stage='scout_move', index=len(moves))
        carried.extend(timing)
        view.before_decision(sim, faction)
        options = [('Finish Scout movement', None)]
        for origin in sorted(_playable_regions(sim, faction)):
            if origin == rc.BRITANNIA:
                continue
            destinations = [r for r in sorted(get_adjacent_for_state(sim, origin, faction))
                            if r != rc.BRITANNIA]
            if not destinations:
                continue
            for visibility in (rc.REVEALED, rc.HIDDEN):
                count = count_pieces_by_state(sim, origin, faction, rc.AUXILIA, visibility)
                count -= scout_moved_count(sim, origin, visibility)
                if count > 0:
                    options.append((f'{visibility} Auxilia from {origin} ({count} unmoved)',
                                    (origin, visibility, count, destinations)))
        with inspect_board(sim, stdout):
            selected = prompt_choice(stdin, stdout, 'Scout movement?', options)
            if selected is None:
                break
            origin, visibility, maximum, destinations = selected
            destination = prompt_choice(stdin, stdout, 'Move Auxilia INTO:',
                                         [(r, r) for r in destinations])
            count = prompt_choice(stdin, stdout, 'How many Auxilia?',
                                  [(str(n), n) for n in range(1, maximum + 1)])
        entry = {'from_region': origin, 'to_region': destination,
                 'count': count, 'piece_state': visibility}
        from fs_bot.engine.diviciacus import KEY
        cooperation = sim.get(KEY, {})
        if cooperation.get('faction') == faction and origin in cooperation.get('pieces', {}):
            from fs_bot.cli.diviciacus import collect_pieces
            raw = sim['spaces'][origin].get('pieces', {})
            available = {
                rc.ROMANS: raw.get(rc.ROMANS, {}).get(visibility, {}).get(rc.AUXILIA, 0)
                    - scout_moved_count(sim, origin, visibility, rc.ROMANS),
                rc.AEDUI: cooperation['pieces'][origin].get(visibility, 0)
                    - scout_moved_count(sim, origin, visibility, rc.AEDUI),
            }
            with inspect_board(sim, stdout):
                entry['physical_owners'] = collect_pieces(sim, faction, {
                    'available': available, 'count': count, 'phase': 'scout_movement',
                    'region': origin, 'piece_type': rc.AUXILIA,
                }, stdin, stdout)['counts']
        # prepare already applied these choices on sim; the engine replays
        # them once from the original board before the same movement.
        scout_movement_step(sim, entry, index=len(moves))
        if carried:
            entry['timing_actions'] = carried
        moves.append(entry)
        carried = []
    movement_tail = carried
    carried = []
    clear_scout_cohorts(sim)
    while True:
        sim, timing = prepare(sim, faction, stdin, stdout, stage='scout_reveal', index=len(targets))
        carried.extend(timing)
        view.before_decision(sim, faction)
        options = [('Finish Scout Reveal', None)]
        for region in sorted(_playable_regions(sim, faction)):
            if (targets and is_capability_active(sim, 12, rc.EVENT_SHADED)
                    and region != targets[0]['region']):
                continue
            if not check_leader_proximity(sim, region, faction, rc.CAESAR, 'Scout Reveal')[0]:
                continue
            hidden = count_pieces_by_state(sim, region, faction, rc.AUXILIA, rc.HIDDEN)
            if hidden:
                options.append((f'Scout in {region} ({hidden} Hidden Auxilia)', (region, hidden)))
        with inspect_board(sim, stdout):
            selected = prompt_choice(stdin, stdout, 'Scout Reveal?', options)
            if selected is None:
                break
            region, hidden = selected
            auxilia = prompt_choice(stdin, stdout, 'How many Hidden Auxilia to Reveal?',
                                    [(str(n), n) for n in range(1, hidden + 1)])
            chosen, used, capacity = [], {}, 2 * auxilia
            while capacity:
                choices = [('Finish target selection', None)]
                for enemy in rc.FACTIONS:
                    if enemy == faction:
                        continue
                    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                        count = count_pieces_by_state(sim, region, enemy, rc.WARBAND, visibility)
                        maximum = min(capacity, count - used.get((enemy, visibility), 0))
                        if maximum:
                            choices.append((f'{enemy} {visibility} Warbands (up to {maximum})',
                                            (enemy, visibility, maximum)))
                if len(choices) == 1:
                    break
                selected = prompt_choice(stdin, stdout, 'Scout which Warbands?', choices)
                if selected is None:
                    break
                enemy, visibility, maximum = selected
                count = prompt_choice(stdin, stdout, 'How many Warbands?',
                                      [(str(n), n) for n in range(1, maximum + 1)])
                chosen.append({'faction': enemy, 'piece_state': visibility, 'count': count})
                used[enemy, visibility] = used.get((enemy, visibility), 0) + count
                capacity -= count
            entry = {'region': region, 'auxilia_count': auxilia, 'targets': chosen}
            from fs_bot.commands.sa_scout import scout_reveal_owners
            available = scout_reveal_owners(sim, region)
            if all(available.values()) and len(available) > 1 and auxilia < sum(available.values()):
                from fs_bot.cli.diviciacus import collect_pieces
                entry['physical_owners'] = collect_pieces(sim, faction, {
                    'available': available, 'count': auxilia, 'phase': 'scout_reveal',
                    'region': region, 'piece_type': rc.AUXILIA,
                }, stdin, stdout)['counts']
        scout_reveal(sim, region, auxilia, chosen, physical_owners=entry.get('physical_owners'))
        if carried:
            entry['timing_actions'] = carried
        targets.append(entry)
        carried = []
    plan = {'auxilia_moves': moves, 'scout_targets': targets}
    if movement_tail:
        plan['movement_timing_actions'] = movement_tail
    extra = {'scout_plan': plan}
    if carried:
        extra['sa_details'] = {'after_sa_timing_actions': carried}
    regions = sorted({m['from_region'] for m in moves} | {t['region'] for t in targets})
    return (regions, extra) if moves or targets or movement_tail or carried else (None, None)
