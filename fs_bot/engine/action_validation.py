"""Shared human-plan constraints from §§2.3.8, 4.1 and 4.2–4.6.

Region eligibility is checked by the executors at the time the SA resolves;
these constraints concern the whole Command and cannot change mid-action.
"""

from fs_bot.rules_consts import BRITANNIA, AEDUI


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
        plan = details.get("rally_plan") or {}
        entries = [e for key in ("citadels", "allies", "warbands")
                   for e in plan.get(key, [])]
    else:
        key = {"Recruit": "recruit_plan", "Raid": "raid_plan",
               "Battle": "battle_plan"}.get(action.get("command"))
        entries = details.get(key, []) if key else []
    return list(dict.fromkeys(e if isinstance(e, str) else e.get("region")
                             for e in entries))


def command_parts(action):
    return (action.get("details") or {}).get("command_parts") or [action]


def validate_human_structure(state, faction, action):
    """Return an error for an illegal whole-action combination, else None."""
    from fs_bot.cli.human_plan import (_FACTION_COMMANDS,
                                       _faction_special_abilities)
    from fs_bot.engine.game_engine import is_frost
    command, sa = action.get("command"), action.get("sa")
    if command == "Event":
        return None  # Event-specific/free Commands are governed by their text.
    if command not in _FACTION_COMMANDS.get(faction, ()):
        return f"{faction} cannot execute {command}"
    if command == "March" and is_frost(state):
        return "No March Command during Frost (§2.3.8)"
    has_sa = sa and sa != "No SA"
    if has_sa:
        if sa not in _faction_special_abilities(faction, state["scenario"]):
            return f"{faction} cannot execute {sa} in this scenario"
        if not compatible_sa(command, sa):
            return f"{sa} cannot accompany {command} (§4)"
        if sa == "Ambush" and faction == AEDUI and len(set(action.get("sa_regions") or [])) > 1:
            return "Aedui Ambush is limited to one Region (§4.4.3)"
    parts = command_parts(action)
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
