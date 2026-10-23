"""Explicit, scoped choices for Event-granted Commands and Special Abilities.

An agent returns a complete ordinary action, ``{'decline': True}``, or
``{'use_default': True}``. Validation simulates on an isolated board and RNG;
neither malformed plans nor out-of-scope choices can partially apply an Event.
An engine-owned ``acting_faction`` may name a different physical force from
the consulted chooser (A34); response data cannot override that grant.
"""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot.commands.common import CommandError, free_action_scope
from fs_bot.board.pieces import PieceError


@contextmanager
def rally_event_scope(state, faction, *, as_if_control=False,
                      allow_devastated=False, regions=None):
    missing = object()
    previous = state.get('_rally_event_grant', missing)
    state['_rally_event_grant'] = {
        'faction': faction, 'as_if_control': as_if_control,
        'allow_devastated': allow_devastated, 'regions': regions,
    }
    try:
        yield
    finally:
        if previous is missing:
            state.pop('_rally_event_grant', None)
        else:
            state['_rally_event_grant'] = previous


def command_options(faction):
    from fs_bot.rules_consts import ROMANS, ROMAN_COMMANDS, GALLIC_COMMANDS
    return list(ROMAN_COMMANDS if faction == ROMANS else GALLIC_COMMANDS)


def _sa_regions(action):
    """Every selected SA Region, including implicit plan entries (Scout origins)."""
    regions = []
    def add(entry):
        region = entry if isinstance(entry, str) else entry.get('region')
        if region is not None:
            regions.append(region)
    for entry in action.get('sa_regions') or []:
        add(entry)
    details = action.get('details') or {}
    merged = dict(details.get('sa_details') or {})
    merged.update(details)
    for key in ('suborn_plan', 'entreat_plan', 'intimidate_plan', 'rampage_plan'):
        for entry in merged.get(key) or []:
            add(entry)
    for entries in (merged.get('build_plan') or {}).values():
        for entry in entries or []:
            add(entry)
    scout = merged.get('scout_plan') or {}
    regions.extend(e.get('from_region') for e in scout.get('auxilia_moves') or [])
    regions.extend(e.get('region') for e in scout.get('scout_targets') or [])
    enlist = merged.get('enlist') or {}
    if enlist.get('region') is not None:
        regions.append(enlist['region'])
    # Borrowed forces may affect several Regions; a free German March
    # selects its origin. Its destination may lie outside the SA Region
    # (§4.5.1 / §5.4), so do not treat that destination as selected.
    regions.extend(enlist.get('regions') or [])
    if enlist.get('origin') is not None:
        regions.append(enlist['origin'])
    return regions


def _result_error(result):
    if isinstance(result, dict):
        if result.get('error'):
            return str(result['error'])
        if result.get('errors'):
            return str(result['errors'][0])
        for value in result.values():
            error = _result_error(value)
            if error:
                return error
    elif isinstance(result, list):
        for value in result:
            error = _result_error(value)
            if error:
                return error
    return None


def execute_free_action_plan(state, faction, request, action):
    """Execute a validated concrete plan, retaining its human SA timing."""
    from fs_bot.engine import execute as ex
    from fs_bot.rules_consts import CMD_BATTLE
    # The request is an engine-owned grant. Responses cannot change its actor.
    faction = request.get('acting_faction', faction)
    with free_action_scope(state, faction), rally_event_scope(
            state, faction, as_if_control=request.get('as_if_control', False),
            allow_devastated=request.get('allow_devastated', False),
            regions=request.get('allowed_regions')):
        if request.get('request_type') == 'event_sa':
            sa = action['sa']
            handlers = {'Build': ex._execute_build, 'Scout': ex._execute_scout,
                        'Suborn': ex._execute_suborn, 'Entreat': ex._execute_entreat,
                        'Devastate': ex._execute_devastate,
                        'Rampage': ex._execute_rampage, 'Enlist': ex._execute_enlist,
                        'Settle': ex._execute_settle, 'Intimidate': ex._execute_intimidate}
            if sa == 'Intimidate':
                return ex._execute_intimidate(
                    state, faction, action,
                    ignore_selection=request.get('intimidate_anywhere', False))
            if sa == 'Trade':
                return ex._execute_trade(state, faction,
                                         allowed_regions=request.get('allowed_regions'))
            return handlers[sa](state, faction, action)
        if request.get('morasses_ambush') and action.get('command') == CMD_BATTLE:
            return ex._execute_battle(state, faction, action, _ambush_anywhere=True)
        if request.get('double_auxilia') and action.get('command') == CMD_BATTLE:
            # Card 6's bonus belongs to the engine-owned grant, never the
            # submitted plan. Validation executes this same path on a copy.
            return ex._execute_battle(state, faction, action, _double_auxilia=True)
        return ex._execute_bot_command(state, faction, action,
                                       with_sa=request.get('with_sa', False))


def validate_free_action_response(state, faction, request, response):
    """Return a useful validation error, or None for a legal explicit response."""
    if not isinstance(response, dict):
        return 'Return a full action, decline, or use_default.'
    if request.get('request_type') == 'impetuosity_enemy_battle':
        if response == {'use_default': True}:
            return None
        if set(response) != {'attacker'} or response['attacker'] not in request['attackers']:
            return 'Choose one of the available Arverni or Belgic attackers.'
        return None
    if request.get('request_type') == 'impetuosity_unshaded_march' and response == {'decline': True}:
        from fs_bot.cards.impetuosity_unshaded import origins_by_destination
        if origins_by_destination(state, faction):
            return 'Impetuosity requires an adjacent March when one is possible.'
    if response == {'decline': True} and not request.get('allow_decline', True):
        return 'This follow-on action must be carried out when possible.'
    if response == {'decline': True} or response == {'use_default': True}:
        return None
    try:
        if request.get("request_type") == "impetuosity_unshaded_march":
            from fs_bot.cards.impetuosity_unshaded import validate_march
            validate_march(state, faction, response)
            return None
        if request.get("request_type") == "publius_march":
            from fs_bot.cards.publius import validate_march
            validate_march(state, response)
            return None
        if request.get("request_type") in ("morasses_faction", "morasses_march"):
            from fs_bot.cards.morasses import validate_faction, validate_march
            validator = validate_faction if request['request_type'] == 'morasses_faction' else validate_march
            validator(state, faction, response)
            return None
        if request.get("request_type") == "impetuosity_march":
            from fs_bot.cards.impetuosity import validate_march
            validate_march(state, faction, response)
            return None
        return _validate_plan(state, faction, request, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, CommandError, PieceError) as exc:
        return f'Invalid free action: {exc}'


def _validate_plan(state, faction, request, action):
    from fs_bot.cli.human_plan import _faction_special_abilities
    from fs_bot.engine.action_validation import command_regions, command_parts, compatible_sa
    from fs_bot.map.map_data import get_playable_regions_for_state
    faction = request.get('acting_faction', faction)
    standalone = request.get('request_type') == 'event_sa'
    cmd, sa = action.get('command'), action.get('sa', 'No SA')
    if standalone:
        if cmd is not None:
            return 'This grant permits only a Special Ability.'
        if request.get('allowed_sas') is not None and sa not in request['allowed_sas']:
            return 'That Special Ability is not granted by this Event.'
        if not sa or sa in ('No SA', 'Ambush', 'Besiege'):
            return 'Choose a standalone Special Ability (no Ambush or Besiege).'
    elif cmd not in request.get('allowed_commands', command_options(faction)):
        return 'That Command is not granted by this Event.'
    if cmd is not None and cmd not in command_options(faction):
        return f'{faction} cannot execute {cmd}.'
    if sa and sa != 'No SA':
        if not standalone and not request.get('with_sa'):
            return 'This Event grants a Command without a Special Ability.'
        if sa not in _faction_special_abilities(faction, state['scenario']):
            return f'{faction} cannot execute {sa}.'
        if not standalone and not compatible_sa(cmd, sa):
            return f'{sa} cannot accompany {cmd}.'
    if request.get('morasses_ambush'):
        from fs_bot.rules_consts import AEDUI, SA_AMBUSH
        plan = (action.get('details') or {}).get('battle_plan') or []
        battle_regions = {e.get('region') for e in plan}
        ambush_regions = action.get('sa_regions') or []
        if (sa != SA_AMBUSH or not ambush_regions
                or any(not isinstance(r, str) for r in ambush_regions)
                or len(ambush_regions) != len(set(ambush_regions))
                or not set(ambush_regions).issubset(battle_regions)):
            return 'Morasses needs explicit Ambush Regions within the Battle Command.'
        if faction == AEDUI and len(ambush_regions) != 1:
            return 'Aedui Ambush still selects at most one Region (§4.4.3).'
        if faction != AEDUI and set(ambush_regions) != battle_regions:
            return 'The Morasses grant adds Ambush to each selected Battle Region.'
    parts = command_parts(action)
    if len(parts) > 1:
        if cmd in ('March', 'Battle') or action.get('sa_timing') != 'during' or len(parts) != 2:
            return 'Invalid interrupted Command.'
        if any(part.get('command') != cmd for part in parts):
            return 'Both portions must use the same Command.'
    selected = []
    for part in parts:
        if cmd == 'Battle':
            entries = (part.get('details') or {}).get('battle_plan') or []
            battle_regions = [entry.get('region') for entry in entries]
            if len(battle_regions) != len(set(battle_regions)):
                return 'Select each Battle Region only once.'
        selected.extend(command_regions(part))
        if cmd == 'March':
            details = part.get('details') or {}
            plan = details.get('march_plan') or details
            selected.extend(e.get('origin') for e in plan.get('extra_groups') or [])
            # Expansion plans may implicitly select the Leader's origin.
            # Scope the moves the executor will actually make, not only the
            # caller's declared origin list; derive on a copy for RNG safety.
            from fs_bot.engine.execute import _collect_march_moves
            planning = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
            moves, _ = _collect_march_moves(planning, faction, part)
            selected.extend(move['origin'] for move in moves)
    if len(parts) > 1 and len(selected) != len(set(selected)):
        return 'Select each Command Region only once.'
    playable = set(get_playable_regions_for_state(state, faction))
    if any(r not in playable for r in selected):
        return 'Select playable Command Regions.'
    allowed = request.get('allowed_regions')
    if allowed is not None and not set(selected).issubset(allowed):
        return 'Command plan leaves the Regions granted by this Event.'
    if request.get('max_regions') is not None and len(set(selected)) > request['max_regions']:
        return f"Select at most {request['max_regions']} Command Region(s)."
    sa_regions = _sa_regions(action)
    if any(r not in playable for r in sa_regions):
        return 'Select playable Special Ability Regions.'
    if allowed is not None and not set(sa_regions).issubset(allowed):
        return 'Special Ability plan leaves the Regions granted by this Event.'
    # A concrete plan is required; never let an omitted plan invoke a bot's
    # board-wide automatic chooser after a restricted human selection.
    details = action.get('details') or {}
    merged = dict(details.get('sa_details') or {}); merged.update(details)
    required = {'Build':'build_plan', 'Scout':'scout_plan', 'Suborn':'suborn_plan',
                'Enlist':'enlist',
                'Intimidate':'intimidate_plan'}.get(sa)
    if sa in ('Entreat', 'Rampage') and not any(
            isinstance(e, dict) for e in action.get('sa_regions') or []):
        return 'Supply an explicit Special Ability plan with targets.'
    if required and required not in merged:
        return f'Supply an explicit {required}.'
    if any(k in details for k in ('no_retreat', 'force_retreat', 'allied_factions',
                                  'warband_full_loss', 'transfers')):
        return 'The plan includes effects not granted by this Event.'
    destinations = request.get('required_destinations')
    if cmd == 'March' and destinations is not None:
        plan = details.get('march_plan') or details
        routes = plan.get('routes') or {}
        if not routes or set(routes) != set(plan.get('origins') or []):
            return 'Supply an explicit route for every March origin.'
        routes = list(routes.values()) + [e.get('route') for e in plan.get('extra_groups') or []]
        if any(not path or path[-1] not in destinations for path in routes):
            return 'Every March group must end in the Event destination.'
    sim = deepcopy({k:v for k,v in state.items() if k != 'decision_agent'})
    result = execute_free_action_plan(sim, faction, request, action)
    error = _result_error(result)
    if error:
        return error
    if not result or result.get('executed') is False:
        return (result or {}).get('reason', 'The proposed free action has no legal effect.')
    return None


def consult_free_action(state, faction, request):
    """None uses the existing NP default; an explicit action is always checked."""
    from fs_bot.engine.agent import consult_agent
    response = consult_agent(state, faction, request)
    if response is None or response == {'use_default': True}:
        return None
    error = validate_free_action_response(state, faction, request, response)
    if error:
        raise ValueError(error)
    return response
