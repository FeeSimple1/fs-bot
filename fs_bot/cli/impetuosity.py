"""Card 72: choose the one Hidden-Warband group allowed to March."""

from fs_bot.cli.menus import prompt_choice


def collect_impetuosity_march(state, faction, request, stdin, stdout):
    """Offer legal origins, adjacent/in-place destinations, and group size.

    Selection does not move, Reveal, or roll for any pieces. The engine
    resolves this March before asking about the optional Battle.
    """
    from fs_bot.cards.impetuosity import march_choices

    while True:
        choice = prompt_choice(
            stdin, stdout,
            f"{faction}: Impetuosity permits one Hidden-Warband group to March (no Leader).",
            [("Plan the action", "plan"), ("Use bot default", "default"),
             ("Decline", "decline")])
        if choice != "plan":
            return {"use_default" if choice == "default" else "decline": True}
        choices = march_choices(state, faction)
        if not choices:
            stdout.write("No Hidden-Warband group can March. Choose another option.\n")
            continue
        origins = sorted({entry["origin"] for entry in choices})
        origin = prompt_choice(stdin, stdout, "March from which Region?",
                               [(region, region) for region in origins])
        destinations = sorted(
            [entry for entry in choices if entry["origin"] == origin],
            key=lambda entry: entry["destination"])
        selected = prompt_choice(
            stdin, stdout, "March to which Region? (The origin is also allowed.)",
            [(entry["destination"], entry) for entry in destinations])
        count = prompt_choice(
            stdin, stdout, "How many Hidden Warbands March?",
            [(str(number), number) for number in range(1, selected["maximum"] + 1)])
        return {"origin": origin, "destination": selected["destination"],
                "warbands": count}
