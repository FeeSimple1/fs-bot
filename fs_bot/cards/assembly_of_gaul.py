"""Card 52 shaded: one free Command with two independently timed abilities."""
from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_enlist import BORROW_KEY, begin_borrow, end_borrow, is_borrow_plan
from fs_bot.engine import execute as ex
from fs_bot.engine.action_validation import command_regions

BATTLE_ABILITIES = (rc.SA_AMBUSH, rc.SA_BESIEGE)
ABILITY_DETAILS = {
    'sa_details', 'diviciacus_sa_regions', 'build_plan', 'scout_plan',
    'suborn_plan', 'intimidate_plan', 'enlist', 'trade_region',
}


def accompanying_action(command, ability):
    return dict(command, sa=ability['sa'], sa_regions=ability.get('sa_regions', []),
                sa_timing=ability['sa_timing'],
                details={**command.get('details', {}), **ability.get('details', {})})


def command_steps(action):
    """Completed steps with a remaining portion of the same Command."""
    cmd = action['command']
    details = action.get('details') or {}
    if cmd == rc.CMD_MARCH:
        from fs_bot.engine.march_interruption import ordered_moves
        moves = ordered_moves(action)
        return [(f'Group {group}, {region} after hop {hop}', {'group': group, 'hop': hop})
                for group, move in enumerate(moves, start=1)
                for hop, region in enumerate([move['origin'], *move['path']])
                if group < len(moves) or hop < len(move['path'])]
    if cmd == rc.CMD_RALLY:
        from fs_bot.commands.rally import rally_plan_steps
        entries = rally_plan_steps(details.get('rally_plan') or {})
    elif cmd == rc.CMD_RECRUIT:
        from fs_bot.commands.rally import recruit_plan_entries
        entries = recruit_plan_entries(details.get('recruit_plan') or [])
    elif cmd == rc.CMD_SEIZE:
        entries = [{'region': region} for region in command_regions(action)]
    else:
        entries = details.get('battle_plan' if cmd == rc.CMD_BATTLE else 'raid_plan') or []
    return [(f"{index}. {entry['region']}", index)
            for index, entry in enumerate(entries[:-1], start=1)]


def plan_error(state, faction, request, action):
    from fs_bot.engine.free_actions import _plan_structure_error
    from fs_bot.engine.action_validation import _validate_battle_or_raid_boundary

    if (request.get('request_type') != 'event_command' or not request.get('with_sa')
            or request.get('max_special_abilities') != 2):
        return 'Only the Assembly of Gaul grant accepts a multi-ability plan.'
    abilities = action['special_abilities']
    if (not isinstance(abilities, list) or len(abilities) != 2
            or any(not isinstance(ability, dict) for ability in abilities)):
        return 'Supply exactly two Special Ability plans, or use the ordinary Command plan.'
    if (action.get('sa') not in (None, 'No SA') or action.get('sa_regions')
            or action.get('sa_timing') is not None):
        return 'Put both Special Abilities in special_abilities.'
    command = {key: value for key, value in action.items() if key != 'special_abilities'}
    details = command.get('details') or {}
    if set(details) & (ABILITY_DETAILS | {'command_parts', 'sa_after_step', 'sa_after_rally_step'}):
        return 'Use one ordered Command plan and put each ability at its own timing.'
    error = _plan_structure_error(state, faction, request, command)
    if error:
        return error
    if abilities[0].get('sa') == abilities[1].get('sa'):
        return 'Choose two distinct Special Abilities.'
    for ability in abilities:
        if (set(ability) - {'sa', 'sa_regions', 'details', 'sa_timing', 'after_step'}
                or not isinstance(ability.get('sa'), str) or ability['sa'] == 'No SA'
                or not isinstance(ability.get('details', {}), dict)
                or set(ability.get('details', {})) - ABILITY_DETAILS):
            return 'Each Special Ability needs its own selection, details and timing.'
        timing = ability.get('sa_timing')
        if timing not in ('before', 'during', 'after'):
            return 'Choose before, during or after the Command for each ability.'
        projected = accompanying_action(command, ability)
        error = _plan_structure_error(state, faction, request, projected)
        if error:
            return error
        if ability['sa'] in BATTLE_ABILITIES:
            regions = projected['sa_regions']
            if (timing != 'during' or 'after_step' in ability or not regions
                    or any(not isinstance(region, str) for region in regions)
                    or len(regions) != len(set(regions))
                    or not set(regions).issubset(command_regions(command))):
                return 'Ambush and Besiege select distinct Regions in the Battle plan.'
            if faction == rc.AEDUI and len(regions) > 1:
                return 'Aedui Ambush selects at most one Region (§4.4.3).'
        elif timing == 'during':
            step = ability.get('after_step')
            cmd = command['command']
            if cmd == rc.CMD_MARCH:
                from fs_bot.engine.march_interruption import validate_boundary
                validate_boundary(state, faction, dict(command, details=dict(details, sa_after_step=step)))
            elif (type(step) is not int
                    or not any(step == value for _, value in command_steps(command))):
                return 'Place an interrupting Special Ability between completed Command steps.'
            elif cmd in (rc.CMD_RAID, rc.CMD_BATTLE):
                error = _validate_battle_or_raid_boundary(
                    state, faction, dict(details, sa_after_step=step), cmd)
                if error:
                    return error
        elif 'after_step' in ability:
            return 'Only a during-Command ability selects an interruption step.'
        if timing == 'after' and is_borrow_plan(projected):
            return 'Borrowed Warbands must join the Command before it completes.'
    return None


def apply_ability(state, faction, action, request):
    if is_borrow_plan(action):
        timing = (action['details'].get('sa_details') or {}).get('timing_actions')
        ex._timing_window(state, 'special_ability', author=faction, sa=rc.SA_ENLIST,
                          timing_actions=timing)
        begin_borrow(state, action)
        return {'sa': rc.SA_ENLIST, 'executed': False, 'type': 'borrow'}
    with standalone_scope(state):
        return ex._execute_sa(state, faction, action, _human_grant=request)


@contextmanager
def standalone_scope(state):
    """Borrowed Warbands participate in the Belgic Command only (§4.5.1)."""
    borrowed = state.pop(BORROW_KEY, None)
    if borrowed is not None:
        refresh_all_control(state)
    try:
        yield
    finally:
        if borrowed is not None:
            state[BORROW_KEY] = borrowed
            refresh_all_control(state)


def run_command(state, faction, action, steps, at_step):
    """Use one Command's own step and physical cohort tracking throughout."""
    from fs_bot.engine.diviciacus import suspend_command_loan

    cmd = action['command']
    if cmd == rc.CMD_MARCH:
        from fs_bot.engine.march_interruption import pause

        def after_hop(group_number, hop, region, group, arrivals):
            step = {'group': group_number, 'hop': hop}
            if step in steps:
                at_step(step, lambda sa: pause(state, faction, region, group, arrivals, sa))

        return ex._execute_march(state, faction, action, free=True, _with_sa=True,
                                 choose_dropoffs=True, _after_hop=after_hop if steps else None)

    def after_step(step):
        if step in steps:
            at_step(step, lambda sa: suspend_command_loan(state, faction))

    callback = after_step if steps else None
    if cmd == rc.CMD_RECRUIT:
        return ex._execute_recruit(state, faction, action, _exact=True, _after_step=callback)
    if cmd == rc.CMD_RAID:
        return ex._execute_raid(state, faction, action, _after_step=callback, _breakpoints=steps)
    handler = {rc.CMD_BATTLE: ex._execute_battle, rc.CMD_RALLY: ex._execute_rally,
               rc.CMD_SEIZE: ex._execute_seize}[cmd]
    return handler(state, faction, action, _after_step=callback)


def execute(state, faction, request, action):
    if request.get('max_special_abilities') != 2:
        raise CommandError('This Event does not grant two Special Abilities.')
    command = {key: value for key, value in action.items() if key != 'special_abilities'}
    abilities = action['special_abilities']
    projected = [accompanying_action(command, ability) for ability in abilities]
    results = [None, None]
    modifier = next((index for index, plan in enumerate(projected)
                     if plan['sa'] in BATTLE_ABILITIES), None)
    steps = [ability['after_step'] for ability in abilities if 'after_step' in ability]
    borrowed = next((index for index, plan in enumerate(projected) if is_borrow_plan(plan)), None)

    def resolve(index):
        results[index] = apply_ability(state, faction, projected[index], request)

    def at_step(step, scope):
        for index, ability in enumerate(abilities):
            if ability.get('after_step') == step:
                with scope(ability['sa']):
                    resolve(index)

    try:
        for index, ability in enumerate(abilities):
            if ability['sa_timing'] == 'before':
                resolve(index)
        if modifier is not None:
            command = projected[modifier]
        build = next((result for result in results
                      if result and result.get('sa') == rc.SA_BUILD), None)
        command, replacement = ex._reconsider_current_recruit(
            state, faction, command, split=True, grant=request, completed_sa_result=build,
            accompanying_sa=rc.SA_BUILD if any(p['sa'] == rc.SA_BUILD for p in projected) else None)
        result = run_command(state, faction, command, steps, at_step)
        if replacement is not None:
            result['supply_replacement'] = replacement
        ex._after_command_window(state, faction, command, result)
        if borrowed is not None and BORROW_KEY in state:
            results[borrowed]['affected_warbands'] = state[BORROW_KEY]['affected']
            results[borrowed]['executed'] = bool(state[BORROW_KEY]['affected']) and result['executed']
    finally:
        if borrowed is not None and BORROW_KEY in state:
            end_borrow(state)
    if borrowed is not None and results[borrowed] is not None:
        details = projected[borrowed]['details'].get('sa_details') or {}
        tail = details.get('after_sa_timing_actions')
        if result['executed'] or tail is not None:
            ex._timing_window(state, 'special_ability_complete', author=faction, sa=rc.SA_ENLIST,
                              timing_actions=tail)
    if modifier is not None:
        results[modifier] = {'sa': projected[modifier]['sa'],
                             'executed': result['battle_sa_executed']}
    for index, ability in enumerate(abilities):
        if ability['sa_timing'] == 'after' and result['executed']:
            resolve(index)
        if results[index] is None:
            results[index] = {'sa': ability['sa'], 'executed': False,
                              'error': 'The selected Command timing did not resolve.'}
        elif not results[index]['executed'] and not results[index].get('declined_no_effect'):
            if index not in (modifier, borrowed) and not ex._command_executed(results[index]):
                results[index].setdefault('error', results[index].get(
                    'reason', 'The selected Special Ability had no legal effect.'))
        results[index]['sa_timing'] = ability['sa_timing']
    result['special_ability_results'] = results
    return result
