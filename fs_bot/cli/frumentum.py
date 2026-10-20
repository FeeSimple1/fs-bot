"""A53's Aedui funding decision and Roman paid action sequence."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.human_plan import (_planning_copy, _collect_command_plan,
                                   _collect_sa_plan)
from fs_bot.engine.frumentum import ACTION_SA, spending_scope, validate_response
from fs_bot.rules_consts import AEDUI, ROMANS


def collect_frumentum(state, faction, request, stdin, stdout):
    for error in request.get("errors", []):
        stdout.write(f"Cannot use this plan: {error}\n")
    if request["kind"] == "frumentum_amount":
        maximum = state["resources"].get(AEDUI, 0)
        amount = prompt_choice(
            stdin, stdout, "Frumentum: how many Aedui Resources fund the Roman actions?",
            [(str(n), n) for n in range(maximum + 1)] + [("Use bot default", None)])
        return {"amount": amount} if amount is not None else {"use_default": True}
    while True:
        remaining = request["remaining_actions"]
        stdout.write(f"Frumentum: {request['remaining_resources']} Aedui Resources remain; "
                     f"the {request['reserved_roman_resources']} Roman Resources are reserved.\n")
        choices = [(f"Command: {c}", c) for c in ("Recruit", "March") if c in remaining]
        if ACTION_SA in remaining:
            choices += [(f"Special Ability: {sa}", sa) for sa in ("Build", "Scout")]
        choices += [(f"Skip {kind}", ("skip", kind)) for kind in remaining]
        choices += [("Use bot default for the next action", "default"),
                    ("Finish Frumentum", "decline")]
        selected = prompt_choice(stdin, stdout, "Which paid action next? (any order)", choices)
        if selected == "default":
            return {"use_default": True}
        if selected == "decline":
            return {"decline": True}
        if isinstance(selected, tuple):
            return {"skip": selected[1]}
        planning = _planning_copy(state)
        with spending_scope(planning, request["remaining_resources"]):
            if selected in ("Recruit", "March"):
                action = _collect_command_plan(planning, ROMANS, selected, stdin, stdout)
            else:
                action = _collect_sa_plan(
                    planning, ROMANS, {"command": None, "regions": [], "sa": "No SA",
                                       "sa_regions": [], "details": {}}, stdin, stdout,
                    sa=selected, standalone=True)
        if action is None:
            stdout.write("No plan selected. Choose another action or finish.\n")
            continue
        try:
            validate_response(state, request, action)
        except ValueError as exc:
            stdout.write(f"Cannot use this plan: {exc}\n")
            continue
        return action
