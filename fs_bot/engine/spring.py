"""Spring Successors (§6.6), NP choices (§8.3.2), and Pax Leader entry."""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, get_available, place_piece
from fs_bot.engine.agent import consult_agent
from fs_bot.map.map_data import get_playable_regions_for_state

KIND = 'spring_leader'
UNLOCK_KEY = 'vercingetorix_entry_unlocked'


@contextmanager
def atomic(state):
    """A paused or invalid choice restores pieces, bookkeeping, and RNG."""
    before = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        yield
    except BaseException:
        state.clear()
        state.update(before)
        if isinstance(card_turn, dict):
            # The card coordinator keeps this dictionary across nested choices.
            # Restore its contents without stranding that live reference.
            card_turn.clear()
            card_turn.update(state['_card_turn'])
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise


def placement_request(state, faction, leader, *, source, legal_regions,
                      can_defer=False, reason=None, equal_priority=False):
    """Build an authored request; Interlude may supply an already ranked tie."""
    return {'kind': KIND, 'faction': faction, 'leader': leader, 'source': source,
            'legal_regions': sorted(set(legal_regions)), 'can_defer': can_defer,
            'reason': reason, 'equal_priority': equal_priority}


def successor_regions(state, faction):
    """Own pieces or printed Home Rally/Recruit symbols, within active geography."""
    homes = {rc.ROMANS: rc.ROMAN_HOME_REGIONS,
             rc.ARVERNI: rc.ARVERNI_HOME_REGIONS_BASE,
             rc.BELGAE: rc.BELGAE_HOME_REGIONS,
             rc.GERMANS: rc.GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC}.get(faction, ())
    return [region for region in get_playable_regions_for_state(state, faction)
            if region in homes or count_pieces(state, region, faction) > 0]


def successor_request(state, faction):
    leaders = (rc.ARIOVISTUS_LEADERS if state['scenario'] in rc.ARIOVISTUS_SCENARIOS
               else rc.BASE_LEADERS)
    factions = {rc.LEADER_FACTION[name] for name in leaders if name != rc.DIVICIACUS}
    if (faction not in factions or find_leader(state, faction) is not None
            or get_available(state, faction, rc.LEADER) < 1
            or any(rc.LEADER_FACTION.get(name) == faction
                   for name in state.get('spring_box_leaders', []))):
        return None
    regions = successor_regions(state, faction)
    if not regions:
        return None
    return placement_request(state, faction, rc.SUCCESSOR, source='available',
                             legal_regions=regions, reason='successor')


def validate_response(state, request, response):
    """Validate against the engine-authored choices without consuming RNG."""
    if isinstance(response, dict) and set(response) == {'use_default'} and response['use_default'] is True:
        return response
    if isinstance(response, dict) and set(response) == {'defer'} and response['defer'] is True:
        if request['can_defer']:
            return response
        raise ValueError('This Leader placement is required.')
    if (not isinstance(response, dict) or set(response) != {'region'}
            or not isinstance(response['region'], str)
            or response['region'] not in request['legal_regions']):
        raise ValueError('Choose one of the offered Leader placement Regions.')
    return response


def choose_region(state, faction, request):
    """Choose only; caller performs its particular named/Successor placement."""
    regions = request['legal_regions']
    if len(regions) == 1 and not request['can_defer']:
        return regions[0]
    response = (consult_agent(state, faction, request)
                if faction not in state.get('non_player_factions', set()) else None)
    if response is not None:
        validate_response(state, request, response)
        if response.get('defer') is True:
            return None
        if 'region' in response:
            return response['region']
    from fs_bot.bots.bot_common import get_leader_placement_region, random_select
    if request.get('equal_priority'):
        return random_select(state, regions)
    return get_leader_placement_region(state, faction, candidates=regions)


def place_successors(state):
    """Mandatory placements; interruption of a later seat rolls back earlier seats."""
    result = []
    leaders = (rc.ARIOVISTUS_LEADERS if state['scenario'] in rc.ARIOVISTUS_SCENARIOS
               else rc.BASE_LEADERS)
    with atomic(state):
        for name in leaders:
            faction = rc.LEADER_FACTION[name]
            request = successor_request(state, faction)
            if request is None:
                continue
            region = choose_region(state, faction, request)
            place_piece(state, region, faction, rc.LEADER, leader_name=rc.SUCCESSOR)
            result.append((faction, region))
    return result


def unlock_spring_box_entry(state):
    """Called only when the first Pax Spring begins, never at Interlude Spring."""
    if rc.VERCINGETORIX in state.get('spring_box_leaders', []):
        state[UNLOCK_KEY] = True


def spring_box_request(state):
    unlocked = state.get(UNLOCK_KEY) is True
    if UNLOCK_KEY not in state:
        # Older saves have no unlock flag. Infer only after a completed Pax
        # Winter, outside its live Winter card, with no first-Winter gate.
        # The Interlude retains that gate until its next Spring.
        unlocked = (state['scenario'] == rc.SCENARIO_PAX_GALLICA
                    and state.get('winter_count', 0) > 0
                    and state.get('current_card') != rc.WINTER_CARD
                    and not state.get('first_winter_special'))
    if (not unlocked or state['scenario'] not in rc.BASE_SCENARIOS
            or rc.VERCINGETORIX not in state.get('spring_box_leaders', [])
            or find_leader(state, rc.ARVERNI) is not None):
        return None
    return placement_request(state, rc.ARVERNI, rc.VERCINGETORIX, source='spring_box',
        legal_regions=get_playable_regions_for_state(state, rc.ARVERNI),
        can_defer=True, reason='pax_vercingetorix')


def resolve_spring_box_entry(state, response=None):
    """Offer optional named entry, or apply an explicit later-entry response."""
    request = spring_box_request(state)
    if request is None:
        return None
    with atomic(state):
        state[UNLOCK_KEY] = True
        if response is None:
            region = choose_region(state, rc.ARVERNI, request)
        else:
            validate_response(state, request, response)
            if response.get('defer') is True:
                region = None
            elif 'region' in response:
                region = response['region']
            else:
                from fs_bot.bots.bot_common import get_leader_placement_region
                region = get_leader_placement_region(state, rc.ARVERNI,
                                                     candidates=request['legal_regions'])
        result = {'faction': rc.ARVERNI, 'leader': rc.VERCINGETORIX}
        if region is None:
            return dict(result, deferred=True)
        # Transfer the physical piece from its separate Spring box through
        # Available, then use the normal placement helper for the map change.
        state['spring_box_leaders'].remove(rc.VERCINGETORIX)
        state['available'][rc.ARVERNI][rc.LEADER] += 1
        place_piece(state, region, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
        state.pop(UNLOCK_KEY, None)
        state.pop('_spring_box_entry_window', None)
        return dict(result, region=region)


def _mid_action_request(state, window, *, allow_preview=False):
    if (rc.ARVERNI in state.get('non_player_factions', set())
            or (state.get('_diviciacus_preview') and not allow_preview)
            or state.get('_resolved_card', {}).get('game_over')):
        return None
    request = spring_box_request(state)
    if request is None:
        return None
    return dict(request, window=deepcopy(window))


def mid_action_request(state, window):
    """Pure human entry offer at an engine-authored semantic step.

    Pax Gallica permits entry at any time beginning with the first Spring,
    including other factions' actions and later Winter phases. The caller
    owns the step's transaction and must offer before deriving its choices.
    Legacy complete-action requests intentionally retain their old shape.
    """
    return _mid_action_request(state, window)


def _validate_mid_action_request(state, request, *, allow_preview=False):
    if not isinstance(request, dict):
        raise ValueError('A current Spring entry request is required.')
    current = _mid_action_request(state, request.get('window'),
                                  allow_preview=allow_preview)
    if current is None or current != request:
        raise ValueError('The Spring entry opportunity has changed.')
    return current


def resolve_mid_action_entry(state, request, response=None):
    """Apply one authored entry response without consulting a decision agent.

    A newly inserted opportunity must not auto-place a human's Leader when
    no response was chosen. Only explicit use_default invokes NP placement
    priorities; the legacy Spring and complete-action behavior is unchanged.
    """
    _validate_mid_action_request(state, request)
    return resolve_spring_box_entry(
        state, {'defer': True} if response is None else response)


def preview_mid_action_entry(state, request, response):
    """Return a detached (state, result) for an explicit placement or deferral.

    Preview never consults an agent or draws a default destination. Callers
    must name a Region to inspect its effect on the rest of the action.
    """
    current = _validate_mid_action_request(state, request, allow_preview=True)
    validate_response(state, current, response)
    if response.get('use_default') is True:
        raise ValueError('Spring entry preview requires an explicit Region or deferral.')
    preview = deepcopy({key: value for key, value in state.items()
                        if key != 'decision_agent'})
    result = resolve_spring_box_entry(preview, response)
    return preview, result


def np_spring_plan(state, faction):
    """Bot-node plan, with a Successor unless the named Spring-box entry is open."""
    request = successor_request(state, faction)
    if request is None and faction == rc.ARVERNI:
        request = spring_box_request(state)
    if request is None:
        return None
    from fs_bot.bots.bot_common import get_leader_placement_region
    region = get_leader_placement_region(state, faction, candidates=request['legal_regions'])
    return {'place_leader': request['leader'], 'region': region}
