"""
Battle Losses — Calculation and resolution per §3.2.4, §3.3.4, §3.4.4.

Losses sub-procedure:
  a) Calculate how many Losses.
  b) Owner resolves Losses one by one.

Reference:
  §3.2.4 LOSSES, §3.3.4 LOSSES, §3.4.4 LOSSES,
  §4.2.3 Besiege, §4.3.3 Ambush, §4.5.3 Belgic Ambush,
  A3.2.4, A3.3.4, A3.4.4, A1.4 (Diviciacus, Ariovistus, Settlements)
  battle_procedure_flowchart.txt
"""

import math

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HARD_TARGET_PIECES, FLIPPABLE_PIECES, MOBILE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    LEADER_FACTION,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Regions
    PROVINCIA,
    # Battle constants
    LOSS_ROLL_THRESHOLD,
    DIVICIACUS_LOSS_ROLL_THRESHOLD,
    DIE_SIDES, DIE_MIN, DIE_MAX,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    remove_piece, flip_piece,
)


# ============================================================================
# LOSSES STEP (a) — CALCULATE LOSSES COUNT
# ============================================================================

def calculate_losses(state, region, attacking_faction, defending_faction,
                     *, is_retreat=False, is_counterattack=False):
    """Calculate the number of Losses inflicted.

    Per §3.2.4/§3.3.4/§3.4.4 LOSSES:
      Losses = (A + B), possibly halved, rounded down.

    Where the "enemy" is the faction causing the losses:
      - In Attack step: enemy = attacker's pieces
      - In Counterattack step: enemy = defender's pieces (survivors)

    A:
      - If defending vs Caesar attacking: Legions × 2
      - If defending vs Ambiorix attacking: Warbands × 1
      - If defending vs Ariovistus (A3.2.4): double total losses unless
        defender has Fort or Citadel
      - Otherwise: Legions × 1 or Warbands × ½

    B:
      - Leader × 1 and Auxilia × ½

    Halving: Defender Fort, Citadel, or Retreat → halve the sum.

    After halving, round fractions down.

    Args:
        state: Game state dict.
        region: Region where battle occurs.
        attacking_faction: The faction whose pieces cause losses
            (attacker during Attack, defender during Counterattack).
        defending_faction: The faction taking losses
            (defender during Attack, attacker during Counterattack).
        is_retreat: True if the defender declared Retreat (halves losses).
        is_counterattack: True if this is the Counterattack step.

    Returns:
        Integer number of Losses (rounded down).
    """
    space = state["spaces"][region]
    # "Enemy" = the faction causing losses
    enemy_faction = attacking_faction
    enemy_pieces = space.get("pieces", {}).get(enemy_faction, {})

    # Count enemy pieces causing losses
    enemy_leader = get_leader_in_region(state, region, enemy_faction)
    enemy_legions = enemy_pieces.get(LEGION, 0)
    enemy_auxilia = _count_all_flippable(enemy_pieces, AUXILIA)
    enemy_warbands = _count_all_flippable(enemy_pieces, WARBAND)

    # Determine leader-based modifiers
    # Caesar × 2 Legions only when Caesar is the ATTACKER (not counterattack)
    # — §3.2.4: "A Defender taking such Losses when Caesar is Attacking"
    caesar_attacking = (
        enemy_leader == CAESAR
        and not is_counterattack
    )

    # Ambiorix × 1 Warbands only when Ambiorix is the ATTACKER
    # — §3.3.4: "when Ambiorix (yellow, Belgic Leader) is Attacking"
    ambiorix_attacking = (
        enemy_leader == AMBIORIX
        and not is_counterattack
    )

    # Ariovistus doubles total losses — A3.2.4, A3.4.4
    # "The Ariovistus piece in Battle causes the enemy to take double Losses
    #  unless that enemy is Defending with Fort or Citadel."
    # NOTE per A3.2.4: "An Attacker, even with a Fort or Citadel, fighting
    # Ariovistus would take double Losses in any German counterattack."
    ariovistus_in_battle = (
        enemy_leader == ARIOVISTUS_LEADER
        and state["scenario"] in ARIOVISTUS_SCENARIOS
    )

    # Component A: Legions or Warbands
    if caesar_attacking:
        # §3.2.4: "two per Legion instead of just one per Legion"
        component_a = enemy_legions * 2
    elif ambiorix_attacking:
        # §3.3.4: "one for each Belgic Warband, not just ½"
        component_a = enemy_warbands * 1
    else:
        # Normal: Legions × 1 or Warbands × ½
        component_a = enemy_legions * 1 + enemy_warbands * 0.5

    # Component B: Leader × 1 and Auxilia × ½
    leader_value = 1 if enemy_leader is not None else 0
    component_b = leader_value + enemy_auxilia * 0.5

    total = component_a + component_b

    # Ariovistus doubling — A3.2.4, A3.4.4
    # Doubles total losses unless enemy (faction taking losses) is Defending
    # with Fort or Citadel. But an Attacker always takes double in
    # counterattack even with Fort/Citadel.
    if ariovistus_in_battle:
        defender_pieces = space.get("pieces", {}).get(defending_faction, {})
        has_fort_or_citadel = (
            defender_pieces.get(FORT, 0) > 0
            or defender_pieces.get(CITADEL, 0) > 0
        )
        if is_counterattack:
            # "An Attacker, even with a Fort or Citadel, fighting Ariovistus
            # would take double Losses in any German counterattack."
            total *= 2
        elif not has_fort_or_citadel:
            total *= 2

    # Halving: Defender's Fort, Citadel, or Retreat — §3.2.4, §3.3.4
    # "The above sum is cut in half for Defenders who are either Retreating
    # or have a Citadel or Fort."
    # Only applies during the Attack step (not Counterattack).
    # The Attacker never gets halving during Counterattack.
    if not is_counterattack:
        defender_pieces = space.get("pieces", {}).get(defending_faction, {})
        has_fort = defender_pieces.get(FORT, 0) > 0
        has_citadel = defender_pieces.get(CITADEL, 0) > 0

        # §4.2.3: "A Defender with a Citadel still suffers only half Losses
        # that Battle, even after the Citadel is removed"
        # This is handled by the caller tracking citadel_at_start.

        if is_retreat or has_fort or has_citadel:
            total = total / 2

    # Round down — §3.2.4: "round any fractions down"
    return int(total)


def _count_all_flippable(faction_pieces, piece_type):
    """Count all instances of a flippable piece type across all states."""
    total = 0
    for ps in (HIDDEN, REVEALED, SCOUTED):
        total += faction_pieces.get(ps, {}).get(piece_type, 0)
    return total


# ============================================================================
# LOSSES STEP (b) — RESOLVE LOSSES
# ============================================================================

def resolve_losses(state, region, faction, num_losses, *,
                   is_retreat=False, is_ambush=False,
                   caesar_counterattacks=False,
                   loss_order=None):
    """Resolve Losses for a faction, removing pieces one by one.

    The owner chooses which pieces to lose (for a bot, this will be
    automated by bot flowchart logic; for now we use a default priority).

    Rules for loss resolution:
    - Leader, Legion, Fort, Citadel: Roll 1-3 to remove (die roll).
      EXCEPTION: Ambush → auto-remove (no roll) UNLESS Caesar will
      Counterattack, in which case still roll 1-3. — §4.3.3, §4.5.3
    - Warband, Auxilia, Ally, Settlement: Remove automatically (no roll).
    - Retreat: Allies, Forts, Citadels FIRST. — §3.2.4
    - No Retreat: Allies, Forts, Citadels LAST. — §3.2.4
    - Provincia Fort never absorbs Losses — §1.4.2, §3.2.4
    - Diviciacus: only removed on roll of 1 (not 1-3) — A3.2.4
    - Diviciacus: may not absorb Losses until last possible piece — A3.2.4
    - Germanic Settlements absorb Losses as if Germanic Allies — A3.2.4
    - In base game, Germans remove Scouted→Revealed→Hidden Warbands,
      then Allies from Cities last — §3.4.5
    - In Ariovistus, Arverni remove Scouted→Revealed→Hidden Warbands,
      then Allies from Cities last, then Citadels — A3.2.4

    Args:
        state: Game state dict.
        region: Region where battle occurs.
        faction: Faction taking Losses.
        num_losses: Number of Losses to resolve.
        is_retreat: If True, Allies/Forts/Citadels must go FIRST.
        is_ambush: If True, hard targets auto-removed (no roll).
        caesar_counterattacks: If True (Caesar rolled high enough), hard
            targets still get die rolls even during Ambush.
        loss_order: Optional list of (piece_type, piece_state_or_None) tuples
            specifying the order in which the owner chooses to lose pieces.
            If None, uses default priority ordering.

    Returns:
        dict with battle results:
            "removed": list of (piece_type, count) removed
            "rolls": list of (piece_type, roll_value, removed_bool)
            "losses_taken": int — actual pieces removed
            "losses_absorbed": int — losses absorbed by surviving rolls
    """
    result = {
        "removed": [],
        "rolls": [],
        "losses_taken": 0,
        "losses_absorbed": 0,
    }

    # Use die rolls for hard targets?
    # Normal: yes. Ambush: no (auto-remove). Exception: Caesar counterattacks.
    use_rolls = not is_ambush or caesar_counterattacks

    remaining = num_losses
    while remaining > 0:
        # Build the priority list of pieces to take losses
        piece_order = _build_loss_priority(
            state, region, faction, is_retreat=is_retreat,
            loss_order=loss_order,
        )

        if not piece_order:
            # No more pieces to remove — stop
            break

        # Take the first available piece from the priority list
        piece_type, piece_state = piece_order[0]

        # Determine if this is a hard target that gets a die roll
        is_hard_target = piece_type in HARD_TARGET_PIECES

        # Provincia Fort never absorbs Losses — §1.4.2
        if piece_type == FORT and region == PROVINCIA:
            # Skip this piece — can never be removed in battle
            # This shouldn't normally appear because _build_loss_priority
            # filters it out, but safety check
            break

        # Diviciacus special handling — A3.2.4
        leader_name = None
        is_diviciacus = False
        if piece_type == LEADER:
            leader_name = get_leader_in_region(state, region, faction)
            is_diviciacus = (leader_name == DIVICIACUS)

        if is_hard_target and use_rolls:
            # Roll to remove — §3.2.4
            roll = state["rng"].randint(DIE_MIN, DIE_MAX)

            if is_diviciacus:
                # Diviciacus: removed only on roll of 1 — A3.2.4
                threshold = DIVICIACUS_LOSS_ROLL_THRESHOLD
            else:
                threshold = LOSS_ROLL_THRESHOLD

            if roll <= threshold:
                # Remove the piece
                _remove_battle_piece(state, region, faction,
                                     piece_type, piece_state)
                result["rolls"].append((piece_type, roll, True))
                result["removed"].append((piece_type, 1))
                result["losses_taken"] += 1
            else:
                # Survived — Loss absorbed without removing
                result["rolls"].append((piece_type, roll, False))
                result["losses_absorbed"] += 1
        elif is_hard_target and not use_rolls:
            # Ambush auto-remove (no roll) — §4.3.3
            _remove_battle_piece(state, region, faction,
                                 piece_type, piece_state)
            result["rolls"].append((piece_type, None, True))
            result["removed"].append((piece_type, 1))
            result["losses_taken"] += 1
        else:
            # Soft target: auto-remove — §3.2.4
            _remove_battle_piece(state, region, faction,
                                 piece_type, piece_state)
            result["removed"].append((piece_type, 1))
            result["losses_taken"] += 1

        remaining -= 1

    return result


def _build_loss_priority(state, region, faction, *, is_retreat=False,
                         loss_order=None):
    """Build the ordered list of pieces eligible to take Losses.

    Returns a list of (piece_type, piece_state_or_None) tuples in order
    of loss priority.

    Ordering rules:
    - Retreat: Allies/Forts/Citadels/Settlements FIRST, then others.
    - No Retreat: Others first, Allies/Forts/Citadels/Settlements LAST.
    - Provincia Fort is NEVER eligible — §1.4.2
    - Diviciacus: may not absorb until last possible piece — A3.2.4
    - In base game, Germans: Scouted→Revealed→Hidden Warbands, then
      Allies from Cities last — §3.4.5
    - In Ariovistus, Arverni: Scouted→Revealed→Hidden Warbands, then
      Allies from Cities last, then Citadels — A3.2.4
    """
    if loss_order is not None:
        return loss_order

    scenario = state["scenario"]
    space = state["spaces"][region]
    f_pieces = space.get("pieces", {}).get(faction, {})

    # Build lists of available pieces
    available_pieces = []

    # Check for special German or Arverni loss ordering
    is_german_base = (faction == GERMANS and scenario in BASE_SCENARIOS)
    is_german_ariovistus = (
        faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS
    )
    is_arverni_ariovistus = (
        faction == ARVERNI and scenario in ARIOVISTUS_SCENARIOS
    )

    # --- Collect static pieces (Allies, Forts, Citadels, Settlements) ---
    static_pieces = []

    # Allies
    ally_count = f_pieces.get(ALLY, 0)
    for _ in range(ally_count):
        static_pieces.append((ALLY, None))

    # Settlements — treated as Allies for loss purposes — A3.2.4
    settlement_count = f_pieces.get(SETTLEMENT, 0)
    for _ in range(settlement_count):
        static_pieces.append((SETTLEMENT, None))

    # Forts — but NOT the Provincia permanent Fort
    fort_count = f_pieces.get(FORT, 0)
    if region == PROVINCIA and fort_count > 0:
        # Provincia Fort never absorbs Losses — §1.4.2
        fort_count = max(0, fort_count - 1)
    for _ in range(fort_count):
        static_pieces.append((FORT, None))

    # Citadels
    citadel_count = f_pieces.get(CITADEL, 0)
    for _ in range(citadel_count):
        static_pieces.append((CITADEL, None))

    # --- Collect mobile/other pieces ---
    other_pieces = []

    # Leader
    leader_name = f_pieces.get(LEADER)
    is_diviciacus = (leader_name == DIVICIACUS)
    has_leader = leader_name is not None

    # Special loss ordering for Germans in base game — §3.4.5
    # and Arverni in Ariovistus — A3.2.4
    if is_german_base or is_german_ariovistus or is_arverni_ariovistus:
        # Scouted Warbands first, then Revealed, then Hidden
        scouted_wb = f_pieces.get(SCOUTED, {}).get(WARBAND, 0)
        revealed_wb = f_pieces.get(REVEALED, {}).get(WARBAND, 0)
        hidden_wb = f_pieces.get(HIDDEN, {}).get(WARBAND, 0)
        for _ in range(scouted_wb):
            other_pieces.append((WARBAND, SCOUTED))
        for _ in range(revealed_wb):
            other_pieces.append((WARBAND, REVEALED))
        for _ in range(hidden_wb):
            other_pieces.append((WARBAND, HIDDEN))
    else:
        # Normal ordering for warbands (Hidden first per remove_piece default)
        wb_total = _count_all_flippable(f_pieces, WARBAND)
        for _ in range(wb_total):
            other_pieces.append((WARBAND, None))

    # Auxilia
    aux_total = _count_all_flippable(f_pieces, AUXILIA)
    for _ in range(aux_total):
        other_pieces.append((AUXILIA, None))

    # Legions
    legion_count = f_pieces.get(LEGION, 0)
    for _ in range(legion_count):
        other_pieces.append((LEGION, None))

    # Leader — added last in "other" for normal, or excluded until end
    # for Diviciacus
    if has_leader and not is_diviciacus:
        other_pieces.append((LEADER, None))

    # Build final ordering based on retreat status
    if is_retreat:
        # Retreat: Allies/Forts/Citadels/Settlements FIRST — §3.2.4
        result = static_pieces + other_pieces
    else:
        # No Retreat: Allies/Forts/Citadels/Settlements LAST — §3.2.4
        result = other_pieces + static_pieces

    # Diviciacus: "may not absorb Losses until he is the last possible
    # piece to do so" — A3.2.4
    if has_leader and is_diviciacus:
        result.append((LEADER, None))

    # Filter to only pieces actually present
    result = _filter_to_present(state, region, faction, result)

    return result


def _filter_to_present(state, region, faction, piece_list):
    """Filter a priority list to only pieces actually in the region.

    Tracks how many of each (piece_type, piece_state) we've already
    "claimed" to avoid duplicates.
    """
    space = state["spaces"][region]
    f_pieces = space.get("pieces", {}).get(faction, {})

    # Track remaining counts
    remaining = {}
    # Leader
    if f_pieces.get(LEADER) is not None:
        remaining[(LEADER, None)] = 1
    # Legions
    remaining[(LEGION, None)] = f_pieces.get(LEGION, 0)
    # Forts (minus Provincia permanent)
    fort_count = f_pieces.get(FORT, 0)
    if region == PROVINCIA and fort_count > 0:
        fort_count = max(0, fort_count - 1)
    remaining[(FORT, None)] = fort_count
    # Allies
    remaining[(ALLY, None)] = f_pieces.get(ALLY, 0)
    # Citadels
    remaining[(CITADEL, None)] = f_pieces.get(CITADEL, 0)
    # Settlements
    remaining[(SETTLEMENT, None)] = f_pieces.get(SETTLEMENT, 0)

    # Flippable pieces — specific states
    for pt in FLIPPABLE_PIECES:
        for ps in (HIDDEN, REVEALED, SCOUTED):
            remaining[(pt, ps)] = f_pieces.get(ps, {}).get(pt, 0)
        # Also track the None-state total (for non-specific ordering)
        remaining[(pt, None)] = _count_all_flippable(f_pieces, pt)

    filtered = []
    # Track consumed counts to avoid double-counting
    consumed = {}

    for piece_type, piece_state in piece_list:
        key = (piece_type, piece_state)
        avail = remaining.get(key, 0) - consumed.get(key, 0)
        if avail > 0:
            filtered.append((piece_type, piece_state))
            consumed[key] = consumed.get(key, 0) + 1
            # For flippable pieces with None state, also consume from the
            # None bucket (and vice versa)
            if piece_type in FLIPPABLE_PIECES and piece_state is not None:
                none_key = (piece_type, None)
                consumed[none_key] = consumed.get(none_key, 0) + 1
            elif piece_type in FLIPPABLE_PIECES and piece_state is None:
                # Need to consume from the most available specific state
                # (remove_piece handles this automatically)
                pass

    return filtered


def _remove_battle_piece(state, region, faction, piece_type, piece_state):
    """Remove a single piece as a battle loss.

    Legions go to Fallen (§1.4.1).
    All other pieces go to Available.
    """
    if piece_type == LEGION:
        remove_piece(state, region, faction, LEGION, 1, to_fallen=True)
    elif piece_type in FLIPPABLE_PIECES:
        remove_piece(state, region, faction, piece_type, 1,
                     piece_state=piece_state)
    else:
        remove_piece(state, region, faction, piece_type, 1)
