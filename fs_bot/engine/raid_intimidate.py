"""A3.4.3: Ariovistus's actual raiders may simultaneously free Intimidate.

This is part of Raid, independent of any accompanying Special Ability. The
trusted credit comes only from a successful Raid's newly revealed Warbands.
"""
from copy import deepcopy

from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region
from fs_bot.engine.agent import consult_agent
from fs_bot.rules_consts import (
    GERMANS, ROMANS, FACTIONS, ARIOVISTUS_SCENARIOS, ARIOVISTUS_LEADER,
    WARBAND, AUXILIA, ALLY, HIDDEN, REVEALED, SCOUTED,
)

RAID_INTIMIDATE = 'raid_intimidate'


def eligible(state, region, raiders):
    # A3.4.3 requires Ariovistus to be in the Region, even when an Event
    # restricts the actual Raiders to newly placed Warbands. The resident
    # Leader is not added to that selected force for March or Battle.
    from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
    physical = {key: value for key, value in state.items() if key != FREE_FORCE_KEY}
    return (state['scenario'] in ARIOVISTUS_SCENARIOS
            and type(raiders) is int and raiders > 0
            and get_leader_in_region(physical, region, GERMANS) == ARIOVISTUS_LEADER)


def target_options(state, region):
    """Physical removable pieces, excluding every Faction with a Leader."""
    from fs_bot.commands.sa_intimidate import romans_immune
    options = []
    for faction in FACTIONS:
        if (faction == GERMANS or get_leader_in_region(state, region, faction)
                or faction == ROMANS and romans_immune(state)):
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
    if response.get('extra_warband'):
        entries[0]['extra_warband'] = True
    return {'details': {'intimidate_plan': entries}}


def removal_limits(state, region, raiders):
    """A3.4.3's simultaneous Raiders plus A22's optional fresh participant.

    A third actual Raider (card 8) can supply A22's added Reveal itself.
    When using a fresh Warband instead, at most two actual Raiders plus
    that one extra Hidden Warband participate. Piece counts retain any
    Event's selected-force boundary, including A29's placed cohort.
    """
    from fs_bot.commands.sa_intimidate import intimidate_limit
    limit = intimidate_limit(state)
    raider_max = min(limit, raiders)
    extra = limit == 3 and count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN) > 0
    extra_max = min(2, raiders) + 1 if extra else 0
    return raider_max, extra, max(raider_max, extra_max), extra_max


def validate_response(state, request, response):
    """Validate the whole optional choice before any Intimidate effect."""
    if response in ({'decline': True}, {'use_default': True}):
        return
    if (not isinstance(response, dict) or 'targets' not in response
            or set(response) - {'targets', 'extra_warband'}):
        raise ValueError('Raid Intimidate requires targets or an explicit decline.')
    targets = response['targets']
    credit = request.get('raiders')
    region = request.get('region')
    if not eligible(state, region, credit):
        raise ValueError('Free Raid Intimidate requires actual raiders with Ariovistus.')
    extra = response.get('extra_warband', False)
    if type(extra) is not bool:
        raise ValueError('extra_warband must be a boolean.')
    raider_max, available, _, extra_max = removal_limits(state, region, credit)
    if extra and (not available or not isinstance(targets, list) or len(targets) < 2):
        raise ValueError('A22 requires an available extra Hidden Warband and extra removal.')
    if not isinstance(targets, list) or len(targets) > (extra_max if extra else raider_max):
        raise ValueError('Too many removals for the selected Raiding and extra Warbands.')
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
    raider_max, extra, maximum, extra_max = removal_limits(state, region, raiders)
    request = {'kind': RAID_INTIMIDATE, 'region': region, 'raiders': raiders,
               'max_removals': maximum, 'targets': target_options(state, region)}
    from fs_bot.commands.sa_intimidate import intimidate_limit
    if intimidate_limit(state) == 3:
        request.update(max_raider_removals=raider_max,
                       extra_warband_available=extra, max_with_extra=extra_max)
    # A29's executor directs the granted Raid, including its offensive
    # intrinsic Intimidate (§5.1, A3.4.3); physical pieces stay German.
    from fs_bot.cards.harudes_bellovaci import RAID_CHOOSER
    chooser = state.get(RAID_CHOOSER, GERMANS)
    if chooser != GERMANS:
        request['acting_faction'] = GERMANS
    response = consult_agent(state, chooser, request)
    if response is None or response == {'use_default': True}:
        from fs_bot.bots.german_bot import _select_intimidate_targets
        selected = _select_intimidate_targets(state, region, maximum)
        response = {'targets': [{key: target[key] for key in
                     ('target_faction', 'target_piece', 'target_state')}
                    for target in selected]}
        if len(selected) > raider_max:
            response['extra_warband'] = True
    validate_response(state, request, response)
    if response == {'decline': True}:
        return {'executed': False, 'declined': True, 'region': region}
    from fs_bot.engine.execute import _execute_intimidate
    result = _execute_intimidate(state, GERMANS, _action(region, response),
                                raid_credits={region: raiders})
    result['intrinsic_raid'] = True
    return result
