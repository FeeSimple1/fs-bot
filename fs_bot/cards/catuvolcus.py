"""Unshaded Catuvolcus, Card Reference 61 and §§5.1–5.1.3, 8.3–8.4.

The Ally and Warband removals are separate choices. The Warband offer
uses the board after the Allies and the intervening timing window.
"""
from collections import defaultdict

from fs_bot import rules_consts as rc
from fs_bot.cards.base_piece_choices import (
    KIND, STATES, _consult, _default, _remove_cohorts, _required_removal_request,
    _take_cohorts, validate_response,
)


WARBAND_LIMIT = 5


def _target_factions(state, npc):
    if npc != rc.AEDUI:
        return rc.FACTIONS
    enemies = ((rc.GERMANS, rc.BELGAE) if state['scenario'] in rc.ARIOVISTUS_SCENARIOS
               else (rc.ARVERNI, rc.BELGAE))
    return tuple(f for f in enemies if f not in state.get('non_player_factions', ()))


def _ally_targets(state, factions):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region

    return [{'tribe': tribe, 'region': rc.NERVII, 'target_faction': info['allied_faction']}
            for tribe, info in sorted(state['tribes'].items())
            if info.get('allied_faction') in factions
            and _tribe_region(state, tribe) == rc.NERVII
            and _tribe_piece_type(state, tribe) == rc.ALLY]


def _warbands(state, factions):
    return [entry for faction in factions if faction != rc.ROMANS
            for entry in _required_removal_request(state, 61, None, faction, (rc.NERVII,),
                                                    {rc.WARBAND: WARBAND_LIMIT})['available']]


def effective(state, npc=None):
    factions = _target_factions(state, npc)
    return bool(_ally_targets(state, factions) or _warbands(state, factions))


def choice_request(state, step):
    owner = state.get('executing_faction')
    npc = owner if owner in state.get('non_player_factions', ()) else None
    factions = _target_factions(state, npc)
    request = {'kind': KIND, 'card_id': 61, 'owner': owner, 'step': step}
    if step == 'allies':
        return dict(request, targets=_ally_targets(state, factions))
    available = _warbands(state, factions)
    return dict(request, available=available,
                required={rc.WARBAND: min(WARBAND_LIMIT, sum(row['count'] for row in available))})


def validate_allies(state, request, response):
    if set(response) != {'tribes'} or not isinstance(response['tribes'], list):
        raise ValueError('Choose one or more offered Allies of the same faction')
    live = choice_request(state, 'allies')['targets']
    offered = {row['tribe']: row['target_faction'] for row in request['targets'] if row in live}
    tribes = response['tribes']
    if (any(not isinstance(tribe, str) or tribe not in offered for tribe in tribes)
            or len(set(tribes)) != len(tribes)
            or len({offered[tribe] for tribe in tribes}) > 1
            or (not tribes and (request['targets'] or live))):
        raise ValueError('Choose distinct offered Allies of a single faction in Nervii')
    return response


def resolve(state, params):
    from fs_bot.cards.card_effects import _event_entries, _event_step, _unally_tribe

    if 'piece_choices' in params and 'warband_removals' in params:
        raise ValueError('Choose one Catuvolcus Warband plan format')
    if 'ally_removals' not in params:
        _event_step(state, '61.ally_choice')
    request = choice_request(state, 'allies')
    explicit = {'tribes': params['ally_removals']} if 'ally_removals' in params else None
    response = _choose(state, request, explicit, bool(request['targets']))
    tribes = response['tribes'] if response is not None else _default_allies(state, request)
    for tribe in _event_entries(state, '61.allies', tribes):
        if any(row['tribe'] == tribe and row in request['targets']
               for row in choice_request(state, 'allies')['targets']):
            _unally_tribe(state, tribe)

    if 'warband_removals' in params:
        _legacy_warbands(state, params['warband_removals'])
        return
    _event_step(state, '61.warband_choice')
    request = choice_request(state, 'warbands')
    explicit = {'selections': params['piece_choices']} if 'piece_choices' in params else None
    response = _choose(state, request, explicit, bool(request['required'][rc.WARBAND]))
    selections = (response['selections'] if response is not None else
                  _default_warbands(state, request, request['required'][rc.WARBAND]))
    _remove_cohorts(state, selections)


def _choose(state, request, explicit, possible):
    response = explicit
    if response is None and possible and request['owner'] not in state.get('non_player_factions', ()):
        response = _consult(state, request)
    if response is None or _default(response):
        return None
    return validate_response(state, request, response)


def _default_allies(state, request):
    from fs_bot.bots.bot_common import get_faction_targeting_order

    owner = request['owner']
    order = get_faction_targeting_order(owner, state['scenario'])
    groups = defaultdict(list)
    for row in request['targets']:
        groups[row['target_faction']].append(row['tribe'])
    if not groups:
        return []
    faction = max(groups, key=lambda f: (f != owner, len(groups[f]), -order.index(f) if f in order else 0))
    return groups[faction]


def _default_warbands(state, request, remaining):
    from fs_bot.bots.bot_common import get_faction_targeting_order

    owner = request['owner']
    order = get_faction_targeting_order(owner, state['scenario'])

    def priority(row):
        own = row['target_faction'] == owner
        visibility = STATES.index(row['piece_state'])
        return (own, -visibility if own else visibility,
                0 if own else order.index(row['target_faction']))

    return _take_cohorts(sorted(request['available'], key=priority), remaining)


def _legacy_warbands(state, removals):
    from fs_bot.cards.card_effects import _event_entries

    if not isinstance(removals, list):
        raise ValueError('Catuvolcus Warband preferences must be a list')
    remaining = WARBAND_LIMIT
    for entry in _event_entries(state, '61.warbands', removals):
        if not remaining:
            break
        if (not isinstance(entry, dict) or entry.get('faction') not in rc.FACTIONS
                or type(entry.get('count', 1)) is not int or entry.get('count', 1) <= 0):
            raise ValueError('Catuvolcus Warband preferences require a faction and positive count')
        request = choice_request(state, 'warbands')
        cohorts = [row for row in request['available'] if row['target_faction'] == entry['faction']]
        picked = _take_cohorts(cohorts, min(remaining, entry.get('count', 1)))
        _remove_cohorts(state, picked)
        remaining -= sum(row['count'] for row in picked)
    _remove_cohorts(state, _default_warbands(state, choice_request(state, 'warbands'), remaining))
