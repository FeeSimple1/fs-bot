"""A66 marker placement and the printed Non-player target restrictions."""
from fs_bot import rules_consts as rc
from fs_bot.map.map_data import get_playable_regions_for_state


def placement_regions(state):
    """A66 permits any Region; Britannia is not one in Ariovistus (A1.3.4)."""
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        return []
    return sorted(get_playable_regions_for_state(state))


def validate_region(state, region):
    if not isinstance(region, str) or region not in placement_regions(state):
        raise ValueError('Winter Uprising requires a playable Region for its marker.')
    return region


def np_regions(state, faction):
    """The NP sheets require Belgica/Germania, and decline before final Winter.

Neither the card nor these instructions require own pieces or Control. Only
the marker is placed now, so future piece-placement priorities are resolved
after Quarters rather than forecast on the current board.
"""
    from fs_bot.engine.game_engine import next_winter_is_final
    if next_winter_is_final(state):
        return []
    area = (rc.BELGICA_REGIONS if faction == rc.BELGAE
            else rc.GERMANIA_REGIONS if faction == rc.GERMANS else ())
    return [region for region in placement_regions(state) if region in area]


def derive_params(state, faction):
    from fs_bot.bots.bot_common import random_select
    regions = np_regions(state, faction)
    return {'region': random_select(state, regions)} if regions else None
