"""Roman selection of a Region for Balearic Slingers pre-fire."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.slingers_choice import validate_response


def collect_slingers(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    options = [(f"{region}: {request['auxilia'][region]} Roman Auxilia; "
                f"attacker {request['attacker']}, defender {request['defenders'][region]}",
                {'region': region}) for region in request['legal_regions']]
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
                                 'Romans: choose the Balearic Slingers Battle Region', options)
    return validate_response(state, request, response)
