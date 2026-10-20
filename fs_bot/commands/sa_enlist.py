"""
Enlist Special Ability — §4.5.1 (Belgae).

Enlist invites help from Germanic kinsmen.
May accompany any Command.

Selection (§4.5.1):
  - Regions in or adjacent to Germania, or further Regions with Germanic
    pieces.
  - Regions must be within one of Ambiorix or have Successor.

Two options:
1. Treat Germanic Warbands as Belgic Warbands for the accompanying Command.
   This includes Rally, March, Raid, Battle, and Control. Germanic Warbands
   cannot be voluntarily removed. Once the Command is done, they revert to
   Germanic.

2. Execute one free Limited Command with Germanic pieces (per §3.4). The
   Region need not be one selected for the Belgic Command but must be in
   leader proximity. Battling Germans must be able to Ambush (§3.4.4).

Ariovistus restrictions (A4.5.1):
  - Max 4 Germanic Warbands + Allies total.
  - May not affect Leader or Settlements.
  - May not select a Region containing Ariovistus.
  - Free Battle: no Ambush added, ignores other Germanic pieces.
  - Free Raid: provides Resources to Germans.

Reference: §4.5.1, A4.5.1
"""

from fs_bot.rules_consts import (
    # Factions
    BELGAE, GERMANS,
    # Piece types
    WARBAND, ALLY, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    AMBIORIX, BODUOGNATUS, ARIOVISTUS_LEADER,
    # Regions
    SUGAMBRI, UBII,
    GERMANIA_REGIONS,
    # Costs
    ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
)
from fs_bot.map.map_data import is_adjacent, get_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity

BORROW_KEY = "_enlist_borrowed"
FREE_FORCE_KEY = "_enlist_free_force"


def scoped_free_force(state, region, counts):
    """A4.5.1 free Battle sees only the selected German Warbands.

    This is a battle-force filter, never a change of physical Control.
    The context manager restores the ordinary view even on interruption.
    """
    from contextlib import contextmanager

    @contextmanager
    def scope():
        from fs_bot.board.pieces import PieceError
        if FREE_FORCE_KEY in state:
            raise CommandError("A free Enlist force is already selected")
        raw = state["spaces"][region].get("pieces", {}).get(GERMANS, {})
        if (not isinstance(counts, dict)
                or set(counts) - {HIDDEN, REVEALED, SCOUTED}
                or any(type(n) is not int or n < 0 for n in counts.values())
                or any(n > raw.get(ps, {}).get(WARBAND, 0)
                       for ps, n in counts.items())):
            raise PieceError("Invalid selected Enlist Warbands")
        valid, reason = validate_enlist_ariovistus_limit(state, sum(counts.values()))
        if not valid:
            raise CommandError(reason)
        state[FREE_FORCE_KEY] = {"region": region, "pieces": {region: dict(counts)}}
        try:
            yield
        finally:
            state.pop(FREE_FORCE_KEY, None)
    return scope()


def enlist_details(action):
    details = action.get("details") or {}
    return details.get("enlist") or (details.get("sa_details") or {}).get("enlist") or {}


def is_borrow_plan(action):
    """The first Enlist option modifies its Command, rather than adding one."""
    return (action.get("sa") == "Enlist" and
            enlist_details(action).get("type")
            in ("borrow", "in_battle"))


def begin_borrow(state, action):
    """Select physical German Warbands for §4.5.1 without changing ownership.

    The effective-piece view treats only these counters as Belgic. Its ledger
    follows each selected counter through flips, losses and movement. New
    German Warbands placed by Rally consume the same A4.5.1 four-piece budget.
    Validate the complete selection before installing any temporary state.
    """
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.board.control import refresh_all_control
    if BORROW_KEY in state:
        raise CommandError("An Enlist borrowing scope is already active")
    ed = enlist_details(action)
    regions = ed.get("regions") or action.get("sa_regions") or [ed.get("region")]
    if not regions or len(set(regions)) != len(regions):
        raise CommandError("Enlist needs distinct affected Regions")
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    pieces, total = {}, 0
    selected = ed.get("warbands")
    for region in regions:
        if region not in playable:
            raise CommandError("Enlist Region is not playable")
        valid, reason = validate_enlist_region(state, region)
        if not valid:
            raise CommandError(reason)
        raw = state["spaces"][region].get("pieces", {}).get(GERMANS, {})
        counts = {}
        if selected is not None:
            if not isinstance(selected, dict) or region not in selected:
                raise CommandError("Specify borrowed Warbands for each Enlist Region")
            counts = selected[region]
            if not isinstance(counts, dict) or set(counts) - {HIDDEN, REVEALED, SCOUTED}:
                raise CommandError("Borrow Warbands by Hidden, Revealed or Scouted state")
        else:
            counts = {ps: raw.get(ps, {}).get(WARBAND, 0)
                      for ps in (HIDDEN, REVEALED, SCOUTED)}
        pieces[region] = {}
        for ps in (HIDDEN, REVEALED, SCOUTED):
            n = counts.get(ps, 0)
            if type(n) is not int or n < 0 or n > raw.get(ps, {}).get(WARBAND, 0):
                raise CommandError("Borrowed Warband count exceeds the physical pieces")
            if state["scenario"] in BASE_SCENARIOS and n != raw.get(ps, {}).get(WARBAND, 0):
                raise CommandError("Base Enlist treats all German Warbands in each selected Region as Belgic")
            pieces[region][ps] = n
            total += n
    valid, reason = validate_enlist_ariovistus_limit(state, total)
    if not valid:
        raise CommandError(reason)
    state[BORROW_KEY] = {"regions": list(regions), "pieces": pieces,
                         "affected": total}
    refresh_all_control(state)


def end_borrow(state):
    """§4.5.1: immediately restore German treatment and Control."""
    from fs_bot.board.control import refresh_all_control
    state.pop(BORROW_KEY, None)
    refresh_all_control(state)


def borrowed_count(state, region, piece_state=None):
    counts = state.get(BORROW_KEY, {}).get("pieces", {}).get(region, {})
    return (sum(counts.values()) if piece_state is None
            else counts.get(piece_state, 0))


def borrowed_loss_choices(state, region, faction, choices):
    """Expose physical ownership where equal-looking Warbands are borrowed."""
    if faction != BELGAE or not borrowed_count(state, region):
        return choices
    out = [p for p in choices if p[0] != WARBAND]
    warbands = []
    for owner in (GERMANS, BELGAE):  # §8.5.1 NP: Germans absorb first.
        raw = state["spaces"][region].get("pieces", {}).get(owner, {})
        for ps in (SCOUTED, REVEALED, HIDDEN):
            n = (borrowed_count(state, region, ps) if owner == GERMANS
                 else raw.get(ps, {}).get(WARBAND, 0))
            warbands.extend([(WARBAND, ps, owner)] * n)
    first = next((i for i, p in enumerate(choices) if p[0] == WARBAND), len(out))
    return out[:first] + warbands + out[first:]


def allocate_borrowed_operation(state, region, faction, count, piece_state,
                                *, owner=None):
    """Physical ownership allocation for a Command's effective Warbands.

    No mutations occur here; an impossible multi-piece request is rejected
    before any counter moves. Explicit owner is used by human loss and March
    choices. Default borrowing-first implements the NP absorption priority.
    """
    from fs_bot.board.pieces import PieceError
    if type(count) is not int or count < 0:
        raise PieceError("Warband count must be a non-negative integer")
    if owner not in (None, BELGAE, GERMANS) or (owner is not None and faction != BELGAE):
        raise PieceError("Invalid physical owner for borrowed Warbands")
    states = (piece_state,) if piece_state is not None else (HIDDEN, REVEALED, SCOUTED)
    allocations, remaining = [], count
    owners = (owner,) if owner else ((GERMANS, BELGAE) if faction == BELGAE else (GERMANS,))
    for physical in owners:
        raw = state["spaces"][region].get("pieces", {}).get(physical, {})
        for ps in states:
            actual = raw.get(ps, {}).get(WARBAND, 0)
            loan = borrowed_count(state, region, ps)
            available = ((loan if physical == GERMANS else actual)
                         if faction == BELGAE else actual - loan)
            take = min(available, remaining)
            if take:
                allocations.append((physical, ps, take))
                remaining -= take
    if remaining:
        raise PieceError("Not enough Warbands of the selected owner/state")
    return allocations


def record_borrowed_change(state, region, piece_state, amount, *,
                            destination=None, new_state=None):
    """Move/flip/remove the loan identity while physical counters stay German."""
    ledger = state[BORROW_KEY]["pieces"]
    ledger[region][piece_state] -= amount
    if destination is not None or new_state is not None:
        counts = ledger.setdefault(destination or region, {})
        ps = new_state or piece_state
        counts[ps] = counts.get(ps, 0) + amount


def enlist_rally_mix(state, region, requested, cap):
    """Validate optional German/Belgic Rally composition before paying costs."""
    from fs_bot.board.pieces import get_available
    if not isinstance(requested, dict) or set(requested) - {BELGAE, GERMANS}:
        raise CommandError("Rally composition must name Belgic/German Warbands")
    mix = {f: requested.get(f, 0) for f in (BELGAE, GERMANS)}
    if any(type(n) is not int or n < 0 for n in mix.values()):
        raise CommandError("Rally Warband counts must be non-negative integers")
    ctx = state.get(BORROW_KEY)
    if not ctx or region not in ctx["regions"]:
        raise CommandError("German placement requires Enlist in the Rally Region")
    if not 0 < sum(mix.values()) <= cap:
        raise CommandError("Rally composition exceeds the Belgic placement limit")
    if any(n > get_available(state, f, WARBAND) for f, n in mix.items()):
        raise CommandError("Not enough physical Warbands Available")
    valid, reason = validate_enlist_ariovistus_limit(state, ctx["affected"] + mix[GERMANS])
    if not valid:
        raise CommandError(reason)
    return mix


def validate_enlist_region(state, region):
    """Validate that a region can be affected by Enlist.

    §4.5.1: Regions in or adjacent to Germania, or further Regions with
    Germanic pieces. Must be within one of Ambiorix or have Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    # Check region eligibility: in/adjacent to Germania or has Germanic pieces
    in_or_adj_germania = (
        region in GERMANIA_REGIONS
        or any(is_adjacent(region, gr) for gr in GERMANIA_REGIONS)
    )
    has_german_pieces = count_pieces(state, region, GERMANS) > 0

    if not in_or_adj_germania and not has_german_pieces:
        return (False,
                f"Region must be in/adjacent to Germania or have Germanic "
                f"pieces for Enlist")

    # Leader proximity
    leader_name = AMBIORIX
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_name = BODUOGNATUS

    valid, reason = check_leader_proximity(
        state, region, BELGAE, leader_name, "Enlist"
    )
    if not valid:
        return (False, reason)

    # Ariovistus: may not select Region containing Ariovistus — A4.5.1
    if scenario in ARIOVISTUS_SCENARIOS:
        ario_leader = get_leader_in_region(state, region, GERMANS)
        if ario_leader == ARIOVISTUS_LEADER:
            return (False,
                    "Enlist may not select a Region containing Ariovistus "
                    "(A4.5.1)")

    return (True, "")


def get_enlistable_german_pieces(state, region):
    """Get count of Germanic Warbands that can be enlisted in a region.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        Integer count of Germanic Warbands in the region.
    """
    total = 0
    for ps in (HIDDEN, REVEALED, SCOUTED):
        total += count_pieces_by_state(
            state, region, GERMANS, WARBAND, ps
        )
    return total


def validate_enlist_ariovistus_limit(state, total_pieces):
    """Validate that Enlist doesn't exceed Ariovistus piece limit.

    A4.5.1: "Each Enlist may affect no more than a total of four Germanic
    Warbands and Allies"

    Args:
        state: Game state dict.
        total_pieces: Total Germanic pieces being enlisted.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return (True, "")  # No limit in base game

    if total_pieces > ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS:
        return (False,
                f"Enlist may affect at most "
                f"{ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS} Germanic pieces "
                f"in Ariovistus, got {total_pieces}")

    return (True, "")


