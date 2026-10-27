"""A23 meeting choices, from its card text and Ariovistus NP instructions."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, get_leader_in_region
from fs_bot.map.map_data import get_adjacent, is_region_playable


def named_leaders(state):
    locations = []
    for faction, name in ((rc.ROMANS, rc.CAESAR),
                          (rc.GERMANS, rc.ARIOVISTUS_LEADER)):
        region = find_leader(state, faction)
        if region and get_leader_in_region(state, region, faction) != name:
            region = None
        locations.append(region)
    return tuple(locations)


def meeting_choices(state):
    """Every printed legal (destination, moving group) pair, without RNG."""
    caesar, ariovistus = named_leaders(state)
    if not caesar or not ariovistus or caesar == ariovistus:
        return []
    caesar_adj = set(get_adjacent(caesar, state['scenario']))
    ario_adj = set(get_adjacent(ariovistus, state['scenario']))
    if ariovistus in caesar_adj:
        choices = [(ariovistus, 'caesar'), (caesar, 'ariovistus')]
    else:
        choices = [(region, 'both') for region in sorted(caesar_adj & ario_adj)]
    # §5.1.1: Parley does not waive stacking restrictions. In particular,
    # A5 permits Caesar in Cisalpina but forbids Ariovistus's group there.
    return [(region, who) for region, who in choices
            if (who == 'ariovistus' or is_region_playable(state, region, rc.ROMANS))
            and (who == 'caesar' or is_region_playable(state, region, rc.GERMANS))]


def np_choices(state, faction):
    """Apply the Roman/German 'Play only' instructions before selection."""
    choices = meeting_choices(state)
    if faction not in (rc.ROMANS, rc.GERMANS):
        return choices
    caesar, ariovistus = named_leaders(state)
    permitted = []
    for target, who in choices:
        romans = count_pieces(state, target, rc.ROMANS)
        germans = count_pieces(state, target, rc.GERMANS)
        if who in ('caesar', 'both'):
            romans += (1 + count_pieces(state, caesar, rc.ROMANS, rc.LEGION)
                       + count_pieces(state, caesar, rc.ROMANS, rc.AUXILIA))
        if who in ('ariovistus', 'both'):
            germans += 1 + count_pieces(state, ariovistus, rc.GERMANS, rc.WARBAND)
        fort = count_pieces(state, target, rc.ROMANS, rc.FORT) > 0
        if ((faction == rc.ROMANS and fort and romans > germans)
                or (faction == rc.GERMANS and not fort and germans > romans)):
            permitted.append((target, who))
    return permitted


def derive_params(state, faction, shaded=False):
    """No other movement priority is specified: break ties per §8.3.4."""
    from fs_bot.bots.bot_common import random_select
    choices = np_choices(state, faction)
    if not choices:
        return None
    target, who = random_select(state, choices)
    return {'meeting_region': target, 'who_moves': who}


def collect_params(state, stdin, stdout):
    """Offer whole legal meetings, preserving both adjacent alternatives."""
    from fs_bot.cli.menus import prompt_choice
    choices = meeting_choices(state)
    if not choices:
        stdout.write('No legal meeting; Romans and Germans become Ineligible.\n')
        return {}
    names = {'caesar': rc.CAESAR, 'ariovistus': rc.ARIOVISTUS_LEADER,
             'both': 'Both groups'}
    target, who = prompt_choice(stdin, stdout, 'Parley meeting:', [
        (f'{names[who]} to {target}', (target, who)) for target, who in choices])
    return {'meeting_region': target, 'who_moves': who}
