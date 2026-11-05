"""Choose a physical Citadel, Ally disc or German Settlement for Besiege."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.besiege_choice import validate_response


def collect_besiege(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    options = [(f"{target['piece_type']} at {target['tribe']}" if target['tribe']
                else target['piece_type'], {'target': target})
               for target in request['targets']]
    options.append(('Do not remove a piece with Besiege', {'decline': True}))
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
            f"{faction}: Besiege {request['defender']} in {request['region']}?", options)
    return validate_response(state, request, response)
