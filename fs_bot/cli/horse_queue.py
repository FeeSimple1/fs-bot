"""Optional Horse activation at a live prospective Battle."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.horse_queue import validate_response


def collect_window(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    labels = {'activate': 'Use Germanic Horse in this Battle',
              'reserve': 'Save it for a later Battle (one may not occur)',
              'decline': 'Decline Germanic Horse for the rest of this Command'}
    options = [(labels[action], {'action': action}) for action in request['actions']]
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
            f"{faction}: Germanic Horse in {request['region']} "
            f"({request['auxilia']} Auxilia)?", options)
    return validate_response(state, request, response)
