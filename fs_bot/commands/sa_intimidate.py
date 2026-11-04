"""
Intimidate Special Ability — A4.6.2 (Germanic, Ariovistus only).

Intimidation cows enemies into submission.
May accompany March, Raid, or Battle Commands — NOT Rally.

Selection (A4.6.2):
  - Region has Ariovistus, OR
  - Region is under Germanic Control and within one of Ariovistus or
    has Successor.

Procedure per region:
  - Flip one or two Hidden Germanic Warbands to Revealed; shaded A22
    permits one added Reveal to remove one extra piece.
  - Place an Intimidated marker there (if none already).
  - Remove that many Warbands, Auxilia, and/or Allies of one Faction
    that has no Leader there.

INTIMIDATED markers block non-Germanic Recruit and Rally by factions
without a Leader in the region. Removed in Spring (A6.6).

Reference: A4.6.2, A3.2.1, A3.3.1
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, FACTIONS,
    # Piece types
    WARBAND, AUXILIA, ALLY, LEGION,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    ARIOVISTUS_LEADER,
    # Markers
    MARKER_INTIMIDATED,
    # Scenarios
    ARIOVISTUS_SCENARIOS, EVENT_SHADED, EVENT_UNSHADED,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    flip_piece, remove_piece, clear_allied_tribe, tribe_has_ally_disc,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.commands.common import CommandError, check_leader_proximity


def intimidate_limit(state):
    """A4.6.2's two Warbands, plus A22 shaded's optional added Reveal."""
    from fs_bot.cards.capabilities import is_capability_active
    return 3 if is_capability_active(state, 'A22', EVENT_SHADED) else 2


def intimidate_capacity(state, region):
    """Ordinary Intimidate's currently available Hidden participants."""
    return min(intimidate_limit(state), count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN))


def romans_immune(state):
    """Read the actual Capability side, retaining legacy modifier saves."""
    from fs_bot.cards.capabilities import get_active_capabilities
    active = get_active_capabilities(state)
    if 'A22' in active:
        return active['A22'] == EVENT_UNSHADED
    return bool(state.get('event_modifiers', {}).get('card_A22_no_intimidate_romans', False))


def ally_targets(state, region, faction):
    """Actual Allied Tribe discs, excluding a City's Citadel (A4.6.2)."""
    return [tribe for tribe in sorted(state.get('tribes', {}))
            if tribe_has_ally_disc(state, region, tribe, faction)]


def plan_removal(entry):
    """Keep optional authored Tribe identity through the engine adapter."""
    removal = (entry.get('target_piece'), entry.get('target_state'))
    if 'target_tribe' in entry:
        removal += (entry['target_tribe'],)
    return removal


def human_plan_error(action):
    """Human plans must identify Ally discs rather than invoke NPC priority.

    Only structure is checked here: an earlier Command or timing window may
    change which Tribes are legal when the Special Ability actually resolves.
    """
    details = action.get('details') or {}
    if not isinstance(details, dict):
        return 'Command details must be an object'
    nested = details.get('sa_details') or {}
    if not isinstance(nested, dict):
        return 'Special Ability details must be an object'
    # Match execute._sa_detail: an explicit null at the merged level falls
    # back to the nested plan; it must not conceal an unnamed human target.
    plan = details.get('intimidate_plan')
    if plan is None:
        plan = nested.get('intimidate_plan')
    if plan is None:
        return None
    if not isinstance(plan, list) or any(not isinstance(e, dict) for e in plan):
        return 'Intimidate needs a list of target entries'
    for entry in plan:
        if entry.get('target_piece') == ALLY:
            tribe = entry.get('target_tribe')
            if not isinstance(tribe, str) or not tribe:
                return 'Choose target_tribe for each Intimidate Ally removal'
        elif 'target_tribe' in entry:
            return 'target_tribe applies only to an Intimidate Ally removal'
    return None


def _reserve_removals(state, region, faction, removals):
    """Validate the complete physical subset before any flips or marker.

    Legacy pairs retain their default allocation. Named Ally triples reserve
    their discs first so an earlier unspecified Ally cannot consume them.
    """
    if not isinstance(removals, (list, tuple)):
        raise CommandError('Intimidate removals must be a list of physical targets')
    parsed, named = [], set()
    allies = ally_targets(state, region, faction)
    for item in removals:
        if not isinstance(item, (list, tuple)) or len(item) not in (2, 3):
            raise CommandError('Intimidate targets need piece, visibility and optional Ally Tribe')
        pt, ps = item[:2]
        tribe = item[2] if len(item) == 3 else None
        if pt not in (WARBAND, AUXILIA, ALLY):
            raise CommandError('Intimidate removes only Warbands, Auxilia or Allies')
        if ps not in (None, HIDDEN, REVEALED, SCOUTED) or (pt == ALLY and ps is not None):
            raise CommandError('Invalid Intimidate target visibility')
        if len(item) == 3:
            if (pt != ALLY or not isinstance(tribe, str) or tribe not in allies
                    or tribe in named):
                raise CommandError('Select a distinct Allied Tribe disc of the target Faction in this Region')
            named.add(tribe)
        parsed.append((pt, ps, tribe))
    pool = {(pt, ps): count_pieces_by_state(state, region, faction, pt, ps)
            for pt in (WARBAND, AUXILIA) for ps in (HIDDEN, REVEALED, SCOUTED)}
    pool[(ALLY, None)] = count_pieces(state, region, faction, ALLY) if faction is not None else 0
    unselected = [tribe for tribe in allies if tribe not in named]
    reserved = []
    for pt, ps, tribe in parsed:
        choices = (None,) if pt == ALLY else ((ps,) if ps is not None
                                             else (HIDDEN, REVEALED, SCOUTED))
        selected = next((p for p in choices if pool.get((pt, p), 0) > 0), False)
        if selected is False:
            raise CommandError(f'Not enough {faction} {pt} in {region}')
        pool[(pt, selected)] -= 1
        if pt == ALLY and tribe is None:
            if unselected:
                tribe = unselected.pop(0)
            elif named:
                raise CommandError('Unspecified Ally would reuse a reserved Tribe')
            # Old direct helper callers can have count-only fixture discs.
            # With no authored Tribe, keep clear_allied_tribe's legacy path.
        reserved.append((pt, selected, tribe))
    return reserved


def validate_intimidate_region(state, region):
    """Validate that a region can be selected for Intimidate.

    A4.6.2: Region has Ariovistus, OR Region is under Germanic Control
    and within one of Ariovistus or has Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return (False, "Intimidate is only available in Ariovistus")

    # Option 1: Region has Ariovistus
    german_leader = get_leader_in_region(state, region, GERMANS)
    if german_leader == ARIOVISTUS_LEADER:
        return (True, "")

    # Option 2: Germanic Control + within 1 of Ariovistus or Successor
    if not is_controlled_by(state, region, GERMANS):
        return (False,
                "Region must have Ariovistus or be under Germanic Control "
                "for Intimidate")

    valid, reason = check_leader_proximity(
        state, region, GERMANS, ARIOVISTUS_LEADER, "Intimidate"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def intimidate(state, region, warbands_to_flip, target_faction,
               target_removals, *, revealed_by_raid=0):
    """Execute Intimidate in a region.

    A4.6.2: Flip 1-2 Hidden Germanic Warbands to Revealed. A22 shaded
    permits one added Warband/removal. Place an Intimidated marker.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Intimidate occurs.
        warbands_to_flip: Participants (1-2, or up to 3 with shaded A22).
        target_faction: Faction targeted for removal.
        target_removals: Pairs (piece_type, piece_state_or_None), or triples
            (ALLY, None, tribe) for exact discs. Length equals participants.

    Returns:
        dict with:
            "warbands_flipped": Number of Warbands flipped.
            "intimidated_placed": True if marker placed.
            "target_removed": List of (piece_type, 1).

    Raises:
        CommandError: If operation violates rules.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        raise CommandError("Intimidate is only available in Ariovistus")
    if not isinstance(target_removals, (list, tuple)):
        raise CommandError('Intimidate removals must be a list of physical targets')
    if target_faction is not None and target_faction not in FACTIONS:
        raise CommandError('Choose a target Faction for Intimidate removals')

    limit = intimidate_limit(state)
    if type(warbands_to_flip) is not int or not 1 <= warbands_to_flip <= limit:
        raise CommandError(
            f"Must flip {'1 or 2' if limit == 2 else '1 to 3'} Warbands for Intimidate, got "
            f"{warbands_to_flip}"
        )

    # A3.4.3: the SAME Warbands may Raid and Intimidate simultaneously.
    # Only the engine's successful Raid result supplies this credit; an
    # action's caller-controlled ``free`` flag never supplies it.
    if (type(revealed_by_raid) is not int
            or not 0 <= revealed_by_raid <= warbands_to_flip
            or count_pieces_by_state(state, region, GERMANS, WARBAND,
                                     REVEALED) < revealed_by_raid):
        raise CommandError("Invalid Raiding Warband credit for Intimidate")
    fresh_flips = warbands_to_flip - revealed_by_raid
    if revealed_by_raid and fresh_flips > int(limit == 3):
        raise CommandError('Raid Intimidate permits only A22\'s one added Hidden Warband')
    # Check Hidden Warbands available
    hidden_wb = count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN
    )
    if hidden_wb < fresh_flips:
        raise CommandError(
            f"Only {hidden_wb} Hidden Germanic Warbands in {region}, "
            f"need {fresh_flips}"
        )

    # Validate target: must have no Leader in region — A4.6.2
    if target_faction == ROMANS and romans_immune(state):
        raise CommandError(
            "A22: Intimidate has no effect on Romans")
    if target_faction == GERMANS:
        raise CommandError("Cannot Intimidate own faction")

    target_leader = (get_leader_in_region(state, region, target_faction)
                     if target_faction is not None else None)
    if target_leader is not None:
        raise CommandError(
            f"{target_faction} has a Leader in {region} — cannot Intimidate"
        )

    # Validate removals match flip count
    marker_only = target_faction is None and not target_removals
    if not marker_only and target_faction not in FACTIONS:
        raise CommandError('Choose a target Faction for Intimidate removals')
    if marker_only and (warbands_to_flip > 2 or (revealed_by_raid and fresh_flips)):
        raise CommandError('A22 added Warband must remove an extra piece')
    if not marker_only and len(target_removals) != warbands_to_flip:
        raise CommandError(
            f"Must remove exactly {warbands_to_flip} pieces, "
            f"got {len(target_removals)}"
        )

    removals = _reserve_removals(state, region, target_faction, target_removals)

    result = {
        "warbands_flipped": fresh_flips,
        "raiding_warbands_used": revealed_by_raid,
        "intimidated_placed": False,
        "target_removed": [],
        "target_details": [],
    }

    # Flip Germanic Warbands
    if fresh_flips:
        flip_piece(state, region, GERMANS, WARBAND,
                   count=fresh_flips,
                   from_state=HIDDEN, to_state=REVEALED)

    # Place Intimidated marker
    markers = state.setdefault("markers", {})
    region_markers = markers.get(region)
    if MARKER_INTIMIDATED not in (region_markers or {}):
        if isinstance(region_markers, set):
            region_markers.add(MARKER_INTIMIDATED)
        elif isinstance(region_markers, dict):
            region_markers[MARKER_INTIMIDATED] = True
        else:
            markers[region] = {MARKER_INTIMIDATED: True}
        result["intimidated_placed"] = True

    # Remove target pieces
    for piece_type, piece_state, tribe in removals:
        if piece_type == ALLY:
            remove_piece(state, region, target_faction, ALLY, 1)
            # Keep state["tribes"] in sync with the removed Ally.
            clear_allied_tribe(state, region, target_faction, ALLY, tribe=tribe)
        else:
            remove_piece(state, region, target_faction, piece_type, 1,
                         piece_state=piece_state)
        result["target_removed"].append((piece_type, 1))
        result['target_details'].append({'piece_type': piece_type,
            'piece_state': piece_state, 'tribe': tribe})

    refresh_all_control(state)
    return result


