"""Executor-owned whole-force March for A19 Captured."""
from fs_bot.cli.menus import prompt_choice


def collect_march(state, faction, request, stdin, stdout):
    selected = prompt_choice(stdin, stdout,
        f'{faction}: March all Roman mobile pieces from one Region to adjacent Germans.',
        [(f"{move['origin']} → {move['destination']}", move)
         for move in request['moves']] + [('Use bot default', None)])
    return {'use_default': True} if selected is None else selected
