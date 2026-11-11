"""Battle Retreat declaration and surviving-piece choices (§§3.2.4, 3.3.4)."""

from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import defender_abatis_active
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import (
    count_pieces, get_effective_faction_pieces, get_leader_in_region, move_piece, remove_piece,
)
from fs_bot.cards.capabilities import is_capability_active
from fs_bot.bots.bot_common import _AllRemovalsRng, _AllSavesRng
from fs_bot.engine.agent import RETREAT_DISPOSITION, consult_agent
from fs_bot.map.map_data import get_adjacent_for_state


def mobile_pieces(state, region, defender):
    force = get_effective_faction_pieces(state, region, defender)
    pieces = []
    leader = force.get(rc.LEADER)
    if leader is not None:
        pieces.append(dict(piece_type=rc.LEADER, piece_state=None, count=1, leader=leader))
    if force.get(rc.LEGION):
        pieces.append(dict(piece_type=rc.LEGION, piece_state=None, count=force[rc.LEGION]))
    for piece in (rc.AUXILIA, rc.WARBAND):
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = force.get(visibility, {}).get(piece, 0)
            if count:
                pieces.append(dict(piece_type=piece, piece_state=visibility, count=count))
    return pieces


def can_declare(state, region, attacker, defender, is_ambush):
    scenario = state['scenario']
    if is_ambush or (scenario in rc.BASE_SCENARIOS and rc.GERMANS in (attacker, defender)):
        return False
    if defender == rc.ARVERNI and scenario in rc.ARIOVISTUS_SCENARIOS:
        return False
    if (defender == rc.GERMANS and is_capability_active(state, 'A33', rc.EVENT_UNSHADED)
            and not is_capability_active(state, 'A31', rc.EVENT_SHADED)):
        return False
    if defender == rc.BELGAE and is_capability_active(state, 'A70', rc.EVENT_UNSHADED):
        return False
    return bool(mobile_pieces(state, region, defender))


def legal_regions(state, region, defender, agreements):
    """Use current Control and only the host promises obtained at Step 2."""
    return sorted(dest for dest in get_adjacent_for_state(state, region, defender)
                  if is_controlled_by(state, dest, defender)
                  or (dest in agreements and is_controlled_by(state, dest, agreements[dest])))


def non_player_should_retreat(state, region, attacker, defender, *, destination,
                              agreements, **battle):
    """Apply §8.4.3 using the defending force after Attack Losses."""
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.engine.action_windows import SCOPE

    def forecast(declaration, rng):
        board = deepcopy({key: value for key, value in state.items()
                          if key not in ('decision_agent', 'rng', SCOPE)})
        board['rng'] = rng
        result = resolve_battle(
            board, region, attacker, defender, retreat_declaration=declaration,
            retreat_region=destination, retreat_agreements=agreements,
            retreat_non_player=True, **battle)
        return count_pieces(board, region, defender), result

    standing_pieces, standing = forecast(False, _AllRemovalsRng())
    attack = standing['attack']
    suffer = (attack['losses_requested'] + attack.get('ally_first_removed', 0)
              + attack.get('auto_legion_removed', 0))
    inflict = (standing['counterattack'] or {}).get('losses_requested', 0)
    save_last_piece = standing_pieces == 0
    # Without refuge, Step 6 removes surviving Legions outright. Preserve
    # the Roman policy of using a legal destination to reduce Legion Losses.
    roman_legion_rolls = (sum(piece == rc.LEGION for piece, _, _ in attack['rolls'])
                          if defender == rc.ROMANS and destination is not None else 0)
    fortified = (count_pieces(state, region, defender, rc.FORT) > 0
                 or count_pieces(state, region, defender, rc.CITADEL) > 0
                 or defender_abatis_active(state, region, attacker, defender))
    outmatched = not fortified and inflict * 2 < suffer
    if not (save_last_piece or roman_legion_rolls or outmatched):
        return False

    remaining, withdrawn = forecast(True, _AllRemovalsRng())
    retreat = withdrawn['retreat']
    if save_last_piece and remaining + sum(count for _, count in retreat['moved']) > 0:
        return True
    if roman_legion_rolls > sum(piece == rc.LEGION for piece, _, _ in
                                withdrawn['attack']['rolls']):
        return True
    if not outmatched or retreat['removed']:
        return False
    if destination is not None:
        return True
    # With no refuge, check that defenders can stay put. A saving roll
    # may leave a piece that must still leave the Region at Step 6.
    if withdrawn['attack']['rolls']:
        remaining, saved = forecast(True, _AllSavesRng())
        return remaining > 0 and not saved['retreat']['removed']
    return remaining > 0


def compatible_declaration(current, saved):
    """Only the new stage field differs on a recorded old declaration."""
    return saved == {key: value for key, value in current.items() if key != 'stage'}


def validate_response(request, response):
    if (not isinstance(response, dict)
            or set(response) != {'region', 'stay_leader', 'stay_hidden_warbands'}):
        raise ValueError('Choose one Retreat destination or removal, and how many pieces stay.')
    destination = response['region']
    if destination is not None and destination not in request['legal_regions']:
        raise ValueError('Choose an offered Retreat destination or null for removal.')
    leader, hidden = response['stay_leader'], response['stay_hidden_warbands']
    if (type(leader) is not bool or (leader and not request['can_stay_leader'])
            or type(hidden) is not int or not 0 <= hidden <= request['max_hidden_warbands']):
        raise ValueError('Only offered surviving Leaders and Hidden Warbands may stay.')
    return response


def disposition_options(request):
    """Distinct survivor choices for detached forecasts."""
    total = sum(p['count'] for p in request['pieces'])
    return tuple((destination, leader, hidden)
                 for leader in ((False, True) if request['can_stay_leader'] else (False,))
                 for hidden in range(request['max_hidden_warbands'] + 1)
                 for destination in (None, *request['legal_regions'])
                 if destination is None or hidden + int(leader) < total)


def disposition_response(choice):
    region, leader, hidden = choice
    return dict(region=region, stay_leader=leader, stay_hidden_warbands=hidden)


def _non_player_disposition(state, region, defender, destinations, preferred, *,
                            pieces, hidden, can_keep_leader):
    """Join a surviving Leader with the most pieces after the Retreat (§8.4.3)."""
    if not destinations:
        return None, can_keep_leader

    has_leader = any(piece['piece_type'] == rc.LEADER for piece in pieces)
    moving = sum(piece['count'] for piece in pieces) - hidden - int(has_leader)
    if preferred not in destinations:
        preferred = max(destinations, key=lambda dest: count_pieces(state, dest, defender))

    if not has_leader:
        if moving:
            preferred = next((dest for dest in destinations
                              if get_leader_in_region(state, dest, defender) is not None),
                             preferred)
        return preferred, False

    companions = {dest: count_pieces(state, dest, defender) + moving for dest in destinations}
    if can_keep_leader:
        # Exclude the Leader himself and the mobile survivors who must leave.
        companions[region] = count_pieces(state, region, defender) - 1 - moving
    maximum = max(companions.values())
    tied = sorted(dest for dest, count in companions.items() if count == maximum)
    selected = tied[0] if len(tied) == 1 else state['rng'].choice(tied)  # §8.3.4
    return (preferred, True) if selected == region else (selected, False)


def execute(state, region, defender, attacker, *, retreat_region, agreements=None,
            non_player=None):
    """Apply one survivor allocation after all Attack losses and timing actions."""
    pieces = mobile_pieces(state, region, defender)
    hidden = sum(p['count'] for p in pieces if p['piece_type'] == rc.WARBAND
                 and p['piece_state'] == rc.HIDDEN and attacker == rc.ROMANS)
    leader = attacker == rc.ROMANS and any(p['piece_type'] == rc.LEADER for p in pieces)
    if non_player is None:
        non_player = defender in state.get('non_player_factions', ())
    destinations = [retreat_region] if retreat_region is not None else []
    if agreements is not None and pieces:
        destinations = legal_regions(state, region, defender, agreements)

    if non_player and pieces:
        retreat_region, leader = _non_player_disposition(
            state, region, defender, destinations, retreat_region,
            pieces=pieces, hidden=hidden, can_keep_leader=leader)
    elif agreements is not None and pieces:
        if retreat_region is not None:
            # A raw legacy answer fixed the destination before Attack.
            if retreat_region not in destinations:
                retreat_region = None
        elif destinations or leader or hidden:
            retreat_region = max(destinations,
                                 key=lambda dest: count_pieces(state, dest, defender), default=None)
            request = dict(kind=RETREAT_DISPOSITION, region=region, attacker=attacker,
                           defender=defender, legal_regions=destinations, pieces=pieces,
                           can_stay_leader=leader, max_hidden_warbands=hidden,
                           window=dict(stage=RETREAT_DISPOSITION, region=region,
                                       attacker=attacker, defender=defender,
                                       card=state.get('current_card')),
                           default=disposition_response((retreat_region, leader, hidden)))
            response = consult_agent(state, defender, request)
            if response is not None and response != {'use_default': True}:
                try:
                    selected = validate_response(request, response)
                except ValueError:
                    selected = request['default']
                retreat_region = selected['region']
                leader, hidden = selected['stay_leader'], selected['stay_hidden_warbands']

    result = dict(moved=[], removed=[], stayed=[])
    for entry in pieces:
        piece, visibility = entry['piece_type'], entry['piece_state']
        stay = 0
        if piece == rc.LEADER:
            stay = int(leader)
        elif piece == rc.WARBAND and visibility == rc.HIDDEN:
            stay = hidden
        if stay:
            result['stayed'].append((piece, stay))
        remaining = entry['count'] - stay
        if remaining == 0:
            continue
        if retreat_region is None:
            remove_piece(state, region, defender, piece, count=remaining,
                         piece_state=visibility, to_fallen=piece == rc.LEGION)
            result['removed'].append((piece, remaining))
        else:
            move_piece(state, region, retreat_region, defender, piece,
                       count=remaining, piece_state=visibility)
            result['moved'].append((piece, remaining))
    return result
