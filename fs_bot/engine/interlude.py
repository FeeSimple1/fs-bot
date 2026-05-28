"""Gallic War Interlude — A Scenario: The Gallic War (lines 14-119).

Mid-game reset for The Gallic War two-part scenario. Triggered after
the 3rd Victory Phase if no faction has won. Resets the board to a
54 BC Pax Gallica?-style state for the second half; the Germanic
player slot becomes Arverni.

The procedure follows the order in the scenario document exactly:

  1. Winter Events (Winter Uprising!, shaded Winter Campaign)
  2. Adjust Forces (Circumvallation cleanup first, then per-Faction:
     German -> Belgae -> Aedui -> Arverni -> Roman; then Cisalpina
     relocation unless Gallia Togata is in effect)
  3. Britannia Expedition (Roman decision; affects Senate marker)
  4. Markers cleanup (Rally, Britannia Not In Play, Nori, Cisalpina
     Control box, all Intimidated)
  5. Spring Phase (with Roman keep-one-Dispersed option)
  6. Eligibility cylinder swap (German -> Arverni)
  7. Edge Track (German Resources to Arverni, cap/boost)
  8. Victory marker swap and recalculation
  9. Lingering Events preserved (Capabilities, Gallia Togata, Colony,
     Abatis)
 10. Deck rebuild per Pax Gallica? composition (with O38 Diviciacus
     substitution and in-effect Capabilities held out)
 11. Set scenario_phase = "second_half", interlude_completed = True
 12. Mark first-Winter-Round-after-Interlude special rules pending

Reference:
  A Scenario: The Gallic War (Interlude section)
  A6.5.1  Senate marker — first Senate Phase after Interlude
  A6.6    Spring Phase in Ariovistus (Intimidated removal)
  A1.3.1  Arverni Home Regions in Ariovistus
  A1.3.2  Cisalpina / Nori
  A1.3.4  Britannia not in play in Ariovistus
  A1.4    Diviciacus, Settlements
  A1.8    Resource tracking (Germans only in Ariovistus)
"""

import math

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Scenarios
    SCENARIO_GALLIC_WAR, ARIOVISTUS_SCENARIOS, BASE_SCENARIOS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, BODUOGNATUS,
    ARIOVISTUS_LEADER, DIVICIACUS, SUCCESSOR,
    LEADER_FACTION,
    # Regions
    ALL_REGIONS, BELGICA_REGIONS, GERMANIA_REGIONS,
    PROVINCIA, CISALPINA, BRITANNIA,
    AEDUI_REGION, ARVERNI_REGION,
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, MANDUBII, VENETI, CARNUTES, PICTONES, BITURIGES,
    SEQUANI,
    # Home regions
    ROMAN_HOME_REGIONS, AEDUI_HOME_REGIONS, BELGAE_HOME_REGIONS,
    ARVERNI_HOME_REGIONS_ARIOVISTUS, GERMAN_HOME_REGIONS_BASE,
    # Tribes (used for Cadurci/Volcae and Nori)
    TRIBE_CADURCI, TRIBE_VOLCAE, TRIBE_NORI,
    TRIBE_TO_REGION,
    # Markers
    MARKER_CIRCUMVALLATION, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_BRITANNIA_NOT_IN_PLAY, MARKER_ARVERNI_RALLY,
    MARKER_INTIMIDATED, MARKER_GALLIA_TOGATA, MARKER_COLONY,
    MARKER_ABATIS, MARKER_WINTER_UPRISING, MARKER_AT_WAR,
    MARKER_NORI, MARKER_CISALPINA_CONTROL_BOX,
    # Senate
    UPROAR, INTRIGUE, ADULATION, SENATE_POSITIONS,
    # Eligibility
    ELIGIBLE,
    # Victory check helper
    MAX_RESOURCES,
    # Interlude config
    INTERLUDE_VICTORY_TRIGGER_WINTER,
    INTERLUDE_GERMAN_WARBANDS_REMOVED,
    PAX_GALLICA_START_ARVERNI, PAX_GALLICA_START_AEDUI,
    PAX_GALLICA_START_BELGAE, PAX_GALLICA_START_ROMANS,
    PAX_GALLICA_DECK_EVENTS, PAX_GALLICA_WINTER_PILES,
    INTERLUDE_DIVICIACUS_CARD,
    BRITANNIA_EXPEDITION_LEGIONS_TO_TRACK,
    BRITANNIA_EXPEDITION_MIN_LEGIONS_TO_BRITANNIA,
    BRITANNIA_EXPEDITION_MIN_AUXILIA_TO_BRITANNIA,
    # Cards
    CARD_NAMES_BASE, WINTER_CARD,
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
)
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, count_pieces,
    count_pieces_by_state, get_available, get_leader_in_region,
    find_leader, PieceError,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.cards.capabilities import is_capability_active


# ============================================================================
# Helpers
# ============================================================================


def _fraction_to_remove(total, fraction):
    """Round-up fraction of a total (per Interlude phrasing: 'round up').

    Returns the minimum number of pieces required to satisfy the
    'at least F of' requirement.
    """
    if total <= 0:
        return 0
    return math.ceil(total * fraction)


def _ensure_removed(state, faction, piece_type, count=1):
    """Permanently remove pieces (not to Available).

    Increments state['removed_pieces'][faction][piece_type] by count.
    """
    rp = state.setdefault("removed_pieces", {})
    fp = rp.setdefault(faction, {})
    fp[piece_type] = fp.get(piece_type, 0) + count


def _remove_leader_from_play(state, faction):
    """Remove a faction's Leader from play permanently.

    The Leader may be on map OR in Available. After this call, the
    leader is in state['removed_pieces'][faction][LEADER], not in
    Available.

    Returns True if a leader was found and removed; False otherwise.
    """
    on_map_region = find_leader(state, faction)
    if on_map_region is not None:
        # Remove from map to Available, then transfer to removed_pieces.
        remove_piece(state, on_map_region, faction, LEADER)
        # The leader is now in Available; transfer it to removed_pieces.
        avail = state["available"].get(faction, {}).get(LEADER, 0)
        if avail > 0:
            state["available"][faction][LEADER] = avail - 1
            _ensure_removed(state, faction, LEADER, 1)
            return True
        # Diviciacus path: remove_piece for DIVICIACUS does NOT add to
        # Available — it just disappears. Mirror by directly recording.
        _ensure_removed(state, faction, LEADER, 1)
        return True
    # Not on map — check Available
    avail = state["available"].get(faction, {}).get(LEADER, 0)
    if avail > 0:
        state["available"][faction][LEADER] = avail - 1
        _ensure_removed(state, faction, LEADER, 1)
        return True
    return False


def _remove_warbands_anywhere(state, faction, count, rng, *,
                              to_removed=False,
                              region_order=None,
                              from_available_first=False):
    """Remove `count` warbands from anywhere (map + optionally Available).

    If from_available_first is True, draws from Available first.

    If to_removed is True, removed pieces go to removed_pieces (off the
    cap entirely). Otherwise to Available.

    If region_order is provided, drain regions in that order; else
    drain in random order, then Home Regions last (region_order None).

    Returns the number actually removed.
    """
    removed = 0
    if from_available_first:
        avail = state["available"].get(faction, {}).get(WARBAND, 0)
        take = min(avail, count - removed)
        if take > 0:
            state["available"][faction][WARBAND] = avail - take
            if to_removed:
                _ensure_removed(state, faction, WARBAND, take)
            removed += take

    if region_order is None:
        regions = [
            r for r in state["spaces"]
            if count_pieces(state, r, faction, WARBAND) > 0
        ]
        rng.shuffle(regions)
    else:
        regions = list(region_order)

    for region in regions:
        if removed >= count:
            break
        in_region = count_pieces(state, region, faction, WARBAND)
        if in_region <= 0:
            continue
        take = min(in_region, count - removed)
        # Remove from Hidden/Revealed/Scouted in order
        to_take = take
        for ps in (HIDDEN, REVEALED, SCOUTED):
            if to_take <= 0:
                break
            in_ps = count_pieces_by_state(
                state, region, faction, WARBAND, ps
            )
            t = min(in_ps, to_take)
            if t <= 0:
                continue
            remove_piece(
                state, region, faction, WARBAND, t,
                piece_state=ps,
                to_available=not to_removed,
            )
            if to_removed:
                _ensure_removed(state, faction, WARBAND, t)
            to_take -= t
        removed += (take - to_take)

    return removed


def _np_region_order(state, faction, *, home_last, rng,
                     home_regions=()):
    """Pick a random region-by-region order for NP force removal.

    Per A2.1: Non-players remove Region by Region at random, Home
    Regions last.
    """
    home = set(home_regions)
    pool_non_home = [
        r for r in state["spaces"]
        if r not in home and count_pieces(state, r, faction) > 0
    ]
    pool_home = [
        r for r in state["spaces"]
        if r in home and count_pieces(state, r, faction) > 0
    ]
    rng.shuffle(pool_non_home)
    rng.shuffle(pool_home)
    if home_last:
        return pool_non_home + pool_home
    return pool_home + pool_non_home


def _region_with_most_pieces(state, faction):
    """Return the region with the most pieces of a faction (random tiebreak)."""
    rng = state["rng"]
    candidates = []
    best = -1
    for region in state["spaces"]:
        n = count_pieces(state, region, faction)
        if n > best:
            best = n
            candidates = [region]
        elif n == best:
            candidates.append(region)
    if best <= 0 or not candidates:
        return None
    return rng.choice(candidates)


# ============================================================================
# STEP 0: Circumvallation cleanup (per "Adjust Forces" prelude)
# ============================================================================


def _step0_circumvallation(state):
    """Remove any Forces under a Circumvallation marker to Available,
    then remove the marker.

    Per the Interlude spec: "Remove any Forces under a Circumvallation
    marker to Available and remove the marker."
    """
    result = {"regions_cleared": []}
    markers = state.get("markers", {})
    for region in list(markers.keys()):
        rm = markers.get(region)
        if rm is None:
            continue
        has_cv = False
        if isinstance(rm, dict):
            has_cv = MARKER_CIRCUMVALLATION in rm
        elif isinstance(rm, set):
            has_cv = MARKER_CIRCUMVALLATION in rm
        if not has_cv:
            continue

        # Remove every mobile / non-permanent piece in this region to
        # Available. The Citadel-faction's pieces are the ones marked
        # by Circumvallation — but the prose says "any Forces under
        # the marker," which the rules use loosely. We remove
        # Warbands, Auxilia, Legions (to track), Allies, Citadels,
        # Forts (except the permanent Provincia Fort), and any Leader.
        space = state["spaces"].get(region, {})
        for faction in list(space.get("pieces", {}).keys()):
            # Warbands and Auxilia
            for pt in (WARBAND, AUXILIA):
                for ps in (HIDDEN, REVEALED, SCOUTED):
                    n = count_pieces_by_state(state, region, faction, pt, ps)
                    if n > 0:
                        remove_piece(
                            state, region, faction, pt, n,
                            piece_state=ps,
                        )
            # Allies, Citadels, Settlements
            for pt in (ALLY, CITADEL, SETTLEMENT):
                n = count_pieces(state, region, faction, pt)
                if n > 0:
                    remove_piece(state, region, faction, pt, n)
            # Forts (skip the permanent Provincia Fort)
            n_fort = count_pieces(state, region, faction, FORT)
            if n_fort > 0:
                if region == PROVINCIA:
                    extra = n_fort - 1
                    if extra > 0:
                        remove_piece(state, region, faction, FORT, extra)
                else:
                    remove_piece(state, region, faction, FORT, n_fort)
            # Legions -> Legions track
            n_leg = count_pieces(state, region, faction, LEGION)
            if n_leg > 0:
                remove_piece(
                    state, region, faction, LEGION, n_leg, to_track=True,
                )
            # Leader -> Available
            if get_leader_in_region(state, region, faction) is not None:
                remove_piece(state, region, faction, LEADER)

        # Remove the marker
        if isinstance(rm, dict):
            del rm[MARKER_CIRCUMVALLATION]
        elif isinstance(rm, set):
            rm.discard(MARKER_CIRCUMVALLATION)
        result["regions_cleared"].append(region)

    return result


# ============================================================================
# STEP 1: Winter Events
# ============================================================================


def _step1_winter_events(state):
    """Resolve Winter Uprising! and shaded Winter Campaign (in that order).

    These Events are stored as in-effect flags in state. We do NOT
    re-execute their card handlers; we simply record that they resolved
    here for the Interlude trace. Their persistent effects remain in
    'capabilities'/markers.

    Returns:
        Dict noting which events were resolved.
    """
    result = {"events_resolved": []}
    caps = state.get("capabilities", {})

    # Winter Uprising! is recorded both as a marker per A66 handler and
    # as a capability. Check either source.
    uprising_active = False
    if "A66" in caps:
        uprising_active = True
    markers = state.get("markers", {})
    for region_markers in markers.values():
        if isinstance(region_markers, dict):
            if MARKER_WINTER_UPRISING in region_markers:
                uprising_active = True
                break
        elif isinstance(region_markers, set):
            if MARKER_WINTER_UPRISING in region_markers:
                uprising_active = True
                break
    if uprising_active:
        result["events_resolved"].append("Winter Uprising!")

    # Shaded Winter Campaign — card 63 (base) or A63 (Ariovistus).
    from fs_bot.rules_consts import EVENT_SHADED
    if caps.get(63) == EVENT_SHADED or caps.get("A63") == EVENT_SHADED:
        result["events_resolved"].append("Winter Campaign (shaded)")

    return result


# ============================================================================
# STEP 2a: Adjust German Forces (player and NP)
# ============================================================================


def _adjust_german_forces(state):
    """Remove German pieces per Interlude spec.

    - Remove Germanic Leader and any 15 Germanic Warbands (incl. from
      Available) from play.
    - Replace each Settlement under Germanic Control with one German
      Ally at a Subdued Tribe in that Region if possible; otherwise
      replace with three Germanic Warbands. Remove all Settlements
      from play.
    - Remove at least 1/4 of total on-map Germanic Allies AND 1/4 of
      remaining Germanic Warbands on map to Available (Germania last).
    """
    rng = state["rng"]
    result = {
        "leader_removed": False,
        "warbands_removed_from_play": 0,
        "settlements_replaced_with_ally": [],
        "settlements_replaced_with_warbands": [],
        "settlements_removed_from_play": 0,
        "allies_to_available": 0,
        "warbands_to_available": 0,
    }
    from fs_bot.rules_consts import GERMANIC_CONTROL

    # 1. Remove Germanic Leader from play.
    if _remove_leader_from_play(state, GERMANS):
        result["leader_removed"] = True

    # 2. Remove any 15 Germanic Warbands from play (incl. Available).
    removed_wb = _remove_warbands_anywhere(
        state, GERMANS, INTERLUDE_GERMAN_WARBANDS_REMOVED, rng,
        to_removed=True, from_available_first=True,
    )
    result["warbands_removed_from_play"] = removed_wb

    # 3. Settlements
    settlements_total = 0
    for region in list(state["spaces"].keys()):
        n_set = count_pieces(state, region, GERMANS, SETTLEMENT)
        if n_set <= 0:
            continue
        settlements_total += n_set
        control = state["spaces"][region].get("control")
        if control == GERMANIC_CONTROL:
            # Try to place an Ally at a Subdued Tribe in this Region.
            from fs_bot.map.map_data import get_tribes_in_region
            tribes = get_tribes_in_region(region, state["scenario"])
            subdued_tribe = None
            for t in tribes:
                tinfo = state["tribes"].get(t)
                if tinfo and tinfo.get("status") is None \
                        and tinfo.get("allied_faction") is None:
                    subdued_tribe = t
                    break
            if subdued_tribe is not None and \
                    get_available(state, GERMANS, ALLY) > 0:
                # Replace settlement with Ally
                remove_piece(
                    state, region, GERMANS, SETTLEMENT, n_set,
                )
                state["tribes"][subdued_tribe]["status"] = "Allied"
                state["tribes"][subdued_tribe]["allied_faction"] = GERMANS
                place_piece(state, region, GERMANS, ALLY, 1)
                result["settlements_replaced_with_ally"].append(region)
            else:
                # Replace with 3 Warbands
                remove_piece(
                    state, region, GERMANS, SETTLEMENT, n_set,
                )
                avail_wb = get_available(state, GERMANS, WARBAND)
                place_n = min(3, avail_wb)
                if place_n > 0:
                    place_piece(state, region, GERMANS, WARBAND, place_n)
                result["settlements_replaced_with_warbands"].append(
                    (region, place_n)
                )
        else:
            # Non-Germanic-Control — replace with 3 Warbands too
            remove_piece(
                state, region, GERMANS, SETTLEMENT, n_set,
            )
            avail_wb = get_available(state, GERMANS, WARBAND)
            place_n = min(3, avail_wb)
            if place_n > 0:
                place_piece(state, region, GERMANS, WARBAND, place_n)
            result["settlements_replaced_with_warbands"].append(
                (region, place_n)
            )

    # All Settlements are now off the board. Remove from play permanently.
    settlements_in_avail = state["available"].get(
        GERMANS, {}
    ).get(SETTLEMENT, 0)
    if settlements_in_avail > 0:
        # The Available count grew because of the remove_piece calls
        # above (default to_available=True for Settlement). Move all
        # available Settlements to removed_pieces.
        state["available"][GERMANS][SETTLEMENT] = 0
        _ensure_removed(state, GERMANS, SETTLEMENT, settlements_in_avail)
    result["settlements_removed_from_play"] = settlements_in_avail

    # 4. Remove >= 1/4 of total on-map Germanic Allies and 1/4 of
    #    Germanic Warbands on map (Germania last) to Available.
    total_allies = 0
    for region in state["spaces"]:
        total_allies += count_pieces(state, region, GERMANS, ALLY)
    need_allies = _fraction_to_remove(total_allies, 0.25)

    total_wb_map = 0
    for region in state["spaces"]:
        total_wb_map += count_pieces(state, region, GERMANS, WARBAND)
    need_wb = _fraction_to_remove(total_wb_map, 0.25)

    region_order = _np_region_order(
        state, GERMANS, home_last=True, rng=rng,
        home_regions=GERMAN_HOME_REGIONS_BASE,
    )

    # Remove Allies
    allies_removed = 0
    for region in region_order:
        if allies_removed >= need_allies:
            break
        n = count_pieces(state, region, GERMANS, ALLY)
        take = min(n, need_allies - allies_removed)
        for _ in range(take):
            remove_piece(state, region, GERMANS, ALLY)
            # Also un-ally a tribe in this region attached to GERMANS
            from fs_bot.map.map_data import get_tribes_in_region
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") == GERMANS:
                    ti["status"] = None
                    ti["allied_faction"] = None
                    break
        allies_removed += take
    result["allies_to_available"] = allies_removed

    # Remove Warbands
    wb_removed = _remove_warbands_anywhere(
        state, GERMANS, need_wb, rng,
        to_removed=False, region_order=region_order,
    )
    result["warbands_to_available"] = wb_removed

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 2b: Belgae
# ============================================================================


def _adjust_belgae_forces(state):
    """Belgae: remove >= 1/2 of on-map Allies + 1/2 of on-map Warbands,
    Belgica last. Place Ambiorix in region with most other Belgic pieces.
    """
    rng = state["rng"]
    result = {
        "allies_to_available": 0,
        "warbands_to_available": 0,
        "ambiorix_placed": None,
    }
    from fs_bot.map.map_data import get_tribes_in_region

    total_allies = 0
    for region in state["spaces"]:
        total_allies += count_pieces(state, region, BELGAE, ALLY)
    need_allies = _fraction_to_remove(total_allies, 0.5)

    total_wb = 0
    for region in state["spaces"]:
        total_wb += count_pieces(state, region, BELGAE, WARBAND)
    need_wb = _fraction_to_remove(total_wb, 0.5)

    region_order = _np_region_order(
        state, BELGAE, home_last=True, rng=rng,
        home_regions=BELGAE_HOME_REGIONS,
    )

    allies_removed = 0
    for region in region_order:
        if allies_removed >= need_allies:
            break
        n = count_pieces(state, region, BELGAE, ALLY)
        take = min(n, need_allies - allies_removed)
        for _ in range(take):
            remove_piece(state, region, BELGAE, ALLY)
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") == BELGAE:
                    ti["status"] = None
                    ti["allied_faction"] = None
                    break
        allies_removed += take
    result["allies_to_available"] = allies_removed

    wb_removed = _remove_warbands_anywhere(
        state, BELGAE, need_wb, rng,
        to_removed=False, region_order=region_order,
    )
    result["warbands_to_available"] = wb_removed

    # Place Ambiorix in Region with most other Belgic pieces (even if
    # currently in Available). Use the Belgic Leader piece (currently
    # named BODUOGNATUS in Ariovistus first-half setup; the prose names
    # the second-half identity Ambiorix). We re-place it with the
    # leader name that reflects what's on the piece now, falling back
    # to AMBIORIX if no leader was placed before.
    current_region = find_leader(state, BELGAE)
    leader_name = AMBIORIX
    if current_region is not None:
        cur_name = get_leader_in_region(state, current_region, BELGAE)
        # Force "Ambiorix" identity for the second half — the piece is
        # the same physical Belgic Leader.
        if cur_name == BODUOGNATUS:
            leader_name = AMBIORIX
        else:
            leader_name = cur_name or AMBIORIX
        # Remove leader from current region back to Available.
        remove_piece(state, current_region, BELGAE, LEADER)
    target = _region_with_most_pieces(state, BELGAE)
    if target is not None and \
            state["available"].get(BELGAE, {}).get(LEADER, 0) > 0:
        place_piece(
            state, target, BELGAE, LEADER, leader_name=leader_name,
        )
        result["ambiorix_placed"] = target

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 2c: Aedui
# ============================================================================


def _adjust_aedui_forces(state):
    """Aedui adjustments.

    - Remove Diviciacus piece from play (may return by Event).
    - Replace 1 Aedui Citadel with an Aedui Ally (Bibracte last; remove
      if no Aedui Allies Available).
    - Remove >= 1/2 of on-map Allies (not Citadels) + 1/2 of Warbands
      to Available (Aedui Region last).
    - If no Aedui Ally or Citadel at Bibracte, remove whatever is
      there and place Aedui Ally there.
    """
    rng = state["rng"]
    result = {
        "diviciacus_removed": False,
        "citadel_replaced_region": None,
        "citadel_removed_region": None,
        "allies_to_available": 0,
        "warbands_to_available": 0,
        "bibracte_replaced": False,
    }
    from fs_bot.map.map_data import get_tribes_in_region

    # Diviciacus removal — A1.4
    aedui_leader_region = find_leader(state, AEDUI)
    if aedui_leader_region is not None:
        leader_name = get_leader_in_region(
            state, aedui_leader_region, AEDUI,
        )
        if leader_name == DIVICIACUS:
            # remove_piece for DIVICIACUS does NOT add to Available,
            # but does set the leader slot to None.
            remove_piece(state, aedui_leader_region, AEDUI, LEADER)
            state["diviciacus_in_play"] = False
            result["diviciacus_removed"] = True

    # Replace 1 Aedui Citadel with an Aedui Ally (Bibracte last).
    citadel_regions = [
        r for r in state["spaces"]
        if count_pieces(state, r, AEDUI, CITADEL) > 0
    ]
    non_bibracte = [r for r in citadel_regions if r != AEDUI_REGION]
    bibracte = [r for r in citadel_regions if r == AEDUI_REGION]
    rng.shuffle(non_bibracte)
    rng.shuffle(bibracte)
    citadel_pick_order = non_bibracte + bibracte
    if citadel_pick_order:
        target = citadel_pick_order[0]
        remove_piece(state, target, AEDUI, CITADEL)
        if get_available(state, AEDUI, ALLY) > 0:
            place_piece(state, target, AEDUI, ALLY, 1)
            # Allied tribe attachment: pick the first subdued tribe.
            tribes = get_tribes_in_region(target, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") is None:
                    ti["status"] = "Allied"
                    ti["allied_faction"] = AEDUI
                    break
            result["citadel_replaced_region"] = target
        else:
            result["citadel_removed_region"] = target

    # Remove >= 1/2 of on-map Aedui Allies (not Citadels) and 1/2 of
    # Warbands to Available (Aedui Region last).
    total_allies = 0
    for region in state["spaces"]:
        total_allies += count_pieces(state, region, AEDUI, ALLY)
    need_allies = _fraction_to_remove(total_allies, 0.5)

    total_wb = 0
    for region in state["spaces"]:
        total_wb += count_pieces(state, region, AEDUI, WARBAND)
    need_wb = _fraction_to_remove(total_wb, 0.5)

    region_order = _np_region_order(
        state, AEDUI, home_last=True, rng=rng,
        home_regions=AEDUI_HOME_REGIONS,
    )

    allies_removed = 0
    for region in region_order:
        if allies_removed >= need_allies:
            break
        n = count_pieces(state, region, AEDUI, ALLY)
        take = min(n, need_allies - allies_removed)
        for _ in range(take):
            remove_piece(state, region, AEDUI, ALLY)
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") == AEDUI:
                    ti["status"] = None
                    ti["allied_faction"] = None
                    break
        allies_removed += take
    result["allies_to_available"] = allies_removed

    wb_removed = _remove_warbands_anywhere(
        state, AEDUI, need_wb, rng,
        to_removed=False, region_order=region_order,
    )
    result["warbands_to_available"] = wb_removed

    # Bibracte rule: if no Aedui Ally or Citadel at Bibracte, remove
    # whatever is there and place an Aedui Ally there.
    bib_allies = count_pieces(state, AEDUI_REGION, AEDUI, ALLY)
    bib_citadels = count_pieces(state, AEDUI_REGION, AEDUI, CITADEL)
    if bib_allies == 0 and bib_citadels == 0:
        # Remove every non-permanent piece in the Aedui Region.
        space = state["spaces"].get(AEDUI_REGION, {})
        for faction in list(space.get("pieces", {}).keys()):
            for pt in (WARBAND, AUXILIA):
                for ps in (HIDDEN, REVEALED, SCOUTED):
                    n = count_pieces_by_state(
                        state, AEDUI_REGION, faction, pt, ps,
                    )
                    if n > 0:
                        remove_piece(
                            state, AEDUI_REGION, faction, pt, n,
                            piece_state=ps,
                        )
            for pt in (ALLY, CITADEL, SETTLEMENT):
                n = count_pieces(state, AEDUI_REGION, faction, pt)
                if n > 0:
                    remove_piece(
                        state, AEDUI_REGION, faction, pt, n,
                    )
            n_fort = count_pieces(state, AEDUI_REGION, faction, FORT)
            if n_fort > 0:
                remove_piece(state, AEDUI_REGION, faction, FORT, n_fort)
            n_leg = count_pieces(state, AEDUI_REGION, faction, LEGION)
            if n_leg > 0:
                remove_piece(
                    state, AEDUI_REGION, faction, LEGION, n_leg,
                    to_track=True,
                )
            if get_leader_in_region(
                state, AEDUI_REGION, faction,
            ) is not None:
                remove_piece(state, AEDUI_REGION, faction, LEADER)
        # Then place an Aedui Ally.
        if get_available(state, AEDUI, ALLY) > 0:
            place_piece(state, AEDUI_REGION, AEDUI, ALLY, 1)
            # Allied tribe attachment
            tribes = get_tribes_in_region(AEDUI_REGION, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") is None:
                    ti["status"] = "Allied"
                    ti["allied_faction"] = AEDUI
                    break
            result["bibracte_replaced"] = True

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 2d: Arverni (German player slot, soon to be Arverni)
# ============================================================================


def _adjust_arverni_forces(state):
    """Arverni adjustments per Interlude (German player carries these out).

    - Place Vercingetorix in the Winter track Spring box.
    - Replace 2 Arverni Citadels (Gergovia last) with Arverni Allies
      (or remove if no Allies Available).
    - Remove >= 1/2 of on-map Arverni Allies (not Citadels) + 1/2 of
      Arverni Warbands to Available. Cadurci and Volcae Allies may be
      removed first (otherwise the Arverni Region last).
    - If no Arverni Ally or Citadel at Gergovia, remove whatever is
      there and place Arverni Ally there.
    - Place Arverni Warbands in the Arverni Region until at least 3
      are there.
    """
    rng = state["rng"]
    result = {
        "vercingetorix_in_spring_box": False,
        "citadels_replaced": [],
        "citadels_removed": [],
        "allies_to_available": 0,
        "warbands_to_available": 0,
        "gergovia_replaced": False,
        "warbands_placed_in_arverni": 0,
    }
    from fs_bot.map.map_data import get_tribes_in_region

    # 1. Place Vercingetorix in the Winter track Spring box.
    # In Ariovistus VERCINGETORIX is not used; he becomes a piece for
    # the second half. Available count starts at 0 in Ariovistus caps
    # because Arverni has no Leader cap in the Ariovistus piece pool.
    # We add him to spring_box_leaders. Validation accepts this.
    sb = state.setdefault("spring_box_leaders", [])
    if VERCINGETORIX not in sb:
        sb.append(VERCINGETORIX)
        result["vercingetorix_in_spring_box"] = True

    # 2. Replace 2 Arverni Citadels (Gergovia last).
    citadel_regions = [
        r for r in state["spaces"]
        if count_pieces(state, r, ARVERNI, CITADEL) > 0
    ]
    non_gergovia = [r for r in citadel_regions if r != ARVERNI_REGION]
    gergovia = [r for r in citadel_regions if r == ARVERNI_REGION]
    rng.shuffle(non_gergovia)
    rng.shuffle(gergovia)
    pick_order = non_gergovia + gergovia
    to_replace = 0
    for region in pick_order:
        if to_replace >= 2:
            break
        # Replace 1 Citadel (might exist multiple per region in theory).
        n = count_pieces(state, region, ARVERNI, CITADEL)
        if n <= 0:
            continue
        remove_piece(state, region, ARVERNI, CITADEL, 1)
        if get_available(state, ARVERNI, ALLY) > 0:
            place_piece(state, region, ARVERNI, ALLY, 1)
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") is None:
                    ti["status"] = "Allied"
                    ti["allied_faction"] = ARVERNI
                    break
            result["citadels_replaced"].append(region)
        else:
            result["citadels_removed"].append(region)
        to_replace += 1

    # 3. Remove >= 1/2 of on-map Arverni Allies and 1/2 of Warbands.
    # Cadurci/Volcae Allies may be removed first; otherwise Arverni
    # Region last.
    total_allies = 0
    for region in state["spaces"]:
        total_allies += count_pieces(state, region, ARVERNI, ALLY)
    need_allies = _fraction_to_remove(total_allies, 0.5)

    total_wb = 0
    for region in state["spaces"]:
        total_wb += count_pieces(state, region, ARVERNI, WARBAND)
    need_wb = _fraction_to_remove(total_wb, 0.5)

    # Build allies-removal order: Cadurci/Volcae regions first, then
    # random non-home regions, then Arverni Home Regions last (Arverni
    # Region absolutely last).
    cadurci_region = TRIBE_TO_REGION.get(TRIBE_CADURCI)
    volcae_region = TRIBE_TO_REGION.get(TRIBE_VOLCAE)
    arverni_home = set(ARVERNI_HOME_REGIONS_ARIOVISTUS)

    priority_alts = []
    if cadurci_region and \
            state["tribes"].get(TRIBE_CADURCI, {}).get(
                "allied_faction") == ARVERNI:
        priority_alts.append(cadurci_region)
    if volcae_region and \
            state["tribes"].get(TRIBE_VOLCAE, {}).get(
                "allied_faction") == ARVERNI:
        priority_alts.append(volcae_region)

    other_non_home = [
        r for r in state["spaces"]
        if r not in arverni_home and r not in priority_alts
        and count_pieces(state, r, ARVERNI) > 0
    ]
    rng.shuffle(other_non_home)

    home_non_arv = [
        r for r in ARVERNI_HOME_REGIONS_ARIOVISTUS
        if r != ARVERNI_REGION
        and count_pieces(state, r, ARVERNI) > 0
    ]
    rng.shuffle(home_non_arv)

    arv_region_last = (
        [ARVERNI_REGION]
        if count_pieces(state, ARVERNI_REGION, ARVERNI) > 0
        else []
    )

    allies_order = (
        priority_alts + other_non_home + home_non_arv + arv_region_last
    )

    allies_removed = 0
    for region in allies_order:
        if allies_removed >= need_allies:
            break
        n = count_pieces(state, region, ARVERNI, ALLY)
        take = min(n, need_allies - allies_removed)
        for _ in range(take):
            remove_piece(state, region, ARVERNI, ALLY)
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") == ARVERNI:
                    ti["status"] = None
                    ti["allied_faction"] = None
                    break
        allies_removed += take
    result["allies_to_available"] = allies_removed

    # Warbands order: same priorities — Cadurci/Volcae Regions first,
    # else random non-home, else Arverni Home (Arverni Region last).
    wb_priority = [
        r for r in priority_alts
        if count_pieces(state, r, ARVERNI, WARBAND) > 0
    ]
    wb_other = [
        r for r in other_non_home
        if count_pieces(state, r, ARVERNI, WARBAND) > 0
    ]
    wb_home_non_arv = [
        r for r in home_non_arv
        if count_pieces(state, r, ARVERNI, WARBAND) > 0
    ]
    wb_arv_last = [
        r for r in arv_region_last
        if count_pieces(state, r, ARVERNI, WARBAND) > 0
    ]
    wb_order = wb_priority + wb_other + wb_home_non_arv + wb_arv_last

    wb_removed = _remove_warbands_anywhere(
        state, ARVERNI, need_wb, rng,
        to_removed=False, region_order=wb_order,
    )
    result["warbands_to_available"] = wb_removed

    # 4. Gergovia rule.
    g_allies = count_pieces(state, ARVERNI_REGION, ARVERNI, ALLY)
    g_citadels = count_pieces(state, ARVERNI_REGION, ARVERNI, CITADEL)
    if g_allies == 0 and g_citadels == 0:
        space = state["spaces"].get(ARVERNI_REGION, {})
        for faction in list(space.get("pieces", {}).keys()):
            for pt in (WARBAND, AUXILIA):
                for ps in (HIDDEN, REVEALED, SCOUTED):
                    n = count_pieces_by_state(
                        state, ARVERNI_REGION, faction, pt, ps,
                    )
                    if n > 0:
                        remove_piece(
                            state, ARVERNI_REGION, faction, pt, n,
                            piece_state=ps,
                        )
            for pt in (ALLY, CITADEL, SETTLEMENT):
                n = count_pieces(state, ARVERNI_REGION, faction, pt)
                if n > 0:
                    remove_piece(
                        state, ARVERNI_REGION, faction, pt, n,
                    )
            n_fort = count_pieces(state, ARVERNI_REGION, faction, FORT)
            if n_fort > 0:
                remove_piece(
                    state, ARVERNI_REGION, faction, FORT, n_fort,
                )
            n_leg = count_pieces(state, ARVERNI_REGION, faction, LEGION)
            if n_leg > 0:
                remove_piece(
                    state, ARVERNI_REGION, faction, LEGION, n_leg,
                    to_track=True,
                )
            if get_leader_in_region(
                state, ARVERNI_REGION, faction,
            ) is not None:
                remove_piece(state, ARVERNI_REGION, faction, LEADER)
        if get_available(state, ARVERNI, ALLY) > 0:
            place_piece(state, ARVERNI_REGION, ARVERNI, ALLY, 1)
            tribes = get_tribes_in_region(
                ARVERNI_REGION, state["scenario"],
            )
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") is None:
                    ti["status"] = "Allied"
                    ti["allied_faction"] = ARVERNI
                    break
            result["gergovia_replaced"] = True

    # 5. Place Arverni Warbands in Arverni Region until >= 3.
    current_wb = count_pieces(state, ARVERNI_REGION, ARVERNI, WARBAND)
    need = max(0, 3 - current_wb)
    avail = get_available(state, ARVERNI, WARBAND)
    place_n = min(need, avail)
    if place_n > 0:
        place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, place_n)
        result["warbands_placed_in_arverni"] = place_n

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 2e: Roman
# ============================================================================


def _adjust_roman_forces(state):
    """Roman adjustments.

    - Remove >= 1/2 of on-map Forts excluding Provincia's, 1/2 of
      Roman Allies, and 1/2 of Auxilia (no Legions; Provincia last).
    - If Roman Leader in Available, place Caesar in Provincia if
      Roman Control, otherwise in Region with most Roman pieces.
    """
    from fs_bot.rules_consts import ROMAN_CONTROL
    rng = state["rng"]
    result = {
        "forts_to_available": 0,
        "allies_to_available": 0,
        "auxilia_to_available": 0,
        "caesar_placed": None,
    }
    from fs_bot.map.map_data import get_tribes_in_region

    # Count Forts (excluding Provincia's permanent Fort).
    total_forts = 0
    for region in state["spaces"]:
        n = count_pieces(state, region, ROMANS, FORT)
        if region == PROVINCIA:
            n = max(0, n - 1)
        total_forts += n
    need_forts = _fraction_to_remove(total_forts, 0.5)

    total_allies = 0
    for region in state["spaces"]:
        total_allies += count_pieces(state, region, ROMANS, ALLY)
    need_allies = _fraction_to_remove(total_allies, 0.5)

    total_aux = 0
    for region in state["spaces"]:
        total_aux += count_pieces(state, region, ROMANS, AUXILIA)
    need_aux = _fraction_to_remove(total_aux, 0.5)

    region_order = _np_region_order(
        state, ROMANS, home_last=True, rng=rng,
        home_regions=ROMAN_HOME_REGIONS,
    )

    # Forts
    forts_removed = 0
    for region in region_order:
        if forts_removed >= need_forts:
            break
        n = count_pieces(state, region, ROMANS, FORT)
        if region == PROVINCIA:
            n = max(0, n - 1)  # Don't touch the permanent Fort
        take = min(n, need_forts - forts_removed)
        for _ in range(take):
            remove_piece(state, region, ROMANS, FORT)
        forts_removed += take
    result["forts_to_available"] = forts_removed

    # Allies
    allies_removed = 0
    for region in region_order:
        if allies_removed >= need_allies:
            break
        n = count_pieces(state, region, ROMANS, ALLY)
        take = min(n, need_allies - allies_removed)
        for _ in range(take):
            remove_piece(state, region, ROMANS, ALLY)
            tribes = get_tribes_in_region(region, state["scenario"])
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") == ROMANS:
                    ti["status"] = None
                    ti["allied_faction"] = None
                    break
        allies_removed += take
    result["allies_to_available"] = allies_removed

    # Auxilia
    aux_removed = 0
    for region in region_order:
        if aux_removed >= need_aux:
            break
        # Remove from Hidden first, then Revealed, then Scouted.
        n_total = count_pieces(state, region, ROMANS, AUXILIA)
        take = min(n_total, need_aux - aux_removed)
        to_take = take
        for ps in (HIDDEN, REVEALED, SCOUTED):
            if to_take <= 0:
                break
            in_ps = count_pieces_by_state(
                state, region, ROMANS, AUXILIA, ps,
            )
            t = min(in_ps, to_take)
            if t > 0:
                remove_piece(
                    state, region, ROMANS, AUXILIA, t, piece_state=ps,
                )
                to_take -= t
        aux_removed += (take - to_take)
    result["auxilia_to_available"] = aux_removed

    # Caesar placement.
    caesar_region = find_leader(state, ROMANS)
    if caesar_region is None and \
            state["available"].get(ROMANS, {}).get(LEADER, 0) > 0:
        refresh_all_control(state)
        prov_control = state["spaces"].get(PROVINCIA, {}).get("control")
        if prov_control == ROMAN_CONTROL:
            place_piece(
                state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR,
            )
            result["caesar_placed"] = PROVINCIA
        else:
            target = _region_with_most_pieces(state, ROMANS)
            if target is not None:
                place_piece(
                    state, target, ROMANS, LEADER, leader_name=CAESAR,
                )
                result["caesar_placed"] = target

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 2f: Cisalpina relocation
# ============================================================================


def _cisalpina_relocation(state):
    """Unless Gallia Togata is in effect, factions relocate forces from
    Cisalpina to Home Regions (Ally to Subdued Tribe only) or remove them.

    Faction order: German -> Belgae -> Aedui -> Arverni -> Roman.
    (The Interlude text says "Factions in the above order".)
    """
    result = {"skipped": False, "removed": {}}
    # Gallia Togata gate
    caps = state.get("capabilities", {})
    if 5 in caps or "A5" in caps:
        result["skipped"] = True
        return result
    markers = state.get("markers", {})
    cis_markers = markers.get(CISALPINA, {})
    has_togata = False
    if isinstance(cis_markers, dict):
        has_togata = MARKER_GALLIA_TOGATA in cis_markers
    elif isinstance(cis_markers, set):
        has_togata = MARKER_GALLIA_TOGATA in cis_markers
    if has_togata:
        result["skipped"] = True
        return result

    # Faction order
    order = (GERMANS, BELGAE, AEDUI, ARVERNI, ROMANS)
    space = state["spaces"].get(CISALPINA, {})
    if not space:
        return result
    pieces = space.get("pieces", {})
    for faction in order:
        f_pieces = pieces.get(faction)
        if not f_pieces:
            continue
        removed_here = 0
        # Warbands and Auxilia
        for pt in (WARBAND, AUXILIA):
            for ps in (HIDDEN, REVEALED, SCOUTED):
                n = count_pieces_by_state(
                    state, CISALPINA, faction, pt, ps,
                )
                if n > 0:
                    remove_piece(
                        state, CISALPINA, faction, pt, n,
                        piece_state=ps,
                    )
                    removed_here += n
        # Allies / Citadels / Settlements all removed (we can't easily
        # "relocate Ally to Subdued Tribe" without choosing a target;
        # leave them removed to Available for simplicity per the
        # second clause: "or remove them").
        for pt in (ALLY, CITADEL, SETTLEMENT):
            n = count_pieces(state, CISALPINA, faction, pt)
            if n > 0:
                remove_piece(state, CISALPINA, faction, pt, n)
                if pt == ALLY:
                    from fs_bot.map.map_data import get_tribes_in_region
                    tribes = get_tribes_in_region(
                        CISALPINA, state["scenario"],
                    )
                    for t in tribes:
                        ti = state["tribes"].get(t)
                        if ti and ti.get("allied_faction") == faction:
                            ti["status"] = None
                            ti["allied_faction"] = None
                            break
                removed_here += n
        # Legions -> back to track
        n_leg = count_pieces(state, CISALPINA, faction, LEGION)
        if n_leg > 0:
            remove_piece(
                state, CISALPINA, faction, LEGION, n_leg,
                to_track=True,
            )
            removed_here += n_leg
        # Leader -> Available
        if get_leader_in_region(state, CISALPINA, faction) is not None:
            remove_piece(state, CISALPINA, faction, LEADER)
            removed_here += 1
        if removed_here > 0:
            result["removed"][faction] = removed_here

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 3: Britannia Expedition
# ============================================================================


def _np_should_conduct_britannia(state):
    """A8.8.9 / Interlude rule: NP Romans conduct expedition if able.

    Per A2.1: 'Non-player Romans conduct it if able, A8.8.9.'
    A8.8.9 does not exist in the reference documents (Chapter A8 stops at
    A8.8.8, then jumps to A8.9) — the cited rule is missing, so there is no
    additional strategic/score criterion to apply. "If able" is therefore
    resolved against the physical requirements the scenario itself states:
    the Romans must move 3 Legions to the Harvest-Phase box PLUS the Roman
    Leader, 3 or more further Legions, and 1 or more Auxilia to Britannia.
    Thus NP Romans conduct the expedition iff they have those pieces on the
    map: >= 6 Legions, >= 1 Auxilia, and the Roman Leader. See QUESTIONS.md.
    """
    # The scenario requires "the Roman Leader ... from the map to Britannia".
    if find_leader(state, ROMANS) is None:
        return False
    legions_on_map = 0
    aux_on_map = 0
    for region in state["spaces"]:
        legions_on_map += count_pieces(state, region, ROMANS, LEGION)
        aux_on_map += count_pieces(state, region, ROMANS, AUXILIA)
    need_legions = (
        BRITANNIA_EXPEDITION_LEGIONS_TO_TRACK
        + BRITANNIA_EXPEDITION_MIN_LEGIONS_TO_BRITANNIA
    )
    if legions_on_map < need_legions:
        return False
    if aux_on_map < BRITANNIA_EXPEDITION_MIN_AUXILIA_TO_BRITANNIA:
        return False
    return True


def _shift_senate_one_box(state, direction):
    """Shift Senate marker one box up (toward Uproar) or down (toward
    Adulation), with flip behavior per A6.5.1 / §6.5.1.
    """
    pos = state["senate"]["position"]
    is_firm = state["senate"]["firm"]
    if pos is None:
        # Not on track (e.g. Pax Gallica setup pre-1st-Winter); set to
        # Intrigue per §6.5.1 conservative default and ignore shift.
        state["senate"]["position"] = INTRIGUE
        return
    idx_map = {p: i for i, p in enumerate(SENATE_POSITIONS)}
    idx = idx_map[pos]
    if direction == "up":
        if idx == 0:
            # Already at Uproar — flip Firm if not yet
            if not is_firm:
                state["senate"]["firm"] = True
            return
        if is_firm:
            state["senate"]["firm"] = False
            return
        state["senate"]["position"] = SENATE_POSITIONS[idx - 1]
    elif direction == "down":
        if idx == len(SENATE_POSITIONS) - 1:
            if not is_firm:
                state["senate"]["firm"] = True
            return
        if is_firm:
            state["senate"]["firm"] = False
            return
        state["senate"]["position"] = SENATE_POSITIONS[idx + 1]


def _step3_britannia(state, britannia_decision, roman_dispersed_keep=None):
    """Britannia Expedition step.

    britannia_decision may be:
        - None: use NP logic (A8.8.9 / "conduct if able")
        - True: conduct (player Roman chose to)
        - False: decline
        - dict: {"conduct": bool, "legions_from": {region: count}, ...}
          for player-customized choices (only "conduct" is required).
    """
    from fs_bot.rules_consts import ROMAN_CONTROL, BELGIC_CONTROL

    result = {
        "conducted": False,
        "decision_source": "np",
        "legions_to_harvest_box": 0,
        "legions_to_britannia": 0,
        "auxilia_to_britannia": 0,
        "caesar_to_britannia": False,
        "belgic_in_britannia": False,
        "senate_shift": None,
    }

    # Resolve decision
    if britannia_decision is None:
        conduct = _np_should_conduct_britannia(state)
        result["decision_source"] = "np"
    elif isinstance(britannia_decision, bool):
        conduct = britannia_decision
        result["decision_source"] = "player_bool"
        # If a player wants to conduct but is unable, refuse.
        if conduct and not _np_should_conduct_britannia(state):
            conduct = False
            result["decision_source"] = "player_unable"
    elif isinstance(britannia_decision, dict):
        conduct = bool(britannia_decision.get("conduct", False))
        result["decision_source"] = "player_dict"
        if conduct and not _np_should_conduct_britannia(state):
            conduct = False
            result["decision_source"] = "player_unable"
    else:
        conduct = bool(britannia_decision)

    if conduct:
        result["conducted"] = True
        # Place 3 Legions onto Winter track's Harvest Phase box.
        # We use the existing winter_track_legions field for this.
        need = BRITANNIA_EXPEDITION_LEGIONS_TO_TRACK
        for region in list(state["spaces"].keys()):
            if need <= 0:
                break
            n = count_pieces(state, region, ROMANS, LEGION)
            take = min(n, need)
            if take > 0:
                # Remove from map -> they sit on the Winter Track.
                # Use to_removed=False: we send them through Fallen as
                # transit, then re-shelf them as winter_track_legions.
                space = state["spaces"][region]["pieces"][ROMANS]
                space[LEGION] = space.get(LEGION, 0) - take
                state["winter_track_legions"] = (
                    state.get("winter_track_legions", 0) + take
                )
                result["legions_to_harvest_box"] += take
                need -= take

        # Caesar to Britannia (from wherever he is; from Available if
        # not on map -- in which case we still need to bring him out).
        caesar_region = find_leader(state, ROMANS)
        if caesar_region is not None and caesar_region != BRITANNIA:
            move_piece(state, caesar_region, BRITANNIA, ROMANS, LEADER)
            result["caesar_to_britannia"] = True
        elif caesar_region == BRITANNIA:
            result["caesar_to_britannia"] = True
        elif state["available"].get(ROMANS, {}).get(LEADER, 0) > 0:
            place_piece(
                state, BRITANNIA, ROMANS, LEADER, leader_name=CAESAR,
            )
            result["caesar_to_britannia"] = True

        # 3+ Legions to Britannia
        need_legions_b = BRITANNIA_EXPEDITION_MIN_LEGIONS_TO_BRITANNIA
        for region in list(state["spaces"].keys()):
            if need_legions_b <= 0:
                break
            if region == BRITANNIA:
                continue
            n = count_pieces(state, region, ROMANS, LEGION)
            take = min(n, need_legions_b)
            if take > 0:
                move_piece(
                    state, region, BRITANNIA, ROMANS, LEGION, take,
                )
                result["legions_to_britannia"] += take
                need_legions_b -= take

        # 1+ Auxilia to Britannia
        need_aux = BRITANNIA_EXPEDITION_MIN_AUXILIA_TO_BRITANNIA
        for region in list(state["spaces"].keys()):
            if need_aux <= 0:
                break
            if region == BRITANNIA:
                continue
            for ps in (HIDDEN, REVEALED, SCOUTED):
                n = count_pieces_by_state(
                    state, region, ROMANS, AUXILIA, ps,
                )
                t = min(n, need_aux)
                if t > 0:
                    move_piece(
                        state, region, BRITANNIA, ROMANS, AUXILIA, t,
                        piece_state=ps,
                    )
                    need_aux -= t
                    result["auxilia_to_britannia"] += t
                if need_aux <= 0:
                    break

        # Senate shift 1 box down (toward Adulation)
        _shift_senate_one_box(state, "down")
        result["senate_shift"] = "down"
    else:
        # Decline / unable: no change to Roman forces; place 1 Belgic
        # Ally + 2 Belgic Warbands (and Belgic Control) in Britannia.
        from fs_bot.rules_consts import TRIBE_CATUVELLAUNI
        # Find a subdued tribe in Britannia to ally
        from fs_bot.map.map_data import get_tribes_in_region
        tribes = get_tribes_in_region(BRITANNIA, state["scenario"])
        if get_available(state, BELGAE, ALLY) > 0:
            place_piece(state, BRITANNIA, BELGAE, ALLY, 1)
            for t in tribes:
                ti = state["tribes"].get(t)
                if ti and ti.get("allied_faction") is None:
                    ti["status"] = "Allied"
                    ti["allied_faction"] = BELGAE
                    break
        avail_wb = get_available(state, BELGAE, WARBAND)
        place_wb = min(2, avail_wb)
        if place_wb > 0:
            place_piece(state, BRITANNIA, BELGAE, WARBAND, place_wb)
        result["belgic_in_britannia"] = True

        # Senate shift 1 box up (toward Uproar)
        _shift_senate_one_box(state, "up")
        result["senate_shift"] = "up"

    refresh_all_control(state)
    return result


# ============================================================================
# STEP 4: Markers cleanup
# ============================================================================


def _step4_markers_cleanup(state):
    """Remove the Arverni Home 'Rally', 'Britannia (Not in play)', Nori
    tribe, Cisalpina Control box, and all Intimidated markers.
    """
    result = {
        "rally_markers_removed": [],
        "britannia_not_in_play_removed": False,
        "nori_marker_removed": False,
        "cisalpina_control_box_removed": False,
        "intimidated_removed": [],
    }
    markers = state.get("markers", {})
    targets_to_remove = (
        MARKER_ARVERNI_RALLY, MARKER_BRITANNIA_NOT_IN_PLAY,
        MARKER_NORI, MARKER_CISALPINA_CONTROL_BOX,
        MARKER_INTIMIDATED,
    )
    for region in list(markers.keys()):
        rm = markers.get(region)
        if rm is None:
            continue
        if isinstance(rm, dict):
            if MARKER_ARVERNI_RALLY in rm:
                del rm[MARKER_ARVERNI_RALLY]
                result["rally_markers_removed"].append(region)
            if MARKER_BRITANNIA_NOT_IN_PLAY in rm:
                del rm[MARKER_BRITANNIA_NOT_IN_PLAY]
                result["britannia_not_in_play_removed"] = True
            if MARKER_NORI in rm:
                del rm[MARKER_NORI]
                result["nori_marker_removed"] = True
            if MARKER_CISALPINA_CONTROL_BOX in rm:
                del rm[MARKER_CISALPINA_CONTROL_BOX]
                result["cisalpina_control_box_removed"] = True
            if MARKER_INTIMIDATED in rm:
                del rm[MARKER_INTIMIDATED]
                result["intimidated_removed"].append(region)
        elif isinstance(rm, set):
            if MARKER_ARVERNI_RALLY in rm:
                rm.discard(MARKER_ARVERNI_RALLY)
                result["rally_markers_removed"].append(region)
            if MARKER_BRITANNIA_NOT_IN_PLAY in rm:
                rm.discard(MARKER_BRITANNIA_NOT_IN_PLAY)
                result["britannia_not_in_play_removed"] = True
            if MARKER_NORI in rm:
                rm.discard(MARKER_NORI)
                result["nori_marker_removed"] = True
            if MARKER_CISALPINA_CONTROL_BOX in rm:
                rm.discard(MARKER_CISALPINA_CONTROL_BOX)
                result["cisalpina_control_box_removed"] = True
            if MARKER_INTIMIDATED in rm:
                rm.discard(MARKER_INTIMIDATED)
                result["intimidated_removed"].append(region)
    return result


# ============================================================================
# STEP 5: Spring Phase
# ============================================================================


def _step5_spring(state, roman_dispersed_keep=None):
    """Conduct a full Spring Phase (§6.6), but Romans may keep ONE
    Dispersed or Dispersed-Gathering marker as is.

    Put the Winter marker in the Quarters box (flag for next Winter).
    """
    from fs_bot.engine.winter import spring_phase

    # The Roman "keep one" option lets the Romans designate a tribe
    # whose Dispersed / Dispersed-Gathering status should NOT be
    # cycled by Spring. Save its current status, run Spring, then
    # restore.
    saved = None
    if roman_dispersed_keep is not None:
        tinfo = state["tribes"].get(roman_dispersed_keep)
        if tinfo is not None:
            saved = {
                "tribe": roman_dispersed_keep,
                "status": tinfo.get("status"),
                "allied_faction": tinfo.get("allied_faction"),
            }

    spring_result = spring_phase(state)

    if saved is not None and saved["status"] in (
        MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    ):
        tinfo = state["tribes"].get(saved["tribe"])
        if tinfo is not None:
            tinfo["status"] = saved["status"]
            tinfo["allied_faction"] = saved["allied_faction"]

    # "Put the Winter marker in the Quarters box" — flag for the next
    # Winter Round so harvest/senate phases know we're in the first
    # round after Interlude.
    state["first_senate_after_interlude_pending"] = True
    state["first_harvest_after_interlude_pending"] = True

    return {
        "spring_phase": spring_result,
        "roman_dispersed_kept": (
            saved["tribe"] if saved is not None else None
        ),
    }


# ============================================================================
# STEP 6: Eligibility cylinder swap
# ============================================================================


def _step6_eligibility(state):
    """Replace the German Eligibility cylinder with an Arverni cylinder.

    Preserves the eligibility status (Eligible/Ineligible) the German
    cylinder had.
    """
    elig = state["eligibility"]
    german_status = elig.get(GERMANS, ELIGIBLE)
    elig[ARVERNI] = german_status
    if GERMANS in elig:
        del elig[GERMANS]
    return {"arverni_eligibility": german_status}


# ============================================================================
# STEP 7: Edge Track (Resources)
# ============================================================================


def _step7_edge_track(state):
    """Adjust Resources per Interlude Edge Track step.

    - Move German Resource amount to Arverni track.
    - Cap any faction with more than 2x its 54 BC start.
    - Boost any faction below 1/2 its 54 BC start by +2.
    """
    result = {
        "german_to_arverni": 0,
        "caps_applied": {},
        "boosts_applied": {},
    }
    res = state["resources"]
    g = res.get(GERMANS, 0)
    if g > 0:
        res[ARVERNI] = res.get(ARVERNI, 0) + g
        result["german_to_arverni"] = g
    # Germans no longer track resources after Interlude — A1.8.
    if GERMANS in res:
        del res[GERMANS]

    # Cap to 2x start (per scenario explicit numbers).
    caps = {
        ARVERNI: 2 * PAX_GALLICA_START_ARVERNI,   # 10
        AEDUI: 2 * PAX_GALLICA_START_AEDUI,        # 10
        BELGAE: 2 * PAX_GALLICA_START_BELGAE,      # 10
        ROMANS: 2 * PAX_GALLICA_START_ROMANS,      # 16
    }
    for f, cap in caps.items():
        cur = res.get(f, 0)
        if cur > cap:
            res[f] = cap
            result["caps_applied"][f] = cap

    # Boost if below 1/2 start (Arverni 0-2, Aedui 0-2, Belgae 0-2,
    # Roman 0-3 -> +2).
    thresholds = {
        ARVERNI: 2,  # 0-2 inclusive
        AEDUI: 2,
        BELGAE: 2,
        ROMANS: 3,
    }
    for f, hi in thresholds.items():
        cur = res.get(f, 0)
        if cur <= hi:
            res[f] = min(cur + 2, MAX_RESOURCES)
            result["boosts_applied"][f] = res[f] - cur

    return result


# ============================================================================
# STEP 8: Victory marker swap
# ============================================================================


def _step8_victory_swap(state):
    """Swap Germanic for Arverni Victory marker; recalc victory margins.

    There's no separate "Victory marker" field in state — victory is
    computed on demand from current piece counts. We simply note in
    state that Arverni now tracks victory and Germans do not.
    """
    state["scenario_phase"] = "second_half"
    return {"victory_swap": "Germans -> Arverni"}


# ============================================================================
# STEP 10: Deck rebuild
# ============================================================================


def _build_pax_gallica_deck_for_interlude(state):
    """Build a Pax Gallica?-style deck for the Interlude.

    Per A2.1 Deck step:
      - 70 non-Events + 5 Winter cards, piles of 5, Winter cards in
        piles 2, 5, 8, 11, 14.
      - Use O38 (Diviciacus 2nd Ed) instead of base 38 Diviciacus.
      - Keep cards for any Capabilities in effect, Gallia Togata, and
        Colony out of the deck (and "by their Factions as appropriate").
      - Build piles in order until no Events remain. If 5+ Events were
        left out (no 14th pile), the 5th Winter card becomes the last
        card of the deck.
    """
    rng = state["rng"]
    excluded = set()

    # Capability cards in effect, plus Gallia Togata (5), Colony (71).
    caps_active = state.get("capabilities", {})
    for card_id in caps_active.keys():
        excluded.add(card_id)
    excluded.update({5, 71})

    # Build the Pax Gallica deck pool: base cards 1..72.
    pool = []
    for card_id in CARD_NAMES_BASE.keys():
        if card_id in excluded:
            continue
        # Substitute O38 for 38.
        if card_id == 38:
            pool.append(INTERLUDE_DIVICIACUS_CARD)
        else:
            pool.append(card_id)
    rng.shuffle(pool)

    # Take only up to 70 events.
    events_to_use = pool[:PAX_GALLICA_DECK_EVENTS]
    left_out_extra = len(pool) - len(events_to_use)

    # Build piles per Pax Gallica? composition: 14 piles of 5.
    piles = []
    idx = 0
    for pile_num in range(1, 15):
        chunk = events_to_use[idx:idx + 5]
        if not chunk:
            break
        piles.append((pile_num, chunk))
        idx += 5

    # Place a Winter card into each pile listed in PAX_GALLICA_WINTER_PILES
    # that exists in our (possibly truncated) piles list.
    winters_placed = 0
    for pile_num in PAX_GALLICA_WINTER_PILES:
        for pn, chunk in piles:
            if pn == pile_num:
                chunk.append(WINTER_CARD)
                rng.shuffle(chunk)
                winters_placed += 1
                break

    deck = []
    for _, chunk in piles:
        deck.extend(chunk)

    # If 5+ Events were excluded (so the 14th pile is missing), the
    # 5th Winter card becomes the last card of the deck.
    if winters_placed < 5:
        for _ in range(5 - winters_placed):
            deck.append(WINTER_CARD)

    state["deck"] = deck
    state["played_cards"] = []
    state["current_card"] = None
    state["next_card"] = deck[0] if deck else None

    return {
        "deck_size": len(deck),
        "events_used": len(events_to_use),
        "events_excluded": len(excluded),
        "winters_in_piles": winters_placed,
    }


# ============================================================================
# STEP 11: Final state flags (handled inline in run_interlude)
# ============================================================================


# ============================================================================
# PUBLIC API
# ============================================================================


def run_interlude(state, *, britannia_decision=None,
                  roman_dispersed_keep=None):
    """Execute the full Gallic War Interlude.

    Should only be called for SCENARIO_GALLIC_WAR after the 3rd Victory
    Phase if no faction has won; the caller (game_engine) handles those
    guards. We re-validate here too.

    Args:
        state: Game state dict (mutated in place).
        britannia_decision: Optional bool or dict for player Roman
            choice on the Britannia expedition. None -> use NP logic
            (A8.8.9 / "conduct if able").
        roman_dispersed_keep: Optional tribe constant — the one tribe
            whose Dispersed / Dispersed-Gathering status the Romans
            choose to keep through Spring. None -> keep none.

    Returns:
        Dict summarizing each step's outcome.

    Raises:
        ValueError: If state["scenario"] is not SCENARIO_GALLIC_WAR.
    """
    if state.get("scenario") != SCENARIO_GALLIC_WAR:
        raise ValueError(
            "Interlude only runs in SCENARIO_GALLIC_WAR, got "
            f"{state.get('scenario')!r}"
        )

    result = {}

    # 1. Winter Events
    result["step1_winter_events"] = _step1_winter_events(state)

    # 2. Adjust Forces — Circumvallation cleanup first
    result["step2_circumvallation"] = _step0_circumvallation(state)
    result["step2_germans"] = _adjust_german_forces(state)
    result["step2_belgae"] = _adjust_belgae_forces(state)
    result["step2_aedui"] = _adjust_aedui_forces(state)
    result["step2_arverni"] = _adjust_arverni_forces(state)
    result["step2_romans"] = _adjust_roman_forces(state)
    result["step2_cisalpina"] = _cisalpina_relocation(state)

    # 3. Britannia expedition
    result["step3_britannia"] = _step3_britannia(
        state, britannia_decision,
        roman_dispersed_keep=roman_dispersed_keep,
    )

    # 4. Markers cleanup
    result["step4_markers"] = _step4_markers_cleanup(state)

    # 5. Spring
    result["step5_spring"] = _step5_spring(
        state, roman_dispersed_keep=roman_dispersed_keep,
    )

    # 6. Eligibility cylinder swap
    result["step6_eligibility"] = _step6_eligibility(state)

    # 7. Edge track (Resources)
    result["step7_edge_track"] = _step7_edge_track(state)

    # 8. Victory marker swap
    result["step8_victory"] = _step8_victory_swap(state)

    # 9. Lingering Events: nothing to do; capabilities/markers persist
    result["step9_lingering"] = {"preserved": True}

    # 10. Deck rebuild
    result["step10_deck"] = _build_pax_gallica_deck_for_interlude(state)

    # 11. State flags
    state["interlude_completed"] = True
    state["scenario_phase"] = "second_half"

    return result
