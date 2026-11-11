"""Roman Region choice for Card 13 unshaded's pre-Battle Auxilia fire."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.capabilities import is_capability_active

KIND = 'slingers_region'


def is_active_for(state, attacker):
    """Slingers fires on enemy attackers unless Stalwart protects them."""
    return (attacker != rc.ROMANS and is_capability_active(state, 13, rc.EVENT_UNSHADED)
            and not (attacker == rc.GERMANS and is_capability_active(state, 'A31', rc.EVENT_SHADED)))


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


def choose_region(state, attacker, battle_plan):
    """Ask the Roman player; raw delegation uses the printed NPC default."""
    from fs_bot.engine.agent import consult_agent
    if not is_active_for(state, attacker):
        return None
    request = selection_request(state, attacker, battle_plan)
    if request is None:
        return None
    default = next(region for region, auxilia in request['auxilia'].items() if auxilia)
    response = consult_agent(state, rc.ROMANS, request)
    if response is None:
        return default
    validate_response(state, request, response)
    return default if 'use_default' in response else response['region']


def choose_for_queue(state, region, attacker, defender, potential_regions):
    """Ask the Roman owner at an actual Battle under PR-13."""
    from fs_bot.engine.capability_queue import choose_window

    has_auxilia = count_pieces(state, region, rc.ROMANS, rc.AUXILIA) > 0
    choice = choose_window(state, 13, rc.ROMANS, region, attacker, defender,
                           potential_regions, applicable=has_auxilia)
    return choice == 'activate'


def fire(state, region, attacker):
    """Apply the selected initial fire before the Battle resolves."""
    from fs_bot.battle.losses import resolve_losses

    if not is_active_for(state, attacker):
        return
    auxilia = count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
    losses = auxilia if is_capability_active(state, 59, rc.EVENT_UNSHADED) else auxilia // 2
    if losses:
        resolve_losses(state, region, attacker, losses)


def fire_for_single_battle(state, region, attacker, defender):
    """Select and apply Slingers for a Command with one fixed Battle."""
    if choose_region(state, attacker, [{'region': region, 'target': defender}]) == region:
        fire(state, region, attacker)
