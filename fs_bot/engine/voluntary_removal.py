"""Player-owned physical counter removal during an authorized action (§1.4.1).

The action-window caller owns Sequence of Play authorization. This module
never infers it from the acting faction of a delegated Command, and never
consults an agent. Options and validation are pure. A response cannot name
another owner or authorize its own timing.

Temporary lending changes what a Command can use, not counter ownership.
Loaned and unloaned counters are separate choices where their removal has
different effects. Callers can similarly supply trusted, disjoint ``cohorts``
for counters carried by a March group. Each cohort identifies a physical
cell by region, piece_type, optional piece_state/loan_kind, and a count; its
id is returned in applied effects so the caller can update its local group.

Responses are ``{"done": True}``, ``{"use_default": True}`` (both no-op),
or ``{"operations": [operation, ...]}``. Each operation contains action,
region, piece_type, and a positive count, plus only the applicable offered
piece_state, tribe, loan_kind, and cohort fields. ``loan_kind`` joins
simultaneous memberships with ``+``; it never changes physical ownership.
"""

from copy import deepcopy
from itertools import combinations

from fs_bot import rules_consts as rc
from fs_bot.board import pieces

KIND = "voluntary_removal"
_VISIBILITIES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
_IDENTITY = ("action", "region", "piece_type", "piece_state", "tribe",
             "loan_kind", "cohort")
_LOANS = ("diviciacus", "enlist", "free_force")
_LOAN_KINDS = tuple("+".join(group) for n in range(1, len(_LOANS) + 1)
                    for group in combinations(_LOANS, n))


def _player(state, faction):
    from fs_bot.engine.game_engine import get_sop_factions
    return (faction in get_sop_factions(state)
            and faction not in state.get("non_player_factions", ()))


def _physical_view(state):
    from fs_bot.battle.combined import COMBINED_KEY
    from fs_bot.battle.excluded_leader import EXCLUDED_LEADER_KEY
    from fs_bot.commands.sa_enlist import BORROW_KEY, FREE_FORCE_KEY
    from fs_bot.engine.diviciacus import KEY
    excluded = {COMBINED_KEY, EXCLUDED_LEADER_KEY, BORROW_KEY, FREE_FORCE_KEY, KEY}
    return {key: value for key, value in state.items() if key not in excluded}


def _loan_cells(state, faction, region, piece_type, visibility):
    """Return exact physical subsets, without imposing a removal priority."""
    from fs_bot.commands.sa_enlist import BORROW_KEY, FREE_FORCE_KEY
    from fs_bot.engine.diviciacus import KEY
    loans = []
    div = state.get(KEY, {})
    if faction == div.get("lender") and piece_type == div.get("physical_type"):
        loans.append(("diviciacus", div.get("pieces", {}).get(region, {})))
    enlisted = state.get(BORROW_KEY, {})
    if faction == rc.GERMANS and piece_type == rc.WARBAND:
        loans.append(("enlist", enlisted.get("pieces", {}).get(region, {})))
    free = state.get(FREE_FORCE_KEY, {})
    if (free and faction == free.get("faction", rc.GERMANS)
            and piece_type == rc.WARBAND):
        loans.append(("free_force", free.get("pieces", {}).get(region, {})))
    return [(kind, counts.get(visibility, 0)) for kind, counts in loans
            if counts.get(visibility, 0)]


def _loan_partitions(loans, amount):
    """Separate exact memberships, including a selection inside a full loan.

    Impetuosity's selected Aedui group can also be lent to a Roman defense
    by Diviciacus. That latter loan includes every physical Aedui Warband,
    so the selected group's intersection is known, not a guessed priority.
    Two independently partial ledgers do not identify their intersection;
    fail rather than silently assigning physical counters to either one.
    """
    if any(type(n) is not int or n < 0 or n > amount for _, n in loans):
        raise ValueError("Removal loan ledger exceeds its physical counters.")
    full = [kind for kind, n in loans if n == amount]
    partial = [(kind, n) for kind, n in loans if n < amount]
    if len(partial) > 1:
        raise ValueError("Overlapping partial removal loans need exact physical membership.")
    def membership(kinds):
        return "+".join(kind for kind in _LOANS if kind in kinds) or None
    if not partial:
        return [(membership(full), amount)]
    kind, count = partial[0]
    return [(membership([*full, kind]), count), (membership(full), amount - count)]


def _cell(choice):
    return tuple(choice.get(key) for key in
                 ("region", "piece_type", "piece_state", "loan_kind"))


def _checked_cohorts(cohorts):
    result, seen = [], set()
    for cohort in cohorts or ():
        required = {"id", "region", "piece_type", "count"}
        allowed = required | {"label", "piece_state", "loan_kind"}
        if (not isinstance(cohort, dict) or not required <= set(cohort)
                or set(cohort) - allowed
                or not isinstance(cohort["id"], str) or not cohort["id"]
                or type(cohort["count"]) is not int or cohort["count"] < 0
                or cohort.get("loan_kind") not in (None, *_LOAN_KINDS)
                or cohort.get("piece_state") not in (None, *_VISIBILITIES)):
            raise ValueError("Invalid engine-owned removal cohort.")
        key = (_cell(cohort), cohort["id"])
        if key in seen:
            raise ValueError("Removal cohorts must be distinct physical subsets.")
        seen.add(key)
        result.append(deepcopy(cohort))
    return result


def _partition(choice, count, cohorts):
    selected = [c for c in cohorts if _cell(c) == _cell(choice)]
    total = sum(c["count"] for c in selected)
    if total > count:
        raise ValueError("Removal cohort exceeds its physical counters.")
    result = []
    for cohort in selected:
        if cohort["count"]:
            result.append(dict(choice, cohort=cohort["id"],
                cohort_label=cohort.get("label", cohort["id"]),
                max_count=cohort["count"]))
    if count > total:
        result.append(dict(choice, max_count=count - total))
    return result


def options(state, faction, *, cohorts=None):
    """List physical own counters; does not grant a legal action window."""
    if not _player(state, faction):
        return []
    cohorts = _checked_cohorts(cohorts)
    physical = _physical_view(state)
    result, cells = [], set()
    for region in sorted(state["spaces"]):
        for piece_type in rc.PIECE_TYPES:
            count = pieces.count_pieces(physical, region, faction, piece_type)
            if not count:
                continue
            choice = {"action": "remove", "region": region,
                      "piece_type": piece_type}
            if piece_type in rc.FLIPPABLE_PIECES:
                for visibility in _VISIBILITIES:
                    amount = pieces.count_pieces_by_state(
                        physical, region, faction, piece_type, visibility)
                    loans = _loan_cells(state, faction, region, piece_type, visibility)
                    partitions = _loan_partitions(loans, amount)
                    for kind, n in partitions:
                        cell = dict(choice, piece_state=visibility)
                        if kind is not None:
                            cell["loan_kind"] = kind
                        cells.add(_cell(cell))
                        result.extend(_partition(cell, n, cohorts))
            elif piece_type in (rc.ALLY, rc.CITADEL):
                for tribe, info in sorted(state.get("tribes", {}).items()):
                    if ((info.get("region") or rc.TRIBE_TO_REGION.get(tribe)) != region
                            or info.get("allied_faction") != faction):
                        continue
                    is_disc = pieces.tribe_has_ally_disc(physical, region, tribe, faction)
                    if ((piece_type == rc.ALLY and is_disc)
                            or (piece_type == rc.CITADEL and not is_disc
                                and tribe in rc.TRIBE_TO_CITY)):
                        item = dict(choice, tribe=tribe, max_count=1)
                        result.append(item)
                        if piece_type == rc.CITADEL:
                            result.append(dict(item, action="downgrade",
                                replacement_available=pieces.get_available(
                                    state, faction, rc.ALLY) > 0))
            else:
                if piece_type == rc.FORT and region == rc.PROVINCIA:
                    count -= 1  # The permanent Fort is never a selectable piece.
                if piece_type == rc.LEADER:
                    choice["leader"] = pieces.get_leader_in_region(physical, region, faction)
                cells.add(_cell(choice))
                result.extend(_partition(choice, count, cohorts))
    if any(c["count"] and _cell(c) not in cells for c in cohorts):
        raise ValueError("Removal cohort has no physical counters.")
    return result


def make_request(state, faction, *, window=None, cohorts=None):
    """Build a request only after the caller authorizes the outer SoP actor."""
    choices = options(state, faction, cohorts=cohorts)
    if not choices:
        return None
    request = {"kind": KIND, "faction": faction, "options": choices}
    if window is not None:
        request["window"] = deepcopy(window)
    if cohorts:
        request["cohorts"] = _checked_cohorts(cohorts)
    return request


def operation(choice, count=1):
    """Return the response fields for a displayed option."""
    return {**{key: choice[key] for key in _IDENTITY if key in choice},
            "count": count}


def advance_cohorts(cohorts, effects):
    """Update a detached cohort description after exactly selected removals."""
    result = _checked_cohorts(cohorts)
    for effect in effects:
        if "cohort" not in effect:
            continue
        matches = [c for c in result if c["id"] == effect["cohort"]
                   and _cell(c) == _cell(effect)]
        if len(matches) != 1 or matches[0]["count"] < effect["count"]:
            raise ValueError("Removed counter does not match its action cohort.")
        matches[0]["count"] -= effect["count"]
    return result


def _apply_operation(state, faction, selected):
    region, piece_type = selected["region"], selected["piece_type"]
    count = selected["count"]
    replace = (selected["action"] == "downgrade"
               and pieces.get_available(state, faction, rc.ALLY) > 0)
    # Deliberately use the physical helper: the effective Command view may
    # route a normal remove_piece call to a different faction's counters.
    pieces._remove_piece_inner(state, region, faction, piece_type, count,
        piece_state=selected.get("piece_state"), to_track=piece_type == rc.LEGION)
    loan_kind = selected.get("loan_kind")
    if loan_kind:
        from fs_bot.commands.sa_enlist import BORROW_KEY, FREE_FORCE_KEY
        from fs_bot.engine.diviciacus import KEY
        for kind in loan_kind.split("+"):
            context = state[{"diviciacus": KEY, "enlist": BORROW_KEY,
                             "free_force": FREE_FORCE_KEY}[kind]]
            context["pieces"][region][selected["piece_state"]] -= count
    if replace:
        pieces.place_piece(state, region, faction, rc.ALLY)
    elif piece_type in (rc.ALLY, rc.CITADEL):
        pieces.clear_allied_tribe(state, region, faction, piece_type,
                                 tribe=selected["tribe"])
    pieces._refresh_region_control(state, region)
    effect = dict(selected, faction=faction)
    if selected["action"] == "downgrade":
        effect["replacement_placed"] = replace
    return effect


def _run(state, request, response, cohorts):
    if (not isinstance(request, dict) or request.get("kind") != KIND
            or not _player(state, request.get("faction"))):
        raise ValueError("Voluntary removal requires an authorized player request.")
    if not isinstance(response, dict):
        raise ValueError("Choose removals or finish voluntary removal.")
    if ((set(response) == {"done"} and response["done"] is True)
            or (set(response) == {"use_default"} and response["use_default"] is True)):
        return []
    if (set(response) != {"operations"} or not isinstance(response["operations"], list)
            or not response["operations"]):
        raise ValueError("Voluntary removal requires an ordered list of operations.")
    effects = []
    for selected in response["operations"]:
        if (not isinstance(selected, dict)
                or type(selected.get("count")) is not int or selected["count"] < 1
                or set(selected) - {*_IDENTITY, "count"}):
            raise ValueError("Invalid voluntary removal operation.")
        choices = options(state, request["faction"], cohorts=cohorts)
        matches = [c for c in choices if operation(c, selected["count"]) == selected
                   and selected["count"] <= c["max_count"]]
        if len(matches) != 1:
            raise ValueError("Choose only the offered own physical counters.")
        effect = _apply_operation(state, request["faction"], selected)
        effects.append(effect)
        cohorts = advance_cohorts(cohorts, [effect])
    return effects


def validate_response(state, request, response, *, cohorts=None):
    """Dry-run the complete ordered batch, preserving the live board and RNG."""
    trial = deepcopy({key: value for key, value in state.items()
                      if key != "decision_agent"})
    _run(trial, request, response, _checked_cohorts(cohorts))
    return response


def apply_response(state, request, response, *, cohorts=None):
    """Apply one validated batch atomically; return exact physical effects.

    Cohorts are trusted caller arguments, never taken from the response or
    request. The caller updates its local group using the returned effects.
    Default delegation explicitly does nothing: bots do not reclaim pieces.
    """
    validate_response(state, request, response, cohorts=cohorts)
    from fs_bot.engine.spring import atomic
    with atomic(state):
        return _run(state, request, response, _checked_cohorts(cohorts))
