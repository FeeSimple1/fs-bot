"""Human choices about the physical members of a Marching group (§3.2.2/3.3.2)."""

from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state
from fs_bot.engine.agent import consult_agent

MARCH_COHORT = "march_cohort"
MARCH_DROPOFF = "march_dropoff"
VISIBILITIES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


@contextmanager
def chooser_scope(state, actor, chooser):
    """An engine-owned grant may delegate German March choices (A34)."""
    if actor == chooser:
        yield
        return
    missing = object()
    previous = state.get('_march_chooser', missing)
    state['_march_chooser'] = {'actor': actor, 'chooser': chooser}
    try:
        yield
    finally:
        if previous is missing:
            state.pop('_march_chooser', None)
        else:
            state['_march_chooser'] = previous


def _chooser(state, faction):
    grant = state.get('_march_chooser', {})
    return grant['chooser'] if grant.get('actor') == faction else faction


def validate_response(request, response):
    if not isinstance(response, dict) or set(response) != {"counts"}:
        raise ValueError("March selection requires counts by visibility.")
    counts = response["counts"]
    available = request["available"]
    if (not isinstance(counts, dict) or set(counts) - set(available)
            or any(type(n) is not int or not 0 <= n <= available[ps]
                   for ps, n in counts.items())
            or sum(counts.values()) != request["count"]):
        raise ValueError("Choose exactly the requested number from the offered pieces.")
    return response


def choose_visibility(state, faction, region, piece, count, available, *,
                      phase, physical_owner=None):
    """Choose an exact subset; bot/default selection retains Hidden first."""
    from fs_bot.engine.game_engine import get_sop_factions
    chooser = _chooser(state, faction)
    available = {ps: available.get(ps, 0) for ps in VISIBILITIES
                 if available.get(ps, 0) > 0}
    remaining, default = count, {}
    for ps, n in available.items():
        take = min(remaining, n)
        if take:
            default[ps] = take
            remaining -= take
    if remaining:
        raise ValueError("March selection exceeds the carried pieces.")
    if (count == 0 or count == sum(available.values()) or len(available) < 2
            or chooser not in get_sop_factions(state)
            or chooser in state.get("non_player_factions", set())):
        return default
    request = {"kind": MARCH_COHORT, "phase": phase, "region": region,
               "piece_type": piece, "count": count, "available": available}
    if chooser != faction:
        request['acting_faction'] = faction
    if physical_owner is not None:
        request["physical_owner"] = physical_owner
    response = consult_agent(state, chooser, request)
    if response is None or response == {"use_default": True}:
        return default
    validate_response(request, response)
    return {ps: n for ps, n in response["counts"].items() if n}


def select_origin_visibility(state, faction, origin, group):
    """Record human-selected visibility after all origin pieces have flipped."""
    from fs_bot.engine.diviciacus import select_march_group
    if select_march_group(state, faction, origin, group):
        return
    from fs_bot.engine.game_engine import get_sop_factions
    chooser = _chooser(state, faction)
    if (chooser not in get_sop_factions(state)
            or chooser in state.get("non_player_factions", set())):
        return
    ledger = group.setdefault("_march_visibility", {})
    for piece in (rc.AUXILIA, rc.WARBAND):
        count = group.get(piece, 0)
        if not count:
            continue
        if piece == rc.WARBAND and "german_warbands" in group:
            # The plan already selects each physical colour under Enlist.
            # Choose visibility within those counts, without changing owners.
            from fs_bot.commands.sa_enlist import borrowed_count
            german = group["german_warbands"]
            owners = group.setdefault("_march_owner_visibility", {})
            ledger[piece] = {}
            for owner, n in ((rc.GERMANS, german), (rc.BELGAE, count - german)):
                if not n:
                    continue
                available = {
                    ps: (borrowed_count(state, origin, ps) if owner == rc.GERMANS
                         else state["spaces"][origin].get("pieces", {}).get(
                             owner, {}).get(ps, {}).get(piece, 0))
                    for ps in VISIBILITIES}
                selected = choose_visibility(state, faction, origin, piece, n,
                    available, phase="formation", physical_owner=owner)
                owners[owner] = selected
                for ps, amount in selected.items():
                    ledger[piece][ps] = ledger[piece].get(ps, 0) + amount
        else:
            available = {ps: count_pieces_by_state(state, origin, faction, piece, ps)
                         for ps in VISIBILITIES}
            ledger[piece] = choose_visibility(state, faction, origin, piece,
                count, available, phase="formation")


def drop_visibility(state, faction, region, group, piece, count):
    """Remove only the selected dropped pieces from the moving cohort."""
    from fs_bot.engine.diviciacus import drop_march_group
    if drop_march_group(state, faction, region, group, piece, count):
        return
    visibility = group.get("_march_visibility", {}).get(piece)
    if visibility is not None:
        dropped = choose_visibility(state, faction, region, piece, count,
                                    visibility, phase="dropoff")
        for ps, n in dropped.items():
            owners = group.get('_march_owner_visibility')
            if owners is not None and piece == rc.WARBAND:
                german = owners.get(rc.GERMANS, {}).get(ps, 0)
                native = owners.get(rc.BELGAE, {}).get(ps, 0)
                lower, upper = max(0, n - native), min(n, german)
                borrowed = upper  # Existing Enlist physical-helper default.
                from fs_bot.engine.game_engine import get_sop_factions
                chooser = _chooser(state, faction)
                if (lower != upper and chooser in get_sop_factions(state)
                        and chooser not in state.get('non_player_factions', ())
                        and not state.get('_diviciacus_preview')):
                    request = {'kind': 'force_cohort', 'operation': 'drop off',
                        'region': region, 'piece_type': piece, 'piece_state': ps,
                        'count': n, 'available': {'selected': german, 'other': native},
                        'selected_label': 'Enlisted German Warbands',
                        'other_label': 'Belgic Warbands'}
                    response = consult_agent(state, chooser, request)
                    if response is not None:
                        from fs_bot.engine.diviciacus import validate_force_cohort_response
                        validate_force_cohort_response(request, response)
                        if 'counts' in response:
                            borrowed = response['counts'].get('selected', 0)
                owners[rc.GERMANS][ps] -= borrowed
                owners[rc.BELGAE][ps] -= n - borrowed
                group['german_warbands'] -= borrowed
            visibility[ps] -= n
    group[piece] -= count


def _dropoff_key(entry):
    return entry['faction'], entry['piece_type'], entry['piece_state']


def validate_dropoffs(request, response):
    """Check an entire physical allocation before changing the moving group."""
    if (not isinstance(response, dict) or set(response) != {'dropoffs'}
            or not isinstance(response['dropoffs'], list)):
        raise ValueError('Choose a dropoffs list of offered pieces, or use the default.')
    available = {_dropoff_key(entry): entry['count'] for entry in request['pieces']}
    left = request['max_dropoffs']
    for entry in response['dropoffs']:
        if (not isinstance(entry, dict)
                or set(entry) != {'faction', 'piece_type', 'piece_state', 'count'}
                or not isinstance(entry['faction'], str)
                or not isinstance(entry['piece_type'], str)
                or not (entry['piece_state'] is None or isinstance(entry['piece_state'], str))):
            raise ValueError('Name each offered piece by faction, type and visibility.')
        count = entry['count']
        if type(count) is not int or not 0 < count <= available.pop(_dropoff_key(entry), 0):
            raise ValueError('Choose each offered cohort once, within its available count.')
        left -= count
    if left < 0:
        raise ValueError('Leave at least one piece in the moving group.')
    return response


def offer_dropoffs(state, faction, region, group, *, origin, step, destination,
                   group_index):
    """Let the current group leave counters here before the next departure."""
    agent = state.get('decision_agent')
    if state.get('_diviciacus_preview') or not (
            getattr(agent, 'supports_march_dropoffs', False)
            or getattr(getattr(agent, '__self__', None), 'supports_march_dropoffs', False)):
        return []
    chooser = _chooser(state, faction)
    if chooser in state.get('non_player_factions', ()):
        return []
    total = int(group.get(rc.LEADER) is not None) + sum(
        group.get(piece, 0) for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND))
    if total < 2:
        return []

    from fs_bot.commands.march import _max_steps_for_group
    from fs_bot.engine.march_timing import COHORT, apply_removals, cohorts
    # A live decision can shorten the route. The remaining pieces still
    # need to be able to take the immediate next hop.
    keep_leader = step >= _max_steps_for_group(state, region, faction, {})
    owners = {faction, *group.get('_diviciacus_owners', {}),
              *group.get('_march_owner_visibility', {})}
    pieces = []
    for owner in rc.FACTIONS:
        if owner not in owners:
            continue
        for entry in cohorts(state, faction, region, group, owner):
            if keep_leader and entry['piece_type'] == rc.LEADER:
                continue
            pieces.append(dict(faction=owner, piece_type=entry['piece_type'],
                               piece_state=entry.get('piece_state'), count=entry['count']))
    if not pieces:
        return []
    window = dict(phase='sequence_of_play', stage=MARCH_DROPOFF,
                  card=state.get('current_card'), origin=origin, region=region,
                  group_index=group_index, step=step, destination=destination)
    request = dict(kind=MARCH_DROPOFF, faction=chooser, acting_faction=faction,
                   region=region, destination=destination, pieces=pieces, window=window,
                   max_dropoffs=min(total - 1, sum(entry['count'] for entry in pieces)))
    if group.get(rc.LEADER) is not None:
        request['leader'] = group[rc.LEADER]
    response = consult_agent(state, chooser, request)
    if response is None or (isinstance(response, dict) and set(response) == {'use_default'}
                            and response['use_default'] is True):
        return []
    selected = validate_dropoffs(request, response)['dropoffs']
    apply_removals(state, faction, group, [dict(entry, cohort=COHORT) for entry in selected])
    return selected
