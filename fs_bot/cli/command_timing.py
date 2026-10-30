"""Detached per-operation planning for Raid and Seize timing choices."""

from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import planning_copy, prepare, inspect_board
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.menus import prompt_choice, prompt_yes_no


def collect_raid(state, faction, stdin, stdout, single, *, excluded=()):
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.cli.human_plan import _regions_with_pieces, _pick_regions
    from fs_bot.commands.common import _is_devastated
    from fs_bot.commands.raid import (
        get_valid_steal_targets, max_raiders_per_region, validate_raid_region,
        _raid_in_region,
    )
    from fs_bot.commands.sa_enlist import borrowed_count, FREE_FORCE_KEY
    from fs_bot.engine.action_windows import get_cohorts, set_cohorts, clear_cohorts
    sim = planning_copy(state)
    view = HumanTurnDisplay(stdout)
    view.remember(state, (faction,))

    def can_gain(region):
        return (not _is_devastated(sim, region)
                and not (faction == rc.GERMANS and sim['scenario'] in rc.BASE_SCENARIOS))

    regions = [region for region in _regions_with_pieces(sim, faction)
               if region not in excluded
               and validate_raid_region(sim, region, faction, allow_base_germans=True)[0]
               and (can_gain(region) or get_valid_steal_targets(sim, region, faction))]
    if not regions:
        return None
    picked = _pick_regions(stdin, stdout, 'Raid in which Region(s)?', regions,
                           single=single, max_regions=state.get('_cli_command_max_regions'))
    plan, carried, tails = [], [], {}
    for region in picked:
        key = f'raid_credit:{region}'
        completed = 0
        while completed < max_raiders_per_region(sim, faction):
            sim, timing = prepare(sim, faction, stdin, stdout, stage='raid_flip',
                                  region=region, index=completed)
            carried.extend(timing)
            view.before_decision(sim, faction)
            hidden = count_pieces_by_state(sim, region, faction, rc.WARBAND, rc.HIDDEN)
            if not hidden:
                break
            options = [('Finish Raiding in this Region', 'done')]
            options.extend((f'Steal from {target}', target)
                           for target in get_valid_steal_targets(sim, region, faction))
            if can_gain(region):
                options.append(('Gain 1 Resource', None))
            with inspect_board(sim, stdout):
                selected = prompt_choice(stdin, stdout,
                    f'Raid {completed + 1} target in {region}?', options)
                if selected == 'done':
                    break
                entry = {'region': region, 'target': selected}
                action = {'type': 'gain'} if selected is None else {'type': 'steal', 'target': selected}
                borrowed = borrowed_count(sim, region, rc.HIDDEN) if faction == rc.BELGAE else 0
                if borrowed:
                    owners = [(owner, owner) for owner, count in (
                        (rc.GERMANS, borrowed), (rc.BELGAE, hidden - borrowed)) if count]
                    owner = (prompt_choice(stdin, stdout,
                             'Reveal a Warband belonging to which Faction?', owners)
                             if len(owners) > 1 else owners[0][1])
                    entry['physical_owner'] = action['physical_owner'] = owner
            # Reserve exactly this deterministic flip. Intrinsic Intimidate
            # remains an actual human decision after all the Region's raids.
            _raid_in_region(sim, region, faction, [action], free=True, _resolve_intrinsic=False)
            if carried:
                entry['timing_actions'] = carried
            plan.append(entry)
            carried = []
            completed += 1
            if faction == rc.GERMANS and sim['scenario'] in rc.ARIOVISTUS_SCENARIOS:
                ledger = get_cohorts(sim, key)
                if not ledger:
                    item = {'id': key, 'label': 'Warbands that just Raided',
                            'region': region, 'piece_type': rc.WARBAND,
                            'piece_state': rc.REVEALED, 'count': 0}
                    force = sim.get(FREE_FORCE_KEY, {})
                    if force.get('faction', rc.GERMANS) == faction and region in force.get('pieces', {}):
                        item['loan_kind'] = 'free_force'
                    ledger = [item]
                ledger[0]['count'] += 1
                set_cohorts(sim, key, faction, ledger)
        if completed and carried:
            tails[region] = carried
            carried = []
        clear_cohorts(sim, key)
    details = {'raid_plan': plan}
    if tails:
        details['raid_timing_actions'] = tails
    if carried:
        details['after_command_timing_actions'] = carried
    return details if plan else None


def collect_seize(state, faction, stdin, stdout, single, *, excluded=()):
    from fs_bot.board.pieces import count_pieces
    from fs_bot.cli.human_plan import _playable_regions, _pick_regions
    from fs_bot.commands.seize import get_dispersible_tribes, calculate_forage
    sim = planning_copy(state)
    stdout.write('Seize planning reserves Dispersed markers and estimates Forage. '
                 'Rally checks and Harassment are resolved during execution; '
                 'their effects may change the later choices.\n')
    view = HumanTurnDisplay(stdout)
    view.remember(state, (faction,))
    candidates = [region for region in _playable_regions(sim, faction)
                  if region not in excluded and count_pieces(sim, region, faction)]
    if not candidates:
        return None
    picked = _pick_regions(stdin, stdout, 'Seize in which Region(s)?', candidates,
                           single=single, max_regions=state.get('_cli_command_max_regions'))
    regions, dispersals, carried, stages = [], [], [], {}
    for region in picked:
        sim, timing = prepare(sim, faction, stdin, stdout, stage='seize_region',
                              region=region, index=len(regions))
        carried.extend(timing)
        view.before_decision(sim, faction)
        if not count_pieces(sim, region, faction):
            continue
        tribes = get_dispersible_tribes(sim, region)
        with inspect_board(sim, stdout):
            disperse = bool(tribes) and prompt_yes_no(stdin, stdout,
                f'Disperse Subdued Tribes in {region}?', default=True)
        chosen = tribes if disperse else []
        if disperse:
            dispersals.append(region)
        if carried:
            stages[f'seize_region:{len(regions)}'] = carried
        regions.append(region)
        carried = []
        # Reserve only deterministic effects. Rally dice and Harassment
        # belong to execution and are never rolled by these planning menus.
        for tribe in chosen:
            sim['tribes'][tribe]['status'] = rc.DISPERSED
        sim['resources'][faction] = min(rc.MAX_RESOURCES,
            sim['resources'][faction] + calculate_forage(sim, region, chosen))
    details = {'_regions': regions, 'disperse_regions': dispersals}
    if stages:
        details['stage_timing_actions'] = stages
    if carried:
        details['after_command_timing_actions'] = carried
    return details if regions else None
