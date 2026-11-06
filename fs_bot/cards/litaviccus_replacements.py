"""Unshaded Litaviccus choices and timed replacement pairs.

Card Reference 45 and §§5.1–5.1.3, 8.3.1 and 8.4.1.
"""
from collections import defaultdict

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, get_available, place_piece, remove_piece
from fs_bot.cards.base_piece_choices import (
    LITAVICCUS_PER_REGION, LITAVICCUS_REGIONS, STATES, _consult, _default, _take_cohorts,
    choice_request, validate_response,
)
from fs_bot.map.map_data import get_playable_regions_for_state, is_region_playable


def effective(state):
    return bool(state['resources'].get(rc.ARVERNI, 0) or choice_request(state, 45)['available'])


def resolve_replacements(state, params):
    from fs_bot.cards.card_effects import _event_entries, _event_step

    if 'regions' in params:
        if 'piece_choices' in params:
            raise ValueError('Choose one Litaviccus replacement plan format')
        groups = _legacy_groups(state, params['regions'])
    else:
        _event_step(state, '45.piece_choice')
        request = choice_request(state, 45)
        npc = request['owner'] in state.get('non_player_factions', ())
        if 'piece_choices' in params:
            response = {'selections': params['piece_choices']}
        elif request['available'] and not npc:
            response = _consult(state, request)
        else:
            response = None
        if response is None or _default(response):
            selections = _default_selections(state, request, npc)
        else:
            selections = validate_response(state, request, response)['selections']
        grouped = defaultdict(list)
        for entry in selections:
            grouped[entry['region']].extend([entry['piece_state']] * entry['count'])
        groups = [{'region': region, 'pieces': pieces} for region, pieces in grouped.items()]

    for group in _event_entries(state, '45.regions', groups):
        region = group['region']
        for visibility in _event_entries(state, f'45.replacements.{region}', group['pieces']):
            order = STATES if visibility is None else (visibility,)
            actual = next((ps for ps in order
                           if count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, ps)), None)
            if actual is None:
                continue
            remove_piece(state, region, rc.ARVERNI, rc.WARBAND, piece_state=actual)
            if (is_region_playable(state, region, rc.AEDUI)
                    and get_available(state, rc.AEDUI, rc.WARBAND) > 0):
                place_piece(state, region, rc.AEDUI, rc.WARBAND)


def _legacy_groups(state, entries):
    if not isinstance(entries, list) or len(entries) > LITAVICCUS_REGIONS:
        raise ValueError('Litaviccus selects up to two distinct Regions')
    legal = get_playable_regions_for_state(state)
    seen, groups = set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Each Litaviccus Region requires a Region and optional count')
        region, count = entry.get('region'), entry.get('count', LITAVICCUS_PER_REGION)
        if not isinstance(region, str) or region not in legal or region in seen:
            raise ValueError('Litaviccus selects distinct playable Regions')
        if type(count) is not int or not 0 <= count <= LITAVICCUS_PER_REGION:
            raise ValueError('Litaviccus replaces zero to two Warbands per Region')
        seen.add(region)
        groups.append(dict(entry, pieces=[None] * count))
    return groups


def _default_selections(state, request, npc):
    from fs_bot.bots.bot_common import random_select

    by_region = defaultdict(list)
    for entry in request['available']:
        by_region[entry['region']].append(entry)
    scores = {region: min(LITAVICCUS_PER_REGION, sum(entry['count'] for entry in entries))
              for region, entries in by_region.items()}
    selections = []
    for _ in range(min(LITAVICCUS_REGIONS, len(scores))):
        best = max(scores.values())
        tied = [region for region, count in scores.items() if count == best]
        region = random_select(state, tied) if npc else tied[0]
        cohorts = by_region[region]
        if request['owner'] == rc.ARVERNI:
            cohorts = reversed(cohorts)
        selections.extend(_take_cohorts(cohorts, scores.pop(region)))
    return selections
