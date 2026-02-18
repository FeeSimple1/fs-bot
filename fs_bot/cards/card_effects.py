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
    raise NotImplementedError("Card 4: Circumvallation")

def execute_card_5(state, shaded=False):
    raise NotImplementedError("Card 5: Gallia Togata")

def execute_card_6(state, shaded=False):
    raise NotImplementedError("Card 6: Marcus Antonius")

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
    raise NotImplementedError("Card 8: Baggage Trains")

def execute_card_9(state, shaded=False):
    raise NotImplementedError("Card 9: Mons Cevenna")

def execute_card_10(state, shaded=False):
    raise NotImplementedError("Card 10: Ballistae")

def execute_card_11(state, shaded=False):
    raise NotImplementedError("Card 11: Numidians")

def execute_card_12(state, shaded=False):
    raise NotImplementedError("Card 12: Titus Labienus")

def execute_card_13(state, shaded=False):
    raise NotImplementedError("Card 13: Balearic Slingers")

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
    raise NotImplementedError("Card 15: Legio X")

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
    raise NotImplementedError("Card 17: Germanic Chieftains")

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
    raise NotImplementedError("Card 19: Lucterius")

def execute_card_20(state, shaded=False):
    raise NotImplementedError("Card 20: Optimates")

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
    raise NotImplementedError("Card 22: Hostages")

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
    raise NotImplementedError("Card 25: Aquitani")

def execute_card_26(state, shaded=False):
    raise NotImplementedError("Card 26: Gobannitio")

def execute_card_27(state, shaded=False):
    raise NotImplementedError("Card 27: Massed Gallic Archers")

def execute_card_28(state, shaded=False):
    raise NotImplementedError("Card 28: Oppida")

def execute_card_29(state, shaded=False):
    raise NotImplementedError("Card 29: Suebi Mobilize")

def execute_card_30(state, shaded=False):
    raise NotImplementedError("Card 30: Vercingetorix's Elite")

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
    raise NotImplementedError("Card 32: Forced Marches")

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
    raise NotImplementedError("Card 34: Acco")

def execute_card_35(state, shaded=False):
    raise NotImplementedError("Card 35: Gallic Shouts")

def execute_card_36(state, shaded=False):
    raise NotImplementedError("Card 36: Morasses")

def execute_card_37(state, shaded=False):
    raise NotImplementedError("Card 37: Boii")

def execute_card_38(state, shaded=False):
    raise NotImplementedError("Card 38: Diviciacus")

def execute_card_39(state, shaded=False):
    raise NotImplementedError("Card 39: River Commerce")

def execute_card_40(state, shaded=False):
    raise NotImplementedError("Card 40: Alpine Tribes")

def execute_card_41(state, shaded=False):
    raise NotImplementedError("Card 41: Avaricum")

def execute_card_42(state, shaded=False):
    raise NotImplementedError("Card 42: Roman Wine")

def execute_card_43(state, shaded=False):
    raise NotImplementedError("Card 43: Convictolitavis")

def execute_card_44(state, shaded=False):
    raise NotImplementedError("Card 44: Dumnorix Loyalists")

def execute_card_45(state, shaded=False):
    raise NotImplementedError("Card 45: Litaviccus")

def execute_card_46(state, shaded=False):
    raise NotImplementedError("Card 46: Celtic Rites")

def execute_card_47(state, shaded=False):
    raise NotImplementedError("Card 47: Chieftains' Council")

def execute_card_48(state, shaded=False):
    raise NotImplementedError("Card 48: Druids")

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
            # Choose which piece to remove
            # Romans: remove Legion to Fallen if any, else Auxilia
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
            elif faction == GERMANS:
                # Germans: Warbands before Allied Tribes per Tips
                if count_pieces(state, region, GERMANS, WARBAND) > 0:
                    remove_piece(state, region, GERMANS, WARBAND)
                elif count_pieces(state, region, GERMANS, ALLY) > 0:
                    remove_piece(state, region, GERMANS, ALLY)
            else:
                # Gallic factions: remove Warband first, then Ally
                if count_pieces(state, region, faction, WARBAND) > 0:
                    remove_piece(state, region, faction, WARBAND)
                elif count_pieces(state, region, faction, ALLY) > 0:
                    remove_piece(state, region, faction, ALLY)
                elif count_pieces(state, region, faction, CITADEL) > 0:
                    remove_piece(state, region, faction, CITADEL)

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
    raise NotImplementedError("Card 51: Surus")

def execute_card_52(state, shaded=False):
    raise NotImplementedError("Card 52: Assembly of Gaul")

def execute_card_53(state, shaded=False):
    raise NotImplementedError("Card 53: Consuetudine")

def execute_card_54(state, shaded=False):
    raise NotImplementedError("Card 54: Joined Ranks")

def execute_card_55(state, shaded=False):
    raise NotImplementedError("Card 55: Commius")

def execute_card_56(state, shaded=False):
    raise NotImplementedError("Card 56: Flight of Ambiorix")

def execute_card_57(state, shaded=False):
    raise NotImplementedError("Card 57: Land of Mist and Mystery")

def execute_card_58(state, shaded=False):
    raise NotImplementedError("Card 58: Aduatuca")

def execute_card_59(state, shaded=False):
    raise NotImplementedError("Card 59: Germanic Horse")

def execute_card_60(state, shaded=False):
    raise NotImplementedError("Card 60: Indutiomarus")

def execute_card_61(state, shaded=False):
    raise NotImplementedError("Card 61: Catuvolcus")

def execute_card_62(state, shaded=False):
    raise NotImplementedError("Card 62: War Fleet")

def execute_card_63(state, shaded=False):
    raise NotImplementedError("Card 63: Winter Campaign")

def execute_card_64(state, shaded=False):
    raise NotImplementedError("Card 64: Correus")

def execute_card_65(state, shaded=False):
    raise NotImplementedError("Card 65: German Allegiances")

def execute_card_66(state, shaded=False):
    raise NotImplementedError("Card 66: Migration")

def execute_card_67(state, shaded=False):
    raise NotImplementedError("Card 67: Arduenna")

def execute_card_68(state, shaded=False):
    raise NotImplementedError("Card 68: Remi Influence")

def execute_card_69(state, shaded=False):
    raise NotImplementedError("Card 69: Segni & Condrusi")

def execute_card_70(state, shaded=False):
    raise NotImplementedError("Card 70: Camulogenus")

def execute_card_71(state, shaded=False):
    raise NotImplementedError("Card 71: Colony")

def execute_card_72(state, shaded=False):
    raise NotImplementedError("Card 72: Impetuosity")


# ---------------------------------------------------------------------------
# Ariovistus replacement/new card stubs
# ---------------------------------------------------------------------------

def execute_card_A5(state, shaded=False):
    raise NotImplementedError("Card A5: Gallia Togata")

def execute_card_A17(state, shaded=False):
    raise NotImplementedError("Card A17: Publius Licinius Crassus")

def execute_card_A18(state, shaded=False):
    raise NotImplementedError("Card A18: Rhenus Bridge")

def execute_card_A19(state, shaded=False):
    raise NotImplementedError("Card A19: Gaius Valerius Procillus")

def execute_card_A20(state, shaded=False):
    raise NotImplementedError("Card A20: Morbihan")

def execute_card_A21(state, shaded=False):
    raise NotImplementedError("Card A21: Vosegus")

def execute_card_A22(state, shaded=False):
    raise NotImplementedError("Card A22: Dread")

def execute_card_A23(state, shaded=False):
    raise NotImplementedError("Card A23: Parley")

def execute_card_A24(state, shaded=False):
    raise NotImplementedError("Card A24: Seduni Uprising!")

def execute_card_A25(state, shaded=False):
    raise NotImplementedError("Card A25: Ariovistus's Wife")

def execute_card_A26(state, shaded=False):
    raise NotImplementedError("Card A26: Divico")

def execute_card_A27(state, shaded=False):
    raise NotImplementedError("Card A27: Sotiates Uprising!")

def execute_card_A28(state, shaded=False):
    raise NotImplementedError("Card A28: Admagetobriga")

def execute_card_A29(state, shaded=False):
    raise NotImplementedError("Card A29: Harudes")

def execute_card_A30(state, shaded=False):
    raise NotImplementedError("Card A30: Orgetorix")

def execute_card_A31(state, shaded=False):
    raise NotImplementedError("Card A31: German Phalanx")

def execute_card_A32(state, shaded=False):
    raise NotImplementedError("Card A32: Veneti Uprising!")

def execute_card_A33(state, shaded=False):
    raise NotImplementedError("Card A33: Wailing Women")

def execute_card_A34(state, shaded=False):
    raise NotImplementedError("Card A34: Divination")

def execute_card_A35(state, shaded=False):
    raise NotImplementedError("Card A35: Nasua & Cimberius")

def execute_card_A36(state, shaded=False):
    raise NotImplementedError("Card A36: Usipetes & Tencteri")

def execute_card_A37(state, shaded=False):
    raise NotImplementedError("Card A37: All Gaul Gathers")

def execute_card_A38(state, shaded=False):
    raise NotImplementedError("Card A38: Vergobret")

def execute_card_A40(state, shaded=False):
    raise NotImplementedError("Card A40: Alpine Tribes")

def execute_card_A43(state, shaded=False):
    raise NotImplementedError("Card A43: Dumnorix")

def execute_card_A45(state, shaded=False):
    raise NotImplementedError("Card A45: Savage Dictates")

def execute_card_A51(state, shaded=False):
    raise NotImplementedError("Card A51: Siege of Bibrax")

def execute_card_A53(state, shaded=False):
    raise NotImplementedError("Card A53: Frumentum")

def execute_card_A56(state, shaded=False):
    raise NotImplementedError("Card A56: Galba")

def execute_card_A57(state, shaded=False):
    raise NotImplementedError("Card A57: Sabis")

def execute_card_A58(state, shaded=False):
    raise NotImplementedError("Card A58: Aduatuci")

def execute_card_A60(state, shaded=False):
    raise NotImplementedError("Card A60: Iccius & Andecomborius")

def execute_card_A63(state, shaded=False):
    raise NotImplementedError("Card A63: Winter Campaign")

def execute_card_A64(state, shaded=False):
    raise NotImplementedError("Card A64: Abatis")

def execute_card_A65(state, shaded=False):
    raise NotImplementedError("Card A65: Kinship")

def execute_card_A66(state, shaded=False):
    raise NotImplementedError("Card A66: Winter Uprising!")

def execute_card_A67(state, shaded=False):
    raise NotImplementedError("Card A67: Arduenna")

def execute_card_A69(state, shaded=False):
    raise NotImplementedError("Card A69: Bellovaci")

def execute_card_A70(state, shaded=False):
    raise NotImplementedError("Card A70: Nervii")


# ---------------------------------------------------------------------------
# 2nd Edition text-change card stubs for Ariovistus
# Cards 11, 30, 39, 44, 54 have different text in Ariovistus.
# The base execute_card_N handles the base text; these handle the
# Ariovistus-modified text when needed.
# ---------------------------------------------------------------------------

def execute_card_11_ariovistus(state, shaded=False):
    raise NotImplementedError("Card 11 (Ariovistus): Numidians")

def execute_card_30_ariovistus(state, shaded=False):
    raise NotImplementedError("Card 30 (Ariovistus): Vercingetorix's Elite")

def execute_card_39_ariovistus(state, shaded=False):
    raise NotImplementedError("Card 39 (Ariovistus): River Commerce")

def execute_card_44_ariovistus(state, shaded=False):
    raise NotImplementedError("Card 44 (Ariovistus): Dumnorix Loyalists")

def execute_card_54_ariovistus(state, shaded=False):
    raise NotImplementedError("Card 54 (Ariovistus): Joined Ranks")


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
