"""A3.4.3: Ariovistus's actual raiders may simultaneously free Intimidate.

This is part of Raid, independent of any accompanying Special Ability. The
trusted credit comes only from a successful Raid's newly revealed Warbands.
"""
from copy import deepcopy

from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region
from fs_bot.engine.agent import consult_agent
from fs_bot.rules_consts import (
    GERMANS, FACTIONS, ARIOVISTUS_SCENARIOS, ARIOVISTUS_LEADER,
    WARBAND, AUXILIA, ALLY, HIDDEN, REVEALED, SCOUTED,
)

RAID_INTIMIDATE = 'raid_intimidate'


def eligible(state, region, raiders):
    return (state['scenario'] in ARIOVISTUS_SCENARIOS
            and type(raiders) is int and raiders > 0
            and get_leader_in_region(state, region, GERMANS) == ARIOVISTUS_LEADER)


def target_options(state, region):
    """Physical removable pieces, excluding every Faction with a Leader."""
    options = []
    for faction in FACTIONS:
        if faction == GERMANS or get_leader_in_region(state, region, faction):
            continue
        for piece in (ALLY, AUXILIA, WARBAND):
            states = (None,) if piece == ALLY else (HIDDEN, REVEALED, SCOUTED)
            for visibility in states:
                count = (count_pieces(state, region, faction, piece)
                         if visibility is None else
                         count_pieces_by_state(state, region, faction, piece, visibility))
                if count:
                    options.append({'target_faction': faction, 'target_piece': piece,
                                    'target_state': visibility, 'available': count})
    return options


def _action(region, response):
    targets = response['targets']
    entries = [dict(target, region=region, free=True) for target in targets]
    if not entries:
        entries = [{'region': region, 'free': True, 'target_faction': None,
                    'target_piece': None, 'target_state': None}]
    return {'details': {'intimidate_plan': entries}}


def validate_response(state, request, response):
    """Validate the whole optional choice before any Intimidate effect."""
    if response in ({'decline': True}, {'use_default': True}):
        return
    if not isinstance(response, dict) or set(response) != {'targets'}:
        raise ValueError('Raid Intimidate requires targets or an explicit decline.')
    targets = response['targets']
    credit = request.get('raiders')
    region = request.get('region')
    if not eligible(state, region, credit):
        raise ValueError('Free Raid Intimidate requires actual raiders with Ariovistus.')
    if not isinstance(targets, list) or len(targets) > min(2, credit):
        raise ValueError('Select at most two removals, and no more than the actual raiders.')
    keys = {'target_faction', 'target_piece', 'target_state'}
    for target in targets:
        if not isinstance(target, dict) or set(target) != keys:
            raise ValueError('Each target needs its Faction, piece type, and visibility.')
    from fs_bot.engine.execute import _execute_intimidate
    sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    result = _execute_intimidate(sim, GERMANS, _action(region, response),
                                raid_credits={region: credit})
    if result.get('errors') or not result.get('executed'):
        raise ValueError(f'Invalid Raid Intimidate choice: {result.get("errors") or result}')


def resolve_raid_intimidate(state, region, raiders):
    """Consult the human or apply A8.7.1's priorities using actual Raid credit."""
    if not eligible(state, region, raiders):
        return None
    request = {'kind': RAID_INTIMIDATE, 'region': region, 'raiders': raiders,
               'max_removals': min(2, raiders), 'targets': target_options(state, region)}
    response = consult_agent(state, GERMANS, request)
    if response is None or response == {'use_default': True}:
        from fs_bot.bots.german_bot import _select_intimidate_targets
        selected = _select_intimidate_targets(state, region, min(2, raiders))
        response = {'targets': [{key: target[key] for key in
                     ('target_faction', 'target_piece', 'target_state')}
                    for target in selected]}
    validate_response(state, request, response)
    if response == {'decline': True}:
        return {'executed': False, 'declined': True, 'region': region}
    from fs_bot.engine.execute import _execute_intimidate
    result = _execute_intimidate(state, GERMANS, _action(region, response),
                                raid_credits={region: raiders})
    result['intrinsic_raid'] = True
    return result
