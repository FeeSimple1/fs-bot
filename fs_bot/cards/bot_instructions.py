"""
bot_instructions.py — Per-card per-faction lookup of non-player bot event instructions.

Parsed from the 8 bot event instruction files:
  Base: roman_, arverni_, aedui_, belgae_bot_event_instructions.txt
  Ariovistus: roman_, aedui_, belgae_, german_bot_event_instructions_ariovistus.txt

Each entry stores:
- action: what the NP faction does (PLAY_UNSHADED, PLAY_SHADED, COMMAND_SA,
  COMMAND_ONLY, NO_EVENT)
- instruction: detailed text for conditional/special handling
- condition: string describing game-state condition, or None

The NP instruction symbols from the Card Reference (L/S/C) encode the
DEFAULT action for each faction on each card:
  C (Carnyx) = play the Event (auto 1-4 for Arverni/Germans)
  L (Laurels) = specific instructions listed in the instruction file
  S (Swords) = "No [Faction]" — skip event, continue on flowchart

Source: §8.2.1, A8.2.1, all *_bot_event_instructions*.txt files
"""

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
    NP_SYMBOL_CARNYX, NP_SYMBOL_LAURELS, NP_SYMBOL_SWORDS,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)

# ---------------------------------------------------------------------------
# Action constants for bot event decisions
# ---------------------------------------------------------------------------

# Carnyx (C): Bot plays the Event automatically (roll 1-4 for Arverni/Germans)
PLAY_EVENT = "Play Event"

# Laurels (L): Bot has specific instructions — may play unshaded, shaded,
# or conditionally decide
SPECIFIC_INSTRUCTION = "Specific Instruction"

# Swords (S): "No [Faction]" — skip event, continue on flowchart
NO_EVENT = "No Event"

# Conditional: instruction file specifies "if X then Y else Z"
CONDITIONAL = "Conditional"


class BotInstruction:
    """One faction's instruction for one card."""

    __slots__ = ("card_id", "faction", "action", "instruction",
                 "no_event_cards", "conditional_no_event")

    def __init__(self, card_id, faction, action, instruction=None,
                 no_event_cards=None, conditional_no_event=False):
        self.card_id = card_id
        self.faction = faction
        self.action = action
        self.instruction = instruction
        # Cards listed in "No [Faction]" general section
        self.no_event_cards = no_event_cards or set()
        # Some cards have conditional no-event (e.g. "No Aedui if Roman
        # player or Roman victory exceeds 12")
        self.conditional_no_event = conditional_no_event

    def __repr__(self):
        return (f"BotInstruction(card_id={self.card_id!r}, "
                f"faction={self.faction!r}, action={self.action!r})")


# ---------------------------------------------------------------------------
# Reverse lookup: card title -> base card ID(s)
# ---------------------------------------------------------------------------

_TITLE_TO_BASE_IDS = {}
for _cid, _title in CARD_NAMES_BASE.items():
    _TITLE_TO_BASE_IDS.setdefault(_title, []).append(_cid)

_TITLE_TO_ARIOVISTUS_IDS = {}
for _cid, _title in CARD_NAMES_ARIOVISTUS.items():
    _TITLE_TO_ARIOVISTUS_IDS.setdefault(_title, []).append(_cid)


def _resolve_card_ids_base(title):
    """Resolve a card title to base game card ID(s)."""
    if title in _TITLE_TO_BASE_IDS:
        return _TITLE_TO_BASE_IDS[title]
    return []


def _resolve_card_ids_ariovistus(title):
    """Resolve a card title to Ariovistus card ID(s).

    Checks both A-prefix cards and base cards that remain in the
    Ariovistus deck.
    """
    ids = []
    # Check A-prefix cards first
    if title in _TITLE_TO_ARIOVISTUS_IDS:
        ids.extend(_TITLE_TO_ARIOVISTUS_IDS[title])
    # Also check base cards (many base cards remain in Ariovistus deck)
    if title in _TITLE_TO_BASE_IDS:
        ids.extend(_TITLE_TO_BASE_IDS[title])
    # Deduplicate while preserving order
    seen = set()
    result = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


# ---------------------------------------------------------------------------
# Parse the bot event instruction files
# ---------------------------------------------------------------------------

# Base game instruction tables: {(card_id, faction): BotInstruction}
_BASE_INSTRUCTIONS = {}

# Ariovistus instruction tables: {(card_id, faction): BotInstruction}
_ARIOVISTUS_INSTRUCTIONS = {}


def _parse_no_event_cards(text):
    """Parse a comma-separated list of card titles from a 'No [Faction]' block."""
    # Clean up multi-line text and extract card titles
    # The text after the colon contains card titles separated by commas
    titles = set()
    for part in text.split(","):
        part = part.strip()
        # Remove trailing instructions like "Continue on flowchart instead."
        # or "Continue on the flowchart instead."
        for suffix in ["Continue on flowchart instead.",
                       "Continue on flowchart instead",
                       "Continue on the flowchart instead.",
                       "Continue on the flowchart instead",
                       ": Continue on flowchart instead."]:
            if part.endswith(suffix):
                part = part[:len(part) - len(suffix)].strip()
                # Remove trailing colon/period
                part = part.rstrip(":").rstrip(".").strip()
        if part and not part.startswith("("):
            titles.add(part)
    return titles


def _build_base_roman_instructions():
    """Build Roman base game bot instructions from parsed reference data."""
    faction = ROMANS

    # "No Romans" cards — Swords (S)
    no_roman_titles = {
        "Chieftains' Council", "Consuetudine", "Convictolitavis", "Druids",
        "Gallic Shouts", "Joined Ranks", "Oppida", "Optimates",
        "River Commerce", "Segni & Condrusi", "Suebi Mobilize", "Surus",
    }

    # Per-card specific instructions (Laurels)
    per_card_instructions = {
        "Aquitani": "Target Arverni and then Belgae, not Aedui.",
        "Assembly of Gaul": "Target Arverni and then Belgae, not Aedui.",
        "Celtic Rites": "Target Arverni and then Belgae, not Aedui.",
        "Sappers": "Target Arverni and then Belgae, not Aedui.",
        "German Allegiances": "March from Romans to no Romans; Ambush per Roman Battle (8.8.1); avoid placing any Germanic Allies; if not possible, treat as 'No Romans'.",
        "Germanic Chieftains": "March from Romans to no Romans; Ambush per Roman Battle (8.8.1); avoid placing any Germanic Allies; if not possible, treat as 'No Romans'.",
        "Migration": "March from Romans to no Romans; Ambush per Roman Battle (8.8.1); avoid placing any Germanic Allies; if not possible, treat as 'No Romans'.",
        "Cicero": "Shift down (toward Adulation, or flip to Firm if already in Adulation and not yet Firm).",
        "Drought": "Place marker to remove player Arverni and/or Belgae (not Non-player) and no Romans.",
        "Forced Marches": "Move Forces using Roman March priorities (8.8.3), then use the full Roman flowchart for any follow-on actions (8.2.3).",
        "War Fleet": "Move Forces using Roman March priorities (8.8.3), then use the full Roman flowchart for any follow-on actions (8.2.3).",
        "Impetuosity": "Unless Roman March priorities (8.2.3, 8.8.3) would result in a Battle, treat as 'No Romans'.",
        "Legiones XIIII et XV": "Place the 2 Legions; if fewer would be placed, treat as 'No Romans'.",
        "Lucterius": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "Numidians": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "The Province": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "Shifting Loyalties": "Select a shaded Capability affecting player Arverni or Belgae, then Romans.",
    }

    for card_id in range(1, 73):
        title = CARD_NAMES_BASE[card_id]
        if title in no_roman_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=NO_EVENT,
                instruction=f"No Romans: {title}",
            )
        elif title in per_card_instructions:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=SPECIFIC_INSTRUCTION,
                instruction=per_card_instructions[title],
            )
        else:
            # No specific instruction — use NP symbol from card data
            # (will be cross-referenced in tests)
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=PLAY_EVENT,
                instruction=None,
            )


def _build_base_arverni_instructions():
    """Build Arverni base game bot instructions from parsed reference data."""
    faction = ARVERNI

    # "No Arverni" cards — Swords (S)
    no_arverni_titles = {
        "Ballistae", "Catuvolcus", "Chieftains' Council", "Circumvallation",
        "Commius", "Correus", "Indutiomarus", "Joined Ranks", "Migration",
    }

    # "Auto 1-4" cards — Carnyx (C): play Event automatically
    auto_titles = {
        "Alaudae", "Balearic Slingers", "Clodius Pulcher", "Gallia Togata",
        "Germanic Horse", "Legio X", "Legiones XIIII et XV", "Lost Eagle",
        "Lucterius", "Massed Gallic Archers", "Pompey", "Sacking", "Sappers",
        "The Province", "Vercingetorix's Elite",
    }

    # Per-card specific instructions (Laurels)
    per_card_instructions = {
        "Acco": "Unless shaded text would place Arverni Citadel, use unshaded text (selecting Arverni, 8.2.3).",
        "Ambacti": "Select Auxilia first to leave Legions without Auxilia in as many Regions as possible.",
        "Dumnorix Loyalists": "Select Auxilia first to leave Legions without Auxilia in as many Regions as possible.",
        "Marcus Antonius": "Select Auxilia first to leave Legions without Auxilia in as many Regions as possible.",
        "Numidians": "Select Auxilia first to leave Legions without Auxilia in as many Regions as possible.",
        "Arduenna": "March and Battle to inflict maximum Losses on Legions; if none possible, treat as 'No Arverni'.",
        "Assembly of Gaul": "If Arverni do not qualify for the benefit, treat as 'No Arverni'.",
        "Remi Influence": "If Arverni do not qualify for the benefit, treat as 'No Arverni'.",
        "Cicero": "Shift up (toward Uproar, or flip to Uproar and not yet Firm).",
        "Forced Marches": "If <9 Arverni Allies+Citadels, treat as 'No Arverni'; move only per 8.7.6.",
        "Optimates": "If <9 Arverni Allies+Citadels, treat as 'No Arverni'; move only per 8.7.6.",
        "Impetuosity": "Move as many Warbands and Leader (if applicable) as possible to take Arverni Control of a Region with player pieces — Roman, then Aedui, then Belgae — then Battle that player there.",
        "War Fleet": "Move as many Warbands and Leader (if applicable) as possible to take Arverni Control of a Region with player pieces — Roman, then Aedui, then Belgae — then Battle that player there.",
        "Shifting Loyalties": "Select an unshaded Capability affecting player Romans or Aedui, then Arverni.",
    }

    for card_id in range(1, 73):
        title = CARD_NAMES_BASE[card_id]
        if title in no_arverni_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=NO_EVENT,
                instruction=f"No Arverni: {title}",
            )
        elif title in auto_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=PLAY_EVENT,
                instruction="Auto 1-4: play Event.",
            )
        elif title in per_card_instructions:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=SPECIFIC_INSTRUCTION,
                instruction=per_card_instructions[title],
            )
        else:
            # Default from NP symbol
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=PLAY_EVENT,
                instruction=None,
            )


def _build_base_aedui_instructions():
    """Build Aedui base game bot instructions from parsed reference data."""
    faction = AEDUI

    # "No Aedui" cards — Swords (S)
    no_aedui_titles = {
        "Aduatuca", "Chieftains' Council", "Cicero", "Consuetudine",
        "Forced Marches", "Germanic Chieftains", "Impetuosity", "Joined Ranks",
        "Optimates", "Sacking", "Segni & Condrusi", "Suebi Mobilize",
    }

    # "No Aedui if Roman player or Roman victory exceeds 12" — conditional
    conditional_no_aedui_titles = {
        "Alaudae", "Ambacti", "Balearic Slingers", "Circumvallation",
        "Clodius Pulcher", "Commius", "Cotuatus & Conconnetodumnus",
        "Flight of Ambiorix", "Gallia Togata", "Legio X",
        "Legiones XIIII et XV", "Marcus Antonius", "Numidians", "Pompey",
        "The Province", "Titus Labienus",
    }

    # Per-card shaded instructions
    shaded_instruction_titles = {
        "Aquitani", "Baggage Trains", "Ballistae", "Camulogenus",
        "Celtic Rites", "Gallic Shouts", "German Allegiances",
        "Germanic Horse", "Remi Influence", "Winter Campaign",
    }

    # Per-card target instructions
    target_instruction_titles = {
        "Assembly of Gaul", "Catuvolcus", "Drought", "Lucterius",
        "Morasses", "Roman Wine", "Sappers",
    }

    per_card_instructions = {
        "Aquitani": "Use shaded text.",
        "Baggage Trains": "Use shaded text.",
        "Ballistae": "Use shaded text.",
        "Camulogenus": "Use shaded text.",
        "Celtic Rites": "Use shaded text.",
        "Gallic Shouts": "Use shaded text.",
        "German Allegiances": "Use shaded text.",
        "Germanic Horse": "Use shaded text.",
        "Remi Influence": "Use shaded text; if Remi are not an Aedui Ally, treat as 'No Aedui' instead.",
        "Winter Campaign": "Use shaded text.",
        "Assembly of Gaul": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Catuvolcus": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Drought": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Lucterius": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Morasses": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Roman Wine": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Sappers": "Select Factions, Regions, and pieces to target player Arverni and/or Belgae only (not Non-player).",
        "Dumnorix Loyalists": "Move no pieces on the Scout; Scout Hidden Arverni, then Belgae, then Germans.",
        "Migration": "Use shaded text; move 2 random Warbands.",
        "Shifting Loyalties": "Select a shaded Capability affecting a player Gaul, then with Aedui symbol 1st on the card.",
        "War Fleet": "Move single largest group possible to a random Region; Rally if places pieces, otherwise Raid.",
    }

    for card_id in range(1, 73):
        title = CARD_NAMES_BASE[card_id]
        if title in no_aedui_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=NO_EVENT,
                instruction=f"No Aedui: {title}",
            )
        elif title in conditional_no_aedui_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=CONDITIONAL,
                instruction=(
                    "If the Romans are a player, or if Non-player Roman "
                    "victory (Subdued+Allies+Dispersed) exceeds 12, treat "
                    "as 'No Aedui' instead."
                ),
                conditional_no_event=True,
            )
        elif title in per_card_instructions:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=SPECIFIC_INSTRUCTION,
                instruction=per_card_instructions[title],
            )
        else:
            # Default from NP symbol
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=PLAY_EVENT,
                instruction=None,
            )


def _build_base_belgae_instructions():
    """Build Belgae base game bot instructions from parsed reference data."""
    faction = BELGAE

    # "No Belgae" cards — Swords (S)
    no_belgae_titles = {
        "Aquitani", "Assembly of Gaul", "Ballistae", "Boii",
        "Chieftains' Council", "Circumvallation", "Consuetudine",
        "Forced Marches", "Germanic Chieftains", "Gobannitio",
        "Joined Ranks", "Optimates", "River Commerce",
        "Segni & Condrusi", "The Province",
    }

    per_card_instructions = {
        "Acco": "Use unshaded text.",
        "Alaudae": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead. If playing 'Cicero', shift up.",
        "Cicero": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead. If playing 'Cicero', shift up.",
        "Gallia Togata": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead.",
        "Lost Eagle": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead.",
        "Pompey": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead.",
        "Sappers": "If Arverni are meeting their victory condition (7.2), or if Roman Non-player, treat as 'No Belgae' instead.",
        "Alpine Tribes": "If Roman Non-player, treat as 'No Belgae'.",
        "Balearic Slingers": "If Roman Non-player, treat as 'No Belgae'.",
        "Legio X": "If Roman Non-player, treat as 'No Belgae'.",
        "Titus Labienus": "If Roman Non-player, treat as 'No Belgae'.",
        "Ambacti": "Select Belgica Regions first.",
        "Hostages": "Select Belgica Regions first.",
        "Marcus Antonius": "Select Belgica Regions first.",
        "Numidians": "Select Belgica Regions first.",
        "Roman Wine": "Select Belgica Regions first.",
        "Correus": "Unless adding to total number of Belgic Allies plus Citadels, treat as 'No Belgae'.",
        "German Allegiances": "Unless adding to total number of Belgic Allies plus Citadels, treat as 'No Belgae'.",
        "Land of Mist and Mystery": "Unless adding to total number of Belgic Allies plus Citadels, treat as 'No Belgae'.",
        "Remi Influence": "Unless adding to total number of Belgic Allies plus Citadels, treat as 'No Belgae'.",
        "Impetuosity": "Move most pieces able to Battle player with highest victory margin.",
        "Legiones XIIII et XV": "Battle where most Losses forced on Legions; if none, treat as 'No Belgae'.",
        "Litaviccus": "Battle where most Losses forced on Legions; if none, treat as 'No Belgae'.",
        "Massed Gallic Archers": "If Arverni are a player and Romans are a Non-player, use unshaded text; otherwise, treat as 'No Belgae' instead.",
        "Vercingetorix's Elite": "If Arverni are a player and Romans are a Non-player, use unshaded text; otherwise, treat as 'No Belgae' instead.",
        "Migration": "Losing no Belgic Control, move just enough Warbands to add Belgic Control where a Subdued Tribe; for Migration, place an Ally; for War Fleet, Rally.",
        "War Fleet": "Losing no Belgic Control, move just enough Warbands to add Belgic Control where a Subdued Tribe; for Migration, place an Ally; for War Fleet, Rally.",
        "Morasses": "Ambush all Romans then Gauls where Losses possible, then March in place to go Hidden.",
        "Shifting Loyalties": "Select an unshaded Capability affecting player Romans or Aedui, then Belgae.",
    }

    for card_id in range(1, 73):
        title = CARD_NAMES_BASE[card_id]
        if title in no_belgae_titles:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=NO_EVENT,
                instruction=f"No Belgae: {title}",
            )
        elif title in per_card_instructions:
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=SPECIFIC_INSTRUCTION,
                instruction=per_card_instructions[title],
            )
        else:
            # Default from NP symbol
            _BASE_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                card_id=card_id, faction=faction,
                action=PLAY_EVENT,
                instruction=None,
            )


# ---------------------------------------------------------------------------
# Ariovistus instruction builders
# ---------------------------------------------------------------------------

def _get_ariovistus_deck_card_ids():
    """Get all card IDs in the Ariovistus deck (excluding Winter cards).

    Returns dict mapping card title -> list of card_ids in the Ariovistus deck.
    """
    from fs_bot.cards.card_data import get_ariovistus_event_card_ids, get_card
    from fs_bot.rules_consts import SCENARIO_ARIOVISTUS
    title_to_ids = {}
    for cid in get_ariovistus_event_card_ids():
        card = get_card(cid, SCENARIO_ARIOVISTUS)
        title_to_ids.setdefault(card.title, []).append(cid)
    return title_to_ids


def _build_ariovistus_roman_instructions():
    """Build Roman Ariovistus bot instructions."""
    faction = ROMANS
    title_to_ids = _get_ariovistus_deck_card_ids()

    no_roman_titles = {
        "Abatis", "All Gaul Gathers", "Chieftains' Council", "Divination",
        "Druids", "Joined Ranks", "River Commerce", "Seduni Uprising!",
        "Sotiates Uprising!", "Veneti Uprising!", "Winter Uprising!",
    }

    per_card_instructions = {
        "Assembly of Gaul": "Target Belgae, not Aedui.",
        "Celtic Rites": "Target Belgae, not Aedui.",
        "Cicero": "Shift down (toward Adulation, or flip to Firm if already in Adulation and not yet Firm).",
        "Drought": "Place marker to remove player Germans and/or Belgae (not Non-player) and no Romans.",
        "Frumentum": "If Aedui player, treat as 'No Romans'; otherwise, use flowchart (8.2.3), Aedui transfer per A8.6.6.",
        "Harudes": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "Nasua & Cimberius": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "Numidians": "Place the full number of Auxilia; if not able, treat as 'No Romans'.",
        "Impetuosity": "Unless Roman March priorities (8.2.3, 8.8.3) would result in a Battle, treat as 'No Romans'.",
        "Legiones XIIII et XV": "Place the 2 Legions; if fewer would be placed, treat as 'No Romans'.",
        "Nervii": "If Belgae Non-player, treat as 'No Romans'.",
        "Parley": "Play only to move Romans and/or Germans to where Fort and Romans will outnumber Germans.",
        "Publius Licinius Crassus": "Move Forces using Roman March priorities (8.8.3), then use Roman Battle priorities (8.8.1).",
        "War Fleet": "Move Forces using Roman March priorities (8.8.3), then the full Roman flowchart for a follow-on Command (8.2.3).",
        "Shifting Loyalties": "Select a shaded Capability affecting player Germans or Belgae, then Romans.",
        "Vergobret": "If Aedui player, treat as 'No Romans'.",
    }

    for title, card_ids in title_to_ids.items():
        for card_id in card_ids:
            if title in no_roman_titles:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=NO_EVENT,
                    instruction=f"No Romans: {title}",
                )
            elif title in per_card_instructions:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=SPECIFIC_INSTRUCTION,
                    instruction=per_card_instructions[title],
                )
            else:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=PLAY_EVENT,
                    instruction=None,
                )


def _build_ariovistus_aedui_instructions():
    """Build Aedui Ariovistus bot instructions."""
    faction = AEDUI
    title_to_ids = _get_ariovistus_deck_card_ids()

    no_aedui_titles = {
        "Chieftains' Council", "Cicero", "Divination",
        "Gaius Valerius Procillus", "Impetuosity", "Joined Ranks",
        "Seduni Uprising!", "Sotiates Uprising!", "Veneti Uprising!",
        "Winter Uprising!",
    }

    conditional_no_aedui_titles = {
        "Alaudae", "Ambacti", "Ariovistus's Wife", "Balearic Slingers",
        "Circumvallation", "Clodius Pulcher", "Commius", "Dread",
        "Gallia Togata", "Iccius & Andecomborius", "Legio X",
        "Legiones XIIII et XV", "Marcus Antonius", "Numidians", "Pompey",
        "Publius Licinius Crassus", "Titus Labienus",
    }

    per_card_instructions = {
        "All Gaul Gathers": "Move no pieces; Scout Hidden Germans, then Belgae, then Arverni.",
        "Dumnorix Loyalists": "Move no pieces; Scout Hidden Germans, then Belgae, then Arverni.",
        "Assembly of Gaul": "Select Factions, Regions, and pieces to target player Germans and/or Belgae only (not Non-player).",
        "Catuvolcus": "Select Factions, Regions, and pieces to target player Germans and/or Belgae only (not Non-player).",
        "Drought": "Select Factions, Regions, and pieces to target player Germans and/or Belgae only (not Non-player).",
        "Galba": "Select Factions, Regions, and pieces to target player Germans and/or Belgae only (not Non-player).",
        "Roman Wine": "Select Factions, Regions, and pieces to target player Germans and/or Belgae only (not Non-player).",
        "Baggage Trains": "Use shaded text.",
        "Ballistae": "Use shaded text.",
        "Celtic Rites": "Use shaded text.",
        "Germanic Horse": "Use shaded text.",
        "Remi Influence": "Use shaded text; if Remi are not an Aedui Ally, treat as 'No Aedui' instead.",
        "Winter Campaign": "Use shaded text.",
        "Divico": "If Aedui have both more Warbands and more Allies+Citadels than Arverni, treat as 'No Aedui'.",
        "Morbihan": "If Aedui have both more Warbands and more Allies+Citadels than Arverni, treat as 'No Aedui'.",
        "Orgetorix": "If Aedui have both more Warbands and more Allies+Citadels than Arverni, treat as 'No Aedui'.",
        "Frumentum": "If Roman player, treat as 'No Aedui'; otherwise, transfer Resources per A8.6.6.",
        "Nervii": "If Belgae Non-player, treat as 'No Aedui'.",
        "Shifting Loyalties": "Select a shaded Capability affecting player Germans or Belgae, then with Aedui symbol 1st on the card.",
        "War Fleet": "Move single largest group possible to a random Region; Rally if places pieces, otherwise Raid.",
    }

    for title, card_ids in title_to_ids.items():
        for card_id in card_ids:
            if title in no_aedui_titles:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=NO_EVENT,
                    instruction=f"No Aedui: {title}",
                )
            elif title in conditional_no_aedui_titles:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=CONDITIONAL,
                    instruction=(
                        "If the Romans are a player, or if Non-player Roman "
                        "victory (Subdued+Allies+Dispersed-Settlement) exceeds "
                        "12, treat as 'No Aedui'."
                    ),
                    conditional_no_event=True,
                )
            elif title in per_card_instructions:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=SPECIFIC_INSTRUCTION,
                    instruction=per_card_instructions[title],
                )
            else:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=PLAY_EVENT,
                    instruction=None,
                )


def _build_ariovistus_belgae_instructions():
    """Build Belgae Ariovistus bot instructions."""
    faction = BELGAE
    title_to_ids = _get_ariovistus_deck_card_ids()

    no_belgae_titles = {
        "Ariovistus's Wife", "Assembly of Gaul", "Ballistae",
        "Chieftains' Council", "Circumvallation", "Dread", "German Phalanx",
        "Harudes", "Joined Ranks", "Nasua & Cimberius", "River Commerce",
        "Usipetes & Tencteri", "Wailing Women",
    }

    per_card_instructions = {
        "Admagetobriga": "Battle where most Losses forced on Legions; if none, 'No Belgae'.",
        "Legiones XIIII et XV": "Battle where most Losses forced on Legions; if none, 'No Belgae'.",
        "Sabis": "Battle where most Losses forced on Legions; if none, 'No Belgae'.",
        "Vosegus": "Battle where most Losses forced on Legions; if none, 'No Belgae'.",
        "Savage Dictates": "If Germans a player, use unshaded text; otherwise, treat as 'No Belgae'.",
        "Alaudae": "If German player or if Roman Non-player, treat as 'No Belgae' instead.",
        "Cicero": "If German player or if Roman Non-player, treat as 'No Belgae' instead. If playing 'Cicero', shift up.",
        "Gallia Togata": "If German player or if Roman Non-player, treat as 'No Belgae' instead.",
        "Pompey": "If German player or if Roman Non-player, treat as 'No Belgae' instead.",
        "Alpine Tribes": "If Roman Non-player, treat as 'No Belgae'.",
        "Balearic Slingers": "If Roman Non-player, treat as 'No Belgae'.",
        "Legio X": "If Roman Non-player, treat as 'No Belgae'.",
        "Titus Labienus": "If Roman Non-player, treat as 'No Belgae'.",
        "Ambacti": "Select Belgica Regions first.",
        "Marcus Antonius": "Select Belgica Regions first.",
        "Numidians": "Select Belgica Regions first.",
        "Publius Licinius Crassus": "Select Belgica Regions first.",
        "Roman Wine": "Select Belgica Regions first.",
        "Impetuosity": "Only as Belgic Leader ends with at least 4 Belgic Warbands, move most pieces able to Battle player with highest victory margin.",
        "Kinship": "If Germans Non-player, treat as 'No Belgae'.",
        "Remi Influence": "Unless adding to total number of Belgic Allies plus Citadels, treat as 'No Belgae'.",
        "Shifting Loyalties": "Select an unshaded Capability affecting player Romans or Aedui, then Belgae.",
        "War Fleet": "Losing no Belgic Control, move just enough Warbands to add Belgic Control where a Subdued Tribe; then Rally.",
        "Winter Uprising!": "If next Winter is the last, treat as 'No Belgae'; if not, place in Belgica, remove when able.",
    }

    for title, card_ids in title_to_ids.items():
        for card_id in card_ids:
            if title in no_belgae_titles:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=NO_EVENT,
                    instruction=f"No Belgae: {title}",
                )
            elif title in per_card_instructions:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=SPECIFIC_INSTRUCTION,
                    instruction=per_card_instructions[title],
                )
            else:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=PLAY_EVENT,
                    instruction=None,
                )


def _build_ariovistus_german_instructions():
    """Build German Ariovistus bot instructions."""
    faction = GERMANS
    title_to_ids = _get_ariovistus_deck_card_ids()

    no_german_titles = {
        "Ballistae", "Bellovaci", "Catuvolcus", "Chieftains' Council",
        "Circumvallation", "Commius", "Galba",
        "Iccius & Andecomborius", "Joined Ranks", "Nervii",
    }

    per_card_instructions = {
        "Admagetobriga": "Battle only where Counterattack would not leave Ariovistus with fewer than 4 Warbands.",
        "Legiones XIIII et XV": "Battle only where Counterattack would not leave Ariovistus with fewer than 4 Warbands.",
        "Sabis": "Battle only where Counterattack would not leave Ariovistus with fewer than 4 Warbands.",
        "Vosegus": "Battle only where Counterattack would not leave Ariovistus with fewer than 4 Warbands.",
        "Alaudae": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Ambacti": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Dumnorix Loyalists": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Marcus Antonius": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Numidians": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Publius Licinius Crassus": "Select Roman pieces to remove the most possible from Germania or where Settlement, then adjacent to Germania or Settlement; if none, treat as 'No Germans'.",
        "Arduenna": "Move as many Warbands and Leader (if applicable) as possible without losing Germanic Control to take Germanic Control of a Region with player pieces — Roman, then Aedui, then Belgae — then Battle that player there.",
        "Impetuosity": "Move as many Warbands and Leader (if applicable) as possible without losing Germanic Control to take Germanic Control of a Region with player pieces — Roman, then Aedui, then Belgae — then Battle that player there.",
        "Assembly of Gaul": "Select Germans then Non-player Belgae if they qualify, otherwise treat as 'No Germans'.",
        "Balearic Slingers": "If Romans are a Non-Player, treat as 'No Germans'.",
        "Clodius Pulcher": "If Romans are a Non-Player, treat as 'No Germans'.",
        "Legio X": "If Romans are a Non-Player, treat as 'No Germans'.",
        "Pompey": "If Romans are a Non-Player, treat as 'No Germans'.",
        "Cicero": "Shift up (toward Uproar, or flip to Firm if already in Uproar and not yet Firm).",
        "Divico": "Remove no German Allies or Control; if not possible, treat as 'No Germans'.",
        "Orgetorix": "Remove no German Allies or Control; if not possible, treat as 'No Germans'.",
        "Seduni Uprising!": "Remove no German Allies or Control; if not possible, treat as 'No Germans'.",
        "Germanic Horse": "Treat as 'No Germans'.",
        "Remi Influence": "Treat as 'No Germans'.",
        "War Fleet": "Treat as 'No Germans'.",
        "Kinship": "If Belgae Non-player, treat as 'No Germans'.",
        "Shifting Loyalties": "Select an unshaded Capability affecting player Romans or Aedui, then Germans.",
        "Winter Uprising!": "If next Winter is the last, treat as 'No Germans'; if not, place in Germania, remove when able.",
        "Gaius Valerius Procillus": "Play only to move to where no Fort and Germans will outnumber Romans.",
        "Parley": "Play only to move to where no Fort and Germans will outnumber Romans.",
    }

    for title, card_ids in title_to_ids.items():
        for card_id in card_ids:
            if title in no_german_titles:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=NO_EVENT,
                    instruction=f"No Germans: {title}",
                )
            elif title in per_card_instructions:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=SPECIFIC_INSTRUCTION,
                    instruction=per_card_instructions[title],
                )
            else:
                _ARIOVISTUS_INSTRUCTIONS[(card_id, faction)] = BotInstruction(
                    card_id=card_id, faction=faction,
                    action=PLAY_EVENT,
                    instruction=None,
                )


# ---------------------------------------------------------------------------
# Initialize all instruction tables
# ---------------------------------------------------------------------------

_build_base_roman_instructions()
_build_base_arverni_instructions()
_build_base_aedui_instructions()
_build_base_belgae_instructions()
_build_ariovistus_roman_instructions()
_build_ariovistus_aedui_instructions()
_build_ariovistus_belgae_instructions()
_build_ariovistus_german_instructions()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_bot_instruction(card_id, faction, scenario):
    """Look up what a non-player faction does for a given card.

    Args:
        card_id: int or str card identifier
        faction: faction constant (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS)
        scenario: scenario constant

    Returns:
        BotInstruction instance

    Raises:
        KeyError if no instruction found for the combination
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        key = (card_id, faction)
        if key in _ARIOVISTUS_INSTRUCTIONS:
            return _ARIOVISTUS_INSTRUCTIONS[key]
        raise KeyError(
            f"No Ariovistus bot instruction for card {card_id!r}, "
            f"faction {faction!r}"
        )
    else:
        key = (card_id, faction)
        if key in _BASE_INSTRUCTIONS:
            return _BASE_INSTRUCTIONS[key]
        raise KeyError(
            f"No base game bot instruction for card {card_id!r}, "
            f"faction {faction!r}"
        )


def get_base_instructions():
    """Return dict of all base game instructions: {(card_id, faction): BotInstruction}."""
    return dict(_BASE_INSTRUCTIONS)


def get_ariovistus_instructions():
    """Return dict of all Ariovistus instructions: {(card_id, faction): BotInstruction}."""
    return dict(_ARIOVISTUS_INSTRUCTIONS)


def get_factions_with_instructions(scenario):
    """Return which factions have bot instruction tables for a scenario.

    Base game: Romans, Arverni, Aedui, Belgae
    Ariovistus: Romans, Aedui, Belgae, Germans (no Arverni — game-run)
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        return (ROMANS, AEDUI, BELGAE, GERMANS)
    return (ROMANS, ARVERNI, AEDUI, BELGAE)
