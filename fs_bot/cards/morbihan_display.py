"""A20's temporary Battle presence is separate from physical board locations.

Morbihan resolves its Ambush with a gathered force and returns survivors using
the Event's allocation. While Romans choose their Losses, retain the original
Warband locations in board displays. The live Battle state is never changed by
this read view, and actual Roman losses remain visible between decisions.
"""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot.rules_consts import ARVERNI, WARBAND, HIDDEN, REVEALED, SCOUTED

PROJECTION_KEY = '_morbihan_projection'


def snapshot_sources(state, regions):
    from fs_bot.board.pieces import count_pieces_by_state
    return {region: {visibility: count_pieces_by_state(
        state, region, ARVERNI, WARBAND, visibility)
        for visibility in (HIDDEN, REVEALED, SCOUTED)}
        for region in regions}


@contextmanager
def projected_battle(state, region, sources):
    """Expose physical origins only while the synthetic Battle is resolving.

    Arverni are game-run here: every human Loss decision occurs before their
    Counterattack losses and Reveal. The Event's existing return loop, rather
    than this display context, assigns surviving Warbands to physical origins.
    """
    previous = state.get(PROJECTION_KEY)
    state[PROJECTION_KEY] = {'region': region, 'sources': sources}
    try:
        yield
    finally:
        if previous is None:
            state.pop(PROJECTION_KEY, None)
        else:
            state[PROJECTION_KEY] = previous


def physical_view(state):
    """Return a detached display representation, preserving live Roman changes."""
    context = state.get(PROJECTION_KEY)
    if not context:
        return state
    view = dict(state)
    view['spaces'] = dict(state['spaces'])
    for region, counts in context['sources'].items():
        space = deepcopy(state['spaces'][region])
        # This is a presentation-only copy, not a piece operation. Restore
        # just Warbands; retain actual Allies, other factions, and board effects.
        pieces = space.setdefault('pieces', {}).setdefault(ARVERNI, {})
        for visibility, number in counts.items():
            visible = pieces.setdefault(visibility, {})
            if number:
                visible[WARBAND] = number
            else:
                visible.pop(WARBAND, None)
        view['spaces'][region] = space
    # Gathering for "as if there" must not invent physical Control changes.
    # Preserve any other live force context when calculating real Control.
    from fs_bot.board.control import calculate_control
    for region in context['sources']:
        view['spaces'][region]['control'] = calculate_control(view, region)
    return view
