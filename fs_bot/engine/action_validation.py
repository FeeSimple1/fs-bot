"""Shared human-plan constraints from §§2.3.8, 4.1 and 4.2–4.6.

Region eligibility is checked by the executors at the time the SA resolves;
these constraints concern the whole Command and cannot change mid-action.
"""

from fs_bot.rules_consts import BRITANNIA, AEDUI
from fs_bot.commands.common import CommandError


SA_COMMANDS = {
    "Build": {"Recruit", "March", "Seize"},
    "Suborn": {"Rally", "March", "Raid"},
    "Rampage": {"Rally", "Raid", "Battle"},
    "Settle": {"Rally", "March"},
    "Intimidate": {"March", "Raid", "Battle"},
    "Ambush": {"Battle"},
    "Besiege": {"Battle"},
}


def compatible_sa(command, sa):
    return command in SA_COMMANDS.get(sa, {command})


def command_regions(action):
    """Selected command Regions, in player order (March: origins)."""
    details = action.get("details") or {}
    if action.get("command") == "Seize":
        return list(action.get("regions") or [])
    if action.get("command") == "March":
        plan = details.get("march_plan") or details
        return list(plan.get("origins") or [])
    if action.get("command") == "Rally":
        from fs_bot.commands.rally import rally_plan_steps
        entries = rally_plan_steps(details.get("rally_plan", {}))
    elif action.get("command") == "Recruit":
        from fs_bot.commands.rally import recruit_plan_entries
        entries = recruit_plan_entries(details.get("recruit_plan", []))
    else:
        key = {"Raid": "raid_plan", "Battle": "battle_plan"}.get(action.get("command"))
        entries = details.get(key, []) if key else []
    return list(dict.fromkeys(e if isinstance(e, str) else e.get("region")
                             for e in entries))


def command_parts(action):
    return (action.get("details") or {}).get("command_parts") or [action]


def validate_human_structure(state, faction, action, *, limited=False):
    """Return an error for an illegal whole-action combination, else None."""
    from fs_bot.cli.human_plan import (_FACTION_COMMANDS,
                                       _faction_special_abilities)
    from fs_bot.engine.game_engine import is_frost
    if not isinstance(action, dict):
        return "The Command plan must be an object"
    command, sa = action.get("command"), action.get("sa")
    if command == "Event":
        return None  # Event-specific/free Commands are governed by their text.
    if command not in _FACTION_COMMANDS.get(faction, ()):
        return f"{faction} cannot execute {command}"
    if command == "March" and is_frost(state):
        return "No March Command during Frost (§2.3.8)"
    has_sa = sa and sa != "No SA"
    if limited and has_sa:
        return "A Limited Command cannot add a Special Ability (§4.1)"
    if has_sa:
        if sa not in _faction_special_abilities(faction, state["scenario"]):
            return f"{faction} cannot execute {sa} in this scenario"
        if not compatible_sa(command, sa):
            return f"{sa} cannot accompany {command} (§4)"
        if sa == "Ambush" and faction == AEDUI and len(set(action.get("sa_regions") or [])) > 1:
            return "Aedui Ambush is limited to one Region (§4.4.3)"
    details = action.get("details") or {}
    if not isinstance(details, dict):
        return "Command details must be an object"
    if ("command_parts" in details
            and not isinstance(details["command_parts"], list)):
        return "Command portions must be a list"
    parts = command_parts(action)
    if any(not isinstance(part, dict) for part in parts):
        return "Each Command portion must be an object"
    # Validate every placement entry before an SA or earlier Region can
    # change the board. Ordered Vercingetorix steps still select one Region.
    selected_regions = []
    if limited or command in ("Rally", "Recruit"):
        try:
            for part in parts:
                selected_regions.extend(command_regions(part))
        except (ValueError, TypeError, AttributeError, KeyError, CommandError) as exc:
            return f"Invalid Command plan: {exc}"
    if limited and len(set(selected_regions)) > 1:
        return "A Limited Command selects at most one Region (§2.3.5)"
    if len(parts) > 1:
        if command in ("March", "Battle"):
            return "Use before/after timing for March or Battle; their Command-wide resolution cannot be split"
        if action.get("sa_timing") != "during" or len(parts) != 2:
            return "An interrupted Command needs exactly two portions and one SA"
        selected = set()
        for part in parts:
            if part.get("command") != command:
                return "Both portions must use the same Command"
            regions = set(command_regions(part))
            if regions & selected:
                return "Select a Region only once for the Command (§3.1)"
            selected.update(regions)
    if has_sa and command == "March":
        for part in parts:
            details = part.get("details") or {}
            plan = details.get("march_plan") or details
            regions = list(plan.get("origins") or [])
            regions.extend(plan.get("destinations") or [])
            for route in (plan.get("routes") or {}).values():
                regions.extend(route)
            for group in plan.get("extra_groups") or []:
                regions.append(group.get("origin"))
                regions.extend(group.get("route") or [])
            if BRITANNIA in regions:
                return "No Special Ability with March into/out of Britannia (§4.1.3)"
    return None
