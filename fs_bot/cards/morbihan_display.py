"""A20's temporary Battle presence is separate from physical board locations.

Morbihan resolves its Ambush with a gathered force and tracks each casualty's
physical origin. While Romans choose their Losses, retain the original
Warband locations in board displays. The live Battle state is never changed by
this read view, and actual Roman losses remain visible between decisions.
"""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot.rules_consts import (
    ARVERNI, WARBAND, HIDDEN, REVEALED, SCOUTED, ARIOVISTUS_SCENARIOS,
)

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
    Counterattack losses and Reveal. Yield a separate survivor ledger so the
    Event can return each surviving counter to its actual origin.
    """
    previous = state.get(PROJECTION_KEY)
    survivors = deepcopy(sources)
    state[PROJECTION_KEY] = {
        'region': region, 'sources': sources, 'survivors': survivors,
    }
    try:
        yield survivors
    finally:
        if previous is None:
            state.pop(PROJECTION_KEY, None)
        else:
            state[PROJECTION_KEY] = previous


def resolve_projected_losses(state, region, faction, num_losses):
    """Resolve only A20's participating Warbands, or return None outside A20.

    A3.2.4 supplies the visibility priority. Owner-adopted provisional PR-09
    supplies the origin tie break: an equal chance for each eligible Region
    on each casualty, irrespective of its remaining number of Warbands. This
    ruling is subject to correction if an authoritative clarification appears.
    Neither the human Event executor nor unrelated local Allies/Citadels
    participate in these casualty choices.
    """
    context = state.get(PROJECTION_KEY)
    if (not context or context['region'] != region or faction != ARVERNI
            or state['scenario'] not in ARIOVISTUS_SCENARIOS):
        return None
    from fs_bot.board.pieces import remove_piece

    survivors = context['survivors']
    result = {'removed': [], 'rolls': [], 'losses_taken': 0,
              'losses_absorbed': 0, 'origin_losses': []}
    remaining = num_losses
    for visibility in (SCOUTED, REVEALED, HIDDEN):
        while remaining > 0:
            origins = sorted(origin for origin, counts in survivors.items()
                             if counts.get(visibility, 0) > 0)
            if not origins:
                break
            origin = (origins[0] if len(origins) == 1
                      else state['rng'].choice(origins))
            remove_piece(state, region, ARVERNI, WARBAND,
                         piece_state=visibility)
            survivors[origin][visibility] -= 1
            remaining -= 1
            result['removed'].append((WARBAND, 1))
            result['origin_losses'].append((origin, visibility, 1))
            result['losses_taken'] += 1
    return result


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
