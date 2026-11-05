"""Live PR-13 use/reserve menus with board inspection."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.capability_queue import validate_response


def collect_window(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    name = 'Balearic Slingers' if request['card_id'] == 13 else 'Germanic Horse'
    labels = {'activate': f'Use {name} in this Battle',
              'reserve': 'Save it for a later Battle (one may not occur)'}
    options = [(labels[action], {'action': action}) for action in request['actions']]
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
            f"{faction}: {name} in {request['region']} "
            f"({request['auxilia']} Roman Auxilia; protected: {request['blocked']})?", options)
    return validate_response(state, request, response)
