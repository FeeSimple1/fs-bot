"""Interlude choices with board inspection throughout allocation."""
from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.engine.interlude_choices import (
    AEDUI_CITADEL, MARKER, SETTLEMENTS, validate_response,
)
from fs_bot.engine import interlude_reductions as reductions


def _collect_reduction(state, request, stdin, stdout):
    stage = request['stage']
    permanent = stage == reductions.PERMANENT
    needed = dict(request['minimums'])
    remaining = [dict(row) for row in request['cohorts']]
    removals = []
    if permanent:
        stdout.write(f"Remove {needed[rc.WARBAND]} German Warbands from play.\n")
    else:
        rules = reductions.STAGE_RULES[stage]
        home = ", ".join(rules["home_regions"])
        stdout.write(f"Return {rules['faction']} pieces to Available. "
                     f"Take {home} last for each type.\n")
    if not prompt_yes_no(stdin, stdout, 'Choose the pieces yourself?', default=True):
        return {'use_default': True}

    while not permanent or needed[rc.WARBAND]:
        choices = []
        if not any(needed.values()):
            choices.append(('Finish selection', None))
        for row in reductions.eligible_cohorts(stage, remaining):
            if row['tribe'] is not None:
                label = f"{row['tribe']} Ally ({row['region']})"
            elif row['region'] is None:
                label = f"Available Warbands ({row['count']})"
            else:
                label = f"{row['region']} {row['piece_state']} Warbands ({row['count']})"
            choices.append((label, row))
        outstanding = ', '.join(f'{n} {kind}' for kind, n in needed.items() if n)
        prompt = f'Select a cohort ({outstanding} still required)' if outstanding else 'Select a cohort'
        row = prompt_choice(stdin, stdout, prompt, choices)
        if row is None:
            break
        kind = row['piece_type']
        limit = min(row['count'], needed[kind]) if permanent else row['count']
        count = 1
        if limit > 1:
            count = prompt_choice(stdin, stdout, 'How many pieces?',
                                  [(str(n), n) for n in range(1, limit + 1)])
        removals.append(dict(row, count=count))
        row['count'] -= count
        needed[kind] = max(0, needed[kind] - count)
    return reductions.validate_response(state, request, {'removals': removals})


def _collect_settlements(state, request, stdin, stdout):
    remaining = dict(request['options'])
    required = request['required_allies']
    stdout.write(f"Choose German Ally placements to replace Settlements ({required} required). "
                 "The other Settlements convert to Warbands as available.\n")
    if not prompt_yes_no(stdin, stdout, 'Choose the Ally placements yourself?', default=True):
        return {'use_default': True}
    allies = {}
    while len(allies) < required:
        region = next(iter(remaining))
        if len(remaining) > required - len(allies):
            region = prompt_choice(stdin, stdout, 'Which Settlement gets an Ally?',
                                   [(name, name) for name in remaining])
        tribes = remaining.pop(region)
        tribe = tribes[0] if len(tribes) == 1 else prompt_choice(
            stdin, stdout, f'Place the Ally at which Tribe in {region}?',
            [(name, name) for name in tribes])
        allies[region] = tribe
    return validate_response(state, request, {'allies': allies})


def collect_interlude(state, faction, request, stdin, stdout):
    with inspect_board(state, stdout):
        if request['kind'] == reductions.KIND:
            return _collect_reduction(state, request, stdin, stdout)
        if request['kind'] == SETTLEMENTS:
            return _collect_settlements(state, request, stdin, stdout)
        if request['kind'] == AEDUI_CITADEL:
            prompt = ('Replace which Aedui Citadel with an Ally?' if request['ally_available']
                      else 'Remove which Aedui Citadel?')
            choices = [(region, region) for region in request['regions']]
            region = prompt_choice(stdin, stdout, prompt, choices + [('Use bot selection', None)])
            response = {'region': region} if region is not None else {'use_default': True}
            return validate_response(state, request, response)
        if request['kind'] == MARKER:
            choices = [('Keep no marker', None)] + [
                (f"{row['tribe']} ({row['status']})", row['tribe']) for row in request['markers']]
            tribe = prompt_choice(stdin, stdout, 'Preserve one marker through Interlude Spring?', choices)
            return validate_response(state, request, {'tribe': tribe})
        stdout.write('\nRomans may conduct the Britannia expedition. Reserve three Legions\n'
                     'for Harvest and send the Leader, at least three other Legions\n'
                     'and at least one Auxilia to Britannia.\n')
        if not request['can_conduct'] or not prompt_yes_no(
                stdin, stdout, 'Conduct the Britannia expedition?', default=False):
            return {'conduct': False}
        remaining = dict(request['legions'])
        harvest, needed = {}, request['harvest_count']
        while needed:
            region = prompt_choice(stdin, stdout, 'Take Harvest Legions from which Region?',
                                   [(r, r) for r, n in remaining.items() if n])
            count = prompt_choice(stdin, stdout, f'How many? ({needed} still required)',
                                  [(str(n), n) for n in range(1, min(remaining[region], needed) + 1)])
            harvest[region] = harvest.get(region, 0) + count
            remaining[region] -= count
            needed -= count
        legions, total = {}, 0
        while True:
            choices = [('Finish Legion selection', None)] if total >= request['minimum_legions'] else []
            choices += [(r, r) for r, n in remaining.items() if n]
            region = prompt_choice(stdin, stdout, 'Send Legions to Britannia from which Region?', choices)
            if region is None:
                break
            count = prompt_choice(stdin, stdout, 'How many Legions?',
                                  [(str(n), n) for n in range(1, remaining[region] + 1)])
            legions[region] = legions.get(region, 0) + count
            remaining[region] -= count
            total += count
        auxilia, used, total = [], {}, 0
        while True:
            choices = [('Finish Auxilia selection', None)] if total >= request['minimum_auxilia'] else []
            for index, row in enumerate(request['auxilia']):
                available = row['count'] - used.get(index, 0)
                if available:
                    choices.append((f"{row['region']} {row['piece_state']} Auxilia ({available})", index))
            index = prompt_choice(stdin, stdout, 'Send Auxilia to Britannia from which cohort?', choices)
            if index is None:
                break
            row = request['auxilia'][index]
            count = prompt_choice(stdin, stdout, 'How many Auxilia?',
                                  [(str(n), n) for n in range(1, row['count'] - used.get(index, 0) + 1)])
            auxilia.append(dict(row, count=count))
            used[index] = used.get(index, 0) + count
            total += count
    return validate_response(state, request, {'conduct': True, 'harvest': harvest,
                                             'legions': legions, 'auxilia': auxilia})
