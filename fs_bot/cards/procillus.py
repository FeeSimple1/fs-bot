"""A19: replace Allies near Caesar or March a whole Roman force.

A Card Reference A19 and §5.1 assign the choice to the Event executor.
Only German non-players apply their no-Fort/outnumber instruction.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, get_leader_in_region
from fs_bot.engine.free_actions import consult_free_action
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state, get_tribe_restriction


MAX_REPLACEMENTS = 3


def replacement_targets(state):
    """Exact non-Roman Ally discs within one Region of named Caesar."""
    from fs_bot.cards.event_targets import roman_leader_regions
    from fs_bot.cards.expansion_validation import source_allies
    regions = roman_leader_regions(state, caesar_only=True)
    return {entry['tribe']: entry for entry in source_allies(state, regions)
            if entry['faction'] != rc.ROMANS}


def roman_ally_allowed(state, tribe):
    # A Colony uses its own circle rather than a printed Tribe restriction.
    return (bool(state['tribes'][tribe].get('region'))
            or get_tribe_restriction(tribe) in (None, rc.ROMANS))


def derive_params(state, faction, shaded):
    if shaded:
        return None
    from fs_bot.bots.bot_common import get_faction_targeting_order, is_ally_in_city_or_remi, random_select

    targets = replacement_targets(state)
    available = get_available(state, rc.ROMANS, rc.ALLY)
    order = get_faction_targeting_order(faction, state['scenario'])
    priorities = {owner: index for index, owner in enumerate(order)}
    replacements, last_region = [], None
    while targets and len(replacements) < MAX_REPLACEMENTS:
        # §§8.3.1/8.4.1: maximize actual replacements, then choose Cities or
        # Remi before other discs and use the printed faction order. A pool
        # shortage or stacking restriction still permits removal (§5.1.1).
        scores = {tribe: (available > 0 and roman_ally_allowed(state, tribe),
                          is_ally_in_city_or_remi(tribe, state['scenario']),
                          -priorities.get(entry['faction'], len(priorities)))
                  for tribe, entry in targets.items()}
        best = max(scores.values())
        choices = [tribe for tribe, score in scores.items() if score == best]
        regions = sorted({targets[tribe]['region'] for tribe in choices})
        region = last_region if last_region in regions else random_select(state, regions)
        tribe = random_select(state, [t for t in choices if targets[t]['region'] == region])
        replacements.append({'tribe': tribe})
        available -= int(best[0])
        last_region = region
        del targets[tribe]
    return {'replacements': replacements} if replacements else None


def mobile_count(state, region):
    return (count_pieces(state, region, rc.ROMANS, rc.LEGION)
            + count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
            + int(get_leader_in_region(state, region, rc.ROMANS) is not None))


def moves(state):
    playable = set(get_playable_regions_for_state(state, rc.ROMANS))
    return [{'origin': origin, 'destination': destination}
            for origin in sorted(playable) if mobile_count(state, origin)
            for destination in sorted(get_adjacent(origin, state['scenario']))
            if destination in playable and count_pieces(state, destination, rc.GERMANS)]


def validate_march(state, response):
    if (not isinstance(response, dict) or set(response) != {'origin', 'destination'}
            or response not in moves(state)):
        raise ValueError('Choose one Roman mobile force and an adjacent Region with Germans.')


def default_move(state, faction):
    candidates = moves(state)
    if faction == rc.GERMANS and faction in state.get('non_player_factions', ()):
        candidates = [move for move in candidates
                      if not count_pieces(state, move['destination'], rc.ROMANS, rc.FORT)
                      and advantage(state, move) > 0]
    return max(candidates, key=lambda move: (mobile_count(state, move['origin']),
                                           advantage(state, move)), default=None)


def advantage(state, move):
    return (count_pieces(state, move['destination'], rc.GERMANS)
            - count_pieces(state, move['destination'], rc.ROMANS)
            - mobile_count(state, move['origin']))


def resolve(state, faction):
    legal = moves(state)
    if not legal:
        return [{'free_action': 'march_romans', 'flag': 'card_A19_march_romans',
                 'executed': False, 'declined_no_effect': True,
                 'reason': 'No Roman mobile force adjacent to Germans'}]
    request = {'kind': 'free_action', 'request_type': 'procillus_march',
               'card_id': 'A19', 'acting_faction': rc.ROMANS, 'moves': legal,
               'allow_decline': False, 'free': True, 'with_sa': False}
    plan = consult_free_action(state, faction, request)
    if plan is None:
        plan = default_move(state, faction)
    if plan is None:
        return [{'free_action': 'march_romans', 'flag': 'card_A19_march_romans',
                 'executed': False, 'declined_no_effect': True,
                 'reason': 'No move where Germans outnumber Romans (no Fort)'}]
    validate_march(state, plan)
    origin, destination = plan['origin'], plan['destination']
    leader = get_leader_in_region(state, origin, rc.ROMANS)
    moved = {'caesar': leader == rc.CAESAR,
             'legions': count_pieces(state, origin, rc.ROMANS, rc.LEGION),
             'auxilia': count_pieces(state, origin, rc.ROMANS, rc.AUXILIA)}
    if leader is not None:
        moved['leader'] = leader
    before_advantage = advantage(state, plan)
    from fs_bot.commands.common import free_action_scope
    from fs_bot.engine.execute import _march_with_harassment
    from fs_bot.engine.march_choices import chooser_scope
    # This is a March, including origin flipping and normal stop rules, not
    # a relocation. No intermediate Region means no Harassment on this hop.
    with free_action_scope(state, rc.ROMANS), chooser_scope(state, rc.ROMANS, faction):
        final = _march_with_harassment(state, rc.ROMANS, origin, [destination])
    return [{'free_action': 'march_romans', 'flag': 'card_A19_march_romans',
             'executed': True, 'source': origin, 'dest': final, 'moved': moved,
             'german_advantage': before_advantage}]
