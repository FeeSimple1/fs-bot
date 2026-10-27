"""The Province's printed human choice (Card Reference 21; §§5.1–5.1.3)."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available


def unshaded_available(state):
    """The printed benefit requires only Roman pieces in Provincia."""
    return (count_pieces(state, rc.PROVINCIA, rc.ROMANS) > 0
            and all(count_pieces(state, rc.PROVINCIA, faction) == 0
                    for faction in rc.FACTIONS if faction != rc.ROMANS))


def collect_params(state, shaded, stdin, stdout):
    """Offer both alternatives, including their legal partial effects."""
    from fs_bot.cli.menus import prompt_choice
    if shaded:
        # The Arverni choose their scoped Raid/Battle after the placement;
        # no unshaded benefit choice belongs to this side of the Event.
        return {}
    if not unshaded_available(state):
        stdout.write('The Province: the unshaded benefit requires only Roman '
                     'pieces in Provincia.\n')
        return {}
    auxilia = min(5, get_available(state, rc.ROMANS, rc.AUXILIA))
    resources = min(10, rc.MAX_RESOURCES - state['resources'][rc.ROMANS])
    choice = prompt_choice(stdin, stdout, 'The Province: choose the Roman benefit:', [
        (f'Place 5 Auxilia in {rc.PROVINCIA} ({auxilia} Available to place)',
         'auxilia'),
        (f'Add +10 Roman Resources ({resources} gained within the Resource cap)',
         'resources'),
    ])
    return {'province_choice': choice}
