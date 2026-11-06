"""Live placement and upgrade options for Oppida (Card Reference 28)."""

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import get_available
from fs_bot.cards.boii import eligible_allies
from fs_bot.map.map_data import is_region_playable


def ally_options(state):
    regions = {rc.TRIBE_TO_REGION[tribe] for tribe in rc.CITY_TO_TRIBE.values()
               if not is_controlled_by(state, rc.TRIBE_TO_REGION[tribe], rc.ROMANS)}
    eligible = {faction: set(eligible_allies(state, regions, faction))
                for faction in rc.GALLIC_FACTIONS if get_available(state, faction, rc.ALLY)}
    return [(city, faction) for city, tribe in rc.CITY_TO_TRIBE.items()
            for faction, tribes in eligible.items() if tribe in tribes]


def upgrade_options(state):
    from fs_bot.cards.card_effects import _tribe_piece_type

    options = {}
    for city, tribe in rc.CITY_TO_TRIBE.items():
        faction = state['tribes'].get(tribe, {}).get('allied_faction')
        if (faction in rc.GALLIC_FACTIONS
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) == faction
                and is_region_playable(state, rc.TRIBE_TO_REGION[tribe], faction)
                and _tribe_piece_type(state, tribe) == rc.ALLY
                and get_available(state, faction, rc.CITADEL)):
            options[city] = faction
    return options
