"""Explicit human choices for scoped Event-granted Commands and SAs."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.human_plan import (_collect_command, _collect_sa_plan,
                                   _planning_copy)
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import (rally_event_scope,
                                        validate_free_action_response)
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA


def collect_free_action(state, faction, request, stdin, stdout):
    """Collect and dry-run a full plan without changing the live board/RNG."""
    if request.get("request_type") == "impetuosity_march":
        from fs_bot.cli.impetuosity import collect_impetuosity_march
        return collect_impetuosity_march(state, faction, request, stdin, stdout)
    actor = request.get("acting_faction", faction)
    message = f"{faction}: Event grants a free action."
    if actor != faction:
        message = f"{faction}: choose a free action using {actor} pieces."
    while True:
        choice = prompt_choice(
            stdin, stdout, message,
            [("Plan the action", "plan"),
             ("Use bot default", "default"), ("Decline", "decline")])
        if choice != "plan":
            return {"use_default" if choice == "default" else "decline": True}
        planning = _planning_copy(state)
        with free_action_scope(planning, actor), rally_event_scope(
                planning, actor,
                as_if_control=request.get("as_if_control", False),
                allow_devastated=request.get("allow_devastated", False),
                regions=request.get("allowed_regions")):
            if request.get("request_type") == "event_sa":
                action = {"command": None, "regions": [], "sa": "No SA",
                          "sa_regions": [], "details": {}}
                action = _collect_sa_plan(
                    planning, actor, action, stdin, stdout, standalone=True,
                    allowed_sas=request.get("allowed_sas"),
                    allowed_regions=request.get("allowed_regions"))
            else:
                action = _collect_command(
                    planning, actor,
                    ACTION_COMMAND_SA if request.get("with_sa") else ACTION_COMMAND,
                    stdin, stdout, allowed_commands=request.get("allowed_commands"),
                    allowed_regions=request.get("allowed_regions"),
                    max_regions=request.get("max_regions"),
                    required_destinations=request.get("required_destinations"))
        if action is None:
            stdout.write("No legal plan selected. Choose another plan or decline.\n")
            continue
        error = validate_free_action_response(state, faction, request, action)
        if error:
            stdout.write(f"Cannot use this plan: {error}\n")
            continue
        return action
