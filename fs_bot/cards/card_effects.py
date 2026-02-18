"""
card_effects.py — Card Event effect implementations.

Each card handler receives (state, shaded) and mutates state in place.
The dispatcher execute_event() routes to the correct handler by card_id.

Convention for player choices:
  state["executing_faction"] — the faction playing the Event
  state["event_params"] — dict of card-specific choices set by the
      caller (bot logic or CLI) before invoking execute_event().

Source: Card Reference, A Card Reference
"""

from fs_bot.rules_consts import (
    CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
    SECOND_EDITION_CARDS,
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS, FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    SENATE_POSITIONS,
    SENATE_UP, SENATE_DOWN,
    # Regions
    PROVINCIA, CISALPINA,
    ALL_REGIONS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Legions
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    # Resources
    MAX_RESOURCES,
    # Markers
    MARKER_DEVASTATED, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_SCOUTED, MARKER_CIRCUMVALLATION, MARKER_COLONY,
    MARKER_GALLIA_TOGATA, MARKER_RAZED,
    MARKER_INTIMIDATED, MARKER_ABATIS,
    # Capabilities
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    # Events
    EVENT_SHADED, EVENT_UNSHADED,
    # Control
    ROMAN_CONTROL, NO_CONTROL, FACTION_CONTROL,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
)
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, flip_piece,
    count_pieces, count_pieces_by_state, get_available,
    get_leader_in_region, find_leader, PieceError,
    _count_on_legions_track,
)
from fs_bot.board.control import (
    calculate_control, refresh_all_control,
    is_controlled_by, get_controlled_regions,
)
from fs_bot.cards.capabilities import (
    activate_capability, deactivate_capability, is_capability_active,
)


# ---------------------------------------------------------------------------
# Shared helpers for card event implementations
# ---------------------------------------------------------------------------

# Senate position index mapping (same as winter.py)
_SENATE_INDEX = {pos: i for i, pos in enumerate(SENATE_POSITIONS)}


def _apply_senate_shift(state, direction):
    """Apply a single Senate marker shift.

    Per §6.5.1:
    - At extreme + not Firm: flip to Firm
    - At extreme + already Firm: no change (already at max)
    - Anywhere + Firm: flip back to normal (without moving)
    - Normal position: move one box in direction

    Args:
        state: game state dict
        direction: SENATE_UP ("up") or SENATE_DOWN ("down")
    """
    position = state["senate"]["position"]
    is_firm = state["senate"]["firm"]
    pos_idx = _SENATE_INDEX[position]

    if direction == SENATE_UP:
        # Toward Uproar (index 0)
        if pos_idx == 0:
            if not is_firm:
                state["senate"]["firm"] = True
        elif is_firm:
            state["senate"]["firm"] = False
        else:
            state["senate"]["position"] = SENATE_POSITIONS[pos_idx - 1]
    elif direction == SENATE_DOWN:
        # Toward Adulation (index 2)
        if pos_idx == len(SENATE_POSITIONS) - 1:
            if not is_firm:
                state["senate"]["firm"] = True
        elif is_firm:
            state["senate"]["firm"] = False
        else:
            state["senate"]["position"] = SENATE_POSITIONS[pos_idx + 1]


def _cap_resources(state, faction, amount):
    """Add resources to a faction, respecting the cap of MAX_RESOURCES (45).

    Args:
        state: game state dict
        faction: faction constant
        amount: integer (positive to add, negative to subtract)

    Returns:
        Actual amount changed.
    """
    current = state["resources"].get(faction, 0)
    new_val = max(0, min(MAX_RESOURCES, current + amount))
    state["resources"][faction] = new_val
    return new_val - current


# ---------------------------------------------------------------------------
# Base game card stubs (1–72)
# ---------------------------------------------------------------------------

def execute_card_1(state, shaded=False):
    """Card 1: Cicero — Senate shift.

    Both unshaded and shaded:
    Shift the Senate 1 box in either direction (or flip to Firm if
    already at top or bottom).

    Tips: The Senate would shift regardless of any Fallen Legions. If
    the Senate is already Firm, the Event would flip the marker in place,
    back to its normal side (6.5.1).

    Requires state["event_params"]["senate_direction"] = SENATE_UP or
    SENATE_DOWN to specify which direction to shift.

    Source: Card Reference, card 1
    """
    params = state.get("event_params", {})
    direction = params.get("senate_direction")
    if direction is None:
        raise ValueError(
            "Card 1 (Cicero) requires event_params['senate_direction'] "
            "to be set to SENATE_UP or SENATE_DOWN"
        )
    _apply_senate_shift(state, direction)

def execute_card_2(state, shaded=False):
    """Card 2: Legiones XIIII et XV — Senate shift + Legions / Free Battle.

    Unshaded: Romans may shift Senate 1 box up (toward Uproar) to place
    2 Legions total from Legions track and/or Fallen into Provincia.
    Tips: Legions can come from Fallen not just track. Shift to place
    must move marker one box up or flip it, so could not occur if
    already at Firm Uproar.

    Shaded: Free Battle against Romans in a Region. The first Loss
    removes a Legion automatically, if any there.
    TODO: Free Battle implementation requires battle module integration.

    Source: Card Reference, card 2
    """
    if not shaded:
        # Unshaded: Shift Senate up to place 2 Legions in Provincia
        # Cannot shift if already at Firm Uproar (per Tips)
        position = state["senate"]["position"]
        is_firm = state["senate"]["firm"]
        pos_idx = _SENATE_INDEX[position]

        can_shift = not (pos_idx == 0 and is_firm)  # Not at Firm Uproar
        if can_shift:
            _apply_senate_shift(state, SENATE_UP)
            # Place up to 2 Legions from track and/or Fallen into Provincia
            params = state.get("event_params", {})
            from_track = params.get("legions_from_track", 0)
            from_fallen = params.get("legions_from_fallen", 0)
            total = from_track + from_fallen
            if total > 2:
                total = 2
                # Clamp to 2 total
                from_track = min(from_track, 2)
                from_fallen = 2 - from_track

            if from_track > 0 and _count_on_legions_track(state) >= from_track:
                place_piece(state, PROVINCIA, ROMANS, LEGION,
                            count=from_track, from_legions_track=True)
            if from_fallen > 0 and state.get("fallen_legions", 0) >= from_fallen:
                place_piece(state, PROVINCIA, ROMANS, LEGION,
                            count=from_fallen, from_fallen=True)
    else:
        # Shaded: Free Battle against Romans in a Region
        # The first Loss removes a Legion automatically if any there
        # TODO: Integrate with battle module — for now, mark the
        # auto-Legion-loss flag in event_params for the battle caller
        params = state.get("event_params", {})
        battle_region = params.get("battle_region")
        if battle_region:
            # The battle itself should be called by the bot/CLI code
            # with the auto_legion_loss modifier. Store the modifier.
            state.setdefault("event_modifiers", {})
            state["event_modifiers"]["card_2_auto_legion_loss"] = True
            state["event_modifiers"]["card_2_battle_region"] = battle_region

def execute_card_3(state, shaded=False):
    """Card 3: Pompey — Senate shift + Legion / remove Legions to track.

    Unshaded: If Adulation, place 1 Legion in Provincia. If not,
    shift the Senate 1 box down (toward Adulation).

    Shaded: If the Legions track has 4 or fewer Legions, Romans
    remove 2 Legions to the Legions track.

    Source: Card Reference, card 3
    """
    if not shaded:
        # Unshaded: If Adulation, place 1 Legion in Provincia;
        # if not, shift Senate 1 box down
        if state["senate"]["position"] == ADULATION:
            # Place 1 Legion in Provincia from Legions track
            if _count_on_legions_track(state) >= 1:
                place_piece(state, PROVINCIA, ROMANS, LEGION,
                            from_legions_track=True)
        else:
            _apply_senate_shift(state, SENATE_DOWN)
    else:
        # Shaded: If Legions track has 4 or fewer, Romans remove 2
        # Legions to track
        track_count = _count_on_legions_track(state)
        if track_count <= 4:
            # Remove 2 Legions from map to track
            # Bot chooses which Legions — use event_params or find any
            params = state.get("event_params", {})
            regions = params.get("legion_removal_regions", [])
            removed = 0
            for region in regions:
                region_legions = count_pieces(state, region, ROMANS, LEGION)
                to_remove = min(region_legions, 2 - removed)
                if to_remove > 0:
                    remove_piece(state, region, ROMANS, LEGION,
                                 count=to_remove, to_track=True)
                    removed += to_remove
                if removed >= 2:
                    break
            # If no regions specified or not enough found, try to find
            # Legions anywhere on map
            if removed < 2:
                for region in list(state["spaces"].keys()):
                    if removed >= 2:
                        break
                    region_legions = count_pieces(
                        state, region, ROMANS, LEGION)
                    to_remove = min(region_legions, 2 - removed)
                    if to_remove > 0:
                        remove_piece(state, region, ROMANS, LEGION,
                                     count=to_remove, to_track=True)
                        removed += to_remove

def execute_card_4(state, shaded=False):
    """Card 4: Circumvallation — Free March to Citadel + marker.

    Unshaded: Romans may free March to an adjacent Citadel and put
    Circumvallation marker on Citadel Faction's pieces there.
    Marked group may not move from Region; if it attacks alone,
    Romans defend as if Fort. Remove marker if group attacks Romans
    in Battle or is eliminated, or if no Romans there.

    Source: Card Reference, card 4
    """
    if not shaded:
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            return
        # Place Circumvallation marker
        state.setdefault("markers", {})
        state["markers"].setdefault(target, set())
        state["markers"][target].add(MARKER_CIRCUMVALLATION)
        # Free March is handled by the caller (bot/CLI)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_4_free_march_to"] = target
    else:
        # Card 4 has only unshaded text in Card Reference
        # Same effect for both sides
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            return
        state.setdefault("markers", {})
        state["markers"].setdefault(target, set())
        state["markers"][target].add(MARKER_CIRCUMVALLATION)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_4_free_march_to"] = target

def execute_card_5(state, shaded=False):
    """Card 5: Gallia Togata — Gallia Togata marker / Remove pieces.

    Unshaded: Place Gallia Togata marker and 3 Auxilia in Cisalpina.
    It is a Supply Line Region where only Romans may stack, March out
    costs 0, and each Recruit places 2 Auxilia.

    Shaded: Unless Senate in Adulation, Romans remove 1 Legion to
    track and 2 Auxilia to Available.
    Tips: Shaded Legion removal is to track not Fallen.

    Source: Card Reference, card 5
    """
    if not shaded:
        # Unshaded: Place Gallia Togata marker and 3 Auxilia in Cisalpina
        state.setdefault("markers", {})
        state["markers"].setdefault(CISALPINA, set())
        state["markers"][CISALPINA].add(MARKER_GALLIA_TOGATA)
        avail = get_available(state, ROMANS, AUXILIA)
        to_place = min(3, avail)
        if to_place > 0:
            place_piece(state, CISALPINA, ROMANS, AUXILIA, count=to_place)
    else:
        # Shaded: Unless Adulation, remove 1 Legion to track + 2 Auxilia
        if state["senate"]["position"] != ADULATION:
            params = state.get("event_params", {})
            legion_region = params.get("legion_removal_region")
            if legion_region is None:
                for region in state["spaces"]:
                    if count_pieces(state, region, ROMANS, LEGION) > 0:
                        legion_region = region
                        break
            if legion_region and count_pieces(
                    state, legion_region, ROMANS, LEGION) > 0:
                remove_piece(state, legion_region, ROMANS, LEGION,
                             to_track=True)
            # Remove 2 Auxilia to Available
            auxilia_regions = params.get("auxilia_removal_regions", [])
            removed = 0
            for region in auxilia_regions:
                avail_in = count_pieces(state, region, ROMANS, AUXILIA)
                to_rem = min(avail_in, 2 - removed)
                if to_rem > 0:
                    remove_piece(state, region, ROMANS, AUXILIA,
                                 count=to_rem)
                    removed += to_rem
                if removed >= 2:
                    break
            if removed < 2:
                for region in list(state["spaces"].keys()):
                    if removed >= 2:
                        break
                    avail_in = count_pieces(
                        state, region, ROMANS, AUXILIA)
                    to_rem = min(avail_in, 2 - removed)
                    if to_rem > 0:
                        remove_piece(state, region, ROMANS, AUXILIA,
                                     count=to_rem)
                        removed += to_rem

def execute_card_6(state, shaded=False):
    """Card 6: Marcus Antonius — Free Scout+Battle / Move Auxilia.

    Unshaded: Romans may free Scout, then may free Battle in 1 Region,
    Auxilia causing twice usual Losses.

    Shaded: Move up to 4 on-map Auxilia to Provincia. Romans Ineligible
    through next card. Executing Faction Eligible.

    Source: Card Reference, card 6
    """
    if not shaded:
        # Unshaded: Free Scout then free Battle with double Auxilia Losses
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_6_free_scout"] = True
        state["event_modifiers"]["card_6_double_auxilia_losses"] = True
        params = state.get("event_params", {})
        battle_region = params.get("battle_region")
        if battle_region:
            state["event_modifiers"]["card_6_battle_region"] = battle_region
    else:
        # Shaded: Move up to 4 Auxilia to Provincia
        params = state.get("event_params", {})
        moves = params.get("auxilia_moves", [])
        moved = 0
        for from_region, count in moves:
            actual = min(count, 4 - moved,
                         count_pieces(state, from_region, ROMANS, AUXILIA))
            if actual > 0:
                for _ in range(actual):
                    remove_piece(state, from_region, ROMANS, AUXILIA)
                    place_piece(state, PROVINCIA, ROMANS, AUXILIA)
                moved += actual
            if moved >= 4:
                break
        # Romans Ineligible, Executing Faction Eligible
        state["eligibility"][ROMANS] = INELIGIBLE
        executing = state.get("executing_faction")
        if executing and executing != ROMANS:
            state["eligibility"][executing] = ELIGIBLE

def execute_card_7(state, shaded=False):
    """Card 7: Alaudae — Place Legion+Auxilia / remove to track.

    Unshaded: Romans place 1 Legion and 1 Auxilia in a Roman
    Controlled Region. Tips: Legion could not be placed from Fallen.

    Shaded: If the Legions track has 7 or fewer Legions, remove
    1 Legion to the track and 1 Auxilia to Available.
    Tips: Legions track does not include Fallen Legions.

    Source: Card Reference, card 7
    """
    if not shaded:
        # Unshaded: Place 1 Legion (from track, NOT Fallen) and 1 Auxilia
        # in a Roman Controlled Region
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            # Auto-select: first Roman controlled region
            controlled = get_controlled_regions(state, ROMANS)
            if not controlled:
                return  # No Roman controlled region — event ineffective
            target = controlled[0]
        # Legion from track (not Fallen per Tips)
        if _count_on_legions_track(state) >= 1:
            place_piece(state, target, ROMANS, LEGION,
                        from_legions_track=True)
        # Auxilia from Available
        if get_available(state, ROMANS, AUXILIA) >= 1:
            place_piece(state, target, ROMANS, AUXILIA)
    else:
        # Shaded: If Legions track has 7 or fewer, remove 1 Legion to
        # track and 1 Auxilia to Available
        track_count = _count_on_legions_track(state)
        if track_count <= 7:
            params = state.get("event_params", {})
            # Remove 1 Legion from map to track
            legion_region = params.get("legion_removal_region")
            if legion_region is None:
                # Auto-find a region with a Legion
                for region in state["spaces"]:
                    if count_pieces(state, region, ROMANS, LEGION) > 0:
                        legion_region = region
                        break
            if legion_region:
                remove_piece(state, legion_region, ROMANS, LEGION,
                             to_track=True)
            # Remove 1 Auxilia from map to Available
            auxilia_region = params.get("auxilia_removal_region")
            if auxilia_region is None:
                for region in state["spaces"]:
                    if count_pieces(state, region, ROMANS, AUXILIA) > 0:
                        auxilia_region = region
                        break
            if auxilia_region:
                remove_piece(state, auxilia_region, ROMANS, AUXILIA)

def execute_card_8(state, shaded=False):
    """Card 8: Baggage Trains — CAPABILITY.

    Unshaded: Your March costs 0 Resources.
    Shaded: Your Raids may use 3 Warbands per Region and steal
    Resources despite Citadels or Forts.

    Source: Card Reference, card 8
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 8, side)

def execute_card_9(state, shaded=False):
    """Card 9: Mons Cevenna — Free March + Command near Provincia.

    Both sides: Free March from a Region into an adjacent Region, both
    within 1 Region of Provincia. Then execute a free Command and any
    free Special Ability in (or from) the destination Region.
    Tips: "Within 1 of Provincia" means Provincia, Sequani, or Arverni.

    Source: Card Reference, card 9
    """
    # Both unshaded and shaded have the same effect
    params = state.get("event_params", {})
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_9_free_march_and_command"] = True
    from_region = params.get("march_from")
    to_region = params.get("march_to")
    if from_region and to_region:
        state["event_modifiers"]["card_9_march_from"] = from_region
        state["event_modifiers"]["card_9_march_to"] = to_region

def execute_card_10(state, shaded=False):
    """Card 10: Ballistae — CAPABILITY.

    Unshaded: Besiege cancels Citadel's halving of Losses. Battle
    rolls remove Forts on 1-2 not 1-3.
    Shaded: Place near a Gallic Faction. That Faction after Ambush
    may remove defending Fort or Citadel.

    Source: Card Reference, card 10
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 10, side)

def execute_card_11(state, shaded=False):
    """Card 11: Numidians — Place Auxilia + Battle / Remove Auxilia.

    Unshaded: Romans place 3 Auxilia in a Region within 1 of their
    Leader and free Battle there, with Auxilia causing double Losses
    (before rounding).

    Shaded: Remove any 4 Auxilia.

    Source: Card Reference, card 11
    """
    if not shaded:
        # Unshaded: Place 3 Auxilia near Roman Leader, then free Battle
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            return
        avail = get_available(state, ROMANS, AUXILIA)
        to_place = min(3, avail)
        if to_place > 0:
            place_piece(state, target, ROMANS, AUXILIA, count=to_place)
        # Battle modifier: Auxilia double Losses
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_11_double_auxilia_losses"] = True
        state["event_modifiers"]["card_11_battle_region"] = target
    else:
        # Shaded: Remove any 4 Auxilia from anywhere
        params = state.get("event_params", {})
        removal_regions = params.get("auxilia_removal_regions", [])
        removed = 0
        for region, count in removal_regions:
            actual = min(count, 4 - removed,
                         count_pieces(state, region, ROMANS, AUXILIA))
            if actual > 0:
                remove_piece(state, region, ROMANS, AUXILIA, count=actual)
                removed += actual
            if removed >= 4:
                break
        # Auto-remove if not enough specified
        if removed < 4:
            for region in list(state["spaces"].keys()):
                if removed >= 4:
                    break
                avail_in_region = count_pieces(
                    state, region, ROMANS, AUXILIA)
                actual = min(avail_in_region, 4 - removed)
                if actual > 0:
                    remove_piece(state, region, ROMANS, AUXILIA,
                                 count=actual)
                    removed += actual

def execute_card_12(state, shaded=False):
    """Card 12: Titus Labienus — CAPABILITY.

    Unshaded: Roman Special Abilities may select Regions regardless
    of where the Roman leader is located.
    Shaded: Build and Scout Reveal are maximum 1 Region.

    Source: Card Reference, card 12
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 12, side)

def execute_card_13(state, shaded=False):
    """Card 13: Balearic Slingers — CAPABILITY.

    Unshaded: Romans choose 1 Region per enemy Battle Command.
    Auxilia there first inflict 1/2 Loss each on attacker. Then resolve
    Battle.
    Shaded: Recruit only where Supply Line, paying 2 Resources per
    Region.

    Source: Card Reference, card 13
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 13, side)

def execute_card_14(state, shaded=False):
    """Card 14: Clodius Pulcher — Senate shift / Leader to Provincia.

    Unshaded: Shift the Senate 1 box down (toward Adulation, or flip
    to Firm if there).

    Shaded: Roman Leader (if on map) to Provincia. Romans Ineligible
    through next card. Executing Faction Eligible.

    Source: Card Reference, card 14
    """
    if not shaded:
        # Unshaded: Shift Senate 1 box down toward Adulation
        _apply_senate_shift(state, SENATE_DOWN)
    else:
        # Shaded: Move Roman Leader to Provincia if on map
        leader_region = find_leader(state, ROMANS)
        if leader_region is not None and leader_region != PROVINCIA:
            move_piece(state, leader_region, PROVINCIA, ROMANS, LEADER)
        # Romans Ineligible through next card
        state["eligibility"][ROMANS] = INELIGIBLE
        # Executing Faction stays Eligible
        executing = state.get("executing_faction")
        if executing and executing != ROMANS:
            state["eligibility"][executing] = ELIGIBLE

def execute_card_15(state, shaded=False):
    """Card 15: Legio X — CAPABILITY.

    Unshaded: In Battles with Roman Leader and Legion, final Losses
    against Romans -1 and final Losses Romans inflict +2.
    Shaded: Caesar attacking in Battle doubles Loss inflicted by
    1 Legion only (not by all Legions).

    Source: Card Reference, card 15
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 15, side)

def execute_card_16(state, shaded=False):
    """Card 16: Ambacti — Place Auxilia / Roll and remove Auxilia.

    Unshaded: Place 4 Auxilia in a Region with Romans or 6 with Caesar.
    Tip: "Romans" means any Roman Forces piece.

    Shaded: Roll a die and remove either 3 or that number of Auxilia
    from anywhere.

    Source: Card Reference, card 16
    """
    if not shaded:
        # Unshaded: Place 4 Auxilia (or 6 if Caesar in region)
        # Region must have at least one Roman Forces piece (Tip: "Romans"
        # means any Roman Forces piece — Leader, Legion, Auxilia, Fort, Ally)
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            return  # No target specified
        # Validate region has Roman pieces
        if count_pieces(state, target, ROMANS) == 0:
            return  # No Roman Forces in this region — event ineffective
        # Check if Caesar is in the region — 6 Auxilia if so, else 4
        leader = get_leader_in_region(state, target, ROMANS)
        num_auxilia = 6 if leader == CAESAR else 4
        avail = get_available(state, ROMANS, AUXILIA)
        to_place = min(num_auxilia, avail)
        if to_place > 0:
            place_piece(state, target, ROMANS, AUXILIA, count=to_place)
    else:
        # Shaded: Roll a die; executing faction chooses to remove either
        # 3 or the die roll number of Auxilia from anywhere.
        # Per Card Reference: "remove either 3 or that number" — a choice.
        from fs_bot.rules_consts import DIE_MIN, DIE_MAX
        roll = state["rng"].randint(DIE_MIN, DIE_MAX)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_16_die_roll"] = roll
        params = state.get("event_params", {})
        # Executing faction chooses: "roll" or "three" (default: max for bot)
        choice = params.get("removal_choice", "max")
        if choice == "roll":
            to_remove = roll
        elif choice == "three":
            to_remove = 3
        else:
            # Default bot behavior: remove as many as possible to hurt Romans
            to_remove = max(roll, 3)
        removal_regions = params.get("auxilia_removal_regions", [])
        removed = 0
        for region, count in removal_regions:
            actual = min(count, to_remove - removed,
                         count_pieces(state, region, ROMANS, AUXILIA))
            if actual > 0:
                remove_piece(state, region, ROMANS, AUXILIA, count=actual)
                removed += actual
            if removed >= to_remove:
                break
        # Auto-remove from anywhere if not enough specified
        if removed < to_remove:
            for region in list(state["spaces"].keys()):
                if removed >= to_remove:
                    break
                avail_in_region = count_pieces(
                    state, region, ROMANS, AUXILIA)
                actual = min(avail_in_region, to_remove - removed)
                if actual > 0:
                    remove_piece(state, region, ROMANS, AUXILIA,
                                 count=actual)
                    removed += actual

def execute_card_17(state, shaded=False):
    """Card 17: Germanic Chieftains — March Germans / Germans Phase.

    Unshaded: Romans March up to 3 German groups, then Ambush with
    Germans in any 1 Region.

    Shaded: Conduct an immediate Germans Phase as if Winter.

    Source: Card Reference, card 17
    """
    if not shaded:
        # Unshaded: Free March + Ambush with Germans (guided by Romans)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_17_march_german_groups"] = 3
        state["event_modifiers"]["card_17_german_ambush"] = True
    else:
        # Shaded: Immediate Germans Phase as if Winter
        # This triggers the full §6.2 procedure
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_17_germans_phase"] = True

def execute_card_18(state, shaded=False):
    """Card 18: Rhenus Bridge — Remove Germans / Roman Resources penalty.

    Unshaded: Romans may remove all Germans from 1 Germania Region
    under or adjacent to Roman Control.
    Tips: "all Germans" means all Germanic pieces: Allies and Warbands.

    Shaded: If a Legion is within 1 Region of Germania, Romans -6
    Resources and Ineligible through next card.
    Tips: "within 1 Region" means either in or adjacent to a Germania
    Region.

    Source: Card Reference, card 18
    """
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.rules_consts import GERMANIA_REGIONS
    if not shaded:
        # Unshaded: Remove all Germans from 1 Germania Region under or
        # adjacent to Roman Control
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            return
        # Validate target is a Germania Region
        if target not in GERMANIA_REGIONS:
            return
        # Validate target is under or adjacent to Roman Control
        roman_ctrl = is_controlled_by(state, target, ROMANS)
        if not roman_ctrl:
            adj_regions = get_adjacent(target, state.get("scenario"))
            roman_ctrl = any(
                is_controlled_by(state, adj, ROMANS) for adj in adj_regions
            )
        if not roman_ctrl:
            return  # Not under or adjacent to Roman Control
        # Remove all Germanic Warbands (all states)
        for ps in (HIDDEN, REVEALED, SCOUTED):
            wbs = count_pieces_by_state(
                state, target, GERMANS, WARBAND, ps)
            if wbs > 0:
                remove_piece(state, target, GERMANS, WARBAND,
                             count=wbs, piece_state=ps)
        # Remove all Germanic Allies
        allies = count_pieces(state, target, GERMANS, ALLY)
        if allies > 0:
            remove_piece(state, target, GERMANS, ALLY, count=allies)
    else:
        # Shaded: If any Legion is in or adjacent to a Germania Region,
        # Romans -6 Resources and Ineligible
        legion_near = False
        for g_region in GERMANIA_REGIONS:
            if count_pieces(state, g_region, ROMANS, LEGION) > 0:
                legion_near = True
                break
            for adj in get_adjacent(g_region, state.get("scenario")):
                if count_pieces(state, adj, ROMANS, LEGION) > 0:
                    legion_near = True
                    break
            if legion_near:
                break
        if legion_near:
            _cap_resources(state, ROMANS, -6)
            state["eligibility"][ROMANS] = INELIGIBLE

def execute_card_19(state, shaded=False):
    """Card 19: Lucterius — Remove Warbands or place Auxilia / Place Leader.

    Unshaded: Either remove up to 6 Arverni Warbands within 1 Region
    of Provincia, or place up to 5 Auxilia in Provincia.

    Shaded: If Arverni Successor on map or Available, Arverni place
    him anywhere, symbol up, as if Vercingetorix.

    Source: Card Reference, card 19
    """
    if not shaded:
        params = state.get("event_params", {})
        choice = params.get("choice", "auxilia")  # "warbands" or "auxilia"
        if choice == "warbands":
            # Remove up to 6 Arverni Warbands within 1 of Provincia
            from fs_bot.map.map_data import get_adjacent
            near_prov = [PROVINCIA] + list(
                get_adjacent(PROVINCIA, state["scenario"]))
            removal_regions = params.get("removal_regions", near_prov)
            removed = 0
            for region in removal_regions:
                if region not in near_prov:
                    continue
                wb_count = count_pieces(state, region, ARVERNI, WARBAND)
                to_rem = min(wb_count, 6 - removed)
                if to_rem > 0:
                    remove_piece(state, region, ARVERNI, WARBAND,
                                 count=to_rem)
                    removed += to_rem
                if removed >= 6:
                    break
        else:
            # Place up to 5 Auxilia in Provincia
            avail = get_available(state, ROMANS, AUXILIA)
            to_place = min(5, avail)
            if to_place > 0:
                place_piece(state, PROVINCIA, ROMANS, AUXILIA,
                            count=to_place)
    else:
        # Shaded: Place Arverni Successor as Vercingetorix
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target and get_available(state, ARVERNI, LEADER) >= 1:
            place_piece(state, target, ARVERNI, LEADER,
                        leader_name=VERCINGETORIX)

def execute_card_20(state, shaded=False):
    """Card 20: Optimates — Early game end condition.

    Both sides: Keep this card by the Winter track. Upon the game's
    2nd and each later Victory Phase, if Roman victory exceeds 12,
    first remove all Legions to the Legions track, then end the game.

    Source: Card Reference, card 20
    """
    # This is a persistent effect — activate as a capability-like marker
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["optimates_active"] = True

def execute_card_21(state, shaded=False):
    """Card 21: The Province — Auxilia/Resources / Senate shift + Warbands.

    Unshaded: If only Roman pieces in Provincia, either place 5 Auxilia
    there, or add +10 Roman Resources.

    Shaded: If Arverni Control Provincia, shift Senate 2 boxes up
    (toward Uproar). If not, Arverni place 4 Warbands there and free
    Raid or Battle there as if no Fort.
    Tips: Shaded Warbands must be Arverni.

    Source: Card Reference, card 21
    """
    if not shaded:
        # Unshaded: If only Roman pieces in Provincia
        only_roman = True
        for faction in FACTIONS:
            if faction == ROMANS:
                continue
            if count_pieces(state, PROVINCIA, faction) > 0:
                only_roman = False
                break
        if only_roman and count_pieces(state, PROVINCIA, ROMANS) > 0:
            params = state.get("event_params", {})
            choice = params.get("province_choice", "auxilia")
            if choice == "resources":
                _cap_resources(state, ROMANS, 10)
            else:
                avail = get_available(state, ROMANS, AUXILIA)
                to_place = min(5, avail)
                if to_place > 0:
                    place_piece(state, PROVINCIA, ROMANS, AUXILIA,
                                count=to_place)
    else:
        # Shaded: Check Arverni Control of Provincia
        if is_controlled_by(state, PROVINCIA, ARVERNI):
            # Shift Senate 2 boxes up
            _apply_senate_shift(state, SENATE_UP)
            _apply_senate_shift(state, SENATE_UP)
        else:
            # Arverni place 4 Warbands in Provincia
            avail = get_available(state, ARVERNI, WARBAND)
            to_place = min(4, avail)
            if to_place > 0:
                place_piece(state, PROVINCIA, ARVERNI, WARBAND,
                            count=to_place)
            # Free Raid or Battle as if no Fort — store modifier
            # TODO: Bot/CLI decides Raid vs Battle; for now store modifier
            state.setdefault("event_modifiers", {})
            state["event_modifiers"]["card_21_no_fort"] = True

def execute_card_22(state, shaded=False):
    """Card 22: Hostages — Replace pieces / Place Allies+Warbands.

    Unshaded: Among Regions that you Control, remove or replace a
    total of up to 4 Warbands or Auxilia with your own.

    Shaded: Place a Gallic Ally and any 1 Warband at each of 1 or
    2 Subdued Tribes where Roman pieces.

    Source: Card Reference, card 22
    """
    if not shaded:
        # Unshaded: Replace up to 4 Warbands/Auxilia in controlled Regions
        params = state.get("event_params", {})
        replacements = params.get("replacements", [])
        executing = state.get("executing_faction")
        count_done = 0
        for repl in replacements:
            if count_done >= 4:
                break
            region = repl.get("region")
            target_faction = repl.get("target_faction")
            piece_type = repl.get("piece_type", WARBAND)
            if (region and target_faction and executing
                    and count_pieces(state, region, target_faction,
                                     piece_type) > 0):
                remove_piece(state, region, target_faction, piece_type)
                replace_type = WARBAND if piece_type == WARBAND else AUXILIA
                if executing == ROMANS:
                    replace_type = AUXILIA
                if get_available(state, executing, replace_type) > 0:
                    place_piece(state, region, executing, replace_type)
                count_done += 1
    else:
        # Shaded: Place Gallic Ally + Warband at 1-2 Subdued Tribes
        # with Roman pieces
        params = state.get("event_params", {})
        tribes = params.get("target_tribes", [])
        executing = state.get("executing_faction")
        if not executing:
            return
        for tribe_info in tribes[:2]:
            region = tribe_info.get("region")
            faction = tribe_info.get("faction", executing)
            if region:
                if get_available(state, faction, ALLY) > 0:
                    place_piece(state, region, faction, ALLY)
                wb_faction = tribe_info.get("warband_faction", faction)
                if get_available(state, wb_faction, WARBAND) > 0:
                    place_piece(state, region, wb_faction, WARBAND)

def execute_card_23(state, shaded=False):
    """Card 23: Sacking — Razed marker / Remove Legion.

    Unshaded: Romans may place Razed marker on a City at Roman Control
    (replace anything) for +8 Resources. It permanently Disperses the City.
    Tips: Razed is like Dispersed for all purposes except not removed in Spring.

    Shaded: If a Legion where your Citadel, remove the Legion and Romans
    Ineligible through next card.
    Tips: Shaded Legion removal is to Fallen.

    Source: Card Reference, card 23
    """
    if not shaded:
        # Unshaded: Place Razed marker on a City at Roman Control
        params = state.get("event_params", {})
        target_city = params.get("target_city")
        if target_city is None:
            return
        # Find the region containing this city
        from fs_bot.rules_consts import CITY_TO_TRIBE, TRIBE_TO_REGION
        tribe = CITY_TO_TRIBE.get(target_city)
        if tribe is None:
            return
        region = TRIBE_TO_REGION.get(tribe)
        if region is None:
            return
        # Validate: City must be at Roman Control
        if not is_controlled_by(state, region, ROMANS):
            return
        # Place Razed marker (replaces anything at that tribe — "replace
        # anything" means existing Ally/Citadel/Dispersed at the city)
        state.setdefault("markers", {})
        state["markers"].setdefault(region, set())
        state["markers"][region].add(MARKER_RAZED)
        # +8 Resources to Romans
        _cap_resources(state, ROMANS, 8)
        # Update tribe status to mark as Razed/Dispersed
        if tribe in state.get("tribes", {}):
            # Remove any existing Ally/Citadel at this tribe
            tribe_info = state["tribes"][tribe]
            if tribe_info.get("allied_faction"):
                allied_fac = tribe_info["allied_faction"]
                ally_count = count_pieces(state, region, allied_fac, ALLY)
                if ally_count > 0:
                    remove_piece(state, region, allied_fac, ALLY)
                tribe_info["allied_faction"] = None
            # Remove Citadel at this tribe if any
            for fac in GALLIC_FACTIONS:
                if count_pieces(state, region, fac, CITADEL) > 0:
                    remove_piece(state, region, fac, CITADEL)
            tribe_info["status"] = MARKER_RAZED
    else:
        # Shaded: If a Legion where executing faction's Citadel,
        # remove the Legion to Fallen, Romans Ineligible
        executing = state.get("executing_faction")
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            # Auto-find: region with both a Legion and executing
            # faction's Citadel
            if executing:
                for region in state["spaces"]:
                    if (count_pieces(state, region, ROMANS, LEGION) > 0
                            and count_pieces(
                                state, region, executing, CITADEL) > 0):
                        target = region
                        break
        if target is not None:
            if count_pieces(state, target, ROMANS, LEGION) > 0:
                remove_piece(state, target, ROMANS, LEGION,
                             to_fallen=True)
                state["eligibility"][ROMANS] = INELIGIBLE

def execute_card_24(state, shaded=False):
    """Card 24: Sappers — Resource loss / Remove Legions+Auxilia.

    Unshaded: A Gallic Faction with a Citadel loses 10 Resources.

    Shaded: In a Region with an Arverni Citadel, remove a total of
    2 Legions and/or Auxilia.
    Tips: Legion removal would be to Fallen.

    Source: Card Reference, card 24
    """
    if not shaded:
        # Unshaded: A Gallic Faction with a Citadel loses 10 Resources
        params = state.get("event_params", {})
        target_faction = params.get("target_faction")
        if target_faction is None:
            # Auto-select: first Gallic faction with a Citadel on map
            for faction in GALLIC_FACTIONS:
                for region in state["spaces"]:
                    if count_pieces(state, region, faction, CITADEL) > 0:
                        target_faction = faction
                        break
                if target_faction:
                    break
        if target_faction is None:
            return  # No Gallic faction has a Citadel
        # Validate the target faction actually has a Citadel on map
        has_citadel = False
        for region in state["spaces"]:
            if count_pieces(state, region, target_faction, CITADEL) > 0:
                has_citadel = True
                break
        if has_citadel and target_faction in state.get("resources", {}):
            _cap_resources(state, target_faction, -10)
    else:
        # Shaded: In a Region with Arverni Citadel, remove 2
        # Legions and/or Auxilia (Legions to Fallen)
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            # Auto-find region with Arverni Citadel
            for region in state["spaces"]:
                if count_pieces(state, region, ARVERNI, CITADEL) > 0:
                    target = region
                    break
        if target is None:
            return
        # Validate target region has Arverni Citadel
        if count_pieces(state, target, ARVERNI, CITADEL) == 0:
            return
        # Remove up to 2 total Legions and/or Auxilia
        legions_to_remove = params.get("legions_to_remove", 0)
        auxilia_to_remove = params.get("auxilia_to_remove", 0)
        total = legions_to_remove + auxilia_to_remove
        # Clamp to 2 total
        if total > 2:
            legions_to_remove = min(legions_to_remove, 2)
            auxilia_to_remove = min(auxilia_to_remove, 2 - legions_to_remove)
        if total == 0:
            # Default: remove Legions first, then Auxilia
            legions_avail = count_pieces(state, target, ROMANS, LEGION)
            legions_to_remove = min(legions_avail, 2)
            auxilia_to_remove = min(
                count_pieces(state, target, ROMANS, AUXILIA),
                2 - legions_to_remove)
        if legions_to_remove > 0:
            remove_piece(state, target, ROMANS, LEGION,
                         count=legions_to_remove, to_fallen=True)
        if auxilia_to_remove > 0:
            remove_piece(state, target, ROMANS, AUXILIA,
                         count=auxilia_to_remove)

def execute_card_25(state, shaded=False):
    """Card 25: Aquitani — Free Battle + extra Losses / CAPABILITY Rally bonus.

    Unshaded: Free Battle in either Pictones or Arverni Region,
    inflicting 3 extra Losses, 1 Ally (not Citadel) first.

    Shaded (CAPABILITY): Your Rally in Pictones and Arverni Regions
    places 2 extra Warbands each.

    Source: Card Reference, card 25
    """
    if shaded:
        # CAPABILITY: Rally bonus in Pictones and Arverni
        activate_capability(state, 25, EVENT_SHADED)
    else:
        # Unshaded: Free Battle with 3 extra Losses
        # The battle itself needs to be invoked by the caller
        # Store the modifier for the battle module
        params = state.get("event_params", {})
        battle_region = params.get("battle_region")
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_25_extra_losses"] = 3
        state["event_modifiers"]["card_25_ally_first"] = True
        if battle_region:
            state["event_modifiers"]["card_25_battle_region"] = battle_region

def execute_card_26(state, shaded=False):
    """Card 26: Gobannitio — Remove at Gergovia / Arverni Rally.

    Unshaded: Remove anything at Gergovia. Place a Roman Ally or
    Aedui Ally or Citadel there (despite Arverni-only stacking).

    Shaded: Arverni may remove and place Allies as desired in Arverni
    Region, then free Rally within 1 of Vercingetorix.

    Source: Card Reference, card 26
    """
    from fs_bot.rules_consts import (
        TRIBE_ARVERNI, ARVERNI_REGION, CITY_GERGOVIA, TRIBE_TO_REGION,
    )
    if not shaded:
        params = state.get("event_params", {})
        region = ARVERNI_REGION
        tribe = TRIBE_ARVERNI  # Gergovia is the city at TRIBE_ARVERNI
        # "Remove anything at Gergovia" — remove Ally and/or Citadel
        # at the Arverni tribe (where Gergovia sits).
        tribe_info = state.get("tribes", {}).get(tribe)
        if tribe_info and tribe_info.get("allied_faction"):
            allied_fac = tribe_info["allied_faction"]
            if count_pieces(state, region, allied_fac, ALLY) > 0:
                remove_piece(state, region, allied_fac, ALLY)
            tribe_info["allied_faction"] = None
        # Remove Citadel at Gergovia if any (check all factions)
        for fac in (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS):
            if count_pieces(state, region, fac, CITADEL) > 0:
                remove_piece(state, region, fac, CITADEL)
        # Place Roman Ally or Aedui Ally or Citadel (despite Arverni-only)
        place_faction = params.get("place_faction", ROMANS)
        place_type = params.get("place_type", ALLY)
        if get_available(state, place_faction, place_type) > 0:
            place_piece(state, region, place_faction, place_type)
            if place_type == ALLY:
                if tribe_info:
                    tribe_info["allied_faction"] = place_faction
    else:
        # Shaded: Arverni remove/place Allies in Arverni Region + free Rally
        params = state.get("event_params", {})
        # Ally removals/placements handled by caller via event_params
        removals = params.get("ally_removals", [])
        for tribe_name in removals:
            t_info = state.get("tribes", {}).get(tribe_name)
            if t_info and t_info.get("allied_faction"):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, ARVERNI_REGION, old_fac, ALLY) > 0:
                    remove_piece(state, ARVERNI_REGION, old_fac, ALLY)
                t_info["allied_faction"] = None
        placements = params.get("ally_placements", [])
        for tribe_name in placements:
            t_info = state.get("tribes", {}).get(tribe_name)
            if t_info and get_available(state, ARVERNI, ALLY) > 0:
                place_piece(state, ARVERNI_REGION, ARVERNI, ALLY)
                t_info["allied_faction"] = ARVERNI
        # Free Rally within 1 Region of Vercingetorix
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_26_arverni_rally"] = True

def execute_card_27(state, shaded=False):
    """Card 27: Massed Gallic Archers — CAPABILITY (both sides).

    Unshaded: Arverni Battle each Region inflicts 1 fewer Defender
    Loss (before any halving).
    Shaded: At start of Battles with 6+ Arverni Warbands, the other
    side first must absorb 1 extra Loss.

    Source: Card Reference, card 27
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 27, side)

def execute_card_28(state, shaded=False):
    """Card 28: Oppida — Gallic Allies at Cities / Citadels.

    Both sides (Hillforts): Place any Available Gallic Allied Tribes at
    Subdued Cities not under Roman Control. Then replace any Gallic
    Allies at any Cities with Available Citadels of same Faction.

    Source: Card Reference, card 28
    """
    from fs_bot.rules_consts import (
        CITY_TO_TRIBE, TRIBE_TO_REGION,
    )
    params = state.get("event_params", {})
    # Place Gallic Allies at Subdued Cities without Roman Control
    ally_placements = params.get("ally_placements", [])
    for placement in ally_placements:
        tribe = placement["tribe"]
        faction = placement["faction"]
        region = TRIBE_TO_REGION.get(tribe)
        if region and faction in GALLIC_FACTIONS:
            tribe_info = state.get("tribes", {}).get(tribe)
            if (tribe_info and tribe_info.get("allied_faction") is None
                    and not is_controlled_by(state, region, ROMANS)):
                if get_available(state, faction, ALLY) > 0:
                    place_piece(state, region, faction, ALLY)
                    tribe_info["allied_faction"] = faction
    # Replace Gallic Allies at Cities with Citadels of same Faction
    citadel_upgrades = params.get("citadel_upgrades", [])
    for city in citadel_upgrades:
        tribe = CITY_TO_TRIBE.get(city)
        if tribe is None:
            continue
        region = TRIBE_TO_REGION.get(tribe)
        tribe_info = state.get("tribes", {}).get(tribe)
        if tribe_info and tribe_info.get("allied_faction") in GALLIC_FACTIONS:
            fac = tribe_info["allied_faction"]
            if (count_pieces(state, region, fac, ALLY) > 0
                    and get_available(state, fac, CITADEL) > 0):
                remove_piece(state, region, fac, ALLY)
                place_piece(state, region, fac, CITADEL)

def execute_card_29(state, shaded=False):
    """Card 29: Suebi Mobilize — Remove Dispersed / Germans Phase.

    Both sides (Germanic pressure): Remove any Dispersed from both
    Suebi tribes. Place Germanic Ally at each Suebi that has none.
    Then conduct immediate Germans Phase as if Winter, but skip Rally.

    Source: Card Reference, card 29
    """
    from fs_bot.rules_consts import SUEBI_TRIBES, TRIBE_TO_REGION
    from fs_bot.commands.march import germans_phase_march
    from fs_bot.commands.raid import germans_phase_raid_region
    from fs_bot.engine.germans_battle import germans_phase_battle
    # Remove Dispersed from both Suebi tribes
    for tribe in SUEBI_TRIBES:
        region = TRIBE_TO_REGION.get(tribe)
        tribe_info = state.get("tribes", {}).get(tribe)
        if tribe_info:
            markers = state.get("markers", {})
            tribe_markers = markers.get(tribe, {})
            if MARKER_DISPERSED in tribe_markers:
                del tribe_markers[MARKER_DISPERSED]
            if MARKER_DISPERSED_GATHERING in tribe_markers:
                del tribe_markers[MARKER_DISPERSED_GATHERING]
        # Place Germanic Ally at each Suebi that has none
        if tribe_info and tribe_info.get("allied_faction") is None:
            if region and get_available(state, GERMANS, ALLY) > 0:
                place_piece(state, region, GERMANS, ALLY)
                tribe_info["allied_faction"] = GERMANS
    # Immediate Germans Phase without Rally: March, Raid, Battle
    germans_phase_march(state)
    # Raid all regions with Germanic Warbands
    for region in state["spaces"]:
        germans_phase_raid_region(state, region)
    germans_phase_battle(state)
    refresh_all_control(state)

def execute_card_30(state, shaded=False):
    """Card 30: Vercingetorix's Elite — CAPABILITY (both sides).

    Unshaded: Arverni Rally places Warbands up to Allies+Citadels
    (not Leader+1).
    Shaded: In any Battles with their Leader, Arverni pick 2 Arverni
    Warbands—they take & inflict Losses as if Legions.

    Source: Card Reference, card 30
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 30, side)

def execute_card_31(state, shaded=False):
    """Card 31: Cotuatus & Conconnetodumnus — Place Legion / Remove Allies.

    Unshaded: Place 1 Legion in Provincia.
    Tip: Legion must be placed from Legions track, not Fallen.

    Shaded: Remove 3 Allies—1 Roman, 1 Aedui, and 1 Roman or Aedui
    (not Citadels).

    Source: Card Reference, card 31
    """
    if not shaded:
        # Unshaded: Place 1 Legion in Provincia from Legions track
        if _count_on_legions_track(state) >= 1:
            place_piece(state, PROVINCIA, ROMANS, LEGION,
                        from_legions_track=True)
    else:
        # Shaded: Remove 3 Allies total: 1 Roman, 1 Aedui, 1 Roman or Aedui
        params = state.get("event_params", {})
        # Remove 1 Roman Ally
        roman_ally_region = params.get("roman_ally_region")
        if roman_ally_region is None:
            for region in state["spaces"]:
                if count_pieces(state, region, ROMANS, ALLY) > 0:
                    roman_ally_region = region
                    break
        if roman_ally_region:
            remove_piece(state, roman_ally_region, ROMANS, ALLY)
        # Remove 1 Aedui Ally
        aedui_ally_region = params.get("aedui_ally_region")
        if aedui_ally_region is None:
            for region in state["spaces"]:
                if count_pieces(state, region, AEDUI, ALLY) > 0:
                    aedui_ally_region = region
                    break
        if aedui_ally_region:
            remove_piece(state, aedui_ally_region, AEDUI, ALLY)
        # Remove 1 more Roman or Aedui Ally (third Ally)
        third_faction = params.get("third_ally_faction")
        third_region = params.get("third_ally_region")
        if third_faction is None:
            # Auto-select: try Romans first, then Aedui
            for fac in (ROMANS, AEDUI):
                for region in state["spaces"]:
                    if count_pieces(state, region, fac, ALLY) > 0:
                        third_faction = fac
                        third_region = region
                        break
                if third_faction:
                    break
        elif third_region is None:
            for region in state["spaces"]:
                if count_pieces(state, region, third_faction, ALLY) > 0:
                    third_region = region
                    break
        if third_region and third_faction:
            remove_piece(state, third_region, third_faction, ALLY)

def execute_card_32(state, shaded=False):
    """Card 32: Forced Marches — Relocate pieces freely.

    Both sides (Double time): Relocate any of your Warbands or Legions
    and Auxilia and/or Leader from any Regions other than Britannia to
    any Regions except Britannia. Pieces moved go Hidden.

    Source: Card Reference, card 32
    """
    from fs_bot.rules_consts import BRITANNIA
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    # moves: list of {"piece_type": ..., "from_region": ..., "to_region": ...,
    #                  "count": ..., "leader_name": ...}
    moves = params.get("moves", [])
    for m in moves:
        from_region = m["from_region"]
        to_region = m["to_region"]
        piece_type = m["piece_type"]
        cnt = m.get("count", 1)
        if from_region == BRITANNIA or to_region == BRITANNIA:
            continue
        if piece_type == LEADER:
            leader_name = m.get("leader_name")
            move_piece(state, from_region, to_region, faction, LEADER,
                       count=1, leader_name=leader_name)
        else:
            piece_state = m.get("piece_state")
            move_piece(state, from_region, to_region, faction, piece_type,
                       count=cnt, piece_state=piece_state)
        # Pieces moved go Hidden — flip to Hidden
        if piece_type in (AUXILIA, WARBAND):
            # Ensure moved pieces are Hidden in destination
            revealed_count = count_pieces_by_state(
                state, to_region, faction, piece_type, REVEALED)
            if revealed_count > 0:
                to_flip = min(cnt, revealed_count)
                flip_piece(state, to_region, faction, piece_type, to_flip,
                           from_state=REVEALED, to_state=HIDDEN)

def execute_card_33(state, shaded=False):
    """Card 33: Lost Eagle — Place Fallen Legion / Remove Legion permanently.

    Unshaded: Romans place 1 Fallen Legion into a Region that has a
    non-Aedui Warband and a Legion already.
    Tips: Legion must come from Fallen box, not track or map.

    Shaded: Remove 1 Fallen Legion permanently from play. This upcoming
    Senate Phase, no shift down (mark).
    Tips: Places Lost Eagle marker to prevent shift toward Adulation
    this Winter only.

    Source: Card Reference, card 33
    """
    if not shaded:
        # Unshaded: Place 1 Fallen Legion into Region with non-Aedui
        # Warband and a Legion already
        if state.get("fallen_legions", 0) < 1:
            return  # No Fallen Legions
        params = state.get("event_params", {})
        target = params.get("target_region")
        if target is None:
            # Auto-find: region with Legion and non-Aedui Warband
            for region in state["spaces"]:
                if count_pieces(state, region, ROMANS, LEGION) == 0:
                    continue
                # Check for non-Aedui Warbands
                has_non_aedui_wb = False
                for faction in (ARVERNI, BELGAE, GERMANS):
                    if count_pieces(state, region, faction, WARBAND) > 0:
                        has_non_aedui_wb = True
                        break
                if has_non_aedui_wb:
                    target = region
                    break
        if target:
            # Validate target has a Legion and a non-Aedui Warband
            if count_pieces(state, target, ROMANS, LEGION) == 0:
                return
            has_non_aedui_wb = any(
                count_pieces(state, target, fac, WARBAND) > 0
                for fac in (ARVERNI, BELGAE, GERMANS)
            )
            if not has_non_aedui_wb:
                return
            place_piece(state, target, ROMANS, LEGION, from_fallen=True)
    else:
        # Shaded: Remove 1 Fallen Legion permanently
        if state.get("fallen_legions", 0) >= 1:
            state["fallen_legions"] -= 1
            state["removed_legions"] = state.get("removed_legions", 0) + 1
        # Mark: no Senate shift down this upcoming Winter
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["lost_eagle_no_shift_down"] = True

def execute_card_34(state, shaded=False):
    """Card 34: Acco — Free Rally / Replace Allies in Carnutes & Mandubii.

    Unshaded: A Gaul or Roman free Rallies or Recruits in any 3 Regions,
    as if with Control.
    Shaded: In Carnutes and Mandubii Regions, replace all Allies with
    Arverni Allies and Citadels with Arverni Citadels.

    Source: Card Reference, card 34
    """
    from fs_bot.rules_consts import CARNUTES, MANDUBII, TRIBE_TO_REGION
    from fs_bot.map.map_data import get_tribes_in_region
    if not shaded:
        # Free Rally in 3 Regions as if with Control — deferred to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_34_free_rally"] = True
        state["event_modifiers"]["card_34_rally_regions"] = 3
    else:
        # Replace all Allies with Arverni Allies in Carnutes & Mandubii
        # Replace all Citadels with Arverni Citadels
        scenario = state["scenario"]
        for region in (CARNUTES, MANDUBII):
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state.get("tribes", {}).get(tribe)
                if not tribe_info:
                    continue
                allied_fac = tribe_info.get("allied_faction")
                if allied_fac and allied_fac != ARVERNI:
                    # Replace Ally with Arverni Ally
                    if count_pieces(state, region, allied_fac, ALLY) > 0:
                        remove_piece(state, region, allied_fac, ALLY)
                        if get_available(state, ARVERNI, ALLY) > 0:
                            place_piece(state, region, ARVERNI, ALLY)
                    tribe_info["allied_faction"] = ARVERNI
            # Replace Citadels with Arverni Citadels
            for fac in (ROMANS, AEDUI, BELGAE, GERMANS):
                cit_count = count_pieces(state, region, fac, CITADEL)
                if cit_count > 0:
                    remove_piece(state, region, fac, CITADEL, count=cit_count)
                    avail = get_available(state, ARVERNI, CITADEL)
                    to_place = min(cit_count, avail)
                    if to_place > 0:
                        place_piece(state, region, ARVERNI, CITADEL,
                                    count=to_place)

def execute_card_35(state, shaded=False):
    """Card 35: Gallic Shouts — Romans peek / Gallic Commands.

    Unshaded: Romans may look at next 2 facedown cards and either
    execute a free Limited Command or be Eligible.
    Shaded: A Gallic Faction executes 1 Command and 1 Limited Command,
    in either order, free, no Battles.

    Source: Card Reference, card 35
    """
    state.setdefault("event_modifiers", {})
    if not shaded:
        # Reveal next 2 cards to Romans + free Limited Command or Eligible
        state["event_modifiers"]["card_35_roman_peek"] = True
        state["event_modifiers"]["card_35_free_limited_command"] = True
    else:
        # Gallic Faction gets 1 Command + 1 Limited Command, free, no Battles
        state["event_modifiers"]["card_35_gallic_commands"] = True
        state["event_modifiers"]["card_35_no_battles"] = True

def execute_card_36(state, shaded=False):
    """Card 36: Morasses — Free Battle special / Gallic Ambush + March.

    Unshaded: Free Battle against a Gallic Faction in 1 Region.
    No Retreat, Counterattack, or Citadel effect. Attackers Hidden.
    Shaded: A Gallic Faction free Battles with Ambush anywhere,
    then free Marches.

    Source: Card Reference, card 36
    """
    state.setdefault("event_modifiers", {})
    if not shaded:
        state["event_modifiers"]["card_36_free_battle"] = True
        state["event_modifiers"]["card_36_no_retreat"] = True
        state["event_modifiers"]["card_36_no_counterattack"] = True
        state["event_modifiers"]["card_36_no_citadel_effect"] = True
        state["event_modifiers"]["card_36_attackers_hidden"] = True
    else:
        state["event_modifiers"]["card_36_gallic_ambush_battle"] = True
        state["event_modifiers"]["card_36_free_march"] = True

def execute_card_37(state, shaded=False):
    """Card 37: Boii — Aedui/Roman placement / Replace Aedui Allies.

    Unshaded: Aedui or Romans place 2 Allies and 2 Warbands or Auxilia
    at or adjacent to Aedui Control.
    Shaded: At or adjacent to Arverni Control, replace 1-2 Aedui Allies
    (not Citadels) with Arverni Allies.

    Source: Card Reference, card 37
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    from fs_bot.map.map_data import get_adjacent, get_tribes_in_region
    params = state.get("event_params", {})
    if not shaded:
        # Place 2 Allies + 2 Warbands/Auxilia at/adjacent to Aedui Control
        faction = params.get("place_faction", AEDUI)
        placements = params.get("placements", [])
        for p in placements:
            region = p["region"]
            piece_type = p["piece_type"]
            cnt = p.get("count", 1)
            if piece_type == ALLY:
                tribe = p.get("tribe")
                tribe_info = state.get("tribes", {}).get(tribe)
                if tribe_info and tribe_info.get("allied_faction") is None:
                    if get_available(state, faction, ALLY) > 0:
                        place_piece(state, region, faction, ALLY)
                        tribe_info["allied_faction"] = faction
            elif piece_type in (WARBAND, AUXILIA):
                if get_available(state, faction, piece_type) >= cnt:
                    place_piece(state, region, faction, piece_type, count=cnt)
    else:
        # Replace 1-2 Aedui Allies with Arverni Allies at/adjacent Arverni Control
        replacements = params.get("replacements", [])
        for r in replacements:
            tribe = r["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            tribe_info = state.get("tribes", {}).get(tribe)
            if (tribe_info and tribe_info.get("allied_faction") == AEDUI
                    and region):
                if count_pieces(state, region, AEDUI, ALLY) > 0:
                    remove_piece(state, region, AEDUI, ALLY)
                    if get_available(state, ARVERNI, ALLY) > 0:
                        place_piece(state, region, ARVERNI, ALLY)
                    tribe_info["allied_faction"] = ARVERNI

def execute_card_38(state, shaded=False):
    """Card 38: Diviciacus — CAPABILITY (both sides).

    Unshaded: If Aedui and Romans agree, their Command or defense
    in Battle may treat Aedui Warbands or Auxilia where together
    as the other.
    Shaded: Romans and Aedui may not transfer Resources to one another.

    Source: Card Reference, card 38
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 38, side)

def execute_card_39(state, shaded=False):
    """Card 39: River Commerce — CAPABILITY (both sides).

    Unshaded: Aedui Allies and Citadels in Supply Lines always yield
    +2 Resources each in Trade.
    Shaded: Trade is maximum 1 Region.

    Source: Card Reference, card 39
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 39, side)

def execute_card_40(state, shaded=False):
    """Card 40: Alpine Tribes — Place pieces near Cisalpina / Drain Roman Resources.

    Unshaded: Place up to any 3 Warbands, 2 Auxilia, or 1 Ally in each
    Region adjacent to Cisalpina. Gain +4 Resources.
    Shaded: For each Region adjacent to Cisalpina that is not under Roman
    Control, -5 Roman Resources. Stay Eligible.

    Source: Card Reference, card 40
    """
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    scenario = state["scenario"]
    adj_cisalpina = get_adjacent(CISALPINA, scenario)
    if not shaded:
        # Place pieces in each Region adjacent to Cisalpina
        placements = params.get("placements", [])
        for p in placements:
            region = p["region"]
            piece_type = p["piece_type"]
            cnt = p.get("count", 1)
            pfac = p.get("faction", faction)
            if region not in adj_cisalpina:
                continue
            if piece_type == ALLY:
                tribe = p.get("tribe")
                tribe_info = state.get("tribes", {}).get(tribe)
                if tribe_info and tribe_info.get("allied_faction") is None:
                    if get_available(state, pfac, ALLY) > 0:
                        place_piece(state, region, pfac, ALLY)
                        tribe_info["allied_faction"] = pfac
            else:
                avail = get_available(state, pfac, piece_type)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, pfac, piece_type, count=to_place)
        # Gain +4 Resources
        if faction:
            _cap_resources(state, faction, 4)
    else:
        # -5 Roman Resources per non-Roman-Controlled adjacent Region
        non_roman_count = 0
        for region in adj_cisalpina:
            if not is_controlled_by(state, region, ROMANS):
                non_roman_count += 1
        _cap_resources(state, ROMANS, -5 * non_roman_count)
        # Stay Eligible
        if faction:
            state["eligibility"][faction] = ELIGIBLE

def execute_card_41(state, shaded=False):
    """Card 41: Avaricum — Place pieces near Avaricum / gain Resources.

    Both sides: If Avaricum is your Ally or Citadel, do any or all
    within 1 Region: place up to 2 Allies; replace 1 Ally with Citadel;
    place 1 Fort; then +1 Resource per Ally, Citadel, Fort there.

    Source: Card Reference, card 41
    """
    from fs_bot.rules_consts import (
        CITY_AVARICUM, CITY_TO_TRIBE, TRIBE_TO_REGION, BITURIGES,
    )
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    scenario = state["scenario"]
    tribe = CITY_TO_TRIBE.get(CITY_AVARICUM)
    tribe_info = state.get("tribes", {}).get(tribe)
    if not tribe_info or tribe_info.get("allied_faction") != faction:
        return
    # Regions within 1 of Avaricum (Bituriges + adjacent)
    target_regions = [BITURIGES] + list(get_adjacent(BITURIGES, scenario))
    # Ally placements
    ally_placements = params.get("ally_placements", [])
    for p in ally_placements:
        t = p["tribe"]
        r = TRIBE_TO_REGION.get(t)
        if r in target_regions:
            t_info = state.get("tribes", {}).get(t)
            if t_info and t_info.get("allied_faction") is None:
                if get_available(state, faction, ALLY) > 0:
                    place_piece(state, r, faction, ALLY)
                    t_info["allied_faction"] = faction
    # Citadel upgrade
    citadel_tribe = params.get("citadel_upgrade_tribe")
    if citadel_tribe:
        r = TRIBE_TO_REGION.get(citadel_tribe)
        if r in target_regions:
            t_info = state.get("tribes", {}).get(citadel_tribe)
            if (t_info and t_info.get("allied_faction") == faction
                    and count_pieces(state, r, faction, ALLY) > 0
                    and get_available(state, faction, CITADEL) > 0):
                remove_piece(state, r, faction, ALLY)
                place_piece(state, r, faction, CITADEL)
    # Fort placement (Romans only)
    fort_region = params.get("fort_region")
    if fort_region and fort_region in target_regions and faction == ROMANS:
        if get_available(state, ROMANS, FORT) > 0:
            place_piece(state, fort_region, ROMANS, FORT)
    # +1 Resource per Ally, Citadel, Fort in those regions
    resource_gain = 0
    for r in target_regions:
        resource_gain += count_pieces(state, r, faction, ALLY)
        resource_gain += count_pieces(state, r, faction, CITADEL)
        if faction == ROMANS:
            resource_gain += count_pieces(state, r, ROMANS, FORT)
    if faction:
        _cap_resources(state, faction, resource_gain)

def execute_card_42(state, shaded=False):
    """Card 42: Roman Wine — Remove Allies under Roman Control.

    Unshaded: Remove up to 4 Allied Tribes (not Citadels) under Roman
    Control, or up to 2 adjacent to Roman Control.
    Shaded: Remove 1-3 Roman or Aedui Allies (not Citadels) from
    Roman-Aedui Supply Lines.

    Source: Card Reference, card 42
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        # Remove Allies under or adjacent to Roman Control
        removals = params.get("removals", [])
        for r in removals:
            tribe = r["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction") and region:
                fac = tribe_info["allied_faction"]
                if count_pieces(state, region, fac, ALLY) > 0:
                    remove_piece(state, region, fac, ALLY)
                tribe_info["allied_faction"] = None
    else:
        # Remove 1-3 Roman or Aedui Allies from Supply Lines
        removals = params.get("removals", [])
        for r in removals:
            tribe = r["tribe"]
            fac = r.get("faction", ROMANS)
            region = TRIBE_TO_REGION.get(tribe)
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction") == fac and region:
                if count_pieces(state, region, fac, ALLY) > 0:
                    remove_piece(state, region, fac, ALLY)
                tribe_info["allied_faction"] = None

def execute_card_43(state, shaded=False):
    """Card 43: Convictolitavis — CAPABILITY (both sides).

    Unshaded: Suborn is maximum 2 Regions.
    Shaded: Resource costs of Aedui Commands are doubled.

    Source: Card Reference, card 43
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 43, side)

def execute_card_44(state, shaded=False):
    """Card 44: Dumnorix Loyalists — Replace Warbands / Replace Auxilia.

    Unshaded: Replace any 4 Warbands with Auxilia or Aedui Warbands.
    They free Scout (as if Auxilia).
    Shaded: Replace any 3 Auxilia or Aedui Warbands total with any
    Warbands. They all free Raid.

    Source: Card Reference, card 44
    """
    params = state.get("event_params", {})
    if not shaded:
        # Replace 4 Warbands with Auxilia or Aedui Warbands
        replacements = params.get("replacements", [])
        for r in replacements:
            region = r["region"]
            from_faction = r["from_faction"]
            to_type = r.get("to_type", AUXILIA)
            to_faction = r.get("to_faction", ROMANS if to_type == AUXILIA else AEDUI)
            ps = r.get("piece_state", HIDDEN)
            if count_pieces_by_state(state, region, from_faction, WARBAND, ps) > 0:
                remove_piece(state, region, from_faction, WARBAND, piece_state=ps)
                if get_available(state, to_faction, to_type) > 0:
                    place_piece(state, region, to_faction, to_type)
        # Free Scout deferred to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_44_free_scout"] = True
    else:
        # Replace 3 Auxilia/Aedui Warbands with any Warbands
        replacements = params.get("replacements", [])
        for r in replacements:
            region = r["region"]
            from_faction = r["from_faction"]
            from_type = r.get("from_type", AUXILIA)
            to_faction = r.get("to_faction")
            if from_type == AUXILIA:
                if count_pieces(state, region, from_faction, AUXILIA) > 0:
                    remove_piece(state, region, from_faction, AUXILIA)
            elif from_type == WARBAND:
                ps = r.get("piece_state", HIDDEN)
                if count_pieces_by_state(state, region, AEDUI, WARBAND, ps) > 0:
                    remove_piece(state, region, AEDUI, WARBAND, piece_state=ps)
            if to_faction and get_available(state, to_faction, WARBAND) > 0:
                place_piece(state, region, to_faction, WARBAND)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_44_free_raid"] = True

def execute_card_45(state, shaded=False):
    """Card 45: Litaviccus — Replace Arverni Warbands / Battle Romans.

    Unshaded: In each of 2 Regions, replace up to 2 Arverni Warbands
    with Aedui Warbands. 4 Arverni Resources to Aedui.
    Shaded: Free Battle against Romans in 1 Region, using Aedui pieces
    as your own, Ambushing if able.

    Source: Card Reference, card 45
    """
    params = state.get("event_params", {})
    if not shaded:
        # Replace Arverni Warbands with Aedui Warbands in 2 Regions
        regions = params.get("regions", [])
        for r_info in regions:
            region = r_info["region"]
            cnt = min(r_info.get("count", 2), 2)
            for _ in range(cnt):
                # Try Hidden first, then Revealed
                removed = False
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, ARVERNI, WARBAND, ps) > 0:
                        remove_piece(state, region, ARVERNI, WARBAND, piece_state=ps)
                        removed = True
                        break
                if removed and get_available(state, AEDUI, WARBAND) > 0:
                    place_piece(state, region, AEDUI, WARBAND)
        # Transfer 4 Resources from Arverni to Aedui
        transfer = min(state["resources"].get(ARVERNI, 0), 4)
        _cap_resources(state, ARVERNI, -transfer)
        _cap_resources(state, AEDUI, transfer)
    else:
        # Free Battle against Romans using Aedui pieces, Ambush if able
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_45_battle_romans"] = True
        state["event_modifiers"]["card_45_use_aedui"] = True
        state["event_modifiers"]["card_45_ambush_if_able"] = True

def execute_card_46(state, shaded=False):
    """Card 46: Celtic Rites — Gallic Factions lose Resources / Free Command.

    Unshaded: Select 1+ Gallic Factions. Each loses 3 Resources and is
    Ineligible through next card.
    Shaded: A Gallic Faction executes a free Command (in multiple
    Regions). Stay Eligible.

    Source: Card Reference, card 46
    """
    params = state.get("event_params", {})
    if not shaded:
        target_factions = params.get("target_factions", [])
        for fac in target_factions:
            if fac in GALLIC_FACTIONS:
                _cap_resources(state, fac, -3)
                state["eligibility"][fac] = INELIGIBLE
    else:
        # Free Command for a Gallic Faction + Stay Eligible
        faction = state.get("executing_faction")
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_46_free_command"] = True
        if faction:
            state["eligibility"][faction] = ELIGIBLE

def execute_card_47(state, shaded=False):
    """Card 47: Chieftains' Council — Multi-faction peek and action.

    Both sides: Select a Region with at least 2 non-German Factions'
    pieces. Two or more player Factions there look at next 2 facedown
    cards, then may either execute a free Limited Command or become
    Eligible.

    Source: Card Reference, card 47
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_47_council"] = True
    # Region selection and faction actions deferred to bot/CLI layer

def execute_card_48(state, shaded=False):
    """Card 48: Druids — Gallic Factions execute free Commands.

    Both sides: Select 1-3 Gallic Factions. In initiative order, each
    executes a free Limited Command that may add a free Special Ability.
    Become Eligible after this card.

    Source: Card Reference, card 48
    """
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_48_druids"] = True
    target_factions = params.get("target_factions", [])
    state["event_modifiers"]["card_48_target_factions"] = target_factions
    # Executing faction stays Eligible
    if faction:
        state["eligibility"][faction] = ELIGIBLE

def execute_card_49(state, shaded=False):
    """Card 49: Drought — Halve Resources, Devastate, remove pieces.

    Both unshaded and shaded (same effect):
    Each Faction drops to half its current Resources (rounded down).
    Place 1 Devastated marker. Each Faction then removes 1 of its
    pieces from each Devastated Region (Legions to Fallen; German
    Warbands before German Allied Tribes).

    Tips: Executing Faction places Devastated marker in any one Region
    without one. Each Faction chooses which piece to remove. Romans
    remove Legions to Fallen. Germans avoid removing Allies if possible.

    Source: Card Reference, card 49
    """
    # Step 1: Halve all faction Resources (rounded down)
    for faction in FACTIONS:
        if faction in state["resources"]:
            state["resources"][faction] = state["resources"][faction] // 2

    # Step 2: Place 1 Devastated marker in a Region without one
    params = state.get("event_params", {})
    devastate_region = params.get("devastate_region")
    if devastate_region is None:
        # Auto-select: first region without Devastated marker
        for region in state["spaces"]:
            markers = state.get("markers", {}).get(region, set())
            if MARKER_DEVASTATED not in markers:
                devastate_region = region
                break
    if devastate_region:
        state.setdefault("markers", {})
        state["markers"].setdefault(devastate_region, set())
        state["markers"][devastate_region].add(MARKER_DEVASTATED)

    # Step 3: Each Faction removes 1 piece from each Devastated Region
    for region in state["spaces"]:
        markers = state.get("markers", {}).get(region, set())
        if MARKER_DEVASTATED not in markers:
            continue
        for faction in FACTIONS:
            if count_pieces(state, region, faction) == 0:
                continue
            # Choose which piece to remove (per Tips: each Faction
            # chooses; bot defaults prioritize least-valuable first)
            # Use event_params piece_removal overrides if specified
            removal_overrides = params.get("piece_removals", {})
            override_key = (faction, region)
            if override_key in removal_overrides:
                pt = removal_overrides[override_key]
                if pt == LEGION:
                    remove_piece(state, region, ROMANS, LEGION,
                                 to_fallen=True)
                elif pt == LEADER:
                    remove_piece(state, region, faction, LEADER)
                elif pt in (AUXILIA, WARBAND):
                    remove_piece(state, region, faction, pt)
                else:
                    remove_piece(state, region, faction, pt)
                continue
            # Default bot removal priority:
            # Romans: Legion (to Fallen) > Auxilia > Fort > Ally > Leader
            if faction == ROMANS:
                if count_pieces(state, region, ROMANS, LEGION) > 0:
                    remove_piece(state, region, ROMANS, LEGION,
                                 to_fallen=True)
                elif count_pieces(state, region, ROMANS, AUXILIA) > 0:
                    remove_piece(state, region, ROMANS, AUXILIA)
                elif count_pieces(state, region, ROMANS, FORT) > 0:
                    try:
                        remove_piece(state, region, ROMANS, FORT)
                    except PieceError:
                        pass  # Permanent Fort in Provincia
                elif count_pieces(state, region, ROMANS, ALLY) > 0:
                    remove_piece(state, region, ROMANS, ALLY)
                elif get_leader_in_region(state, region, ROMANS) is not None:
                    remove_piece(state, region, ROMANS, LEADER)
            elif faction == GERMANS:
                # Germans: Warbands before Allied Tribes per Tips
                if count_pieces(state, region, GERMANS, WARBAND) > 0:
                    remove_piece(state, region, GERMANS, WARBAND)
                elif count_pieces(state, region, GERMANS, ALLY) > 0:
                    remove_piece(state, region, GERMANS, ALLY)
            else:
                # Gallic factions: Warband > Ally > Citadel > Leader
                if count_pieces(state, region, faction, WARBAND) > 0:
                    remove_piece(state, region, faction, WARBAND)
                elif count_pieces(state, region, faction, ALLY) > 0:
                    remove_piece(state, region, faction, ALLY)
                elif count_pieces(state, region, faction, CITADEL) > 0:
                    remove_piece(state, region, faction, CITADEL)
                elif get_leader_in_region(
                        state, region, faction) is not None:
                    remove_piece(state, region, faction, LEADER)

def execute_card_50(state, shaded=False):
    """Card 50: Shifting Loyalties — Remove a Capability.

    Both unshaded and shaded (same effect):
    Choose 1 Capability of any Faction. Remove it from play.
    Tip: Can remove disadvantageous Capability from friendly or
    advantageous from foe.

    Source: Card Reference, card 50
    """
    params = state.get("event_params", {})
    target_capability = params.get("target_capability")
    if target_capability is not None:
        deactivate_capability(state, target_capability)
    else:
        # Auto-select: remove first active capability
        active = state.get("capabilities", {})
        if active:
            first_cap = next(iter(active))
            deactivate_capability(state, first_cap)

def execute_card_51(state, shaded=False):
    """Card 51: Surus — Replace Warbands in Treveri area.

    Unshaded: Replace any 4 Warbands in a Region within 1 of Treveri
    with Aedui Warbands. Then Aedui execute a free Command.
    Shaded: In a Region within 1 of Treveri, replace up to 4 Aedui
    Warbands with German March, Raid, or Battle with them.

    Source: Card Reference, card 51
    """
    from fs_bot.rules_consts import TREVERI
    params = state.get("event_params", {})
    if not shaded:
        # Replace 4 Warbands with Aedui Warbands in region within 1 of Treveri
        region = params.get("region")
        replacements = params.get("replacements", [])
        for r in replacements:
            reg = r.get("region", region)
            from_fac = r["from_faction"]
            ps = r.get("piece_state", HIDDEN)
            if count_pieces_by_state(state, reg, from_fac, WARBAND, ps) > 0:
                remove_piece(state, reg, from_fac, WARBAND, piece_state=ps)
                if get_available(state, AEDUI, WARBAND) > 0:
                    place_piece(state, reg, AEDUI, WARBAND)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_51_aedui_free_command"] = True
    else:
        # Replace up to 4 Aedui Warbands with German pieces + action
        region = params.get("region")
        count = params.get("count", 4)
        if region:
            replaced = 0
            for _ in range(count):
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, AEDUI, WARBAND, ps) > 0:
                        remove_piece(state, region, AEDUI, WARBAND, piece_state=ps)
                        if get_available(state, GERMANS, WARBAND) > 0:
                            place_piece(state, region, GERMANS, WARBAND)
                        replaced += 1
                        break
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_51_german_action"] = True
        if region:
            state["event_modifiers"]["card_51_action_region"] = region

def execute_card_52(state, shaded=False):
    """Card 52: Assembly of Gaul — Drain Resources / Free Command.

    Unshaded: If Carnutes are Roman Ally, Subdued, or Dispersed, drop
    1+ Gallic Factions' Resources each -8.
    Shaded: Faction Controlling Carnutes Region executes a Command
    that may add 2 Special Abilities, free.

    Source: Card Reference, card 52
    """
    from fs_bot.rules_consts import CARNUTES, TRIBE_CARNUTES
    params = state.get("event_params", {})
    if not shaded:
        # Check Carnutes tribe status
        tribe_info = state.get("tribes", {}).get(TRIBE_CARNUTES)
        if tribe_info:
            allied_fac = tribe_info.get("allied_faction")
            markers = state.get("markers", {}).get(TRIBE_CARNUTES, {})
            is_roman_ally = (allied_fac == ROMANS)
            is_subdued = (allied_fac is None and MARKER_DISPERSED not in markers)
            is_dispersed = (MARKER_DISPERSED in markers)
            if is_roman_ally or is_subdued or is_dispersed:
                target_factions = params.get("target_factions", [])
                for fac in target_factions:
                    if fac in GALLIC_FACTIONS:
                        _cap_resources(state, fac, -8)
    else:
        # Faction Controlling Carnutes Region gets free Command + 2 SAs
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_52_free_command_sa"] = True
        state["event_modifiers"]["card_52_special_abilities"] = 2

def execute_card_53(state, shaded=False):
    """Card 53: Consuetudine — Germanic Warbands Hidden + Germans Phase.

    Both sides: All Germanic Warbands to Hidden. Then conduct immediate
    Germans Phase as if Winter, but skip March, and all Germans Ambush.

    Source: Card Reference, card 53
    """
    from fs_bot.commands.rally import germans_phase_rally
    from fs_bot.commands.raid import germans_phase_raid_region
    from fs_bot.engine.germans_battle import germans_phase_battle
    # Flip all Germanic Warbands to Hidden
    for region in state["spaces"]:
        revealed = count_pieces_by_state(state, region, GERMANS, WARBAND, REVEALED)
        if revealed > 0:
            flip_piece(state, region, GERMANS, WARBAND, revealed,
                       from_state=REVEALED, to_state=HIDDEN)
    # Germans Phase without March: Rally, Raid, Battle with Ambush
    germans_phase_rally(state)
    for region in list(state["spaces"]):
        germans_phase_raid_region(state, region)
    # Battle with forced Ambush
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_53_german_ambush"] = True
    germans_phase_battle(state)
    refresh_all_control(state)

def execute_card_54(state, shaded=False):
    """Card 54: Joined Ranks — Free March + multi-faction Battle.

    Both sides: Executing Faction may free March a group of up to 8
    pieces to a Region with 2+ other Gallic/Roman Factions. Then
    executing Faction and a 2nd player Faction may each free Battle
    against a 3rd. First Battle: no Retreat.

    Source: Card Reference, card 54
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_54_joined_ranks"] = True
    state["event_modifiers"]["card_54_march_limit"] = 8
    state["event_modifiers"]["card_54_no_retreat_first"] = True

def execute_card_55(state, shaded=False):
    """Card 55: Commius — CAPABILITY (both sides).

    Unshaded: Belgica Regions for Roman Recruit count as Roman
    Controlled and +1 Roman Ally.
    Shaded: Belgic Rally costs 0 and treats any Region with Belgic
    pieces as Belgic Controlled.

    Source: Card Reference, card 55
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 55, side)

def execute_card_56(state, shaded=False):
    """Card 56: Flight of Ambiorix — Remove or Place Ambiorix.

    Unshaded: If Ambiorix is in a Roman Controlled Region, or if
    Belgic victory < 10, remove Ambiorix.
    Shaded: If Ambiorix is not on the map, place Belgic Leader within
    1 Region of Germania, symbol up (as Ambiorix).

    Source: Card Reference, card 56
    """
    from fs_bot.rules_consts import GERMANIA_REGIONS
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        # Remove Ambiorix if in Roman Controlled Region or Belgic victory < 10
        leader_loc = find_leader(state, AMBIORIX)
        if leader_loc is None:
            return
        in_roman_control = is_controlled_by(state, leader_loc, ROMANS)
        # Check Belgic victory value (Control + Allies + Citadels)
        belgic_victory = 0
        for region in state["spaces"]:
            if is_controlled_by(state, region, BELGAE):
                from fs_bot.rules_consts import CONTROL_VALUES
                belgic_victory += CONTROL_VALUES.get(region, 0)
        for tribe, t_info in state.get("tribes", {}).items():
            if t_info.get("allied_faction") == BELGAE:
                belgic_victory += 1
        for region in state["spaces"]:
            belgic_victory += count_pieces(state, region, BELGAE, CITADEL)
        if in_roman_control or belgic_victory < 10:
            remove_piece(state, leader_loc, BELGAE, LEADER)
    else:
        # Place Ambiorix within 1 Region of Germania
        leader_loc = find_leader(state, AMBIORIX)
        if leader_loc is not None:
            return  # Already on map
        target_region = params.get("target_region")
        if target_region is None:
            # Default: first Germania region
            for g_region in GERMANIA_REGIONS:
                target_region = g_region
                break
        if target_region and get_available(state, BELGAE, LEADER) > 0:
            place_piece(state, target_region, BELGAE, LEADER,
                        leader_name=AMBIORIX)

def execute_card_57(state, shaded=False):
    """Card 57: Land of Mist and Mystery — March to Britannia.

    Unshaded: A non-German Faction may free March into Britannia, add
    any free Special Ability there, then +4 Resources if in Britannia.
    Shaded: Remove an Ally or Dispersed from Britannia. Place any 1
    Gallic Ally and up to 4 Warbands there.

    Source: Card Reference, card 57
    """
    from fs_bot.rules_consts import BRITANNIA, TRIBE_TO_REGION
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    if not shaded:
        # Free March into Britannia + SA + Resources — deferred to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_57_march_britannia"] = True
        state["event_modifiers"]["card_57_free_sa"] = True
        # +4 Resources if faction has pieces in Britannia
        if faction:
            _cap_resources(state, faction, 4)
    else:
        # Remove Ally or Dispersed from Britannia
        removal = params.get("removal")
        if removal:
            if removal.get("type") == "ally":
                tribe = removal.get("tribe")
                tribe_info = state.get("tribes", {}).get(tribe)
                if tribe_info and tribe_info.get("allied_faction"):
                    fac = tribe_info["allied_faction"]
                    if count_pieces(state, BRITANNIA, fac, ALLY) > 0:
                        remove_piece(state, BRITANNIA, fac, ALLY)
                    tribe_info["allied_faction"] = None
            elif removal.get("type") == "dispersed":
                tribe = removal.get("tribe")
                markers = state.get("markers", {})
                if tribe in markers and MARKER_DISPERSED in markers[tribe]:
                    del markers[tribe][MARKER_DISPERSED]
        # Place 1 Gallic Ally and up to 4 Warbands
        ally_faction = params.get("ally_faction")
        ally_tribe = params.get("ally_tribe")
        if ally_faction and ally_tribe:
            tribe_info = state.get("tribes", {}).get(ally_tribe)
            if tribe_info and get_available(state, ally_faction, ALLY) > 0:
                place_piece(state, BRITANNIA, ally_faction, ALLY)
                tribe_info["allied_faction"] = ally_faction
        wb_faction = params.get("warband_faction")
        wb_count = params.get("warband_count", 0)
        if wb_faction and wb_count > 0:
            avail = get_available(state, wb_faction, WARBAND)
            to_place = min(wb_count, avail, 4)
            if to_place > 0:
                place_piece(state, BRITANNIA, wb_faction, WARBAND,
                            count=to_place)

def execute_card_58(state, shaded=False):
    """Card 58: Aduatuca — Remove Warbands at Fort / German Battle.

    Unshaded: Remove 9 Belgic and/or Germanic Warbands from a Region
    with a Fort.
    Shaded: March Germans to 1 Region with a Fort. They Ambush Romans
    there, 1 Loss per 2 Warbands.

    Source: Card Reference, card 58
    """
    params = state.get("event_params", {})
    if not shaded:
        region = params.get("region")
        if region is None:
            return
        removals = params.get("removals", [])
        total_removed = 0
        for r in removals:
            fac = r.get("faction")
            cnt = r.get("count", 1)
            if fac not in (BELGAE, GERMANS):
                continue
            for _ in range(cnt):
                if total_removed >= 9:
                    break
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, fac, WARBAND, ps) > 0:
                        remove_piece(state, region, fac, WARBAND, piece_state=ps)
                        total_removed += 1
                        break
    else:
        # German March to Fort region + Ambush, 1 Loss per 2 Warbands
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_58_german_march_battle"] = True
        state["event_modifiers"]["card_58_loss_per_2_warbands"] = True

def execute_card_59(state, shaded=False):
    """Card 59: Germanic Horse — CAPABILITY (both sides).

    Unshaded: Romans may inflict 1 Loss per Auxilia (not 1/2) in
    1 Region per Battle Command.
    Shaded: If Gallic, take this card. Each Battle Command, you double
    enemy's Losses in 1 Region unless Defender with Fort/Citadel.

    Source: Card Reference, card 59
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 59, side)

def execute_card_60(state, shaded=False):
    """Card 60: Indutiomarus — Remove Belgic pieces / Place Belgic+German.

    Unshaded: Remove 6 Belgic Warbands and/or Allies (not Citadels)
    from Treveri or 1 Region adjacent to it.
    Shaded: Remove any Ally or marker from Treveri and Ubii. Place
    Belgic Ally, 2 Belgic and 1 German Warband at each.

    Source: Card Reference, card 60
    """
    from fs_bot.rules_consts import TREVERI, UBII, TRIBE_TREVERI, TRIBE_UBII
    params = state.get("event_params", {})
    if not shaded:
        region = params.get("region", TREVERI)
        removals = params.get("removals", [])
        total = 0
        for r in removals:
            if total >= 6:
                break
            rtype = r.get("type", WARBAND)
            if rtype == ALLY:
                tribe = r.get("tribe")
                tribe_info = state.get("tribes", {}).get(tribe)
                if tribe_info and tribe_info.get("allied_faction") == BELGAE:
                    if count_pieces(state, region, BELGAE, ALLY) > 0:
                        remove_piece(state, region, BELGAE, ALLY)
                        tribe_info["allied_faction"] = None
                        total += 1
            else:
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, BELGAE, WARBAND, ps) > 0:
                        remove_piece(state, region, BELGAE, WARBAND, piece_state=ps)
                        total += 1
                        break
    else:
        # Remove Ally/marker from Treveri and Ubii, place pieces
        for region, tribe in ((TREVERI, TRIBE_TREVERI), (UBII, TRIBE_UBII)):
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction"):
                fac = tribe_info["allied_faction"]
                if count_pieces(state, region, fac, ALLY) > 0:
                    remove_piece(state, region, fac, ALLY)
                tribe_info["allied_faction"] = None
            # Remove Dispersed marker if present
            markers = state.get("markers", {})
            if tribe in markers:
                markers[tribe].pop(MARKER_DISPERSED, None)
                markers[tribe].pop(MARKER_DISPERSED_GATHERING, None)
            # Place Belgic Ally
            if tribe_info and get_available(state, BELGAE, ALLY) > 0:
                place_piece(state, region, BELGAE, ALLY)
                tribe_info["allied_faction"] = BELGAE
            # Place 2 Belgic Warbands
            avail_b = get_available(state, BELGAE, WARBAND)
            to_place_b = min(2, avail_b)
            if to_place_b > 0:
                place_piece(state, region, BELGAE, WARBAND, count=to_place_b)
            # Place 1 German Warband
            if get_available(state, GERMANS, WARBAND) > 0:
                place_piece(state, region, GERMANS, WARBAND)

def execute_card_61(state, shaded=False):
    """Card 61: Catuvolcus — Remove Allies + Warbands / Place Belgic Allies.

    Unshaded: Remove 1+ Allied Tribes of same Faction in Nervii Region
    and 5 Warbands there.
    Shaded: Place Belgic Allies at Nervii and Eburones, replacing any
    Allies or Dispersed there. Add +6 Belgic Resources.

    Source: Card Reference, card 61
    """
    from fs_bot.rules_consts import NERVII, TRIBE_NERVII, TRIBE_EBURONES
    params = state.get("event_params", {})
    if not shaded:
        # Remove Allies of same Faction + 5 Warbands in Nervii
        ally_removals = params.get("ally_removals", [])
        for tribe in ally_removals:
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction"):
                fac = tribe_info["allied_faction"]
                if count_pieces(state, NERVII, fac, ALLY) > 0:
                    remove_piece(state, NERVII, fac, ALLY)
                tribe_info["allied_faction"] = None
        # Remove 5 Warbands (any faction)
        wb_removals = params.get("warband_removals", [])
        removed = 0
        for r in wb_removals:
            if removed >= 5:
                break
            fac = r.get("faction")
            cnt = r.get("count", 1)
            for _ in range(min(cnt, 5 - removed)):
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, NERVII, fac, WARBAND, ps) > 0:
                        remove_piece(state, NERVII, fac, WARBAND, piece_state=ps)
                        removed += 1
                        break
    else:
        # Place Belgic Allies at Nervii and Eburones, replacing existing
        for tribe in (TRIBE_NERVII, TRIBE_EBURONES):
            tribe_info = state.get("tribes", {}).get(tribe)
            if not tribe_info:
                continue
            region = NERVII  # Both tribes are in Nervii region
            # Remove existing Ally
            if tribe_info.get("allied_faction"):
                old_fac = tribe_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                tribe_info["allied_faction"] = None
            # Remove Dispersed marker
            markers = state.get("markers", {})
            if tribe in markers:
                markers[tribe].pop(MARKER_DISPERSED, None)
                markers[tribe].pop(MARKER_DISPERSED_GATHERING, None)
            # Place Belgic Ally
            if get_available(state, BELGAE, ALLY) > 0:
                place_piece(state, region, BELGAE, ALLY)
                tribe_info["allied_faction"] = BELGAE
        # +6 Belgic Resources
        _cap_resources(state, BELGAE, 6)

def execute_card_62(state, shaded=False):
    """Card 62: War Fleet — Move pieces among coastal Regions.

    Both sides: Move any of your Warbands, Auxilia, Legions, or Leaders
    among Arverni Region, Pictones, and Regions within 1 of Britannia.
    Then execute a free Command in 1 of those Regions.

    Source: Card Reference, card 62
    """
    # Complex multi-step: movement + free Command — defer to caller
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_62_war_fleet"] = True
    # Piece movements handled via event_params by bot/CLI layer
    params = state.get("event_params", {})
    moves = params.get("moves", [])
    faction = state.get("executing_faction")
    for m in moves:
        from_region = m["from_region"]
        to_region = m["to_region"]
        piece_type = m["piece_type"]
        cnt = m.get("count", 1)
        if piece_type == LEADER:
            leader_name = m.get("leader_name")
            move_piece(state, from_region, to_region, faction, LEADER,
                       count=1, leader_name=leader_name)
        else:
            ps = m.get("piece_state")
            move_piece(state, from_region, to_region, faction, piece_type,
                       count=cnt, piece_state=ps)

def execute_card_63(state, shaded=False):
    """Card 63: Winter Campaign — CAPABILITY (both sides).

    Unshaded: Romans pay costs of Quarters only in Devastated Regions.
    Shaded: Place this card near a Gallic Faction. After each Harvest,
    it may do any 2 Commands and/or Special Abilities (paying costs).

    Source: Card Reference, card 63
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 63, side)

def execute_card_64(state, shaded=False):
    """Card 64: Correus — Replace Belgic pieces / Remove+Rally Belgae.

    Unshaded: Replace up to 8 Belgic Allies plus Warbands in Atrebates
    Region with yours (Auxilia for Warbands).
    Shaded: Remove 2 Allies from Atrebates. Belgae place up to 2 Allies
    there, then free Rally in 1 Belgica Region.

    Source: Card Reference, card 64
    """
    from fs_bot.rules_consts import ATREBATES, TRIBE_TO_REGION
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    if not shaded:
        # Replace up to 8 Belgic pieces in Atrebates
        replacements = params.get("replacements", [])
        for r in replacements:
            orig_type = r.get("from_type")
            if orig_type == ALLY:
                tribe = r.get("tribe")
                tribe_info = state.get("tribes", {}).get(tribe)
                if tribe_info and tribe_info.get("allied_faction") == BELGAE:
                    if count_pieces(state, ATREBATES, BELGAE, ALLY) > 0:
                        remove_piece(state, ATREBATES, BELGAE, ALLY)
                        if faction and get_available(state, faction, ALLY) > 0:
                            place_piece(state, ATREBATES, faction, ALLY)
                            tribe_info["allied_faction"] = faction
                        else:
                            tribe_info["allied_faction"] = None
            elif orig_type == WARBAND:
                ps = r.get("piece_state", HIDDEN)
                if count_pieces_by_state(state, ATREBATES, BELGAE, WARBAND, ps) > 0:
                    remove_piece(state, ATREBATES, BELGAE, WARBAND, piece_state=ps)
                    # Replace with Auxilia
                    if faction and get_available(state, faction, AUXILIA) > 0:
                        place_piece(state, ATREBATES, faction, AUXILIA)
    else:
        # Remove 2 Allies from Atrebates
        ally_removals = params.get("ally_removals", [])
        for tribe in ally_removals[:2]:
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction"):
                fac = tribe_info["allied_faction"]
                if count_pieces(state, ATREBATES, fac, ALLY) > 0:
                    remove_piece(state, ATREBATES, fac, ALLY)
                tribe_info["allied_faction"] = None
        # Belgae place up to 2 Allies
        belgae_placements = params.get("belgae_ally_placements", [])
        for tribe in belgae_placements[:2]:
            tribe_info = state.get("tribes", {}).get(tribe)
            if tribe_info and tribe_info.get("allied_faction") is None:
                if get_available(state, BELGAE, ALLY) > 0:
                    place_piece(state, ATREBATES, BELGAE, ALLY)
                    tribe_info["allied_faction"] = BELGAE
        # Free Rally in 1 Belgica Region — defer
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_64_belgae_rally"] = True

def execute_card_65(state, shaded=False):
    """Card 65: German Allegiances — March+Ambush Germans / Replace Germans.

    Unshaded: March Germans from up to 2 Regions, then Ambush with
    all Germans able.
    Shaded: Where you have Control, remove or replace 5 Germanic
    Warbands and 1 German Ally with your own.

    Source: Card Reference, card 65
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    if not shaded:
        # German March + Ambush — defer to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_65_german_march_ambush"] = True
        state["event_modifiers"]["card_65_march_regions"] = 2
    else:
        # Replace 5 Germanic Warbands + 1 German Ally with your pieces
        wb_replacements = params.get("warband_replacements", [])
        replaced = 0
        for r in wb_replacements:
            if replaced >= 5:
                break
            region = r["region"]
            for ps in (HIDDEN, REVEALED):
                if count_pieces_by_state(state, region, GERMANS, WARBAND, ps) > 0:
                    remove_piece(state, region, GERMANS, WARBAND, piece_state=ps)
                    if faction and get_available(state, faction, AUXILIA) > 0:
                        place_piece(state, region, faction, AUXILIA)
                    replaced += 1
                    break
        # Replace 1 German Ally
        ally_tribe = params.get("ally_replacement_tribe")
        if ally_tribe:
            region = TRIBE_TO_REGION.get(ally_tribe)
            tribe_info = state.get("tribes", {}).get(ally_tribe)
            if (tribe_info and tribe_info.get("allied_faction") == GERMANS
                    and region):
                if count_pieces(state, region, GERMANS, ALLY) > 0:
                    remove_piece(state, region, GERMANS, ALLY)
                if faction and get_available(state, faction, ALLY) > 0:
                    place_piece(state, region, faction, ALLY)
                    tribe_info["allied_faction"] = faction
                else:
                    tribe_info["allied_faction"] = None

def execute_card_66(state, shaded=False):
    """Card 66: Migration — German Rally+March / Gallic relocation.

    Unshaded: Execute Germanic Rally then March in/from up to 2
    Regions each.
    Shaded: A Gallic Faction moves its Warbands and Leader as desired
    to a Region with No Control and places an Ally there.

    Source: Card Reference, card 66
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        # Germanic Rally then March — defer to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_66_german_rally_march"] = True
    else:
        # Gallic Faction moves Warbands+Leader to No Control region + Ally
        faction = state.get("executing_faction")
        target_region = params.get("target_region")
        # Moves handled by caller, but place Ally
        ally_tribe = params.get("ally_tribe")
        if ally_tribe and faction:
            region = TRIBE_TO_REGION.get(ally_tribe)
            tribe_info = state.get("tribes", {}).get(ally_tribe)
            if (tribe_info and tribe_info.get("allied_faction") is None
                    and region and get_available(state, faction, ALLY) > 0):
                place_piece(state, region, faction, ALLY)
                tribe_info["allied_faction"] = faction
        # Piece moves from event_params
        moves = params.get("moves", [])
        for m in moves:
            from_region = m["from_region"]
            to_region = m["to_region"]
            piece_type = m["piece_type"]
            cnt = m.get("count", 1)
            if piece_type == LEADER:
                leader_name = m.get("leader_name")
                move_piece(state, from_region, to_region, faction, LEADER,
                           count=1, leader_name=leader_name)
            else:
                ps = m.get("piece_state")
                move_piece(state, from_region, to_region, faction, piece_type,
                           count=cnt, piece_state=ps)

def execute_card_67(state, shaded=False):
    """Card 67: Arduenna — March + Command in Nervii/Treveri, Hidden.

    Both sides: Romans or a Gallic Faction may free March into either
    or both Nervii or Treveri Regions, then execute a free Command
    except March in one or both, then flip all friendly pieces there
    to Hidden.

    Source: Card Reference, card 67
    """
    from fs_bot.rules_consts import NERVII, TREVERI
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_67_arduenna"] = True
    state["event_modifiers"]["card_67_target_regions"] = [NERVII, TREVERI]
    # After Command, flip pieces Hidden — deferred to caller
    # but if event_params has pieces already moved, flip them
    faction = state.get("executing_faction")
    params = state.get("event_params", {})
    flip_regions = params.get("flip_hidden_regions", [])
    for region in flip_regions:
        if region in (NERVII, TREVERI) and faction:
            for piece_type in (AUXILIA, WARBAND):
                revealed = count_pieces_by_state(
                    state, region, faction, piece_type, REVEALED)
                if revealed > 0:
                    flip_piece(state, region, faction, piece_type, revealed,
                               from_state=REVEALED, to_state=HIDDEN)

def execute_card_68(state, shaded=False):
    """Card 68: Remi Influence — Replace Allies / Remove+Citadel.

    Unshaded: If Remi are Roman Ally or Subdued, replace 1-2 Allies
    within 1 Region of Remi with Roman Allies.
    Shaded: A Gallic Faction with Remi as Ally may remove anything at
    Alesia or Cenabum and place a Citadel there with 4 Warbands.

    Source: Card Reference, card 68
    """
    from fs_bot.rules_consts import (
        TRIBE_REMI, TRIBE_TO_REGION, ATREBATES,
        CITY_ALESIA, CITY_CENABUM, CITY_TO_TRIBE,
    )
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        tribe_info = state.get("tribes", {}).get(TRIBE_REMI)
        if not tribe_info:
            return
        is_roman = tribe_info.get("allied_faction") == ROMANS
        is_subdued = (tribe_info.get("allied_faction") is None)
        markers = state.get("markers", {}).get(TRIBE_REMI, {})
        if MARKER_DISPERSED in markers:
            is_subdued = False
        if not (is_roman or is_subdued):
            return
        # Replace 1-2 Allies within 1 Region of Remi (Atrebates + adjacent)
        remi_region = ATREBATES
        valid_regions = [remi_region] + list(get_adjacent(remi_region, scenario))
        replacements = params.get("replacements", [])
        for r in replacements[:2]:
            tribe = r["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            if region not in valid_regions:
                continue
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction")
                    and t_info["allied_faction"] != ROMANS):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                if get_available(state, ROMANS, ALLY) > 0:
                    place_piece(state, region, ROMANS, ALLY)
                t_info["allied_faction"] = ROMANS
    else:
        tribe_info = state.get("tribes", {}).get(TRIBE_REMI)
        if not tribe_info or tribe_info.get("allied_faction") not in GALLIC_FACTIONS:
            return
        faction = state.get("executing_faction")
        target_city = params.get("target_city")
        if target_city not in (CITY_ALESIA, CITY_CENABUM):
            return
        tribe = CITY_TO_TRIBE.get(target_city)
        region = TRIBE_TO_REGION.get(tribe)
        # Remove anything at the city
        t_info = state.get("tribes", {}).get(tribe)
        if t_info and t_info.get("allied_faction"):
            old_fac = t_info["allied_faction"]
            if count_pieces(state, region, old_fac, ALLY) > 0:
                remove_piece(state, region, old_fac, ALLY)
            t_info["allied_faction"] = None
        for fac in (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS):
            while count_pieces(state, region, fac, CITADEL) > 0:
                remove_piece(state, region, fac, CITADEL)
        # Remove Dispersed/Razed markers
        markers = state.get("markers", {})
        if tribe in markers:
            markers[tribe].pop(MARKER_DISPERSED, None)
            markers[tribe].pop(MARKER_DISPERSED_GATHERING, None)
            markers[tribe].pop(MARKER_RAZED, None)
        # Place Citadel + 4 Warbands of executing faction
        if faction and get_available(state, faction, CITADEL) > 0:
            place_piece(state, region, faction, CITADEL)
        if faction:
            avail = get_available(state, faction, WARBAND)
            to_place = min(4, avail)
            if to_place > 0:
                place_piece(state, region, faction, WARBAND, count=to_place)

def execute_card_69(state, shaded=False):
    """Card 69: Segni & Condrusi — Place Germanic Warbands + Germans Phase.

    Both sides: Place 4 Germanic Warbands each in Nervii and Treveri.
    Then conduct immediate Germans Phase as if Winter, but skip Rally.

    Source: Card Reference, card 69
    """
    from fs_bot.rules_consts import NERVII, TREVERI
    from fs_bot.commands.march import germans_phase_march
    from fs_bot.commands.raid import germans_phase_raid_region
    from fs_bot.engine.germans_battle import germans_phase_battle
    # Place 4 Germanic Warbands in each region
    for region in (NERVII, TREVERI):
        avail = get_available(state, GERMANS, WARBAND)
        to_place = min(4, avail)
        if to_place > 0:
            place_piece(state, region, GERMANS, WARBAND, count=to_place)
    # Germans Phase without Rally
    germans_phase_march(state)
    for region in list(state["spaces"]):
        germans_phase_raid_region(state, region)
    germans_phase_battle(state)
    refresh_all_control(state)

def execute_card_70(state, shaded=False):
    """Card 70: Camulogenus — Roman March+Battle / Place Warbands+Command.

    Unshaded: Romans may free March up to 4 Legions & any Auxilia to
    Atrebates, Carnutes, or Mandubii and free Battle there.
    Shaded: Place 0-6 Warbands among Atrebates, Carnutes, and Mandubii;
    select 1 for a free Command + Special Ability.

    Source: Card Reference, card 70
    """
    from fs_bot.rules_consts import ATREBATES, CARNUTES, MANDUBII
    params = state.get("event_params", {})
    if not shaded:
        # Roman March + Battle — defer to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_70_roman_march_battle"] = True
        state["event_modifiers"]["card_70_legion_limit"] = 4
        state["event_modifiers"]["card_70_target_regions"] = [
            ATREBATES, CARNUTES, MANDUBII]
    else:
        # Place 0-6 Warbands among target regions
        faction = state.get("executing_faction")
        placements = params.get("placements", [])
        total = 0
        for p in placements:
            if total >= 6:
                break
            region = p["region"]
            cnt = p.get("count", 1)
            if region not in (ATREBATES, CARNUTES, MANDUBII):
                continue
            cnt = min(cnt, 6 - total)
            if faction:
                avail = get_available(state, faction, WARBAND)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, faction, WARBAND,
                                count=to_place)
                    total += to_place
        # Free Command + SA in 1 of those regions — defer
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_70_free_command_sa"] = True

def execute_card_71(state, shaded=False):
    """Card 71: Colony — Place Colony marker and Ally.

    Both sides: In a Region you Control or No Control, place +1 marker,
    Colony marker, and your Ally on it. Add +1 to that Control Value.
    The Colony is a Tribe.

    Source: Card Reference, card 71
    """
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    region = params.get("region")
    if not region or not faction:
        return
    # Check Control prerequisite
    has_control = is_controlled_by(state, region, faction)
    no_control = (calculate_control(state, region) == NO_CONTROL)
    if not (has_control or no_control):
        return
    # Place Colony marker
    markers = state.setdefault("markers", {})
    region_markers = markers.setdefault(region, {})
    region_markers[MARKER_COLONY] = True
    # Place Ally
    if get_available(state, faction, ALLY) > 0:
        place_piece(state, region, faction, ALLY)
        # The Colony becomes a tribe — track in tribes dict
        colony_name = params.get("colony_tribe_name", f"Colony_{region}")
        state.setdefault("tribes", {})[colony_name] = {
            "status": None,
            "allied_faction": faction,
        }

def execute_card_72(state, shaded=False):
    """Card 72: Impetuosity — March into Region + enemy Battle / Hidden March.

    Unshaded: Free March into 1 Region from any adjacent. Either
    Arverni or Belgae there free Battle against you.
    Shaded: Free March 1 group of your Hidden Warbands (no Leader).
    That group then may free Battle (alone).

    Source: Card Reference, card 72
    """
    state.setdefault("event_modifiers", {})
    if not shaded:
        state["event_modifiers"]["card_72_march_and_enemy_battle"] = True
    else:
        state["event_modifiers"]["card_72_hidden_march_battle"] = True


# ---------------------------------------------------------------------------
# Ariovistus replacement/new card stubs
# ---------------------------------------------------------------------------

def execute_card_A5(state, shaded=False):
    """Card A5: Gallia Togata — Cisalpina garrison / Remove Roman pieces.

    Unshaded: Place Gallia Togata marker and 3 Auxilia in Cisalpina.
    Only Romans may stack there.
    Shaded: Unless Senate in Adulation, Romans remove 1 Legion to track
    and 2 Auxilia to Available.

    Source: A Card Reference, card A5
    """
    if not shaded:
        markers = state.setdefault("markers", {})
        region_markers = markers.setdefault(CISALPINA, {})
        region_markers[MARKER_GALLIA_TOGATA] = True
        avail = get_available(state, ROMANS, AUXILIA)
        to_place = min(3, avail)
        if to_place > 0:
            place_piece(state, CISALPINA, ROMANS, AUXILIA, count=to_place)
        # Non-Roman pieces must be moved/removed — deferred to caller
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A5_remove_non_romans"] = True
    else:
        if state["senate"]["position"] != ADULATION:
            params = state.get("event_params", {})
            # Remove 1 Legion to track
            legion_region = params.get("legion_region")
            if legion_region and count_pieces(state, legion_region, ROMANS, LEGION) > 0:
                remove_piece(state, legion_region, ROMANS, LEGION,
                             to_track=True, to_available=False)
            # Remove 2 Auxilia to Available
            auxilia_removals = params.get("auxilia_removals", [])
            for r in auxilia_removals[:2]:
                region = r.get("region")
                if region:
                    for ps in (HIDDEN, REVEALED):
                        if count_pieces_by_state(state, region, ROMANS,
                                                 AUXILIA, ps) > 0:
                            remove_piece(state, region, ROMANS, AUXILIA,
                                         piece_state=ps)
                            break

def execute_card_A17(state, shaded=False):
    """Card A17: Publius Licinius Crassus — Roman March+Battle / Remove Auxilia.

    Unshaded: Romans free March 1-4 Legions + 1-8 Auxilia to Region
    without Caesar and Battle there, double Losses by Auxilia.
    Shaded: Remove 4 Auxilia from any 1 Region. Romans Ineligible.

    Source: A Card Reference, card A17
    """
    params = state.get("event_params", {})
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A17_roman_march_battle"] = True
        state["event_modifiers"]["card_A17_double_auxilia_losses"] = True
    else:
        region = params.get("region")
        if region:
            for _ in range(4):
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, ROMANS,
                                             AUXILIA, ps) > 0:
                        remove_piece(state, region, ROMANS, AUXILIA,
                                     piece_state=ps)
                        break
        state["eligibility"][ROMANS] = INELIGIBLE

def execute_card_A18(state, shaded=False):
    """Card A18: Rhenus Bridge — Remove Germans / Roman resource drain.

    Unshaded: Remove all Germans from 1 Germania Region without
    Ariovistus and under/adjacent to Roman Control.
    Shaded: If Legion within 1 of Germania, Romans -6 and Ineligible.

    Source: A Card Reference, card A18
    """
    from fs_bot.rules_consts import GERMANIA_REGIONS
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        region = params.get("region")
        if region and region in GERMANIA_REGIONS:
            leader = get_leader_in_region(state, region, GERMANS)
            if leader != ARIOVISTUS_LEADER:
                for ps in (HIDDEN, REVEALED):
                    c = count_pieces_by_state(state, region, GERMANS,
                                              WARBAND, ps)
                    if c > 0:
                        remove_piece(state, region, GERMANS, WARBAND,
                                     count=c, piece_state=ps)
                for pt in (ALLY, SETTLEMENT):
                    cnt = count_pieces(state, region, GERMANS, pt)
                    if cnt > 0:
                        remove_piece(state, region, GERMANS, pt, count=cnt)
    else:
        has_legion_near = False
        for g_region in GERMANIA_REGIONS:
            if count_pieces(state, g_region, ROMANS, LEGION) > 0:
                has_legion_near = True
                break
            for adj in get_adjacent(g_region, scenario):
                if count_pieces(state, adj, ROMANS, LEGION) > 0:
                    has_legion_near = True
                    break
            if has_legion_near:
                break
        if has_legion_near:
            _cap_resources(state, ROMANS, -6)
            state["eligibility"][ROMANS] = INELIGIBLE

def execute_card_A19(state, shaded=False):
    """Card A19: Gaius Valerius Procillus — Replace Allies / March Romans.

    Unshaded: Within 1 of Caesar, replace up to 3 Allies with Roman.
    Shaded: March all Romans in 1 Region to adjacent with Germans.
    Romans Ineligible.

    Source: A Card Reference, card A19
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        caesar_loc = find_leader(state, CAESAR)
        if caesar_loc is None:
            return
        valid = [caesar_loc] + list(get_adjacent(caesar_loc, scenario))
        replacements = params.get("replacements", [])
        for r in replacements[:3]:
            tribe = r["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            if region not in valid:
                continue
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction")
                    and t_info["allied_faction"] != ROMANS):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                if get_available(state, ROMANS, ALLY) > 0:
                    place_piece(state, region, ROMANS, ALLY)
                t_info["allied_faction"] = ROMANS
    else:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A19_march_romans"] = True
        state["eligibility"][ROMANS] = INELIGIBLE

def execute_card_A20(state, shaded=False):
    """Card A20: Morbihan — Veneti operations.

    Unshaded: If Romans within 1 of Veneti, remove all Arverni from
    Veneti and free Seize there.
    Shaded: If Veneti Arverni Ally, Arverni Ambush Romans near Veneti.

    Source: A Card Reference, card A20
    """
    from fs_bot.rules_consts import VENETI, TRIBE_VENETI
    from fs_bot.map.map_data import get_adjacent
    scenario = state["scenario"]
    if not shaded:
        has_romans = False
        regions_near = [VENETI] + list(get_adjacent(VENETI, scenario))
        for r in regions_near:
            if (count_pieces(state, r, ROMANS, LEGION) > 0 or
                    count_pieces(state, r, ROMANS, AUXILIA) > 0):
                has_romans = True
                break
        if has_romans:
            # Remove all Arverni from Veneti
            for pt in (ALLY, CITADEL):
                while count_pieces(state, VENETI, ARVERNI, pt) > 0:
                    remove_piece(state, VENETI, ARVERNI, pt)
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, VENETI, ARVERNI, WARBAND, ps)
                if c > 0:
                    remove_piece(state, VENETI, ARVERNI, WARBAND,
                                 count=c, piece_state=ps)
            t_info = state.get("tribes", {}).get(TRIBE_VENETI)
            if t_info and t_info.get("allied_faction") == ARVERNI:
                t_info["allied_faction"] = None
            state.setdefault("event_modifiers", {})
            state["event_modifiers"]["card_A20_free_seize_veneti"] = True
    else:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A20_arverni_ambush"] = True

def execute_card_A21(state, shaded=False):
    """Card A21: Vosegus — Decisive battle near Sequani.

    Both sides: Free Battle in Region within 1 of Sequani. No Retreat.
    Then optional second Battle there (Retreat allowed).

    Source: A Card Reference, card A21
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A21_double_battle"] = True
    state["event_modifiers"]["card_A21_first_no_retreat"] = True

def execute_card_A22(state, shaded=False):
    """Card A22: Dread — Cancel/enhance Intimidate.

    Unshaded: Intimidate markers have no effect on Romans.
    Shaded (CAPABILITY): Intimidate may Reveal 1 added Warband to
    remove 1 extra piece.

    Source: A Card Reference, card A22
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A22_no_intimidate_romans"] = True
    else:
        activate_capability(state, "A22", EVENT_SHADED)

def execute_card_A23(state, shaded=False):
    """Card A23: Parley — Move Caesar/Ariovistus together.

    Both sides: Move Caesar group or Ariovistus group to other's
    Region (or meet in between). Romans and Germans Ineligible.

    Source: A Card Reference, card A23
    """
    params = state.get("event_params", {})
    caesar_loc = find_leader(state, CAESAR)
    ario_loc = find_leader(state, ARIOVISTUS_LEADER)
    if caesar_loc is None or ario_loc is None:
        state["eligibility"][ROMANS] = INELIGIBLE
        state["eligibility"][GERMANS] = INELIGIBLE
        return
    target = params.get("meeting_region")
    who_moves = params.get("who_moves")  # "caesar", "ariovistus", "both"
    if target and who_moves:
        if who_moves in ("caesar", "both") and caesar_loc != target:
            move_piece(state, caesar_loc, target, ROMANS, LEADER,
                       leader_name=CAESAR)
            cnt = count_pieces(state, caesar_loc, ROMANS, LEGION)
            if cnt > 0:
                move_piece(state, caesar_loc, target, ROMANS, LEGION,
                           count=cnt)
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, caesar_loc, ROMANS,
                                          AUXILIA, ps)
                if c > 0:
                    move_piece(state, caesar_loc, target, ROMANS, AUXILIA,
                               count=c, piece_state=ps)
        if who_moves in ("ariovistus", "both") and ario_loc != target:
            move_piece(state, ario_loc, target, GERMANS, LEADER,
                       leader_name=ARIOVISTUS_LEADER)
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, ario_loc, GERMANS,
                                          WARBAND, ps)
                if c > 0:
                    move_piece(state, ario_loc, target, GERMANS, WARBAND,
                               count=c, piece_state=ps)
    state["eligibility"][ROMANS] = INELIGIBLE
    state["eligibility"][GERMANS] = INELIGIBLE

def execute_card_A24(state, shaded=False):
    """Card A24: Seduni Uprising! — Arverni Allies + Arverni Phase.

    Both sides: Remove Allies at Sequani, Helvetii, Nori, Helvii.
    Place Arverni Ally at each and 2 Arverni Warbands each in Sequani,
    Cisalpina, Provincia. Conduct Arverni Phase as if At War.

    Source: A Card Reference, card A24
    """
    from fs_bot.rules_consts import (
        SEQUANI, TRIBE_SEQUANI, TRIBE_HELVETII, TRIBE_NORI,
        TRIBE_HELVII, TRIBE_TO_REGION,
    )
    tribes = [TRIBE_SEQUANI, TRIBE_HELVETII, TRIBE_NORI, TRIBE_HELVII]
    for tribe in tribes:
        region = TRIBE_TO_REGION.get(tribe)
        t_info = state.get("tribes", {}).get(tribe)
        if not t_info:
            continue
        # Remove existing Ally
        if t_info.get("allied_faction"):
            old_fac = t_info["allied_faction"]
            if region and count_pieces(state, region, old_fac, ALLY) > 0:
                remove_piece(state, region, old_fac, ALLY)
            t_info["allied_faction"] = None
        # Place Arverni Ally
        if region and get_available(state, ARVERNI, ALLY) > 0:
            place_piece(state, region, ARVERNI, ALLY)
            t_info["allied_faction"] = ARVERNI
    # Place 2 Arverni Warbands in Sequani, Cisalpina, Provincia
    for region in (SEQUANI, CISALPINA, PROVINCIA):
        avail = get_available(state, ARVERNI, WARBAND)
        to_place = min(2, avail)
        if to_place > 0:
            place_piece(state, region, ARVERNI, WARBAND, count=to_place)
    # Conduct Arverni Phase as if At War
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A24_arverni_phase"] = True

def execute_card_A25(state, shaded=False):
    """Card A25: Ariovistus's Wife — Remove/place German pieces.

    Unshaded: Remove all non-Leader German pieces from Cisalpina.
    German Resources -6.
    Shaded: Germans remove Ally at Nori, place their Ally and 6
    Warbands there, and gain +6 Resources.

    Source: A Card Reference, card A25
    """
    from fs_bot.rules_consts import TRIBE_NORI, TRIBE_TO_REGION
    if not shaded:
        # Remove all non-Leader German pieces from Cisalpina
        for ps in (HIDDEN, REVEALED):
            c = count_pieces_by_state(state, CISALPINA, GERMANS, WARBAND, ps)
            if c > 0:
                remove_piece(state, CISALPINA, GERMANS, WARBAND,
                             count=c, piece_state=ps)
        for pt in (ALLY, SETTLEMENT):
            cnt = count_pieces(state, CISALPINA, GERMANS, pt)
            if cnt > 0:
                remove_piece(state, CISALPINA, GERMANS, pt, count=cnt)
        _cap_resources(state, GERMANS, -6)
    else:
        region = TRIBE_TO_REGION.get(TRIBE_NORI)
        t_info = state.get("tribes", {}).get(TRIBE_NORI)
        if t_info:
            # Remove any Ally at Nori
            if t_info.get("allied_faction"):
                old_fac = t_info["allied_faction"]
                if region and count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                t_info["allied_faction"] = None
            # Place German Ally
            if region and get_available(state, GERMANS, ALLY) > 0:
                place_piece(state, region, GERMANS, ALLY)
                t_info["allied_faction"] = GERMANS
        # Place 6 German Warbands at Nori's region
        if region:
            avail = get_available(state, GERMANS, WARBAND)
            to_place = min(6, avail)
            if to_place > 0:
                place_piece(state, region, GERMANS, WARBAND, count=to_place)
        _cap_resources(state, GERMANS, 6)

def execute_card_A26(state, shaded=False):
    """Card A26: Divico — Remove/place Arverni.

    Unshaded: Remove Arverni Ally at Helvetii and all Arverni Warbands
    from Sequani and Aedui Regions.
    Shaded: Place up to 12 Arverni Warbands among Aedui and Sequani.

    Source: A Card Reference, card A26
    """
    from fs_bot.rules_consts import (
        SEQUANI, AEDUI_REGION, TRIBE_HELVETII, TRIBE_TO_REGION,
    )
    if not shaded:
        # Remove Arverni Ally at Helvetii
        t_info = state.get("tribes", {}).get(TRIBE_HELVETII)
        region = TRIBE_TO_REGION.get(TRIBE_HELVETII)
        if t_info and t_info.get("allied_faction") == ARVERNI:
            if region and count_pieces(state, region, ARVERNI, ALLY) > 0:
                remove_piece(state, region, ARVERNI, ALLY)
            t_info["allied_faction"] = None
        # Remove all Arverni Warbands from Sequani and Aedui
        for reg in (SEQUANI, AEDUI_REGION):
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, reg, ARVERNI, WARBAND, ps)
                if c > 0:
                    remove_piece(state, reg, ARVERNI, WARBAND,
                                 count=c, piece_state=ps)
    else:
        # Place up to 12 Arverni Warbands among Aedui and Sequani
        params = state.get("event_params", {})
        placements = params.get("placements", [])
        total = 0
        for p in placements:
            if total >= 12:
                break
            region = p["region"]
            if region not in (AEDUI_REGION, SEQUANI):
                continue
            cnt = min(p.get("count", 1), 12 - total)
            avail = get_available(state, ARVERNI, WARBAND)
            to_place = min(cnt, avail)
            if to_place > 0:
                place_piece(state, region, ARVERNI, WARBAND, count=to_place)
                total += to_place

def execute_card_A27(state, shaded=False):
    """Card A27: Sotiates Uprising! — Arverni Allies + Arverni Phase.

    Both sides: Remove Allies at Pictones, Santones, Volcae, Cadurci.
    Place Arverni Ally at each and 3 Arverni Warbands each in Pictones
    and Arverni Regions. Conduct Arverni Phase as if At War.

    Source: A Card Reference, card A27
    """
    from fs_bot.rules_consts import (
        PICTONES, ARVERNI_REGION, TRIBE_PICTONES, TRIBE_SANTONES,
        TRIBE_VOLCAE, TRIBE_CADURCI, TRIBE_TO_REGION,
    )
    tribes = [TRIBE_PICTONES, TRIBE_SANTONES, TRIBE_VOLCAE, TRIBE_CADURCI]
    for tribe in tribes:
        region = TRIBE_TO_REGION.get(tribe)
        t_info = state.get("tribes", {}).get(tribe)
        if not t_info:
            continue
        if t_info.get("allied_faction"):
            old_fac = t_info["allied_faction"]
            if region and count_pieces(state, region, old_fac, ALLY) > 0:
                remove_piece(state, region, old_fac, ALLY)
            t_info["allied_faction"] = None
        if region and get_available(state, ARVERNI, ALLY) > 0:
            place_piece(state, region, ARVERNI, ALLY)
            t_info["allied_faction"] = ARVERNI
    for region in (PICTONES, ARVERNI_REGION):
        avail = get_available(state, ARVERNI, WARBAND)
        to_place = min(3, avail)
        if to_place > 0:
            place_piece(state, region, ARVERNI, WARBAND, count=to_place)
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A27_arverni_phase"] = True

def execute_card_A28(state, shaded=False):
    """Card A28: Admagetobriga — Combined Battle near Sequani.

    Both sides: Free Battle in and adjacent to Sequani, treating
    Arverni and allied Warbands/Auxilia as your own. No Retreat.

    Source: A Card Reference, card A28
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A28_combined_battle"] = True
    state["event_modifiers"]["card_A28_no_retreat"] = True
    state["event_modifiers"]["card_A28_use_arverni"] = True

def execute_card_A29(state, shaded=False):
    """Card A29: Harudes — Place pieces near Settlements / German Raid.

    Unshaded: A Gaul or Roman places up to 2 Allies and 5 Warbands
    or 3 Auxilia among Regions with Settlements.
    Shaded: Place 4 German Warbands & 1 Settlement adjacent to
    Germania. They free Raid.

    Source: A Card Reference, card A29
    """
    from fs_bot.rules_consts import GERMANIA_REGIONS
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        # Placements among Regions with Settlements — deferred to caller
        faction = state.get("executing_faction")
        placements = params.get("placements", [])
        for p in placements:
            region = p["region"]
            piece_type = p["piece_type"]
            cnt = p.get("count", 1)
            pfac = p.get("faction", faction)
            if piece_type == ALLY:
                tribe = p.get("tribe")
                t_info = state.get("tribes", {}).get(tribe)
                if t_info and t_info.get("allied_faction") is None:
                    if pfac and get_available(state, pfac, ALLY) > 0:
                        place_piece(state, region, pfac, ALLY)
                        t_info["allied_faction"] = pfac
            else:
                if pfac:
                    avail = get_available(state, pfac, piece_type)
                    to_place = min(cnt, avail)
                    if to_place > 0:
                        place_piece(state, region, pfac, piece_type,
                                    count=to_place)
    else:
        # Place 4 German Warbands + 1 Settlement adjacent to Germania
        adj_regions = set()
        for g_region in GERMANIA_REGIONS:
            adj_regions.update(get_adjacent(g_region, scenario))
        placements = params.get("placements", [])
        wb_placed = 0
        for p in placements:
            region = p["region"]
            if region not in adj_regions:
                continue
            piece_type = p.get("piece_type", WARBAND)
            if piece_type == WARBAND and wb_placed < 4:
                cnt = min(p.get("count", 1), 4 - wb_placed)
                avail = get_available(state, GERMANS, WARBAND)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, GERMANS, WARBAND,
                                count=to_place)
                    wb_placed += to_place
            elif piece_type == SETTLEMENT:
                if get_available(state, GERMANS, SETTLEMENT) > 0:
                    place_piece(state, region, GERMANS, SETTLEMENT)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A29_german_raid"] = True

def execute_card_A30(state, shaded=False):
    """Card A30: Orgetorix — Remove Arverni / Place Arverni.

    Unshaded: Remove all Arverni from 1 Region within 1 of Sequani.
    Shaded: In Aedui and Sequani, remove Allies/Citadel and place
    9 Arverni pieces total (despite Aedui-only stacking).

    Source: A Card Reference, card A30
    """
    from fs_bot.rules_consts import SEQUANI, AEDUI_REGION, TRIBE_TO_REGION
    from fs_bot.map.map_data import get_adjacent, get_tribes_in_region
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        region = params.get("region")
        if region:
            # Remove all Arverni from the region
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, region, ARVERNI, WARBAND, ps)
                if c > 0:
                    remove_piece(state, region, ARVERNI, WARBAND,
                                 count=c, piece_state=ps)
            for pt in (ALLY, CITADEL):
                cnt = count_pieces(state, region, ARVERNI, pt)
                if cnt > 0:
                    remove_piece(state, region, ARVERNI, pt, count=cnt)
            # Clear Arverni leader if present
            leader = get_leader_in_region(state, region, ARVERNI)
            if leader:
                remove_piece(state, region, ARVERNI, LEADER)
            # Clear Arverni tribe allies in this region
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                t_info = state.get("tribes", {}).get(tribe)
                if t_info and t_info.get("allied_faction") == ARVERNI:
                    t_info["allied_faction"] = None
    else:
        # Remove Allies/Citadel, place 9 Arverni pieces in Aedui + Sequani
        for reg in (AEDUI_REGION, SEQUANI):
            tribes = get_tribes_in_region(reg, scenario)
            for tribe in tribes:
                t_info = state.get("tribes", {}).get(tribe)
                if t_info and t_info.get("allied_faction"):
                    old_fac = t_info["allied_faction"]
                    if count_pieces(state, reg, old_fac, ALLY) > 0:
                        remove_piece(state, reg, old_fac, ALLY)
                    t_info["allied_faction"] = None
            for fac in FACTIONS:
                cnt = count_pieces(state, reg, fac, CITADEL)
                if cnt > 0:
                    remove_piece(state, reg, fac, CITADEL, count=cnt)
        # Place 9 Arverni pieces total
        placements = params.get("placements", [])
        total = 0
        for p in placements:
            if total >= 9:
                break
            region = p["region"]
            if region not in (AEDUI_REGION, SEQUANI):
                continue
            piece_type = p["piece_type"]
            cnt = min(p.get("count", 1), 9 - total)
            if piece_type == ALLY:
                tribe = p.get("tribe")
                t_info = state.get("tribes", {}).get(tribe)
                if t_info and t_info.get("allied_faction") is None:
                    if get_available(state, ARVERNI, ALLY) > 0:
                        place_piece(state, region, ARVERNI, ALLY)
                        t_info["allied_faction"] = ARVERNI
                        total += 1
            else:
                avail = get_available(state, ARVERNI, piece_type)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, ARVERNI, piece_type,
                                count=to_place)
                    total += to_place

def execute_card_A31(state, shaded=False):
    """Card A31: German Phalanx — Cancel/protect German Battle effects.

    Unshaded: Event effects benefitting Germans in Battle cancelled,
    Ariovistus does not double Losses.
    Shaded (CAPABILITY - Stalwart): Event effects harming Germans
    cancelled, named enemy Leaders don't double Losses to Germans.

    Source: A Card Reference, card A31
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A31_cancel_german_benefits"] = True
        state["event_modifiers"]["card_A31_no_ario_double"] = True
    else:
        activate_capability(state, "A31", EVENT_SHADED)

def execute_card_A32(state, shaded=False):
    """Card A32: Veneti Uprising! — Arverni Allies + Arverni Phase.

    Both sides: Remove Allies at Veneti, Namnetes, Morini, Menapii.
    Place Arverni Ally at each, 4 Arverni Warbands in Veneti and 2
    in Morini. Conduct Arverni Phase as if At War.

    Source: A Card Reference, card A32
    """
    from fs_bot.rules_consts import (
        VENETI, MORINI, TRIBE_VENETI, TRIBE_NAMNETES, TRIBE_MORINI,
        TRIBE_MENAPII, TRIBE_TO_REGION,
    )
    tribes = [TRIBE_VENETI, TRIBE_NAMNETES, TRIBE_MORINI, TRIBE_MENAPII]
    for tribe in tribes:
        region = TRIBE_TO_REGION.get(tribe)
        t_info = state.get("tribes", {}).get(tribe)
        if not t_info:
            continue
        if t_info.get("allied_faction"):
            old_fac = t_info["allied_faction"]
            if region and count_pieces(state, region, old_fac, ALLY) > 0:
                remove_piece(state, region, old_fac, ALLY)
            t_info["allied_faction"] = None
        if region and get_available(state, ARVERNI, ALLY) > 0:
            place_piece(state, region, ARVERNI, ALLY)
            t_info["allied_faction"] = ARVERNI
    # 4 Warbands in Veneti, 2 in Morini
    for region, cnt in ((VENETI, 4), (MORINI, 2)):
        avail = get_available(state, ARVERNI, WARBAND)
        to_place = min(cnt, avail)
        if to_place > 0:
            place_piece(state, region, ARVERNI, WARBAND, count=to_place)
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A32_arverni_phase"] = True

def execute_card_A33(state, shaded=False):
    """Card A33: Wailing Women — German Retreat/CAPABILITY.

    Unshaded: Germans never Retreat; unless Ariovistus on map, remove
    outnumbered Warbands after Counterattack.
    Shaded (CAPABILITY - Motivation): Defending Germans half Losses
    and inflict +1 Counterattack Loss.

    Source: A Card Reference, card A33
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A33_no_german_retreat"] = True
        state["event_modifiers"]["card_A33_remove_outnumbered"] = True
    else:
        activate_capability(state, "A33", EVENT_SHADED)

def execute_card_A34(state, shaded=False):
    """Card A34: Divination — Use German pieces / German free Command.

    Unshaded: Non-German player may use German pieces to free March
    or Battle in up to 3 Regions.
    Shaded: Germans or Belgae free Command and stay Eligible.

    Source: A Card Reference, card A34
    """
    state.setdefault("event_modifiers", {})
    if not shaded:
        state["event_modifiers"]["card_A34_use_german_pieces"] = True
        state["event_modifiers"]["card_A34_regions_limit"] = 3
    else:
        faction = state.get("executing_faction")
        state["event_modifiers"]["card_A34_free_command"] = True
        if faction in (GERMANS, BELGAE):
            state["eligibility"][faction] = ELIGIBLE

def execute_card_A35(state, shaded=False):
    """Card A35: Nasua & Cimberius — Place at Treveri / German placement.

    Unshaded: Place 1 Gallic/Roman Ally at Treveri (replacing anything)
    and up to 8 Warbands or 4 Auxilia there.
    Shaded: Place up to 8 Germanic Warbands and 1 Settlement among
    Regions within 1 of Germania.

    Source: A Card Reference, card A35
    """
    from fs_bot.rules_consts import (
        TREVERI, TRIBE_TREVERI, GERMANIA_REGIONS, TRIBE_TO_REGION,
    )
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        faction = state.get("executing_faction")
        t_info = state.get("tribes", {}).get(TRIBE_TREVERI)
        if t_info:
            # Replace anything at Treveri with Ally
            if t_info.get("allied_faction"):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, TREVERI, old_fac, ALLY) > 0:
                    remove_piece(state, TREVERI, old_fac, ALLY)
                t_info["allied_faction"] = None
            ally_faction = params.get("ally_faction", faction)
            if ally_faction and get_available(state, ally_faction, ALLY) > 0:
                place_piece(state, TREVERI, ally_faction, ALLY)
                t_info["allied_faction"] = ally_faction
        # Place Warbands or Auxilia
        piece_type = params.get("piece_type", WARBAND)
        limit = 8 if piece_type == WARBAND else 4
        cnt = params.get("count", limit)
        cnt = min(cnt, limit)
        pfac = params.get("piece_faction", faction)
        if pfac:
            avail = get_available(state, pfac, piece_type)
            to_place = min(cnt, avail)
            if to_place > 0:
                place_piece(state, TREVERI, pfac, piece_type, count=to_place)
    else:
        # Place German pieces near Germania
        adj_regions = set()
        for g_region in GERMANIA_REGIONS:
            adj_regions.add(g_region)
            adj_regions.update(get_adjacent(g_region, scenario))
        placements = params.get("placements", [])
        wb_placed = 0
        settlement_placed = False
        for p in placements:
            region = p["region"]
            if region not in adj_regions:
                continue
            pt = p.get("piece_type", WARBAND)
            if pt == WARBAND and wb_placed < 8:
                cnt = min(p.get("count", 1), 8 - wb_placed)
                avail = get_available(state, GERMANS, WARBAND)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, GERMANS, WARBAND,
                                count=to_place)
                    wb_placed += to_place
            elif pt == SETTLEMENT and not settlement_placed:
                if get_available(state, GERMANS, SETTLEMENT) > 0:
                    place_piece(state, region, GERMANS, SETTLEMENT)
                    settlement_placed = True

def execute_card_A36(state, shaded=False):
    """Card A36: Usipetes & Tencteri — Remove/place German pieces.

    Unshaded: Remove 2 Settlements and 8 German Warbands total from
    Morini, Nervii, Treveri.
    Shaded: Place 2 Settlements + 4 Warbands and remove 2 Allies
    among Regions within 1 of Sugambri.

    Source: A Card Reference, card A36
    """
    from fs_bot.rules_consts import (
        MORINI, NERVII, TREVERI, SUGAMBRI, TRIBE_TO_REGION,
    )
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        # Remove 2 Settlements from target regions
        target_regions = [MORINI, NERVII, TREVERI]
        settlements_removed = 0
        for region in target_regions:
            if settlements_removed >= 2:
                break
            cnt = count_pieces(state, region, GERMANS, SETTLEMENT)
            to_remove = min(cnt, 2 - settlements_removed)
            if to_remove > 0:
                remove_piece(state, region, GERMANS, SETTLEMENT,
                             count=to_remove)
                settlements_removed += to_remove
        # Remove 8 German Warbands
        wb_removed = 0
        for region in target_regions:
            if wb_removed >= 8:
                break
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, region, GERMANS, WARBAND, ps)
                to_remove = min(c, 8 - wb_removed)
                if to_remove > 0:
                    remove_piece(state, region, GERMANS, WARBAND,
                                 count=to_remove, piece_state=ps)
                    wb_removed += to_remove
    else:
        # Place near Sugambri
        adj_regions = set([SUGAMBRI])
        adj_regions.update(get_adjacent(SUGAMBRI, scenario))
        placements = params.get("placements", [])
        for p in placements:
            region = p["region"]
            if region not in adj_regions:
                continue
            pt = p.get("piece_type")
            if pt == SETTLEMENT:
                if get_available(state, GERMANS, SETTLEMENT) > 0:
                    place_piece(state, region, GERMANS, SETTLEMENT)
            elif pt == WARBAND:
                cnt = p.get("count", 1)
                avail = get_available(state, GERMANS, WARBAND)
                to_place = min(cnt, avail)
                if to_place > 0:
                    place_piece(state, region, GERMANS, WARBAND,
                                count=to_place)
        # Remove 2 Allies
        ally_removals = params.get("ally_removals", [])
        for r in ally_removals[:2]:
            tribe = r.get("tribe")
            t_info = state.get("tribes", {}).get(tribe)
            region = TRIBE_TO_REGION.get(tribe)
            if t_info and t_info.get("allied_faction") and region in adj_regions:
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                t_info["allied_faction"] = None

def execute_card_A37(state, shaded=False):
    """Card A37: All Gaul Gathers — Place Allies or remove them.

    Unshaded: If Aedui or Roman, place any Allies in 1 Celtica Region
    within 1 of German Control, then move Leader+Warbands/Auxilia there.
    Shaded: Remove up to 3 Aedui/Roman Allies from Celtica within 1
    of German Control.

    Source: A Card Reference, card A37
    """
    from fs_bot.rules_consts import CELTICA_REGIONS, TRIBE_TO_REGION
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    faction = state.get("executing_faction")
    if not shaded:
        # Place Allies + move Leader — partially deferred
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A37_place_allies_move"] = True
        # Handle Ally placements from params
        ally_placements = params.get("ally_placements", [])
        for p in ally_placements:
            tribe = p["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            pfac = p.get("faction", faction)
            t_info = state.get("tribes", {}).get(tribe)
            if t_info and t_info.get("allied_faction") is None and pfac:
                if region and get_available(state, pfac, ALLY) > 0:
                    place_piece(state, region, pfac, ALLY)
                    t_info["allied_faction"] = pfac
    else:
        # Remove up to 3 Aedui/Roman Allies from Celtica near German Control
        removals = params.get("removals", [])
        for r in removals[:3]:
            tribe = r["tribe"]
            fac = r.get("faction")
            region = TRIBE_TO_REGION.get(tribe)
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction") == fac
                    and fac in (AEDUI, ROMANS) and region):
                if count_pieces(state, region, fac, ALLY) > 0:
                    remove_piece(state, region, fac, ALLY)
                t_info["allied_faction"] = None

def execute_card_A38(state, shaded=False):
    """Card A38: Vergobret — Suborn enhancement / CAPABILITY restriction.

    Unshaded: Suborn can pay to place/remove 1 more piece per Region
    and places Auxilia at 0 cost.
    Shaded (CAPABILITY): Suborn only at Diviciacus. If no Diviciacus,
    Suborn and Trade only within 1 of Bibracte.

    Source: A Card Reference, card A38
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A38_suborn_enhanced"] = True
    else:
        activate_capability(state, "A38", EVENT_SHADED)

def execute_card_A40(state, shaded=False):
    """Card A40: Alpine Tribes — Place pieces near Cisalpina.

    Unshaded: Place up to 3 Warbands, 2 Auxilia, or 1 Ally in each
    of 3 Regions within 1 of Cisalpina.
    Shaded: -5 Roman Resources per Region (up to 3) within 1 of
    Cisalpina not under Roman Control. Stay Eligible.

    Source: A Card Reference, card A40
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    scenario = state["scenario"]
    adj_cisalpina = list(get_adjacent(CISALPINA, scenario)) + [CISALPINA]
    if not shaded:
        placements = params.get("placements", [])
        for p in placements:
            region = p["region"]
            piece_type = p["piece_type"]
            cnt = p.get("count", 1)
            pfac = p.get("faction", faction)
            if region not in adj_cisalpina:
                continue
            if piece_type == ALLY:
                tribe = p.get("tribe")
                t_info = state.get("tribes", {}).get(tribe)
                if t_info and t_info.get("allied_faction") is None and pfac:
                    if get_available(state, pfac, ALLY) > 0:
                        place_piece(state, region, pfac, ALLY)
                        t_info["allied_faction"] = pfac
            else:
                if pfac:
                    avail = get_available(state, pfac, piece_type)
                    to_place = min(cnt, avail)
                    if to_place > 0:
                        place_piece(state, region, pfac, piece_type,
                                    count=to_place)
    else:
        non_roman = 0
        for region in adj_cisalpina:
            if not is_controlled_by(state, region, ROMANS):
                non_roman += 1
        drain = min(non_roman, 3)
        _cap_resources(state, ROMANS, -5 * drain)
        if faction:
            state["eligibility"][faction] = ELIGIBLE

def execute_card_A43(state, shaded=False):
    """Card A43: Dumnorix — Replace Arverni pieces / Remove+place Arverni.

    Unshaded: Replace 2 Arverni Allies and 2 Arverni Warbands within
    1 of Bibracte with Roman/Aedui counterparts.
    Shaded: Remove Bituriges, Bibracte, Helvetii Citadels/Allies.
    Arverni place Ally+2 Warbands at each (despite Aedui-only stacking).

    Source: A Card Reference, card A43
    """
    from fs_bot.rules_consts import (
        TRIBE_BITURIGES, TRIBE_AEDUI, TRIBE_HELVETII, TRIBE_TO_REGION,
        CITY_BIBRACTE,
    )
    from fs_bot.map.map_data import get_adjacent
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        # Replace within 1 of Bibracte
        replacements = params.get("replacements", [])
        for r in replacements:
            region = r["region"]
            from_type = r.get("from_type")
            to_faction = r.get("to_faction")
            if from_type == ALLY:
                tribe = r.get("tribe")
                t_info = state.get("tribes", {}).get(tribe)
                if (t_info and t_info.get("allied_faction") == ARVERNI
                        and region):
                    if count_pieces(state, region, ARVERNI, ALLY) > 0:
                        remove_piece(state, region, ARVERNI, ALLY)
                    if to_faction and get_available(state, to_faction, ALLY) > 0:
                        place_piece(state, region, to_faction, ALLY)
                        t_info["allied_faction"] = to_faction
                    else:
                        t_info["allied_faction"] = None
            elif from_type == WARBAND:
                ps = r.get("piece_state", HIDDEN)
                to_type = AUXILIA if to_faction == ROMANS else WARBAND
                if count_pieces_by_state(state, region, ARVERNI,
                                         WARBAND, ps) > 0:
                    remove_piece(state, region, ARVERNI, WARBAND,
                                 piece_state=ps)
                    if to_faction and get_available(state, to_faction,
                                                    to_type) > 0:
                        place_piece(state, region, to_faction, to_type)
    else:
        # Remove Citadels/Allies at Bituriges, Bibracte (Aedui tribe), Helvetii
        target_tribes = [TRIBE_BITURIGES, TRIBE_AEDUI, TRIBE_HELVETII]
        for tribe in target_tribes:
            region = TRIBE_TO_REGION.get(tribe)
            t_info = state.get("tribes", {}).get(tribe)
            if not t_info or not region:
                continue
            # Remove Ally
            if t_info.get("allied_faction"):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                t_info["allied_faction"] = None
            # Remove Citadels
            for fac in FACTIONS:
                cnt = count_pieces(state, region, fac, CITADEL)
                if cnt > 0:
                    remove_piece(state, region, fac, CITADEL, count=cnt)
            # Place Arverni Ally + 2 Warbands
            if get_available(state, ARVERNI, ALLY) > 0:
                place_piece(state, region, ARVERNI, ALLY)
                t_info["allied_faction"] = ARVERNI
            avail = get_available(state, ARVERNI, WARBAND)
            to_place = min(2, avail)
            if to_place > 0:
                place_piece(state, region, ARVERNI, WARBAND, count=to_place)

def execute_card_A45(state, shaded=False):
    """Card A45: Savage Dictates — Place non-German Allies / Free Intimidate.

    Unshaded: Place up to 3 non-German Allies in Celtica within 1
    of Intimidated markers.
    Shaded: Germans may free Intimidate anywhere regardless of
    Ariovistus or Control.

    Source: A Card Reference, card A45
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        placements = params.get("placements", [])
        for p in placements[:3]:
            tribe = p["tribe"]
            faction = p["faction"]
            region = TRIBE_TO_REGION.get(tribe)
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction") is None
                    and faction != GERMANS and region):
                if get_available(state, faction, ALLY) > 0:
                    place_piece(state, region, faction, ALLY)
                    t_info["allied_faction"] = faction
    else:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A45_free_intimidate"] = True

def execute_card_A51(state, shaded=False):
    """Card A51: Siege of Bibrax — Aid Remi / Remove from Atrebates.

    Unshaded: If Remi Roman/Aedui Ally or Subdued, place 4 Auxilia or
    Aedui Warbands and Fort, remove up to 6 Belgic Warbands there.
    Shaded: Remove up to 5 non-Legion non-Leader Roman/Aedui pieces
    from Atrebates.

    Source: A Card Reference, card A51
    """
    from fs_bot.rules_consts import ATREBATES, TRIBE_REMI, TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        t_info = state.get("tribes", {}).get(TRIBE_REMI)
        if not t_info:
            return
        region = TRIBE_TO_REGION.get(TRIBE_REMI)
        allied = t_info.get("allied_faction")
        markers = state.get("markers", {}).get(TRIBE_REMI, {})
        is_valid = (allied in (ROMANS, AEDUI)
                    or (allied is None and MARKER_DISPERSED not in markers))
        if not is_valid:
            return
        # Place 4 Auxilia or Aedui Warbands
        piece_type = params.get("piece_type", AUXILIA)
        pfac = ROMANS if piece_type == AUXILIA else AEDUI
        avail = get_available(state, pfac, piece_type)
        to_place = min(4, avail)
        if to_place > 0 and region:
            place_piece(state, region, pfac, piece_type, count=to_place)
        # Place Fort
        if region and get_available(state, ROMANS, FORT) > 0:
            try:
                place_piece(state, region, ROMANS, FORT)
            except PieceError:
                pass  # Max forts reached
        # Remove up to 6 Belgic Warbands
        removed = 0
        if region:
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, region, BELGAE, WARBAND, ps)
                to_remove = min(c, 6 - removed)
                if to_remove > 0:
                    remove_piece(state, region, BELGAE, WARBAND,
                                 count=to_remove, piece_state=ps)
                    removed += to_remove
    else:
        # Remove up to 5 non-Legion non-Leader Roman/Aedui from Atrebates
        removals = params.get("removals", [])
        removed = 0
        for r in removals:
            if removed >= 5:
                break
            fac = r.get("faction")
            pt = r.get("piece_type")
            if fac not in (ROMANS, AEDUI) or pt in (LEGION, LEADER):
                continue
            if pt in (AUXILIA, WARBAND):
                ps = r.get("piece_state", HIDDEN)
                if count_pieces_by_state(state, ATREBATES, fac, pt, ps) > 0:
                    remove_piece(state, ATREBATES, fac, pt, piece_state=ps)
                    removed += 1
            elif pt in (ALLY, CITADEL, FORT):
                if count_pieces(state, ATREBATES, fac, pt) > 0:
                    remove_piece(state, ATREBATES, fac, pt)
                    removed += 1

def execute_card_A53(state, shaded=False):
    """Card A53: Frumentum — Aedui corn / Resource drain.

    Unshaded: Aedui specify Resources amount. Romans spend on
    Recruit+March+1 SA.
    Shaded: Aedui and Roman Resources -4 each. Both Ineligible.
    Executing Faction stays Eligible.

    Source: A Card Reference, card A53
    """
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A53_aedui_corn"] = True
        # Resource transfer handled by bot/CLI layer
    else:
        _cap_resources(state, AEDUI, -4)
        _cap_resources(state, ROMANS, -4)
        state["eligibility"][AEDUI] = INELIGIBLE
        state["eligibility"][ROMANS] = INELIGIBLE
        if faction:
            state["eligibility"][faction] = ELIGIBLE

def execute_card_A56(state, shaded=False):
    """Card A56: Galba — Belgae surrender / King placement.

    Unshaded: Remove all Belgae except Leader from Atrebates.
    Belgae Resources -4.
    Shaded: Place 4 Belgic Warbands and 2 Belgic Allies (may replace)
    in Belgica. Belgae Resources +4.

    Source: A Card Reference, card A56
    """
    from fs_bot.rules_consts import (
        ATREBATES, BELGICA_REGIONS, TRIBE_TO_REGION,
    )
    from fs_bot.map.map_data import get_tribes_in_region
    params = state.get("event_params", {})
    scenario = state["scenario"]
    if not shaded:
        # Remove all Belgae except Leader from Atrebates
        for ps in (HIDDEN, REVEALED):
            c = count_pieces_by_state(state, ATREBATES, BELGAE, WARBAND, ps)
            if c > 0:
                remove_piece(state, ATREBATES, BELGAE, WARBAND,
                             count=c, piece_state=ps)
        for pt in (ALLY, CITADEL):
            cnt = count_pieces(state, ATREBATES, BELGAE, pt)
            if cnt > 0:
                remove_piece(state, ATREBATES, BELGAE, pt, count=cnt)
        # Clear Belgae tribe allies in Atrebates
        tribes = get_tribes_in_region(ATREBATES, scenario)
        for tribe in tribes:
            t_info = state.get("tribes", {}).get(tribe)
            if t_info and t_info.get("allied_faction") == BELGAE:
                t_info["allied_faction"] = None
        _cap_resources(state, BELGAE, -4)
    else:
        # Place 4 Warbands in Belgica
        wb_placements = params.get("warband_placements", [])
        wb_total = 0
        for p in wb_placements:
            if wb_total >= 4:
                break
            region = p["region"]
            if region not in BELGICA_REGIONS:
                continue
            cnt = min(p.get("count", 1), 4 - wb_total)
            avail = get_available(state, BELGAE, WARBAND)
            to_place = min(cnt, avail)
            if to_place > 0:
                place_piece(state, region, BELGAE, WARBAND, count=to_place)
                wb_total += to_place
        # Place 2 Belgic Allies (may replace)
        ally_placements = params.get("ally_placements", [])
        for p in ally_placements[:2]:
            tribe = p["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            if region not in BELGICA_REGIONS:
                continue
            t_info = state.get("tribes", {}).get(tribe)
            if not t_info:
                continue
            # May replace existing Ally
            if t_info.get("allied_faction") and t_info["allied_faction"] != BELGAE:
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                t_info["allied_faction"] = None
            if t_info.get("allied_faction") is None:
                if get_available(state, BELGAE, ALLY) > 0:
                    place_piece(state, region, BELGAE, ALLY)
                    t_info["allied_faction"] = BELGAE
        _cap_resources(state, BELGAE, 4)

def execute_card_A57(state, shaded=False):
    """Card A57: Sabis — Decisive battle in Belgica.

    Both sides: Free Battle in a Belgica Region. No Retreat. Then
    optional second Battle there (Retreat allowed).

    Source: A Card Reference, card A57
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A57_double_battle"] = True
    state["event_modifiers"]["card_A57_first_no_retreat"] = True

def execute_card_A58(state, shaded=False):
    """Card A58: Aduatuci — Roman Battle+Seize / Replace Roman pieces.

    Unshaded: Romans free Battle anywhere in Belgica, then free Seize
    in Belgica as if Roman Control.
    Shaded: In 1 Belgica Region, replace 1 Roman Ally and 3 Auxilia
    with yours, free Ambush Romans.

    Source: A Card Reference, card A58
    """
    from fs_bot.rules_consts import BELGICA_REGIONS, TRIBE_TO_REGION
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A58_roman_battle_seize"] = True
    else:
        region = params.get("region")
        if region and region in BELGICA_REGIONS:
            # Replace 1 Roman Ally
            ally_tribe = params.get("ally_tribe")
            if ally_tribe:
                t_info = state.get("tribes", {}).get(ally_tribe)
                if t_info and t_info.get("allied_faction") == ROMANS:
                    if count_pieces(state, region, ROMANS, ALLY) > 0:
                        remove_piece(state, region, ROMANS, ALLY)
                    if faction and get_available(state, faction, ALLY) > 0:
                        place_piece(state, region, faction, ALLY)
                        t_info["allied_faction"] = faction
                    else:
                        t_info["allied_faction"] = None
            # Replace 3 Auxilia with Warbands
            replaced = 0
            for _ in range(3):
                for ps in (HIDDEN, REVEALED):
                    if count_pieces_by_state(state, region, ROMANS,
                                             AUXILIA, ps) > 0:
                        remove_piece(state, region, ROMANS, AUXILIA,
                                     piece_state=ps)
                        if faction and get_available(state, faction,
                                                     WARBAND) > 0:
                            place_piece(state, region, faction, WARBAND)
                        replaced += 1
                        break
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A58_free_ambush"] = True

def execute_card_A60(state, shaded=False):
    """Card A60: Iccius & Andecomborius — Roman Ally at Remi / Replace.

    Unshaded: Place Roman Ally at Remi (replacing any) and up to 4
    Auxilia there. For each piece not placed, Roman Resources +2.
    Shaded: In Atrebates, replace up to 5 Roman pieces with Belgae.

    Source: A Card Reference, card A60
    """
    from fs_bot.rules_consts import ATREBATES, TRIBE_REMI, TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        region = TRIBE_TO_REGION.get(TRIBE_REMI)
        t_info = state.get("tribes", {}).get(TRIBE_REMI)
        if t_info and region:
            # Replace any Ally at Remi
            if t_info.get("allied_faction"):
                old_fac = t_info["allied_faction"]
                if count_pieces(state, region, old_fac, ALLY) > 0:
                    remove_piece(state, region, old_fac, ALLY)
                t_info["allied_faction"] = None
            # Place Roman Ally
            if get_available(state, ROMANS, ALLY) > 0:
                place_piece(state, region, ROMANS, ALLY)
                t_info["allied_faction"] = ROMANS
            # Place up to 4 Auxilia
            avail = get_available(state, ROMANS, AUXILIA)
            to_place = min(4, avail)
            if to_place > 0:
                place_piece(state, region, ROMANS, AUXILIA, count=to_place)
            not_placed = 4 - to_place
            if not_placed > 0:
                _cap_resources(state, ROMANS, 2 * not_placed)
    else:
        # Replace up to 5 Roman pieces in Atrebates with Belgae
        replacements = params.get("replacements", [])
        for r in replacements[:5]:
            from_type = r.get("from_type")
            if from_type == ALLY:
                tribe = r.get("tribe")
                t_info = state.get("tribes", {}).get(tribe)
                if (t_info and t_info.get("allied_faction") == ROMANS):
                    if count_pieces(state, ATREBATES, ROMANS, ALLY) > 0:
                        remove_piece(state, ATREBATES, ROMANS, ALLY)
                    if get_available(state, BELGAE, ALLY) > 0:
                        place_piece(state, ATREBATES, BELGAE, ALLY)
                        t_info["allied_faction"] = BELGAE
                    else:
                        t_info["allied_faction"] = None
            elif from_type == AUXILIA:
                ps = r.get("piece_state", HIDDEN)
                if count_pieces_by_state(state, ATREBATES, ROMANS,
                                         AUXILIA, ps) > 0:
                    remove_piece(state, ATREBATES, ROMANS, AUXILIA,
                                 piece_state=ps)
                    if get_available(state, BELGAE, WARBAND) > 0:
                        place_piece(state, ATREBATES, BELGAE, WARBAND)

def execute_card_A63(state, shaded=False):
    """Card A63: Winter Campaign — CAPABILITY.

    Unshaded: Romans pay Quarters costs only in Devastated Regions.
    Shaded (CAPABILITY - Cold war): Unless Roman, after each Harvest,
    you may do 2 Commands/SAs (paying costs).

    Source: A Card Reference, card A63
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A63_quarters_devastated_only"] = True
    else:
        activate_capability(state, "A63", EVENT_SHADED)

def execute_card_A64(state, shaded=False):
    """Card A64: Abatis — Place Abatis marker.

    Both sides: Place your Faction's Abatis marker in a Region where
    you have a Warband. Acts as Fort for defense, negates Auxilia
    Losses. Roman March treats as Devastation.

    Source: A Card Reference, card A64
    """
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    region = params.get("region")
    if region and faction:
        # Verify faction has Warband there
        has_wb = False
        for ps in (HIDDEN, REVEALED):
            if count_pieces_by_state(state, region, faction, WARBAND, ps) > 0:
                has_wb = True
                break
        if has_wb:
            markers = state.setdefault("markers", {})
            region_markers = markers.setdefault(region, {})
            region_markers[MARKER_ABATIS] = faction

def execute_card_A65(state, shaded=False):
    """Card A65: Kinship — Belgae/Germans Battle each other / Swap pieces.

    Unshaded: Either Belgae without Leader Battle Germans or Germans
    without Leader Battle Belgae.
    Shaded: Replace 4 Warbands and 2 Allies of either Belgae or
    Germans with the other's.

    Source: A Card Reference, card A65
    """
    from fs_bot.rules_consts import TRIBE_TO_REGION
    params = state.get("event_params", {})
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A65_kinship_battle"] = True
    else:
        from_faction = params.get("from_faction", BELGAE)
        to_faction = GERMANS if from_faction == BELGAE else BELGAE
        # Replace 4 Warbands
        wb_replacements = params.get("warband_replacements", [])
        for r in wb_replacements[:4]:
            region = r["region"]
            ps = r.get("piece_state", HIDDEN)
            if count_pieces_by_state(state, region, from_faction,
                                     WARBAND, ps) > 0:
                remove_piece(state, region, from_faction, WARBAND,
                             piece_state=ps)
                if get_available(state, to_faction, WARBAND) > 0:
                    place_piece(state, region, to_faction, WARBAND)
        # Replace 2 Allies
        ally_replacements = params.get("ally_replacements", [])
        for r in ally_replacements[:2]:
            tribe = r["tribe"]
            region = TRIBE_TO_REGION.get(tribe)
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction") == from_faction
                    and region):
                if count_pieces(state, region, from_faction, ALLY) > 0:
                    remove_piece(state, region, from_faction, ALLY)
                if get_available(state, to_faction, ALLY) > 0:
                    place_piece(state, region, to_faction, ALLY)
                    t_info["allied_faction"] = to_faction
                else:
                    t_info["allied_faction"] = None

def execute_card_A66(state, shaded=False):
    """Card A66: Winter Uprising! — Place Uprising marker for later.

    Both sides: Take this card. Place Uprising marker in a Region.
    After Quarters Phase, execute faction-specific placement + Command.

    Source: A Card Reference, card A66
    """
    params = state.get("event_params", {})
    region = params.get("region")
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A66_winter_uprising"] = True
    if region:
        markers = state.setdefault("markers", {})
        region_markers = markers.setdefault(region, {})
        region_markers["Uprising"] = True
        state["event_modifiers"]["card_A66_uprising_region"] = region

def execute_card_A67(state, shaded=False):
    """Card A67: Arduenna — March + Command in Nervii/Treveri, Hidden.

    Both sides: A Faction other than Arverni may free March into
    Nervii or Treveri, then free Command except March, then flip
    friendly pieces there Hidden.

    Source: A Card Reference, card A67
    """
    from fs_bot.rules_consts import NERVII, TREVERI
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_A67_arduenna"] = True
    state["event_modifiers"]["card_A67_target_regions"] = [NERVII, TREVERI]
    # Flip Hidden deferred, but handle if provided
    faction = state.get("executing_faction")
    params = state.get("event_params", {})
    flip_regions = params.get("flip_hidden_regions", [])
    for region in flip_regions:
        if region in (NERVII, TREVERI) and faction:
            for piece_type in (AUXILIA, WARBAND):
                revealed = count_pieces_by_state(
                    state, region, faction, piece_type, REVEALED)
                if revealed > 0:
                    flip_piece(state, region, faction, piece_type, revealed,
                               from_state=REVEALED, to_state=HIDDEN)

def execute_card_A69(state, shaded=False):
    """Card A69: Bellovaci — Remove/place at Bellovaci.

    Unshaded: At Bellovaci, remove Ally if Belgic and 4 Belgic
    Warbands. Place Roman/Aedui Ally and 4 Warbands/Auxilia there.
    Shaded: If Bellovaci Belgic Ally, place 6 Belgic Warbands there.
    They Ambush causing 1 Loss each.

    Source: A Card Reference, card A69
    """
    from fs_bot.rules_consts import (
        ATREBATES, TRIBE_BELLOVACI, TRIBE_TO_REGION,
    )
    params = state.get("event_params", {})
    faction = state.get("executing_faction")
    region = TRIBE_TO_REGION.get(TRIBE_BELLOVACI)
    t_info = state.get("tribes", {}).get(TRIBE_BELLOVACI)
    if not shaded:
        if t_info and region:
            # Remove Belgic Ally
            if t_info.get("allied_faction") == BELGAE:
                if count_pieces(state, region, BELGAE, ALLY) > 0:
                    remove_piece(state, region, BELGAE, ALLY)
                t_info["allied_faction"] = None
            # Remove 4 Belgic Warbands
            removed = 0
            for ps in (HIDDEN, REVEALED):
                c = count_pieces_by_state(state, region, BELGAE, WARBAND, ps)
                to_remove = min(c, 4 - removed)
                if to_remove > 0:
                    remove_piece(state, region, BELGAE, WARBAND,
                                 count=to_remove, piece_state=ps)
                    removed += to_remove
            # Place Roman/Aedui Ally
            ally_fac = params.get("ally_faction", ROMANS)
            if get_available(state, ally_fac, ALLY) > 0:
                place_piece(state, region, ally_fac, ALLY)
                t_info["allied_faction"] = ally_fac
            # Place 4 Warbands or Auxilia
            piece_type = params.get("piece_type", AUXILIA)
            pfac = params.get("piece_faction", ally_fac)
            avail = get_available(state, pfac, piece_type)
            to_place = min(4, avail)
            if to_place > 0:
                place_piece(state, region, pfac, piece_type, count=to_place)
    else:
        if (t_info and t_info.get("allied_faction") == BELGAE
                and region):
            avail = get_available(state, BELGAE, WARBAND)
            to_place = min(6, avail)
            if to_place > 0:
                place_piece(state, region, BELGAE, WARBAND, count=to_place)
            state.setdefault("event_modifiers", {})
            state["event_modifiers"]["card_A69_ambush"] = True
            state["event_modifiers"]["card_A69_loss_per_warband"] = to_place

def execute_card_A70(state, shaded=False):
    """Card A70: Nervii — No Belgae Retreat / CAPABILITY.

    Unshaded: Belgae never Retreat.
    Shaded (CAPABILITY): If Nervii Subdued at end of any Faction's
    action, place Belgic Ally there. Rally there places +2 Warbands.

    Source: A Card Reference, card A70
    """
    if not shaded:
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_A70_no_belgae_retreat"] = True
    else:
        activate_capability(state, "A70", EVENT_SHADED)


# ---------------------------------------------------------------------------
# 2nd Edition text-change card stubs for Ariovistus
# Cards 11, 30, 39, 44, 54 have different text in Ariovistus.
# The base execute_card_N handles the base text; these handle the
# Ariovistus-modified text when needed.
# ---------------------------------------------------------------------------

def execute_card_11_ariovistus(state, shaded=False):
    """Card 11 (Ariovistus): Numidians — Auxilia Battle / Remove Auxilia.

    Unshaded: Romans place 3 Auxilia within 1 of Leader and free Battle
    there with Auxilia causing double Losses.
    Shaded: Remove any 4 Auxilia.

    Source: A Card Reference, card 11 (Ariovistus text)
    """
    params = state.get("event_params", {})
    if not shaded:
        # Place 3 Auxilia in region within 1 of Roman Leader
        region = params.get("region")
        if region:
            avail = get_available(state, ROMANS, AUXILIA)
            to_place = min(3, avail)
            if to_place > 0:
                place_piece(state, region, ROMANS, AUXILIA, count=to_place)
        # Free Battle with Auxilia double Losses — defer
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_11a_auxilia_battle"] = True
        state["event_modifiers"]["card_11a_double_auxilia_losses"] = True
    else:
        # Remove any 4 Auxilia
        removals = params.get("removals", [])
        removed = 0
        for r in removals:
            if removed >= 4:
                break
            region = r.get("region")
            fac = r.get("faction", ROMANS)
            for ps in (HIDDEN, REVEALED):
                if count_pieces_by_state(state, region, fac, AUXILIA, ps) > 0:
                    remove_piece(state, region, fac, AUXILIA, piece_state=ps)
                    removed += 1
                    break

def execute_card_30_ariovistus(state, shaded=False):
    """Card 30 (Ariovistus): Vercingetorix's Elite — CAPABILITY.

    Unshaded: Arverni Rally places Warbands up to Allies+Citadels.
    Shaded (CAPABILITY): In Battles with Leader, Arverni pick 4
    Warbands that take & inflict Losses as if Legions.

    Source: A Card Reference, card 30 (Ariovistus text — 4 Warbands)
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 30, side)
    # Note: Ariovistus version has 4 Warbands (not 2) for shaded.
    # The capability system tracks this via scenario check.

def execute_card_39_ariovistus(state, shaded=False):
    """Card 39 (Ariovistus): River Commerce — CAPABILITY.

    Unshaded: Aedui Trade yields Resources regardless of Supply Lines.
    Shaded (CAPABILITY): Trade is maximum 1 Region.

    Source: A Card Reference, card 39 (Ariovistus text)
    """
    side = EVENT_UNSHADED if not shaded else EVENT_SHADED
    activate_capability(state, 39, side)

def execute_card_44_ariovistus(state, shaded=False):
    """Card 44 (Ariovistus): Dumnorix Loyalists — Replace pieces.

    Unshaded: Replace any 4 Warbands with Auxilia or Aedui Warbands.
    Free Scout.
    Shaded: Replace any 3 Auxilia or Aedui Warbands with any Warbands.
    Execute a free Command in Regions placed.

    Source: A Card Reference, card 44 (Ariovistus text — free Command)
    """
    params = state.get("event_params", {})
    if not shaded:
        # Same as base unshaded
        replacements = params.get("replacements", [])
        for r in replacements:
            region = r["region"]
            from_faction = r["from_faction"]
            to_type = r.get("to_type", AUXILIA)
            to_faction = r.get("to_faction",
                               ROMANS if to_type == AUXILIA else AEDUI)
            ps = r.get("piece_state", HIDDEN)
            if count_pieces_by_state(state, region, from_faction,
                                     WARBAND, ps) > 0:
                remove_piece(state, region, from_faction, WARBAND,
                             piece_state=ps)
                if get_available(state, to_faction, to_type) > 0:
                    place_piece(state, region, to_faction, to_type)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_44_free_scout"] = True
    else:
        # Ariovistus shaded: replace + free Command (not just Raid)
        replacements = params.get("replacements", [])
        placed_regions = set()
        for r in replacements:
            region = r["region"]
            from_faction = r["from_faction"]
            from_type = r.get("from_type", AUXILIA)
            to_faction = r.get("to_faction")
            if from_type == AUXILIA:
                if count_pieces(state, region, from_faction, AUXILIA) > 0:
                    remove_piece(state, region, from_faction, AUXILIA)
            elif from_type == WARBAND:
                ps = r.get("piece_state", HIDDEN)
                if count_pieces_by_state(state, region, AEDUI,
                                         WARBAND, ps) > 0:
                    remove_piece(state, region, AEDUI, WARBAND,
                                 piece_state=ps)
            if to_faction and get_available(state, to_faction, WARBAND) > 0:
                place_piece(state, region, to_faction, WARBAND)
                placed_regions.add(region)
        state.setdefault("event_modifiers", {})
        state["event_modifiers"]["card_44a_free_command"] = True
        state["event_modifiers"]["card_44a_command_regions"] = list(
            placed_regions)

def execute_card_54_ariovistus(state, shaded=False):
    """Card 54 (Ariovistus): Joined Ranks — March + multi-faction Battle.

    Both sides: March up to 8 pieces to Region with 2+ other Factions.
    Executing Faction then 2nd player Faction may each Battle a 3rd.
    First Battle: no Retreat. (Clarified: 2nd Faction gets Retreat
    even if 1st declines.)

    Source: A Card Reference, card 54 (Ariovistus text — clarified)
    """
    state.setdefault("event_modifiers", {})
    state["event_modifiers"]["card_54_joined_ranks"] = True
    state["event_modifiers"]["card_54_march_limit"] = 8
    state["event_modifiers"]["card_54_no_retreat_first"] = True
    # Ariovistus clarification: 2nd faction always gets Retreat
    state["event_modifiers"]["card_54a_second_always_retreat"] = True


# ---------------------------------------------------------------------------
# Dispatcher tables
# ---------------------------------------------------------------------------

# Base game dispatcher: card_id (int) -> handler function
_BASE_HANDLERS = {
    1: execute_card_1, 2: execute_card_2, 3: execute_card_3,
    4: execute_card_4, 5: execute_card_5, 6: execute_card_6,
    7: execute_card_7, 8: execute_card_8, 9: execute_card_9,
    10: execute_card_10, 11: execute_card_11, 12: execute_card_12,
    13: execute_card_13, 14: execute_card_14, 15: execute_card_15,
    16: execute_card_16, 17: execute_card_17, 18: execute_card_18,
    19: execute_card_19, 20: execute_card_20, 21: execute_card_21,
    22: execute_card_22, 23: execute_card_23, 24: execute_card_24,
    25: execute_card_25, 26: execute_card_26, 27: execute_card_27,
    28: execute_card_28, 29: execute_card_29, 30: execute_card_30,
    31: execute_card_31, 32: execute_card_32, 33: execute_card_33,
    34: execute_card_34, 35: execute_card_35, 36: execute_card_36,
    37: execute_card_37, 38: execute_card_38, 39: execute_card_39,
    40: execute_card_40, 41: execute_card_41, 42: execute_card_42,
    43: execute_card_43, 44: execute_card_44, 45: execute_card_45,
    46: execute_card_46, 47: execute_card_47, 48: execute_card_48,
    49: execute_card_49, 50: execute_card_50, 51: execute_card_51,
    52: execute_card_52, 53: execute_card_53, 54: execute_card_54,
    55: execute_card_55, 56: execute_card_56, 57: execute_card_57,
    58: execute_card_58, 59: execute_card_59, 60: execute_card_60,
    61: execute_card_61, 62: execute_card_62, 63: execute_card_63,
    64: execute_card_64, 65: execute_card_65, 66: execute_card_66,
    67: execute_card_67, 68: execute_card_68, 69: execute_card_69,
    70: execute_card_70, 71: execute_card_71, 72: execute_card_72,
}

# Ariovistus-only card dispatcher: card_id (str "A##") -> handler function
_ARIOVISTUS_HANDLERS = {
    "A5": execute_card_A5, "A17": execute_card_A17,
    "A18": execute_card_A18, "A19": execute_card_A19,
    "A20": execute_card_A20, "A21": execute_card_A21,
    "A22": execute_card_A22, "A23": execute_card_A23,
    "A24": execute_card_A24, "A25": execute_card_A25,
    "A26": execute_card_A26, "A27": execute_card_A27,
    "A28": execute_card_A28, "A29": execute_card_A29,
    "A30": execute_card_A30, "A31": execute_card_A31,
    "A32": execute_card_A32, "A33": execute_card_A33,
    "A34": execute_card_A34, "A35": execute_card_A35,
    "A36": execute_card_A36, "A37": execute_card_A37,
    "A38": execute_card_A38, "A40": execute_card_A40,
    "A43": execute_card_A43, "A45": execute_card_A45,
    "A51": execute_card_A51, "A53": execute_card_A53,
    "A56": execute_card_A56, "A57": execute_card_A57,
    "A58": execute_card_A58, "A60": execute_card_A60,
    "A63": execute_card_A63, "A64": execute_card_A64,
    "A65": execute_card_A65, "A66": execute_card_A66,
    "A67": execute_card_A67, "A69": execute_card_A69,
    "A70": execute_card_A70,
}

# 2nd Edition text-change handlers for Ariovistus scenarios
_ARIOVISTUS_TEXT_CHANGE_HANDLERS = {
    11: execute_card_11_ariovistus,
    30: execute_card_30_ariovistus,
    39: execute_card_39_ariovistus,
    44: execute_card_44_ariovistus,
    54: execute_card_54_ariovistus,
}


def execute_event(state, card_id, shaded=False):
    """Dispatch to the correct card handler.

    For Ariovistus scenarios, uses Ariovistus-specific handlers for
    A-prefix cards and 2nd Edition text-change cards.

    Args:
        state: game state dict (must have state["scenario"])
        card_id: int or str card identifier
        shaded: True for shaded Event, False for unshaded

    Raises:
        NotImplementedError: always (stubs not yet implemented)
        KeyError: if card_id not found
    """
    from fs_bot.rules_consts import ARIOVISTUS_SCENARIOS

    scenario = state.get("scenario")
    is_ariovistus = scenario in ARIOVISTUS_SCENARIOS if scenario else False

    # A-prefix cards (Ariovistus-only)
    if isinstance(card_id, str) and card_id.startswith("A"):
        if card_id in _ARIOVISTUS_HANDLERS:
            return _ARIOVISTUS_HANDLERS[card_id](state, shaded)
        raise KeyError(f"Unknown Ariovistus card: {card_id!r}")

    # Integer card IDs
    if isinstance(card_id, int):
        # In Ariovistus, 2nd Edition text-change cards use modified handlers
        if is_ariovistus and card_id in _ARIOVISTUS_TEXT_CHANGE_HANDLERS:
            return _ARIOVISTUS_TEXT_CHANGE_HANDLERS[card_id](state, shaded)
        # Base game handler
        if card_id in _BASE_HANDLERS:
            return _BASE_HANDLERS[card_id](state, shaded)

    raise KeyError(f"Unknown card_id: {card_id!r}")


def get_all_card_ids():
    """Return all card IDs that have handlers (base + Ariovistus)."""
    ids = list(_BASE_HANDLERS.keys())
    ids.extend(_ARIOVISTUS_HANDLERS.keys())
    return ids
