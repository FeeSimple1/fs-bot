"""Human choices for Morasses' beneficiary and complete free March."""
from fs_bot import rules_consts as rc
from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.cli.human_plan import _pick_regions, _collect_march, _planning_copy
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.cards.morasses import origins


def collect_morasses(state, faction, request, stdin, stdout):
    if request['request_type'] == 'morasses_faction':
        selected = prompt_choice(stdin, stdout, 'Morasses: which Gallic Faction receives the free actions?',
            [(f, f) for f in rc.GALLIC_FACTIONS] + [('Use bot default', None), ('Decline', False)])
        if selected is None or selected is False:
            return {'use_default' if selected is None else 'decline': True}
        return {'faction': selected}
    while True:
        selected = prompt_choice(stdin, stdout, f'{faction}: Morasses free March (including in place).',
            [('Plan the action', 'plan'), ('Use bot default', 'default'), ('Decline', 'decline')])
        if selected != 'plan':
            return {'use_default' if selected == 'default' else 'decline': True}
        planning = _planning_copy(state)
        candidates = origins(planning, faction)
        in_place = (_pick_regions(stdin, stdout, 'March in place in which Regions? (Done for none)', candidates, at_least_one=False)
                    if candidates else [])
        action = None
        with free_action_scope(planning, faction):
            if set(candidates) - set(in_place) and prompt_yes_no(
                    stdin, stdout, 'Also move groups from other origins?', default=False):
                details = _collect_march(planning, faction, stdin, stdout, False, excluded=in_place)
                if details:
                    action = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [],
                              'regions': details['march_plan']['origins'], 'details': details}
        response = {'action': action, 'in_place': in_place}
        error = validate_free_action_response(state, faction, request, response)
        if error:
            stdout.write(f'Cannot use this plan: {error}\n')
            continue
        return response


def collect_morasses_battle(state, faction, request, stdin, stdout):
    from fs_bot.cli.free_actions import collect_free_action
    # Collect one ordinary Battle plan, then select the Event's Ambush Region.
    plain = dict(request, with_sa=False)
    plain.pop('morasses_ambush')
    action = collect_free_action(state, faction, plain, stdin, stdout)
    if action in ({'decline': True}, {'use_default': True}):
        return action
    regions = [e['region'] for e in action['details']['battle_plan']]
    selected = ([prompt_choice(stdin, stdout, 'Aedui Ambush in which one Battle Region?',
                              [(r, r) for r in regions])]
                if faction == rc.AEDUI else regions)
    return dict(action, sa=rc.SA_AMBUSH, sa_regions=selected)
