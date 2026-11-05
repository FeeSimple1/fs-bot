"""Live zero-to-maximum choices for the three optional expansion effects."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.cards.expansion_up_to import validate_response


def collect_choice(state, faction, request, stdin, stdout):
    card = request['card_id']
    with inspect_board(state, stdout):
        if card == 'A40':
            regions = []
            while len(regions) < request['max_count']:
                region = prompt_choice(stdin, stdout, 'Alpine Tribes: select Regions (-5 Roman Resources each):',
                    [('Finish selecting Regions', None)] +
                    [(r, r) for r in request['legal_regions'] if r not in regions])
                if region is None:
                    break
                regions.append(region)
            response = {'regions': regions}
        elif card == 'A51':
            remaining, entries = request['max_count'], []
            for entry in request['available']:
                if not remaining:
                    break
                ps = entry['piece_state']
                count = prompt_choice(stdin, stdout, f'Siege of Bibrax: how many {ps} Belgic Warbands to remove?',
                    [(str(n), n) for n in range(min(remaining, entry['count']) + 1)])
                if count:
                    entries.append(dict(entry, count=count))
                    remaining -= count
            response = {'removals': entries}
        else:
            available = min(4, request['available_count'])
            count = prompt_choice(stdin, stdout, 'Iccius & Andecomborius: how many Auxilia to place?',
                [(f'{n} Auxilia; +{2 * (4 - n)} Resources for unplaced Auxilia', n)
                 for n in range(available + 1)])
            response = {'count': count}
    return validate_response(state, request, response)
