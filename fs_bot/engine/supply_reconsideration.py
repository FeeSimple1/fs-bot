"""Human reconsideration after the actual NP Aedui Supply refusal (§8.6.6).

Recruit is reconsidered at its current Command boundary, after any preceding
Special Ability. Build is reconsidered at its own boundary, so an earlier
March or Seize stays resolved. An untouched interrupted Command may be
replaced as a whole; a later portion cannot change already resolved portions.
PR-07 fixes the automated answer across all of these choices.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc

KIND = 'supply_refusal'
ACK = ('np_aedui_supply_refusal_acknowledged',)
SA_DETAILS = {
    'build_plan', 'scout_plan', 'sa_details', 'diviciacus_sa_regions',
}


def _copy(state):
    result = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    result['_diviciacus_preview'] = True
    return result


def _dependencies(state, action, *, sa_only):
    from fs_bot.engine.recruit_planning import forecast_supply, ANSWERS
    from fs_bot.engine.supply_retry import RECEIPT
    from fs_bot.engine.execute import _execute_recruit, _execute_build
    sim = _copy(state)
    # Discover dependencies despite a refusal, but retain already binding
    # promises (including Region-keyed replies from older saved contexts).
    # A known permission must never be replaced by another consent die.
    for cache in ('_supply_line_agreements', ANSWERS):
        if cache in sim:
            sim[cache] = {key: value for key, value in sim[cache].items()
                          if value is True}
    if ('_card_turn' in sim
            and not sim['_card_turn'].get(RECEIPT, {}).get('answer')):
        sim['_card_turn'].pop(RECEIPT, None)
    with forecast_supply(sim) as requests:
        if sa_only:
            _execute_build(sim, rc.ROMANS, action)
        else:
            _execute_recruit(sim, rc.ROMANS, action, _exact=True)
    answers = sim.get(ANSWERS, {})
    return [r for r in requests if r['faction'] == rc.AEDUI
            and r['requesting_faction'] == rc.ROMANS
            and not answers.get((rc.ROMANS, rc.AEDUI, r['region']))
            and not answers.get((rc.ROMANS, rc.AEDUI, None))]


def _command_projection(action):
    """Fields a replacement SA cannot rewrite after the Command resolved."""
    result = deepcopy(action)
    for key in ('sa', 'sa_regions', 'sa_timing'):
        result.pop(key, None)
    details = result.get('details') or {}
    for key in SA_DETAILS:
        details.pop(key, None)
    result['details'] = details
    return result


def validate_response(state, request, response):
    if type(response) is not dict:
        raise ValueError('Supply refusal needs continue or a replacement action')
    continuing = set(response) == {'continue'} and response['continue'] is True
    if continuing and request['action_type'] == 'special_ability':
        return response
    if not continuing and (set(response) != {'replacement'} or type(response['replacement']) is not dict):
        raise ValueError('Return {continue: true} or {replacement: action}')
    replacement = request['action'] if continuing else response['replacement']
    if (not continuing and request.get('frumentum') is not None
            and set(replacement) == {'skip'}):
        if replacement['skip'] != request['action'].get('command'):
            raise ValueError('Skip only the current Frumentum Command')
        from fs_bot.engine.frumentum import validate_response as validate_frumentum
        validate_frumentum(state, request['frumentum'], replacement)
        return response
    # Validate before accessing nested fields or projecting the completed
    # Command. An AttributeError here would escape the durable validator
    # and the raw decision-agent adapter would silently defer the choice.
    details = replacement.get('details', {})
    if not isinstance(details, dict):
        raise ValueError('Replacement Command details must be an object')
    if not continuing and details.get('transfers'):
        raise ValueError('Supply reconsideration cannot add Resource transfers')
    from fs_bot.engine.action_validation import validate_human_structure, command_regions
    from fs_bot.engine.moves import validate_player_action
    sa_only = request['action_type'] == 'special_ability'
    if sa_only:
        if _command_projection(replacement) != _command_projection(request['action']):
            raise ValueError('Rechoosing Build cannot change the preceding Command')
    elif replacement.get('command') not in request['allowed_commands']:
        raise ValueError('Replacement Command is not allowed for this action')
    sa = replacement.get('sa') or 'No SA'
    if sa not in request['allowed_special_abilities']:
        raise ValueError('Replacement Special Ability is not allowed')
    if sa_only:
        # The accompanying Command already passed its own validation and
        # may have executed under an Event's free/Frost exception. Rechecking
        # that old Command as an ordinary new action would reject legal SAs.
        from fs_bot.engine.action_validation import compatible_sa
        if (replacement.get('command') is not None
                and not compatible_sa(replacement.get('command'), sa)):
            raise ValueError('Replacement Special Ability cannot accompany this Command')
    else:
        structural = deepcopy(replacement)
        accompanying = request.get('accompanying_sa')
        if accompanying and accompanying != 'No SA':
            structural['sa'] = accompanying
        error = validate_human_structure(
            state, rc.ROMANS, structural, limited=request.get('limited', False),
            allow_frost=request.get('grant') is not None or request.get('frumentum') is not None)
        if error:
            raise ValueError(error)
    allowed = request.get('allowed_regions')
    if allowed is not None:
        from fs_bot.engine.free_actions import _sa_regions
        regions = _sa_regions(replacement) if sa_only else command_regions(replacement)
        if not set(regions).issubset(allowed):
            raise ValueError('Replacement selects a Region outside the action grant')
    if request.get('max_regions') is not None and not sa_only:
        if len(set(command_regions(replacement))) > request['max_regions']:
            raise ValueError('Replacement selects too many Regions')
    if (not sa_only and set(command_regions(replacement))
            & set(request.get('excluded_regions', ()))):
        raise ValueError('Replacement reselects a Region already used by this Command')
    completed_sa = request.get('completed_sa_result') or {}
    if not sa_only and replacement.get('command') == rc.CMD_SEIZE:
        built_allies = {effect[1] for effect in completed_sa.get('actions', ())
                        if completed_sa.get('sa') == rc.SA_BUILD
                        and isinstance(effect, (tuple, list)) and len(effect) >= 2
                        and effect[0] in ('ally', 'subdue')}
        if set(command_regions(replacement)) & built_allies:
            raise ValueError('Seize cannot select a Region where the accompanying Build placed/subdued an Ally (§4.2.1)')
    if request.get('frumentum') is not None:
        if sa_only and sa == 'No SA':
            return response
        from fs_bot.engine.frumentum import validate_response as validate_frumentum
        validate_frumentum(state, request['frumentum'], replacement)
        return response
    if request.get('grant') is not None:
        from fs_bot.engine.free_actions import validate_free_action_response
        grant = deepcopy(request['grant'])
        candidate = deepcopy(replacement)
        if sa_only:
            if sa == 'No SA' and grant.get('allow_decline', True):
                return response
            grant['request_type'] = 'event_sa'
            candidate['command'] = None
        else:
            # Reconsidering the Command does not execute its accompanying
            # Special Ability a second time during validation.
            if request.get('command_only', True):
                grant['with_sa'] = False
        error = validate_free_action_response(state, rc.ROMANS, grant, candidate)
        if error:
            raise ValueError(error)
        return response
    if sa_only:
        if sa == 'No SA':
            return response
        from fs_bot.engine.execute import _execute_sa
        result = _execute_sa(_copy(state), rc.ROMANS, replacement)
        if (not isinstance(result, dict) or not result.get('executed')
                or result.get('errors')):
            raise ValueError('Replacement Special Ability has no legal complete effect')
    else:
        valid, result = validate_player_action(state, rc.ROMANS, replacement)
        if not valid or not isinstance(result, dict) or result.get('errors'):
            raise ValueError(f'Replacement Command is not executable: {result}')
    return response


def reconsider(state, faction, action, *, sa_only=False, limited=False, with_sa=True,
               allowed_commands=None, accompanying_sa=None, continuation=False,
               excluded_regions=(), grant=None, dependency_action=None, frumentum=None,
               completed_sa_result=None):
    """Return the original or explicitly revised plan, without applying it."""
    from fs_bot.commands.rally import np_aedui_supply_key
    key = np_aedui_supply_key(state, faction, rc.AEDUI)
    if (key is None or state.get('_diviciacus_preview')
            or (action.get('sa') != rc.SA_BUILD if sa_only
                else action.get('command') != rc.CMD_RECRUIT)):
        return action
    agreements = state.get('_supply_line_agreements')
    ack = ACK + ('special_ability' if sa_only else 'command',)
    if agreements is None or agreements.get(ack):
        return action
    dependencies = _dependencies(state, dependency_action or action, sa_only=sa_only)
    if not dependencies:
        return action
    from fs_bot.engine.supply_retry import resolve_np_supply
    before = state['rng'].getstate()
    answer = agreements.get(key)
    if answer is None:
        answer = resolve_np_supply(state, rc.AEDUI, rc.ROMANS)
        from fs_bot.engine.supply_retry import current_receipt
        if answer or state['rng'].getstate() != before or current_receipt(state) is not None:
            agreements[key] = answer
    # Only the real 5–6 refusal grants this additional reconsideration.
    # The ordinary >12 refusal remains known during normal plan validation.
    if answer or key not in agreements:
        return action
    from fs_bot.engine.action_validation import compatible_sa
    sas = (['No SA'] if limited or not with_sa else
           [rc.SA_BUILD, rc.SA_SCOUT, rc.SA_BESIEGE, 'No SA'])
    if sa_only and action.get('command') is not None:
        sas = [sa for sa in sas if compatible_sa(action['command'], sa)]
    elif sa_only:
        sas = [rc.SA_BUILD, rc.SA_SCOUT, 'No SA']
    request = {
        'kind': KIND, 'action_type': 'special_ability' if sa_only else 'command',
        'action': deepcopy(action),
        'allowed_commands': list(allowed_commands if allowed_commands is not None else rc.ROMAN_COMMANDS),
        'allowed_special_abilities': sas, 'limited': bool(limited),
        'command_only': not with_sa,
        'context': {'host': rc.AEDUI, 'answer': False,
                    'reason': 'Non-player Aedui refused Supply; the same answer applies to this action.'},
    }
    if frumentum is not None:
        request['frumentum'] = deepcopy(frumentum)
    if grant is not None:
        request['grant'] = deepcopy(grant)
        request['allowed_commands'] = [cmd for cmd in request['allowed_commands']
                                      if cmd in grant.get('allowed_commands', rc.ROMAN_COMMANDS)]
        if sa_only and grant.get('allowed_sas') is not None:
            request['allowed_special_abilities'] = [
                sa for sa in sas if sa in grant['allowed_sas']
                or sa == 'No SA' and grant.get('allow_decline', True)]
        for field in ('allowed_regions', 'max_regions'):
            if grant.get(field) is not None:
                request[field] = deepcopy(grant[field])
    if accompanying_sa:
        request['accompanying_sa'] = accompanying_sa
    if completed_sa_result is not None:
        request['completed_sa_result'] = deepcopy(completed_sa_result)
    if continuation:
        request['continuation'] = True
    if excluded_regions:
        request['excluded_regions'] = list(excluded_regions)
    if 'allowed_regions' not in request and state.get('_command_region_scope') is not None:
        request['allowed_regions'] = sorted(state['_command_region_scope'])
    if state.get('_command_max_regions') is not None:
        request['max_regions'] = state['_command_max_regions']
    from fs_bot.engine.agent import consult_agent
    response = consult_agent(state, faction, request)
    if response is None:
        return action  # Raw callback's documented default: keep its chosen plan.
    validate_response(state, request, response)
    agreements[ack] = True
    return deepcopy(response.get('replacement', action))
