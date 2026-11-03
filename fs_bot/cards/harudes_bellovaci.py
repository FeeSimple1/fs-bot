"""A29/A69 shaded: executor choices over the surviving placed-piece grants.

The Event executor chooses Raid targets/counts and the Ambush defender (§5.1),
even when German/Belgic counters belong to another seat. Ordinary Raid and
Ambush rules remain (§§5.1.1, 5.4). Defender and casualty decisions retain
their normal owners; only A29's offensive intrinsic Raid Intimidate follows
the executor's selection authority (A3.4.3).
"""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import _is_devastated, free_action_scope
from fs_bot.commands.raid import get_valid_steal_targets, max_raiders_per_region
from fs_bot.engine.action_windows import COHORTS, get_cohorts, clear_cohorts

HARUDES = 'harudes_raid'
BELLOVACI = 'bellovaci_ambush'
RAID_COHORT = 'card_A29_raid'
AMBUSH_COHORT = 'card_A69_ambush'
RAID_CHOOSER = '_harudes_raid_chooser'


def _copy(state):
    result = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    result['_diviciacus_preview'] = True
    return result


def harudes_cohort(state):
    """Read the live ledger even when every placed counter was removed."""
    if RAID_COHORT in state.get(COHORTS, {}):
        return [{'region': e['region'], 'faction': rc.GERMANS, 'count': e['count']}
                for e in get_cohorts(state, RAID_COHORT)
                if e['count'] and e['piece_state'] == rc.HIDDEN]
    return deepcopy(state.get('event_modifiers', {}).get('card_A29_raid_cohort', []))


def harudes_regions(state, cohort):
    regions = {}
    for entry in cohort:
        region = entry['region']
        targets = get_valid_steal_targets(state, region, rc.GERMANS)
        gain = not _is_devastated(state, region)
        if entry['count'] and (gain or targets):
            regions[region] = {'max_raiders': min(entry['count'],
                max_raiders_per_region(state, rc.GERMANS)),
                'can_gain': gain, 'targets': targets}
    return regions


def validate_harudes(state, request, response):
    if set(response) != {'raid_actions'} or not isinstance(response['raid_actions'], list):
        raise ValueError('Harudes needs raid_actions, one entry per placed Warband used.')
    entries = response['raid_actions']
    if not entries:
        raise ValueError('Choose at least one legal Raid with the placed Warbands.')
    cohort = harudes_cohort(state)
    regions = harudes_regions(state, cohort)
    counts = Counter()
    actions = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'region', 'target_faction'}:
            raise ValueError('Each Raid needs region and target_faction (null to gain).')
        region, target = entry['region'], entry['target_faction']
        if not isinstance(region, str) or region not in regions:
            raise ValueError('Raid only in a Region with surviving placed Warbands.')
        option = regions[region]
        counts[region] += 1
        if counts[region] > option['max_raiders']:
            raise ValueError('Raid exceeds the placed cohort or ordinary per-Region limit.')
        if ((target is None and not option['can_gain'])
                or (target is not None and target not in option['targets'])):
            raise ValueError('Choose a legal enemy to steal from, or gain outside Devastation.')
        actions.append(dict(entry, faction=rc.GERMANS))
    # The shared cohort executor validates successive steals against the
    # remaining Resources, using exactly the same ordinary Raid procedure.
    from fs_bot.cards.dumnorix import raid_cohort
    raid_cohort(_copy(state), cohort, actions)


@contextmanager
def _raid_chooser(state, chooser):
    missing = object()
    previous = state.get(RAID_CHOOSER, missing)
    state[RAID_CHOOSER] = chooser
    try:
        yield
    finally:
        if previous is missing:
            state.pop(RAID_CHOOSER, None)
        else:
            state[RAID_CHOOSER] = previous


def resolve_harudes(state, chooser):
    from fs_bot.cards.dumnorix import derive_raids, raid_cohort
    from fs_bot.engine.free_actions import consult_free_action
    cohort = harudes_cohort(state)
    regions = harudes_regions(state, cohort)
    request = {'kind': 'free_action', 'request_type': HARUDES,
        'card_id': 'A29', 'acting_faction': rc.GERMANS, 'cohort': cohort,
        'regions': regions, 'free': True, 'allow_decline': False}
    response = consult_free_action(state, chooser, request) if regions else None
    if response is None:
        actions = derive_raids(state, cohort) if regions else []
    else:
        actions = [dict(entry, faction=rc.GERMANS) for entry in response['raid_actions']]
    state.get('event_modifiers', {}).pop('card_A29_raid_cohort', None)
    # raid_cohort now owns these exact counters through its scoped force.
    clear_cohorts(state, RAID_COHORT)
    with free_action_scope(state, rc.GERMANS), _raid_chooser(state, chooser):
        result = raid_cohort(state, cohort, actions, allow_reduced=True)
    if not result['executed']:
        result['declined_no_effect'] = True
    return [{'free_action': 'raid', 'flag': 'card_A29', 'faction': rc.GERMANS,
             'result': result}]


def bellovaci_placed(state):
    if AMBUSH_COHORT in state.get(COHORTS, {}):
        return sum(e['count'] for e in get_cohorts(state, AMBUSH_COHORT))
    return state.get('event_modifiers', {}).get('card_A69_loss_per_warband', 0)


def bellovaci_defenders(state):
    from fs_bot.commands.sa_ambush import validate_ambush_region
    region = rc.TRIBE_TO_REGION[rc.TRIBE_BELLOVACI]
    if not bellovaci_placed(state):
        return []
    return [enemy for enemy in rc.FACTIONS if enemy != rc.BELGAE
            and count_pieces(state, region, enemy)
            and validate_ambush_region(state, region, rc.BELGAE, enemy)[0]]


def validate_bellovaci(state, request, response):
    if set(response) != {'defender'} or response['defender'] not in bellovaci_defenders(state):
        raise ValueError('Choose a legal Ambush defender at Bellovaci.')


def bellovaci_default_defenders(state):
    """Retain the existing NP policy's positive-Loss target filter."""
    from fs_bot.battle.resolve import _calculate_attack_losses
    region = rc.TRIBE_TO_REGION[rc.TRIBE_BELLOVACI]
    return [enemy for enemy in bellovaci_defenders(state)
            if _calculate_attack_losses(state, region, rc.BELGAE, enemy,
                is_retreat=False,
                had_citadel_at_start=count_pieces(state, region, enemy, rc.CITADEL) > 0,
                had_fort_at_start=count_pieces(state, region, enemy, rc.FORT) > 0,
                full_loss_warbands=bellovaci_placed(state)) > 0]


def validate_bellovaci_default(state):
    if bellovaci_defenders(state) and not bellovaci_default_defenders(state):
        raise ValueError('Choose the required Ambush defender; the bot default has no action.')


def _bellovaci_no_effect(state, reason='no legal Belgic Ambush at Bellovaci'):
    state.get('event_modifiers', {}).pop('card_A69_loss_per_warband', None)
    clear_cohorts(state, AMBUSH_COHORT)
    return [{'free_action': 'ambush', 'flag': 'card_A69', 'executed': False,
             'declined_no_effect': True, 'reason': reason}]


def resolve_bellovaci(state, chooser):
    from fs_bot.engine.execute import _execute_battle
    from fs_bot.engine.free_actions import consult_free_action
    region = rc.TRIBE_TO_REGION[rc.TRIBE_BELLOVACI]
    placed = bellovaci_placed(state)
    candidates = bellovaci_defenders(state)
    if not candidates:
        return _bellovaci_no_effect(state)
    defaults = bellovaci_default_defenders(state)
    request = {'kind': 'free_action', 'request_type': BELLOVACI,
        'card_id': 'A69', 'acting_faction': rc.BELGAE, 'region': region,
        'defenders': candidates, 'placed_warbands': placed,
        'free': True, 'allow_decline': False, 'default_available': bool(defaults),
        'validate_default_response': True}
    response = consult_free_action(state, chooser, request)
    if response is None and not defaults:
        # Only NP/raw callback deferral can take this no-effect path. An
        # explicit human default was validated before becoming None.
        return _bellovaci_no_effect(state, 'bot priorities select no effective Bellovaci Ambush')
    defender = (max(defaults, key=lambda enemy: count_pieces(state, region, enemy))
                if response is None else response['defender'])
    tracked = AMBUSH_COHORT in state.get(COHORTS, {})
    state.get('event_modifiers', {}).pop('card_A69_loss_per_warband', None)
    try:
        with free_action_scope(state, rc.BELGAE):
            result = _execute_battle(state, rc.BELGAE, {
                'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH, 'sa_regions': [region],
                'details': {'battle_plan': [{'region': region, 'target': defender}]}},
                _full_loss_warbands=placed, _require_ambush=True,
                **({'_full_loss_cohort': AMBUSH_COHORT} if tracked else {}))
    finally:
        clear_cohorts(state, AMBUSH_COHORT)
    return [{'free_action': 'ambush', 'flag': 'card_A69', 'region': region,
             'faction': rc.BELGAE, 'defender': defender, 'result': result}]
