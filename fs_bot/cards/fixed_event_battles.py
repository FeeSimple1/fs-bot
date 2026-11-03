"""Owner-selected targets for the modified Battles on 11/25/36/45/70.

Card text supplies the exceptions. Human responses select one Region and
one defender; they cannot inject Battle modifiers or accompanying abilities.
All these follow-on Battles are required when possible (§5.1.3); card 70's
initial permission covers its March-and-Battle grant, not a later opt-out.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.map.map_data import get_playable_regions_for_state

REQUEST = 'fixed_event_battle'


def legal_defenders(state, faction, card_id, allowed_regions):
    """Apply printed scope without imposing non-player target priorities."""
    playable = set(get_playable_regions_for_state(state, faction))
    choices = {}
    for region in sorted(set(allowed_regions) & playable):
        if card_id == 25:
            # Card Tips expressly permit the three extra Losses without
            # any friendly Forces in either of the two printed Regions.
            if region not in (rc.PICTONES, rc.ARVERNI_REGION):
                continue
        elif card_id == '11a':
            if not count_pieces(state, region, faction, rc.AUXILIA):
                continue
        elif card_id == 45:
            if faction == rc.ROMANS or not (
                    count_pieces(state, region, faction)
                    or count_pieces(state, region, rc.AEDUI)):
                continue
        elif not count_pieces(state, region, faction):
            continue
        defenders = [enemy for enemy in rc.FACTIONS
                     if enemy != faction and count_pieces(state, region, enemy)]
        if card_id == 36:
            defenders = [enemy for enemy in defenders if enemy in rc.GALLIC_FACTIONS]
        elif card_id == 45:
            defenders = [enemy for enemy in defenders if enemy == rc.ROMANS]
        if defenders:
            choices[region] = defenders
    return choices


def _default_available(state, faction, choices, default_plan):
    if default_plan is None:
        return False
    trial = deepcopy({key: value for key, value in state.items()
                      if key != 'decision_agent'})
    trial['_diviciacus_preview'] = True
    action = default_plan(trial)
    if not action:
        return False
    plan = (action.get('details') or {}).get('battle_plan') or []
    return (len(plan) == 1 and plan[0].get('target')
            in choices.get(plan[0].get('region'), ()))


def make_request(state, faction, card_id, allowed_regions, default_plan=None,
                 *, attempt=1, previous_error=None):
    choices = legal_defenders(state, faction, card_id, allowed_regions)
    request = {
        'kind': 'free_action', 'request_type': REQUEST, 'card_id': card_id,
        'allowed_commands': [rc.CMD_BATTLE],
        'allowed_regions': sorted(allowed_regions),
        'defenders_by_region': choices, 'max_regions': 1,
        'with_sa': False, 'free': True, 'allow_decline': False,
        'validate_default_response': True,
        'default_available': _default_available(state, faction, choices, default_plan),
        'attempt': attempt,
    }
    if previous_error:
        request['previous_error'] = previous_error
    return request


def validate_response(state, faction, request, response):
    """Validate current legal targets without executing or consuming input."""
    from fs_bot.engine.free_actions import _explicit_sentinel
    if _explicit_sentinel(response, 'decline'):
        return 'This Event Battle is required when possible.'
    if _explicit_sentinel(response, 'use_default'):
        return (None if request.get('default_available') else
                'No legal default applies; choose the required Battle explicitly.')
    if not isinstance(response, dict) or set(response) != {'region', 'defender'}:
        return 'Choose exactly one Region and defender; the Event supplies all Battle modifiers.'
    region, defender = response['region'], response['defender']
    if not isinstance(region, str) or not isinstance(defender, str):
        return 'Choose an offered Region and defender.'
    choices = legal_defenders(state, faction, request['card_id'], request['allowed_regions'])
    if defender not in choices.get(region, ()):
        return 'Choose a legal defender in an offered Battle Region on the current board.'
    return None


def resolve(state, faction, card_id, allowed_regions, default_plan, execute_action):
    """Choose and resolve once, retrying an explicit plan after a refused loan.

    Returns ``(action, result)`` or ``(None, None)`` when no Battle applies.
    NPCs and legacy raw callback deferral keep the existing planner. Missing
    durable input never uses that fallback: the session suspends beforehand.
    """
    from fs_bot.engine.agent import consult_agent
    from fs_bot.engine.free_actions import _explicit_sentinel
    from fs_bot.engine.execute import _request_event_diviciacus, SA_ACTION_NONE_LABEL
    from fs_bot.engine.diviciacus_planning import clear_confirmation
    from fs_bot.commands.common import free_action_scope
    human = (faction not in state.get('non_player_factions', ())
             and not (faction == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS))
    attempt, previous_error = 1, None
    while True:
        explicit = False
        if human:
            request = make_request(state, faction, card_id, allowed_regions,
                                   default_plan, attempt=attempt,
                                   previous_error=previous_error)
            if not request['defenders_by_region']:
                return None, None
            response = consult_agent(state, faction, request)
            if response is not None:
                explicit = True
                error = validate_response(state, faction, request, response)
                if error:
                    raise ValueError(error)
                if _explicit_sentinel(response, 'use_default'):
                    action = default_plan(state)
                else:
                    region, defender = response['region'], response['defender']
                    action = {'command': rc.CMD_BATTLE, 'sa': SA_ACTION_NONE_LABEL,
                              'regions': [region], 'sa_regions': [],
                              'details': {'battle_plan': [{'region': region, 'target': defender}]}}
                    _request_event_diviciacus(state, faction, action, card_id)
            else:
                action = default_plan(state)
        else:
            action = default_plan(state)
        if action is None:
            return None, None
        try:
            with free_action_scope(state, faction):
                result = execute_action(action)
        finally:
            clear_confirmation(state, faction, action)
        if (explicit and result.get('executed') is False
                and result.get('reason') == 'Diviciacus agreement was refused; choose a new plan'):
            attempt += 1
            previous_error = result['reason']
            continue
        return action, result
