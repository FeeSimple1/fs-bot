"""Owner's optional post-Ambush removal: Card 10 shaded, §1.4.2."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, remove_piece, clear_allied_tribe

KIND = 'ballistae_target'


def target_options(state, region, defender):
    """Offer surviving physical Citadels/Forts, excluding Provincia's Fort."""
    from fs_bot.engine.besiege_choice import target_options as besiege_targets
    context = state.get('_combined_battle_force', {})
    owners = [defender]
    if (context.get('faction') == defender
            and rc.CITADEL in context.get('piece_types', ())):
        owners.extend(context.get('owners', {}).get(region, ()))
    physical = {key: value for key, value in state.items()
                if key != '_combined_battle_force'}
    options = []
    for owner in dict.fromkeys(owners):
        if count_pieces(physical, region, owner, rc.CITADEL):
            citadels = [target for target in besiege_targets(physical, region, owner)
                        if target['piece_type'] == rc.CITADEL]
            # Older raw fixtures can have a Citadel counter without a Tribe
            # record. Keep its optional activation, without inventing a name.
            for target in citadels or [{'piece_type': rc.CITADEL, 'tribe': None}]:
                options.append(dict(target, owner=owner))
        if (count_pieces(physical, region, owner, rc.FORT)
                and not (region == rc.PROVINCIA and owner == rc.ROMANS)):
            options.append({'piece_type': rc.FORT, 'tribe': None, 'owner': owner})
    return options


def _flag(response, key):
    return isinstance(response, dict) and set(response) == {key} and response[key] is True


def validate_response(state, request, response):
    """Reject malformed choices and targets no longer on the live board."""
    if _flag(response, 'decline') or _flag(response, 'use_default'):
        return response
    if (not isinstance(response, dict) or set(response) != {'target'}
            or response['target'] not in request['targets']
            or response['target'] not in target_options(
                state, request['region'], request['defender'])):
        raise ValueError('Choose one offered Ballistae target or decline removal.')
    return response


def remove_after_ambush(state, region, attacker, defender):
    """Ask the capability owner after combat, retaining the NPC/raw default."""
    from fs_bot.engine.agent import consult_agent
    options = target_options(state, region, defender)
    if not options:
        return
    request = {'kind': KIND, 'card_id': 10, 'side': rc.EVENT_SHADED,
               'region': region, 'attacker': attacker, 'defender': defender,
               'targets': options, 'may_decline': True}
    response = consult_agent(state, attacker, request)
    if response is None or _flag(response, 'use_default'):
        target = next((target for target in options if target['piece_type'] == rc.CITADEL),
                      options[0])
    else:
        validate_response(state, request, response)
        if _flag(response, 'decline'):
            return
        target = response['target']
    owner, piece = target['owner'], target['piece_type']
    context = state.get('_combined_battle_force', {})
    kwargs = ({'physical_owner': owner}
              if context.get('faction') == defender
              and region in context.get('owners', {})
              and piece in context.get('piece_types', ()) else {})
    remove_piece(state, region, defender if kwargs else owner, piece, **kwargs)
    if piece == rc.CITADEL:
        clear_allied_tribe(state, region, owner, piece, tribe=target['tribe'])
