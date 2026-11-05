"""Roman Region choice for Card 13 unshaded's pre-Battle Auxilia fire."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces

KIND = 'slingers_region'


def selection_request(state, attacker, battle_plan):
    """Offer selected Battles, including Regions where choosing has no effect."""
    defenders = {}
    for entry in battle_plan:
        region = entry.get('region')
        defender = entry.get('target') or next(iter(entry.get('targets') or []), None)
        if (region in state['spaces'] and defender is not None
                and count_pieces(state, region, attacker)
                and count_pieces(state, region, defender)):
            defenders.setdefault(region, defender)
    auxilia = {region: count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
               for region in defenders}
    if not any(auxilia.values()):
        return None
    return {'kind': KIND, 'card_id': 13, 'side': rc.EVENT_UNSHADED,
            'attacker': attacker, 'legal_regions': list(defenders),
            'defenders': defenders, 'auxilia': auxilia, 'may_decline': False}


def validate_response(state, request, response):
    """Require one offered, still-present Battle or explicit delegation."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'region'}
            or response['region'] not in request['legal_regions']):
        raise ValueError('Choose one offered Battle Region for Balearic Slingers.')
    region = response['region']
    if (region not in state['spaces']
            or not count_pieces(state, region, request['attacker'])
            or not count_pieces(state, region, request['defenders'][region])):
        raise ValueError('The selected Slingers Battle is no longer present.')
    return response


def choose_region(state, attacker, battle_plan, default):
    """Ask the Roman player; raw delegation uses the printed NPC default."""
    from fs_bot.engine.agent import consult_agent
    request = selection_request(state, attacker, battle_plan)
    if request is None:
        return default
    response = consult_agent(state, rc.ROMANS, request)
    if response is None:
        return default
    validate_response(state, request, response)
    return default if 'use_default' in response else response['region']
