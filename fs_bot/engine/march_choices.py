"""Human choices within a Marching group (§3.2.2/3.3.2).

The action plan chooses counts. These reactive choices identify the actual
Hidden/Revealed pieces after origin flipping, or the carried pieces to drop.
They do not move pieces, roll dice, or change the action's selected counts.
"""

from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state
from fs_bot.engine.agent import consult_agent

MARCH_COHORT = "march_cohort"
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
            visibility[ps] -= n
    group[piece] -= count
