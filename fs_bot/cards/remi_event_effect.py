"""Card 68 shaded: the Gallic Ally of Remi owns its optional City effect.

Card Reference 68 and §§5.1–5.1.3, 8.2.3, 8.3.1, 8.3.4, 8.4.1.
The Event executor retains voluntary-removal authority during the effect.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import get_available, place_piece
from fs_bot.map.map_data import get_playable_regions_for_state

_STEPS = {'68.citadel', '68.warbands'}
_STATUSES = (rc.MARKER_DISPERSED, rc.MARKER_DISPERSED_GATHERING, rc.MARKER_RAZED)


def owner(state):
    faction = state.get('tribes', {}).get(rc.TRIBE_REMI, {}).get('allied_faction')
    return faction if faction in rc.GALLIC_FACTIONS else None


def options(state):
    """Legal printed targets, without consuming randomness or player input."""
    from fs_bot.cards.card_effects import _tribe_region
    playable = get_playable_regions_for_state(state)
    return {'target_cities': [city for city in (rc.CITY_ALESIA, rc.CITY_CENABUM)
            if rc.CITY_TO_TRIBE[city] in state.get('tribes', {})
            and _tribe_region(state, rc.CITY_TO_TRIBE[city]) in playable]}


def _normalize(params):
    if not isinstance(params, dict):
        raise ValueError('Remi Influence choices must be an object')
    return deepcopy(params)


def _shape(params, *, allow_outer=False):
    if set(params) & {'decline', 'use_default'}:
        if len(params) != 1 or next(iter(params.values())) is not True:
            raise ValueError('Decline or use_default must be a single field set to boolean true')
        return
    if set(params) - {'target_city', 'stage_timing_actions'}:
        raise ValueError('Unexpected Remi Influence fields or wrong-side choices')
    if 'stage_timing_actions' in params:
        stages = params['stage_timing_actions']
        allowed = _STEPS | ({'handler_complete'} if allow_outer else set())
        if (not isinstance(stages, dict) or set(stages) - allowed
                or any(not isinstance(value, list) for value in stages.values())):
            raise ValueError('Choose existing Remi Influence steps with timing-action lists')


def _discard_markers(markers, names):
    for marker in names:
        if isinstance(markers, dict):
            markers.pop(marker, None)
        elif isinstance(markers, set):
            markers.discard(marker)


def _apply(state, actor, params, *, complete=True, stage=None):
    from fs_bot.cards.card_effects import _tribe_region, _unally_tribe, _event_step
    _shape(params)
    if params.get('decline') is True or actor is None:
        return False
    city = params.get('target_city')
    if city is None and not complete:
        return False
    if city not in options(state)['target_cities']:
        raise ValueError('Choose Alesia or Cenabum for Remi Influence')
    tribe = rc.CITY_TO_TRIBE[city]
    region = _tribe_region(state, tribe)
    info = state['tribes'][tribe]
    # "Anything at" means the City's Ally, Citadel or status marker, never
    # the mobile forces elsewhere in its Region (Card 68 Tips).
    _unally_tribe(state, tribe)
    if info.get('status') in _STATUSES:
        info['status'] = None
    _discard_markers(state.get('markers', {}).get(tribe), _STATUSES)
    # Sacking also records its City's Razed marker at Region level. There
    # is one City per Region; other tribes' Dispersed markers stay intact.
    _discard_markers(state.get('markers', {}).get(region), (rc.MARKER_RAZED,))
    if stage == '68.citadel':
        return True
    _event_step(state, '68.citadel')
    # Re-read Available after each timing window. Partial execution removes
    # the old City piece even when no replacement Citadel is Available.
    if get_available(state, actor, rc.CITADEL) > 0:
        place_piece(state, region, actor, rc.CITADEL)
        info['allied_faction'] = actor
        refresh_all_control(state)
    if stage == '68.warbands':
        return True
    _event_step(state, '68.warbands')
    warbands = min(4, get_available(state, actor, rc.WARBAND))
    if warbands:
        place_piece(state, region, actor, rc.WARBAND, count=warbands)
    return True


def preview(state, params, complete=False, stage=None):
    """Detached result, or board immediately before a named timing window."""
    from fs_bot.engine.action_windows import scope
    if stage is not None and stage not in _STEPS:
        raise ValueError('Unknown Remi Influence preview stage')
    params = _normalize(params)
    sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    sim['_diviciacus_preview'] = True
    actor = owner(state)
    executor = state.get('executing_faction') or actor
    sim['event_params'] = params
    sim['executing_faction'] = actor
    with scope(sim, actor=executor, plan=params, force=True):
        _apply(sim, actor, params, complete=complete, stage=stage)
    return sim


def validate_response(state, faction, request, response):
    if (request.get('card_id') != 68 or faction != owner(state)
            or faction is None or request.get('acting_faction', faction) != faction):
        raise ValueError('Only the Gallic Ally of Remi chooses this Event effect')
    response = _normalize(response)
    _shape(response)
    if response.get('decline') is True or response.get('use_default') is True:
        return
    preview(state, response, complete=True)


def _ranked_targets(state):
    from fs_bot.bots.bot_common import get_faction_targeting_order
    from fs_bot.cards.card_effects import _tribe_piece_type
    actor = owner(state)
    if actor is None:
        return []
    order = get_faction_targeting_order(actor, state['scenario'])
    ranked = []
    for city in options(state)['target_cities']:
        info = state['tribes'][rc.CITY_TO_TRIBE[city]]
        target = info.get('allied_faction')
        kind = _tribe_piece_type(state, rc.CITY_TO_TRIBE[city])
        own_citadel = int(target == actor and kind == rc.CITADEL)
        own_ally = int(target == actor and kind == rc.ALLY)
        placed = int(get_available(state, actor, rc.CITADEL) + own_citadel > 0)
        net_citadels = placed - own_citadel
        if actor == rc.BELGAE and net_citadels - own_ally <= 0:
            continue  # Card 68: must increase total Belgic Allies+Citadels.
        enemy_citadel = int(target != actor and kind == rc.CITADEL)
        enemy_ally = int(target != actor and kind == rc.ALLY)
        warbands = min(4, get_available(state, actor, rc.WARBAND))
        if not (net_citadels or enemy_citadel or enemy_ally or warbands
                or info.get('status') in _STATUSES):
            continue
        score = (net_citadels + enemy_citadel, enemy_ally - own_ally, warbands,
                 -order.index(target) if target in order else -len(order))
        ranked.append((city, score))
    return ranked


def default_params(state):
    from fs_bot.bots.bot_common import random_select
    ranked = _ranked_targets(state)
    if not ranked:
        return {'decline': True}
    best = max(score for _, score in ranked)
    return {'target_city': random_select(state, [city for city, score in ranked if score == best])}


def request(state):
    return {'kind': 'free_action', 'request_type': 'remi_event_effect',
            'card_id': 68, 'acting_faction': owner(state), 'free': True,
            'with_sa': False, 'allow_decline': True,
            'validate_default_response': True, **options(state)}


def execute(state):
    from fs_bot.engine.free_actions import consult_free_action
    from fs_bot.engine.action_windows import scope
    actor = owner(state)
    executor = state.get('executing_faction') or actor
    raw = state.get('event_params')
    params = _normalize({} if raw is None else raw)
    _shape(params, allow_outer=True)
    if 'stage_timing_actions' in params:
        params['stage_timing_actions'].pop('handler_complete', None)
    if actor is None:
        return {'accepted': False, 'acting_faction': None}
    selections = set(params) - {'stage_timing_actions'}
    if executor != actor and (selections or params.get('stage_timing_actions')):
        raise ValueError('The Gallic Ally of Remi, not the Event executor, chooses the target and its authored stages')
    if not selections:
        automatic = actor == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
        chosen = None if automatic else consult_free_action(state, actor, request(state))
        chosen = default_params(state) if chosen is None else _normalize(chosen)
        params = (chosen if chosen.get('decline') is True else
                  {**{k: v for k, v in params.items() if k == 'stage_timing_actions'}, **chosen})
    elif params.get('use_default') is True:
        params = default_params(state)
    previous = state.get('event_params')
    had_executor = 'executing_faction' in state
    previous_executor = state.get('executing_faction')
    state['event_params'] = params
    state['executing_faction'] = actor
    try:
        with scope(state, actor=executor, plan=params, force=True):
            accepted = _apply(state, actor, params)
        return {'accepted': accepted, 'acting_faction': actor}
    finally:
        state['event_params'] = previous
        if had_executor:
            state['executing_faction'] = previous_executor
        else:
            state.pop('executing_faction', None)


def derive_params(state, faction):
    return default_params(state) if faction == owner(state) else None


def np_available(state, faction):
    return faction == owner(state) and bool(_ranked_targets(state))
