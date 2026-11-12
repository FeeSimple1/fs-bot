"""Numeric58 shaded: executor chooses German groups and a single Fort."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import consult_free_action, _explicit_sentinel
from fs_bot.engine.march_choices import chooser_scope
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

REQUEST = 'aduatuca_march'
FLAG = 'card_58_german_march_battle'


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})


def targets(state):
    return [r for r in sorted(get_playable_regions_for_state(state, rc.GERMANS))
            if count_pieces(state, r, rc.ROMANS, rc.FORT)]


def origins(state, destination):
    playable = set(get_playable_regions_for_state(state, rc.GERMANS))
    return {r: count_pieces(state, r, rc.GERMANS, rc.WARBAND)
            for r in sorted(set(get_adjacent_for_state(state, destination, rc.GERMANS)) & playable)
            if count_pieces(state, r, rc.GERMANS, rc.WARBAND)}


def make_request(state):
    return {'kind': 'free_action', 'request_type': REQUEST, 'card_id': 58,
            'acting_faction': rc.GERMANS, 'destinations': targets(state),
            'origins_by_destination': {r: origins(state, r) for r in targets(state)},
            'free': True, 'with_sa': False, 'allow_decline': False,
            'validate_default_response': True}


def validate_response(state, request, response):
    try:
        _validate(state, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return str(exc)
    return None


def _validate(state, response):
    if _explicit_sentinel(response, 'use_default'):
        return
    if not isinstance(response, dict) or set(response) != {'destination', 'marches'}:
        raise ValueError('Choose one Fort destination and an ordered list of German March groups.')
    destination, marches = response['destination'], response['marches']
    if not isinstance(destination, str) or destination not in targets(state):
        raise ValueError('Choose a playable Region with a Roman Fort.')
    if not isinstance(marches, list):
        raise ValueError('Marches must be a list; an empty list leaves only resident Germans to Ambush.')
    available, selected = origins(state, destination), set()
    for group in marches:
        if not isinstance(group, dict) or set(group) != {'origin', 'warbands'}:
            raise ValueError('Each group needs only origin and warbands.')
        origin, n = group['origin'], group['warbands']
        if not isinstance(origin, str) or origin not in available or origin in selected:
            raise ValueError('Select each adjacent German origin at most once (§3.4.2).')
        if type(n) is not int or not 0 <= n <= available[origin]:
            raise ValueError('Choose an available number of German Warbands; zero selects an origin for hiding only.')
        # Use the actual movement validator, including active geography effects.
        from fs_bot.cli.human_plan import _march_routes
        sim = _copy(state)
        sim['_diviciacus_preview'] = True
        with free_action_scope(sim, rc.GERMANS):
            probe = {rc.WARBAND: max(1, n), rc.LEADER: None, rc.LEGION: 0, rc.AUXILIA: 0}
            if [destination] not in _march_routes(sim, origin, rc.GERMANS, probe):
                raise ValueError('This origin cannot make the adjacent German March.')
        selected.add(origin)


def _resolve(state, executor):
    from fs_bot.engine.execute import _resolve_card58_german_ambush_default, _march_with_harassment
    from fs_bot.engine.battle_capabilities import resolve_single
    from fs_bot.commands.march import _flip_origin_pieces
    from fs_bot.engine.action_windows import window
    if executor in state.get('non_player_factions', ()):
        return _resolve_card58_german_ambush_default(state)
    if not targets(state):
        return [{'free_action': 'ambush', 'flag': FLAG, 'executed': False,
                 'declined_no_effect': True, 'reason': 'No Roman Fort destination.'}]
    response = consult_free_action(state, executor, make_request(state))
    if response is None:
        return _resolve_card58_german_ambush_default(state)
    destination = response['destination']
    marched, movement = 0, []
    # Every source differs from the common destination. Arrivals therefore
    # cannot join a subsequent group; each initial origin is selected once.
    with free_action_scope(state, rc.GERMANS), chooser_scope(state, rc.GERMANS, executor):
        for entry in response['marches']:
            origin, n = entry['origin'], entry['warbands']
            if n:
                before = count_pieces(state, destination, rc.GERMANS, rc.WARBAND)
                final = _march_with_harassment(state, rc.GERMANS, origin, [destination],
                                               {rc.WARBAND: n, rc.LEADER: False})
                moved = count_pieces(state, destination, rc.GERMANS, rc.WARBAND) - before
                marched += moved
                movement.append({'origin': origin, 'final_region': final, 'warbands': moved})
            else:
                window(state, 'march_origin', region=origin, marching_faction=rc.GERMANS)
                _flip_origin_pieces(state, origin, rc.GERMANS)
                movement.append({'origin': origin, 'final_region': origin, 'warbands': 0})
    total = count_pieces(state, destination, rc.GERMANS, rc.WARBAND)
    if not total or not count_pieces(state, destination, rc.ROMANS):
        return [{'free_action': 'ambush', 'flag': FLAG, 'region': destination,
                 'marches': movement, 'warbands_marched': marched, 'executed': bool(marched),
                 'declined_no_effect': not bool(marched), 'reason': 'No German/Roman force remains for Ambush.'}]
    battle = resolve_single(state, destination, rc.GERMANS, rc.ROMANS,
                            is_ambush=True, ignore_fort=True)
    return [{'free_action': 'ambush', 'flag': FLAG, 'region': destination,
             'defender': rc.ROMANS, 'warbands_gathered': total,
             'warbands_marched': marched, 'marches': movement, 'result': battle}]


def resolve(state, executor):
    snapshot = _copy(state)
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        return _resolve(state, executor)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if card_turn is not None:
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise
