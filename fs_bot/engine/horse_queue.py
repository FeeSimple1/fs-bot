"""Optional unshaded Horse use as prospective Battles actually become selected.

Card 59 unshaded says 'may', so reserving or declining the benefit is legal
even if no later Battle occurs. Mandatory Card 13/59-shaded windows remain a
source question; see Q-CAPABILITY-QUEUE-TIMING in QUESTIONS.md.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.engine.agent import consult_agent

KIND = 'horse_window'


def validate_response(state, request, response):
    """Validate the offered action against the actual selected Battle."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'action'}
            or response['action'] not in request['actions']):
        raise ValueError('Choose an offered Horse activation, reservation or decline.')
    region = request['region']
    if (region not in state['spaces']
            or not count_pieces(state, region, request['attacker'])
            or not count_pieces(state, region, request['defender'])
            or not count_pieces(state, region, rc.ROMANS, rc.AUXILIA)):
        raise ValueError('The offered Horse Battle is no longer applicable.')
    return response


def choose_window(state, region, attacker, defender, potential_regions):
    """Raw/NPC delegation activates here; human reservation consumes no use."""
    potential = list(dict.fromkeys(potential_regions))
    actions = ['activate', *(['reserve'] if potential else []), 'decline']
    request = {'kind': KIND, 'card_id': 59, 'side': rc.EVENT_UNSHADED,
               'owner': rc.ROMANS, 'region': region, 'attacker': attacker,
               'defender': defender, 'actions': actions,
               'auxilia': count_pieces(state, region, rc.ROMANS, rc.AUXILIA),
               'potential_regions': potential}
    response = consult_agent(state, rc.ROMANS, request)
    if response is None:
        return 'activate'
    validate_response(state, request, response)
    return 'activate' if 'use_default' in response else response['action']
