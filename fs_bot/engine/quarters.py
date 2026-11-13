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


# A Roman Provincia row can explicitly choose its movement step.
ADJACENT_STEP = 'adjacent'
SUPPLY_STEP = 'supply'


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


def eligible_quarters_host(state, guest, host):
    """Control required for the adjacent Quarters step, before consent.

    §6.3.3 excludes German Control even in Ariovistus: A6.3.3 retains
    Roman Quartering unchanged. The game-run faction cannot host either.
    """
    excluded = ({rc.GERMANS} if state['scenario'] in rc.BASE_SCENARIOS
                else {rc.ARVERNI})
    if guest == rc.ROMANS:
        excluded.add(rc.GERMANS)
    return host in rc.FACTIONS and host not in excluded


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


class _QuartersAgreementCache:
    """Trusted engine scope shared by planning and actual declarations."""
    def __init__(self, original):
        self.original = original
        self.replies = {}

    def __deepcopy__(self, memo):
        # Detached Quarters validation uses the same live agreement scope.
        return self

    @property
    def supports_action_windows(self):
        from fs_bot.engine.action_windows import enabled
        return enabled({'decision_agent': self.original})

    def __call__(self, board, faction, request):
        from fs_bot.engine.agent import AGREEMENT
        if request.get('kind') != AGREEMENT:
            return self.original(board, faction, request) if self.original else None
        context = request.get('context') or {}
        key = (faction, request.get('requesting_faction'),
               request.get('request_type'),
               None if request.get('request_type') == 'supply_line' else context.get('region'))
        if key not in self.replies:
            if (request.get('request_type') == 'supply_line'
                    and faction in board.get('non_player_factions', ())):
                from fs_bot.bots.bot_common import np_agrees_to_supply_line
                response = np_agrees_to_supply_line(
                    faction, request.get('requesting_faction'), board)
            else:
                if (request.get('request_type') == 'supply_line'
                        and request.get('requesting_faction') == rc.ROMANS):
                    # Planning queries can reach a different Region first.
                    # The cached declaration covers this host for Quarters.
                    declaration = supply_declaration_context(board, faction)
                    if declaration:
                        request = dict(request, context=declaration)
                response = self.original(board, faction, request) if self.original else None
                if response is None:
                    response = _bot_host_agrees(board, request.get('requesting_faction'),
                                               faction, request.get('request_type'))
            self.replies[key] = response
        return self.replies[key]


def cached_np_supply_answer(state, guest, host, region):
    """Use an engine-owned Quarters cache, never an external NP callback."""
    agent = state.get('decision_agent')
    if not isinstance(agent, _QuartersAgreementCache):
        return None
    from fs_bot.engine.agent import AGREEMENT
    return agent(state, host, {
        'kind': AGREEMENT, 'request_type': 'supply_line',
        'requesting_faction': guest, 'context': {'region': region}})


@contextmanager
def agreement_cache(state):
    """Do not ask the same host twice while planning and applying Quarters."""
    original = state.get('decision_agent')
    state['decision_agent'] = _QuartersAgreementCache(original)
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


def supply_host_regions(state, host):
    """List the host's playable Regions in map order for one declaration."""
    return [region for region in get_playable_regions_for_state(state, rc.ROMANS)
            if _controller(state, region) == host]


def supply_declaration_context(state, host):
    regions = supply_host_regions(state, host)
    return ({'region': regions[0], 'regions': regions, 'phase': 'quarters'}
            if regions else None)


def relocation_parts(move):
    """Read legacy four-entry moves or an exact fifth visibility entry."""
    _need(isinstance(move, (list, tuple)) and len(move) in (4, 5),
          'Each relocation needs piece, origin, destination, count and optional visibility')
    piece, origin, destination, count = move[:4]
    _need(all(isinstance(value, str) for value in (piece, origin, destination)),
          'Quarters moves must name pieces and Regions')
    _nonnegative(count, 'Relocation count')
    _need(count > 0 and (piece != rc.LEADER or count == 1),
          'Relocation count must be positive (one for a Leader)')
    visibility = move[4] if len(move) == 5 else None
    if len(move) == 5:
        _need(piece in rc.FLIPPABLE_PIECES and visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED),
              'Explicit Quarters visibility requires Hidden/Revealed/Scouted mobile pieces')
    return piece, origin, destination, count, visibility


def relocation_row(move):
    """Return the physical move and an optional Provincia step choice."""
    if (isinstance(move, (list, tuple)) and len(move) >= 5
            and move[-1] in (ADJACENT_STEP, SUPPLY_STEP)):
        return move[:-1], move[-1]
    return move, None


def _reserve_states(remaining, origin, piece, count, visibility):
    states = (visibility,) if visibility is not None else (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
    _need(count <= sum(remaining.get((origin, piece, ps), 0) for ps in states),
          'Cannot relocate unavailable visibility cohorts or move arrivals again')
    allocated = []
    for ps in states:
        amount = min(count, remaining.get((origin, piece, ps), 0))
        if amount:
            remaining[origin, piece, ps] -= amount
            allocated.append((ps, amount))
            count -= amount
    return allocated


def _state_budget(state, faction):
    return {(r, p, ps): count_pieces_by_state(state, r, faction, p, ps)
            for r in get_playable_regions_for_state(state, faction)
            for p in rc.FLIPPABLE_PIECES for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)}


def _move(state, faction, piece, origin, destination, count, visibility=None):
    if piece in rc.FLIPPABLE_PIECES:
        available = {(origin, piece, ps): count_pieces_by_state(state, origin, faction, piece, ps)
                     for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)}
        allocated = _reserve_states(available, origin, piece, count, visibility)
        for ps, amount in allocated:
            move_piece(state, origin, destination, faction, piece, count=amount, piece_state=ps)
    elif count:
        move_piece(state, origin, destination, faction, piece, count=count)


def _adjacent_allocations(state, faction, moves, *, confirm):
    """Reserve original pieces and obtain consent before any adjacent moves."""
    if not moves:
        return []
    remaining = {}
    remaining_states = _state_budget(state, faction)
    allocated = []
    permissions = {}
    for piece, origin, destination, count, visibility in map(relocation_parts, moves):
        _need(destination in get_adjacent_for_state(state, origin, faction),
              'Quarters relocation must be to an adjacent Region')
        _need(not _is_devastated(state, destination), 'Quarters destination is Devastated')
        host = _controller(state, destination)
        _need(eligible_quarters_host(state, faction, host),
              'Quarters destination must have eligible faction Control')
        key = (origin, piece)
        if key not in remaining:
            remaining[key] = count_pieces(state, origin, faction, piece)
        _need(count <= remaining[key], 'Cannot relocate unavailable pieces or move arrivals again')
        if confirm and host != faction:
            host_key = (host, destination)
            if host_key not in permissions:
                permissions[host_key] = _host_agrees(state, faction, host, destination, 'quarters')
            _need(permissions[host_key], f'{host} did not agree to Quarters in {destination}')
        remaining[key] -= count
        if piece in rc.FLIPPABLE_PIECES:
            for ps, amount in _reserve_states(remaining_states, origin, piece, count, visibility):
                allocated.append((piece, origin, destination, amount, ps))
        else:
            allocated.append((piece, origin, destination, count, None))
    return allocated


def _move_allocated(state, faction, allocated):
    for piece, origin, destination, count, visibility in allocated:
        move_piece(state, origin, destination, faction, piece,
                   count=count, piece_state=visibility)


def _implicit_provincia_adjacencies(state, adjacent, provincia):
    """Interpret untagged rows as Supply where a route could exist.

    Legacy rows can share a Supply path that a premature departure would
    break. Forecast on the board with the declared adjacent moves first.
    """
    host = _controller(state, rc.PROVINCIA) if provincia else None
    if not eligible_quarters_host(state, rc.ROMANS, host) or _is_devastated(state, rc.PROVINCIA):
        return set()
    candidates = [move for move, step in provincia
                  if move[0] != rc.LEADER and step is None
                  and rc.PROVINCIA in get_adjacent_for_state(state, move[1], rc.ROMANS)]
    if not candidates:
        return set()
    projection = state
    if adjacent:
        projection = _clone(state)
        allocated = _adjacent_allocations(state, rc.ROMANS, adjacent, confirm=False)
        _move_allocated(projection, rc.ROMANS, allocated)
    all_agree = dict.fromkeys(rc.FACTIONS, True)
    return {origin for origin in dict.fromkeys(move[1] for move in candidates)
            if not has_supply_line(projection, origin, rc.ROMANS, agreements=all_agree)}


def preview_relocations(state, faction, moves, *, confirm=False, _live=False,
                        _outcome=None):
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
    sim = state if _live else _clone(state)
    if confirm:
        sim['rng'] = state['rng']
    playable = set(get_playable_regions_for_state(state, faction))
    types = ((rc.LEADER, rc.LEGION, rc.AUXILIA) if faction == rc.ROMANS
             else (rc.LEADER, rc.WARBAND))
    adjacent, provincia = [], []
    for move in moves:
        row, step = relocation_row(move)
        piece, origin, destination, count, visibility = relocation_parts(row)
        _need(piece in types, 'Only the faction\'s mobile pieces may relocate in Quarters')
        _need(origin in playable and destination in playable and origin != destination,
              f'Quarters relocation requires distinct playable Regions: {origin} to {destination}')
        to_provincia = faction == rc.ROMANS and destination == rc.PROVINCIA
        _need(not step or (to_provincia and (step == ADJACENT_STEP or piece != rc.LEADER)),
              'A movement step can be specified for Roman moves to Provincia '
              '(Supply transfers are for troops)')
        if to_provincia and step != ADJACENT_STEP:
            provincia.append((tuple(row), step))
        else:
            adjacent.append(tuple(row))
    adjacent_origins = _implicit_provincia_adjacencies(sim, adjacent, provincia)
    transfers = []
    for move, step in provincia:
        if step is None and move[0] != rc.LEADER and move[1] in adjacent_origins:
            adjacent.append(move)
        else:
            transfers.append(move)
    # §6.3.2-.3 selects the faction's adjacent relocations as one step.
    # Supply Lines use the board after that step, including its Provincia moves.
    _move_allocated(sim, faction, _adjacent_allocations(sim, faction, adjacent, confirm=confirm))
    if _live and faction == rc.ROMANS:
        from fs_bot.engine.action_windows import window
        window(sim, 'quarters_before_supply', faction=faction)
    # Freeze Supply after the adjacent step (§6.3.3). The live continuation
    # may select a different origin, so include the full set when needed.
    supply_origins = {origin for piece, origin, *_ in transfers if piece != rc.LEADER}
    if _live and supply_origins:
        supply_origins = playable
    supply_agreements = dict.fromkeys(rc.FACTIONS, True)
    if confirm and supply_origins:
        for host in rc.FACTIONS:
            if host == rc.ROMANS:
                continue
            regions = supply_host_regions(sim, host)
            if regions:
                supply_agreements[host] = _host_agrees(
                    sim, rc.ROMANS, host, regions[0], 'supply_line')
    supplied = {origin for origin in supply_origins if has_supply_line(
        sim, origin, rc.ROMANS, agreements=supply_agreements)}
    if _live and faction == rc.ROMANS:
        # Supply Line Regions are fixed now for the rest of Quarters. A
        # Spring entry between the adjacent step and this check may have
        # invalidated a previously legal Provincia plan; ask only for the
        # unfinished step, without replaying committed adjacent moves.
        legal_moves = _provincia_options(sim, supplied)
        request = {'kind': 'quarters_provincia', 'faction': rc.ROMANS,
                   'original_moves': [list(move) for move in transfers],
                   'legal_moves': legal_moves}
        try:
            validate_provincia_response(sim, request, {'moves': transfers})
        except QuartersError as exc:
            request['errors'] = [str(exc)]
            transfers = _reconsider_provincia(sim, request)
            if _outcome is not None:
                _outcome['reconsider_quartering'] = True
        for index, move in enumerate(transfers):
            piece, origin, destination, count, visibility = relocation_parts(move)
            window(sim, 'quarters_provincia_move', faction=faction,
                   region=origin, index=index)
            _move(sim, faction, piece, origin, destination, count, visibility)
        refresh_all_control(sim)
        if _outcome is not None:
            _outcome['moves'] = adjacent + [tuple(move) for move in transfers]
        return sim
    for move in transfers:
        piece, origin, destination, count, visibility = relocation_parts(move)
        _need(count <= count_pieces(sim, origin, faction, piece),
              'Cannot relocate unavailable Roman pieces to Provincia')
        _need(piece == rc.LEADER or origin in supplied,
              f'{origin} has no agreed Supply Line to Provincia')
        _move(sim, faction, piece, origin, destination, count, visibility)
    refresh_all_control(sim)
    return sim


def apply_relocations(state, faction, moves):
    from fs_bot.engine.action_windows import scope
    with scope(state, phase='winter'):
        return _apply_relocations(state, faction, moves)


def _apply_relocations(state, faction, moves):
    from fs_bot.engine.action_windows import enabled, is_preview
    outcome = {'moves': [relocation_row(move)[0] for move in moves],
               'reconsider_quartering': False}
    if enabled(state) and not is_preview(state):
        from fs_bot.engine.spring import atomic
        # Missing responses restore the live step while its outer frontend
        # retains accepted decisions for replay. A published NP refusal die
        # remains consumed just as in the legacy detached execution path.
        refused_rng = None
        try:
            with atomic(state):
                try:
                    preview_relocations(state, faction, moves, confirm=True, _live=True,
                                        _outcome=outcome)
                except QuartersError:
                    refused_rng = state['rng'].getstate()
                    raise
        except QuartersError:
            state['rng'].setstate(refused_rng)
            raise
        return outcome
    sim = preview_relocations(state, faction, moves, confirm=True)
    # All changes above used piece helpers, on a detached board. Commit only
    # after the complete relocation plan and required agreements succeeded.
    state['spaces'] = sim['spaces']
    # Departures can end Circumvallation even on the detached legacy path.
    # Commit its marker effects with the accepted physical relocations.
    state['markers'] = sim['markers']
    return outcome


def _provincia_options(state, supplied):
    options = []
    for region in sorted(get_playable_regions_for_state(state, rc.ROMANS)):
        if region == rc.PROVINCIA:
            continue
        for piece in (rc.LEGION, rc.AUXILIA, rc.LEADER):
            count = count_pieces(state, region, rc.ROMANS, piece)
            if count and (piece == rc.LEADER or region in supplied):
                options.append([piece, region, rc.PROVINCIA, count])
    return options


def validate_provincia_response(state, request, response):
    """Validate a continuation against the frozen, authored Supply choices."""
    if isinstance(response, dict) and (response == {'decline': True}
                                      or response == {'use_default': True}):
        _need(type(next(iter(response.values()))) is bool,
              'Provincia decline/default must be boolean')
        return response
    _need(isinstance(response, dict) and set(response) == {'moves'},
          'Provincia continuation requires moves or an explicit decline')
    _need(isinstance(response['moves'], (list, tuple)), 'Provincia moves must be a list')
    remaining = {(piece, origin, destination): count
                 for piece, origin, destination, count in request['legal_moves']}
    states = _state_budget(state, rc.ROMANS)
    for move in response['moves']:
        piece, origin, destination, count, visibility = relocation_parts(move)
        key = (piece, origin, destination)
        _need(key in remaining, f'{origin} has no agreed Supply Line to Provincia')
        _need(count <= remaining[key], 'Provincia move selects unavailable pieces')
        remaining[key] -= count
        if piece in rc.FLIPPABLE_PIECES:
            _reserve_states(states, origin, piece, count, visibility)
    return response


def _reconsider_provincia(state, request):
    from fs_bot.engine.agent import consult_agent
    while True:
        response = (consult_agent(state, rc.ROMANS, request)
                    if rc.ROMANS not in state.get('non_player_factions', ()) else None)
        if response is not None:
            try:
                validate_provincia_response(state, request, response)
            except QuartersError as exc:
                request = dict(request, errors=[str(exc)])
                continue
        if response is None or response.get('use_default') is True:
            remaining = {(p, origin, dest): n for p, origin, dest, n in request['legal_moves']}
            states = _state_budget(state, rc.ROMANS)
            result = []
            for move in request['original_moves']:
                p, origin, dest, n, visibility = relocation_parts(move)
                count = min(n, remaining.get((p, origin, dest), 0))
                if p in rc.FLIPPABLE_PIECES:
                    available = sum(states.get((origin, p, ps), 0) for ps in
                                    ((visibility,) if visibility is not None else
                                     (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)))
                    count = min(count, available)
                if count:
                    entry = (p, origin, dest, count)
                    result.append(entry + (visibility,) if visibility is not None else entry)
                    remaining[p, origin, dest] -= count
                    if p in rc.FLIPPABLE_PIECES:
                        _reserve_states(states, origin, p, count, visibility)
            return result
        return [] if response.get('decline') else response['moves']


def validate_payment_response(state, request, response):
    """Check revised payments after the actual relocation outcome."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    _need(isinstance(response, dict) and set(response) == {'payments'},
          'Revised Quartering requires payments or an explicit default')
    quartering_allocations(state, response['payments'])
    return response


def reconsider_quartering(state):
    """A changed Provincia result requires fresh choices for pieces left behind."""
    from fs_bot.engine.agent import consult_agent
    request = {'kind': 'quarters_payment', 'faction': rc.ROMANS,
               'reason': 'Provincia relocations changed; choose for the pieces now remaining.'}
    while True:
        response = (consult_agent(state, rc.ROMANS, request)
                    if rc.ROMANS not in state.get('non_player_factions', ()) else None)
        if response is not None:
            try:
                validate_payment_response(state, request, response)
            except QuartersError as exc:
                request = dict(request, errors=[str(exc)])
                continue
        if response is not None and 'payments' in response:
            return response['payments']
        # §8.8.7 standard payment order, applied to the actual pieces now
        # present without replanning or replaying any completed relocation.
        order, payments = [], {}
        for region in state['spaces']:
            number = sum(n for _, _, n in quartering_inventory(state, region))
            if region == rc.PROVINCIA or not number:
                continue
            priority = (0 if count_pieces(state, region, rc.ROMANS, rc.ALLY)
                        else 2 if _is_devastated(state, region) else 1)
            order.append((priority, region))
            payments[region] = {'pay': number}
        payments['_pay_order'] = [region for _, region in sorted(order)]
        return payments


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
