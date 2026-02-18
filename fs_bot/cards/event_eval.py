"""
event_eval.py — Per-card event evaluation for bot flowchart decisions.

Provides:
1. Per-card boolean flag tables describing what each card's event does
   (static properties built from Card Reference text, not inferred).
2. Per-card is_effective() checks that evaluate game state to determine
   if executing the event would produce any change (§8.1.1).
3. A unified should_skip_event() function for bot flowchart decision
   nodes (R4, V2b, A3, B3b, G3b).

§8.1.1: Non-players decline the following Events:
  - Ineffective Events — those that would have no effect or would merely
    Reveal own pieces. Adding or removing a Capability IS an effect.
  - Capabilities during the last year (next Winter is final).
  - "No [Faction]" Events per bot instruction tables.

Source: Card Reference, A Card Reference, §8.1.1, §8.2, bot flowcharts
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS, FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Senate
    SENATE_POSITIONS,
    # Regions / groups
    PROVINCIA, CISALPINA,
    ALL_REGIONS,
    BELGICA_REGIONS, GERMANIA_REGIONS, CELTICA_REGIONS,
    # Tribes
    TRIBE_CARNUTES, TRIBE_REMI, TRIBE_MANDUBII,
    TRIBE_AEDUI, TRIBE_ARVERNI, TRIBE_SEQUANI,
    TRIBE_HELVETII, TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_MORINI, TRIBE_MENAPII, TRIBE_HELVII,
    TRIBE_PICTONES, TRIBE_SANTONES, TRIBE_VOLCAE, TRIBE_CADURCI,
    TRIBE_ATREBATES, TRIBE_NERVII, TRIBE_EBURONES,
    TRIBE_TREVERI, TRIBE_BITURIGES, TRIBE_NORI,
    TRIBE_TO_REGION,
    # Cities
    CITY_AVARICUM, CITY_CENABUM, CITY_ALESIA,
    CITY_BIBRACTE, CITY_GERGOVIA,
    CITY_TO_TRIBE,
    # Markers
    MARKER_DEVASTATED, MARKER_GALLIA_TOGATA,
    MARKER_CIRCUMVALLATION, MARKER_COLONY,
    # Capabilities
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    # Max resources
    MAX_RESOURCES,
    # Control
    ROMAN_CONTROL, NO_CONTROL,
)
from fs_bot.board.pieces import (
    get_available, count_pieces, find_leader,
    _count_on_legions_track,
)
from fs_bot.board.control import is_controlled_by, get_controlled_regions
from fs_bot.cards.card_data import is_capability_card
from fs_bot.cards.bot_instructions import (
    get_bot_instruction, NO_EVENT, CONDITIONAL,
)


# ---------------------------------------------------------------------------
# Event effect flag constants
# ---------------------------------------------------------------------------
# Each card side (unshaded/shaded) gets a frozenset of these flag strings.
# Flags describe what the event text does, built from Card Reference.

# Piece placement / removal
PLACES_LEGIONS = "places_legions"
REMOVES_LEGIONS = "removes_legions"
PLACES_AUXILIA = "places_auxilia"
REMOVES_AUXILIA = "removes_auxilia"
PLACES_WARBANDS = "places_warbands"
REMOVES_WARBANDS = "removes_warbands"
PLACES_ALLIES = "places_allies"
REMOVES_ALLIES = "removes_allies"
PLACES_CITADELS = "places_citadels"
REMOVES_CITADELS = "removes_citadels"
PLACES_FORTS = "places_forts"
REMOVES_FORTS = "removes_forts"
PLACES_SETTLEMENTS = "places_settlements"
REMOVES_SETTLEMENTS = "removes_settlements"
PLACES_LEADER = "places_leader"
REMOVES_LEADER = "removes_leader"
MOVES_PIECES = "moves_pieces"

# Senate
SHIFTS_SENATE = "shifts_senate"

# Resources
ADDS_RESOURCES = "adds_resources"
REMOVES_RESOURCES = "removes_resources"

# Free actions
FREE_COMMAND = "free_command"
FREE_BATTLE = "free_battle"
FREE_MARCH = "free_march"
FREE_RALLY = "free_rally"
FREE_RAID = "free_raid"
FREE_SCOUT = "free_scout"
FREE_SEIZE = "free_seize"
FREE_SA = "free_special_ability"

# State changes
AFFECTS_ELIGIBILITY = "affects_eligibility"
PLACES_MARKERS = "places_markers"
REMOVES_MARKERS = "removes_markers"
IS_CAPABILITY = "is_capability"
TRIGGERS_GERMANS_PHASE = "triggers_germans_phase"
TRIGGERS_ARVERNI_PHASE = "triggers_arverni_phase"

# All flag constants for validation
_ALL_FLAGS = frozenset({
    PLACES_LEGIONS, REMOVES_LEGIONS, PLACES_AUXILIA, REMOVES_AUXILIA,
    PLACES_WARBANDS, REMOVES_WARBANDS, PLACES_ALLIES, REMOVES_ALLIES,
    PLACES_CITADELS, REMOVES_CITADELS, PLACES_FORTS, REMOVES_FORTS,
    PLACES_SETTLEMENTS, REMOVES_SETTLEMENTS, PLACES_LEADER, REMOVES_LEADER,
    MOVES_PIECES, SHIFTS_SENATE, ADDS_RESOURCES, REMOVES_RESOURCES,
    FREE_COMMAND, FREE_BATTLE, FREE_MARCH, FREE_RALLY, FREE_RAID,
    FREE_SCOUT, FREE_SEIZE, FREE_SA,
    AFFECTS_ELIGIBILITY, PLACES_MARKERS, REMOVES_MARKERS, IS_CAPABILITY,
    TRIGGERS_GERMANS_PHASE, TRIGGERS_ARVERNI_PHASE,
})


# ---------------------------------------------------------------------------
# Per-card flag tables — Base game cards 1-72
# Format: {card_id: (unshaded_flags, shaded_flags)}
# Built directly from Card Reference text.
# For cards with a single effect (no unshaded/shaded split), both sides
# get the same flags.
# ---------------------------------------------------------------------------

_BASE_FLAGS = {
    # Card 1: Cicero — Shift Senate 1 box either direction
    1: (frozenset({SHIFTS_SENATE}),
        frozenset({SHIFTS_SENATE})),

    # Card 2: Legiones XIIII et XV
    # Un: shift Senate 1 up, place 2 Legions in Provincia
    # Sh: Free Battle against Romans; first Loss removes Legion
    2: (frozenset({SHIFTS_SENATE, PLACES_LEGIONS}),
        frozenset({FREE_BATTLE, REMOVES_LEGIONS})),

    # Card 3: Pompey
    # Un: If Adulation place 1 Legion; otherwise shift Senate 1 down
    # Sh: If Legions track ≤4: remove 2 Legions to track
    3: (frozenset({PLACES_LEGIONS, SHIFTS_SENATE}),
        frozenset({REMOVES_LEGIONS})),

    # Card 4: Circumvallation — Capability
    # Un: free March + place marker
    # Sh: Capability effect on battles
    4: (frozenset({FREE_MARCH, PLACES_MARKERS, IS_CAPABILITY}),
        frozenset({IS_CAPABILITY})),

    # Card 5: Gallia Togata
    # Un: Place marker + 3 Auxilia in Cisalpina
    # Sh: Remove 1 Legion to track + 2 Auxilia
    5: (frozenset({PLACES_MARKERS, PLACES_AUXILIA}),
        frozenset({REMOVES_LEGIONS, REMOVES_AUXILIA})),

    # Card 6: Marcus Antonius
    # Un: free Scout, then free Battle with 2x Auxilia Losses
    # Sh: Move up to 4 Auxilia to Provincia; Romans Ineligible
    6: (frozenset({FREE_SCOUT, FREE_BATTLE}),
        frozenset({MOVES_PIECES, AFFECTS_ELIGIBILITY})),

    # Card 7: Alaudae
    # Un: Place 1 Legion + 1 Auxilia in Roman Controlled Region
    # Sh: If track ≤7: remove 1 Legion to track, 1 Auxilia to Available
    7: (frozenset({PLACES_LEGIONS, PLACES_AUXILIA}),
        frozenset({REMOVES_LEGIONS, REMOVES_AUXILIA})),

    # Card 8: Baggage Trains — Capability
    # Un: March costs 0 Resources
    # Sh: Raids use 3 Warbands per Region, steal despite Citadels/Forts
    8: (frozenset({IS_CAPABILITY}),
        frozenset({IS_CAPABILITY})),

    # Card 9: Mons Cevenna
    # Both: free March + free Command + free SA
    9: (frozenset({FREE_MARCH, FREE_COMMAND, FREE_SA}),
        frozenset({FREE_MARCH, FREE_COMMAND, FREE_SA})),

    # Card 10: Ballistae — Capability
    # Un: Besiege improvement + Battle roll improvement
    # Sh: Place near Gallic Faction; may remove Fort/Citadel after Ambush
    10: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 11: Numidians
    # Un: Place 3 Auxilia within 1 of Leader; free Battle 2x Auxilia Losses
    # Sh: Remove any 4 Auxilia
    11: (frozenset({PLACES_AUXILIA, FREE_BATTLE}),
         frozenset({REMOVES_AUXILIA})),

    # Card 12: Titus Labienus — Capability
    # Un: Roman SAs may select Regions regardless of Leader location
    # Sh: Build and Scout max 1 Region
    12: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 13: Balearic Slingers — Capability
    # Un: 1 Region per Battle; Auxilia inflict ½ Loss each on attacker
    # Sh: Recruit only where Supply Line, paying 2 per Region
    13: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 14: Clodius Pulcher
    # Un: Shift Senate 1 down or flip to Firm
    # Sh: Roman Leader to Provincia; Romans Ineligible
    14: (frozenset({SHIFTS_SENATE}),
         frozenset({MOVES_PIECES, AFFECTS_ELIGIBILITY})),

    # Card 15: Legio X — Capability
    # Un: In Battles with Leader+Legion, final Losses -1, inflict +2
    # Sh: Caesar doubles Loss from 1 Legion only
    15: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 16: Ambacti
    # Un: Place 4 Auxilia (or 6 with Caesar)
    # Sh: Roll die; remove 3 or that number of Auxilia
    16: (frozenset({PLACES_AUXILIA}),
         frozenset({REMOVES_AUXILIA})),

    # Card 17: Germanic Chieftains
    # Un: March up to 3 German groups, Ambush with Germans
    # Sh: Conduct Germans Phase as if Winter
    17: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({TRIGGERS_GERMANS_PHASE})),

    # Card 18: Rhenus Bridge
    # Un: Remove all Germans from 1 Germania Region
    # Sh: Romans -6 Resources, Ineligible
    18: (frozenset({REMOVES_WARBANDS}),
         frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY})),

    # Card 19: Lucterius
    # Un: Remove up to 6 Arverni Warbands OR place up to 5 Auxilia
    # Sh: If Successor Available, place as Vercingetorix
    19: (frozenset({REMOVES_WARBANDS, PLACES_AUXILIA}),
         frozenset({PLACES_LEADER})),

    # Card 20: Optimates — Capability (keep by Winter track)
    # Both: on 2nd+ Victory Phase, if Roman victory >12, remove Legions
    20: (frozenset({IS_CAPABILITY, REMOVES_LEGIONS}),
         frozenset({IS_CAPABILITY, REMOVES_LEGIONS})),

    # Card 21: The Province
    # Un: If only Roman pieces in Provincia: +5 Auxilia or +10 Resources
    # Sh: If Arverni Control Provincia: Senate shift; else Warbands + Raid
    21: (frozenset({PLACES_AUXILIA, ADDS_RESOURCES}),
         frozenset({SHIFTS_SENATE, PLACES_WARBANDS, FREE_RAID, FREE_BATTLE})),

    # Card 22: Hostages
    # Un: In Controlled Regions, replace up to 4 enemy Warbands/Auxilia
    # Sh: Place Gallic Ally + 1 Warband at 1-2 Subdued Tribes with Romans
    22: (frozenset({REMOVES_WARBANDS, REMOVES_AUXILIA, PLACES_WARBANDS, PLACES_AUXILIA}),
         frozenset({PLACES_ALLIES, PLACES_WARBANDS})),

    # Card 23: Sacking
    # Un: Place Razed marker on City at Roman Control (+8 Resources)
    # Sh: If Legion where Citadel: remove Legion, Romans Ineligible
    23: (frozenset({PLACES_MARKERS, ADDS_RESOURCES}),
         frozenset({REMOVES_LEGIONS, AFFECTS_ELIGIBILITY})),

    # Card 24: Sappers
    # Un: Gallic Faction with Citadel loses 10 Resources
    # Sh: Remove 2 Legions/Auxilia where Arverni Citadel
    24: (frozenset({REMOVES_RESOURCES}),
         frozenset({REMOVES_LEGIONS, REMOVES_AUXILIA})),

    # Card 25: Aquitani — Capability
    # Un: Free Battle in Pictones or Arverni Region, +3 Losses, 1 Ally first
    # Sh: Rally places 2 extra Warbands in Pictones/Arverni
    25: (frozenset({FREE_BATTLE, IS_CAPABILITY}),
         frozenset({PLACES_WARBANDS, IS_CAPABILITY})),

    # Card 26: Gobannitio
    # Un: Remove anything at Gergovia; place Roman/Aedui Ally or Citadel
    # Sh: Remove/place Allies in Arverni Region; free Rally
    26: (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS, REMOVES_AUXILIA,
                    PLACES_ALLIES, PLACES_CITADELS}),
         frozenset({REMOVES_ALLIES, PLACES_ALLIES, FREE_RALLY})),

    # Card 27: Massed Gallic Archers — Capability
    # Un: Arverni Battle inflicts 1 fewer Defender Loss
    # Sh: Battles with 6+ Arverni Warbands, other side absorbs 1 extra Loss
    27: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 28: Oppida — same effect both sides
    # Place Gallic Allies at Subdued Cities; replace Allies with Citadels
    28: (frozenset({PLACES_ALLIES, PLACES_CITADELS}),
         frozenset({PLACES_ALLIES, PLACES_CITADELS})),

    # Card 29: Suebi Mobilize
    # Un: Remove Dispersed from Suebi; place Germanic Ally at each
    # Sh: Germans Phase as if Winter, skip Rally
    29: (frozenset({REMOVES_MARKERS, PLACES_ALLIES}),
         frozenset({TRIGGERS_GERMANS_PHASE})),

    # Card 30: Vercingetorix's Elite — Capability
    # Un: Arverni Rally places Warbands up to Allies+Citadels
    # Sh: Arverni pick 2 Warbands as Legions in Battle
    30: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 31: Cotuatus & Conconnetodumnus
    # Un: Place 1 Legion in Provincia
    # Sh: Remove 3 Allies (1 Roman, 1 Aedui, 1 Roman/Aedui)
    31: (frozenset({PLACES_LEGIONS}),
         frozenset({REMOVES_ALLIES})),

    # Card 32: Forced Marches — both sides same effect
    # Relocate Warbands/Legions/Auxilia/Leader; pieces go Hidden
    32: (frozenset({MOVES_PIECES}),
         frozenset({MOVES_PIECES})),

    # Card 33: Lost Eagle
    # Un: Place 1 Fallen Legion into Region with non-Aedui Warband + Legion
    # Sh: Remove 1 Fallen Legion permanently; no Senate shift down
    33: (frozenset({PLACES_LEGIONS}),
         frozenset({REMOVES_LEGIONS})),

    # Card 34: Acco
    # Un: Free Rally/Recruit in 3 Regions as if with Control
    # Sh: Replace Allies+Citadels at Carnutes and Mandubii with Arverni
    34: (frozenset({FREE_RALLY}),
         frozenset({REMOVES_ALLIES, REMOVES_CITADELS,
                    PLACES_ALLIES, PLACES_CITADELS})),

    # Card 35: Gallic Shouts
    # Un: Look at next 2 cards; free Limited Command or become Eligible
    # Sh: Gallic Faction 1 Command + 1 Limited Command free, no Battles
    35: (frozenset({FREE_COMMAND}),
         frozenset({FREE_COMMAND})),

    # Card 36: Morasses
    # Un: Free Battle, no Retreat/Counterattack/Citadel; Attackers Hidden
    # Sh: Gallic Faction free Battles+Ambush, then free Marches
    36: (frozenset({FREE_BATTLE}),
         frozenset({FREE_BATTLE, FREE_MARCH})),

    # Card 37: Boii
    # Un: Place 2 Allies + 2 Warbands/Auxilia at/adjacent Aedui Control
    # Sh: Replace 1-2 Aedui Allies with Arverni at/adjacent Arverni Control
    37: (frozenset({PLACES_ALLIES, PLACES_WARBANDS, PLACES_AUXILIA}),
         frozenset({REMOVES_ALLIES, PLACES_ALLIES})),

    # Card 38: Diviciacus — Capability
    # Un: Aedui Warbands/Auxilia treated as each other
    # Sh: Romans and Aedui may not transfer Resources
    38: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 39: River Commerce — Capability
    # Un: Aedui Trade +2 per Ally/Citadel in Supply Lines
    # Sh: Trade max 1 Region
    39: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 40: Alpine Tribes
    # Un: Place pieces in Regions adj to Cisalpina; +4 Resources
    # Sh: -5 Roman Resources per Region adj to Cisalpina not Roman Control
    40: (frozenset({PLACES_WARBANDS, PLACES_AUXILIA, PLACES_ALLIES,
                    ADDS_RESOURCES}),
         frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY})),

    # Card 41: Avaricum — same effect both sides
    # Place Allies, replace with Citadel, place Fort; gain Resources
    41: (frozenset({PLACES_ALLIES, PLACES_CITADELS, PLACES_FORTS,
                    ADDS_RESOURCES}),
         frozenset({PLACES_ALLIES, PLACES_CITADELS, PLACES_FORTS,
                    ADDS_RESOURCES})),

    # Card 42: Roman Wine
    # Un: Remove up to 4 Allies under Roman Control (or 2 adjacent)
    # Sh: Remove 1-3 Roman/Aedui Allies from Supply Lines
    42: (frozenset({REMOVES_ALLIES}),
         frozenset({REMOVES_ALLIES})),

    # Card 43: Convictolitavis — Capability
    # Un: Suborn max 2 Regions
    # Sh: Aedui Command costs doubled
    43: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 44: Dumnorix Loyalists
    # Un: Replace 4 Warbands with Auxilia/Aedui; free Scout
    # Sh: Replace 3 Auxilia/Aedui with Warbands; all free Raid
    44: (frozenset({REMOVES_WARBANDS, PLACES_AUXILIA, PLACES_WARBANDS,
                    FREE_SCOUT}),
         frozenset({REMOVES_AUXILIA, REMOVES_WARBANDS, PLACES_WARBANDS,
                    FREE_RAID})),

    # Card 45: Litaviccus
    # Un: Replace Arverni Warbands with Aedui; transfer 4 Resources
    # Sh: Free Battle against Romans with Aedui as own
    45: (frozenset({REMOVES_WARBANDS, PLACES_WARBANDS, ADDS_RESOURCES}),
         frozenset({FREE_BATTLE})),

    # Card 46: Celtic Rites
    # Un: Select Gallic Factions; each -3 Resources, Ineligible
    # Sh: Gallic Faction free Command; Stay Eligible
    46: (frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY}),
         frozenset({FREE_COMMAND, AFFECTS_ELIGIBILITY})),

    # Card 47: Chieftains' Council — same effect both sides
    # Factions look at next 2 cards; free Limited Command or become Eligible
    47: (frozenset({FREE_COMMAND}),
         frozenset({FREE_COMMAND})),

    # Card 48: Druids — same effect both sides
    # Select 1-3 Gallic Factions; each free Limited Command + optional SA
    48: (frozenset({FREE_COMMAND, FREE_SA}),
         frozenset({FREE_COMMAND, FREE_SA})),

    # Card 49: Drought — same effect both sides
    # Half Resources; place Devastated; remove 1 piece per Devastated Region
    49: (frozenset({REMOVES_RESOURCES, PLACES_MARKERS, REMOVES_WARBANDS,
                    REMOVES_AUXILIA, REMOVES_LEGIONS}),
         frozenset({REMOVES_RESOURCES, PLACES_MARKERS, REMOVES_WARBANDS,
                    REMOVES_AUXILIA, REMOVES_LEGIONS})),

    # Card 50: Shifting Loyalties — same effect both sides
    # Remove 1 Capability from play
    50: (frozenset({REMOVES_MARKERS}),
         frozenset({REMOVES_MARKERS})),

    # Card 51: Surus
    # Un: Replace 4 Warbands with Aedui near Treveri; Aedui free Command
    # Sh: Replace Aedui Warbands with any near Treveri; free German action
    51: (frozenset({REMOVES_WARBANDS, PLACES_WARBANDS, FREE_COMMAND}),
         frozenset({REMOVES_WARBANDS, PLACES_WARBANDS, FREE_MARCH,
                    FREE_RAID, FREE_BATTLE})),

    # Card 52: Assembly of Gaul
    # Un: If Carnutes Roman/Subdued/Dispersed: Gallic Resources -8 each
    # Sh: Faction Controlling Carnutes: Command + 2 free SAs
    52: (frozenset({REMOVES_RESOURCES}),
         frozenset({FREE_COMMAND, FREE_SA})),

    # Card 53: Consuetudine — same effect both sides
    # Germanic Warbands Hidden; Germans Phase skip March, all Ambush
    53: (frozenset({TRIGGERS_GERMANS_PHASE}),
         frozenset({TRIGGERS_GERMANS_PHASE})),

    # Card 54: Joined Ranks — same effect both sides
    # Free March up to 8 pieces; then free Battle
    54: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({FREE_MARCH, FREE_BATTLE})),

    # Card 55: Commius — Capability
    # Un: Belgica counts as Roman Controlled for Recruit; +1 Roman Ally
    # Sh: Belgic Rally costs 0; treats Region with Belgic pieces as Controlled
    55: (frozenset({IS_CAPABILITY, PLACES_ALLIES}),
         frozenset({IS_CAPABILITY})),

    # Card 56: Flight of Ambiorix
    # Un: If Ambiorix in Roman Controlled or Belgic victory <10: remove
    # Sh: If Ambiorix not on map: place within 1 of Germania
    56: (frozenset({REMOVES_LEADER}),
         frozenset({PLACES_LEADER})),

    # Card 57: Land of Mist and Mystery
    # Un: Free March into Britannia, free SA, +4 Resources
    # Sh: Remove Ally/Dispersed from Britannia; place Ally + 4 Warbands
    57: (frozenset({FREE_MARCH, FREE_SA, ADDS_RESOURCES}),
         frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS})),

    # Card 58: Aduatuci
    # Un: Remove 9 Belgic/Germanic Warbands from Region with Fort
    # Sh: March Germans to Fort; Ambush Romans
    58: (frozenset({REMOVES_WARBANDS}),
         frozenset({FREE_MARCH, FREE_BATTLE})),

    # Card 59: Germanic Horse — Capability
    # Un: Romans inflict 1 Loss per Auxilia per Battle
    # Sh: Each Battle double enemy Losses in 1 Region
    59: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 60: Indutiomarus
    # Un: Remove 6 Belgic Warbands/Allies from Treveri or adjacent
    # Sh: Remove Ally/marker from Treveri+Ubii; place Belgic+German pieces
    60: (frozenset({REMOVES_WARBANDS, REMOVES_ALLIES}),
         frozenset({REMOVES_ALLIES, REMOVES_MARKERS, PLACES_ALLIES,
                    PLACES_WARBANDS})),

    # Card 61: Catuvolcus
    # Un: Remove Allied Tribes + 5 Warbands in Nervii
    # Sh: Place Belgic Allies at Nervii/Eburones; +6 Resources
    61: (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS}),
         frozenset({PLACES_ALLIES, ADDS_RESOURCES})),

    # Card 62: War Fleet — same effect both sides
    # Move pieces among coastal Regions; free Command in 1
    62: (frozenset({MOVES_PIECES, FREE_COMMAND}),
         frozenset({MOVES_PIECES, FREE_COMMAND})),

    # Card 63: Winter Campaign — Capability
    # Un: Quarters costs only in Devastated Regions
    # Sh: May do 2 Commands/SAs after Harvest
    63: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 64: Correus
    # Un: Replace up to 8 Belgic Allies/Warbands in Atrebates
    # Sh: Remove 2 Allies from Atrebates; place 2 Belgic Allies, free Rally
    64: (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS, PLACES_AUXILIA}),
         frozenset({REMOVES_ALLIES, PLACES_ALLIES, FREE_RALLY})),

    # Card 65: German Allegiances
    # Un: March Germans from 2 Regions, Ambush
    # Sh: Where you Control, replace 5 Germanic Warbands + 1 Ally
    65: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({REMOVES_WARBANDS, REMOVES_ALLIES,
                    PLACES_WARBANDS, PLACES_ALLIES})),

    # Card 66: Migration
    # Un: Germanic Rally then March in up to 2 Regions
    # Sh: Move Warbands/Leader to No Control Region; place Ally
    66: (frozenset({FREE_RALLY, FREE_MARCH}),
         frozenset({MOVES_PIECES, PLACES_ALLIES})),

    # Card 67: Arduenna — same effect both sides
    # Free March into Nervii/Treveri, free Command except March, flip Hidden
    67: (frozenset({FREE_MARCH, FREE_COMMAND}),
         frozenset({FREE_MARCH, FREE_COMMAND})),

    # Card 68: Remi Influence
    # Un: If Remi Roman Ally/Subdued: replace 1-2 Allies with Roman
    # Sh: Gallic Faction with Remi: remove anything at Alesia/Cenabum;
    #     place Citadel + 4 Warbands
    68: (frozenset({REMOVES_ALLIES, PLACES_ALLIES}),
         frozenset({REMOVES_ALLIES, REMOVES_WARBANDS, REMOVES_AUXILIA,
                    REMOVES_LEGIONS, PLACES_CITADELS, PLACES_WARBANDS})),

    # Card 69: Segni & Condrusi — same effect both sides
    # Place 4 Germanic Warbands each in Nervii/Treveri; Germans Phase
    69: (frozenset({PLACES_WARBANDS, TRIGGERS_GERMANS_PHASE}),
         frozenset({PLACES_WARBANDS, TRIGGERS_GERMANS_PHASE})),

    # Card 70: Camulogenus
    # Un: Free March Legions+Auxilia to specific Regions; free Battle
    # Sh: Place Warbands; free Command + SA
    70: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({PLACES_WARBANDS, FREE_COMMAND, FREE_SA})),

    # Card 71: Colony — same effect both sides
    # Place marker, Colony marker, Ally; add +1 Control Value
    71: (frozenset({PLACES_MARKERS, PLACES_ALLIES}),
         frozenset({PLACES_MARKERS, PLACES_ALLIES})),

    # Card 72: Impetuosity
    # Un: Free March into 1 Region; Arverni/Belgae may free Battle
    # Sh: Free March 1 group Hidden Warbands; may free Battle alone
    72: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({FREE_MARCH, FREE_BATTLE})),
}


# ---------------------------------------------------------------------------
# Per-card flag tables — Ariovistus A-prefix cards
# ---------------------------------------------------------------------------

_ARIOVISTUS_FLAGS = {
    # A5: Gallia Togata (Ariovistus)
    # Un: Place marker + 3 Auxilia in Cisalpina; Recruit +1; March ignores Alps
    # Sh: Remove 1 Legion to track + 2 Auxilia
    "A5": (frozenset({PLACES_MARKERS, PLACES_AUXILIA}),
           frozenset({REMOVES_LEGIONS, REMOVES_AUXILIA})),

    # A17: Publius Licinius Crassus
    # Un: Free March Legions+Auxilia; Battle with 2x Auxilia Losses
    # Sh: Remove 4 Auxilia; Romans Ineligible
    "A17": (frozenset({FREE_MARCH, FREE_BATTLE}),
            frozenset({REMOVES_AUXILIA, AFFECTS_ELIGIBILITY})),

    # A18: Rhenus Bridge (Ariovistus)
    # Un: Remove all Germans from 1 Germania Region without Ariovistus
    # Sh: Romans -6 Resources, Ineligible
    "A18": (frozenset({REMOVES_WARBANDS}),
            frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY})),

    # A19: Gaius Valerius Procillus
    # Un: Replace up to 3 Allies with Roman Allies near Caesar
    # Sh: March Romans to adjacent Germans Region; Ineligible
    "A19": (frozenset({REMOVES_ALLIES, PLACES_ALLIES}),
            frozenset({MOVES_PIECES, AFFECTS_ELIGIBILITY})),

    # A20: Morbihan
    # Un: If Romans near Veneti: remove Arverni, free Seize
    # Sh: Arverni Warbands Ambush Romans
    "A20": (frozenset({REMOVES_WARBANDS, FREE_SEIZE}),
            frozenset({FREE_BATTLE})),

    # A21: Vosegus — same effect both sides
    # Free Battle near Sequani; no Retreat; optional 2nd Battle
    "A21": (frozenset({FREE_BATTLE}),
            frozenset({FREE_BATTLE})),

    # A22: Dread — Capability
    # Un: Intimidate markers have no effect on Romans
    # Sh: Intimidate may Reveal 1 extra Warband to remove 1 extra piece
    "A22": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY})),

    # A23: Parley
    # Move Caesar+forces or Ariovistus+forces to other's Region
    # Both Ineligible
    "A23": (frozenset({MOVES_PIECES, AFFECTS_ELIGIBILITY}),
            frozenset({MOVES_PIECES, AFFECTS_ELIGIBILITY})),

    # A24: Seduni Uprising!
    # Remove Allies; place Arverni Allies; place Warbands; Arverni Phase
    "A24": (frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE}),
            frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE})),

    # A25: Ariovistus's Wife
    # Un: Remove non-Leader German pieces from Cisalpina; -6 Resources
    # Sh: Remove Ally at Nori, place German Ally + 6 Warbands; +6 Resources
    "A25": (frozenset({REMOVES_WARBANDS, REMOVES_RESOURCES}),
            frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       ADDS_RESOURCES})),

    # A26: Divico
    # Un: Remove Arverni Ally at Helvetii + Warbands from Sequani/Aedui
    # Sh: Place up to 12 Arverni Warbands among Aedui/Sequani
    "A26": (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS}),
            frozenset({PLACES_WARBANDS})),

    # A27: Sotiates Uprising!
    # Remove Allies; place Arverni Allies + Warbands; Arverni Phase
    "A27": (frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE}),
            frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE})),

    # A28: Admagetobriga
    # Free Battle in/adjacent Sequani; treat other Faction Warbands as own
    "A28": (frozenset({FREE_BATTLE}),
            frozenset({FREE_BATTLE})),

    # A29: Harudes
    # Un: Place up to 2 Allies + 5 Warbands/3 Auxilia among Settlement Regions
    # Sh: Place 4 German Warbands + 1 Settlement; free Raid
    "A29": (frozenset({PLACES_ALLIES, PLACES_WARBANDS, PLACES_AUXILIA}),
            frozenset({PLACES_WARBANDS, PLACES_SETTLEMENTS, FREE_RAID})),

    # A30: Orgetorix
    # Un: Remove all Arverni from 1 Region near Sequani
    # Sh: Remove Allies/Citadels in Aedui/Sequani; place 9 Arverni pieces
    "A30": (frozenset({REMOVES_WARBANDS, REMOVES_ALLIES}),
            frozenset({REMOVES_ALLIES, REMOVES_CITADELS,
                       PLACES_WARBANDS, PLACES_ALLIES})),

    # A31: German Phalanx — Capability
    # Un: Event benefits in Battle cancelled; Ariovistus no double Losses
    # Sh: Event harms cancelled; named Leaders don't double Losses
    "A31": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY})),

    # A32: Veneti Uprising!
    # Remove Allies; place Arverni Allies + Warbands; Arverni Phase
    "A32": (frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE}),
            frozenset({REMOVES_ALLIES, PLACES_ALLIES, PLACES_WARBANDS,
                       TRIGGERS_ARVERNI_PHASE})),

    # A33: Wailing Women — Capability
    # Un: Germans never Retreat; if no Ariovistus, remove outnumbered
    # Sh: Defending Germans ½ Losses; inflict +1 Counterattack
    "A33": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY})),

    # A34: Divination
    # Un: Non-German uses German pieces for free March/Battle in 3 Regions
    # Sh: Germans or Belgae free Command; stay Eligible
    "A34": (frozenset({FREE_MARCH, FREE_BATTLE}),
            frozenset({FREE_COMMAND, AFFECTS_ELIGIBILITY})),

    # A35: Nasua & Cimberius
    # Un: Place 1 Ally at Treveri + up to 8 Warbands/4 Auxilia
    # Sh: Place up to 8 Germanic Warbands + 1 Settlement near Germania
    "A35": (frozenset({PLACES_ALLIES, PLACES_WARBANDS, PLACES_AUXILIA}),
            frozenset({PLACES_WARBANDS, PLACES_SETTLEMENTS})),

    # A36: Usipetes & Tencteri
    # Un: Remove 2 Settlements + 8 Warbands from specific Regions
    # Sh: Place 2 Settlements + 4 Warbands; remove 2 Allies near Sugambri
    "A36": (frozenset({REMOVES_SETTLEMENTS, REMOVES_WARBANDS}),
            frozenset({PLACES_SETTLEMENTS, PLACES_WARBANDS, REMOVES_ALLIES})),

    # A37: All Gaul Gathers
    # Un: Place Allies in Celtica near German Control; move pieces there
    # Sh: Remove up to 3 Aedui/Roman Allies from Celtica near German Control
    "A37": (frozenset({PLACES_ALLIES, MOVES_PIECES}),
            frozenset({REMOVES_ALLIES})),

    # A38: Vergobret — Capability
    # Un: Suborn places/removes 1 more per Region; Auxilia at 0 cost
    # Sh: Suborn only at Diviciacus; or within 1 of Bibracte
    "A38": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY})),

    # A40: Alpine Tribes (Ariovistus)
    # Un: Place pieces in each of 3 Regions within 1 of Cisalpina
    # Sh: -5 Roman Resources per Region not Roman Control; Stay Eligible
    "A40": (frozenset({PLACES_WARBANDS, PLACES_AUXILIA, PLACES_ALLIES}),
            frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY})),

    # A43: Dumnorix (Ariovistus)
    # Un: Replace Arverni pieces near Bibracte with Roman/Aedui
    # Sh: Remove Citadels/Allies; Arverni place Ally + Warbands
    "A43": (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS,
                       PLACES_ALLIES, PLACES_AUXILIA}),
            frozenset({REMOVES_CITADELS, REMOVES_ALLIES,
                       PLACES_ALLIES, PLACES_WARBANDS})),

    # A45: Savage Dictates
    # Un: Place up to 3 non-German Allies near Intimidated markers
    # Sh: Germans free Intimidate anywhere
    "A45": (frozenset({PLACES_ALLIES}),
            frozenset({REMOVES_WARBANDS, REMOVES_AUXILIA, REMOVES_ALLIES,
                       PLACES_MARKERS})),

    # A51: Siege of Bibrax
    # Un: Place 4 Auxilia/Warbands + Fort at Remi; remove 6 Belgic Warbands
    # Sh: Remove up to 5 non-Legion Roman/Aedui pieces from Atrebates
    "A51": (frozenset({PLACES_AUXILIA, PLACES_WARBANDS, PLACES_FORTS,
                       REMOVES_WARBANDS}),
            frozenset({REMOVES_AUXILIA, REMOVES_WARBANDS, REMOVES_ALLIES})),

    # A53: Frumentum
    # Un: Aedui specify Resources; Romans spend on Recruit+March+SA
    # Sh: Aedui/Roman Resources -4 each; both Ineligible
    "A53": (frozenset({ADDS_RESOURCES, FREE_COMMAND, FREE_SA}),
            frozenset({REMOVES_RESOURCES, AFFECTS_ELIGIBILITY})),

    # A56: Galba
    # Un: Remove all Belgae except Leader from Atrebates; -4 Resources
    # Sh: Place 4 Warbands + 2 Allies in Belgica; +4 Resources
    "A56": (frozenset({REMOVES_WARBANDS, REMOVES_ALLIES, REMOVES_RESOURCES}),
            frozenset({PLACES_WARBANDS, PLACES_ALLIES, ADDS_RESOURCES})),

    # A57: Sabis — same effect both sides
    # Free Battle in Belgica; no Retreat; optional 2nd Battle
    "A57": (frozenset({FREE_BATTLE}),
            frozenset({FREE_BATTLE})),

    # A58: Aduatuci (Ariovistus)
    # Un: Free Battle in Belgica; free Seize as if Roman Control
    # Sh: Replace Roman pieces with yours in Belgica; free Ambush
    "A58": (frozenset({FREE_BATTLE, FREE_SEIZE}),
            frozenset({REMOVES_ALLIES, REMOVES_AUXILIA,
                       PLACES_ALLIES, PLACES_WARBANDS, FREE_BATTLE})),

    # A60: Iccius & Andecomborius
    # Un: Place Roman Ally at Remi + up to 4 Auxilia; +2 per unplaced
    # Sh: Replace up to 5 Roman pieces with Belgae in Atrebates
    "A60": (frozenset({PLACES_ALLIES, PLACES_AUXILIA, ADDS_RESOURCES}),
            frozenset({REMOVES_AUXILIA, REMOVES_ALLIES,
                       PLACES_ALLIES, PLACES_WARBANDS})),

    # A63: Winter Campaign (Ariovistus) — Capability
    # Un: Quarters costs only in Devastated Regions
    # Sh: After Harvest, do 2 Commands/SAs
    "A63": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY})),

    # A64: Abatis — Capability (but with immediate placement)
    # Place Abatis marker in Region with Warband
    "A64": (frozenset({PLACES_MARKERS, IS_CAPABILITY}),
            frozenset({PLACES_MARKERS, IS_CAPABILITY})),

    # A65: Kinship
    # Un: Belgae without Leader Battle Germans or vice versa
    # Sh: Replace 4 Warbands + 2 Allies of Belgae/Germans with other
    "A65": (frozenset({FREE_BATTLE}),
            frozenset({REMOVES_WARBANDS, REMOVES_ALLIES,
                       PLACES_WARBANDS, PLACES_ALLIES})),

    # A66: Winter Uprising! — Capability
    # Un: Place Uprising marker
    # Sh: (same — single effect, marker + later effects)
    "A66": (frozenset({PLACES_MARKERS, IS_CAPABILITY}),
            frozenset({PLACES_MARKERS, IS_CAPABILITY})),

    # A67: Arduenna (Ariovistus) — same effect both sides
    # Non-Arverni free March into Nervii/Treveri; free Command; flip Hidden
    "A67": (frozenset({FREE_MARCH, FREE_COMMAND}),
            frozenset({FREE_MARCH, FREE_COMMAND})),

    # A69: Bellovaci
    # Un: Remove Belgic pieces at Bellovaci; place Roman/Aedui
    # Sh: Place 6 Belgic Warbands; Ambush 1 Loss each
    "A69": (frozenset({REMOVES_ALLIES, REMOVES_WARBANDS,
                       PLACES_ALLIES, PLACES_WARBANDS, PLACES_AUXILIA}),
            frozenset({PLACES_WARBANDS, FREE_BATTLE})),

    # A70: Nervii — Capability
    # Un: Belgae never Retreat
    # Sh: If Nervii Subdued, place Belgic Ally; Rally +2 Warbands
    "A70": (frozenset({IS_CAPABILITY}),
            frozenset({IS_CAPABILITY, PLACES_ALLIES})),
}


# ---------------------------------------------------------------------------
# Per-card flag tables — 2nd Edition text-change cards (Ariovistus variants)
# These are keyed by (int_card_id, "ariovistus") tuples internally but
# looked up via card_id + scenario.
# ---------------------------------------------------------------------------

_SECOND_EDITION_FLAGS = {
    # Card 11 (Ariovistus): Auxilia-only Battle effect
    11: (frozenset({PLACES_AUXILIA, FREE_BATTLE}),
         frozenset({REMOVES_AUXILIA})),

    # Card 30 (Ariovistus): Shaded uses 4 Warbands not 2
    30: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 39 (Ariovistus): Trade yields Resources regardless of Supply
    39: (frozenset({IS_CAPABILITY}),
         frozenset({IS_CAPABILITY})),

    # Card 44 (Ariovistus): Shaded gives free Command instead of free Raid
    44: (frozenset({REMOVES_WARBANDS, PLACES_AUXILIA, PLACES_WARBANDS,
                    FREE_SCOUT}),
         frozenset({REMOVES_AUXILIA, REMOVES_WARBANDS, PLACES_WARBANDS,
                    FREE_COMMAND})),

    # Card 54 (Ariovistus): Clarified no-Retreat scope
    54: (frozenset({FREE_MARCH, FREE_BATTLE}),
         frozenset({FREE_MARCH, FREE_BATTLE})),
}


# ---------------------------------------------------------------------------
# Public API: get_event_flags
# ---------------------------------------------------------------------------

def get_event_flags(card_id, shaded=False, scenario=None):
    """Return the set of boolean effect flags for a card's event side.

    Args:
        card_id: int for base cards, str "A##" for Ariovistus cards
        shaded: True for shaded text, False for unshaded
        scenario: scenario constant, used to select Ariovistus text-change
                  variants for cards in SECOND_EDITION_CARDS

    Returns:
        frozenset of flag strings describing what the event does.

    Raises:
        KeyError if card_id not found in any flag table.
    """
    idx = 1 if shaded else 0

    # A-prefix cards
    if isinstance(card_id, str) and card_id.startswith("A"):
        if card_id in _ARIOVISTUS_FLAGS:
            return _ARIOVISTUS_FLAGS[card_id][idx]
        raise KeyError(f"No flags for Ariovistus card {card_id!r}")

    # Integer cards: check if Ariovistus text-change applies
    if (scenario is not None and scenario in ARIOVISTUS_SCENARIOS
            and card_id in _SECOND_EDITION_FLAGS):
        return _SECOND_EDITION_FLAGS[card_id][idx]

    # Base game cards
    if card_id in _BASE_FLAGS:
        return _BASE_FLAGS[card_id][idx]

    raise KeyError(f"No flags for card {card_id!r}")


# ---------------------------------------------------------------------------
# Per-card is_effective() checks
# ---------------------------------------------------------------------------
# §8.1.1: An event is "Ineffective" if it would have no effect or would
# merely Reveal own pieces. Adding or removing a Capability IS an effect.
#
# For Capability cards, they are always considered effective per §8.1.1
# ("Adding or removing a Capability is an effect") — the separate
# "Capability in final year" check handles the last-year rejection.

def _has_legions_on_map(state):
    """Check if any Legions exist on the map."""
    for region in ALL_REGIONS:
        if count_pieces(state, region, ROMANS, LEGION) > 0:
            return True
    return False


def _has_fallen_legions(state):
    """Check if any Fallen Legions exist."""
    return state.get("fallen_legions", 0) > 0


def _total_legions_on_track(state):
    """Count total Legions on the Legions track."""
    return _count_on_legions_track(state)


def _faction_has_pieces_on_map(state, faction, piece_type=None):
    """Check if a faction has any pieces on the map."""
    for region in ALL_REGIONS:
        if piece_type:
            if count_pieces(state, region, faction, piece_type) > 0:
                return True
        else:
            if count_pieces(state, region, faction) > 0:
                return True
    return False


def _any_gallic_faction_has_citadel(state):
    """Check if any Gallic faction has a Citadel on the map."""
    for faction in GALLIC_FACTIONS:
        if _faction_has_pieces_on_map(state, faction, CITADEL):
            return True
    return False


def _count_on_map(state, faction, piece_type):
    """Count total pieces of a type on the map for a faction."""
    total = 0
    for region in ALL_REGIONS:
        total += count_pieces(state, region, faction, piece_type)
    return total


def _any_allies_on_map(state, factions=None):
    """Check if any Allied Tribes exist on the map for given factions."""
    if factions is None:
        factions = FACTIONS
    for faction in factions:
        if _faction_has_pieces_on_map(state, faction, ALLY):
            return True
    return False


def _has_subdued_tribes(state):
    """Check if any Subdued tribes exist."""
    for tribe_data in state.get("tribes", {}).values():
        if tribe_data.get("status") == "subdued":
            return True
    return False


def _has_subdued_city_tribes(state):
    """Check if any Subdued tribes at Cities exist."""
    for city, tribe in CITY_TO_TRIBE.items():
        tribe_data = state.get("tribes", {}).get(tribe, {})
        if tribe_data.get("status") == "subdued":
            return True
    return False


def _any_active_capabilities(state):
    """Check if any Capabilities are currently active."""
    caps = state.get("capabilities", {})
    for card_id, sides in caps.items():
        for side, active in sides.items():
            if active:
                return True
    return False


def is_event_effective(state, card_id, shaded=False):
    """Check if an event would have any effect in the current game state.

    Per §8.1.1: An event is "Ineffective" if it would have no effect
    or would merely Reveal own pieces. Adding or removing a Capability
    IS an effect.

    Args:
        state: game state dict
        card_id: int or str card identifier
        shaded: True for shaded text, False for unshaded

    Returns:
        True if the event would have an effect, False if ineffective.
    """
    scenario = state.get("scenario")

    # Capability cards are always effective per §8.1.1
    # ("Adding or removing a Capability is an effect")
    if is_capability_card(card_id, scenario):
        return True

    # Check card-specific effectiveness via the flag table plus state checks
    try:
        flags = get_event_flags(card_id, shaded, scenario)
    except KeyError:
        # Unknown card — assume effective to be safe
        return True

    # If the card has free commands/battles/marches, it's almost always
    # effective (something can be done). The only exception would be if
    # no pieces exist at all, which is extremely rare.
    free_action_flags = {
        FREE_COMMAND, FREE_BATTLE, FREE_MARCH, FREE_RALLY,
        FREE_RAID, FREE_SCOUT, FREE_SEIZE, FREE_SA,
    }
    if flags & free_action_flags:
        return True

    # If the card shifts the Senate, it's always effective
    if SHIFTS_SENATE in flags:
        return True

    # If the card triggers Germans Phase or Arverni Phase, check if
    # relevant faction has pieces
    if TRIGGERS_GERMANS_PHASE in flags:
        if _faction_has_pieces_on_map(state, GERMANS):
            return True
        # Germans Phase with no Germans on map might still do something
        # (Rally places from Available)
        if get_available(state, GERMANS, WARBAND) > 0:
            return True
        if get_available(state, GERMANS, ALLY) > 0:
            return True
        return False

    if TRIGGERS_ARVERNI_PHASE in flags:
        # Arverni Phase (Ariovistus) — check if Arverni have pieces
        if _faction_has_pieces_on_map(state, ARVERNI):
            return True
        if get_available(state, ARVERNI, WARBAND) > 0:
            return True
        return False

    # If the card affects eligibility, it's always effective
    if AFFECTS_ELIGIBILITY in flags:
        return True

    # If the card adds/removes resources, usually effective unless at cap/0
    if ADDS_RESOURCES in flags or REMOVES_RESOURCES in flags:
        return True

    # If the card places markers, generally effective
    if PLACES_MARKERS in flags:
        return True

    # If the card removes markers, check if any relevant markers exist
    if REMOVES_MARKERS in flags:
        # Card 50 (Shifting Loyalties): removes a Capability
        if card_id == 50:
            return _any_active_capabilities(state)
        return True

    # If the card moves pieces, check if pieces exist to move
    if MOVES_PIECES in flags:
        return True

    # Check piece placement flags against Available pools
    if PLACES_LEGIONS in flags:
        # Legions come from track, not Available
        if _total_legions_on_track(state) > 0:
            return True
        if _has_fallen_legions(state):
            return True

    if PLACES_AUXILIA in flags:
        if get_available(state, ROMANS, AUXILIA) > 0:
            return True

    if PLACES_WARBANDS in flags:
        for faction in (ARVERNI, AEDUI, BELGAE, GERMANS):
            if get_available(state, faction, WARBAND) > 0:
                return True

    if PLACES_ALLIES in flags:
        for faction in FACTIONS:
            if get_available(state, faction, ALLY) > 0:
                return True

    if PLACES_CITADELS in flags:
        for faction in GALLIC_FACTIONS:
            if get_available(state, faction, CITADEL) > 0:
                return True

    if PLACES_FORTS in flags:
        if get_available(state, ROMANS, FORT) > 0:
            return True

    if PLACES_SETTLEMENTS in flags:
        if get_available(state, GERMANS, SETTLEMENT) > 0:
            return True

    if PLACES_LEADER in flags:
        return True

    # Check piece removal flags against what's on the map
    if REMOVES_LEGIONS in flags:
        if _has_legions_on_map(state):
            return True

    if REMOVES_AUXILIA in flags:
        if _faction_has_pieces_on_map(state, ROMANS, AUXILIA):
            return True

    if REMOVES_WARBANDS in flags:
        for faction in (ARVERNI, AEDUI, BELGAE, GERMANS):
            if _faction_has_pieces_on_map(state, faction, WARBAND):
                return True

    if REMOVES_ALLIES in flags:
        if _any_allies_on_map(state):
            return True

    if REMOVES_CITADELS in flags:
        if _any_gallic_faction_has_citadel(state):
            return True

    if REMOVES_FORTS in flags:
        if _faction_has_pieces_on_map(state, ROMANS, FORT):
            return True

    if REMOVES_SETTLEMENTS in flags:
        if _faction_has_pieces_on_map(state, GERMANS, SETTLEMENT):
            return True

    if REMOVES_LEADER in flags:
        return True

    # If we got here and no flags matched as effective, the event
    # is ineffective (nothing would happen)
    # But only return False if we actually had flags to check
    if flags:
        return False

    # Empty flag set — shouldn't happen, assume effective
    return True


# ---------------------------------------------------------------------------
# Capability in final year check
# ---------------------------------------------------------------------------

def is_capability_final_year(state, card_id):
    """Check if this is a Capability card and the next Winter is the last.

    Per §8.1.1: Non-players decline Capabilities during the last year.

    Args:
        state: game state dict
        card_id: int or str card identifier

    Returns:
        True if this is a Capability in the final year (should skip),
        False otherwise.
    """
    scenario = state.get("scenario")
    if not is_capability_card(card_id, scenario):
        return False

    # Check if next Winter is the last
    # The deck contains Winter cards; if only 1 remains, this is final year
    deck = state.get("deck", [])
    winter_count = sum(
        1 for cid in deck
        if isinstance(cid, str) and cid.startswith("W")
    )
    return winter_count <= 1


# ---------------------------------------------------------------------------
# Unified evaluation: should_skip_event
# ---------------------------------------------------------------------------

def should_skip_event(state, card_id, faction):
    """Determine if a bot should skip (decline) an event.

    Checks the three criteria from §8.1.1 used by bot flowchart nodes
    R4, V2b, A3, B3b, G3b:
    1. Event is Ineffective (would have no effect)
    2. Capability in final year (next Winter is last)
    3. "No [Faction]" per bot instruction tables

    Args:
        state: game state dict
        card_id: int or str card identifier
        faction: faction constant (ROMANS, ARVERNI, etc.)

    Returns:
        True if the bot should skip the event, False if it should play it.
    """
    scenario = state.get("scenario")

    # Determine which side the faction would use (§8.2.2)
    # Romans and Aedui: unshaded; Arverni, Belgae, Germans: shaded
    shaded = faction in (ARVERNI, BELGAE, GERMANS)

    # Check "No [Faction]" via bot instructions
    try:
        instruction = get_bot_instruction(card_id, faction, scenario)
        if instruction.action == NO_EVENT:
            return True
    except KeyError:
        pass

    # Check Capability in final year
    if is_capability_final_year(state, card_id):
        return True

    # Check if event is ineffective
    if not is_event_effective(state, card_id, shaded):
        return True

    return False


# ---------------------------------------------------------------------------
# Utility: get all flag tables (for testing/inspection)
# ---------------------------------------------------------------------------

def get_base_flag_table():
    """Return the complete base game flag table."""
    return dict(_BASE_FLAGS)


def get_ariovistus_flag_table():
    """Return the complete Ariovistus A-prefix flag table."""
    return dict(_ARIOVISTUS_FLAGS)


def get_second_edition_flag_table():
    """Return the 2nd Edition text-change flag table."""
    return dict(_SECOND_EDITION_FLAGS)
