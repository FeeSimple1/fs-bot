"""A20/A58 Roman acceptance and exact Seize choices."""
from fs_bot import rules_consts as rc
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def _cooperation(state, faction, request, stdin, stdout):
    from fs_bot.cli.human_plan import _planning_copy
    from fs_bot.cli.diviciacus import choose_regions, planning_scope
    from fs_bot.cards.roman_event_grants import command_request
    planning = _planning_copy(state)
    planning['_cli_allowed_regions'] = request['allowed_regions']
    selected = choose_regions(planning, faction, 'command', stdin, stdout)
    with planning_scope(planning, faction, selected, 'command'):
        offered = command_request(planning, request['card_id'], request['allowed_commands'][0])
    return selected, offered


def collect_accept(state, faction, request, stdin, stdout):
    benefit = ('remove all Arverni from Veneti, then free Seize there'
               if request['card_id'] == 'A20' else 'free Battle, then free Seize in Belgica')
    choice = prompt_choice(stdin, stdout, f'Romans may {benefit}.',
                           [('Accept the entire benefit', 'accept'),
                            ('Use bot default', 'use_default'), ('Decline', 'decline')])
    return {choice: True}


def collect_seize(state, faction, request, stdin, stdout):
    while True:
        mode = prompt_choice(stdin, stdout, 'Romans: choose the Event Seize.',
                              [('Plan Seize', 'plan'), ('Use bot default', 'default')])
        if mode == 'default':
            response = {'use_default': True}
            error = validate_free_action_response(state, faction, request, response)
            if error:
                stdout.write(f'Cannot use this plan: {error}\n')
                continue
            return response
        cooperation, offered = _cooperation(state, faction, request, stdin, stdout)
        remaining = list(offered['allowed_regions'])
        regions, dispersals = [], {}
        markers = request['available_markers']
        while remaining:
            options = [(r, r) for r in remaining]
            if regions:
                options.append(('Finish Seize selection', None))
            region = prompt_choice(stdin, stdout, 'Select next Seize Region:', options)
            if region is None:
                break
            remaining.remove(region)
            regions.append(region)
            tribes = list(request['dispersible_tribes'][region])
            chosen = []
            while tribes and markers:
                tribe = prompt_choice(stdin, stdout,
                    f'Disperse which Tribe in {region}? ({markers} markers available)',
                    [(t, t) for t in tribes] + [('Finish Dispersal (Forage still occurs)', None)])
                if tribe is None:
                    break
                tribes.remove(tribe)
                chosen.append(tribe)
                markers -= 1
            dispersals[region] = chosen
        action = {'command': rc.CMD_SEIZE, 'regions': regions, 'sa': 'No SA',
                  'sa_regions': [], 'details': {'disperse_tribes': dispersals}}
        if cooperation is not None:
            action['details']['diviciacus_regions'] = cooperation
        error = validate_free_action_response(state, faction, request, action)
        if error:
            stdout.write(f'Cannot use this plan: {error}\n')
            continue
        return action


def collect_battle(state, faction, request, stdin, stdout):
    """A58 permits all Belgica Battle selections, including static Forces."""
    while True:
        mode = prompt_choice(stdin, stdout, 'Romans: choose the Event Battle.',
                              [('Plan Battle', 'plan'), ('Use bot default', 'default')])
        if mode == 'default':
            action = {'use_default': True}
        else:
            cooperation, offered = _cooperation(state, faction, request, stdin, stdout)
            remaining, plan = list(offered['allowed_regions']), []
            while remaining:
                options = [(r, r) for r in remaining]
                if plan:
                    options.append(('Finish Battle selection', None))
                region = prompt_choice(stdin, stdout, 'Select next Battle Region:', options)
                if region is None:
                    break
                remaining.remove(region)
                target = prompt_choice(stdin, stdout, f'Battle whom in {region}?',
                    [(f, f) for f in offered['battle_targets'][region]])
                plan.append({'region': region, 'target': target})
            action = {'command': rc.CMD_BATTLE, 'regions': [p['region'] for p in plan],
                      'sa': 'No SA', 'sa_regions': [], 'details': {'battle_plan': plan}}
            if cooperation is not None:
                action['details']['diviciacus_regions'] = cooperation
        error = validate_free_action_response(state, faction, request, action)
        if error:
            stdout.write(f'Cannot use this plan: {error}\n')
            continue
        return action
