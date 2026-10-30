"""Keep an explicitly selected moving group distinct at action windows."""

from fs_bot import rules_consts as rc

COHORT = "moving_group"
_STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def _take(available, count):
    result = {}
    for visibility in _STATES:
        n = min(available.get(visibility, 0), count)
        if n:
            result[visibility] = n
            count -= n
    if count:
        raise ValueError("Marching counters are no longer present.")
    return result


def freeze_members(state, faction, region, group):
    """Retain the existing mechanical selection, including bot/default order.

    Human origin choices have already populated these ledgers. A default
    group also needs exact ownership before removal can distinguish it from
    residents; its selection remains Hidden first and Enlisted first within
    each selected visibility, matching the existing movement helpers.
    """
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.commands.sa_enlist import BORROW_KEY
    from fs_bot.engine.diviciacus import KEY, select_march_group
    div = state.get(KEY, {})
    if div.get("faction") == faction and "_diviciacus_owners" not in group:
        select_march_group(state, faction, region, group)
    visibility = group.setdefault("_march_visibility", {})
    if faction == rc.BELGAE and BORROW_KEY in state:
        ledger = group.get("_march_owner_visibility")
        if ledger is None:
            raw = state["spaces"][region].get("pieces", {}).get(faction, {})
            own = {ps: raw.get(ps, {}).get(rc.WARBAND, 0) for ps in _STATES}
            loan = state[BORROW_KEY].get("pieces", {}).get(region, {})
            count = group.get(rc.WARBAND, 0)
            if "german_warbands" in group:
                germans = _take(loan, group["german_warbands"])
                belgae = _take(own, count - group["german_warbands"])
            else:
                selected = visibility.get(rc.WARBAND)
                if selected is None:
                    selected = _take({ps: own[ps] + loan.get(ps, 0)
                                      for ps in _STATES}, count)
                germans, belgae = {}, {}
                for ps, n in selected.items():
                    borrowed = min(n, loan.get(ps, 0))
                    germans[ps], belgae[ps] = borrowed, n - borrowed
            ledger = group["_march_owner_visibility"] = {
                rc.GERMANS: germans, rc.BELGAE: belgae}
            group["german_warbands"] = sum(germans.values())
            visibility[rc.WARBAND] = {
                ps: germans.get(ps, 0) + belgae.get(ps, 0) for ps in _STATES}
    for piece in (rc.AUXILIA, rc.WARBAND):
        if piece not in visibility and group.get(piece, 0):
            visibility[piece] = _take({ps: count_pieces_by_state(
                state, region, faction, piece, ps) for ps in _STATES}, group[piece])


def cohorts(state, faction, region, group, owner):
    """Return only the outer executor's selected physical counters."""
    if owner is None:
        return []
    from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
    from fs_bot.engine.diviciacus import KEY
    freeze_members(state, faction, region, group)
    result = []
    def add(piece, count, visibility=None, loan=None):
        if count:
            item = {"id": COHORT, "label": "Moving group", "region": region,
                    "piece_type": piece, "count": count}
            if visibility is not None:
                item["piece_state"] = visibility
            if loan is not None:
                item["loan_kind"] = loan
            result.append(item)
    if owner == faction:
        add(rc.LEADER, int(group.get(rc.LEADER) is not None))
        add(rc.LEGION, group.get(rc.LEGION, 0))
    div = state.get(KEY, {})
    for piece in (rc.AUXILIA, rc.WARBAND):
        physical, loan, selected = piece, None, {}
        if piece == div.get("piece_type") and "_diviciacus_owners" in group:
            selected = group["_diviciacus_owners"].get(owner, {})
            if owner == div.get("lender"):
                physical, loan = div["physical_type"], "diviciacus"
        elif piece == rc.WARBAND and "_march_owner_visibility" in group:
            selected = group["_march_owner_visibility"].get(owner, {})
            if owner == rc.GERMANS:
                loan = "enlist"
        elif owner == faction:
            selected = group.get("_march_visibility", {}).get(piece, {})
            free = state.get(FREE_FORCE_KEY, {})
            if free and owner == free.get("faction", rc.GERMANS) and piece == rc.WARBAND:
                loan = "free_force"
        for visibility, count in selected.items():
            add(physical, count, visibility, loan)
    return result


def apply_removals(state, faction, group, effects):
    """Subtract the exact selected members; residents do not change a group."""
    from fs_bot.engine.diviciacus import KEY
    div = state.get(KEY, {})
    for effect in effects:
        if effect.get("cohort") != COHORT:
            continue
        piece, owner, count = effect["piece_type"], effect["faction"], effect["count"]
        if (owner == div.get("lender") and piece == div.get("physical_type")
                and "_diviciacus_owners" in group):
            piece = div["piece_type"]
        if piece == rc.LEADER:
            if count != 1 or group.get(piece) is None:
                raise ValueError("Removed Leader was not in the moving group.")
            group[piece] = None
            continue
        if group.get(piece, 0) < count:
            raise ValueError("Removed counters exceed the moving group.")
        group[piece] -= count
        if piece not in (rc.AUXILIA, rc.WARBAND):
            continue
        ps = effect["piece_state"]
        ledgers = [group.get("_march_visibility", {}).get(piece)]
        if "_diviciacus_owners" in group and piece == div.get("piece_type"):
            ledgers.append(group["_diviciacus_owners"].get(owner))
        elif "_march_owner_visibility" in group and piece == rc.WARBAND:
            ledgers.append(group["_march_owner_visibility"].get(owner))
            if owner == rc.GERMANS:
                group["german_warbands"] -= count
        for ledger in ledgers:
            if ledger is None or ledger.get(ps, 0) < count:
                raise ValueError("Removed counters do not match March visibility/ownership.")
            ledger[ps] -= count


def window(state, faction, region, group, stage, **context):
    from fs_bot.engine import action_windows
    if action_windows.SCOPE not in state or action_windows.is_preview(state):
        return []
    owner = state[action_windows.SCOPE].get("actor")
    selected = cohorts(state, faction, region, group, owner)
    return action_windows.window(state, stage, cohorts=selected,
        on_removal=lambda effects: apply_removals(state, faction, group, effects),
        region=region, marching_faction=faction, **context)
