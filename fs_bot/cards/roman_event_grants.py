"""Roman-owned compound grants: A20 Morbihan and A58 Aduatuci.

The optional choice precedes every effect. Once accepted, §5.1.3 resolves
the components in order, with fresh Command choices on the resulting board.
Only engine requests carry Seize exceptions; action details never grant them.
"""
from contextlib import contextmanager
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, remove_piece
from fs_bot.commands.seize import count_dispersed_on_map, validate_seize_region
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan
from fs_bot.map.map_data import get_adjacent_for_state, get_tribes_in_region_for_state

SEIZE_GRANT = '_roman_event_seize_grant'


def accepts_morbihan(state):
    return any(count_pieces(state, region, rc.ROMANS)
               for region in {rc.VENETI, *get_adjacent_for_state(state, rc.VENETI)})


def accept_request(card_id):
    return {'kind': 'free_action', 'request_type': 'roman_event_accept',
            'card_id': card_id, 'acting_faction': rc.ROMANS,
            'free': True, 'with_sa': False, 'allow_decline': True,
            'validate_default_response': True}


def validate_accept(response):
    if not (isinstance(response, dict) and set(response) == {'accept'}
            and response['accept'] is True):
        raise ValueError('Accept the entire Roman benefit with {accept: true}, or decline.')


def command_request(state, card_id, command):
    regions = [rc.VENETI] if card_id == 'A20' else sorted(rc.BELGICA_REGIONS)
    if command == rc.CMD_SEIZE:
        regions = [region for region in regions if validate_seize_region(state, region)[0]]
    else:
        # §3.2.4 permits any Roman pieces, including static-only Forces.
        regions = [r for r in regions if count_pieces(state, r, rc.ROMANS)
                   and any(count_pieces(state, r, f) for f in rc.FACTIONS if f != rc.ROMANS)]
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'card_id': card_id, 'acting_faction': rc.ROMANS,
               'roman_event_card': card_id,
               'allowed_commands': [command], 'allowed_regions': regions,
               'free': True, 'with_sa': False, 'allow_decline': False,
               'validate_default_response': True}
    if command == rc.CMD_SEIZE:
        request.update(request_type='roman_event_seize', seize_as_if_control=True,
                       seize_no_rally=True, seize_no_harassment=card_id == 'A58',
                       dispersible_tribes={r: subdued_tribes(state, r) for r in regions},
                       available_markers=4 - count_dispersed_on_map(state))
    else:
        request['request_type'] = 'roman_event_battle'
        request['battle_targets'] = {r: [f for f in rc.FACTIONS
            if f != rc.ROMANS and count_pieces(state, r, f)] for r in regions}
    return request


def subdued_tribes(state, region):
    """All physical choices, even when fewer markers than Tribes remain."""
    return [tribe for tribe in get_tribes_in_region_for_state(state, region)
            if state['tribes'][tribe].get('allied_faction') is None
            and state['tribes'][tribe].get('status') is None]


@contextmanager
def seize_scope(state, request):
    """Install only the trusted request's temporary, Region-limited grant."""
    missing = object()
    previous = state.get(SEIZE_GRANT, missing)
    grant = request if request.get('request_type') == 'roman_event_seize' else {}
    if grant:
        state[SEIZE_GRANT] = grant
    else:
        # Ordinary grants must not acquire a new empty frame in their durable
        # board signatures. Nested unrelated actions also lose these privileges.
        state.pop(SEIZE_GRANT, None)
    try:
        yield
    finally:
        if previous is missing:
            state.pop(SEIZE_GRANT, None)
        else:
            state[SEIZE_GRANT] = previous


def seize_flags(state, region):
    grant = state.get(SEIZE_GRANT) or {}
    if region not in grant.get('allowed_regions', ()):
        return False, False, False
    return (bool(grant.get('seize_as_if_control')), bool(grant.get('seize_no_rally')),
            bool(grant.get('seize_no_harassment')))


def validate_seize_plan(state, request, action):
    regions = action.get('regions')
    details = action.get('details')
    if (not isinstance(regions, list) or not regions
            or any(not isinstance(r, str) for r in regions)
            or len(regions) != len(set(regions))
            or not set(regions) <= set(request['allowed_regions'])):
        raise ValueError('Choose distinct offered Seize Regions in execution order.')
    if (not isinstance(details, dict) or set(details) - {'disperse_tribes', 'diviciacus_regions'}
            or 'disperse_tribes' not in details
            or not isinstance(details['disperse_tribes'], dict)
            or set(details['disperse_tribes']) != set(regions)):
        raise ValueError('Supply disperse_tribes for every selected Seize Region (empty lists permit Forage only).')
    chosen = []
    for region, tribes in details['disperse_tribes'].items():
        if (not isinstance(tribes, list) or any(not isinstance(t, str) for t in tribes)
                or len(tribes) != len(set(tribes))
                or not set(tribes) <= set(subdued_tribes(state, region))):
            raise ValueError('Choose distinct Subdued Tribes in their selected Region.')
        chosen.extend(tribes)
    if len(chosen) + count_dispersed_on_map(state) > 4:
        raise ValueError('The selected Tribes exceed the available Dispersed markers.')


def validate_cooperation(request, action):
    if 'command_parts' in (action.get('details') or {}):
        # These grants have no SA/interruption. A fake single nested portion
        # must not conceal the top-level Command from regional validation.
        raise ValueError('This Event Command does not permit command_parts.')
    regions = (action.get('details') or {}).get('diviciacus_regions', [])
    if (not isinstance(regions, list) or any(not isinstance(r, str) for r in regions)
            or not set(regions) <= set(request['allowed_regions'])):
        raise ValueError('Diviciacus cooperation must stay within the granted Command Regions.')


def _remove_arverni(state):
    from fs_bot.cards.card_effects import _unally_faction_tribes_in_region, clear_allied_tribe
    _unally_faction_tribes_in_region(state, rc.VENETI, rc.ARVERNI)
    for piece in (rc.ALLY, rc.CITADEL):
        while count_pieces(state, rc.VENETI, rc.ARVERNI, piece):
            remove_piece(state, rc.VENETI, rc.ARVERNI, piece)
            clear_allied_tribe(state, rc.VENETI, rc.ARVERNI, piece)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        n = count_pieces_by_state(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, visibility)
        if n:
            remove_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, n, piece_state=visibility)


def default_seize_plan(state, request):
    """§§8.2.3, 8.3.4, 8.8.5: safe Dispersal first, then all Forage.

Event exceptions change actual Dispersal/Harassment legality, not Roman
priorities. Equal Regions and physical Tribes use the seeded tie-breaker.
"""
    from fs_bot.bots.bot_common import random_select
    from fs_bot.commands.seize import calculate_forage
    from fs_bot.engine.game_engine import get_sop_factions
    players = set(get_sop_factions(state)) - set(state.get('non_player_factions', ())) - {rc.ROMANS}
    regions = [r for r in request['allowed_regions'] if request['seize_no_harassment']
               or not any(count_pieces_by_state(state, r, f, rc.WARBAND, rc.HIDDEN) >= 3
                          for f in rc.FACTIONS if f != rc.ROMANS)]
    def priority(region):
        return (bool([t for t in subdued_tribes(state, region) if t != rc.TRIBE_HELVII]),
                any(count_pieces(state, region, f) for f in players),
                region in rc.BELGICA_REGIONS)
    ordered = []
    while regions:
        best = max(priority(r) for r in regions)
        region = random_select(state, [r for r in regions if priority(r) == best])
        regions.remove(region)
        ordered.append(region)
    markers = 4 - count_dispersed_on_map(state)
    disperse = {}
    for region in ordered:
        candidates = [t for t in subdued_tribes(state, region) if t != rc.TRIBE_HELVII]
        selected = []
        while candidates and markers:
            tribe = random_select(state, candidates)
            candidates.remove(tribe)
            selected.append(tribe)
            markers -= 1
        if selected or calculate_forage(state, region, []) > 0:
            disperse[region] = selected
    if not disperse:
        return None
    return {'command': rc.CMD_SEIZE, 'regions': list(disperse), 'sa': 'No SA',
            'sa_regions': [], 'details': {'disperse_tribes': disperse}}


def _component(state, card_id, command):
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, f'{card_id}.roman_{command.lower()}')
    attempt, previous_error = 1, None
    while True:
        # Live timing choices can remove a target after a default was
        # validated. Rebuild every retry from the actual resulting board;
        # §5.1.3 does not require an action that has become impossible.
        request = command_request(state, card_id, command)
        if not request['allowed_regions']:
            return {'executed': False, 'declined_no_effect': True,
                    'reason': f'No legal {command} Region.'}
        if attempt > 1:
            request.update(attempt=attempt, previous_error=previous_error)
        from fs_bot.engine.agent import consult_agent
        from fs_bot.engine.free_actions import validate_free_action_response, _explicit_sentinel
        action = consult_agent(state, rc.ROMANS, request)
        explicit = action is not None
        if explicit:
            error = validate_free_action_response(state, rc.ROMANS, request, action)
            if error:
                raise ValueError(error)
            if _explicit_sentinel(action, 'use_default'):
                action = None
        if action is None:
            if command == rc.CMD_BATTLE:
                result = _default_battle(state, request)
                if not explicit or result.get('executed'):
                    return result
                # An accepted default was validated optimistically. Actual
                # lender refusal can exhaust its NP priorities; that does not
                # satisfy the human's accepted mandatory Battle component.
                attempt += 1
                previous_error = result.get('reason', 'The default Battle did not execute.')
                continue
            else:
                action = default_seize_plan(state, request)
                if action is None:
                    return {'executed': False, 'declined_no_effect': True,
                            'reason': 'Roman Seize priorities select no Region.'}
        result = execute_free_action_plan(state, rc.ROMANS, request, action)
        if (explicit and not result.get('executed')
                and result.get('reason') == 'Diviciacus agreement was refused; choose a new plan'):
            # Refusal precedes every Command effect. The accepted mandatory
            # component remains to be chosen, on this unchanged current board.
            attempt += 1
            previous_error = result['reason']
            continue
        return result


def _default_battle(state, request):
    from fs_bot.engine.execute import _resolve_free_command
    return _resolve_free_command(state, rc.ROMANS,
        allowed_regions=request['allowed_regions'],
        exclude_commands=[rc.CMD_RECRUIT, rc.CMD_MARCH, rc.CMD_SEIZE],
        with_sa=False, _consult=False)


def validate_default(state, request):
    """Explicit default cannot evade an accepted, possible human component.

Raw callbacks returning None keep their documented NP-fallback contract.
Durable users instead supply a legal plan if Roman priorities select none.
"""
    sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    sim['_diviciacus_preview'] = True
    if request['allowed_commands'] == [rc.CMD_SEIZE]:
        valid = default_seize_plan(sim, request) is not None
    else:
        valid = bool(_default_battle(sim, request).get('executed'))
    if not valid:
        raise ValueError('Roman bot priorities select no action; supply a legal plan for the accepted benefit.')


def _resolve(state, card_id):
    flag = 'card_A20_free_seize_veneti' if card_id == 'A20' else 'card_A58_roman_battle_seize'
    if card_id == 'A20' and not accepts_morbihan(state):
        return []
    response = consult_free_action(state, rc.ROMANS, accept_request(card_id))
    if response and response.get('decline'):
        return [{'free_action': 'roman_benefit', 'flag': flag, 'executed': False,
                 'declined_no_effect': True, 'reason': 'Romans declined the compound Event benefit.'}]
    results = []
    if card_id == 'A20':
        _remove_arverni(state)
    else:
        battle = _component(state, card_id, rc.CMD_BATTLE)
        results.append({'free_action': 'battle', 'flag': flag, 'result': battle})
    seize = _component(state, card_id, rc.CMD_SEIZE)
    results.append({'free_action': 'seize', 'flag': flag, 'result': seize,
                    **({key: seize[key] for key in ('executed', 'declined_no_effect', 'reason')
                        if key in seize} if seize.get('executed') is False else {})})
    return results


def resolve(state, card_id):
    """A pause or invalid later component rolls back the whole compound grant."""
    snapshot = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        return _resolve(state, card_id)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if card_turn is not None:
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise
