"""Card 51 shaded: exact replacements and a Command with the new Germans.

Card Reference 51 and its Tips; §§3.4, 5.1.1, 5.4, 8.2.3. The acting
German pieces remain physically German, and retain intrinsic German rules.
"""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.cards.base_piece_choices import (
    STATES, SURUS_LIMIT, _consult, _default, choice_request, validate_response,
)
from fs_bot.engine.action_windows import COHORTS, get_cohorts, clear_cohorts
from fs_bot.commands.sa_enlist import scoped_free_force
from fs_bot.engine.free_actions import (
    consult_free_action, execute_free_action_plan, validate_free_action_response,
)

KEY = 'card_51_german'


def derive_params(state, chooser, shaded):
    """§§8.2.3/8.3.1: maximize enemy replacements, equal Regions random."""
    if state['scenario'] not in rc.BASE_SCENARIOS:
        return None
    if shaded:
        return _shaded_default(state, choice_request(state, 51), randomized=True)
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state
    from fs_bot.bots.bot_common import random_select
    from fs_bot.map.map_data import get_adjacent
    regions = sorted({rc.TREVERI, *get_adjacent(rc.TREVERI, state['scenario'])})
    # Aedui use unshaded; Romans decline Surus, Arverni/Belgae use shaded.
    if chooser != rc.AEDUI:
        return None
    enemies = (rc.ARVERNI, rc.BELGAE, rc.GERMANS)
    candidates = [region for region in regions
                  if any(count_pieces(state, region, f, rc.WARBAND)
                         for f in (*enemies, rc.AEDUI))]
    if not candidates:
        return {'region': random_select(state, regions), 'replacements': []}
    counts = {region: min(4, sum(count_pieces(state, region, f, rc.WARBAND)
                                 for f in enemies)) for region in candidates}
    most = max(counts.values())
    region = random_select(state, [region for region in candidates if counts[region] == most])
    replacements = []
    # §8.4.1: visibility precedes enemy faction; own losses reverse visibility.
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        for enemy in enemies:
            count = count_pieces_by_state(state, region, enemy, rc.WARBAND, visibility)
            replacements.extend({'from_faction': enemy, 'piece_state': visibility}
                                for _ in range(min(count, 4 - len(replacements))))
    for visibility in (rc.SCOUTED, rc.REVEALED, rc.HIDDEN):
        count = count_pieces_by_state(state, region, rc.AEDUI, rc.WARBAND, visibility)
        replacements.extend({'from_faction': rc.AEDUI, 'piece_state': visibility}
                            for _ in range(min(count, 4 - len(replacements))))
    return {'region': region, 'replacements': replacements}


def _shaded_default(state, request, *, randomized):
    from fs_bot.bots.bot_common import random_select

    totals = Counter()
    for row in request['available']:
        totals[row['region']] += row['count']
    if not totals:
        return {'count': 0}
    counts = {region: min(SURUS_LIMIT, total) for region, total in totals.items()}
    most = max(counts.values())
    tied = [region for region, count in counts.items() if count == most]
    return {'region': random_select(state, tied) if randomized else tied[0], 'count': most}


def _shaded_plan(state, params):
    from fs_bot.cards.base_event_limits import surus_regions
    from fs_bot.cards.card_effects import _event_step

    if {'region', 'count'} & params.keys():
        if 'piece_choices' in params:
            raise ValueError('Choose one Surus replacement plan format')
    else:
        _event_step(state, '51.piece_choice')
        request = choice_request(state, 51)
        npc = request['owner'] in state.get('non_player_factions', ())
        if 'piece_choices' in params:
            response = {'selections': params['piece_choices']}
        else:
            response = _consult(state, request) if request['available'] and not npc else None
        if response is not None and not _default(response):
            selections = validate_response(state, request, response)['selections']
            region = selections[0]['region'] if selections else None
            return region, [row['piece_state'] for row in selections for _ in range(row['count'])]
        params = _shaded_default(state, request, randomized=npc)

    region, count = params.get('region'), params.get('count', SURUS_LIMIT)
    if type(count) is not int or not 0 <= count <= SURUS_LIMIT:
        raise ValueError('Surus replaces zero to four Aedui Warbands')
    if region is not None and (not isinstance(region, str) or region not in surus_regions(state)):
        raise ValueError('Surus replacements must be within one Region of Treveri')
    return region, [None] * count if region else []


def resolve_replacements(state, params):
    from fs_bot.board.pieces import count_pieces_by_state, get_available, place_piece, remove_piece
    from fs_bot.cards.card_effects import _event_entries, _track_event_placement
    from fs_bot.map.map_data import is_region_playable

    region, plan = _shaded_plan(state, params)
    placed = 0
    if region:
        for visibility in _event_entries(state, '51.german_replacements', plan):
            order = STATES if visibility is None else (visibility,)
            actual = next((ps for ps in order
                           if count_pieces_by_state(state, region, rc.AEDUI, rc.WARBAND, ps)), None)
            if actual is None:
                continue
            remove_piece(state, region, rc.AEDUI, rc.WARBAND, piece_state=actual)
            if is_region_playable(state, region, rc.GERMANS) and get_available(state, rc.GERMANS, rc.WARBAND):
                place_piece(state, region, rc.GERMANS, rc.WARBAND)
                placed += 1
                _track_event_placement(state, KEY, rc.GERMANS, region, rc.WARBAND, 1)
    mods = state.setdefault('event_modifiers', {})
    mods['card_51_german_action'] = True
    mods['card_51_german_cohort'] = [{'region': region, 'faction': rc.GERMANS, 'count': placed}] if placed else []
    if region:
        mods['card_51_action_region'] = region


def resolve_surus(state, chooser):
    mods = state.get('event_modifiers', {})
    placed = mods.pop('card_51_german_cohort', [])
    if KEY in state.get(COHORTS, {}):
        placed = get_cohorts(state, KEY)
    # Transfer ownership of the ledger to the ordinary selected-force scope;
    # keeping both would double-count the same counters at later windows.
    clear_cohorts(state, KEY)
    region = mods.pop('card_51_action_region', None)
    count = sum(entry['count'] for entry in placed if entry['region'] == region)
    if not region or not count:
        return [{'free_action': 'german_command', 'flag': 'card_51',
                 'executed': False, 'declined_no_effect': True,
                 'reason': 'No newly placed German Warbands remain'}]
    with scoped_free_force(state, region, {rc.HIDDEN: count},
                           faction=rc.GERMANS, source='Surus'):
        from fs_bot.cards.card_effects import _event_step
        _event_step(state, '51.german_command')
        request = {'kind': 'free_action', 'request_type': 'event_command',
                   'card_id': 51, 'acting_faction': rc.GERMANS,
                   'allowed_commands': [rc.CMD_MARCH, rc.CMD_RAID, rc.CMD_BATTLE],
                   'allowed_regions': [region], 'max_regions': 1,
                   'with_sa': False, 'free': True, 'allow_decline': False}
        action = consult_free_action(state, chooser, request)
        if action is None:
            from fs_bot.cards.surus_np import choose_surus_action
            action = choose_surus_action(state, chooser, region)
        if action is None:
            result = {'executed': False, 'declined_no_effect': True,
                      'reason': 'The guiding flowchart found no applicable German Command'}
        else:
            error = validate_free_action_response(state, chooser, request, action)
            if error:
                raise ValueError(error)
            result = execute_free_action_plan(state, chooser, request, action)
    return [{'free_action': 'german_command', 'flag': 'card_51',
             'chooser': chooser, 'acting_faction': rc.GERMANS,
             'region': region, 'result': result}]
