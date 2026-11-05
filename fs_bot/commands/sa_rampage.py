"""
Rampage Special Ability — §4.5.2 (Belgae).

Rampaging demonstrates Belgic ferocity to frighten enemy Forces out of
Regions and compel surrender.
May accompany Rally, Raid, or Battle.

Selection (§4.5.2):
  - Region must have Hidden Belgic Warbands.
  - Region must be within one of Ambiorix or have Successor.

Procedure per region:
  1. Select one target Roman or Gallic Faction (not Germanic) that has
     neither a Leader, nor a Citadel, nor a Fort in the Region.
  2. Target Faction must remove or Retreat one piece (Warband, Auxilia,
     or Legion — no roll) per Hidden Belgic Warband that the Belgae
     flip to Revealed.
  3. Retreat per Battle procedure — into one adjacent Region where the
     targeted Faction or an agreeing Faction has Control.

Ariovistus note (A4.5 NOTE): Rampage may not Target Germans. When
targeting Arverni in Ariovistus, they are removed rather than Retreating
(since Arverni never Retreat in Ariovistus — A3.2.4).

Reference: §4.5.2, §3.2.4, §3.3.4, A4.5
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, CITADEL,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    AMBIORIX, BODUOGNATUS,
    SA_RAMPAGE,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    flip_piece, remove_piece, move_piece,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import is_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def rampage_capacity(state, region, target_faction):
    """§4.5.2: one affected mobile piece per selected Hidden Warband."""
    return min(count_pieces_by_state(state, region, BELGAE, WARBAND, HIDDEN),
               sum(count_pieces(state, region, target_faction, piece)
                   for piece in (WARBAND, AUXILIA, LEGION)))


def human_plan_error(action):
    """Human target entries choose quantity; omission is only an NPC default.

    Dynamic availability is checked when Rampage resolves, after the Command
    and any authorized timing actions, rather than on the starting board.
    """
    if action.get('sa') != SA_RAMPAGE:
        return None
    entries = action.get('sa_regions')
    if not isinstance(entries, list) or not entries or any(not isinstance(e, dict) for e in entries):
        return 'Rampage needs Region/target entries with an explicit count'
    regions = []
    for entry in entries:
        if not isinstance(entry.get('region'), str) or entry.get('target') not in (ROMANS, ARVERNI, AEDUI):
            return 'Each Rampage entry needs a Region and Roman or Gallic target'
        regions.append(entry['region'])
        if type(entry.get('count')) is not int or entry['count'] < 1:
            return 'Choose a positive integer count for each Rampage Region'
    if len(regions) != len(set(regions)):
        return 'Select each Rampage Region only once (§4.1)'
    return None


def validate_rampage_region(state, region):
    """Validate that a region can be selected for Rampage.

    §4.5.2: Must have Hidden Belgic Warbands and be within one of
    Ambiorix or have Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    # Must have Hidden Belgic Warbands
    hidden_wb = count_pieces_by_state(
        state, region, BELGAE, WARBAND, HIDDEN
    )
    if hidden_wb < 1:
        return (False,
                "Region must have Hidden Belgic Warbands for Rampage")

    # Leader proximity
    leader_name = AMBIORIX
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_name = BODUOGNATUS

    valid, reason = check_leader_proximity(
        state, region, BELGAE, leader_name, "Rampage"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def validate_rampage_target(state, region, target_faction):
    """Validate that a faction can be targeted by Rampage.

    §4.5.2: Target must be Roman or Gallic (not Germanic), and must not
    have a Leader, Citadel, or Fort in the Region.

    A4.5 NOTE: Rampage may not Target Germans.

    Args:
        state: Game state dict.
        region: Rampage region.
        target_faction: Faction to target.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Cannot target self
    if target_faction == BELGAE:
        return (False, "Cannot Rampage own faction")

    # Cannot target Germans — §4.5.2, A4.5 NOTE
    if target_faction == GERMANS:
        return (False, "Rampage cannot target Germans")

    # Must be Roman or Gallic
    if target_faction not in (ROMANS, ARVERNI, AEDUI):
        return (False, f"Rampage can only target Roman or Gallic factions")

    # Target must not have Leader, Citadel, or Fort in region
    space = state["spaces"][region]
    t_pieces = space.get("pieces", {}).get(target_faction, {})

    if get_leader_in_region(state, region, target_faction) is not None:
        return (False,
                f"{target_faction} has a Leader in {region} — cannot Rampage")

    if t_pieces.get(CITADEL, 0) > 0:
        return (False,
                f"{target_faction} has a Citadel in {region} — cannot Rampage")

    if t_pieces.get(FORT, 0) > 0:
        return (False,
                f"{target_faction} has a Fort in {region} — cannot Rampage")

    return (True, "")


def rampage(state, region, target_faction, warbands_to_flip,
            target_actions, *, retreat_regions=None):
    """Apply one complete Rampage transaction, including any agreed Retreat."""
    from fs_bot.engine.spring import atomic
    with atomic(state):
        return _rampage(state, region, target_faction, warbands_to_flip,
                        target_actions, retreat_regions=retreat_regions)


def _rampage(state, region, target_faction, warbands_to_flip,
             target_actions, *, retreat_regions=None):
    """Execute Rampage in a region.

    §4.5.2: Belgae flip Hidden Warbands to Revealed. For each flipped
    Warband, the target must remove or Retreat one piece.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Rampage occurs.
        target_faction: Faction being Rampaged.
        warbands_to_flip: Number of Hidden Belgic Warbands to flip.
        target_actions: List of dicts, one per flipped Warband:
            "action": "remove" or "retreat"
            "piece_type": WARBAND, AUXILIA, or LEGION
            "piece_state": For flippable, the state.
            "retreat_region": For retreat, the destination.

    Returns:
        dict with:
            "warbands_flipped": Number of Belgic Warbands flipped.
            "target_removed": List of (piece_type, count).
            "target_retreated": List of (piece_type, retreat_region).

    Raises:
        CommandError: If operation violates rules.
    """
    scenario = state["scenario"]

    from collections import Counter
    from fs_bot.engine.rampage_choices import victim_pieces, validate_response
    if type(warbands_to_flip) is not int or warbands_to_flip < 0:
        raise CommandError('Rampage requires a nonnegative integer Warband count')
    if not isinstance(target_actions, list) or len(target_actions) != warbands_to_flip:
        raise CommandError(f'Need exactly {warbands_to_flip} target actions')
    if warbands_to_flip == 0:
        return {'warbands_flipped': 0, 'target_removed': [], 'target_retreated': []}
    valid, reason = validate_rampage_region(state, region)
    if valid:
        valid, reason = validate_rampage_target(state, region, target_faction)
    if not valid:
        raise CommandError(reason)
    if warbands_to_flip > count_pieces_by_state(state, region, BELGAE, WARBAND, HIDDEN):
        raise CommandError('Rampage count exceeds Hidden Belgic Warbands')
    pool = victim_pieces(state, region, target_faction)
    available = Counter(pool)
    normalized, destinations = [], set()
    for entry in target_actions:
        if (not isinstance(entry, dict)
                or set(entry) - {'action', 'piece_type', 'piece_state', 'retreat_region'}
                or entry.get('piece_type') not in (WARBAND, AUXILIA, LEGION)
                or entry.get('piece_state') not in (None, HIDDEN, REVEALED, SCOUTED)):
            raise CommandError('Rampage needs physical mobile pieces and valid dispositions')
        piece, visibility = entry['piece_type'], entry.get('piece_state')
        if piece in FLIPPABLE_PIECES and visibility is None:
            visibility = next((ps for ps in (HIDDEN, REVEALED, SCOUTED)
                               if available[piece, ps] > 0), None)
        if available[piece, visibility] <= 0:
            raise CommandError('Rampage selects an unavailable physical piece')
        available[piece, visibility] -= 1
        action = entry.get('action')
        if action == 'retreat':
            if target_faction == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
                raise CommandError('Arverni cannot Retreat in Ariovistus — must remove')
            destination = entry.get('retreat_region')
            if not isinstance(destination, str):
                raise CommandError('Must specify retreat_region for Rampage retreat')
            destinations.add(destination)
        elif entry.get('retreat_region') is not None:
            raise CommandError('A removed Rampage victim cannot name a Retreat destination')
        normalized.append({'action': action, 'piece_type': piece, 'piece_state': visibility})
    if len(destinations) > 1:
        raise CommandError('Rampage victims must share one Retreat destination')
    destination = next(iter(destinations), None)
    if destination is not None and retreat_regions is None:
        from fs_bot.engine.execute import _retreat_destinations
        retreat_regions = _retreat_destinations(state, region, target_faction, rampage=True)
    request = {'region': region, 'defender': target_faction, 'pieces': pool,
               'context': {'num_pieces': warbands_to_flip}, 'legal_regions': retreat_regions or []}
    try:
        validate_response(state, request, {'actions': normalized, 'retreat_region': destination})
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    target_actions = [dict(entry, **({'retreat_region': destination} if entry['action'] == 'retreat' else {}))
                      for entry in normalized]

    result = {
        "warbands_flipped": warbands_to_flip,
        "target_removed": [],
        "target_retreated": [],
    }

    # Flip Belgic Warbands from Hidden to Revealed
    flip_piece(state, region, BELGAE, WARBAND,
               count=warbands_to_flip,
               from_state=HIDDEN, to_state=REVEALED)

    # Process target actions
    for action_info in target_actions:
        action = action_info["action"]
        piece_type = action_info["piece_type"]
        piece_state = action_info.get("piece_state")

        if action == "remove":
            # A4.5 NOTE: "When Rampage Targets Arverni, they are removed
            # rather than Retreating" in Ariovistus.
            if piece_type == LEGION:
                remove_piece(state, region, target_faction, LEGION, 1,
                             to_fallen=True)
            else:
                remove_piece(state, region, target_faction, piece_type, 1,
                             piece_state=piece_state)
            result["target_removed"].append((piece_type, 1))

        elif action == "retreat":
            retreat_region = action_info['retreat_region']

            # Move the piece
            if piece_type == LEGION:
                move_piece(state, region, retreat_region,
                           target_faction, LEGION)
            else:
                move_piece(state, region, retreat_region,
                           target_faction, piece_type,
                           piece_state=piece_state)
            result["target_retreated"].append(
                (piece_type, retreat_region)
            )

        else:
            raise CommandError(f"Unknown Rampage action: {action}")

    refresh_all_control(state)
    return result


