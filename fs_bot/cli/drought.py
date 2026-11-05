"""Owner-specific Drought casualty menu with live board inspection."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.cards.drought import validate_response


def collect_loss(state, faction, request, stdin, stdout):
    choices = []
    for target in request['targets']:
        detail = target.get('piece_state') or target.get('tribe') or target.get('leader_name')
        label = target['piece_type'] + (f' ({detail})' if detail else '')
        choices.append((label, target))
    with inspect_board(state, stdout):
        target = prompt_choice(stdin, stdout,
            f"{faction}: choose one Drought casualty in {request['region']}:", choices)
    return validate_response(state, request, {'piece': target})
