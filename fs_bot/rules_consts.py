"""
rules_consts.py — Canonical Labels for Falling Sky Bot Engine

Every string label for factions, pieces, markers, leaders, regions, tribes,
space IDs, commands, special abilities, and any other game concept used
anywhere in the codebase MUST come from this file.

If a label doesn't exist here, it is wrong.

Source hierarchy (read-only, never modify):
  1. This file (rules_consts.py)
  2. Reference Documents/Card Reference & Ariovistus/A Card Reference
  3. Reference Documents/ (everything else)

Organization: constants grouped by category, each traced to a specific
Reference Document section.
"""

# ============================================================================
# FACTIONS (§1.5, A1.5)
# ============================================================================

ROMANS = "Romans"           # Roman Republic (red) — §1.5
ARVERNI = "Arverni"         # Arverni Confederation (green) — §1.5
AEDUI = "Aedui"             # Aedui Confederation (blue) — §1.5
BELGAE = "Belgae"           # Belgic Tribes (yellow-orange) — §1.5
GERMANS = "Germans"         # Germanic Tribes (black) — §1.5

FACTIONS = (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS)

# Collective groupings — §1.5
GALLIC_FACTIONS = (ARVERNI, AEDUI, BELGAE)

# Faction colors — §1.5
FACTION_COLORS = {
    ROMANS: "red",
    ARVERNI: "green",
    AEDUI: "blue",
    BELGAE: "yellow",
    GERMANS: "black",
}

# Faction abbreviations on cards — Card Reference header, A Card Reference
FACTION_ABBREV = {
    ROMANS: "Ro",
    ARVERNI: "Ar",
    AEDUI: "Ae",
    BELGAE: "Be",
    GERMANS: "Ge",
}


# ============================================================================
# SCENARIOS (Setup pp.26-29, A2.1 pp.13-17)
# ============================================================================

# Base game scenarios — Setup
SCENARIO_PAX_GALLICA = "Pax Gallica?"
SCENARIO_RECONQUEST = "Reconquest of Gaul"
SCENARIO_GREAT_REVOLT = "The Great Revolt"

# Ariovistus scenarios — A2.1
SCENARIO_ARIOVISTUS = "Ariovistus"
SCENARIO_GALLIC_WAR = "The Gallic War"

BASE_SCENARIOS = (
    SCENARIO_PAX_GALLICA,
    SCENARIO_RECONQUEST,
    SCENARIO_GREAT_REVOLT,
)

ARIOVISTUS_SCENARIOS = (
    SCENARIO_ARIOVISTUS,
    SCENARIO_GALLIC_WAR,
)

ALL_SCENARIOS = BASE_SCENARIOS + ARIOVISTUS_SCENARIOS


# ============================================================================
# LEADERS (§1.4, §1.4.3, A1.4)
# ============================================================================

# Named leaders (symbol end up) — §1.4.3
CAESAR = "Caesar"                       # Roman — §1.4.3
VERCINGETORIX = "Vercingetorix"         # Arverni — §1.4.3
AMBIORIX = "Ambiorix"                   # Belgae — §1.4.3
ARIOVISTUS_LEADER = "Ariovistus"        # Germans (Ariovistus) — A1.4
DIVICIACUS = "Diviciacus"              # Aedui (Ariovistus) — A1.4
BODUOGNATUS = "Boduognatus"             # Belgae in Ariovistus (same piece) — A1.4

# Successor form (symbol end down) — §1.4.3, §6.6
SUCCESSOR = "Successor"

# Leader-to-faction mapping — §1.4.3, A1.4
LEADER_FACTION = {
    CAESAR: ROMANS,
    VERCINGETORIX: ARVERNI,
    AMBIORIX: BELGAE,
    ARIOVISTUS_LEADER: GERMANS,
    DIVICIACUS: AEDUI,
    BODUOGNATUS: BELGAE,
}

# Base game leaders — §1.4.3
BASE_LEADERS = (CAESAR, VERCINGETORIX, AMBIORIX)

# Ariovistus leaders — A1.4
ARIOVISTUS_LEADERS = (CAESAR, BODUOGNATUS, ARIOVISTUS_LEADER, DIVICIACUS)


# ============================================================================
# PIECE TYPES (§1.4, A1.4)
# ============================================================================

LEADER = "Leader"               # Tall cylinder — §1.4
LEGION = "Legion"               # Cube (Roman only) — §1.4
AUXILIA = "Auxilia"             # Hexagonal cylinder (Roman) — §1.4
WARBAND = "Warband"             # Hexagonal cylinder (Gallic/Germanic) — §1.4
FORT = "Fort"                   # Square (Roman only) — §1.4
ALLY = "Ally"                   # Disc (Allied Tribe) — §1.4
CITADEL = "Citadel"             # Diamond (Gallic only) — §1.4
SETTLEMENT = "Settlement"       # Germanic piece (Ariovistus only) — A1.4

PIECE_TYPES = (LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL,
               SETTLEMENT)

# Mobile pieces (can March/Retreat/relocate) — §1.4, §3.2.2, §3.3.2
MOBILE_PIECES = (LEADER, LEGION, AUXILIA, WARBAND)

# Static pieces (cannot March) — §1.4
STATIC_PIECES = (FORT, ALLY, CITADEL, SETTLEMENT)

# Pieces that can be Hidden/Revealed — §1.4.3
FLIPPABLE_PIECES = (AUXILIA, WARBAND)

# "Hard target" pieces that roll to absorb losses — §3.2.4 LOSSES
HARD_TARGET_PIECES = (LEADER, LEGION, FORT, CITADEL)

# Pieces per faction — §1.4, A1.4
ROMAN_PIECE_TYPES = (LEADER, LEGION, AUXILIA, FORT, ALLY)
ARVERNI_PIECE_TYPES = (LEADER, WARBAND, ALLY, CITADEL)
AEDUI_PIECE_TYPES_BASE = (WARBAND, ALLY, CITADEL)
AEDUI_PIECE_TYPES_ARIOVISTUS = (LEADER, WARBAND, ALLY, CITADEL)
BELGAE_PIECE_TYPES = (LEADER, WARBAND, ALLY, CITADEL)
GERMAN_PIECE_TYPES_BASE = (WARBAND, ALLY)
GERMAN_PIECE_TYPES_ARIOVISTUS = (LEADER, WARBAND, ALLY, SETTLEMENT)


# ============================================================================
# PIECE STATES (§1.4.3, §4.2.2)
# ============================================================================

HIDDEN = "Hidden"               # Symbol end down — §1.4.3
REVEALED = "Revealed"           # Symbol end up — §1.4.3
SCOUTED = "Scouted"             # Revealed + Scouted marker — §4.2.2


# ============================================================================
# REGION GROUPS (§1.3, §1.3.1)
# ============================================================================

BELGICA = "Belgica"             # Northern Gaul, 3 regions — §1.3.1
GERMANIA = "Germania"           # East of Gaul, 2 regions — §1.3
CELTICA = "Celtica"             # Central Gaul, 9 regions — §1.3
BRITANNIA_GROUP = "Britannia"   # Island, 1 region — §1.3.4
PROVINCIA_GROUP = "Provincia"   # Southeast, 1 region — §1.3
CISALPINA_GROUP = "Cisalpina"   # Border area — §1.4.2, A1.3.2

REGION_GROUPS = (BELGICA, GERMANIA, CELTICA, BRITANNIA_GROUP,
                 PROVINCIA_GROUP, CISALPINA_GROUP)


# ============================================================================
# REGIONS (Map Transcription)
# ============================================================================

# Belgica regions (3) — Map Transcription
MORINI = "Morini"
NERVII = "Nervii"
ATREBATES = "Atrebates"

# Germania regions (2) — Map Transcription
SUGAMBRI = "Sugambri"
UBII = "Ubii"

# Celtica regions (9) — Map Transcription
TREVERI = "Treveri"
CARNUTES = "Carnutes"
MANDUBII = "Mandubii"
VENETI = "Veneti"
PICTONES = "Pictones"
BITURIGES = "Bituriges"
AEDUI_REGION = "Aedui"
SEQUANI = "Sequani"
ARVERNI_REGION = "Arverni"

# Britannia (1) — Map Transcription
BRITANNIA = "Britannia"

# Provincia (1) — Map Transcription
PROVINCIA = "Provincia"

# Cisalpina (1) — Map Transcription, A1.3.2
CISALPINA = "Cisalpina"

ALL_REGIONS = (
    # Belgica
    MORINI, NERVII, ATREBATES,
    # Germania
    SUGAMBRI, UBII,
    # Celtica
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    # Other
    BRITANNIA, PROVINCIA, CISALPINA,
)

BELGICA_REGIONS = (MORINI, NERVII, ATREBATES)
GERMANIA_REGIONS = (SUGAMBRI, UBII)
CELTICA_REGIONS = (TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
                   BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION)

# Control Values per region — Map Transcription, §1.3.1, §7.2
REGION_CONTROL_VALUES = {
    MORINI: 2,
    NERVII: 2,
    ATREBATES: 3,
    SUGAMBRI: 1,       # Design note 7.2: CV excludes Suebi
    UBII: 1,           # Design note 7.2: CV excludes Suebi
    TREVERI: 1,
    CARNUTES: 2,
    MANDUBII: 3,
    VENETI: 2,
    PICTONES: 2,
    BITURIGES: 1,
    AEDUI_REGION: 1,
    SEQUANI: 2,
    ARVERNI_REGION: 3,
    BRITANNIA: 1,
    PROVINCIA: 1,
    CISALPINA: 0,       # 0 in base; 1 in Ariovistus (Nori) — A1.3.2
}

# Cisalpina CV in Ariovistus — A1.3.2
CISALPINA_CV_ARIOVISTUS = 1

# Region-to-group mapping — Map Transcription
REGION_TO_GROUP = {
    MORINI: BELGICA,
    NERVII: BELGICA,
    ATREBATES: BELGICA,
    SUGAMBRI: GERMANIA,
    UBII: GERMANIA,
    TREVERI: CELTICA,
    CARNUTES: CELTICA,
    MANDUBII: CELTICA,
    VENETI: CELTICA,
    PICTONES: CELTICA,
    BITURIGES: CELTICA,
    AEDUI_REGION: CELTICA,
    SEQUANI: CELTICA,
    ARVERNI_REGION: CELTICA,
    BRITANNIA: BRITANNIA_GROUP,
    PROVINCIA: PROVINCIA_GROUP,
    CISALPINA: CISALPINA_GROUP,
}


# ============================================================================
# TRIBES (Map Transcription, §1.3.2)
# 30 total in base game; in Ariovistus: -Catuvellauni +Nori = 30
# ============================================================================

# Belgica tribes — Map Transcription
TRIBE_MENAPII = "Menapii"
TRIBE_MORINI = "Morini"
TRIBE_EBURONES = "Eburones"
TRIBE_NERVII = "Nervii"
TRIBE_BELLOVACI = "Bellovaci"
TRIBE_ATREBATES = "Atrebates"
TRIBE_REMI = "Remi"

# Germania tribes — Map Transcription
TRIBE_SUEBI_NORTH = "Suebi (North)"       # germanic-only — §1.4.2
TRIBE_SUGAMBRI = "Sugambri"
TRIBE_SUEBI_SOUTH = "Suebi (South)"       # germanic-only — §1.4.2
TRIBE_UBII = "Ubii"

# Celtica tribes — Map Transcription
TRIBE_TREVERI = "Treveri"
TRIBE_CARNUTES = "Carnutes"
TRIBE_AULERCI = "Aulerci"
TRIBE_MANDUBII = "Mandubii"
TRIBE_SENONES = "Senones"
TRIBE_LINGONES = "Lingones"
TRIBE_VENETI = "Veneti"
TRIBE_NAMNETES = "Namnetes"
TRIBE_PICTONES = "Pictones"
TRIBE_SANTONES = "Santones"
TRIBE_BITURIGES = "Bituriges"
TRIBE_AEDUI = "Aedui"                      # aedui-only — §1.4.2
TRIBE_SEQUANI = "Sequani"
TRIBE_HELVETII = "Helvetii"
TRIBE_ARVERNI = "Arverni"                   # arverni-only — §1.4.2
TRIBE_CADURCI = "Cadurci"
TRIBE_VOLCAE = "Volcae"

# Britannia tribe (base game only) — Map Transcription
TRIBE_CATUVELLAUNI = "Catuvellauni"

# Provincia tribe — Map Transcription
TRIBE_HELVII = "Helvii"

# Ariovistus-only tribe (replaces Catuvellauni) — A1.3.2
TRIBE_NORI = "Nori"

# All base game tribes (30) — Map Transcription, §1.3.2
BASE_TRIBES = (
    TRIBE_MENAPII, TRIBE_MORINI,
    TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI,
    TRIBE_SUEBI_SOUTH, TRIBE_UBII,
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
)

# Ariovistus tribes (30) — A1.3.2: -Catuvellauni +Nori
ARIOVISTUS_TRIBES = (
    TRIBE_MENAPII, TRIBE_MORINI,
    TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI,
    TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI,
    TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
    TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_BITURIGES,
    TRIBE_AEDUI,
    TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_NORI,
    TRIBE_HELVII,
)

# Tribe-to-region mapping — Map Transcription
TRIBE_TO_REGION = {
    TRIBE_MENAPII: MORINI,
    TRIBE_MORINI: MORINI,
    TRIBE_EBURONES: NERVII,
    TRIBE_NERVII: NERVII,
    TRIBE_BELLOVACI: ATREBATES,
    TRIBE_ATREBATES: ATREBATES,
    TRIBE_REMI: ATREBATES,
    TRIBE_SUEBI_NORTH: SUGAMBRI,
    TRIBE_SUGAMBRI: SUGAMBRI,
    TRIBE_SUEBI_SOUTH: UBII,
    TRIBE_UBII: UBII,
    TRIBE_TREVERI: TREVERI,
    TRIBE_CARNUTES: CARNUTES,
    TRIBE_AULERCI: CARNUTES,
    TRIBE_MANDUBII: MANDUBII,
    TRIBE_SENONES: MANDUBII,
    TRIBE_LINGONES: MANDUBII,
    TRIBE_VENETI: VENETI,
    TRIBE_NAMNETES: VENETI,
    TRIBE_PICTONES: PICTONES,
    TRIBE_SANTONES: PICTONES,
    TRIBE_BITURIGES: BITURIGES,
    TRIBE_AEDUI: AEDUI_REGION,
    TRIBE_SEQUANI: SEQUANI,
    TRIBE_HELVETII: SEQUANI,
    TRIBE_ARVERNI: ARVERNI_REGION,
    TRIBE_CADURCI: ARVERNI_REGION,
    TRIBE_VOLCAE: ARVERNI_REGION,
    TRIBE_CATUVELLAUNI: BRITANNIA,
    TRIBE_HELVII: PROVINCIA,
    TRIBE_NORI: CISALPINA,           # Ariovistus only — A1.3.2
}

# Suebi tribes (excluded from Belgic CV) — Map Transcription design note 7.2
SUEBI_TRIBES = (TRIBE_SUEBI_NORTH, TRIBE_SUEBI_SOUTH)

# Stacking restrictions — §1.4.2, Map Transcription
# These tribes can only hold Allies/Citadels of the specified faction
TRIBE_FACTION_RESTRICTION = {
    TRIBE_AEDUI: AEDUI,             # aedui-only — §1.4.2
    TRIBE_ARVERNI: ARVERNI,         # arverni-only — §1.4.2
    TRIBE_SUEBI_NORTH: GERMANS,     # germanic-only — §1.4.2
    TRIBE_SUEBI_SOUTH: GERMANS,     # germanic-only — §1.4.2
}


# ============================================================================
# CITIES (Map Transcription, §1.3.3)
# Gray diamonds — tribes that have Cities where Citadels can be placed
# ============================================================================

CITY_CENABUM = "Cenabum"           # Carnutes tribe — Map Transcription
CITY_ALESIA = "Alesia"             # Mandubii tribe — Map Transcription
CITY_AVARICUM = "Avaricum"         # Bituriges tribe — Map Transcription
CITY_BIBRACTE = "Bibracte"         # Aedui tribe — Map Transcription
CITY_VESONTIO = "Vesontio"         # Sequani tribe — Map Transcription
CITY_GERGOVIA = "Gergovia"         # Arverni tribe — Map Transcription

ALL_CITIES = (CITY_CENABUM, CITY_ALESIA, CITY_AVARICUM,
              CITY_BIBRACTE, CITY_VESONTIO, CITY_GERGOVIA)

# City-to-tribe mapping — Map Transcription
CITY_TO_TRIBE = {
    CITY_CENABUM: TRIBE_CARNUTES,
    CITY_ALESIA: TRIBE_MANDUBII,
    CITY_AVARICUM: TRIBE_BITURIGES,
    CITY_BIBRACTE: TRIBE_AEDUI,
    CITY_VESONTIO: TRIBE_SEQUANI,
    CITY_GERGOVIA: TRIBE_ARVERNI,
}

# Tribe-to-city mapping (reverse) — Map Transcription
TRIBE_TO_CITY = {v: k for k, v in CITY_TO_TRIBE.items()}


# ============================================================================
# TRIBE STATUSES (§1.7, §3.2.3, §6.6)
# ============================================================================

SUBDUED = "Subdued"                     # Empty tribe circle — §1.7
ALLIED = "Allied"                       # Has an Ally disc — §1.4
DISPERSED = "Dispersed"                 # Dispersed marker — §1.7, §3.2.3
DISPERSED_GATHERING = "Dispersed-Gathering"  # Flip side — §6.6, §3.2.3


# ============================================================================
# CONTROL LEVELS (§1.6)
# ============================================================================

ROMAN_CONTROL = "Roman Control"
ARVERNI_CONTROL = "Arverni Control"
AEDUI_CONTROL = "Aedui Control"
BELGIC_CONTROL = "Belgic Control"
GERMANIC_CONTROL = "Germanic Control"
NO_CONTROL = "No Control"

FACTION_CONTROL = {
    ROMANS: ROMAN_CONTROL,
    ARVERNI: ARVERNI_CONTROL,
    AEDUI: AEDUI_CONTROL,
    BELGAE: BELGIC_CONTROL,
    GERMANS: GERMANIC_CONTROL,
}


# ============================================================================
# SENATE TRACK (§6.5, §6.5.1)
# ============================================================================

UPROAR = "Uproar"                  # Top — adverse to Romans — §6.5
INTRIGUE = "Intrigue"              # Middle — §6.5
ADULATION = "Adulation"            # Bottom — best for Romans — §6.5

# Firm state (flipped marker) — §6.5.1
FIRM = "Firm"

# Senate positions in order from top (worst for Romans) to bottom (best)
SENATE_POSITIONS = (UPROAR, INTRIGUE, ADULATION)

# Shift directions — §6.5.1
SENATE_UP = "up"                    # Toward Uproar — §6.5.1
SENATE_DOWN = "down"                # Toward Adulation — §6.5.1

# Auxilia placed by Senate Phase per position — §6.5.3
SENATE_AUXILIA = {
    UPROAR: 3,
    INTRIGUE: 4,
    ADULATION: 5,
}

# Ariovistus: max Legions placed per Senate Phase — A6.5.2
ARIOVISTUS_SENATE_MAX_LEGIONS = 2


# ============================================================================
# LEGIONS TRACK (§1.4.1, §6.5)
# ============================================================================

LEGIONS_TRACK = "Legions Track"
FALLEN_LEGIONS = "Fallen Legions"

# Legions track row positions — §6.5
LEGIONS_ROW_BOTTOM = "Bottom"       # Below Adulation
LEGIONS_ROW_MIDDLE = "Middle"       # At Adulation level
LEGIONS_ROW_TOP = "Top"             # At Intrigue level

LEGIONS_ROWS = (LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP)
LEGIONS_PER_ROW = 4                 # §1.4.1


# ============================================================================
# COMMANDS (§3.0, §3.2-3.4, A3.0, A3.4)
# ============================================================================

# Roman commands — §3.2
CMD_RECRUIT = "Recruit"
CMD_MARCH = "March"
CMD_SEIZE = "Seize"
CMD_BATTLE = "Battle"

# Gallic commands — §3.3
CMD_RALLY = "Rally"
# CMD_MARCH shared with Roman
CMD_RAID = "Raid"
# CMD_BATTLE shared with Roman

ROMAN_COMMANDS = (CMD_RECRUIT, CMD_MARCH, CMD_SEIZE, CMD_BATTLE)
GALLIC_COMMANDS = (CMD_RALLY, CMD_MARCH, CMD_RAID, CMD_BATTLE)
GERMAN_COMMANDS = (CMD_RALLY, CMD_MARCH, CMD_RAID, CMD_BATTLE)

ALL_COMMANDS = (CMD_RECRUIT, CMD_RALLY, CMD_MARCH, CMD_SEIZE,
                CMD_RAID, CMD_BATTLE)

# Limited Command — §2.3.5
LIMITED_COMMAND = "Limited Command"


# ============================================================================
# SPECIAL ABILITIES (§4.0, A4.0, A4.6)
# ============================================================================

# Roman SAs — §4.2
SA_BUILD = "Build"
SA_SCOUT = "Scout"
SA_BESIEGE = "Besiege"

# Arverni SAs (base game) — §4.3
SA_ENTREAT = "Entreat"
SA_DEVASTATE = "Devastate"
SA_AMBUSH = "Ambush"

# Aedui SAs — §4.4
SA_TRADE = "Trade"
SA_SUBORN = "Suborn"
# SA_AMBUSH shared

# Belgae SAs — §4.5
SA_ENLIST = "Enlist"
SA_RAMPAGE = "Rampage"
# SA_AMBUSH shared

# Germanic SAs (Ariovistus) — A4.6
SA_SETTLE = "Settle"
SA_INTIMIDATE = "Intimidate"
# SA_AMBUSH shared

ROMAN_SPECIAL_ABILITIES = (SA_BUILD, SA_SCOUT, SA_BESIEGE)
ARVERNI_SPECIAL_ABILITIES_BASE = (SA_ENTREAT, SA_DEVASTATE, SA_AMBUSH)
ARVERNI_SPECIAL_ABILITIES_ARIOVISTUS = (SA_AMBUSH,)    # A4.3
AEDUI_SPECIAL_ABILITIES = (SA_TRADE, SA_SUBORN, SA_AMBUSH)
BELGAE_SPECIAL_ABILITIES = (SA_ENLIST, SA_RAMPAGE, SA_AMBUSH)
GERMAN_SPECIAL_ABILITIES_BASE = (SA_AMBUSH,)           # §3.4.4, §4.1
GERMAN_SPECIAL_ABILITIES_ARIOVISTUS = (SA_SETTLE, SA_INTIMIDATE, SA_AMBUSH)

ALL_SPECIAL_ABILITIES = (SA_BUILD, SA_SCOUT, SA_BESIEGE, SA_ENTREAT,
                         SA_DEVASTATE, SA_AMBUSH, SA_TRADE, SA_SUBORN,
                         SA_ENLIST, SA_RAMPAGE, SA_SETTLE, SA_INTIMIDATE)


# ============================================================================
# MARKER TYPES (§1.6, §1.7, §2.3.8, §3.2.3, §4.2.2, §4.3.2, §5.3,
#               Card Reference cards 4/5/71, A1.3.4, A2.3.9, A4.6.2,
#               A5.1.4 cards A64/A66)
# ============================================================================

MARKER_CONTROL = "Control"                  # §1.6
MARKER_NO_CONTROL = "No Control"            # §1.6
MARKER_DEVASTATED = "Devastated"            # §4.3.2
MARKER_DISPERSED = "Dispersed"              # §1.7, §3.2.3
MARKER_DISPERSED_GATHERING = "Dispersed-Gathering"  # §6.6
MARKER_SCOUTED = "Scouted"                  # §4.2.2
MARKER_FROST = "Frost"                      # §2.3.8
MARKER_WINTER = "Winter"                    # §2.4
MARKER_OVERFLOW = "Overflow"                # §1.3.6
MARKER_CAPABILITY = "Capability"            # §5.3
MARKER_CIRCUMVALLATION = "Circumvallation"  # Card 4 — Card Reference
MARKER_COLONY = "Colony"                    # Card 71 — Card Reference
MARKER_GALLIA_TOGATA = "Gallia Togata"      # Card 5 — Card Reference
MARKER_RAZED = "Razed"                      # Card 23 (Sacking) — §6.6

# Ariovistus-only markers — A1.3.4, A2.3.9, A4.6.2, A5.1.4
MARKER_AT_WAR = "At War"                    # A2.3.9, A6.2
MARKER_AT_PEACE = "At Peace"                # A2.3.9, A6.2
MARKER_INTIMIDATED = "Intimidated"          # A4.6.2
MARKER_BRITANNIA_NOT_IN_PLAY = "Britannia (Not in play)"  # A1.3.4
MARKER_ARVERNI_RALLY = "Rally"              # A1.3.1 — Arverni Home markers
MARKER_ARVERNI_TARGET = "Target"            # A6.2 — Arverni target marker
MARKER_ABATIS = "Abatis"                    # Card A64 — A5.1.4
MARKER_WINTER_UPRISING = "Winter Uprising!" # Card A66 — A5.1.4

# Max Dispersed markers on map — §3.2.3
MAX_DISPERSED_MARKERS = 4


# ============================================================================
# VICTORY (§7.0, §7.2, §7.3, A7.0, A7.2, A7.3)
# ============================================================================

# Victory markers — §1.9, A1.9
VICTORY_MARKER_ROMAN = "Subdued+Dispersed+Allies"          # §1.9
VICTORY_MARKER_ARVERNI = "Off-Map Legions"                  # §1.9
VICTORY_MARKER_BELGAE = "Control+Allies"                    # §1.9
VICTORY_MARKER_AEDUI = "Other Most Allies"                  # §1.9
VICTORY_MARKER_GERMAN = "Control Germania+Settlements"      # A1.9

# Victory thresholds — §7.2, A7.2
ROMAN_VICTORY_THRESHOLD = 15           # Exceeds 15 — §7.2
ARVERNI_LEGIONS_THRESHOLD = 6          # Off-map Legions exceed 6 — §7.2
ARVERNI_ALLIES_THRESHOLD = 8           # Allies + Citadels exceed 8 — §7.2
BELGAE_VICTORY_THRESHOLD = 15          # CV + Allies + Citadels exceed 15 — §7.2
GERMAN_VICTORY_THRESHOLD = 6           # Germania + Settlements exceed 6 — A7.2

# Tie-breaking priority (base) — §7.1
TIEBREAK_ORDER_BASE = (ROMANS, ARVERNI, AEDUI)

# Tie-breaking priority (Ariovistus) — A7.1
TIEBREAK_ORDER_ARIOVISTUS = (ROMANS, GERMANS, AEDUI)


# ============================================================================
# WINTER PHASES (§6.0, A6.0)
# ============================================================================

PHASE_VICTORY = "Victory Phase"             # §6.1
PHASE_GERMANS = "Germans Phase"             # §6.2 (base game)
PHASE_ARVERNI = "Arverni Phase"             # A6.2 (Ariovistus)
PHASE_QUARTERS = "Quarters Phase"           # §6.3
PHASE_HARVEST = "Harvest Phase"             # §6.4
PHASE_SENATE = "Senate Phase"               # §6.5
PHASE_SPRING = "Spring Phase"               # §6.6

BASE_WINTER_PHASES = (PHASE_VICTORY, PHASE_GERMANS, PHASE_QUARTERS,
                      PHASE_HARVEST, PHASE_SENATE, PHASE_SPRING)

ARIOVISTUS_WINTER_PHASES = (PHASE_VICTORY, PHASE_QUARTERS,
                            PHASE_HARVEST, PHASE_SENATE, PHASE_SPRING)


# ============================================================================
# SEQUENCE OF PLAY (§2.3)
# ============================================================================

ELIGIBLE = "Eligible"               # §2.3.1
INELIGIBLE = "Ineligible"           # §2.3.1

# 1st/2nd eligible — §2.3.2
FIRST_ELIGIBLE = "1st Eligible"
SECOND_ELIGIBLE = "2nd Eligible"

# Pass resources — §2.3.3
PASS_RESOURCES_GALLIC = 1          # +1 for Gallic Factions — §2.3.3
PASS_RESOURCES_ROMAN = 2           # +2 for Romans — §2.3.3
PASS_RESOURCES_GERMAN_ARIOVISTUS = 1  # +1 for Germans — A2.3.3

# 2nd Eligible options based on 1st Eligible action — §2.3.4
FIRST_DID_COMMAND_ONLY = "Command Only"
FIRST_DID_COMMAND_AND_SA = "Command & Special Ability"
FIRST_DID_EVENT = "Event"


# ============================================================================
# NON-PLAYER EVENT INSTRUCTION SYMBOLS (§8.2.1, A8.2.1)
# ============================================================================

NP_SYMBOL_CARNYX = "Carnyx"        # Celtic trumpet — §8.2.1
NP_SYMBOL_LAURELS = "Laurels"      # §8.2.1
NP_SYMBOL_SWORDS = "Swords"        # §8.2.1

# Abbreviations on cards — Card Reference header
NP_ABBREV_CARNYX = "C"
NP_ABBREV_LAURELS = "L"
NP_ABBREV_SWORDS = "S"


# ============================================================================
# EVENT TYPES (§5.2)
# ============================================================================

EVENT_UNSHADED = "Unshaded"         # 1st choice, often pro-Roman — §5.2
EVENT_SHADED = "Shaded"             # 2nd choice, often anti-Roman — §5.2


# ============================================================================
# RESOURCE AND PIECE CAPS (§1.8, available_forces.txt,
#                          available_forces_ariovistus.txt)
# ============================================================================

# Maximum Resources per faction — §1.8
MAX_RESOURCES = 45

# ----- Base game piece caps — available_forces.txt -----

CAPS_BASE = {
    ROMANS: {
        LEADER: 1,
        AUXILIA: 20,
        FORT: 6,
        LEGION: 12,
        ALLY: 6,
    },
    ARVERNI: {
        LEADER: 1,       # Vercingetorix / Successor
        WARBAND: 35,
        ALLY: 10,
        CITADEL: 3,
    },
    BELGAE: {
        LEADER: 1,       # Ambiorix / Successor
        WARBAND: 25,
        ALLY: 10,
        CITADEL: 1,
    },
    AEDUI: {
        LEADER: 0,       # No leader in base game
        WARBAND: 20,
        ALLY: 6,
        CITADEL: 2,
    },
    GERMANS: {
        LEADER: 0,       # No leader in base game
        WARBAND: 15,
        ALLY: 6,
    },
}

# ----- Ariovistus piece caps — available_forces_ariovistus.txt -----

CAPS_ARIOVISTUS = {
    ROMANS: {
        LEADER: 1,       # Caesar / Successor (unchanged)
        AUXILIA: 20,
        FORT: 6,
        LEGION: 12,
        ALLY: 6,
    },
    ARVERNI: {
        LEADER: 0,       # Vercingetorix removed from play — A1.4
        WARBAND: 35,
        ALLY: 10,
        CITADEL: 3,
    },
    BELGAE: {
        LEADER: 1,       # Boduognatus / Successor — A1.4
        WARBAND: 25,
        ALLY: 10,
        CITADEL: 1,
    },
    AEDUI: {
        LEADER: 1,       # Diviciacus (no Successor) — A1.4
        WARBAND: 20,
        ALLY: 6,
        CITADEL: 2,
    },
    GERMANS: {
        LEADER: 1,       # Ariovistus / Successor — A1.4
        WARBAND: 30,     # 15 base + 15 additional — A1.4
        ALLY: 6,
        SETTLEMENT: 6,   # New piece type — A1.4
    },
}


# ============================================================================
# HOME REGIONS (§1.3.1, §3.2.1, §3.3.1, §3.4.1, A1.3.1)
# ============================================================================

# Roman home / Recruit symbol — §3.2.1
ROMAN_HOME_REGIONS = (PROVINCIA,)

# Arverni home / Rally symbol (base game) — §3.3.1
ARVERNI_HOME_REGIONS_BASE = (ARVERNI_REGION,)

# Belgae home / Rally symbol — §3.3.1
BELGAE_HOME_REGIONS = BELGICA_REGIONS  # All Belgica regions

# Germanic home (base game) — §3.4.1
GERMAN_HOME_REGIONS_BASE = GERMANIA_REGIONS

# Aedui home / Rally symbol — §3.3.1
AEDUI_HOME_REGIONS = (AEDUI_REGION,)

# Arverni home (Ariovistus) — A1.3.1
ARVERNI_HOME_REGIONS_ARIOVISTUS = (VENETI, CARNUTES, PICTONES, ARVERNI_REGION)

# Germanic home (Ariovistus): Germania + Settlement regions — A1.3.1, A1.4
# Settlement regions are dynamic; only static homes listed here
GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC = GERMANIA_REGIONS


# ============================================================================
# ADJACENCY DATA (Map Transcription)
# (rhenus) = halts March — §1.3.5
# (coastal) = Britannia sea connection — §1.3.4
# ============================================================================

# Adjacency type flags
ADJ_NORMAL = "normal"
ADJ_RHENUS = "rhenus"           # §1.3.5
ADJ_COASTAL = "coastal"         # §1.3.4

# Complete adjacency list — Map Transcription
# Each entry: (region_a, region_b, adjacency_type)
ADJACENCIES = (
    # Morini adjacencies
    (MORINI, NERVII, ADJ_NORMAL),
    (MORINI, ATREBATES, ADJ_NORMAL),
    (MORINI, SUGAMBRI, ADJ_RHENUS),
    (MORINI, BRITANNIA, ADJ_COASTAL),
    # Nervii adjacencies
    (NERVII, ATREBATES, ADJ_NORMAL),
    (NERVII, TREVERI, ADJ_NORMAL),
    (NERVII, SUGAMBRI, ADJ_RHENUS),
    # Atrebates adjacencies
    (ATREBATES, TREVERI, ADJ_NORMAL),
    (ATREBATES, CARNUTES, ADJ_NORMAL),
    (ATREBATES, MANDUBII, ADJ_NORMAL),
    (ATREBATES, BRITANNIA, ADJ_COASTAL),
    (ATREBATES, VENETI, ADJ_NORMAL),
    # Sugambri adjacencies
    (SUGAMBRI, UBII, ADJ_NORMAL),
    (SUGAMBRI, TREVERI, ADJ_RHENUS),
    # Ubii adjacencies
    (UBII, TREVERI, ADJ_RHENUS),
    (UBII, SEQUANI, ADJ_RHENUS),
    (UBII, CISALPINA, ADJ_NORMAL),
    # Treveri adjacencies
    (TREVERI, MANDUBII, ADJ_NORMAL),
    (TREVERI, SEQUANI, ADJ_NORMAL),
    # Carnutes adjacencies
    (CARNUTES, MANDUBII, ADJ_NORMAL),
    (CARNUTES, PICTONES, ADJ_NORMAL),
    (CARNUTES, BITURIGES, ADJ_NORMAL),
    (CARNUTES, VENETI, ADJ_NORMAL),
    # Mandubii adjacencies
    (MANDUBII, AEDUI_REGION, ADJ_NORMAL),
    (MANDUBII, SEQUANI, ADJ_NORMAL),
    (MANDUBII, BITURIGES, ADJ_NORMAL),
    # Veneti adjacencies
    (VENETI, PICTONES, ADJ_NORMAL),
    (VENETI, BRITANNIA, ADJ_COASTAL),
    # Pictones adjacencies
    (PICTONES, BITURIGES, ADJ_NORMAL),
    (PICTONES, ARVERNI_REGION, ADJ_NORMAL),
    # Bituriges adjacencies
    (BITURIGES, AEDUI_REGION, ADJ_NORMAL),
    (BITURIGES, ARVERNI_REGION, ADJ_NORMAL),
    # Aedui adjacencies
    (AEDUI_REGION, SEQUANI, ADJ_NORMAL),
    (AEDUI_REGION, ARVERNI_REGION, ADJ_NORMAL),
    (AEDUI_REGION, PROVINCIA, ADJ_NORMAL),
    # Sequani adjacencies
    (SEQUANI, ARVERNI_REGION, ADJ_NORMAL),
    (SEQUANI, PROVINCIA, ADJ_NORMAL),
    (SEQUANI, CISALPINA, ADJ_NORMAL),
    # Arverni adjacencies
    (ARVERNI_REGION, PROVINCIA, ADJ_NORMAL),
    # Provincia adjacencies
    (PROVINCIA, CISALPINA, ADJ_NORMAL),
)

# Non-playable areas — §1.4.2
AQUITANIA = "Aquitania"            # Non-playable area — §1.4.2


# ============================================================================
# CARD NAMES — BASE GAME (Card Reference)
# 72 Event cards + 5 Winter cards
# ============================================================================

CARD_NAMES_BASE = {
    1: "Cicero",
    2: "Legiones XIIII et XV",
    3: "Pompey",
    4: "Circumvallation",
    5: "Gallia Togata",
    6: "Marcus Antonius",
    7: "Alaudae",
    8: "Baggage Trains",
    9: "Mons Cevenna",
    10: "Ballistae",
    11: "Numidians",
    12: "Titus Labienus",
    13: "Balearic Slingers",
    14: "Clodius Pulcher",
    15: "Legio X",
    16: "Ambacti",
    17: "Germanic Chieftains",
    18: "Rhenus Bridge",
    19: "Lucterius",
    20: "Optimates",
    21: "The Province",
    22: "Hostages",
    23: "Sacking",
    24: "Sappers",
    25: "Aquitani",
    26: "Gobannitio",
    27: "Massed Gallic Archers",
    28: "Oppida",
    29: "Suebi Mobilize",
    30: "Vercingetorix's Elite",
    31: "Cotuatus & Conconnetodumnus",
    32: "Forced Marches",
    33: "Lost Eagle",
    34: "Acco",
    35: "Gallic Shouts",
    36: "Morasses",
    37: "Boii",
    38: "Diviciacus",
    39: "River Commerce",
    40: "Alpine Tribes",
    41: "Avaricum",
    42: "Roman Wine",
    43: "Convictolitavis",
    44: "Dumnorix Loyalists",
    45: "Litaviccus",
    46: "Celtic Rites",
    47: "Chieftains' Council",
    48: "Druids",
    49: "Drought",
    50: "Shifting Loyalties",
    51: "Surus",
    52: "Assembly of Gaul",
    53: "Consuetudine",
    54: "Joined Ranks",
    55: "Commius",
    56: "Flight of Ambiorix",
    57: "Land of Mist and Mystery",
    58: "Aduatuca",
    59: "Germanic Horse",
    60: "Indutiomarus",
    61: "Catuvolcus",
    62: "War Fleet",
    63: "Winter Campaign",
    64: "Correus",
    65: "German Allegiances",
    66: "Migration",
    67: "Arduenna",
    68: "Remi Influence",
    69: "Segni & Condrusi",
    70: "Camulogenus",
    71: "Colony",
    72: "Impetuosity",
}

# Winter cards — §2.4, Setup (Deck Preparation)
WINTER_CARD_COUNT = 5
WINTER_CARD = "Winter"


# ============================================================================
# CARD NAMES — ARIOVISTUS (A Card Reference)
# Replacement cards for Ariovistus scenarios (A## prefix)
# ============================================================================

CARD_NAMES_ARIOVISTUS = {
    "A5": "Gallia Togata",
    11: "Numidians",
    "A17": "Publius Licinius Crassus",
    "A18": "Rhenus Bridge",
    "A19": "Gaius Valerius Procillus",
    "A20": "Morbihan",
    "A21": "Vosegus",
    "A22": "Dread",
    "A23": "Parley",
    "A24": "Seduni Uprising!",
    "A25": "Ariovistus's Wife",
    "A26": "Divico",
    "A27": "Sotiates Uprising!",
    "A28": "Admagetobriga",
    "A29": "Harudes",
    "A30": "Orgetorix",
    "A31": "German Phalanx",
    "A32": "Veneti Uprising!",
    "A33": "Wailing Women",
    "A34": "Divination",
    "A35": "Nasua & Cimberius",
    "A36": "Usipetes & Tencteri",
    "A37": "All Gaul Gathers",
    "A38": "Vergobret",
    "A40": "Alpine Tribes",
    "A43": "Dumnorix",
    "A45": "Savage Dictates",
    "A51": "Siege of Bibrax",
    "A53": "Frumentum",
    "A56": "Galba",
    "A57": "Sabis",
    "A58": "Aduatuci",
    "A60": "Iccius & Andecomborius",
    "A63": "Winter Campaign",
    "A64": "Abatis",
    "A65": "Kinship",
    "A66": "Winter Uprising!",
    "A67": "Arduenna",
    "A69": "Bellovaci",
    "A70": "Nervii",
}

# Optional replacement card — A1.4, A2.1
CARD_O38 = "O38"
CARD_O38_NAME = "Diviciacus"

# 2nd Edition replacement cards — A1.2.1, A5.0
SECOND_EDITION_CARDS = (11, 30, 39, 44, 54)

# Deck sizes — Setup, A Scenario
BASE_EVENT_CARD_COUNT = 72
ARIOVISTUS_EVENT_CARD_COUNT = 72


# ============================================================================
# CAPABILITY CARDS (§5.3, Card Reference, A Card Reference)
# Cards marked CAPABILITY whose effects persist.
# Keyed by card number; values are the card title.
# ============================================================================

# Base game capabilities — Card Reference, §5.3
# Only cards with the literal "CAPABILITY" marker in the Card Reference.
CAPABILITY_CARDS = {
    8: "Baggage Trains",
    10: "Ballistae",
    12: "Titus Labienus",
    13: "Balearic Slingers",
    15: "Legio X",
    25: "Aquitani",
    30: "Vercingetorix's Elite",
    38: "Diviciacus",
    39: "River Commerce",
    43: "Convictolitavis",
    55: "Commius",
    59: "Germanic Horse",
    63: "Winter Campaign",
}

# Ariovistus-exclusive capability cards — A Card Reference
# Only new/replacement capabilities with an A## card number.
# Base game capability cards (from CAPABILITY_CARDS) that appear in the
# Ariovistus deck are also capabilities — code should check both dicts.
CAPABILITY_CARDS_ARIOVISTUS = {
    "A22": "Dread",
    "A31": "German Phalanx",
    "A33": "Wailing Women",
    "A38": "Vergobret",
    "A63": "Winter Campaign",
    "A70": "Nervii",
}


# ============================================================================
# BATTLE PROCEDURE (§3.2.4, §3.3.4, §3.4.4,
#                   battle_procedure_flowchart.txt)
# ============================================================================

BATTLE_STEP_TARGET = "Step 1 Target"
BATTLE_STEP_DECLARE_RETREAT = "Step 2 Declare Retreat"
BATTLE_STEP_ATTACK = "Step 3 Attack"
BATTLE_STEP_COUNTERATTACK = "Step 4 Counterattack"
BATTLE_STEP_REVEAL = "Step 5 Reveal"
BATTLE_STEP_RETREAT = "Step 6 Retreat"

# Loss die roll threshold — §3.2.4 LOSSES
LOSS_ROLL_THRESHOLD = 3            # Remove on 1-3, survive on 4-6

# Caesar defending vs Ambush: 4-6 retains roll ability — §4.3.3
CAESAR_AMBUSH_ROLL_THRESHOLD = 4   # 4, 5, or 6

# Caesar defending vs Belgic Ambush: 5-6 — §4.5.3
CAESAR_BELGIC_AMBUSH_ROLL_THRESHOLD = 5  # 5 or 6

# Diviciacus: removed only on roll of 1 — A1.4, A3.2.4
DIVICIACUS_LOSS_ROLL_THRESHOLD = 1

# Harassment: 1 loss per 3 Hidden Warbands (rounded down) — §3.2.2
HARASSMENT_WARBANDS_PER_LOSS = 3


# ============================================================================
# COMMAND COSTS (§3.1, §3.2, §3.3, §3.4, A3.4)
# ============================================================================

# Roman costs — §3.2
RECRUIT_COST = 2                    # Per region, 0 if Supply Line — §3.2.1
ROMAN_MARCH_COST = 2               # Per origin, x2 if Devastated — §3.2.2
SEIZE_COST = 0                     # Free — §3.2.3
ROMAN_BATTLE_COST = 2              # Per region, x2 if Devastated — §3.2.4

# Gallic costs — §3.3
RALLY_COST = 1                     # Per region — §3.3.1
BELGAE_RALLY_OUTSIDE_BELGICA = 2   # Belgae outside Belgica — §3.3.1
ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX = 2  # §3.3.1
GALLIC_MARCH_COST = 1              # Per origin, x2 if Devastated — §3.3.2
RAID_COST = 0                      # Free — §3.3.3
GALLIC_BATTLE_COST = 1             # Per region, x2 if Devastated — §3.3.4

# Germanic costs (base game) — §3.4: all 0
GERMAN_COMMAND_COST_BASE = 0

# Germanic costs (Ariovistus) — A3.4.1
GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT = 2   # A3.4.1
GERMAN_RALLY_COST_AT_SETTLEMENT = 1                     # A3.4.1
GERMAN_RALLY_COST_IN_GERMANIA = 0                        # A3.4.1

# Settle costs — A4.6.1
SETTLE_COST = 2                     # Per region, x2 if Devastated — A4.6.1

# Build costs — §4.2.1
BUILD_COST_PER_FORT = 2            # §4.2.1
BUILD_COST_PER_ALLY = 2            # §4.2.1

# Entreat cost — §4.3.1
ENTREAT_COST = 1                   # Per region — §4.3.1

# Suborn costs — §4.4.2
SUBORN_COST_PER_ALLY = 2           # §4.4.2
SUBORN_COST_PER_PIECE = 1          # Per Warband or Auxilia — §4.4.2
SUBORN_MAX_PIECES = 3              # Max total pieces in one region — §4.4.2
SUBORN_MAX_ALLIES = 1              # Max Allies per Suborn — §4.4.2

# Convictolitavis capability expands Suborn — §5.3, Card 43
CONVICTOLITAVIS_SUBORN_MAX_PIECES = 6   # 3 per region x 2 regions
CONVICTOLITAVIS_SUBORN_MAX_ALLIES = 2   # Max 2 Allies total
CONVICTOLITAVIS_SUBORN_MAX_REGIONS = 2  # 2 regions


# ============================================================================
# HARVEST / INCOME (§6.4, A6.4)
# ============================================================================

AEDUI_RIVER_TOLLS = 4              # §6.4.3


# ============================================================================
# SENATE SHIFT THRESHOLDS (§6.5.1)
# ============================================================================

SENATE_SHIFT_LOW_THRESHOLD = 10    # Below 10: toward Uproar — §6.5.1
SENATE_SHIFT_HIGH_THRESHOLD = 12   # Above 12: toward Adulation — §6.5.1


# ============================================================================
# QUARTERS PHASE COSTS (§6.3.3)
# ============================================================================

QUARTERS_COST_WITH_ALLY = 1         # Per piece if Roman Ally — §6.3.3
QUARTERS_COST_WITHOUT_ALLY = 2      # Per piece if no Roman Ally — §6.3.3
QUARTERS_DEVASTATED_MULTIPLIER = 2  # Doubles cost — §6.3.3
QUARTERS_FREE_PIECES_PER_ALLY = 1   # §6.3.3
QUARTERS_FREE_PIECES_PER_FORT = 1   # §6.3.3


# ============================================================================
# GALLIC WAR INTERLUDE (A2.1 — The Gallic War scenario)
# ============================================================================

INTERLUDE = "Interlude"                 # A2.1

# Force reduction fractions during Interlude — A2.1
INTERLUDE_GERMAN_WARBANDS_REMOVED = 15  # Remove any 15 Warbands
INTERLUDE_FRACTION_QUARTER = 0.25       # 1/4 removal (Germans)
INTERLUDE_FRACTION_HALF = 0.50          # 1/2 removal (others)

# Britannia expedition — A2.1
BRITANNIA_EXPEDITION_LEGIONS_TO_TRACK = 3
BRITANNIA_EXPEDITION_MIN_LEGIONS_TO_BRITANNIA = 3
BRITANNIA_EXPEDITION_MIN_AUXILIA_TO_BRITANNIA = 1


# ============================================================================
# ENLIST LIMITS — ARIOVISTUS (A4.5.1)
# ============================================================================

ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS = 4  # Max Warbands+Allies — A4.5.1


# ============================================================================
# MISCELLANEOUS GAME CONSTANTS
# ============================================================================

# Total tribe count — §1.3.2, A1.3.2
TOTAL_TRIBES_BASE = 30
TOTAL_TRIBES_ARIOVISTUS = 30

# Colony adds a tribe — Card 71, §7.2
COLONY_EXTRA_TRIBE = 1

# Total regions — §1.3.1, Map Transcription
TOTAL_REGIONS = 17

# Permanent Fort in Provincia — §1.4.2
PROVINCIA_PERMANENT_FORT = True

# Maximum 1 Fort per region — §1.4.2
MAX_FORTS_PER_REGION = 1

# Maximum 1 Settlement per region — A1.4.2
MAX_SETTLEMENTS_PER_REGION = 1

# Arverni Rally: Warbands = Allies + Citadels + Leader + 1 — §3.3.1
ARVERNI_RALLY_EXTRA_WARBAND = 1

# Germans Phase: Quarters relocation die roll — §6.3.1
GERMAN_QUARTERS_SUGAMBRI_THRESHOLD = 3  # 1-3 Sugambri, 4-6 Ubii

# Desertion die roll threshold — §6.3.2
DESERTION_ROLL_THRESHOLD = 3       # Remove Warband on 1-3

# Die — standard d6
DIE_SIDES = 6
DIE_MIN = 1
DIE_MAX = 6
