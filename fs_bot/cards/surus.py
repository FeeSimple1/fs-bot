"""Card 51 shaded: the executor commands only the newly placed Germans.

Card Reference 51 and its Tips; §§3.4, 5.1.1, 5.4, 8.2.3. The acting
German pieces remain physically German, and retain intrinsic German rules.
"""
from fs_bot import rules_consts as rc
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
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state
    from fs_bot.bots.bot_common import random_select
    from fs_bot.map.map_data import get_adjacent
    regions = sorted({rc.TREVERI, *get_adjacent(rc.TREVERI, state['scenario'])})
    if shaded:
        counts = {region: min(4, count_pieces(state, region, rc.AEDUI, rc.WARBAND))
                  for region in regions}
        most = max(counts.values())
        if not most:
            return {'count': 0}
        region = random_select(state, [region for region in regions if counts[region] == most])
        return {'region': region, 'count': most}
    # Aedui use unshaded; Romans decline Surus, Arverni/Belgae use shaded.
    if chooser != rc.AEDUI:
        return None
    enemies = (rc.ARVERNI, rc.BELGAE, rc.GERMANS)
    candidates = [region for region in regions
                  if any(count_pieces(state, region, f, rc.WARBAND)
                         for f in (*enemies, rc.AEDUI))]
    if not candidates:
        return {'replacements': []}
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
