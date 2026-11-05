"""Roman choice of one physical Besiege target (§4.2.3 / A4.2.3)."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, tribe_has_ally_disc

KIND = 'besiege_target'


def target_options(state, region, defender):
    """List named Citadels/discs and the expansion's German Settlement."""
    options = []
    for piece in (rc.CITADEL, rc.ALLY):
        if not count_pieces(state, region, defender, piece):
            continue
        for tribe, info in sorted(state.get('tribes', {}).items()):
            if (info.get('allied_faction') != defender or
                    (info.get('region') or rc.TRIBE_TO_REGION.get(tribe)) != region):
                continue
            disc = tribe_has_ally_disc(state, region, tribe, defender)
            if (piece == rc.ALLY and disc) or (
                    piece == rc.CITADEL and tribe in rc.TRIBE_TO_CITY and not disc):
                options.append({'piece_type': piece, 'tribe': tribe})
    if (state['scenario'] in rc.ARIOVISTUS_SCENARIOS and defender == rc.GERMANS
            and count_pieces(state, region, defender, rc.SETTLEMENT)):
        options.append({'piece_type': rc.SETTLEMENT, 'tribe': None})
    return options


def _flag(response, key):
    return isinstance(response, dict) and set(response) == {key} and response[key] is True


def validate_response(state, request, response):
    """Validate against both the offered and current physical targets."""
    if _flag(response, 'decline') or _flag(response, 'use_default'):
        return response
    if (not isinstance(response, dict) or set(response) != {'target'}
            or response['target'] not in request['targets']
            or response['target'] not in target_options(
                state, request['region'], request['defender'])):
        raise ValueError('Choose one offered physical Besiege target or decline.')
    return response


def choose_target(state, region, defender, default):
    """Retain the NPC/raw-callback default; human sessions require a response."""
    from fs_bot.engine.agent import consult_agent
    options = target_options(state, region, defender)
    legacy = {'piece_type': default, 'tribe': None}
    if not options:
        # Low-level fixtures/legacy boards may have counters without Tribe
        # records. Preserve their old mechanics; never invent an identity.
        return legacy
    request = {'kind': KIND, 'region': region, 'defender': defender,
               'targets': options, 'may_decline': True}
    response = consult_agent(state, rc.ROMANS, request)
    if response is None or _flag(response, 'use_default'):
        return legacy
    validate_response(state, request, response)
    if _flag(response, 'decline'):
        return None
    return response['target']
