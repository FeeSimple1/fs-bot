"""Explicit, scoped choices for Event-granted Commands and Special Abilities.

An agent returns a complete ordinary action, ``{'decline': True}``, or
``{'use_default': True}``. Validation simulates on an isolated board and RNG;
neither malformed plans nor out-of-scope choices can partially apply an Event.
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
            if sa == 'Trade':
                return ex._execute_trade(state, faction,
                                         allowed_regions=request.get('allowed_regions'))
            return handlers[sa](state, faction, action)
        return ex._execute_bot_command(state, faction, action,
                                       with_sa=request.get('with_sa', False))


def validate_free_action_response(state, faction, request, response):
    """Return a useful validation error, or None for a legal explicit response."""
    if not isinstance(response, dict):
        return 'Return a full action, decline, or use_default.'
    if response == {'decline': True} or response == {'use_default': True}:
        return None
    try:
        return _validate_plan(state, faction, request, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, CommandError, PieceError) as exc:
        return f'Invalid free action: {exc}'


def _validate_plan(state, faction, request, action):
    from fs_bot.cli.human_plan import _faction_special_abilities
    from fs_bot.engine.action_validation import command_regions, command_parts, compatible_sa
    from fs_bot.map.map_data import get_playable_regions
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
    parts = command_parts(action)
    if len(parts) > 1:
        if cmd in ('March', 'Battle') or action.get('sa_timing') != 'during' or len(parts) != 2:
            return 'Invalid interrupted Command.'
        if any(part.get('command') != cmd for part in parts):
            return 'Both portions must use the same Command.'
    selected = []
    for part in parts:
        selected.extend(command_regions(part))
        if cmd == 'March':
            details = part.get('details') or {}
            plan = details.get('march_plan') or details
            selected.extend(e.get('origin') for e in plan.get('extra_groups') or [])
    if len(parts) > 1 and len(selected) != len(set(selected)):
        return 'Select each Command Region only once.'
    playable = set(get_playable_regions(state['scenario'], state.get('capabilities')))
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
