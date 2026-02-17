"""
Scenario setup module — Load each of the 5 scenarios.

Parses piece placements, resource levels, Senate position, Legions track,
tribal allegiances, and deck composition from the Reference Documents.
Uses place_piece() for all placements — never sets piece counts directly.

All 5 scenarios must produce a valid state that passes validate_state().

Reference: Setup (§2.1), A Setup (A2.1), all 5 scenario files.
"""

from fs_bot.rules_consts import (
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST, SCENARIO_GREAT_REVOLT,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, SUCCESSOR,
    ARIOVISTUS_LEADER, DIVICIACUS, BODUOGNATUS,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA, CISALPINA,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI,
    TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
    TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_BITURIGES,
    TRIBE_AEDUI,
    TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_CATUVELLAUNI,
    TRIBE_HELVII,
    TRIBE_NORI,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    # Control
    ROMAN_CONTROL, ARVERNI_CONTROL, AEDUI_CONTROL,
    BELGIC_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
    # Markers
    MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_GALLIA_TOGATA,
    MARKER_AT_WAR, MARKER_BRITANNIA_NOT_IN_PLAY,
    MARKER_ARVERNI_RALLY,
    # Victory
    MAX_RESOURCES,
    # Eligibility
    ELIGIBLE,
    # Cards
    CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
    WINTER_CARD, WINTER_CARD_COUNT,
    SECOND_EDITION_CARDS,
    # Tribe status
    ALLIED, DISPERSED, DISPERSED_GATHERING,
)

from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.board.pieces import place_piece, remove_piece, PieceError
from fs_bot.board.control import refresh_all_control


def _set_tribe_allied(state, tribe, faction):
    """Set a tribe as allied to a faction."""
    state["tribes"][tribe]["status"] = ALLIED
    state["tribes"][tribe]["allied_faction"] = faction


def _set_tribe_dispersed(state, tribe):
    """Set a tribe as Dispersed."""
    state["tribes"][tribe]["status"] = DISPERSED
    state["tribes"][tribe]["allied_faction"] = None


def _set_tribe_dispersed_gathering(state, tribe):
    """Set a tribe as Dispersed-Gathering."""
    state["tribes"][tribe]["status"] = DISPERSED_GATHERING
    state["tribes"][tribe]["allied_faction"] = None


def _set_legions_track(state, bottom=0, middle=0, top=0):
    """Set legions track to specific values.

    Called AFTER all map placements to set the final track distribution.
    Any Legions that were on the track but are not accounted for by the
    new track values go to Fallen (to maintain the invariant
    map + track + fallen + removed = cap).
    """
    # Count how many are currently on the track
    current_track = sum(
        state["legions_track"].get(row, 0) for row in LEGIONS_ROWS
    )
    new_track = bottom + middle + top
    # If there are more on track than the scenario wants, the extras
    # go to a special holding area (e.g. Pax Gallica winter track)
    # or to Fallen. We handle this via the winter_track_legions field.
    state["legions_track"][LEGIONS_ROW_BOTTOM] = bottom
    state["legions_track"][LEGIONS_ROW_MIDDLE] = middle
    state["legions_track"][LEGIONS_ROW_TOP] = top
    # Extra Legions on track go to winter_track_legions
    extras = current_track - new_track
    if extras > 0:
        state["winter_track_legions"] = state.get(
            "winter_track_legions", 0
        ) + extras


def _set_resources(state, faction, amount):
    """Set resources for a faction."""
    state["resources"][faction] = min(amount, MAX_RESOURCES)


def _set_senate(state, position, firm=False):
    """Set the Senate marker position."""
    state["senate"]["position"] = position
    state["senate"]["firm"] = firm


def _place_permanent_fort(state):
    """Place the permanent Fort in Provincia — §1.4.2."""
    place_piece(state, PROVINCIA, ROMANS, FORT)


def _build_base_deck(state, num_events, winter_positions):
    """Build deck for base game scenarios.

    Per Setup (§2.1): Deal events into piles of 5, shuffle Winter
    cards into specified piles, stack them.

    Args:
        state: Game state dict.
        num_events: Number of event cards to use.
        winter_positions: List of pile numbers (1-indexed) that get
            Winter cards.
    """
    rng = state["rng"]

    # All base event card numbers
    all_events = list(CARD_NAMES_BASE.keys())
    rng.shuffle(all_events)

    # Take only the needed events
    events = all_events[:num_events]

    # Deal into piles of 5
    num_piles = num_events // 5
    piles = []
    for i in range(num_piles):
        pile = events[i * 5:(i + 1) * 5]
        piles.append(pile)

    # Shuffle Winter cards into specified piles
    for pile_num in winter_positions:
        idx = pile_num - 1  # Convert to 0-indexed
        if idx < len(piles):
            piles[idx].append(WINTER_CARD)
            rng.shuffle(piles[idx])

    # Stack piles: 1st on top
    deck = []
    for pile in piles:
        deck.extend(pile)

    state["deck"] = deck


def _build_ariovistus_deck(state, num_events, winter_positions):
    """Build deck for Ariovistus scenarios.

    Per A Setup (A2.1): Replace 39 cards, then deal/shuffle per scenario.

    The Ariovistus deck replaces certain base cards with A-prefixed cards.
    Per A2.1, the full replacement list produces 72 Event cards total.
    """
    rng = state["rng"]

    # Build the Ariovistus card pool
    # Start with base cards, then remove replaced ones and add A-cards
    # Cards replaced per A2.1:
    # Remove 19-36 (all 18 Arverni-first), replace with A19-A36
    # Remove 5, 17, 18 (Roman first), replace with A5, A17, A18
    # Remove 37, 38, 40, 43, 45, 51, 53 (Aedui first), replace with
    #   A37, A38, A40, A43, A45, A51, A53
    # Remove 56, 57, 58, 60, 63, 64, 65, 66, 67, 69, 70 (Belgae first),
    #   replace with A56-A70

    removed_base = set(range(19, 37))  # 19-36
    removed_base |= {5, 17, 18}
    removed_base |= {37, 38, 40, 43, 45, 51, 53}
    removed_base |= {56, 57, 58, 60, 63, 64, 65, 66, 67, 69, 70}

    # Also replace the 5 2nd Edition cards
    # These are already in the base deck (cards 11, 30, 39, 44, 54)
    # They stay as-is in the Ariovistus deck (they're the 2nd Ed versions)

    # Keep base cards not removed
    base_kept = [c for c in CARD_NAMES_BASE.keys() if c not in removed_base]

    # Add Ariovistus replacement cards (A-prefix string keys only).
    # CARD_NAMES_ARIOVISTUS also contains integer keys (11, 30, 39, 44, 54)
    # which are 2nd Edition text amendments — they tell card handlers to use
    # different text, but are NOT additional cards inserted into the deck.
    # Those cards remain in base_kept under their original number.
    ario_cards = [k for k in CARD_NAMES_ARIOVISTUS if isinstance(k, str)]

    # The full deck is base_kept + ario_cards (should be 72 total)
    all_events = base_kept + ario_cards
    rng.shuffle(all_events)

    # Take only the needed events
    events = all_events[:num_events]

    # Deal into piles of 5
    num_piles = num_events // 5
    piles = []
    for i in range(num_piles):
        pile = events[i * 5:(i + 1) * 5]
        piles.append(pile)

    # Shuffle Winter cards into specified piles
    for pile_num in winter_positions:
        idx = pile_num - 1
        if idx < len(piles):
            piles[idx].append(WINTER_CARD)
            rng.shuffle(piles[idx])

    # Stack piles
    deck = []
    for pile in piles:
        deck.extend(pile)

    state["deck"] = deck


# ============================================================================
# SCENARIO: PAX GALLICA? (54 BC, late Summer)
# ============================================================================

def _setup_pax_gallica(state):
    """Set up the Pax Gallica? scenario.

    Reference: Scenario: Pax Gallica?
    """
    # --- Senate ---
    # NOTE: During the first year, the Senate is not in Uproar, nor
    # Intrigue, nor Adulation and does not shift.
    # We set it to None — the 1st Winter special rules will set it.
    _set_senate(state, None, firm=False)

    # --- Resources ---
    _set_resources(state, ARVERNI, 5)
    _set_resources(state, AEDUI, 5)
    _set_resources(state, BELGAE, 5)
    _set_resources(state, ROMANS, 8)

    # --- Place permanent Fort ---
    _place_permanent_fort(state)

    # --- BRITANNIA ---
    # Roman Control, Caesar, 5x Legions, 1x Auxilia
    place_piece(state, BRITANNIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, BRITANNIA, ROMANS, LEGION, 5,
                from_legions_track=True)
    place_piece(state, BRITANNIA, ROMANS, AUXILIA, 1)

    # --- BELGICA ---

    # Morini: Belgic Control, Menapii=Belgic Ally, 1x Belgic Warband
    _set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
    place_piece(state, MORINI, BELGAE, ALLY, 1)
    place_piece(state, MORINI, BELGAE, WARBAND, 1)

    # Nervii: Belgic Control, Ambiorix, Eburones=Belgic Ally,
    #         2x Belgic Warbands, 2x Germanic Warbands, Roman Fort
    _set_tribe_allied(state, TRIBE_EBURONES, BELGAE)
    place_piece(state, NERVII, BELGAE, LEADER, leader_name=AMBIORIX)
    place_piece(state, NERVII, BELGAE, ALLY, 1)
    place_piece(state, NERVII, BELGAE, WARBAND, 2)
    place_piece(state, NERVII, GERMANS, WARBAND, 2)
    place_piece(state, NERVII, ROMANS, FORT, 1)

    # Atrebates: No Control, Bellovaci=Belgic Ally, 2x Belgic Warbands,
    #            Atrebates=Roman Ally, Remi=Roman Ally, 1x Auxilia
    _set_tribe_allied(state, TRIBE_BELLOVACI, BELGAE)
    place_piece(state, ATREBATES, BELGAE, ALLY, 1)
    place_piece(state, ATREBATES, BELGAE, WARBAND, 2)
    _set_tribe_allied(state, TRIBE_ATREBATES, ROMANS)
    place_piece(state, ATREBATES, ROMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_REMI, ROMANS)
    place_piece(state, ATREBATES, ROMANS, ALLY, 1)
    place_piece(state, ATREBATES, ROMANS, AUXILIA, 1)

    # --- GERMANIA ---

    # Sugambri: Germanic Control, Sugambri=Germanic Ally,
    #           Suebi(north)=Germanic Ally, 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SUEBI_NORTH, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    place_piece(state, SUGAMBRI, GERMANS, WARBAND, 4)

    # Ubii: Germanic Control, Suebi(south)=Germanic Ally,
    #       4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SUEBI_SOUTH, GERMANS)
    place_piece(state, UBII, GERMANS, ALLY, 1)
    place_piece(state, UBII, GERMANS, WARBAND, 4)

    # --- CELTICA ---

    # Treveri: Belgic Control, Treveri=Belgic Ally, 1x Belgic Warband
    _set_tribe_allied(state, TRIBE_TREVERI, BELGAE)
    place_piece(state, TREVERI, BELGAE, ALLY, 1)
    place_piece(state, TREVERI, BELGAE, WARBAND, 1)

    # Veneti: Veneti=Dispersed Tribe
    _set_tribe_dispersed(state, TRIBE_VENETI)

    # Mandubii: Arverni Control, Senones=Arverni Ally,
    #           3x Arverni Warbands, 2x Aedui Warbands
    _set_tribe_allied(state, TRIBE_SENONES, ARVERNI)
    place_piece(state, MANDUBII, ARVERNI, ALLY, 1)
    place_piece(state, MANDUBII, ARVERNI, WARBAND, 3)
    place_piece(state, MANDUBII, AEDUI, WARBAND, 2)

    # Aedui: Aedui Control, Aedui<Bibracte>=Aedui Ally (no Citadel),
    #        2x Aedui Warbands
    _set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
    place_piece(state, AEDUI_REGION, AEDUI, ALLY, 1)
    place_piece(state, AEDUI_REGION, AEDUI, WARBAND, 2)

    # Arverni: Arverni Control, Arverni<Gergovia>=Arverni Ally (no Citadel),
    #          2x Arverni Warbands
    _set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
    place_piece(state, ARVERNI_REGION, ARVERNI, ALLY, 1)
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 2)

    # --- PROVINCIA ---
    # Roman Control, 2x Auxilia, Roman Fort (permanent — already placed)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2)

    # (Carnutes, Pictones, Bituriges, Sequani are empty)

    # --- Legions Track ---
    # "4x Legions on bottom row"
    # After placing 5 Legions on map, 7 remain on track.
    # Scenario says 4 on bottom row; the other 3 go to the
    # Winter Track "Harvest Phase box" (1st Winter special rules).
    _set_legions_track(state, bottom=4)

    # --- Refresh control ---
    refresh_all_control(state)

    # --- Deck ---
    # Deal 70 Events into 14 piles of 5.
    # Winter cards in 2nd, 5th, 8th, 11th, 14th piles.
    _build_base_deck(state, 70, [2, 5, 8, 11, 14])

    # --- 1st Winter special rules stored in state ---
    state["first_winter_special"] = {
        "skip_victory_phase": True,
        "skip_germans_phase": True,
        "harvest_place_legions_in_belgica": 3,
        "senate_set_to_intrigue": True,
        "place_vercingetorix_in_spring": True,
    }


# ============================================================================
# SCENARIO: RECONQUEST OF GAUL (53 BC, mid-Winter)
# ============================================================================

def _setup_reconquest(state):
    """Set up the Reconquest of Gaul scenario.

    Reference: Scenario: Reconquest of Gaul
    """
    # --- Senate ---
    # Intrigue
    _set_senate(state, INTRIGUE)

    # --- Resources ---
    _set_resources(state, ARVERNI, 10)
    _set_resources(state, BELGAE, 10)
    _set_resources(state, AEDUI, 15)
    _set_resources(state, ROMANS, 20)

    # --- Place permanent Fort ---
    _place_permanent_fort(state)

    # --- BELGICA ---

    # Morini: Belgic Control
    # Morini=Belgic Ally, Menapii=Belgic Ally, 4x Belgic Warbands,
    # 1x Legion, 1x Auxilia
    _set_tribe_allied(state, TRIBE_MORINI, BELGAE)
    place_piece(state, MORINI, BELGAE, ALLY, 1)
    _set_tribe_allied(state, TRIBE_MENAPII, BELGAE)
    place_piece(state, MORINI, BELGAE, ALLY, 1)
    place_piece(state, MORINI, BELGAE, WARBAND, 4)
    place_piece(state, MORINI, ROMANS, LEGION, 1, from_legions_track=True)
    place_piece(state, MORINI, ROMANS, AUXILIA, 1)

    # Nervii: Belgic Control
    # Ambiorix, Nervii=Belgic Ally, Eburones=Belgic Ally,
    # 4x Belgic Warbands, 1x Germanic Warband,
    # Roman Fort, 2x Legions, 2x Auxilia
    _set_tribe_allied(state, TRIBE_NERVII, BELGAE)
    place_piece(state, NERVII, BELGAE, ALLY, 1)
    _set_tribe_allied(state, TRIBE_EBURONES, BELGAE)
    place_piece(state, NERVII, BELGAE, ALLY, 1)
    place_piece(state, NERVII, BELGAE, LEADER, leader_name=AMBIORIX)
    place_piece(state, NERVII, BELGAE, WARBAND, 4)
    place_piece(state, NERVII, GERMANS, WARBAND, 1)
    place_piece(state, NERVII, ROMANS, FORT, 1)
    place_piece(state, NERVII, ROMANS, LEGION, 2, from_legions_track=True)
    place_piece(state, NERVII, ROMANS, AUXILIA, 2)

    # Atrebates: Belgic Control
    # Atrebates=Belgic Ally, Bellovaci=Belgic Ally, 3x Belgic Warbands,
    # Remi=Roman Ally, 1x Auxilia
    _set_tribe_allied(state, TRIBE_ATREBATES, BELGAE)
    place_piece(state, ATREBATES, BELGAE, ALLY, 1)
    _set_tribe_allied(state, TRIBE_BELLOVACI, BELGAE)
    place_piece(state, ATREBATES, BELGAE, ALLY, 1)
    place_piece(state, ATREBATES, BELGAE, WARBAND, 3)
    _set_tribe_allied(state, TRIBE_REMI, ROMANS)
    place_piece(state, ATREBATES, ROMANS, ALLY, 1)
    place_piece(state, ATREBATES, ROMANS, AUXILIA, 1)

    # --- GERMANIA ---

    # Sugambri: Germanic Control
    # Sugambri=Germanic Ally, Suebi(north)=Germanic Ally,
    # 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SUEBI_NORTH, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    place_piece(state, SUGAMBRI, GERMANS, WARBAND, 4)

    # Ubii: Germanic Control
    # Suebi(south)=Germanic Ally, 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SUEBI_SOUTH, GERMANS)
    place_piece(state, UBII, GERMANS, ALLY, 1)
    place_piece(state, UBII, GERMANS, WARBAND, 4)

    # --- CELTICA ---

    # Treveri: Belgic Control
    # Treveri=Belgic Ally, 4x Belgic Warbands,
    # Roman Fort, 1x Legion, 2x Auxilia
    _set_tribe_allied(state, TRIBE_TREVERI, BELGAE)
    place_piece(state, TREVERI, BELGAE, ALLY, 1)
    place_piece(state, TREVERI, BELGAE, WARBAND, 4)
    place_piece(state, TREVERI, ROMANS, FORT, 1)
    place_piece(state, TREVERI, ROMANS, LEGION, 1, from_legions_track=True)
    place_piece(state, TREVERI, ROMANS, AUXILIA, 2)

    # Veneti: Veneti=Dispersed-Gathering
    _set_tribe_dispersed_gathering(state, TRIBE_VENETI)

    # Carnutes: Arverni Control
    # Carnutes<Cenabum>=Arverni Ally (no Citadel), 4x Arverni Warbands
    _set_tribe_allied(state, TRIBE_CARNUTES, ARVERNI)
    place_piece(state, CARNUTES, ARVERNI, ALLY, 1)
    place_piece(state, CARNUTES, ARVERNI, WARBAND, 4)

    # Mandubii: No Control
    # Senones=Arverni Ally, 3x Arverni Warbands,
    # Lingones=Aedui Ally, 3x Aedui Warbands
    _set_tribe_allied(state, TRIBE_SENONES, ARVERNI)
    place_piece(state, MANDUBII, ARVERNI, ALLY, 1)
    place_piece(state, MANDUBII, ARVERNI, WARBAND, 3)
    _set_tribe_allied(state, TRIBE_LINGONES, AEDUI)
    place_piece(state, MANDUBII, AEDUI, ALLY, 1)
    place_piece(state, MANDUBII, AEDUI, WARBAND, 3)

    # Bituriges: Aedui Control
    # Bituriges<Avaricum>=Aedui Ally (no Citadel), 3x Aedui Warbands
    _set_tribe_allied(state, TRIBE_BITURIGES, AEDUI)
    place_piece(state, BITURIGES, AEDUI, ALLY, 1)
    place_piece(state, BITURIGES, AEDUI, WARBAND, 3)

    # Aedui: Aedui Control
    # Aedui<Bibracte>=Aedui Citadel, 3x Aedui Warbands
    _set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
    place_piece(state, AEDUI_REGION, AEDUI, CITADEL, 1)
    place_piece(state, AEDUI_REGION, AEDUI, WARBAND, 3)

    # Arverni: Arverni Control
    # Vercingetorix, Arverni<Gergovia>=Arverni Ally (no Citadel),
    # 6x Arverni Warbands
    _set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
    place_piece(state, ARVERNI_REGION, ARVERNI, ALLY, 1)
    place_piece(state, ARVERNI_REGION, ARVERNI, LEADER,
                leader_name=VERCINGETORIX)
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 6)

    # --- PROVINCIA ---
    # Roman Control, Caesar, 4x Legions, 6x Auxilia,
    # Roman Fort (permanent — already placed)
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, PROVINCIA, ROMANS, LEGION, 4,
                from_legions_track=True)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 6)

    # (Britannia, Pictones, Sequani are empty)

    # --- Legions Track ---
    # 4x Legions on bottom row. 8 placed on map, 4 remain on track.
    _set_legions_track(state, bottom=4)

    # --- Refresh control ---
    refresh_all_control(state)

    # --- Deck ---
    # Deal 60 Events into 12 piles of 5.
    # Winter in 3rd, 6th, 9th, 12th piles.
    _build_base_deck(state, 60, [3, 6, 9, 12])


# ============================================================================
# SCENARIO: THE GREAT REVOLT (52 BC, Spring)
# ============================================================================

def _setup_great_revolt(state):
    """Set up The Great Revolt scenario.

    Reference: Scenario: The Great Revolt
    """
    # --- Senate ---
    # Intrigue
    _set_senate(state, INTRIGUE)

    # --- Resources ---
    _set_resources(state, BELGAE, 10)
    _set_resources(state, AEDUI, 15)
    _set_resources(state, ARVERNI, 20)
    _set_resources(state, ROMANS, 20)

    # --- Place permanent Fort ---
    _place_permanent_fort(state)

    # --- BELGICA ---

    # Morini: Belgic Control
    # Morini=Belgic Ally, 4x Belgic Warbands
    _set_tribe_allied(state, TRIBE_MORINI, BELGAE)
    place_piece(state, MORINI, BELGAE, ALLY, 1)
    place_piece(state, MORINI, BELGAE, WARBAND, 4)

    # Nervii: Roman Control
    # Eburones=Dispersed-Gathering, Roman Fort, 2x Auxilia,
    # 1x Belgic Warband, 1x Germanic Warband
    _set_tribe_dispersed_gathering(state, TRIBE_EBURONES)
    place_piece(state, NERVII, ROMANS, FORT, 1)
    place_piece(state, NERVII, ROMANS, AUXILIA, 2)
    place_piece(state, NERVII, BELGAE, WARBAND, 1)
    place_piece(state, NERVII, GERMANS, WARBAND, 1)

    # Atrebates: Roman Control
    # Bellovaci=Belgic Ally, 1x Belgic Warband,
    # Remi=Roman Ally, 2x Auxilia
    _set_tribe_allied(state, TRIBE_BELLOVACI, BELGAE)
    place_piece(state, ATREBATES, BELGAE, ALLY, 1)
    place_piece(state, ATREBATES, BELGAE, WARBAND, 1)
    _set_tribe_allied(state, TRIBE_REMI, ROMANS)
    place_piece(state, ATREBATES, ROMANS, ALLY, 1)
    place_piece(state, ATREBATES, ROMANS, AUXILIA, 2)

    # --- GERMANIA ---

    # Sugambri: Belgic Control
    # Belgic Successor (or Ambiorix), 4x Belgic Warbands,
    # Sugambri=Germanic Ally, Suebi(north)=Germanic Ally,
    # 2x Germanic Warbands
    # NOTE: "Players and Victory" says if a player runs only the Belgae
    # or if Romans+Aedui are one player, flip to Ambiorix.
    # Default setup uses Successor.
    place_piece(state, SUGAMBRI, BELGAE, LEADER, leader_name=SUCCESSOR)
    place_piece(state, SUGAMBRI, BELGAE, WARBAND, 4)
    _set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SUEBI_NORTH, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    place_piece(state, SUGAMBRI, GERMANS, WARBAND, 2)

    # Ubii: Germanic Control
    # Suebi(south)=Germanic Ally, 1x Germanic Warband
    _set_tribe_allied(state, TRIBE_SUEBI_SOUTH, GERMANS)
    place_piece(state, UBII, GERMANS, ALLY, 1)
    place_piece(state, UBII, GERMANS, WARBAND, 1)

    # --- CELTICA ---

    # Treveri: Roman Control
    # 2x Germanic Warbands, Roman Fort, 2x Legions, 2x Auxilia
    place_piece(state, TREVERI, GERMANS, WARBAND, 2)
    place_piece(state, TREVERI, ROMANS, FORT, 1)
    place_piece(state, TREVERI, ROMANS, LEGION, 2, from_legions_track=True)
    place_piece(state, TREVERI, ROMANS, AUXILIA, 2)

    # Veneti: Arverni Control
    # Namnetes=Arverni Ally, 2x Arverni Warbands
    _set_tribe_allied(state, TRIBE_NAMNETES, ARVERNI)
    place_piece(state, VENETI, ARVERNI, ALLY, 1)
    place_piece(state, VENETI, ARVERNI, WARBAND, 2)

    # Carnutes: Arverni Control
    # Vercingetorix, Carnutes<Cenabum>=Arverni Ally (no Citadel),
    # Aulerci=Arverni Ally, 10x Arverni Warbands
    _set_tribe_allied(state, TRIBE_CARNUTES, ARVERNI)
    place_piece(state, CARNUTES, ARVERNI, ALLY, 1)
    _set_tribe_allied(state, TRIBE_AULERCI, ARVERNI)
    place_piece(state, CARNUTES, ARVERNI, ALLY, 1)
    place_piece(state, CARNUTES, ARVERNI, LEADER,
                leader_name=VERCINGETORIX)
    place_piece(state, CARNUTES, ARVERNI, WARBAND, 10)

    # Mandubii: Roman Control
    # Senones=Arverni Ally, 4x Arverni Warbands,
    # Mandubii<Alesia>=Aedui Ally (no Citadel), 4x Aedui Warbands,
    # Lingones=Roman Ally, Roman Fort, 8x Legions, 2x Auxilia
    _set_tribe_allied(state, TRIBE_SENONES, ARVERNI)
    place_piece(state, MANDUBII, ARVERNI, ALLY, 1)
    place_piece(state, MANDUBII, ARVERNI, WARBAND, 4)
    _set_tribe_allied(state, TRIBE_MANDUBII, AEDUI)
    place_piece(state, MANDUBII, AEDUI, ALLY, 1)
    place_piece(state, MANDUBII, AEDUI, WARBAND, 4)
    _set_tribe_allied(state, TRIBE_LINGONES, ROMANS)
    place_piece(state, MANDUBII, ROMANS, ALLY, 1)
    place_piece(state, MANDUBII, ROMANS, FORT, 1)
    place_piece(state, MANDUBII, ROMANS, LEGION, 8,
                from_legions_track=True)
    place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)

    # Pictones: Arverni Control
    # Pictones=Arverni Ally, Santones=Arverni Ally, 2x Arverni Warbands
    _set_tribe_allied(state, TRIBE_PICTONES, ARVERNI)
    place_piece(state, PICTONES, ARVERNI, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SANTONES, ARVERNI)
    place_piece(state, PICTONES, ARVERNI, ALLY, 1)
    place_piece(state, PICTONES, ARVERNI, WARBAND, 2)

    # Bituriges: Aedui Control
    # Bituriges<Avaricum>=Aedui Ally (no Citadel), 4x Aedui Warbands
    _set_tribe_allied(state, TRIBE_BITURIGES, AEDUI)
    place_piece(state, BITURIGES, AEDUI, ALLY, 1)
    place_piece(state, BITURIGES, AEDUI, WARBAND, 4)

    # Aedui: Aedui Control
    # Aedui<Bibracte>=Aedui Citadel, 6x Aedui Warbands
    _set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
    place_piece(state, AEDUI_REGION, AEDUI, CITADEL, 1)
    place_piece(state, AEDUI_REGION, AEDUI, WARBAND, 6)

    # Sequani: Arverni Control
    # Sequani<Vesontio>=Arverni Ally (no Citadel), Helvetii=Arverni Ally,
    # 1x Arverni Warband
    _set_tribe_allied(state, TRIBE_SEQUANI, ARVERNI)
    place_piece(state, SEQUANI, ARVERNI, ALLY, 1)
    _set_tribe_allied(state, TRIBE_HELVETII, ARVERNI)
    place_piece(state, SEQUANI, ARVERNI, ALLY, 1)
    place_piece(state, SEQUANI, ARVERNI, WARBAND, 1)

    # Arverni: Arverni Control
    # Arverni<Gergovia>=Arverni Citadel, Cadurci=Arverni Ally,
    # 10x Arverni Warbands
    _set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
    place_piece(state, ARVERNI_REGION, ARVERNI, CITADEL, 1)
    _set_tribe_allied(state, TRIBE_CADURCI, ARVERNI)
    place_piece(state, ARVERNI_REGION, ARVERNI, ALLY, 1)
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 10)

    # --- PROVINCIA ---
    # Roman Control, Caesar, 6x Auxilia, Helvii=Roman Ally,
    # Roman Fort (permanent — already placed)
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 6)
    _set_tribe_allied(state, TRIBE_HELVII, ROMANS)
    place_piece(state, PROVINCIA, ROMANS, ALLY, 1)

    # (Britannia is empty)

    # --- Legions Track ---
    # 2x Legions on bottom row. 10 placed on map, 2 remain.
    _set_legions_track(state, bottom=2)

    # --- Refresh control ---
    refresh_all_control(state)

    # --- Deck ---
    # Deal 45 Events into 9 piles of 5.
    # Winter in 3rd, 6th, 9th piles.
    _build_base_deck(state, 45, [3, 6, 9])


# ============================================================================
# SCENARIO: ARIOVISTUS (58 BC)
# ============================================================================

def _setup_ariovistus(state):
    """Set up the Ariovistus scenario.

    Reference: A Scenario: Ariovistus
    """
    # --- Senate ---
    # Intrigue
    _set_senate(state, INTRIGUE)

    # --- Resources ---
    # Germans track resources in Ariovistus — A1.8
    _set_resources(state, BELGAE, 5)
    _set_resources(state, AEDUI, 10)
    _set_resources(state, GERMANS, 10)
    _set_resources(state, ROMANS, 20)

    # --- Place permanent Fort ---
    _place_permanent_fort(state)

    # --- Ariovistus markers ---
    # Mark Arverni as "At War" — near the deck
    state["at_war"] = True

    # Mark Britannia as not in play — A1.3.4
    state["markers"][BRITANNIA] = {MARKER_BRITANNIA_NOT_IN_PLAY: True}

    # Mark Arverni Home regions with Rally markers — A1.3.1
    for region in (VENETI, CARNUTES, PICTONES, ARVERNI_REGION):
        state["markers"].setdefault(region, {})[MARKER_ARVERNI_RALLY] = True

    # --- BELGICA ---

    # Morini: No Control
    # Morini=Belgic Ally, 1x Germanic Warband
    _set_tribe_allied(state, TRIBE_MORINI, BELGAE)
    place_piece(state, MORINI, BELGAE, ALLY, 1)
    place_piece(state, MORINI, GERMANS, WARBAND, 1)

    # Nervii: Belgic Control
    # Boduognatus (Ambiorix piece), Nervii=Belgic Ally,
    # 2x Belgic Warbands, 1x Germanic Warband
    _set_tribe_allied(state, TRIBE_NERVII, BELGAE)
    place_piece(state, NERVII, BELGAE, LEADER, leader_name=BODUOGNATUS)
    place_piece(state, NERVII, BELGAE, ALLY, 1)
    place_piece(state, NERVII, BELGAE, WARBAND, 2)
    place_piece(state, NERVII, GERMANS, WARBAND, 1)

    # Atrebates: No Control
    # Bellovaci=Belgic Ally, 1x Belgic Warband,
    # Remi=Roman Ally, 1x Auxilia
    _set_tribe_allied(state, TRIBE_BELLOVACI, BELGAE)
    place_piece(state, ATREBATES, BELGAE, ALLY, 1)
    place_piece(state, ATREBATES, BELGAE, WARBAND, 1)
    _set_tribe_allied(state, TRIBE_REMI, ROMANS)
    place_piece(state, ATREBATES, ROMANS, ALLY, 1)
    place_piece(state, ATREBATES, ROMANS, AUXILIA, 1)

    # --- GERMANIA ---

    # Sugambri: Germanic Control
    # Sugambri=Germanic Ally, Suebi(north)=Germanic Ally,
    # 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SUGAMBRI, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SUEBI_NORTH, GERMANS)
    place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
    place_piece(state, SUGAMBRI, GERMANS, WARBAND, 4)

    # Ubii: Germanic Control
    # Ariovistus, Ubii=Germanic Ally, Suebi(south)=Germanic Ally,
    # 8x Germanic Warbands
    _set_tribe_allied(state, TRIBE_UBII, GERMANS)
    place_piece(state, UBII, GERMANS, ALLY, 1)
    _set_tribe_allied(state, TRIBE_SUEBI_SOUTH, GERMANS)
    place_piece(state, UBII, GERMANS, ALLY, 1)
    place_piece(state, UBII, GERMANS, LEADER,
                leader_name=ARIOVISTUS_LEADER)
    place_piece(state, UBII, GERMANS, WARBAND, 8)

    # --- CISALPINA ---
    # Germanic Control, Nori=Germanic Ally, 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_NORI, GERMANS)
    place_piece(state, CISALPINA, GERMANS, ALLY, 1)
    place_piece(state, CISALPINA, GERMANS, WARBAND, 4)

    # --- CELTICA ---

    # Treveri: No Control
    # Treveri=Aedui Ally, 1x Germanic Warband
    _set_tribe_allied(state, TRIBE_TREVERI, AEDUI)
    place_piece(state, TREVERI, AEDUI, ALLY, 1)
    place_piece(state, TREVERI, GERMANS, WARBAND, 1)

    # Mandubii: No Control
    # 1x Arverni Warband, Lingones=Aedui Ally
    place_piece(state, MANDUBII, ARVERNI, WARBAND, 1)
    _set_tribe_allied(state, TRIBE_LINGONES, AEDUI)
    place_piece(state, MANDUBII, AEDUI, ALLY, 1)

    # Carnutes: Arverni Control; Arverni Home
    # 1x Arverni Warband
    place_piece(state, CARNUTES, ARVERNI, WARBAND, 1)

    # Veneti: Arverni Control; Arverni Home
    # 1x Arverni Warband
    place_piece(state, VENETI, ARVERNI, WARBAND, 1)

    # Pictones: Arverni Control; Arverni Home
    # 1x Arverni Warband
    place_piece(state, PICTONES, ARVERNI, WARBAND, 1)

    # Aedui: Aedui Control
    # Diviciacus, Aedui<Bibracte>=Aedui Ally (no Citadel),
    # 2x Aedui Warbands, 1x Arverni Warband
    _set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
    place_piece(state, AEDUI_REGION, AEDUI, ALLY, 1)
    place_piece(state, AEDUI_REGION, AEDUI, LEADER,
                leader_name=DIVICIACUS)
    state["diviciacus_in_play"] = True
    place_piece(state, AEDUI_REGION, AEDUI, WARBAND, 2)
    place_piece(state, AEDUI_REGION, ARVERNI, WARBAND, 1)

    # Sequani: Arverni Control; At War
    # Sequani<Vesontio>=Arverni Ally (no Citadel),
    # Helvetii=Arverni Ally, 6x Arverni Warbands,
    # 1x Aedui Warband, 1x Germanic Settlement, 4x Germanic Warbands
    _set_tribe_allied(state, TRIBE_SEQUANI, ARVERNI)
    place_piece(state, SEQUANI, ARVERNI, ALLY, 1)
    _set_tribe_allied(state, TRIBE_HELVETII, ARVERNI)
    place_piece(state, SEQUANI, ARVERNI, ALLY, 1)
    place_piece(state, SEQUANI, ARVERNI, WARBAND, 6)
    place_piece(state, SEQUANI, AEDUI, WARBAND, 1)
    place_piece(state, SEQUANI, GERMANS, SETTLEMENT, 1)
    place_piece(state, SEQUANI, GERMANS, WARBAND, 4)

    # Arverni: Arverni Control (Arverni Home)
    # Arverni<Gergovia>=Arverni Ally (no Citadel), 2x Arverni Warbands
    _set_tribe_allied(state, TRIBE_ARVERNI, ARVERNI)
    place_piece(state, ARVERNI_REGION, ARVERNI, ALLY, 1)
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 2)

    # --- PROVINCIA ---
    # Roman Control, Caesar, 6x Legions, 8x Auxilia,
    # Roman Fort (permanent — already placed)
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, PROVINCIA, ROMANS, LEGION, 6,
                from_legions_track=True)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 8)

    # (Bituriges is empty)

    # --- Legions Track ---
    # 2x on middle row, 4x on bottom row. 6 placed on map, 6 remain.
    _set_legions_track(state, bottom=4, middle=2)

    # --- Refresh control ---
    refresh_all_control(state)

    # --- Deck ---
    # Ariovistus deck: 45 Events, Winter in 3rd, 6th, 9th piles.
    _build_ariovistus_deck(state, 45, [3, 6, 9])


# ============================================================================
# SCENARIO: THE GALLIC WAR (58-50 BC)
# ============================================================================

def _setup_gallic_war(state):
    """Set up The Gallic War scenario (first half = Ariovistus setup).

    Reference: A Scenario: The Gallic War
    The first half uses the Ariovistus scenario setup.
    The Interlude is handled separately during gameplay.
    """
    # The Gallic War first half is identical to Ariovistus setup
    _setup_ariovistus(state)

    # Override the deck for Gallic War first half:
    # Same as Ariovistus: 45 Events, Winter in 3rd, 6th, 9th piles
    # (already built by _setup_ariovistus)

    # Mark this as the Gallic War scenario (already set in state)
    # The interlude/second half is handled separately during gameplay


# ============================================================================
# PUBLIC API
# ============================================================================

_SETUP_FUNCTIONS = {
    SCENARIO_PAX_GALLICA: _setup_pax_gallica,
    SCENARIO_RECONQUEST: _setup_reconquest,
    SCENARIO_GREAT_REVOLT: _setup_great_revolt,
    SCENARIO_ARIOVISTUS: _setup_ariovistus,
    SCENARIO_GALLIC_WAR: _setup_gallic_war,
}


def setup_scenario(scenario, seed=None):
    """Set up a scenario and return the initial game state.

    Args:
        scenario: Scenario identifier from rules_consts.
        seed: Optional RNG seed for deterministic replay.

    Returns:
        Complete game state dictionary, validated.

    Raises:
        ValueError: If scenario is unknown.
        PieceError: If setup violates piece rules (indicates a bug).
    """
    if scenario not in _SETUP_FUNCTIONS:
        raise ValueError(f"Unknown scenario: {scenario}")

    state = build_initial_state(scenario, seed=seed)
    _SETUP_FUNCTIONS[scenario](state)

    # Validate state integrity
    errors = validate_state(state)
    if errors:
        raise ValueError(
            f"State validation failed after setup:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return state
