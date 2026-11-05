"""Printed optional setup rules, retained independently of ongoing scenario.

Sources: §2.3.8, A Setup Deck Preparation, The Great Revolt Deck.
Absent fields in older saves mean the standard setup was selected.
"""

from fs_bot.rules_consts import SCENARIO_PAX_GALLICA, SCENARIO_GREAT_REVOLT


SETUP_OPTION_HELP = {
    "sudden_frost": "Use Sudden Frost, with all players' agreement at setup",
    "even_initiative": "Balance first-symbol initiative (except Pax Gallica?)",
    "short_great_revolt": "Use the 30-Event, two-Winter Great Revolt deck",
}


def setup_option_values(state):
    """Read saved selections, including standard defaults for older saves."""
    return {key: state.get(key, False) for key in SETUP_OPTION_HELP}


def validate_setup_options(scenario, options):
    """Validate new-game choices before setup consumes RNG or places pieces."""
    for key, value in options.items():
        if type(value) is not bool:
            raise ValueError(f"{key} must be true or false")
    if options["even_initiative"] and scenario == SCENARIO_PAX_GALLICA:
        raise ValueError("Even Initiative is not available in Pax Gallica?")
    if options["short_great_revolt"] and scenario != SCENARIO_GREAT_REVOLT:
        raise ValueError("The short Great Revolt deck requires The Great Revolt")
