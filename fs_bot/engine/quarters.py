"""Validated Quarters choices, shared by human frontends and Winter execution.

§6.3.2-.3/A6.3.2: only mobile pieces relocate, once to an adjacent agreed
controlled Region; Romans then have the additional relocation to Provincia.
A6.3.1 excludes game-run Arverni. A6.3.3 retains Roman Quartering rules.
Validation previews do not ask for agreements or consume RNG. Execution asks
for the required agreements before committing that faction's relocations.
"""
import copy
from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, move_piece, remove_piece
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.common import _is_devastated
from fs_bot.commands.rally import has_supply_line
from fs_bot.map.map_data import (get_adjacent_for_state, get_playable_regions_for_state)


class QuartersError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise QuartersError(reason)


def _nonnegative(number, label):
    _need(type(number) is int and number >= 0, f"{label} must be a nonnegative integer")


def _clone(state):
    sim = copy.deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    if 'decision_agent' in state:
        sim['decision_agent'] = state['decision_agent']
    return sim


def quarters_factions(state):
    return ((rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.ROMANS)
            if state['scenario'] in rc.BASE_SCENARIOS
            else (rc.BELGAE, rc.AEDUI, rc.GERMANS, rc.ROMANS))


def _host_agrees(state, guest, host, region, request_type):
    if guest == host:
        return True
    if ((state['scenario'] in rc.BASE_SCENARIOS and host == rc.GERMANS)
            or (state['scenario'] in rc.ARIOVISTUS_SCENARIOS and host == rc.ARVERNI)):
        return False
    from fs_bot.engine.agent import consult_agent, AGREEMENT
    response = consult_agent(state, host, {
        'kind': AGREEMENT, 'request_type': request_type,
        'requesting_faction': guest, 'context': {'region': region}})
    if response is not None:
        return bool(response)
    return _bot_host_agrees(state, guest, host, request_type)


def _bot_host_agrees(state, guest, host, request_type):
    if host not in state.get('non_player_factions', set()):
        return False
    from fs_bot.bots.roman_bot import node_r_agreements
    from fs_bot.bots.aedui_bot import node_a_agreements
    from fs_bot.bots.belgae_bot import node_b_agreements
    from fs_bot.bots.arverni_bot import node_v_agreements
    from fs_bot.bots.german_bot import node_g_agreements
    nodes = {rc.ROMANS: node_r_agreements, rc.AEDUI: node_a_agreements,
             rc.BELGAE: node_b_agreements, rc.ARVERNI: node_v_agreements,
             rc.GERMANS: node_g_agreements}
    return bool(nodes[host](state, guest, request_type))


@contextmanager
def agreement_cache(state):
    """Do not ask the same host twice while planning and applying Quarters."""
    from fs_bot.engine.agent import AGREEMENT
    original = state.get('decision_agent')
    replies = {}
    def agent(board, faction, request):
        if request.get('kind') != AGREEMENT:
            return original(board, faction, request) if original else None
        context = request.get('context') or {}
        key = (faction, request.get('requesting_faction'),
               request.get('request_type'),
               None if request.get('request_type') == 'supply_line' else context.get('region'))
        if key not in replies:
            response = original(board, faction, request) if original else None
            if response is None:
                response = _bot_host_agrees(board, request.get('requesting_faction'),
                                           faction, request.get('request_type'))
            replies[key] = response
        return replies[key]
    state['decision_agent'] = agent
    try:
        yield
    finally:
        if original is None:
            state.pop('decision_agent', None)
        else:
            state['decision_agent'] = original


def _controller(state, region):
    control = state['spaces'][region].get('control')
    return next((f for f, flag in rc.FACTION_CONTROL.items() if flag == control), None)


def _move(state, faction, piece, origin, destination, count):
    if piece in rc.FLIPPABLE_PIECES:
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            amount = min(count, count_pieces_by_state(state, origin, faction, piece, visibility))
            if amount:
                move_piece(state, origin, destination, faction, piece,
                           count=amount, piece_state=visibility)
                count -= amount
    elif count:
        move_piece(state, origin, destination, faction, piece, count=count)


def preview_relocations(state, faction, moves, *, confirm=False):
    """Return a detached post-relocation board or raise QuartersError.

    ``confirm=False`` admits destinations requiring another faction's consent;
    ``confirm=True`` obtains that consent before moving any real pieces.
    """
    _need(faction in quarters_factions(state), 'This faction cannot choose Quarters relocations')
    _need(isinstance(moves, (list, tuple)), 'Quarters relocations must be a list')
    # Reject malformed/illegal plans before consulting anyone. Consent can
    # itself require a published NP die roll, which belongs to the live RNG
    # even if the host refuses and the player must choose a different plan.
    if confirm:
        preview_relocations(state, faction, moves, confirm=False)
    sim = _clone(state)
    if confirm:
        sim['rng'] = state['rng']
    playable = set(get_playable_regions_for_state(state, faction))
    types = ((rc.LEADER, rc.LEGION, rc.AUXILIA) if faction == rc.ROMANS
             else (rc.LEADER, rc.WARBAND))
    adjacent, provincia = [], []
    for move in moves:
        _need(isinstance(move, (list, tuple)) and len(move) == 4,
              'Each relocation must contain piece, origin, destination, and count')
        piece, origin, destination, count = move
        _need(piece in types, 'Only the faction\'s mobile pieces may relocate in Quarters')
        _need(isinstance(origin, str) and isinstance(destination, str)
              and origin in playable and destination in playable and origin != destination,
              f'Quarters relocation requires distinct playable Regions: {origin} to {destination}')
        _nonnegative(count, 'Relocation count')
        _need(count > 0 and (piece != rc.LEADER or count == 1),
              'Relocation count must be positive (one for a Leader)')
        (provincia if faction == rc.ROMANS and destination == rc.PROVINCIA
         else adjacent).append(tuple(move))
    # Only pieces present before the adjacent step may take that step.
    remaining = {(r, p): count_pieces(sim, r, faction, p)
                 for r in playable for p in types}
    remaining_states = {(r, p, ps): count_pieces_by_state(sim, r, faction, p, ps)
                        for r in playable for p in types if p in rc.FLIPPABLE_PIECES
                        for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)}
    allocated = []
    permissions = {}
    # §6.3.2-.3 selects the faction's adjacent relocations as one step.
    # Validate all destination hosts before moving the selected pieces:
    # a Legion and its accompanying Auxilia are not separate rules steps,
    # and their arrival can remove the agreeing host's Control. Supply
    # Lines are explicitly determined after this whole adjacent step.
    for piece, origin, destination, count in adjacent:
        _need(destination in get_adjacent_for_state(sim, origin, faction),
              'Quarters relocation must be to an adjacent Region')
        _need(not _is_devastated(sim, destination), 'Quarters destination is Devastated')
        host = _controller(sim, destination)
        excluded = ({rc.GERMANS} if sim['scenario'] in rc.BASE_SCENARIOS
                    else ({rc.ARVERNI, rc.GERMANS} if faction == rc.ROMANS
                          else {rc.ARVERNI}))
        _need(host is not None and host not in excluded,
              'Quarters destination must have eligible faction Control')
        _need(count <= remaining[origin, piece], 'Cannot relocate unavailable pieces or move arrivals again')
        if confirm and host != faction:
            key = (host, destination)
            if key not in permissions:
                permissions[key] = _host_agrees(sim, faction, host, destination, 'quarters')
            _need(permissions[key], f'{host} did not agree to Quarters in {destination}')
        remaining[origin, piece] -= count
        if piece in rc.FLIPPABLE_PIECES:
            # Allocate the original pieces now. Earlier Hidden arrivals
            # must not replace an origin's Revealed/Scouted departing pieces.
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                amount = min(count, remaining_states[origin, piece, visibility])
                if amount:
                    allocated.append((piece, origin, destination, amount, visibility))
                    remaining_states[origin, piece, visibility] -= amount
                    count -= amount
        else:
            allocated.append((piece, origin, destination, count, None))
    for piece, origin, destination, count, visibility in allocated:
        move_piece(sim, origin, destination, faction, piece,
                   count=count, piece_state=visibility)
    # Determine all Supply Line Regions once, after the adjacent step (§6.3.3).
    supply_agreements = {f: True for f in rc.FACTIONS}
    if confirm and any(p != rc.LEADER for p, *_ in provincia):
        for host in rc.FACTIONS:
            if host == rc.ROMANS:
                continue
            regions = [r for r in playable if _controller(sim, r) == host]
            if regions:
                supply_agreements[host] = _host_agrees(
                    sim, rc.ROMANS, host, regions[0], 'supply_line')
    supplied = {origin for piece, origin, _, _ in provincia
                if piece != rc.LEADER and has_supply_line(sim, origin, rc.ROMANS,
                                                         agreements=supply_agreements)}
    for piece, origin, destination, count in provincia:
        _need(count <= count_pieces(sim, origin, faction, piece),
              'Cannot relocate unavailable Roman pieces to Provincia')
        # A direct adjacent move into friendly Provincia is also legal in
        # the first step, even if its origin cannot trace a Supply Line.
        direct_adjacent = (rc.PROVINCIA in get_adjacent_for_state(sim, origin, faction)
                           and _controller(sim, rc.PROVINCIA) == rc.ROMANS
                           and not _is_devastated(sim, rc.PROVINCIA))
        _need(piece == rc.LEADER or origin in supplied or direct_adjacent,
              f'{origin} has no agreed Supply Line to Provincia')
        _move(sim, faction, piece, origin, destination, count)
    refresh_all_control(sim)
    return sim


def apply_relocations(state, faction, moves):
    sim = preview_relocations(state, faction, moves, confirm=True)
    # All changes above used piece helpers, on a detached board. Commit only
    # after the complete relocation plan and required agreements succeeded.
    state['spaces'] = sim['spaces']


def quartering_inventory(state, region):
    return [(rc.LEGION, None, count_pieces(state, region, rc.ROMANS, rc.LEGION))] + [
        (rc.AUXILIA, ps, count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, ps))
        for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)]


def quartering_cost(state, region):
    allies = count_pieces(state, region, rc.ROMANS, rc.ALLY)
    cost = rc.QUARTERS_COST_WITH_ALLY if allies else rc.QUARTERS_COST_WITHOUT_ALLY
    if _is_devastated(state, region):
        return cost * rc.QUARTERS_DEVASTATED_MULTIPLIER
    from fs_bot.cards.capabilities import is_capability_active
    if (state.get('event_modifiers', {}).get('card_A63_quarters_devastated_only')
            or is_capability_active(state, 63, rc.EVENT_UNSHADED)):
        return 0
    return cost


def quartering_allocations(state, decisions):
    """Validate and allocate free/paid/rolling pieces without spending or rolling."""
    _need(isinstance(decisions, dict), 'Roman quartering decisions must be an object')
    order = decisions.get('_pay_order', [])
    _need(isinstance(order, (list, tuple)) and all(isinstance(r, str) for r in order)
          and len(order) == len(set(order)) and all(r in state['spaces'] for r in order),
          'Roman payment order must list distinct Regions')
    _need(all(r == '_pay_order' or r in state['spaces'] for r in decisions),
          'Roman quartering contains an unknown Region')
    budget = state['resources'].get(rc.ROMANS, 0)
    allocations = {}
    for region in list(order) + [r for r in state['spaces'] if r not in order]:
        choice = decisions.get(region, {})
        _need(isinstance(choice, dict), f'Quartering choice for {region} must be an object')
        _need(set(choice) <= {'pay', 'roll', 'free_pieces', 'pay_pieces'},
              'Unknown Roman quartering choice')
        for name in ('pay', 'roll'):
            if name in choice:
                _nonnegative(choice[name], f'Quartering {name}')
        if region == rc.PROVINCIA:
            _need(not choice, 'Provincia pieces Quarter free without a payment choice')
            continue
        remaining = {(p, ps): n for p, ps, n in quartering_inventory(state, region)}
        slots = min(sum(remaining.values()), count_pieces(state, region, rc.ROMANS, rc.ALLY)
                    + count_pieces(state, region, rc.ROMANS, rc.FORT))
        def take(entries, limit, label):
            _need(isinstance(entries, (list, tuple)), f'{label} must be a list of piece/state/count entries')
            selected = []
            for entry in entries:
                _need(isinstance(entry, (list, tuple)) and len(entry) == 3,
                      f'{label} needs piece/state/count entries')
                piece, visibility, n = entry
                _nonnegative(n, label)
                _need((piece, visibility) in remaining and n <= remaining[piece, visibility],
                      f'{label} selects unavailable pieces')
                _need(n <= limit, f'{label} exceeds its allocation')
                remaining[piece, visibility] -= n
                limit -= n
                selected.extend([(piece, visibility)] * n)
            return selected
        def select(limit, preference):
            entries = []
            for piece, visibility in preference:
                number = min(remaining[piece, visibility], limit)
                if number:
                    entries.append((piece, visibility, number))
                    limit -= number
            return entries
        # §8.8.7: the standard plan leaves Auxilia at Forts/Allies. Other
        # allocations are a human choice, exposed explicitly by the frontend.
        aux_first = [(rc.AUXILIA, ps) for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)] + [(rc.LEGION, None)]
        legion_first = [(rc.LEGION, None)] + aux_first[:-1]
        free = take(choice.get('free_pieces', select(slots, aux_first)), slots, 'free_pieces')
        cost = quartering_cost(state, region)
        capacity = sum(remaining.values())
        requested = choice.get('pay', 0)
        if 'pay_pieces' in choice:
            paid = take(choice['pay_pieces'], capacity, 'pay_pieces')
            if 'pay' in choice:
                _need(choice['pay'] == len(paid), 'pay count disagrees with pay_pieces')
            _need(len(paid) * cost <= budget, 'Not enough Roman Resources for selected payments')
        else:
            n = min(requested, capacity, budget // cost if cost else capacity)
            if cost == 0:
                n = capacity  # Card 63/A63: no costs outside Devastation.
            paid = take(select(n, legion_first), n, 'pay_pieces')
        budget -= len(paid) * cost
        rolling = [(p, ps) for p, ps in reversed(legion_first) for _ in range(remaining[p, ps])]
        # Legacy roll counts express the intended unpaid remainder. If
        # Resources run out, every additional unpaid piece must still roll.
        allocations[region] = {'free': free, 'paid': paid, 'roll': rolling, 'cost': len(paid) * cost}
    return allocations


def validate_quarters_plan(state, relocations, *, faction=None):
    """Return errors without mutation, RNG draws, or human agreement prompts."""
    try:
        _need(isinstance(relocations, dict), 'Quarters plan must be an object')
        allowed = set(quarters_factions(state)) | {rc.ROMANS + '_quartering'}
        if faction is not None:
            allowed = {faction} | ({rc.ROMANS + '_quartering'} if faction == rc.ROMANS else set())
        _need(set(relocations) <= allowed, 'Quarters plan may choose only the acting faction\'s pieces')
        sim = _clone(state)
        for owner in quarters_factions(sim):
            if owner in relocations:
                sim = preview_relocations(sim, owner, relocations[owner])
        if rc.ROMANS + '_quartering' in relocations:
            quartering_allocations(sim, relocations[rc.ROMANS + '_quartering'])
        return []
    except (ValueError, TypeError, KeyError) as exc:
        return [str(exc)]
