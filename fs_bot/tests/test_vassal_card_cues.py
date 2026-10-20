"""NP cues corroborated by faction instructions and physical card faces.

Base §8.2.1/A8.2.1: swords mean No Event; laurels refer to instructions.
A24/A70's transcribed headers disagree with their faction instruction files.
The Vassal 4.0.0 faces corroborate those files; no Event behavior is changed.
"""

from pathlib import Path

import pytest

from fs_bot.bots.bot_common import is_no_faction_event
from fs_bot.cards import card_text
from fs_bot.cards.bot_instructions import (
    NO_EVENT, PLAY_EVENT, SPECIFIC_INSTRUCTION, get_bot_instruction,
)
from fs_bot.cards.card_data import get_card, get_np_symbols
from fs_bot.cli.display import format_card
from fs_bot.rules_consts import (
    AEDUI, BELGAE, GERMANS, ROMANS,
    NP_SYMBOL_LAURELS, NP_SYMBOL_SWORDS,
    SCENARIO_ARIOVISTUS, SCENARIO_PAX_GALLICA,
)


@pytest.mark.parametrize("card_id,symbols,header,briefing", [
    ("A24", {GERMANS: NP_SYMBOL_LAURELS, ROMANS: NP_SYMBOL_SWORDS,
             AEDUI: NP_SYMBOL_SWORDS},
     "A24. Seduni Uprising! Ge L Ro S Be Ae S",
     "NP symbols:    Ger=Laurels, Rom=Swords, Aed=Swords"),
    ("A70", {AEDUI: NP_SYMBOL_LAURELS, GERMANS: NP_SYMBOL_SWORDS,
             ROMANS: NP_SYMBOL_LAURELS},
     "A70. Nervii Be Ae L Ge S Ro L C",
     "NP symbols:    Aed=Laurels, Ger=Swords, Rom=Laurels"),
])
def test_card_briefing_cues_match_faction_event_instructions(
        card_id, symbols, header, briefing):
    assert get_np_symbols(card_id, SCENARIO_ARIOVISTUS) == symbols
    text = card_text.get_card_text(card_id, SCENARIO_ARIOVISTUS)
    assert text.splitlines()[0] == header
    rendered = format_card(card_id, SCENARIO_ARIOVISTUS, include_text=True)
    assert briefing in rendered
    assert header in rendered

    # Header repair must not alter, omit, or summarize either Event effect.
    reference = (Path(card_text._reference_dir()) / "Ariovistus"
                 / "A Card Reference")
    original = card_text._parse_file(
        reference, card_text._HEADER_RE, card_text._card_id)[card_id]
    assert text.partition("\n")[2] == original.partition("\n")[2]


@pytest.mark.parametrize("faction,action", [
    (GERMANS, SPECIFIC_INSTRUCTION), (ROMANS, NO_EVENT),
    (BELGAE, PLAY_EVENT), (AEDUI, NO_EVENT),
])
def test_seduni_bot_decisions_still_follow_instruction_sheet(faction, action):
    # The corrected cues describe existing rules-defined decisions; they
    # must not make Belgae decline or make Romans/Aedui play Seduni.
    instruction = get_bot_instruction("A24", faction, SCENARIO_ARIOVISTUS)
    assert instruction.action == action
    assert is_no_faction_event("A24", faction, SCENARIO_ARIOVISTUS) == (
        action == NO_EVENT)


@pytest.mark.parametrize("faction", [ROMANS, AEDUI])
def test_nervii_laurels_describe_conditional_not_automatic_refusal(faction):
    instruction = get_bot_instruction("A70", faction, SCENARIO_ARIOVISTUS)
    assert instruction.action == SPECIFIC_INSTRUCTION
    assert "If Belgae Non-player" in instruction.instruction
    assert not is_no_faction_event("A70", faction, SCENARIO_ARIOVISTUS)


def test_card_level_carnyx_is_separate_from_np_cues():
    assert not get_card("A24", SCENARIO_ARIOVISTUS).has_carnyx_trigger
    assert get_card("A70", SCENARIO_ARIOVISTUS).has_carnyx_trigger
    assert GERMANS in get_np_symbols("A70", SCENARIO_ARIOVISTUS)
    assert "Arverni carnyx trigger" in format_card(
        "A70", SCENARIO_ARIOVISTUS)


def test_base_cards_with_same_numbers_keep_their_own_cues():
    assert get_np_symbols(24, SCENARIO_PAX_GALLICA)[BELGAE] == NP_SYMBOL_LAURELS
    assert get_np_symbols(70, SCENARIO_PAX_GALLICA) == {
        AEDUI: NP_SYMBOL_LAURELS}
