"""
Suborn Special Ability — §4.4.2 (Aedui).

Suborning buys allegiance to the Aedui or others.
May accompany Rally, March, or Raid.

Selection (§4.4.2):
  - Any one Region with a Hidden Aedui Warband.
  - No Leader requirement in base game.
  - Ariovistus with Diviciacus: within 1 of Diviciacus — A4.4, A4.1.2.

Procedure:
  - Pay 2 Aedui Resources per Ally and 1 per Warband or Auxilia.
  - Remove and/or place a total of up to 3 pieces in the Region.
  - At most 1 of the 3 may be an Allied Tribe (no Citadels).
  - Any Faction's pieces may be involved.
  - Place Allies only at Subdued Tribes (faction-restricted tribes apply).

Convictolitavis (§5.3, Card 43): up to 2 Regions, each with its own limits.
Vergobret (A38): one additional piece per Region, which may be an Ally.

Reference: §4.4.2, §1.4.2, A4.4
"""

from contextlib import contextmanager
from copy import deepcopy

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    WARBAND, AUXILIA, ALLY,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    DIVICIACUS,
    # Costs
    SUBORN_COST_PER_ALLY, SUBORN_COST_PER_PIECE,
    SUBORN_MAX_PIECES, SUBORN_MAX_ALLIES,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
    TRIBE_TO_REGION,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region, find_leader,
    place_piece, remove_piece, get_available,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import (
    is_adjacent, get_tribes_in_region,
)
from fs_bot.commands.common import action_cost, CommandError


def validate_suborn_region(state, region):
    """Validate that a region can be selected for Suborn.

    §4.4.2: Must have a Hidden Aedui Warband. One region only (not checked
    here — caller enforces count).

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    from fs_bot.map.map_data import get_playable_regions_for_state
    if region not in get_playable_regions_for_state(state):
        return False, "Suborn must select a playable Region"
    # Must have Hidden Aedui Warband
    hidden_wb = count_pieces_by_state(
        state, region, AEDUI, WARBAND, HIDDEN
    )
    if hidden_wb < 1:
        return (False,
                "Region must have a Hidden Aedui Warband for Suborn")

    # Ariovistus Diviciacus proximity — A4.4, A4.1.2
    # Keyed on the PIECE, not the scenario (A4.1.2 / card O38).
    leader_region = find_leader(state, AEDUI)
    if leader_region is not None:
        # Must be within 1 of Diviciacus
        if region != leader_region and not is_adjacent(region, leader_region):
            return (False,
                    "Region must be within 1 of Diviciacus for Suborn")

    # Card A38 (Vergobret) shaded CAPABILITY: "Suborn only at Diviciacus.
    # If no Diviciacus, Suborn and Trade only within 1 Region of Bibracte."
    # Source: A Card Reference, card A38. Reachable in the Gallic War
    # second half (A2.1 Deck substitutes A38 for base 38).
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_SHADED, AEDUI_REGION
    if is_capability_active(state, "A38", EVENT_SHADED):
        if leader_region is not None:
            if region != leader_region:
                return (False,
                        "Card A38 shaded: Suborn only at Diviciacus")
        else:
            if (region != AEDUI_REGION
                    and not is_adjacent(region, AEDUI_REGION)):
                return (False,
                        "Card A38 shaded: no Diviciacus — Suborn only "
                        "within 1 Region of Bibracte")

    return (True, "")


def suborn_limits(state):
    """Printed per-Region piece/Ally limits, including Vergobret's extra Ally."""
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_UNSHADED
    enhanced = is_capability_active(state, "A38", EVENT_UNSHADED)
    return (SUBORN_MAX_PIECES + bool(enhanced),
            SUBORN_MAX_ALLIES + bool(enhanced))


def suborn_region_limit(state):
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import EVENT_UNSHADED
    return 2 if is_capability_active(state, 43, EVENT_UNSHADED) else 1


def suborn_tribes(state, region):
    """Printed Tribes plus Card 71's additional Colony Tribe in this Region."""
    tribes = list(get_tribes_in_region(region, state['scenario']))
    tribes.extend(tribe for tribe, info in state.get('tribes', {}).items()
                  if tribe not in TRIBE_TO_REGION and info.get('region') == region)
    return tribes


def suborn_operation_cost(state, operation):
    if operation["piece_type"] == ALLY:
        cost = SUBORN_COST_PER_ALLY
    elif (suborn_limits(state)[0] > SUBORN_MAX_PIECES
          and operation.get("action") == "place"
          and operation["piece_type"] == AUXILIA):
        cost = 0
    else:
        cost = SUBORN_COST_PER_PIECE
    return action_cost(state, AEDUI, cost)


@contextmanager
def _operation_view(state, region, operation):
    """Explicit physical counters never change colour under cooperation.

    Legacy effective-type plans may still use Diviciacus conversion. New
    native-owner operations name physical_owner explicitly; update any active
    loan ledger after their physical mutation so subsequent operations see it.
    """
    owner = operation.get("physical_owner")
    if owner is None:
        yield
        return
    if owner != operation.get("faction"):
        raise CommandError("Suborn physical_owner must match the named Faction")
    from fs_bot.engine.diviciacus import KEY, STATES
    context = state.pop(KEY, None)
    try:
        yield
    finally:
        if context is not None:
            if owner == context['lender'] and region in context['pieces']:
                raw = state['spaces'][region].get('pieces', {}).get(owner, {})
                context['pieces'][region] = {
                    ps: raw.get(ps, {}).get(context['physical_type'], 0)
                    for ps in STATES}
            state[KEY] = context


def _apply_suborn_operation(state, region, operation):
    action, faction, piece_type = (operation[key] for key in
                                    ("action", "faction", "piece_type"))
    if action == "remove":
        remove_piece(state, region, faction, piece_type, 1,
                     piece_state=operation.get("piece_state"))
        if piece_type == ALLY:
            tribe = operation.get("tribe")
            if tribe:
                state["tribes"][tribe]["allied_faction"] = None
                from fs_bot.rules_consts import ALLIED
                if state["tribes"][tribe].get("status") == ALLIED:
                    state["tribes"][tribe]["status"] = None
            else:
                from fs_bot.board.pieces import clear_allied_tribe
                clear_allied_tribe(state, region, faction, ALLY)
    elif piece_type == ALLY:
        place_piece(state, region, faction, ALLY)
        state["tribes"][operation["tribe"]]["allied_faction"] = faction
    else:
        place_piece(state, region, faction, piece_type, piece_state=HIDDEN)


def legal_suborn_operations(state, region):
    """Every currently affordable native-counter operation in one Region."""
    from fs_bot.engine.diviciacus import KEY
    physical = {key: value for key, value in state.items() if key != KEY}
    operations = []
    tribes = suborn_tribes(state, region)
    for faction in FACTIONS:
        for piece_type in (WARBAND, AUXILIA, ALLY):
            placements = ([{"tribe": tribe} for tribe in tribes]
                          if piece_type == ALLY else [{}])
            removals = ([{"tribe": tribe} for tribe, info in state["tribes"].items()
                         if (info.get("region") or TRIBE_TO_REGION.get(tribe)) == region]
                        if piece_type == ALLY else
                        [{"piece_state": ps} for ps in (HIDDEN, REVEALED, SCOUTED)])
            for action, choices in (("place", placements), ("remove", removals)):
                for extra in choices:
                    operation = {"action": action, "faction": faction,
                                 "piece_type": piece_type,
                                 "physical_owner": faction, **extra}
                    try:
                        _validate_suborn_operation(physical, region, operation)
                    except CommandError:
                        continue
                    if suborn_operation_cost(physical, operation) <= physical["resources"].get(AEDUI, 0):
                        operations.append(operation)
    return operations


def _validate_suborn_shape(state, operations):
    if not isinstance(operations, (list, tuple)):
        raise CommandError("Suborn operations must be a list")
    max_pieces, max_allies = suborn_limits(state)
    if len(operations) > max_pieces:
        raise CommandError(f"Suborn allows at most {max_pieces} pieces, got {len(operations)}")
    if any(not isinstance(op, dict) for op in operations):
        raise CommandError("Each Suborn operation must be an object")
    ally_ops = sum(op.get("piece_type") == ALLY for op in operations)
    if ally_ops > max_allies:
        raise CommandError(f"Suborn allows at most {max_allies} Ally operations, got {ally_ops}")


def suborn_preview(state, region, operations):
    """Reserve an ordered sequence on a detached board, including its timing.

    Selection eligibility belongs to the Region's start, not to each piece:
    removing the last Hidden Aedui does not cancel the remaining operations.
    """
    _validate_suborn_shape(state, operations)
    sim = deepcopy({k: v for k, v in state.items() if k != "decision_agent"})
    sim['_diviciacus_preview'] = True
    cost = 0
    for index, operation in enumerate(operations):
        from fs_bot.engine.action_windows import window
        window(sim, 'suborn_operation', author=AEDUI, region=region,
               index=index, timing_actions=operation.get('timing_actions'))
        with _operation_view(sim, region, operation):
            _validate_suborn_operation(sim, region, operation)
            charge = suborn_operation_cost(sim, operation)
            stock = sim["resources"].get(AEDUI, 0)
            if stock < charge:
                raise CommandError(f"Not enough Resources ({stock}) for Suborn (need {charge})")
            sim["resources"][AEDUI] -= charge
            cost += charge
            _apply_suborn_operation(sim, region, operation)
    refresh_all_control(sim)
    return sim, cost


def suborn(state, region, operations):
    """Apply an atomic ordered sequence of up to 3 pieces (4 with A38).

    Each operation names action (place/remove), faction, piece_type and,
    where relevant, tribe or removal piece_state. An explicit physical_owner
    equal to faction requests that native counter even under Diviciacus.
    """
    from fs_bot.engine.action_windows import interactive
    _validate_suborn_shape(state, operations)
    if not interactive(state):
        suborn_preview(state, region, operations)
    result = {"removed": [], "placed": [], "cost": 0}
    before = deepcopy({key: value for key, value in state.items()
                       if key not in ('decision_agent', '_card_turn')})
    agent, card_turn = state.get('decision_agent'), state.get('_card_turn')
    try:
        for index, operation in enumerate(operations):
            from fs_bot.engine.action_windows import window
            window(state, 'suborn_operation', author=AEDUI, region=region,
                   index=index, timing_actions=operation.get('timing_actions'))
            with _operation_view(state, region, operation):
                _validate_suborn_operation(state, region, operation)
                charge = suborn_operation_cost(state, operation)
                stock = state['resources'].get(AEDUI, 0)
                if stock < charge:
                    raise CommandError(f'Not enough Resources ({stock}) for Suborn (need {charge})')
                state['resources'][AEDUI] -= charge
                _apply_suborn_operation(state, region, operation)
                result['cost'] += charge
            result["removed" if operation["action"] == "remove" else "placed"].append(
                (operation["faction"], operation["piece_type"], 1))
        refresh_all_control(state)
    except BaseException:
        # Invalid later operations or a pending owner choice cannot leave a
        # partially paid Suborn. Outer action transactions own frontend replay.
        state.clear()
        state.update(before)
        if agent is not None:
            state['decision_agent'] = agent
        if card_turn is not None:
            state['_card_turn'] = card_turn
        raise
    return result


def _validate_suborn_operation(state, region, op):
    """Validate a single Suborn operation.

    Raises:
        CommandError: If operation is invalid.
    """
    if not isinstance(op, dict) or not all(key in op for key in ("action", "faction", "piece_type")):
        raise CommandError("Suborn operation requires action, faction and piece_type")
    action = op["action"]
    faction = op["faction"]
    piece_type = op["piece_type"]
    if not isinstance(faction, str) or faction not in FACTIONS:
        raise CommandError("Unknown Suborn Faction")
    if not isinstance(region, str) or region not in state["spaces"]:
        raise CommandError("Unknown Suborn Region")
    if op.get("tribe") is not None and not isinstance(op["tribe"], str):
        raise CommandError("Suborn Tribe must be named")
    if op.get("count", 1) != 1 or type(op.get("count", 1)) is not int:
        raise CommandError("Each Suborn operation affects exactly one piece")
    if op.get("piece_state") not in (None, HIDDEN, REVEALED, SCOUTED):
        raise CommandError("Unknown Suborn piece visibility")
    if action == "place" and op.get("piece_state") not in (None, HIDDEN):
        raise CommandError("Suborn places Warbands and Auxilia Hidden")

    # Only Warbands, Auxilia, or Allies — no Citadels
    if piece_type not in (WARBAND, AUXILIA, ALLY):
        raise CommandError(
            f"Suborn can only affect Warbands, Auxilia, or Allies, "
            f"not {piece_type}"
        )

    if action == "remove":
        # Check piece exists in region
        piece_state = op.get("piece_state")
        if piece_type == ALLY:
            space = state["spaces"][region]
            f_pieces = space.get("pieces", {}).get(faction, {})
            if f_pieces.get(ALLY, 0) < 1:
                raise CommandError(
                    f"No {faction} Ally in {region} to remove"
                )
            # The named tribe must BE the target faction's allied tribe
            # here — the executor pairs the piece removal with that
            # tribe's allegiance, so trusting a wrong name (e.g. one of
            # the REMOVER's own tribes) silently desyncs tribes from
            # pieces. Found live in human-seat play.
            tribe = op.get("tribe")
            if tribe is not None:
                ti = state.get("tribes", {}).get(tribe, {})
                from fs_bot.board.pieces import tribe_has_ally_disc
                if ti.get("allied_faction") != faction:
                    raise CommandError(
                        f"Tribe {tribe} is not a {faction} Ally"
                    )
                treg = ti.get("region") or TRIBE_TO_REGION.get(tribe)
                if treg != region:
                    raise CommandError(f"Tribe {tribe} is not in {region}")
                if not tribe_has_ally_disc(state, region, tribe, faction):
                    raise CommandError("Suborn cannot remove a Citadel as an Ally")
        else:
            if piece_state:
                avail = count_pieces_by_state(
                    state, region, faction, piece_type, piece_state
                )
            else:
                avail = count_pieces(state, region, faction, piece_type)
            if avail < 1:
                raise CommandError(
                    f"No {faction} {piece_type} in {region} to remove"
                )

    elif action == "place":
        if piece_type == ALLY:
            tribe = op.get("tribe")
            if not tribe:
                raise CommandError("Must specify tribe for Ally placement")

            # Tribe must be in region
            tribes = suborn_tribes(state, region)
            if tribe not in tribes:
                raise CommandError(f"Tribe {tribe} is not in {region}")

            # Tribe must be Subdued — unallied AND no status marker
            # (a Dispersed/Dispersed-Gathering Tribe is NOT Subdued,
            # §1.7/§3.2.3; allying one strands the Ally piece when the
            # Spring Phase clears the marker — found by the player_fuzz
            # structural oracle).
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") is not None
                    or tribe_info.get("status") is not None):
                raise CommandError(f"Tribe {tribe} is not Subdued")

            # Check stacking restriction — §1.4.2
            restriction = TRIBE_FACTION_RESTRICTION.get(tribe)
            if restriction is not None and restriction != faction:
                raise CommandError(
                    f"Cannot place {faction} Ally at {tribe} — restricted "
                    f"to {restriction}"
                )

            # Check Available
            avail = get_available(state, faction, ALLY)
            if avail < 1:
                raise CommandError(f"No {faction} Allies Available")
        else:
            # Check Available for Warband/Auxilia
            from fs_bot.engine.diviciacus import placement_available
            avail = placement_available(state, region, faction, piece_type,
                                        get_available(state, faction, piece_type))
            if avail < 1:
                raise CommandError(
                    f"No {faction} {piece_type} Available"
                )

    else:
        raise CommandError(f"Unknown Suborn action: {action}")
