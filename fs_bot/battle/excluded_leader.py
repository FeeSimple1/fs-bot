"""Event Battle participants, without moving excluded physical counters.

Kinship excludes its attacking Leader; revised Numidians includes only
Auxilia. Control and inventories still read the complete physical board.
"""
from contextlib import contextmanager
from functools import wraps

from fs_bot.rules_consts import LEADER, AUXILIA, HIDDEN, REVEALED, SCOUTED

EXCLUDED_LEADER_KEY = '_battle_excluded_leader'
AUXILIA_ONLY_KEY = '_battle_auxilia_only'


@contextmanager
def without_attacker_leader(state, faction, regions):
    """Exclude the Leader from strength, casualty choices and battle reactions.

    Control and inventories read physical counters. This view lasts through
    the complete Command (including prefire) and is always removed on pause.
    """
    if EXCLUDED_LEADER_KEY in state:
        raise ValueError('A Leader exclusion is already active')
    state[EXCLUDED_LEADER_KEY] = {'faction': faction, 'regions': list(regions)}
    try:
        yield
    finally:
        state.pop(EXCLUDED_LEADER_KEY, None)


@contextmanager
def only_attacker_auxilia(state, faction, region):
    """Revised 11: Auxilia alone Attack and take Counterattack Losses.

    The caller can include the defender's Retreat evaluation in this view;
    the Battle resolver also opens it for direct callers. Restore any outer
    view on interruption, including a pending human decision.
    """
    old = state.get(AUXILIA_ONLY_KEY)
    state[AUXILIA_ONLY_KEY] = {'faction': faction, 'region': region}
    try:
        yield
    finally:
        if old is None:
            state.pop(AUXILIA_ONLY_KEY, None)
        else:
            state[AUXILIA_ONLY_KEY] = old


def auxilia_only_battle(function):
    @wraps(function)
    def wrapped(state, region, attacking_faction, defending_faction, **kwargs):
        if not kwargs.get('auxilia_only_attack'):
            return function(state, region, attacking_faction, defending_faction, **kwargs)
        with only_attacker_auxilia(state, attacking_faction, region):
            return function(state, region, attacking_faction, defending_faction, **kwargs)
    return wrapped


def effective_pieces(state, region, faction, pieces):
    context = state.get(AUXILIA_ONLY_KEY)
    if context and context['faction'] == faction and context['region'] == region:
        # This native-counter view precedes Diviciacus conversion, so any
        # agreed Aedui Warbands still enter as Auxilia with their own owner.
        return {ps: {AUXILIA: pieces.get(ps, {}).get(AUXILIA, 0)}
                for ps in (HIDDEN, REVEALED, SCOUTED)}
    context = state.get(EXCLUDED_LEADER_KEY)
    if context and context['faction'] == faction and region in context['regions']:
        return {key: value for key, value in pieces.items() if key != LEADER}
    return pieces
