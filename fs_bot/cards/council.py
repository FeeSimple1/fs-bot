"""Card 47: executor selections and each beneficiary's private Council choice.

Player Factions are the seats defined in §1.5/A1.5, including their §8
Non-player substitutes. Germans never qualify a Region's non-German count;
in Ariovistus they can nevertheless receive the benefit in Arverni's printed
initiative position (§A2.3.2). Private future cards belong only to the chosen
beneficiary's request, never to public Event modifiers or execution results.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.card_data import get_card
from fs_bot.cards.card_text import get_card_text
from fs_bot.engine.agent import consult_agent
from fs_bot.engine.free_actions import (
    command_options, execute_free_action_plan, validate_free_action_response,
)
from fs_bot.map.map_data import get_playable_regions_for_state

COUNCIL_SELECTION = 'council_selection'
COUNCIL_CHOICE = 'council_choice'


def _sentinel(response, key):
    return (isinstance(response, dict) and set(response) == {key}
            and response[key] is True)


def faction_order(state):
    """The order printed on Council, with the scenario's player-seat mapping."""
    from fs_bot.engine.game_engine import _faction_order_for_card
    return _faction_order_for_card(state, 47)


def eligible_regions(state):
    """Regions satisfying both the meeting condition and 2+ player choices."""
    order = faction_order(state)
    candidates = {}
    for region in sorted(get_playable_regions_for_state(state)):
        present = [f for f in rc.FACTIONS if count_pieces(state, region, f)]
        players = [f for f in order if f in present]
        if len([f for f in present if f != rc.GERMANS]) >= 2 and len(players) >= 2:
            candidates[region] = players
    return candidates


def selection_request(state):
    return {'kind': COUNCIL_SELECTION, 'card_id': 47,
            'regions': eligible_regions(state), 'minimum_factions': 2}


def validate_selection(state, response):
    if not isinstance(response, dict) or set(response) != {'region', 'target_factions'}:
        raise ValueError('Council requires a Region and target_factions.')
    region, targets = response['region'], response['target_factions']
    candidates = eligible_regions(state)
    if not isinstance(region, str) or region not in candidates:
        raise ValueError('Council needs a Region with at least two non-German Factions and two player Factions.')
    if (not isinstance(targets, list) or len(targets) < 2
            or any(not isinstance(f, str) for f in targets)
            or len(targets) != len(set(targets))
            or not set(targets).issubset(candidates[region])):
        raise ValueError('Select at least two distinct player Factions with pieces in the Council Region.')
    return response


def default_selection(state):
    """Compatibility fallback, not a rule for NP Event selection.

All NP sheets decline Council. Raw callers without a decision agent, and
humans explicitly accepting an interface default, choose a seeded Region
and all player Factions there. Normal NP Event dispatch remains unchanged.
"""
    candidates = eligible_regions(state)
    if not candidates:
        return None
    region = state['rng'].choice(list(candidates))
    return {'region': region, 'target_factions': list(candidates[region])}


def command_request(faction):
    return {'kind': 'free_action', 'request_type': 'event_command', 'card_id': 47,
            'allowed_commands': command_options(faction), 'allowed_regions': None,
            'max_regions': 1, 'with_sa': False, 'free': True}


def private_cards(state):
    """The deck's first entry is already face up (§2.2); inspect the next two."""
    from fs_bot.engine.game_engine import _faction_order_for_card
    cards = []
    for card_id in state.get('deck', [])[1:3]:
        # Live decks store the canonical Winter sentinel, while card metadata
        # uses W1-W5. Winter has no Event text in the card-reference source.
        card = None if card_id == rc.WINTER_CARD else get_card(card_id, state['scenario'])
        title = card.title if card else rc.WINTER_CARD
        order = list(_faction_order_for_card(state, card_id)) if card else []
        symbols = dict(card.np_symbols) if card else {}
        if state['scenario'] in rc.ARIOVISTUS_SCENARIOS and rc.ARVERNI in symbols:
            symbols[rc.GERMANS] = symbols.pop(rc.ARVERNI)
        cards.append({'card_id': card_id, 'title': title,
                      'faction_order': order, 'np_symbols': symbols,
                      'is_winter': not card or card.is_winter,
                      'has_carnyx_trigger': bool(card and card.has_carnyx_trigger),
                      'text': get_card_text(card_id, state['scenario'],
                                            state.get('card_edition'))})
    return cards


def choice_request(state, faction, selection):
    request = command_request(faction)
    request.update(kind=COUNCIL_CHOICE, region=selection['region'],
                   target_factions=list(selection['target_factions']),
                   private_cards=private_cards(state))
    return request


def validate_choice(state, faction, response):
    if (response == {'choice': 'eligible'} or _sentinel(response, 'decline')
            or _sentinel(response, 'use_default')):
        return response
    if (not isinstance(response, dict)
            or set(response) & {'choice', 'decline', 'use_default'}):
        raise ValueError('Choose Eligible, decline, or supply a complete free Limited Command.')
    error = validate_free_action_response(state, faction, command_request(faction), response)
    if error:
        raise ValueError(error)
    return response


def validate_response(state, request, response):
    if _sentinel(response, 'use_default'):
        return response
    if request['kind'] == COUNCIL_SELECTION:
        return validate_selection(state, response)
    return validate_choice(state, request['faction'], response)


def _become_eligible(state, faction):
    # The current Event wins over older contrary Event effects (§5.1.2).
    state.setdefault('eligibility', {})[faction] = rc.ELIGIBLE
    (state.get('forced_ineligible') or {}).pop(faction, None)
    stay = state.setdefault('stay_eligible', [])
    if faction not in stay:
        stay.append(faction)


def _resolve(state, executor, selection):
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "47.selection")
    if selection is None:
        params = state.get('event_params')
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError('Council event_params must be an object.')
        if 'region' in params or 'target_factions' in params:
            selection = {key: params[key] for key in ('region', 'target_factions') if key in params}
    if selection is None:
        if not eligible_regions(state):
            return [{'free_action': 'council', 'flag': 'card_47', 'executed': False,
                     'reason': 'No Region supports a Council of two player Factions.'}]
        selection = consult_agent(state, executor, selection_request(state))
        if selection is None or _sentinel(selection, 'use_default'):
            selection = default_selection(state)
    validate_selection(state, selection)
    # Freeze the invited subset before any Command moves or removes pieces.
    targets = [f for f in faction_order(state) if f in selection['target_factions']]
    selection = {'region': selection['region'], 'target_factions': targets}
    results = []
    for faction in targets:
        from fs_bot.cards.card_effects import _event_step
        _event_step(state, "47.benefit")
        request = choice_request(state, faction, selection)
        response = consult_agent(state, faction, request)
        default = response is None or _sentinel(response, 'use_default')
        if default:
            # §8.2.3: randomize an otherwise unprioritized Event choice.
            # §8.4: carry out an action rather than voluntarily declining it.
            mode = state['rng'].choice(('eligible', 'command'))
            response = {'choice': 'eligible'} if mode == 'eligible' else None
        if response is not None:
            validate_choice(state, faction, response)
        result = {'flag': 'card_47', 'region': selection['region'], 'faction': faction}
        if response == {'choice': 'eligible'}:
            _become_eligible(state, faction)
            result.update(free_action='stay_eligible', executed=True)
        elif _sentinel(response, 'decline'):
            result.update(free_action='council', executed=False, reason='Council benefit declined')
        else:
            if default:
                from fs_bot.engine.execute import _resolve_free_command
                from fs_bot.commands.common import free_action_scope
                with free_action_scope(state, faction):
                    outcome = _resolve_free_command(state, faction, limited=True, _consult=False)
            else:
                outcome = execute_free_action_plan(state, faction, command_request(faction), response)
            result.update(free_action='free_command', result=outcome)
        results.append(result)
    return results


def resolve_council(state, executor, selection=None):
    """Resolve atomically, including a later beneficiary's pending decision."""
    snapshot = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        return _resolve(state, executor, selection)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if card_turn is not None:
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise
