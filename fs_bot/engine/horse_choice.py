"""Germanic Horse Region choices: Card 59 Tips, §8.3.3, and A64 Abatis."""
from functools import wraps

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.capabilities import is_capability_active, get_capability_owner

KIND = 'horse_region'
FLAGS = ('card59_unshaded_region', 'card59_shaded_region')
_MISSING = object()


def command_scope(function):
    """Keep each Battle Command's Horse flags separate, including nested ones."""
    @wraps(function)
    def scoped(state, *args, **kwargs):
        previous = {key: state.get('event_modifiers', {}).get(key, _MISSING)
                    for key in FLAGS}
        for key in FLAGS:
            state.get('event_modifiers', {}).pop(key, None)
        try:
            return function(state, *args, **kwargs)
        finally:
            for key, value in previous.items():
                state.get('event_modifiers', {}).pop(key, None)
                if value is not _MISSING:
                    state.setdefault('event_modifiers', {})[key] = value
    return scoped


def attack_blocked(state, region, attacker, defender):
    """A defending Fort/Citadel or active Abatis prevents shaded doubling."""
    if (count_pieces(state, region, defender, rc.FORT)
            or count_pieces(state, region, defender, rc.CITADEL)):
        return True
    abatis = state.get('markers', {}).get(region, {}).get(rc.MARKER_ABATIS) == defender
    if (defender == rc.GERMANS and state.get('event_modifiers', {}).get(
            'card_A31_cancel_german_benefits')):
        abatis = False
    if attacker == rc.GERMANS and is_capability_active(state, 'A31', rc.EVENT_SHADED):
        abatis = False
    return abatis


def selection_request(state, attacker, battle_plan, side):
    """Offer the owner's actual Battles; blocked/zero-Loss choices stay legal."""
    owner = rc.ROMANS if side == rc.EVENT_UNSHADED else get_capability_owner(state, 59)
    if owner is None or (side == rc.EVENT_SHADED and owner not in rc.GALLIC_FACTIONS):
        return None
    defenders = {}
    for entry in battle_plan:
        region = entry.get('region')
        defender = entry.get('target') or next(iter(entry.get('targets') or []), None)
        if (region in state['spaces'] and defender is not None
                and owner in (attacker, defender)
                and count_pieces(state, region, attacker)
                and count_pieces(state, region, defender)):
            defenders.setdefault(region, defender)
    if not defenders:
        return None
    blocked = {region: (attack_blocked(state, region, attacker, defender)
                        if attacker == owner else bool(count_pieces(
                            state, region, owner, rc.CITADEL)))
               for region, defender in defenders.items()} if side == rc.EVENT_SHADED else {}
    return {'kind': KIND, 'card_id': 59, 'side': side, 'owner': owner,
            'attacker': attacker, 'legal_regions': list(defenders),
            'defenders': defenders, 'blocked': blocked,
            'auxilia': {region: count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
                        for region in defenders},
            'may_decline': side == rc.EVENT_UNSHADED}


def _flag(response, key):
    return isinstance(response, dict) and set(response) == {key} and response[key] is True


def validate_response(state, request, response):
    """Accept one live offered Region, permitted decline, or explicit default."""
    if _flag(response, 'use_default') or (request['may_decline'] and _flag(response, 'decline')):
        return response
    if (not isinstance(response, dict) or set(response) != {'region'}
            or response['region'] not in request['legal_regions']):
        raise ValueError('Choose one offered Germanic Horse Battle Region.')
    region = response['region']
    if (region not in state['spaces']
            or not count_pieces(state, region, request['attacker'])
            or not count_pieces(state, region, request['defenders'][region])):
        raise ValueError('The selected Horse Battle is no longer present.')
    return response


def select_for_command(state, attacker, battle_plan):
    """Ask the Roman/Gallic owner; the NPC uses its first applicable Region."""
    from fs_bot.engine.agent import consult_agent
    side = (rc.EVENT_UNSHADED if is_capability_active(state, 59, rc.EVENT_UNSHADED)
            else rc.EVENT_SHADED if is_capability_active(state, 59, rc.EVENT_SHADED) else None)
    if side is None:
        return
    request = selection_request(state, attacker, battle_plan, side)
    if request is None:
        return
    default = next((region for region in request['legal_regions']
                    if (request['auxilia'][region] > 0 if side == rc.EVENT_UNSHADED
                        else not request['blocked'][region])), None)
    response = consult_agent(state, request['owner'], request)
    if response is None or _flag(response, 'use_default'):
        selected = default
    else:
        validate_response(state, request, response)
        selected = None if _flag(response, 'decline') else response['region']
    if selected is not None:
        key = FLAGS[0] if side == rc.EVENT_UNSHADED else FLAGS[1]
        state.setdefault('event_modifiers', {})[key] = selected
