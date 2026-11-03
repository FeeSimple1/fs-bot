"""Explicit human choices for scoped Event-granted Commands and SAs."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.human_plan import (_collect_command, _collect_sa_plan,
                                   _planning_copy)
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import (rally_event_scope,
                                        validate_free_action_response)
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA


def collect_free_action(state, faction, request, stdin, stdout):
    """Collect and dry-run a full plan without changing the live board/RNG."""
    if request.get('request_type') == 'camulogenus_march':
        from fs_bot.cli.camulogenus import collect_march
        return collect_march(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'fixed_event_battle':
        from fs_bot.cli.fixed_event_battles import collect_battle
        return collect_battle(state, faction, request, stdin, stdout)
    if request.get('request_type') in ('gallic_event_beneficiary', 'gallic_command_order'):
        from fs_bot.cli.gallic_event_grants import collect_selection
        return collect_selection(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'remi_event_effect':
        from fs_bot.cli.remi_event_effect import collect_response
        return collect_response(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'named_event_effect':
        from fs_bot.cli.named_event_effects import collect_response
        return collect_response(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'expansion_event_choices':
        from fs_bot.cli.expansion_validation import collect_response
        return collect_response(state, faction, request, stdin, stdout)
    if request.get('request_type') in ('gallia_evacuation', 'gallia_evacuation_order'):
        from fs_bot.cli.gallia_evacuation import collect_evacuation
        return collect_evacuation(state, faction, request, stdin, stdout)
    if request.get("request_type") in ("arduenna_faction", "arduenna_accept"):
        from fs_bot.cli.arduenna import collect_faction
        with inspect_board(state, stdout):
            return collect_faction(state, faction, request, stdin, stdout)
    if request.get("request_type") == "procillus_march":
        from fs_bot.cli.procillus import collect_march
        return collect_march(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'decisive_battle':
        from fs_bot.cli.decisive_battle import collect_battle
        return collect_battle(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'roman_event_accept':
        from fs_bot.cli.roman_event_grants import collect_accept
        return collect_accept(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'roman_event_seize':
        from fs_bot.cli.roman_event_grants import collect_seize
        return collect_seize(state, faction, request, stdin, stdout)
    if request.get('request_type') == 'roman_event_battle':
        from fs_bot.cli.roman_event_grants import collect_battle
        return collect_battle(state, faction, request, stdin, stdout)
    if request.get('request_type') in ('harudes_raid', 'bellovaci_ambush'):
        from fs_bot.cli.harudes_bellovaci import collect_grant
        return collect_grant(state, faction, request, stdin, stdout)
    if request.get("request_type") == "impetuosity_unshaded_march":
        from fs_bot.cli.impetuosity_unshaded import collect_march
        return collect_march(state, faction, request, stdin, stdout)
    if request.get("request_type") == "impetuosity_enemy_battle":
        from fs_bot.cli.impetuosity_unshaded import collect_attacker
        return collect_attacker(state, faction, request, stdin, stdout)
    if request.get("request_type") == "publius_march":
        from fs_bot.cli.publius import collect_publius_march
        return collect_publius_march(state, faction, request, stdin, stdout)
    if request.get("request_type") in ("morasses_faction", "morasses_march"):
        from fs_bot.cli.morasses import collect_morasses
        return collect_morasses(state, faction, request, stdin, stdout)
    if request.get("request_type") == "impetuosity_march":
        from fs_bot.cli.impetuosity import collect_impetuosity_march
        return collect_impetuosity_march(state, faction, request, stdin, stdout)
    if request.get('morasses_ambush'):
        from fs_bot.cli.morasses import collect_morasses_battle
        return collect_morasses_battle(state, faction, request, stdin, stdout)
    actor = request.get("acting_faction", faction)
    message = f"{faction}: Event grants a free action."
    if actor != faction:
        message = f"{faction}: choose a free action using {actor} pieces."
    while True:
        options = [("Plan the action", "plan"), ("Use bot default", "default")]
        if request.get("allow_decline", True):
            options.append(("Decline", "decline"))
        with inspect_board(state, stdout):
            choice = prompt_choice(stdin, stdout, message, options)
        if choice != "plan":
            response = {"use_default" if choice == "default" else "decline": True}
            if request.get('validate_default_response'):
                error = validate_free_action_response(state, faction, request, response)
                if error:
                    stdout.write(f'Cannot use this default: {error}\n')
                    continue
            return response
        planning = _planning_copy(state)
        if request.get('request_type') == 'arduenna_march':
            planning['_cli_arduenna_transit'] = True
        with inspect_board(planning, stdout), free_action_scope(planning, actor), rally_event_scope(
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
            stdout.write("No legal plan selected. Choose another plan.\n")
            continue
        error = validate_free_action_response(state, faction, request, action)
        if error:
            stdout.write(f"Cannot use this plan: {error}\n")
            continue
        return action
