"""Printed reference text must stay with its own card and scenario."""

import re

import pytest

from fs_bot.cards import card_text
from fs_bot.cards.card_data import get_ariovistus_event_card_ids
from fs_bot.rules_consts import (
    ALL_SCENARIOS, ARIOVISTUS_SCENARIOS, CARD_NAMES_ARIOVISTUS,
    CARD_NAMES_BASE, CARD_O38, SCENARIO_ARIOVISTUS, SCENARIO_PAX_GALLICA,
    SECOND_EDITION_CARDS,
)


@pytest.mark.parametrize("card_id", CARD_NAMES_BASE)
def test_every_base_card_has_its_own_complete_block(card_id):
    text = card_text.get_card_text(card_id, SCENARIO_PAX_GALLICA)
    headers = re.findall(r"^([A-Z]?\d+C?)\. ", text, flags=re.MULTILINE)
    assert headers == [str(card_id)]
    assert len(text.splitlines()) >= 3


@pytest.mark.parametrize("card_id", get_ariovistus_event_card_ids())
def test_every_expansion_deck_card_has_its_own_complete_block(card_id):
    text = card_text.get_card_text(card_id, SCENARIO_ARIOVISTUS)
    headers = re.findall(r"^([A-Z]?\d+C?)\. ", text, flags=re.MULTILINE)
    assert headers == [str(card_id)]
    assert len(text.splitlines()) >= 3


@pytest.mark.parametrize("card_id", [*CARD_NAMES_ARIOVISTUS, CARD_O38])
def test_every_expansion_reference_identity_is_available(card_id):
    text = card_text.get_card_text(card_id, SCENARIO_ARIOVISTUS)
    assert text.startswith(f"{card_id}. ")


def test_numeric_amendment_does_not_become_part_of_gallia_togata():
    text = card_text.get_card_text("A5")
    assert "already playable area; adds Arverni trigger." in text
    assert "Numidians" not in text
    assert "Potent flankers" not in text


@pytest.mark.parametrize("scenario", ALL_SCENARIOS)
@pytest.mark.parametrize("card_id,amended_phrase,base_phrase", [
    (11, "there with Auxilia, causing double", "there, with Auxilia causing double"),
    (30, "pick 4 Arverni Warbands", "pick 2 Arverni Warbands"),
    (39, "Trade yields Resources regardless", "always\nyield +2 Resources"),
    (44, "Execute a free Command", "They all free Raid"),
    (54, "In the 1st Faction’s Battle", "In the first Battle"),
])
def test_numeric_amendments_match_scenario_effects(
        scenario, card_id, amended_phrase, base_phrase):
    text = card_text.get_card_text(card_id, scenario)
    if scenario in ARIOVISTUS_SCENARIOS:
        assert amended_phrase in text
        assert base_phrase not in text
    else:
        assert base_phrase in text
        assert amended_phrase not in text


@pytest.mark.parametrize("card_id", SECOND_EDITION_CARDS)
def test_default_lookup_retains_base_scenario_text(card_id):
    assert card_text.get_card_text(card_id) == card_text.get_card_text(
        card_id, SCENARIO_PAX_GALLICA)


def test_parser_preserves_carnyx_identity_and_delimits_numeric_amendment(tmp_path):
    reference = tmp_path / "cards"
    reference.write_text(
        "A15C. Legio X\nFirst card.\n\n11. Numidians\nAmended card.\n",
        encoding="utf-8")
    blocks = card_text._parse_file(
        reference, card_text._HEADER_RE, card_text._card_id)
    assert blocks == {
        "A15C": "A15C. Legio X\nFirst card.",
        11: "11. Numidians\nAmended card.",
    }


def test_formatter_preserves_reference_without_inventing_shaded_effect():
    # Cicero is a single-effect Event; it must not gain a second/shaded label.
    text = card_text.get_card_text(1)
    rendered = card_text.format_card_text(1, indent=" | ")
    assert rendered == "\n".join(" | " + line for line in text.splitlines())
    assert "SHADED" not in rendered


def test_formatter_passes_through_scenario():
    rendered = card_text.format_card_text(
        30, indent=" | ", scenario=SCENARIO_ARIOVISTUS)
    assert "pick 4 Arverni Warbands" in rendered
    assert "pick 2 Arverni Warbands" not in rendered


def test_missing_reference_files_and_unknown_cards_remain_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(card_text, "_CACHE", None)
    monkeypatch.setattr(card_text, "_reference_dir", lambda: str(tmp_path))
    assert card_text.get_card_text(11, SCENARIO_ARIOVISTUS) == ""
    assert card_text.format_card_text("unknown") == ""
