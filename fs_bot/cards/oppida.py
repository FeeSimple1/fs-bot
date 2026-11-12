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


def np_available(state, faction):
    """§8.2.3: a bot uses its own Allies or Citadels."""
    return (any(owner == faction for _, owner in ally_options(state))
            or faction in upgrade_options(state).values())


def _choose_cities(state, cities, limit):
    from fs_bot.bots.bot_common import random_select_multiple
    return cities if len(cities) <= limit else random_select_multiple(state, cities, limit)


def derive_params(state, faction, shaded):
    """Plan upgrades on the board after the Event's Ally placements."""
    if faction not in rc.GALLIC_FACTIONS:
        return None
    from fs_bot.cards.event_preview import preview_event_prefix

    cities = [city for city, owner in ally_options(state) if owner == faction]
    selected = _choose_cities(state, cities, get_available(state, faction, rc.ALLY))
    placements = [{'tribe': rc.CITY_TO_TRIBE[city], 'faction': faction} for city in selected]
    citadels = get_available(state, faction, rc.CITADEL)
    board = state
    if placements and citadels:
        board = preview_event_prefix(state, faction, 28, shaded, {'ally_placements': placements},
                                     step='28.citadels', index=0)
    upgrades = [city for city, owner in upgrade_options(board).items() if owner == faction]
    upgrades = _choose_cities(state, upgrades, citadels)
    return {'ally_placements': placements, 'citadel_upgrades': upgrades} if placements or upgrades else None
