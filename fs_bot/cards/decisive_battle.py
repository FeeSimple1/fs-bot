"""A21 Vosegus / A57 Sabis: first required Battle, optional second there.

A Card Reference A21/A57 and §§5.1, 5.1.3, 5.4 assign the executing
human the Region and defender choices. The NP instructions and second-Battle
policy apply only to NP seats, explicit delegation, or raw callback fallback.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_playable_regions_for_state

REQUEST = 'decisive_battle'


def legal_defenders(state, faction, allowed_regions):
    """Normal Battle requires own and enemy Forces, not an NP damage score.

    §§3.2.4/3.3.4 permit static Forces too. In particular, a surviving Ally,
    Citadel, Fort or Settlement remains a legal second-Battle target.
    """
    playable = set(get_playable_regions_for_state(state, faction))
    result = {}
    for region in sorted(set(allowed_regions) & playable):
        if not count_pieces(state, region, faction):
            continue
        defenders = [enemy for enemy in rc.FACTIONS if enemy != faction
                     and count_pieces(state, region, enemy)]
        if defenders:
            result[region] = defenders
    return result


def _default_action(state, faction, request):
    from fs_bot.engine.execute import _plan_free_battle_command
    return _plan_free_battle_command(
        state, faction, request['allowed_regions'],
        second=request['phase'] == 'second')


def _default_available(state, faction, request):
    preview = deepcopy({key: value for key, value in state.items()
                        if key != 'decision_agent'})
    preview['_diviciacus_preview'] = True
    return _default_action(preview, faction, request) is not None


def validate_response(state, faction, request, response):
    """Return an error without consuming human reactions or live RNG."""
    from fs_bot.engine.free_actions import _explicit_sentinel
    if _explicit_sentinel(response, 'decline'):
        return None if request['allow_decline'] else 'The first Battle is required when possible.'
    if _explicit_sentinel(response, 'use_default'):
        if request['allow_decline'] or _default_available(state, faction, request):
            return None
        return 'No bot default applies; choose the required first Battle explicitly.'
    if not isinstance(response, dict) or set(response) != {'region', 'defender'}:
        return 'Choose exactly one Region and defender; the Event supplies all Battle modifiers.'
    region, defender = response['region'], response['defender']
    if not isinstance(region, str) or not isinstance(defender, str):
        return 'Choose an offered Region and defender.'
    choices = legal_defenders(state, faction, request['allowed_regions'])
    if defender not in choices.get(region, ()):
        return 'Choose a legal defender in an offered Battle Region on the current board.'
    return None


def _human_action(state, faction, card_id, allowed_regions, *, second=False,
                  attempt=1, previous_error=None):
    from fs_bot.engine.agent import consult_agent
    from fs_bot.engine.free_actions import _explicit_sentinel
    from fs_bot.engine.execute import _request_event_diviciacus, SA_ACTION_NONE_LABEL
    choices = legal_defenders(state, faction, allowed_regions)
    if not choices:
        return None, False
    request = {
        'kind': 'free_action', 'request_type': REQUEST, 'card_id': card_id,
        'phase': 'second' if second else 'first',
        'allowed_commands': [rc.CMD_BATTLE], 'allowed_regions': sorted(allowed_regions),
        'defenders_by_region': choices, 'max_regions': 1,
        'no_retreat': not second, 'free': True, 'with_sa': False,
        'allow_decline': second, 'validate_default_response': True,
        'attempt': attempt,
    }
    if previous_error:
        request['previous_error'] = previous_error
    request['default_available'] = _default_available(state, faction, request)
    response = consult_agent(state, faction, request)
    if response is None:
        # A raw None is intentionally the documented legacy delegation path.
        # Durable sessions never produce None for missing/invalid input.
        return _default_action(state, faction, request), False
    error = validate_response(state, faction, request, response)
    if error:
        raise ValueError(error)
    if _explicit_sentinel(response, 'use_default'):
        return _default_action(state, faction, request), True
    if response.get('decline'):
        return None, True
    region, defender = response['region'], response['defender']
    details = {'battle_plan': [{'region': region, 'target': defender}]}
    action = {'command': rc.CMD_BATTLE, 'sa': SA_ACTION_NONE_LABEL,
              'regions': [region], 'sa_regions': [], 'details': details}
    _request_event_diviciacus(state, faction, action, card_id)
    return action, True


def _resolve_one(state, faction, card_id, flag, allowed, *, second=False):
    from fs_bot.engine.execute import _EXEC_ERRORS, _execute_battle, _plan_free_battle_command
    human = faction not in state.get('non_player_factions', ())
    attempt, previous_error = 1, None
    while True:
        if human:
            action, explicit = _human_action(
                state, faction, card_id, allowed, second=second,
                attempt=attempt, previous_error=previous_error)
        else:
            action = _plan_free_battle_command(
                state, faction, allowed, second=second)
            explicit = False
        if action is None:
            return None
        chosen = action['details']['battle_plan'][0]
        region, defender = chosen['region'], chosen['target']
        label = 'battle_second' if second else 'battle'
        try:
            with free_action_scope(state, faction):
                result = _execute_battle(state, faction, action, _no_retreat=not second)
        except _EXEC_ERRORS as exc:
            return {'free_action': label, 'flag': flag, 'executed': False,
                    'reason': repr(exc), **({'region': region} if second else {})}
        if (explicit and not result.get('executed')
                and action['details'].get('diviciacus_regions')
                and result.get('reason') == 'Diviciacus agreement was refused; choose a new plan'):
            # The optional loan is refused before any Battle effect. Preserve
            # the mandatory first Battle (and the optional second's choice)
            # by returning to selection on this same board, not silently
            # accepting an unexecuted Command. Raw callback fallback retains
            # its historical one-attempt contract.
            attempt += 1
            previous_error = result['reason']
            continue
        return {'free_action': label, 'flag': flag, 'region': region,
                'defender': defender, 'result': result}


def resolve_decisive_battle(state, faction, flag):
    """Keep NP planning unchanged and rebuild the human second choice live."""
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.engine.execute import _DOUBLE_BATTLE_FLAG, _free_battle_region_set
    allowed = _free_battle_region_set(state, flag)
    card_id = 'A21' if flag == 'card_A21_first_no_retreat' else 'A57'
    first = _resolve_one(state, faction, card_id, flag, allowed)
    if first is None:
        return [{'free_action': 'battle', 'flag': flag, 'executed': False,
                 'reason': 'no valid target',
                 **({'declined_no_effect': True} if card_id == 'A21' else {})}]
    results = [first]
    double = _DOUBLE_BATTLE_FLAG[flag]
    if (not first.get('result', {}).get('executed')
            or not state.get('event_modifiers', {}).get(double)):
        return results
    _event_step(state, f'grant.{double}')
    second = _resolve_one(state, faction, card_id, double, {first['region']}, second=True)
    if second is not None:
        results.append(second)
    return results
