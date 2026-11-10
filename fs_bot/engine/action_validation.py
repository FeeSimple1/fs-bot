"""Shared human-plan constraints from §§2.3.4–2.3.8, 3.1 and 4.1–4.6.

Region eligibility is checked by the executors at the time the SA resolves;
these constraints concern the whole Command and cannot change mid-action.
"""

from fs_bot.rules_consts import (
    BRITANNIA, AEDUI, FACTIONS, FIRST_DID_EVENT, CMD_BATTLE, CMD_MARCH, CMD_RAID,
    CMD_RALLY, CMD_RECRUIT, CMD_SEIZE, SA_AMBUSH, SA_BESIEGE, SA_BUILD,
    SA_DEVASTATE, SA_ENTREAT, SA_ENLIST, SA_RAMPAGE, SA_SCOUT, SA_SUBORN, SA_INTIMIDATE,
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


EVENT_BATTLE_FIELDS = frozenset({
    'no_retreat', 'force_retreat', 'allied_factions', 'warband_full_loss',
})


def human_turn_error(response, options, *, require_plan=True):
    """Validate player-owned turn fields before execution or history recording."""
    from fs_bot.engine.game_engine import ACTION_PASS
    if not isinstance(response, dict):
        return 'A turn response must be an action object.'
    if any(key in response for key in ('assistant_rejected', 'supply_reconsideration')):
        return 'Supply refusal receipts are engine history, not player choices.'
    if 'bot_action' in response:
        return 'Human responses must use player_action, not bot_action.'
    if response.get('action') not in options:
        return "Choose one of this turn's offered actions (§2.3.4)."
    fields = {'action'} if response['action'] == ACTION_PASS else {'action', 'player_action'}
    if set(response) - fields:
        return 'Turn fields are limited to action and its player_action plan. Other fields are engine history.'
    if (require_plan and response['action'] != ACTION_PASS
            and not isinstance(response.get('player_action'), dict)):
        return 'This action needs a player_action plan.'
    return None


def compatible_sa(command, sa):
    return command in SA_COMMANDS.get(sa, {command})


def _march_plan(action):
    details = action.get('details') or {}
    plan = details.get('march_plan') or details
    if not isinstance(plan, dict):
        raise CommandError('The March plan must be an object.')
    return plan


def _region_names(entries):
    # The legacy destination planner also accepts (Region, priority) entries.
    if not isinstance(entries, (list, tuple)):
        raise CommandError('Choose a list of March Regions.')
    regions = [entry[0] if isinstance(entry, (list, tuple)) and entry else entry
               for entry in entries]
    if any(not isinstance(region, str) for region in regions):
        raise CommandError('Choose named March Regions.')
    return regions


def command_regions(action):
    """Selected command Regions, in player order (March: origins)."""
    details = action.get("details") or {}
    if action.get("command") == "Seize":
        return list(action.get("regions") or [])
    if action.get('command') == CMD_MARCH:
        plan = _march_plan(action)
        if 'explicit_moves' in plan:
            moves = plan['explicit_moves']
            if (not isinstance(moves, list) or any(not isinstance(move, dict)
                    or not isinstance(move.get('origin'), str) for move in moves)):
                raise CommandError('Each explicit March move needs a named origin.')
            return list(dict.fromkeys(move['origin'] for move in moves))
        return _region_names(plan.get('origins') or [])
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


def validate_command_parts(action):
    """Only an active split Command may carry two portions."""
    details = action.get('details') or {}
    if 'command_parts' not in details:
        return None
    command = action.get('command')
    if command in (CMD_BATTLE, CMD_MARCH):
        return f'Use one {command} plan with sa_after_step for during timing'
    parts = details['command_parts']
    if (command not in (CMD_RALLY, CMD_RECRUIT, CMD_RAID, CMD_SEIZE)
            or action.get('sa_timing') != 'during'
            or action.get('sa') in (None, '', 'No SA', SA_AMBUSH, SA_BESIEGE)
            or not isinstance(parts, list) or len(parts) != 2
            or any(not isinstance(part, dict) for part in parts)):
        return 'An interrupted Command needs exactly two portions and one Special Ability.'
    if 'sa_after_step' in details or 'sa_after_rally_step' in details:
        return 'Use one ordered Command plan with one interruption.'
    for part in parts:
        part_details = part.get('details') or {}
        if part.get('command') != command:
            return 'Both portions must use the same Command.'
        if (not isinstance(part_details, dict)
                or any(key in part_details for key in ('command_parts', 'sa_after_step',
                                                       'sa_after_rally_step'))
                or part.get('sa') not in (None, '', 'No SA')):
            return 'Use Command portions without nested interruptions or Special Abilities.'
    return None


def battle_target(entry):
    """Read the single defender from either supported Battle entry shape."""
    target = entry.get('target')
    ranked = entry.get('targets') or ()
    return target if target is not None else (ranked[0] if ranked else None)


def validate_region_selections(faction, action):
    """Check unique Seize, Battle, Entreat and Devastate selections (§§3.1, 4.1).

    These plans select one Region per entry. Other plans can encode several
    operations within one selection: Raid flips, Rally options, March groups,
    and Build operations must not be deduplicated as Region selections.
    """
    command = action.get('command')
    if command == CMD_BATTLE:
        entries = (action.get('details') or {}).get('battle_plan', [])
        if (not isinstance(entries, list) or any(not isinstance(entry, dict)
                or not isinstance(entry.get('region'), str) for entry in entries)):
            return 'Supply ordered Battle entries with named Regions.'
        if len({entry['region'] for entry in entries}) != len(entries):
            return 'Select each Battle Region only once (§3.1).'
        for entry in entries:
            if (entry.get('target') is None
                    and not isinstance(entry.get('targets') or (), (list, tuple))):
                return 'Each Battle must name an opposing Faction.'
            target = battle_target(entry)
            if target == faction or target not in FACTIONS:
                return 'Each Battle must name an opposing Faction (§3.2.4).'
    if command == CMD_SEIZE:
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
    sa = action.get('sa')
    if sa in (SA_ENTREAT, SA_DEVASTATE):
        entries = action.get("sa_regions") or []
        if not isinstance(entries, list):
            return f'{sa} Regions must be a list.'
        regions = []
        for entry in entries:
            region = entry.get('region') if sa == SA_ENTREAT and isinstance(entry, dict) else entry
            if not isinstance(region, str):
                return f'Each {sa} entry needs a Region name.'
            regions.append(region)
        if len(regions) != len(set(regions)):
            return f'Select a Region only once for {sa} (§4.1).'
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
    """Check a boundary in a single ordered Command plan (§4.1)."""
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
    if command == CMD_MARCH:
        from fs_bot.engine.march_interruption import validate_boundary
        try:
            validate_boundary(state, faction, action)
        except CommandError as exc:
            return str(exc)
    elif command in (CMD_BATTLE, CMD_RAID):
        error = _validate_battle_or_raid_boundary(state, faction, details, command)
        if error:
            return error
    else:
        return 'This interruption requires an ordered March, Battle, or Raid plan.'
    from fs_bot.engine.execute import _sa_detail
    explicit = {SA_BUILD: 'build_plan', SA_SCOUT: 'scout_plan', SA_SUBORN: 'suborn_plan',
                SA_ENLIST: 'enlist', SA_INTIMIDATE: 'intimidate_plan'}.get(sa)
    if explicit and _sa_detail(action, explicit) is None:
        return f'Supply an explicit {explicit} for the interruption.'
    if sa in (SA_ENTREAT, SA_RAMPAGE) and not any(
            isinstance(entry, dict) for entry in action.get('sa_regions') or []):
        return 'Supply explicit Special Ability targets for the interruption.'
    return None


def _validate_battle_or_raid_boundary(state, faction, details, command):
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
    if command == CMD_RAID:
        from collections import Counter
        from itertools import groupby
        from fs_bot.commands.raid import max_raiders_per_region
        grouped = [region for region, _ in groupby(regions)]
        if len(grouped) != len(set(grouped)):
            return 'Keep all Raid flips for each Region together in the plan.'
        maximum = max_raiders_per_region(state, faction)
        if any(count > maximum for count in Counter(regions).values()):
            return f'Use at most {maximum} Raid flips in each selected Region.'
    return None


def march_scope_error(moves, *, limited=False, with_sa=False):
    """Check the footprint of the March that will be executed."""
    if limited and len({move['origin'] for move in moves}) > 1:
        return 'A Limited Command selects at most one Region (§2.3.5).'
    if with_sa and any(move['path'] and (move['origin'] == BRITANNIA
                       or BRITANNIA in move['path']) for move in moves):
        return 'No Special Ability with March into/out of Britannia (§4.1.3).'
    return None


def _validate_march_plan(state, faction, action, *, limited, with_sa):
    from copy import copy
    from fs_bot.engine.execute import _collect_march_moves

    details = action.get('details') or {}
    plan = _march_plan(action)
    if 'dropoffs' in details or 'dropoffs' in plan:
        return 'Choose ordinary March drop-offs at the live march_dropoff decision.'
    origins = command_regions(action)
    if limited and len(set(origins)) > 1:
        return 'A Limited Command selects at most one Region (§2.3.5).'
    if 'explicit_moves' in plan:
        moves = plan['explicit_moves']
        if any(not isinstance(move.get('path'), list)
               or any(not isinstance(region, str) for region in move['path']) for move in moves):
            return 'Each explicit March move needs a path of Region names.'
        return march_scope_error(moves, limited=limited, with_sa=with_sa)
    extras = plan.get('extra_groups') or []
    if (not isinstance(extras, list) or any(not isinstance(group, dict)
            or group.get('origin') not in origins for group in extras)):
        return 'Extra March groups must use selected origins.'
    if 'sa_after_step' in details or not (limited or with_sa):
        return None  # Ordered interruptions already validated every route.
    if with_sa:
        routes = plan.get('routes') or {}
        # Preserve the declared restriction even if timing changes later make
        # a currently empty origin or unavailable route usable. A stay is not a crossing.
        regions = [origin for origin in origins if routes.get(origin) != []]
        regions.extend(_region_names(plan.get('destinations') or []))
        for path in [*routes.values(), *(group.get('route') or [] for group in extras)]:
            regions.extend(path)
        if BRITANNIA in regions:
            return 'No Special Ability with March into/out of Britannia (§4.1.3).'
    # Legacy destination plans can also pick a Leader's implicit origin.
    # Planning reads the board and only consumes randomness when breaking route ties.
    planning = dict(state, rng=copy(state['rng']))
    moves, _ = _collect_march_moves(planning, faction, action)
    return march_scope_error(moves, limited=limited, with_sa=with_sa)


def validate_human_structure(state, faction, action, *, limited=False, allow_frost=False,
                             action_type=None):
    """Return an error for an illegal whole-action combination, else None."""
    from fs_bot.cli.human_plan import (_FACTION_COMMANDS,
                                       _faction_special_abilities)
    from fs_bot.engine.game_engine import (
        ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND, is_frost,
        is_winter_card,
    )
    if not isinstance(action, dict):
        return "The Command plan must be an object"
    details = action.get("details") or {}
    if not isinstance(details, dict):
        return "Command details must be an object"
    command, sa = action.get('command'), action.get('sa')
    if command == CMD_BATTLE and EVENT_BATTLE_FIELDS.intersection(details):
        return 'The Event supplies Battle modifiers through its own resolution (§5.1.1).'
    has_sa = bool(sa and sa != 'No SA')
    limited = limited or action_type == ACTION_LIMITED_COMMAND
    if action_type not in (None, ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT,
                           ACTION_LIMITED_COMMAND):
        return 'Choose a Command or the current Event for this plan.'
    event = command == FIRST_DID_EVENT
    if ((action_type == ACTION_EVENT and not event)
            or (event and (limited or action_type not in (None, ACTION_EVENT)))):
        return 'The executable plan must match the chosen Command or Event (§2.3.4).'
    if event:
        if has_sa:
            return 'Resolve Special Abilities granted by an Event through that Event (§5.4).'
        if action.get('sa_timing') == 'during':
            return 'Play the Event without Command interruption timing.'
        current = state.get('current_card')
        card_id = details.get('card_id', current)
        if (action_type is not None or current is not None) and (
                current is None or is_winter_card(current)
                or type(card_id) is not type(current) or card_id != current):
            return f'Play the current Event card ({current}), as shown on the board (§2.3.4).'
    if limited and has_sa:
        return 'A Limited Command cannot add a Special Ability (§4.1)'
    if action_type == ACTION_COMMAND and has_sa:
        return 'Choose Command + Special Ability to include a Special Ability (§2.3.4).'
    error = validate_command_parts(action)
    if error:
        return error
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
    error = validate_region_selections(faction, action)
    if error:
        return error
    if sa == SA_ENTREAT:
        from fs_bot.commands.sa_entreat import validate_entreat_ally_target
        for entry in action.get('sa_regions') or []:
            if isinstance(entry, dict) and entry.get('action') in ('replace_ally', 'remove_ally'):
                try:
                    validate_entreat_ally_target(state, entry['region'],
                                                entry.get('target_faction'), entry.get('tribe'))
                except CommandError as exc:
                    return str(exc)
    from fs_bot.commands.sa_build import build_plan_error
    error = build_plan_error(action, state)
    if error:
        return error
    from fs_bot.commands.seize import seize_plan_error
    error = seize_plan_error(action, require_exact=True, state=state)
    if error:
        return error
    if event:
        return None  # The Event's own grants are governed by its text.
    if command not in _FACTION_COMMANDS.get(faction, ()):
        return f"{faction} cannot execute {command}"
    if command == "March" and is_frost(state) and not allow_frost:
        return "No March Command during Frost (§2.3.8)"
    if command == CMD_MARCH:
        try:
            error = _validate_march_plan(state, faction, action, limited=limited, with_sa=has_sa)
        except (ValueError, TypeError, AttributeError, KeyError, IndexError, CommandError) as exc:
            return f'Invalid March plan: {exc}'
        if error:
            return error
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
    parts = command_parts(action)
    # Validate every placement entry before an SA or earlier Region can
    # change the board. Ordered Vercingetorix steps still select one Region.
    placement = command in (CMD_RALLY, CMD_RECRUIT)
    if (limited and command != CMD_MARCH) or placement or len(parts) > 1:
        try:
            regions_by_part = [set(command_regions(part)) for part in parts]
        except (ValueError, TypeError, AttributeError, KeyError, CommandError) as exc:
            return f"Invalid Command plan: {exc}"
        if limited and len(regions_by_part[0]) > 1:
            return "A Limited Command selects at most one Region (§2.3.5)"
        if placement and not any(regions_by_part):
            return "The Command needs at least one placement or Rally option"
        if len(parts) == 2 and regions_by_part[0] & regions_by_part[1]:
            return "Select a Region only once for the Command (§3.1)"
    return None
