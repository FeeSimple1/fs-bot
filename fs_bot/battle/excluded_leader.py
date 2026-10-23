"""Kinship's nonparticipating attacker Leader stays physically on the board."""
from contextlib import contextmanager

from fs_bot.rules_consts import LEADER

EXCLUDED_LEADER_KEY = '_battle_excluded_leader'


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


def effective_pieces(state, region, faction, pieces):
    context = state.get(EXCLUDED_LEADER_KEY)
    if context and context['faction'] == faction and region in context['regions']:
        return {key: value for key, value in pieces.items() if key != LEADER}
    return pieces
