"""Saved selection of the five optional Second Edition card replacements.

A Setup, Deck Preparation recommends cards 11/30/39/44/54 for every
scenario; A1.2.1 distinguishes these from the A-prefix expansion cards.
This choice changes those five cards only, never the scenario's faction
roles, map, deck replacements, or optional Diviciacus card.

``legacy`` retains the pre-selector behavior: revised cards during an
Ariovistus scenario, original cards during a base scenario. Missing fields
in old saves also mean legacy. Explicit choices survive the Interlude.
"""

from collections.abc import Mapping

from fs_bot.rules_consts import ARIOVISTUS_SCENARIOS


CARD_EDITIONS = ("legacy", "original", "second-edition")


def validate_card_edition(value):
    """Return a supported profile, rejecting typos instead of guessing."""
    if value not in CARD_EDITIONS:
        raise ValueError(f"Unknown card edition: {value!r}; expected "
                         + ", ".join(CARD_EDITIONS))
    return value


def uses_second_edition(state_or_scenario=None, card_edition=None):
    """Whether the five numeric replacement cards use their revised text."""
    if isinstance(state_or_scenario, Mapping):
        scenario = state_or_scenario.get("scenario")
        if card_edition is None:
            card_edition = state_or_scenario.get("card_edition", "legacy")
    else:
        scenario = state_or_scenario
    profile = validate_card_edition(
        "legacy" if card_edition is None else card_edition)
    return (profile == "second-edition"
            or (profile == "legacy" and scenario in ARIOVISTUS_SCENARIOS))


def card_edition_label(state):
    """Human-readable profile plus its effective five-card selection."""
    profile = state.get("card_edition", "legacy")
    revised = uses_second_edition(state)
    effective = "Second Edition replacements" if revised else "original cards"
    if profile == "legacy":
        return f"legacy scenario default ({effective})"
    return effective
