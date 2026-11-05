"""Distribute mandatory first-Harvest Legions among any Belgica Regions."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.harvest_legions import validate_response


def collect_harvest_legions(state, faction, request, stdin, stdout):
    remaining, placements = request['count'], {}
    stdout.write(f"\n{faction}: place all {remaining} Winter Track Legions in Belgica.\n")
    with inspect_board(state, stdout):
        for index, region in enumerate(request['legal_regions']):
            if not remaining:
                break
            count = (remaining if index == len(request['legal_regions']) - 1 else
                     prompt_choice(stdin, stdout, f'How many Legions in {region}?',
                                   [(str(n), n) for n in range(remaining + 1)]))
            if count:
                placements[region] = count
                remaining -= count
    return validate_response(state, request, {'placements': placements})
