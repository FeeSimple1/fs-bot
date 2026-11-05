"""Display an Event beneficiary's private future cards without drawing them."""


def show_private_cards(faction, cards, source, stdout):
    stdout.write(f'\n{faction}: private {source} look at the next facedown cards:\n')
    for index, card in enumerate(cards, 1):
        stdout.write(f'  {index}. Card {card["card_id"]}: {card["title"]}\n')
        if card['faction_order']:
            stdout.write('  Faction order: ' + ' > '.join(card['faction_order']) + '\n')
        if card['np_symbols']:
            stdout.write('  NP symbols: ' + ', '.join(
                f'{f}: {symbol}' for f, symbol in card['np_symbols'].items()) + '\n')
        if card['is_winter']:
            stdout.write('  Resolve the Winter Round (§6.0).\n')
        if card['has_carnyx_trigger']:
            stdout.write('  Arverni carnyx trigger: check At War (§A2.3.9).\n')
        if card['text']:
            stdout.write(card['text'] + '\n')
    if not cards:
        stdout.write('  No facedown cards remain.\n')
