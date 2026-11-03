"""Named-owner choices for Legiones, Rhenus Bridge, Sacking and Gobannitio.

Card Reference 2/18/23/26 and A Card Reference A18; §§5.1–5.1.3.
The named faction owns optional effects, even on another faction's Event.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (count_pieces, count_pieces_by_state, get_available,
                                 get_leader_in_region, place_piece, remove_piece,
                                 _count_on_legions_track)
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

_TIMING = {'stage_timing_actions'}


def supported(card_id, shaded):
    return (card_id, shaded) in {(2, False), (18, False), ('A18', False),
                                (23, False), (26, True)}


def owner(card_id):
    return rc.ARVERNI if card_id == 26 else rc.ROMANS


def _clone(state):
    sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    sim['_diviciacus_preview'] = True
    return sim


def _can_shift(state):
    senate = state['senate']
    return senate['position'] is not None and not (
        senate['position'] == rc.UPROAR and senate['firm'])


def options(state, card_id):
    """Current legal concrete targets; no random calls or input consultation."""
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    if card_id == 2:
        track, fallen = _count_on_legions_track(state), state.get('fallen_legions', 0)
        return {'can_shift': _can_shift(state), 'legions_track': track,
                'fallen_legions': fallen, 'required_legions': min(2, track + fallen)}
    if card_id in (18, 'A18'):
        playable = set(get_playable_regions_for_state(state))
        regions = [r for r in rc.GERMANIA_REGIONS if r in playable
                   and (card_id != 'A18' or get_leader_in_region(state, r, rc.GERMANS) != rc.ARIOVISTUS_LEADER)
                   and any(is_controlled_by(state, p, rc.ROMANS)
                           for p in {r, *get_adjacent_for_state(state, r)})]
        return {'target_regions': sorted(regions)}
    if card_id == 23:
        return {'target_cities': sorted(city for city, tribe in rc.CITY_TO_TRIBE.items()
            if tribe in state['tribes'] and _tribe_region(state, tribe) in get_playable_regions_for_state(state)
            and is_controlled_by(state, _tribe_region(state, tribe), rc.ROMANS))}
    if card_id == 26:
        from fs_bot.cards.all_gaul_gathers import ally_options
        return {'removable_tribes': sorted(t for t in state['tribes']
                    if _tribe_region(state, t) == rc.ARVERNI_REGION
                    and _tribe_piece_type(state, t) == rc.ALLY),
                'placeable_tribes': sorted(t for t, f in ally_options(state, rc.ARVERNI_REGION)
                                          if f == rc.ARVERNI)}
    raise ValueError('Unsupported named Event')


def _normalize(card_id, params):
    if not isinstance(params, dict):
        raise ValueError('Named Event choices must be an object')
    params = deepcopy(params)
    if card_id == 'A18' and 'region' in params:
        if 'target_region' in params and params['target_region'] != params['region']:
            raise ValueError('A18 has exactly one selected target Region')
        params['target_region'] = params.pop('region')
    return params


def _outer_steps(card_id):
    return {'handler_complete'} | ({'grant.card_26_arverni_rally'} if card_id == 26 else set())


def _shape(card_id, params, *, allow_outer=False):
    if set(params) & {'decline', 'use_default'}:
        if len(params) != 1 or next(iter(params.values())) is not True:
            raise ValueError('Decline or use_default must be a single field set to boolean true')
        return
    allowed = {2: {'legions_from_track', 'legions_from_fallen'},
               18: {'target_region'}, 'A18': {'target_region'}, 23: {'target_city'},
               26: {'ally_removals', 'ally_placements'}}[card_id]
    if set(params) - allowed - _TIMING:
        raise ValueError('Unexpected named Event fields or wrong-side choices')
    if card_id == 2:
        counts = [params.get(k, 0) for k in ('legions_from_track', 'legions_from_fallen')]
        if any(type(n) is not int or n < 0 for n in counts) or sum(counts) > 2:
            raise ValueError('Choose nonnegative integer Legion source counts totaling at most two')
    if card_id == 26:
        for key in ('ally_removals', 'ally_placements'):
            entries = params.get(key, [])
            if not isinstance(entries, list) or any(not isinstance(t, str) for t in entries):
                raise ValueError('Gobannitio choices are lists of exact Tribe names')
            if len(set(entries)) != len(entries):
                raise ValueError('Do not repeat a Tribe within a Gobannitio component')
    if 'stage_timing_actions' in params:
        stages = params['stage_timing_actions']
        if not isinstance(stages, dict):
            raise ValueError('stage_timing_actions must be an object of named Event steps')
        allowed_steps = ({'2.legions', '2.fallen_legions'} if card_id == 2 else
            {f'26.{part}:{index}' for part, key in (('removals', 'ally_removals'),
                                                  ('placements', 'ally_placements'))
             for index in range(len(params.get(key, [])) + 1)} if card_id == 26 else set())
        if allow_outer:
            allowed_steps.update(_outer_steps(card_id))
        if set(stages) - allowed_steps or any(not isinstance(value, list) for value in stages.values()):
            raise ValueError('Choose existing named Event step/index keys with timing-action lists')


def _apply(state, card_id, params, *, complete=True):
    from fs_bot.cards.card_effects import (_apply_senate_shift, _event_step,
        _event_entries, _unally_tribe, _ally_tribe, _tribe_region,
        _unally_faction_tribes_in_region, _add_region_marker, _cap_resources)
    _shape(card_id, params)
    if params.get('decline') is True:
        return False
    if card_id == 2:
        # The shift is a prerequisite, so the whole effect is impossible while
        # Senate is off track or already at Firm Uproar (Card 2 Tips).
        if not _can_shift(state):
            return False
        _apply_senate_shift(state, rc.SENATE_UP)
        _event_step(state, '2.legions')
        track = params.get('legions_from_track', 0)
        early_track = min(track, _count_on_legions_track(state))
        if early_track:
            place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, count=early_track, from_legions_track=True)
        _event_step(state, '2.fallen_legions')
        # Later legal reclamation can supply an initially unavailable part
        # of the chosen track allocation. Keep its authored window in place,
        # and require the complete source allocation before committing.
        late_track = track - early_track
        if late_track > _count_on_legions_track(state):
            if complete:
                raise ValueError('Not enough Legions on the track for that source selection')
            late_track = _count_on_legions_track(state)
        if late_track:
            place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, count=late_track, from_legions_track=True)
        fallen = params.get('legions_from_fallen', 0)
        if fallen > state.get('fallen_legions', 0):
            raise ValueError('Not enough Fallen Legions for that source selection')
        if fallen:
            place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, count=fallen, from_fallen=True)
        if complete and track + fallen < min(2, track + fallen + _count_on_legions_track(state) + state.get('fallen_legions', 0)):
            raise ValueError('Accepted Legiones must place two Legions as far as possible')
        return True
    if card_id in (18, 'A18'):
        target = params.get('target_region')
        if target is None and not complete:
            return False
        if target not in options(state, card_id)['target_regions']:
            raise ValueError('Choose a legal Germania Region under or adjacent to Roman Control')
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            n = count_pieces_by_state(state, target, rc.GERMANS, rc.WARBAND, visibility)
            if n:
                remove_piece(state, target, rc.GERMANS, rc.WARBAND, count=n, piece_state=visibility)
        _unally_faction_tribes_in_region(state, target, rc.GERMANS)
        # A18 says all Germans. Its prohibition names Ariovistus, so an
        # unprotected Successor and Settlements are removed as well.
        for kind in (rc.ALLY, rc.SETTLEMENT, rc.LEADER):
            n = count_pieces(state, target, rc.GERMANS, kind)
            if n:
                remove_piece(state, target, rc.GERMANS, kind, count=n)
        return True
    if card_id == 23:
        city = params.get('target_city')
        if city is None and not complete:
            return False
        if city not in options(state, card_id)['target_cities']:
            raise ValueError('Choose a City at Roman Control')
        tribe = rc.CITY_TO_TRIBE[city]
        region = _tribe_region(state, tribe)
        _unally_tribe(state, tribe)
        state['tribes'][tribe]['status'] = rc.MARKER_RAZED
        _add_region_marker(state, region, rc.MARKER_RAZED)
        _cap_resources(state, rc.ROMANS, 8)
        return True
    for tribe in _event_entries(state, '26.removals', params.get('ally_removals', [])):
        if tribe not in options(state, 26)['removable_tribes']:
            raise ValueError('Gobannitio removes an existing Ally in Arverni Region, never a Citadel')
        _unally_tribe(state, tribe)
    for tribe in _event_entries(state, '26.placements', params.get('ally_placements', [])):
        if tribe not in options(state, 26)['placeable_tribes']:
            raise ValueError('Gobannitio places an Available Arverni Ally at a legal Subdued Tribe in Arverni Region')
        _ally_tribe(state, tribe, rc.ARVERNI)
    return True


def preview(state, card_id, params, complete=False):
    from fs_bot.engine.action_windows import scope
    sim = _clone(state)
    params = _normalize(card_id, params)
    executor = state.get('executing_faction') or owner(card_id)
    sim['event_params'] = params
    # Response timing is authored by its named owner (including Arverni
    # Spring entry); the trusted scope keeps reclamation with the executor.
    sim['executing_faction'] = owner(card_id)
    with scope(sim, actor=executor, plan=params, force=True):
        _apply(sim, card_id, params, complete=complete)
    return sim


def validate_response(state, faction, request, response):
    card_id = request['card_id']
    if faction != owner(card_id) or request.get('acting_faction', faction) != faction:
        raise ValueError('Only the named faction chooses this Event effect')
    response = _normalize(card_id, response)
    _shape(card_id, response)
    if response.get('decline') is True or response.get('use_default') is True:
        return
    preview(state, card_id, response, complete=True)


def default_params(state, card_id):
    from fs_bot.bots.bot_common import random_select, get_faction_targeting_order
    if card_id == 2:
        opts = options(state, card_id)
        # Roman card instruction explicitly requires both Legions.
        if not opts['can_shift'] or opts['required_legions'] < 2:
            return {'decline': True}
        # The supplied instructions name no source-pool priority. Equal
        # complete allocations use seeded selection (§§8.2.3, 8.3.4).
        allocations = [{'legions_from_track': track, 'legions_from_fallen': 2 - track}
                       for track in range(3) if track <= opts['legions_track']
                       and 2 - track <= opts['fallen_legions']]
        return random_select(state, allocations)
    if card_id in (18, 'A18'):
        regions = [r for r in options(state, card_id)['target_regions'] if count_pieces(state, r, rc.GERMANS)]
        if not regions:
            return {'decline': True}
        def score(r):
            return (count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT),
                    count_pieces(state, r, rc.GERMANS, rc.ALLY),
                    count_pieces(state, r, rc.GERMANS))
        best = max(map(score, regions))
        return {'target_region': random_select(state, [r for r in regions if score(r) == best])}
    if card_id == 23:
        from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
        cities = [city for city in options(state, 23)['target_cities']
                  if state['resources'][rc.ROMANS] < rc.MAX_RESOURCES
                  or state['tribes'][rc.CITY_TO_TRIBE[city]].get('status') != rc.MARKER_RAZED]
        if not cities:
            return {'decline': True}
        order = list(get_faction_targeting_order(rc.ROMANS, state['scenario']))
        def score(city):
            tribe = rc.CITY_TO_TRIBE[city]
            target = state['tribes'][tribe].get('allied_faction')
            kind = _tribe_piece_type(state, tribe)
            # Prefer enemy removals over sacrificing an own Ally, then
            # structures and enemy faction priorities (§§8.3.1, 8.4.1).
            return (target != rc.ROMANS, kind == rc.CITADEL and target != rc.ROMANS,
                    kind == rc.ALLY and target != rc.ROMANS,
                    -order.index(target) if target in order else -len(order))
        best = max(map(score, cities))
        return {'target_city': random_select(state, [c for c in cities if score(c) == best])}
    from fs_bot.cards.ally_events import derive_gobannitio
    return derive_gobannitio(state, rc.ARVERNI, True)


def request(state, card_id):
    return {'kind': 'free_action', 'request_type': 'named_event_effect',
            'card_id': card_id, 'acting_faction': owner(card_id),
            'free': True, 'with_sa': False, 'allow_decline': True,
            'validate_default_response': True, **options(state, card_id)}


def execute(state, card_id):
    from fs_bot.engine.free_actions import consult_free_action
    from fs_bot.engine.action_windows import scope
    actor = owner(card_id)
    executor = state.get('executing_faction') or actor
    raw = state.get('event_params')
    params = _normalize(card_id, {} if raw is None else raw)
    _shape(card_id, params, allow_outer=True)
    # Handler completion and the subsequent Rally grant belong to the outer
    # executor and are consumed after this helper restores its input.
    if 'stage_timing_actions' in params:
        for step in _outer_steps(card_id):
            params['stage_timing_actions'].pop(step, None)
    selections = set(params) - _TIMING
    if executor != actor and (selections or any(params.get(k) for k in _TIMING)):
        raise ValueError('The named faction, not the Event executor, chooses this optional effect and its authored stages')
    if not selections:
        automatic = actor == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
        chosen = None if automatic else consult_free_action(state, actor, request(state, card_id))
        chosen = default_params(state, card_id) if chosen is None else _normalize(card_id, chosen)
        # Only the same owner may carry pre-authored component timing into
        # its response. Foreign executor entry timing belongs to the outer
        # action; its live reclamation windows retain the trusted scope.
        params = (chosen if chosen.get('decline') is True else
                  {**{k: v for k, v in params.items() if k in _TIMING}, **chosen})
    elif params.get('use_default') is True:
        params = default_params(state, card_id)
    previous = state.get('event_params')
    had_executor = 'executing_faction' in state
    previous_executor = state.get('executing_faction')
    state['event_params'] = params
    state['executing_faction'] = actor
    try:
        with scope(state, actor=executor, plan=params, force=True):
            accepted = _apply(state, card_id, params)
        if card_id == 26 and accepted:
            state.setdefault('event_modifiers', {})['card_26_arverni_rally'] = True
        return {'accepted': accepted, 'acting_faction': actor}
    finally:
        state['event_params'] = previous
        if had_executor:
            state['executing_faction'] = previous_executor
        else:
            state.pop('executing_faction', None)


def derive_params(state, faction, card_id):
    # Other executors cannot pre-author the named owner's response.
    return default_params(state, card_id) if faction == owner(card_id) else None


def np_available(state, card_id):
    if card_id == 2:
        opts = options(state, card_id)
        return opts['can_shift'] and opts['required_legions'] == 2
    if card_id in (18, 'A18'):
        return any(count_pieces(state, r, rc.GERMANS) for r in options(state, card_id)['target_regions'])
    if card_id == 23:
        return any(state['resources'][rc.ROMANS] < rc.MAX_RESOURCES
                   or state['tribes'][rc.CITY_TO_TRIBE[city]].get('status') != rc.MARKER_RAZED
                   for city in options(state, card_id)['target_cities'])
    return None  # Existing Gobannitio full-effect preview includes its Rally.
