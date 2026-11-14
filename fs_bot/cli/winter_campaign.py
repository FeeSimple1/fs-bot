"""Human menu for each of card 63/A63's two paid actions."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.human_plan import (_FACTION_COMMANDS, _faction_special_abilities,
                                   _collect_borrowed_command, _collect_command_plan,
                                   _collect_sa_plan)
from fs_bot.rules_consts import SA_ENLIST


def collect_winter_campaign(state, faction, request, stdin, stdout):
    from fs_bot.engine.winter_campaign import validate_human_plan
    remaining = request.get("remaining_actions", 2)
    for error in request.get("errors", []):
        stdout.write(f"Cannot use this plan: {error}\n")
    while True:
        commands = list(_FACTION_COMMANDS.get(faction, ()))
        abilities = list(_faction_special_abilities(faction, state["scenario"]))
        choices = [(f"Command: {cmd}", ("command", cmd)) for cmd in commands]
        choices += [(f"Special Ability: {sa}", ("sa", sa)) for sa in abilities
                    if sa not in ("Ambush", "Besiege")]
        if remaining >= 2 and "Battle" in commands:
            choices += [(f"Battle + {sa} (both actions)", ("battle_sa", sa))
                        for sa in abilities if sa in ("Ambush", "Besiege")]
        if remaining >= 2 and SA_ENLIST in abilities:
            choices.append(("Command + Enlist (both actions)", ("borrow", None)))
        choices.append(("Finish Winter Campaign", ("decline", None)))
        kind, value = prompt_choice(
            stdin, stdout, f"{faction}: Winter Campaign ({remaining} actions left; pay costs)",
            choices)
        if kind == "decline":
            return {"decline": True}
        if kind == "sa":
            action = {"command": None, "regions": [], "sa": "No SA",
                      "sa_regions": [], "details": {}}
            action = _collect_sa_plan(state, faction, action, stdin, stdout,
                                      sa=value, standalone=True, borrow_allowed=False)
        elif kind == "borrow":
            command = prompt_choice(stdin, stdout, "Which Command uses the borrowed Warbands?",
                                    [(cmd, cmd) for cmd in commands])
            action = _collect_borrowed_command(state, faction, command, stdin, stdout)
        else:
            action = _collect_command_plan(
                state, faction, "Battle" if kind == "battle_sa" else value,
                stdin, stdout)
            if action is not None and kind == "battle_sa":
                action = _collect_sa_plan(state, faction, action, stdin, stdout, sa=value)
        if action is None or (kind == "sa" and action.get("sa") == "No SA"):
            stdout.write("No plan selected. Choose another action or finish.\n")
            continue
        try:
            validate_human_plan(state, faction, action, remaining)
        except ValueError as exc:
            stdout.write(f"Cannot use this plan: {exc}\n")
            continue
        return action
