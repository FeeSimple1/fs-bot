"""Human menu for each of card 63/A63's two paid actions."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.human_plan import (_FACTION_COMMANDS, _faction_special_abilities,
                                   _collect_command_plan, _collect_sa_plan)


def collect_winter_campaign(state, faction, request, stdin, stdout):
    remaining = request.get("remaining_actions", 2)
    while True:
        commands = list(_FACTION_COMMANDS.get(faction, ()))
        abilities = list(_faction_special_abilities(faction, state["scenario"]))
        choices = [(f"Command: {cmd}", ("command", cmd)) for cmd in commands]
        choices += [(f"Special Ability: {sa}", ("sa", sa)) for sa in abilities
                    if sa not in ("Ambush", "Besiege")]
        if remaining >= 2 and "Battle" in commands:
            choices += [(f"Battle + {sa} (both actions)", ("battle_sa", sa))
                        for sa in abilities if sa in ("Ambush", "Besiege")]
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
                                      sa=value, standalone=True)
            if action.get("sa") != "No SA":
                return action
        else:
            action = _collect_command_plan(
                state, faction, "Battle" if kind == "battle_sa" else value,
                stdin, stdout)
            if action is not None:
                if kind == "battle_sa":
                    action = _collect_sa_plan(state, faction, action, stdin, stdout,
                                              sa=value)
                return action
        stdout.write("No plan selected. Choose another action or finish.\n")
