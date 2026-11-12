"""Shaded A26 placements and the German non-player Control restriction."""

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, get_available


REGIONS = (rc.AEDUI_REGION, rc.SEQUANI)
MAX_WARBANDS = 12


def _control_margin(state, region, faction):
    return 2 * count_pieces(state, region, faction) - count_pieces(state, region)


def placement_limit(state, faction, region):
    """Warbands placeable here without breaking a German bot's instruction."""
    if region not in REGIONS:
        return 0
    limit = min(MAX_WARBANDS, get_available(state, rc.ARVERNI, rc.WARBAND))
    if faction == rc.GERMANS and is_controlled_by(state, region, rc.GERMANS):
        # Control requires strictly more pieces than all opposing Forces.
        limit = min(limit, max(0, _control_margin(state, region, rc.GERMANS) - 1))
    return limit


def np_available(state, faction):
    return any(placement_limit(state, faction, region) for region in REGIONS)


def derive_params(state, faction, shaded):
    if not shaded:
        return None
    from fs_bot.bots.bot_common import random_select

    capacity = {region: placement_limit(state, faction, region) for region in REGIONS}
    remaining = min(MAX_WARBANDS, get_available(state, rc.ARVERNI, rc.WARBAND))
    placements = []
    while remaining and any(capacity.values()):
        # Finish the chosen Region before moving on (§8.3.1). Prefer keeping
        # the chooser's Control when the same number can be placed elsewhere.
        scores = {region: (min(remaining, limit),
                          not is_controlled_by(state, region, faction)
                          or min(remaining, limit) < _control_margin(state, region, faction))
                  for region, limit in capacity.items() if limit}
        best = max(scores.values())
        region = random_select(state, [r for r, score in scores.items() if score == best])
        count = best[0]
        placements.append({'region': region, 'count': count})
        remaining -= count
        del capacity[region]
    return {'placements': placements} if placements else None
