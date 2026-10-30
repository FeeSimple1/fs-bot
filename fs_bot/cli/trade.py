"""Human shaded River Commerce choice after Supply declarations (§4.4.1)."""

from fs_bot.cli.menus import prompt_choice


def collect_trade_region(state, faction, request, stdin, stdout):
    """Offer all legal Regions, including lower-yield and zero-yield options."""
    agreement = "agreed" if request['roman_agreed'] else "declined"
    stdout.write(f"\n{faction}: Romans {agreement} to Trade. River Commerce permits at most one Region.\n")
    choices = [(f"{entry['region']} (+{entry['resources_gained']} Resources)",
                {'region': entry['region']}) for entry in request['choices']]
    choices.append(("Call off Trade", {'decline': True}))
    return prompt_choice(stdin, stdout, "Trade in which Region?", choices)
