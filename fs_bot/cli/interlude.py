"""Roman Interlude choices with board inspection throughout allocation."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice, prompt_yes_no
from fs_bot.engine.interlude_choices import MARKER, validate_response


def collect_interlude(state, faction, request, stdin, stdout):
    with inspect_board(state, stdout):
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
