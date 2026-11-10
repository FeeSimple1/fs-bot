"""Plan one Special Ability at a completed step of an ordered Command."""

from copy import deepcopy
from functools import partial

from fs_bot import rules_consts as rc
from fs_bot.cli import human_plan
from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.engine import action_windows


def _preview_boundary(state, faction, action):
    from fs_bot.engine.execute import _execute_interrupted_command

    class AtBoundary(Exception):
        pass

    def stop(board):
        # Keep the actual board before the executor unwinds its timing scopes.
        raise AtBoundary(human_plan._planning_copy(board))

    preview = human_plan._planning_copy(state)
    try:
        with action_windows.scope(preview, actor=faction, plan=action,
                                  phase='sequence_of_play'):
            _execute_interrupted_command(preview, faction, action, _on_boundary=stop)
    except AtBoundary as pause:
        return pause.args[0]
    return None


def collect_battle(state, faction, stdin, stdout, *, allowed_sas):
    command = human_plan._collect_command_plan(state, faction, rc.CMD_BATTLE, stdin, stdout)
    if command is None:
        return None
    action = deepcopy(command)
    plan = action['details']['battle_plan']
    if len(plan) < 2:
        stdout.write('Only one Battle was selected. Choose the Special Activity after it.\n')
        sim = human_plan._preview_command(state, faction, action)
        action['sa_timing'] = 'after'
    else:
        step = prompt_choice(stdin, stdout, 'Special Activity after which Battle?',
                             [(entry['region'], index)
                              for index, entry in enumerate(plan[:-1], start=1)])
        action['details']['sa_after_step'] = step
        action['sa_timing'] = 'during'

        sim = _preview_boundary(state, faction, action)
        if sim is None:
            stdout.write('The selected Battle cannot resolve before the Special Activity.\n')
            return None
    action = human_plan._collect_sa_plan(sim, faction, action, stdin, stdout,
                                         standalone=True, allowed_sas=allowed_sas,
                                         borrow_allowed=False)
    return command if action['sa'] in (None, 'No SA') else action


def collect_march(state, faction, stdin, stdout, *, allowed_sas):
    from fs_bot.engine.march_interruption import ordered_moves

    planning = dict(state, _cli_march_with_sa=True)
    command = human_plan._collect_command_plan(planning, faction, rc.CMD_MARCH, stdin, stdout)
    if command is None:
        return None
    action = deepcopy(command)
    moves = ordered_moves(action)
    options = []
    for index, move in enumerate(moves, start=1):
        path = move['path']
        for hop, region in enumerate([move['origin'], *path]):
            if index == len(moves) and hop == len(path):
                continue
            label = (f'Group {index} after hop {hop} into {region}' if hop else
                     f'Group {index} in {region} after origin preparation')
            options.append((label, {'group': index, 'hop': hop}))
    if options:
        action['details']['sa_after_step'] = prompt_choice(
            stdin, stdout, 'Special Activity at which March step?', options)
        action['sa_timing'] = 'during'
        sim = _preview_boundary(state, faction, action)
        if sim is None:
            stdout.write('The March cannot reach that step before the Special Activity.\n')
            return None
    else:
        stdout.write('The March has one hide-only origin. Choose the Special Activity after it.\n')
        sim = human_plan._preview_command(state, faction, command)
        action['sa_timing'] = 'after'
    action = human_plan._collect_sa_plan(sim, faction, action, stdin, stdout,
                                         standalone=True, allowed_sas=allowed_sas,
                                         borrow_allowed=False)
    return command if action['sa'] in (None, 'No SA') else action


def collect_raid(state, faction, stdin, stdout, *, allowed_sas):
    from fs_bot.cli.action_windows import inspect_board
    from fs_bot.cli.command_timing import collect_raid as collect_flips
    from fs_bot.engine.diviciacus import suspend_command_loan

    action = {'command': rc.CMD_RAID, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {}}

    def interrupt(sim, step, region):
        nonlocal action
        with inspect_board(sim, stdout):
            if not prompt_yes_no(stdin, stdout, f'Use the Special Activity after this Raid in {region}?',
                                 default=False):
                return False
        with suspend_command_loan(sim, faction):
            candidate = human_plan._collect_sa_plan(
                sim, faction, deepcopy(action), stdin, stdout, standalone=True,
                allowed_sas=allowed_sas, borrow_allowed=False)
            if candidate['sa'] in (None, 'No SA'):
                return False
            human_plan._preview_sa(sim, faction, candidate)
        action = candidate
        action['details']['sa_after_step'] = step
        return True

    command = human_plan._collect_command_plan(
        state, faction, rc.CMD_RAID, stdin, stdout,
        collector=partial(collect_flips, interrupt=interrupt))
    if command is None:
        return None
    details = action['details']
    details.update(command['details'])
    step = details.get('sa_after_step')
    if step == len(details['raid_plan']):
        details.pop('sa_after_step')
        action['sa_timing'] = 'after'
    elif step is not None:
        action['sa_timing'] = 'during'
    return action
