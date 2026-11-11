"""Collect both Assembly of Gaul abilities at their chosen Command stages."""
from copy import deepcopy
from contextlib import nullcontext

from fs_bot.cards import assembly_of_gaul as assembly
from fs_bot.cli import human_plan
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_enlist import BORROW_KEY, end_borrow
from fs_bot.engine import action_windows
from fs_bot.engine.action_validation import compatible_sa
from fs_bot.rules_consts import CMD_MARCH


def _collect_ability(state, faction, command, ability, stdin, stdout):
    scope = nullcontext() if ability['sa'] in assembly.BATTLE_ABILITIES else assembly.standalone_scope(state)
    with scope:
        plan = human_plan._collect_sa_plan(
            state, faction, dict(deepcopy(command), sa_timing=ability['sa_timing']),
            stdin, stdout, sa=ability['sa'], borrow_allowed=ability['sa_timing'] != 'after')
    if plan['sa'] != ability['sa']:
        raise CommandError(f"Choose a legal {ability['sa']} plan.")
    ability['sa_regions'] = plan['sa_regions']
    ability['details'] = {key: value for key, value in plan['details'].items()
                          if key in assembly.ABILITY_DETAILS}
    return assembly.accompanying_action(command, ability)


def collect_pair(state, faction, request, stdin, stdout):
    available = human_plan._faction_special_abilities(faction, state['scenario'])
    choices = {cmd: [sa for sa in available if compatible_sa(cmd, sa)]
               for cmd in request['allowed_commands']}
    with inspect_board(state, stdout):
        cmd = prompt_choice(stdin, stdout, 'Which Command with two Special Activities?',
                            [(cmd, cmd) for cmd, sas in choices.items() if len(sas) >= 2])
        abilities = []
        for label in ('First', 'Second'):
            chosen = {ability['sa'] for ability in abilities}
            sa = prompt_choice(stdin, stdout, f'{label} Special Activity?',
                               [(sa, sa) for sa in choices[cmd] if sa not in chosen])
            timing = ('during' if sa in assembly.BATTLE_ABILITIES else
                      prompt_choice(stdin, stdout, f'When to use {sa}?',
                                    [(when.title(), when) for when in ('before', 'during', 'after')]))
            abilities.append({'sa': sa, 'sa_timing': timing})

    planning = human_plan._planning_copy(state)
    if cmd == CMD_MARCH:
        planning['_cli_march_with_sa'] = True
    empty = {'command': cmd, 'sa': 'No SA', 'sa_regions': [], 'regions': [], 'details': {}}
    try:
        for ability in abilities:
            if ability['sa_timing'] == 'before':
                plan = _collect_ability(planning, faction, empty, ability, stdin, stdout)
                with action_windows.scope(planning, actor=faction, plan=plan, phase='sequence_of_play'):
                    assembly.apply_ability(planning, faction, plan, request)
        command = human_plan._collect_command_plan(planning, faction, cmd, stdin, stdout)
        if command is None:
            return None

        preview_command = command
        for ability in abilities:
            if ability['sa'] in assembly.BATTLE_ABILITIES:
                preview_command = _collect_ability(
                    planning, faction, command, ability, stdin, stdout)
            elif ability['sa_timing'] == 'during':
                steps = assembly.command_steps(command)
                if not steps:
                    raise CommandError('Choose at least two Command steps to place an ability during them.')
                with inspect_board(planning, stdout):
                    ability['after_step'] = prompt_choice(
                        stdin, stdout, f"When during the Command to use {ability['sa']}?", steps)

        def at_step(step, scope):
            for ability in abilities:
                if ability.get('after_step') == step:
                    with scope(ability['sa']):
                        plan = _collect_ability(planning, faction, command, ability, stdin, stdout)
                        assembly.apply_ability(planning, faction, plan, request)

        steps = [ability['after_step'] for ability in abilities if 'after_step' in ability]
        with action_windows.scope(planning, actor=faction, plan=preview_command,
                                  phase='sequence_of_play'):
            result = assembly.run_command(planning, faction, preview_command, steps, at_step)
        if not result['executed'] or result.get('errors'):
            raise CommandError('The selected Command steps could not resolve.')
        if BORROW_KEY in planning:
            end_borrow(planning)
        for ability in abilities:
            if ability['sa_timing'] == 'after':
                plan = _collect_ability(planning, faction, command, ability, stdin, stdout)
                with action_windows.scope(planning, actor=faction, plan=plan, phase='sequence_of_play'):
                    assembly.apply_ability(planning, faction, plan, request)
        return dict(command, special_abilities=abilities)
    except CommandError as exc:
        stdout.write(f'Cannot use this plan: {exc}\n')
        return None
