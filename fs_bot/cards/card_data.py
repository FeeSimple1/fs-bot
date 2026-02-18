"""
card_data.py — Structured metadata for every Event card.

Each card has:
- card_id: int for base cards, str (e.g. "A5") for Ariovistus-only cards
- title: from CARD_NAMES_BASE / CARD_NAMES_ARIOVISTUS
- faction_order: tuple of faction constants in card initiative order
- np_symbols: dict mapping faction to NP instruction symbol (L/S/C)
- is_capability: bool
- is_winter: bool (True only for Winter cards)
- has_carnyx_trigger: bool (True for Ariovistus cards with carnyx symbol — A2.3.9)

Source: Card Reference, A Card Reference, rules_consts.py
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Card name dicts
    CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
    # Capability dicts
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # NP symbols
    NP_SYMBOL_CARNYX, NP_SYMBOL_LAURELS, NP_SYMBOL_SWORDS,
    # Winter
    WINTER_CARD,
    # 2nd Edition replacement keys (for text lookup only, not deck composition)
    SECOND_EDITION_CARDS,
)

# ---------------------------------------------------------------------------
# Faction abbreviation mapping (Card Reference header)
# ---------------------------------------------------------------------------
_FACTION_FROM_ABBREV = {
    "Ro": ROMANS,
    "Ar": ARVERNI,
    "Ae": AEDUI,
    "Be": BELGAE,
    "Ge": GERMANS,
}

_NP_FROM_ABBREV = {
    "C": NP_SYMBOL_CARNYX,
    "L": NP_SYMBOL_LAURELS,
    "S": NP_SYMBOL_SWORDS,
}


# ---------------------------------------------------------------------------
# CardData namedtuple-like class
# ---------------------------------------------------------------------------
class CardData:
    """Metadata for one Event card."""

    __slots__ = (
        "card_id", "title", "faction_order", "np_symbols",
        "is_capability", "is_winter", "has_carnyx_trigger",
    )

    def __init__(self, card_id, title, faction_order, np_symbols,
                 is_capability=False, is_winter=False,
                 has_carnyx_trigger=False):
        self.card_id = card_id
        self.title = title
        self.faction_order = tuple(faction_order)
        self.np_symbols = dict(np_symbols)
        self.is_capability = is_capability
        self.is_winter = is_winter
        self.has_carnyx_trigger = has_carnyx_trigger

    def __repr__(self):
        return (
            f"CardData(card_id={self.card_id!r}, title={self.title!r}, "
            f"faction_order={self.faction_order}, "
            f"is_capability={self.is_capability})"
        )


def _parse_faction_line(tokens):
    """Parse a sequence of faction/NP-symbol tokens into faction_order and np_symbols.

    Tokens come from the Card Reference after the card title, e.g.:
        ["Ro", "L", "Ar", "C", "Ae", "L", "Be", "L"]

    The faction ORDER is the sequence of faction abbreviations (Ro/Ar/Ae/Be/Ge).
    Each NP symbol (L/S/C) between faction abbreviations applies to the
    faction immediately preceding it.

    Returns (faction_order, np_symbols) where:
      faction_order: tuple of faction constants
      np_symbols: dict {faction: NP_SYMBOL_*}
    """
    faction_order = []
    np_symbols = {}
    current_faction = None

    for tok in tokens:
        if tok in _FACTION_FROM_ABBREV:
            current_faction = _FACTION_FROM_ABBREV[tok]
            faction_order.append(current_faction)
        elif tok in _NP_FROM_ABBREV:
            if current_faction is not None:
                np_symbols[current_faction] = _NP_FROM_ABBREV[tok]
        # else: ignore unexpected tokens

    return tuple(faction_order), np_symbols


# ---------------------------------------------------------------------------
# Raw faction-order data parsed from Card Reference
# Format: card_id -> token string (space-separated faction abbrevs + NP symbols)
# ---------------------------------------------------------------------------

# Base game cards (1–72) — parsed from Card Reference
_BASE_FACTION_TOKENS = {
    1:  "Ro L Ar L Ae S Be L",
    2:  "Ro L Ar C Ae L Be L",
    3:  "Ro Ar C Ae L Be L",
    4:  "Ro Ar S Be S Ae L",
    5:  "Ro Ar C Be L Ae L",
    6:  "Ro Ar L Be L Ae L",
    7:  "Ro Ae L Ar C Be L",
    8:  "Ro Ae L Ar Be",
    9:  "Ro Ae Ar Be",
    10: "Ro Ae L Be S Ar S",
    11: "Ro L Ae L Be L Ar L",
    12: "Ro Ae L Be L Ar",
    13: "Ro Be L Ar C Ae L",
    14: "Ro Be Ar C Ae L",
    15: "Ro Be L Ar C Ae L",
    16: "Ro Be L Ae L Ar L",
    17: "Ro L Be S Ae S Ar",
    18: "Ro Be Ae Ar",
    19: "Ar C Ro L Ae L Be",
    20: "Ar L Ro S Ae S Be S",
    21: "Ar C Ro L Ae L Be S",
    22: "Ar Ro Be L Ae",
    23: "Ar C Ro Be Ae S",
    24: "Ar C Ro L Be L Ae L",
    25: "Ar Ae L Ro L Be S",
    26: "Ar Ae Ro Be S",
    27: "Ar C Ae Ro Be L",
    28: "Ar Ae Be Ro S",
    29: "Ar Ae S Be Ro S",
    30: "Ar C Ae Be L Ro",
    31: "Ar Be Ro Ae L",
    32: "Ar L Be S Ro L Ae S",
    33: "Ar C Be L Ro Ae",
    34: "Ar L Be L Ae Ro",
    35: "Ar Be Ae L Ro S",
    36: "Ar Be L Ae L Ro",
    37: "Ae Ro Ar Be S",
    38: "Ae Ro Ar Be",
    39: "Ae Ro S Ar Be S",
    40: "Ae Ro Be L Ar",
    41: "Ae Ro Be Ar",
    42: "Ae L Ro Be L Ar",
    43: "Ae Ar Ro S Be",
    44: "Ae L Ar L Ro Be",
    45: "Ae Ar Ro Be L",
    46: "Ae L Ar Be Ro L",
    47: "Ae S Ar S Be S Ro S",
    48: "Ae Ar Be Ro S",
    49: "Ae L Be Ro L Ar",
    50: "Ae L Be L Ro L Ar L",
    51: "Ae Be Ro S Ar",
    52: "Ae L Be S Ar L Ro L",
    53: "Ae S Be S Ar Ro S",
    54: "Ae S Be S Ar S Ro S",
    55: "Be Ro Ar S Ae L",
    56: "Be Ro Ar Ae L",
    57: "Be L Ro Ar Ae",
    58: "Be Ro Ae S Ar",
    59: "Be Ro Ae L Ar C",
    60: "Be Ro Ae Ar S",
    61: "Be Ar S Ro Ae L",
    62: "Be L Ar L Ro L Ae L",
    63: "Be Ar Ro Ae L",
    64: "Be L Ar S Ae Ro",
    65: "Be L Ar Ae L Ro L",
    66: "Be L Ar S Ae L Ro L",
    67: "Be Ae Ro Ar L",
    68: "Be L Ae L Ro Ar L",
    69: "Be S Ae S Ro S Ar",
    70: "Be Ae L Ar Ro",
    71: "Be Ae Ar Ro",
    72: "Be L Ae S Ar L Ro L",
}

# Ariovistus replacement/new cards — parsed from A Card Reference
# Keys: "A##" for new cards, int for 2nd-Edition text-change cards
_ARIOVISTUS_FACTION_TOKENS = {
    "A5":  "Ro Ge Be L Ae L C",
    11:    "Ro L Ae L Be L Ar L",
    "A17": "Ro L Be L Ae L Ge L C",
    "A18": "Ro Be Ae Ge C",
    "A19": "Ge L Ro Ae S Be C",
    "A20": "Ge Ro Ae L Be C",
    "A21": "Ge L Ro Ae Be L C",
    "A22": "Ge Ro Be S Ae L",
    "A23": "Ge L Ro L Be Ae",
    "A24": "Ge Ro Be S Ae L",
    "A25": "Ge Ae L Ro Be S",
    "A26": "Ge L Ae L Ro Be",
    "A27": "Ge Ae S Ro S Be",
    "A28": "Ge L Ae Be L Ro",
    "A29": "Ge Ae Be S Ro L",
    "A30": "Ge L Ae L Be Ro",
    30:    "Ar C Ae Be L Ro",
    "A31": "Ge Be S Ro Ae",
    "A32": "Ge Be Ro S Ae S",
    "A33": "Ge Be S Ro Ae",
    "A34": "Ge Be Ae S Ro S",
    "A35": "Ge Be S Ae Ro L",
    "A36": "Ge Be S Ae Ro",
    "A37": "Ae L Ro S Ge Be C",
    "A38": "Ae Ro L Ge Be C",
    39:    "Ae Ro S Ar Be S",
    "A40": "Ae Ro Be L Ge C",
    "A43": "Ae Ge Ro Be C",
    44:    "Ae L Ar L Ro Be",
    "A45": "Ae Ge Ro Be L C",
    "A51": "Ae Be Ro Ge C",
    "A53": "Ae L Be Ge Ro L C",
    54:    "Ae S Be S Ar S Ro S",
    "A56": "Be Ro Ge S Ae L C",
    "A57": "Be L Ro Ge L Ae C",
    "A58": "Be Ro Ae Ge C",
    "A60": "Be Ro Ae L Ge S C",
    "A63": "Be Ge Ro Ae L C",
    "A64": "Be Ge Ae Ro S C",
    "A65": "Be L Ge L Ae Ro C",
    "A66": "Be L Ge L Ae S Ro S C",
    "A67": "Be Ae Ro Ge L C",
    "A69": "Be Ae Ro Ge S C",
    "A70": "Be Ae Ge S Ro C",
}


# ---------------------------------------------------------------------------
# Build the card database
# ---------------------------------------------------------------------------

# Base game cards (72 Event + 5 Winter)
_BASE_CARDS = {}

for card_id in range(1, 73):
    tokens = _BASE_FACTION_TOKENS[card_id].split()
    faction_order, np_symbols = _parse_faction_line(tokens)
    _BASE_CARDS[card_id] = CardData(
        card_id=card_id,
        title=CARD_NAMES_BASE[card_id],
        faction_order=faction_order,
        np_symbols=np_symbols,
        is_capability=(card_id in CAPABILITY_CARDS),
        is_winter=False,
    )

# Winter cards (base game) — §2.4
# Winter cards have no faction order or NP symbols
for i in range(1, 6):
    wid = f"W{i}"
    _BASE_CARDS[wid] = CardData(
        card_id=wid,
        title=WINTER_CARD,
        faction_order=(),
        np_symbols={},
        is_capability=False,
        is_winter=True,
    )


# Ariovistus deck cards
# The Ariovistus deck = base cards NOT replaced + A-prefix replacement cards.
# CARD_NAMES_ARIOVISTUS integer keys (SECOND_EDITION_CARDS: 11, 30, 39, 44, 54)
# are for TEXT LOOKUP only — they indicate cards whose text differs in
# Ariovistus. They are NOT additional deck entries (the same card number
# stays in the deck; its metadata may differ between scenarios).
#
# For the Ariovistus deck:
# - A-prefix keys in CARD_NAMES_ARIOVISTUS are replacement cards that go
#   INTO the deck, replacing the base card with the same number suffix.
# - Base cards that are NOT replaced also appear in the Ariovistus deck
#   with their base metadata (unless their text differs, in which case
#   we use the Ariovistus faction tokens if available).

# Determine which base card numbers are replaced by A-prefix cards
_REPLACED_BY_A_PREFIX = set()
for key in CARD_NAMES_ARIOVISTUS:
    if isinstance(key, str) and key.startswith("A"):
        try:
            num = int(key[1:])
            _REPLACED_BY_A_PREFIX.add(num)
        except ValueError:
            pass

# Build Ariovistus-specific card entries (A-prefix cards and text-changed cards)
_ARIOVISTUS_SPECIFIC_CARDS = {}

for card_id, token_str in _ARIOVISTUS_FACTION_TOKENS.items():
    tokens = token_str.split()

    # Detect trailing "C" as Arverni carnyx trigger (A2.3.9), not an NP symbol.
    # The carnyx trigger is a card-level symbol at top right of Ariovistus cards.
    # It appears as the last token "C" when it follows the final faction's NP
    # symbol (or directly after the final faction abbreviation).
    carnyx = False
    if tokens and tokens[-1] == "C":
        # Only treat trailing "C" as carnyx trigger for A-prefix cards.
        # For integer text-change cards, "C" in the middle of the string
        # is an NP symbol (e.g., card 30: "Ar C Ae Be L Ro").
        if isinstance(card_id, str) and card_id.startswith("A"):
            carnyx = True
            tokens = tokens[:-1]  # Strip the carnyx trigger before parsing

    faction_order, np_symbols = _parse_faction_line(tokens)

    if isinstance(card_id, str) and card_id.startswith("A"):
        # A-prefix replacement card
        title = CARD_NAMES_ARIOVISTUS[card_id]
        is_cap = (card_id in CAPABILITY_CARDS_ARIOVISTUS)
    elif isinstance(card_id, int) and card_id in SECOND_EDITION_CARDS:
        # 2nd Edition text-change card — same card_id, different text/metadata
        title = CARD_NAMES_BASE[card_id]
        # Check both capability dicts
        is_cap = (card_id in CAPABILITY_CARDS)
    else:
        continue

    _ARIOVISTUS_SPECIFIC_CARDS[card_id] = CardData(
        card_id=card_id,
        title=title,
        faction_order=faction_order,
        np_symbols=np_symbols,
        is_capability=is_cap,
        is_winter=False,
        has_carnyx_trigger=carnyx,
    )


# Full Ariovistus deck: base cards not replaced + A-prefix replacements +
# text-changed cards (keyed by their original int id for deck purposes)
_ARIOVISTUS_DECK_CARDS = {}

# Start with base cards that are NOT replaced
for card_id in range(1, 73):
    if card_id not in _REPLACED_BY_A_PREFIX:
        if card_id in _ARIOVISTUS_SPECIFIC_CARDS:
            # This base card has text changes in Ariovistus
            _ARIOVISTUS_DECK_CARDS[card_id] = _ARIOVISTUS_SPECIFIC_CARDS[card_id]
        else:
            # Unchanged base card in Ariovistus deck
            _ARIOVISTUS_DECK_CARDS[card_id] = _BASE_CARDS[card_id]

# Add A-prefix replacement cards
for card_id, card in _ARIOVISTUS_SPECIFIC_CARDS.items():
    if isinstance(card_id, str) and card_id.startswith("A"):
        _ARIOVISTUS_DECK_CARDS[card_id] = card

# Winter cards (Ariovistus uses same Winter cards)
for i in range(1, 6):
    wid = f"W{i}"
    _ARIOVISTUS_DECK_CARDS[wid] = _BASE_CARDS[wid]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_card(card_id, scenario=None):
    """Look up card metadata by card_id.

    Args:
        card_id: int (base cards), str "A##" (Ariovistus cards),
                 str "W#" (Winter cards)
        scenario: if provided, returns scenario-appropriate metadata
                  (e.g. Ariovistus text changes for cards like 30, 39)

    Returns:
        CardData instance, or raises KeyError if not found.
    """
    if scenario is not None and scenario in ARIOVISTUS_SCENARIOS:
        if card_id in _ARIOVISTUS_DECK_CARDS:
            return _ARIOVISTUS_DECK_CARDS[card_id]
        # Fall back to Ariovistus-specific cards (e.g. text-change int keys)
        if card_id in _ARIOVISTUS_SPECIFIC_CARDS:
            return _ARIOVISTUS_SPECIFIC_CARDS[card_id]
    # Base game lookup
    if card_id in _BASE_CARDS:
        return _BASE_CARDS[card_id]
    # Try Ariovistus cards directly (for A-prefix lookups without scenario)
    if card_id in _ARIOVISTUS_SPECIFIC_CARDS:
        return _ARIOVISTUS_SPECIFIC_CARDS[card_id]
    raise KeyError(f"Unknown card_id: {card_id!r}")


def get_faction_order(card_id, scenario=None):
    """Return the faction initiative order for a card.

    Returns tuple of faction constants.
    """
    return get_card(card_id, scenario).faction_order


def is_capability_card(card_id, scenario=None):
    """Check if a card is a Capability card.

    For Ariovistus scenarios, checks both base and Ariovistus capability sets.
    """
    if scenario is not None and scenario in ARIOVISTUS_SCENARIOS:
        return (card_id in CAPABILITY_CARDS or
                card_id in CAPABILITY_CARDS_ARIOVISTUS)
    return card_id in CAPABILITY_CARDS


def get_base_event_card_ids():
    """Return sorted list of base game event card IDs (1-72)."""
    return list(range(1, 73))


def get_ariovistus_event_card_ids():
    """Return list of Ariovistus deck event card IDs.

    Includes: base cards not replaced by A-prefix + A-prefix replacement cards.
    Excludes: Winter cards, integer text-lookup-only keys from
    CARD_NAMES_ARIOVISTUS that are not separate deck entries.
    """
    ids = []
    for card_id in _ARIOVISTUS_DECK_CARDS:
        if isinstance(card_id, str) and card_id.startswith("W"):
            continue  # Skip Winter cards
        ids.append(card_id)
    return ids


def get_winter_card_ids():
    """Return list of Winter card IDs."""
    return [f"W{i}" for i in range(1, 6)]


def get_all_base_cards():
    """Return dict of all base game cards (event + winter)."""
    return dict(_BASE_CARDS)


def get_all_ariovistus_cards():
    """Return dict of all Ariovistus deck cards (event + winter)."""
    return dict(_ARIOVISTUS_DECK_CARDS)


def get_np_symbols(card_id, scenario=None):
    """Return NP instruction symbols dict for a card.

    Returns dict mapping faction -> NP_SYMBOL_* constant.
    """
    return get_card(card_id, scenario).np_symbols


def card_has_carnyx_trigger(card_id, scenario=None):
    """Check if a card has the Arverni carnyx trigger symbol — A2.3.9.

    The carnyx symbol appears on 24 Ariovistus Event cards and cues an
    Arverni At War check before the normal Sequence of Play.

    Returns True only for Ariovistus-specific cards with the trigger.
    """
    return get_card(card_id, scenario).has_carnyx_trigger
