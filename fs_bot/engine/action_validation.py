"""Shared human-plan constraints from §§2.3.8, 4.1 and 4.2–4.6.

Region eligibility is checked by the executors at the time the SA resolves;
these constraints concern the whole Command and cannot change mid-action.
"""

from fs_bot.rules_consts import (
    BRITANNIA, AEDUI, FACTIONS, CMD_BATTLE, CMD_RAID, CMD_SEIZE, SA_AMBUSH,
    SA_BESIEGE, SA_ENTREAT, SA_ENLIST, SA_RAMPAGE, SA_SCOUT, SA_SUBORN, SA_INTIMIDATE,
)
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


def validate_region_uniqueness(action):
    """Reject repeated Seize/Entreat selections (§§3.1, 4.1, 4.3.1).

    These plans select one Region per entry. Other plans can encode several
    operations within one selection: Raid flips, Rally options, March groups,
    and Build operations must not be deduplicated as Region selections.
    """
    if action.get("command") == CMD_SEIZE:
        regions = []
        details = action.get("details") or {}
        if not isinstance(details, dict):
            return "Command details must be an object"
        parts = command_parts(action)
        if not isinstance(parts, list) or any(not isinstance(part, dict) for part in parts):
            return "Command portions must be a list of objects"
        for part in parts:
            selected = part.get("regions") or []
            if not isinstance(selected, list) or any(not isinstance(r, str) for r in selected):
                return "Seize Regions must be a list of Region names"
            regions.extend(selected)
        if len(regions) != len(set(regions)):
            return "Select a Region only once for the Command (§3.1)"
    if action.get("sa") == SA_ENTREAT:
        entries = action.get("sa_regions") or []
        if not isinstance(entries, list):
            return "Entreat Regions must be a list"
        regions = []
        for entry in entries:
            region = entry.get("region") if isinstance(entry, dict) else entry
            if not isinstance(region, str):
                return "Each Entreat entry needs a Region name"
            regions.append(region)
        if len(regions) != len(set(regions)):
            return "Select a Region only once for the Special Ability (§4.1; Entreat §4.3.1)"
    return None


def validate_rally_interruption(state, faction, action):
    """Validate the one SA boundary inside an ordered Vercingetorix Rally.

    Presence and placement legality are checked on the evolving board, not
    here: an earlier step or the intervening SA can change later options.
    """
    from fs_bot.rules_consts import ARVERNI, BASE_SCENARIOS, CMD_RALLY, SA_DEVASTATE, SA_ENTREAT
    details = action.get('details') or {}
    if not isinstance(details, dict) or 'sa_after_rally_step' not in details:
        return None
    if (action.get('command') != CMD_RALLY or faction != ARVERNI
            or state['scenario'] not in BASE_SCENARIOS):
        return "An option-level Special Activity requires a base-game Arverni Rally"
    if 'command_parts' in details:
        return "Use one ordered Rally plan for an option-level Special Activity"
    if action.get('sa_timing') != 'during' or action.get('sa') not in (SA_DEVASTATE, SA_ENTREAT):
        return "An interrupted Rally needs one accompanying Special Activity with during timing"
    plan = details.get('rally_plan')
    if not isinstance(plan, dict) or 'steps' not in plan:
        return "An interrupted Rally needs ordered Rally steps"
    from fs_bot.commands.rally import rally_plan_steps, validate_rally_sequence
    try:
        steps = rally_plan_steps(plan)
        validate_rally_sequence(state, faction, steps)
    except (ValueError, TypeError, AttributeError, KeyError, CommandError) as exc:
        return f"Invalid interrupted Rally: {exc}"
    boundary = details['sa_after_rally_step']
    last_with_tail = (boundary == len(steps)
                      and bool(details.get('after_command_timing_actions')))
    if (type(boundary) is not int or boundary <= 0
            or not (boundary < len(steps) or last_with_tail)):
        return "Place the Special Activity after a Rally step and before the final step"
    return None


def validate_command_interruption(state, faction, action):
    """Check a boundary in a single ordered Battle or Raid plan (§4.1)."""
    details = action.get('details') or {}
    if 'sa_after_step' not in details:
        return None
    command, sa = action.get('command'), action.get('sa')
    from fs_bot.commands.sa_enlist import enlist_details
    enlist = enlist_details(action) if sa == SA_ENLIST else {}
    if (action.get('sa_timing') != 'during' or not isinstance(sa, str)
            or sa in ('No SA', SA_AMBUSH, SA_BESIEGE)
            or not isinstance(enlist, dict) or enlist.get('type') in ('borrow', 'in_battle')):
        return 'Choose one standalone Special Ability for the Command interruption.'
    if 'command_parts' in details or 'sa_after_rally_step' in details:
        return 'Use one ordered Command plan with one interruption.'
    if command not in (CMD_BATTLE, CMD_RAID):
        return 'This interruption requires an ordered Battle or Raid plan.'
    key = 'battle_plan' if command == CMD_BATTLE else 'raid_plan'
    entries = details.get(key)
    if (not isinstance(entries, list) or any(not isinstance(entry, dict)
            or not isinstance(entry.get('region'), str) for entry in entries)):
        return f'Supply ordered {command} entries with named Regions.'
    boundary = details['sa_after_step']
    if type(boundary) is not int or not 0 < boundary < len(entries):
        return 'Place the Special Ability between two Command steps.'
    regions = [entry['region'] for entry in entries]
    from fs_bot.map.map_data import get_playable_regions_for_state
    if set(regions) - set(get_playable_regions_for_state(state, faction)):
        return 'Select playable Command Regions.'
    if command == CMD_BATTLE:
        if len(set(regions)) != len(regions):
            return 'Select each Battle Region only once.'
        for entry in entries:
            target = entry.get('target')
            if target is None and isinstance(entry.get('targets'), list) and entry['targets']:
                target = entry['targets'][0]
            if target == faction or target not in FACTIONS:
                return 'Each Battle must name an opposing Faction.'
    else:
        from collections import Counter
        from itertools import groupby
        from fs_bot.commands.raid import max_raiders_per_region
        grouped = [region for region, _ in groupby(regions)]
        if len(grouped) != len(set(grouped)):
            return 'Keep all Raid flips for each Region together in the plan.'
        maximum = max_raiders_per_region(state, faction)
        if any(count > maximum for count in Counter(regions).values()):
            return f'Use at most {maximum} Raid flips in each selected Region.'
    from fs_bot.engine.execute import _sa_detail
    explicit = {SA_SCOUT: 'scout_plan', SA_SUBORN: 'suborn_plan',
                SA_ENLIST: 'enlist', SA_INTIMIDATE: 'intimidate_plan'}.get(sa)
    if explicit and _sa_detail(action, explicit) is None:
        return f'Supply an explicit {explicit} for the interruption.'
    if sa in (SA_ENTREAT, SA_RAMPAGE) and not any(
            isinstance(entry, dict) for entry in action.get('sa_regions') or []):
        return 'Supply explicit Special Ability targets for the interruption.'
    return None


def validate_human_structure(state, faction, action, *, limited=False, allow_frost=False):
    """Return an error for an illegal whole-action combination, else None."""
    from fs_bot.cli.human_plan import (_FACTION_COMMANDS,
                                       _faction_special_abilities)
    from fs_bot.engine.game_engine import is_frost
    if not isinstance(action, dict):
        return "The Command plan must be an object"
    details = action.get("details") or {}
    if not isinstance(details, dict):
        return "Command details must be an object"
    from fs_bot.commands.sa_intimidate import human_plan_error
    error = human_plan_error(action)
    if error:
        return error
    from fs_bot.commands.sa_trade import validate_trade_plan
    error = validate_trade_plan(action)
    if error:
        return error
    error = validate_rally_interruption(state, faction, action)
    if error:
        return error
    error = validate_command_interruption(state, faction, action)
    if error:
        return error
    error = validate_region_uniqueness(action)
    if error:
        return error
    from fs_bot.commands.sa_build import build_plan_error
    error = build_plan_error(action, state)
    if error:
        return error
    from fs_bot.commands.seize import seize_plan_error
    error = seize_plan_error(action, require_exact=True, state=state)
    if error:
        return error
    command, sa = action.get("command"), action.get("sa")
    if command == "Event":
        return None  # Event-specific/free Commands are governed by their text.
    if command not in _FACTION_COMMANDS.get(faction, ()):
        return f"{faction} cannot execute {command}"
    if command == "March" and is_frost(state) and not allow_frost:
        return "No March Command during Frost (§2.3.8)"
    if command == "March":
        march = details.get("march_plan") or details
        if "dropoffs" in details or (isinstance(march, dict) and "dropoffs" in march):
            return "Choose ordinary March drop-offs at the live march_dropoff decision."
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
    from fs_bot.commands.sa_rampage import human_plan_error as rampage_plan_error
    error = rampage_plan_error(action)
    if error:
        return error
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
    if command in ('Rally', 'Recruit') and not selected_regions:
        return "The Command needs at least one placement or Rally option"
    if len(parts) > 1:
        if command == CMD_BATTLE:
            return "Use one Battle plan with sa_after_step for during timing"
        if command == "March":
            return "Use before/after timing for March; its Command-wide resolution cannot be split"
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
            routes = plan.get("routes") or {}
            # Staying in Britannia does not enter or leave it (§4.1.3).
            regions = [r for r in plan.get("origins") or []
                       if routes.get(r) != []]
            regions.extend(plan.get("destinations") or [])
            for route in (plan.get("routes") or {}).values():
                regions.extend(route)
            for group in plan.get("extra_groups") or []:
                regions.append(group.get("origin"))
                regions.extend(group.get("route") or [])
            if BRITANNIA in regions:
                return "No Special Ability with March into/out of Britannia (§4.1.3)"
    return None
