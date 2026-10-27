"""A2.3.2 maps retained base-card initiative and NP cues to German seats."""
from fs_bot import rules_consts as rc
from fs_bot.cards.card_data import get_card
from fs_bot.cli.display import format_card


def test_base_card_in_ariovistus_displays_germans_without_mutating_printed_metadata():
    card = get_card(47, rc.SCENARIO_ARIOVISTUS)
    printed_order, printed_symbols = card.faction_order, dict(card.np_symbols)
    text = format_card(47, rc.SCENARIO_ARIOVISTUS, include_text=True)
    assert 'Faction order: Aed > Ger > Bel > Rom' in text
    symbols = next(line for line in text.splitlines() if 'NP symbols:' in line)
    assert f'Ger={rc.NP_SYMBOL_SWORDS}' in symbols and 'Arv=' not in symbols
    assert card.faction_order == printed_order and card.np_symbols == printed_symbols


def test_base_game_and_expansion_card_displays_keep_their_own_seats():
    base = format_card(47, rc.SCENARIO_GREAT_REVOLT)
    assert 'Faction order: Aed > Arv > Bel > Rom' in base
    assert f'Arv={rc.NP_SYMBOL_SWORDS}' in base and 'Ger=' not in base
    expansion = format_card('A5', rc.SCENARIO_ARIOVISTUS)
    assert 'Faction order: Rom > Ger > Bel > Aed' in expansion
