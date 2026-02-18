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
    raise NotImplementedError("Card 2: Legiones XIIII et XV")

def execute_card_3(state, shaded=False):
    raise NotImplementedError("Card 3: Pompey")

def execute_card_4(state, shaded=False):
    raise NotImplementedError("Card 4: Circumvallation")

def execute_card_5(state, shaded=False):
    raise NotImplementedError("Card 5: Gallia Togata")

def execute_card_6(state, shaded=False):
    raise NotImplementedError("Card 6: Marcus Antonius")

def execute_card_7(state, shaded=False):
    raise NotImplementedError("Card 7: Alaudae")

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
    raise NotImplementedError("Card 14: Clodius Pulcher")

def execute_card_15(state, shaded=False):
    raise NotImplementedError("Card 15: Legio X")

def execute_card_16(state, shaded=False):
    raise NotImplementedError("Card 16: Ambacti")

def execute_card_17(state, shaded=False):
    raise NotImplementedError("Card 17: Germanic Chieftains")

def execute_card_18(state, shaded=False):
    raise NotImplementedError("Card 18: Rhenus Bridge")

def execute_card_19(state, shaded=False):
    raise NotImplementedError("Card 19: Lucterius")

def execute_card_20(state, shaded=False):
    raise NotImplementedError("Card 20: Optimates")

def execute_card_21(state, shaded=False):
    raise NotImplementedError("Card 21: The Province")

def execute_card_22(state, shaded=False):
    raise NotImplementedError("Card 22: Hostages")

def execute_card_23(state, shaded=False):
    raise NotImplementedError("Card 23: Sacking")

def execute_card_24(state, shaded=False):
    raise NotImplementedError("Card 24: Sappers")

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
    raise NotImplementedError("Card 31: Cotuatus & Conconnetodumnus")

def execute_card_32(state, shaded=False):
    raise NotImplementedError("Card 32: Forced Marches")

def execute_card_33(state, shaded=False):
    raise NotImplementedError("Card 33: Lost Eagle")

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
    raise NotImplementedError("Card 49: Drought")

def execute_card_50(state, shaded=False):
    raise NotImplementedError("Card 50: Shifting Loyalties")

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
