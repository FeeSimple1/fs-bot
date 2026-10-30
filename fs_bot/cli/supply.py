"""Human reconsideration after an NPC Aedui Supply refusal (§8.6.6)."""
from copy import deepcopy

from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.human_plan import (
    _SA_NONE, _planning_copy, _collect_command, _collect_sa_plan,
)
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND,
)


def collect_supply_refusal(state, faction, request, stdin, stdout):
    """Replan only the offered action, using its live board and fixed refusal."""
    from fs_bot.engine.supply_reconsideration import SA_DETAILS, validate_response
    action_type = request["action_type"]
    stdout.write("\nThe Aedui refused Supply for this action. That answer remains in force.\n")
    if action_type == "special_ability":
        stdout.write("Choose the remaining Special Activity; completed Command effects stay in place.\n")
    while True:
        options = [("Continue with the original plan", "continue")]
        if action_type == "command":
            options.append(("Choose a different Command plan", "replace"))
            if request.get('frumentum') is not None:
                options.append(("Skip this Frumentum Command", "skip"))
        else:
            options += [("No Special Activity" if sa == _SA_NONE else f"Choose {sa}", sa)
                        for sa in request["allowed_special_abilities"]]
        selected = prompt_choice(stdin, stdout, "How will Rome proceed?", options)
        if selected == "continue":
            response = {"continue": True}
        elif selected == 'skip':
            response = {'replacement': {'skip': request['action']['command']}}
        else:
            planning = _planning_copy(state)
            if action_type == "command":
                abilities = request.get("allowed_special_abilities", [])
                engine_action = (ACTION_LIMITED_COMMAND if request.get("limited") else
                                 ACTION_COMMAND_SA if any(sa != _SA_NONE for sa in abilities)
                                 else ACTION_COMMAND)
                allowed_regions = request.get("allowed_regions")
                if request.get("excluded_regions"):
                    candidates = (planning['spaces'] if allowed_regions is None
                                  else allowed_regions)
                    allowed_regions = [region for region in candidates
                                       if region not in request['excluded_regions']]
                replacement = _collect_command(
                    planning, faction, engine_action, stdin, stdout,
                    allowed_commands=request["allowed_commands"],
                    allowed_regions=allowed_regions,
                    max_regions=request.get("max_regions"),
                    required_destinations=(request.get('grant') or {}).get('required_destinations'),
                    allowed_sas=abilities)
            else:
                replacement = deepcopy(request["action"])
                replacement["sa"] = _SA_NONE
                replacement["sa_regions"] = []
                details = replacement.setdefault("details", {})
                for key in SA_DETAILS:
                    details.pop(key, None)
                if selected != _SA_NONE:
                    replacement = _collect_sa_plan(
                        planning, faction, replacement, stdin, stdout,
                        sa=selected, standalone=True,
                        allowed_sas=request["allowed_special_abilities"],
                        allowed_regions=request.get("allowed_regions"))
            if replacement is None:
                stdout.write("No replacement selected. Choose how to proceed.\n")
                continue
            response = {"replacement": replacement}
        try:
            validate_response(state, request, response)
        except ValueError as exc:
            stdout.write(f"Cannot use this plan: {exc}\n")
            continue
        return response
