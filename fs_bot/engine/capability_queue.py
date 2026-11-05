"""PR-13: mandatory one-Region choices as prospective Battles become real."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.engine.agent import consult_agent

KIND = 'capability_window'


def validate_response(state, request, response):
    """Require an offered action at a still-present Battle; no general decline."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'action'}
            or response['action'] not in request['actions']):
        raise ValueError('Choose an offered capability use or reservation.')
    region = request['region']
    if (region not in state['spaces']
            or not count_pieces(state, region, request['attacker'])
            or not count_pieces(state, region, request['defender'])):
        raise ValueError('The offered capability Battle is no longer present.')
    return response


def choose_window(state, card_id, owner, region, attacker, defender,
                  potential_regions, *, applicable, blocked=False):
    """Humans may reserve; delegation retains first-applicable NPC use."""
    potential = list(dict.fromkeys(potential_regions))
    request = {'kind': KIND, 'card_id': card_id,
               'side': rc.EVENT_UNSHADED if card_id == 13 else rc.EVENT_SHADED,
               'owner': owner, 'region': region, 'attacker': attacker,
               'defender': defender, 'potential_regions': potential,
               'actions': ['activate', *(['reserve'] if potential else [])],
               'auxilia': count_pieces(state, region, rc.ROMANS, rc.AUXILIA),
               'blocked': blocked}
    response = consult_agent(state, owner, request)
    if response is None:
        return 'activate' if applicable else 'reserve'
    validate_response(state, request, response)
    if 'use_default' in response:
        return 'activate' if applicable else 'reserve'
    return response['action']
