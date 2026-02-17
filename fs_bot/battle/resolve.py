"""
Battle resolution — Full battle procedure (Steps 1-6).

Implements the complete Battle resolution per §3.2.4, §3.3.4, §3.4.4,
with Ambush (§4.3.3, §4.4.3, §4.5.3) and Besiege (§4.2.3) integration.

The caller provides battle parameters. This module resolves the battle
mechanically. Bot target selection logic is NOT implemented here (Phase 5).

Reference:
  §3.2.4, §3.3.4, §3.4.4 — Battle procedure
  §4.2.3 — Besiege
  §4.3.3 — Arverni Ambush
  §4.4.3 — Aedui Ambush
  §4.5.3 — Belgic Ambush
  A3.2.4, A3.3.4, A3.4.4 — Ariovistus modifications
  battle_procedure_flowchart.txt — Unified flow
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    MOBILE_PIECES, FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Battle constants
    CAESAR_AMBUSH_ROLL_THRESHOLD,
    CAESAR_BELGIC_AMBUSH_ROLL_THRESHOLD,
    DIE_MIN, DIE_MAX,
    # Regions
    PROVINCIA,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    move_piece, flip_piece, remove_piece,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import get_adjacent, is_adjacent
from fs_bot.battle.losses import calculate_losses, resolve_losses


def resolve_battle(state, region, attacking_faction, defending_faction,
                   *, is_ambush=False, besiege_target=None,
                   retreat_declaration=None, retreat_region=None,
                   attack_loss_order=None, defend_loss_order=None,
                   citadel_at_start=None):
    """Resolve a complete Battle in a Region.

    This implements Steps 1-6 of the Battle procedure. Step 1 (target
    selection) is handled by the caller providing attacking/defending
    factions.

    Args:
        state: Game state dict. Modified in place.
        region: Region where battle occurs.
        attacking_faction: Faction initiating battle.
        defending_faction: Faction being attacked.
        is_ambush: True if Ambush accompanies this battle.
        besiege_target: If Besiege accompanies: (piece_type,) to remove
            before losses — one of CITADEL, ALLY, or SETTLEMENT.
            Must be a piece the defender has in the region.
        retreat_declaration: True/False/None.
            True: Defender Retreats.
            False: Defender does not Retreat.
            None: Auto-determine (forced no retreat for Ambush/Germanic).
        retreat_region: Region to retreat to (required if retreating).
        attack_loss_order: Optional loss priority for Attack step.
        defend_loss_order: Optional loss priority for Counterattack step.
        citadel_at_start: If provided, overrides the check for whether
            defender started with a Citadel (for Besiege: defender still
            gets half losses even after Citadel removed — §4.2.3).

    Returns:
        dict with detailed battle results:
            "attack": Attack step results (from resolve_losses).
            "counterattack": Counterattack results (or None).
            "besiege": Besiege results (or None).
            "reveal": True if Reveal step executed.
            "retreat": Retreat results (or None).
            "caesar_roll": (roll, success) if Caesar Defending roll occurred.
            "defender_retreated": True if defender retreated.
    """
    scenario = state["scenario"]

    result = {
        "attack": None,
        "counterattack": None,
        "besiege": None,
        "reveal": False,
        "retreat": None,
        "caesar_roll": None,
        "defender_retreated": False,
    }

    # ── Step 2: Determine Retreat ──
    # Cannot retreat if:
    # - Ambush — §4.3.3: "The Defender may not Retreat"
    # - No mobile pieces — §3.2.4: "has only Allied Tribes (discs)
    #   and/or Citadels"
    # - Gallic Battle adds Forts to immobile list — §3.3.4: "Allied Tribe
    #   (disc), Citadel, or Fort pieces"
    # Base game Germanic attacker: no retreat — §3.2.4: "Germans never Retreat"
    #   and §3.4.4: "Skip Step 2; there will be no Retreat."
    # Ariovistus: Germans CAN retreat and ARE retreated from — A3.2.4
    # Ariovistus: Arverni never Retreat — A3.2.4

    can_retreat = True
    if is_ambush:
        can_retreat = False
    elif (attacking_faction == GERMANS
          and scenario in BASE_SCENARIOS):
        # §3.4.4: Germanic Battle skips Steps 2 and 6
        can_retreat = False
    elif (defending_faction == ARVERNI
          and scenario in ARIOVISTUS_SCENARIOS):
        # A3.2.4: "The Arverni never Retreat"
        can_retreat = False

    # Check if defender has mobile pieces — §3.2.4, §3.3.4
    if can_retreat:
        space = state["spaces"][region]
        d_pieces = space.get("pieces", {}).get(defending_faction, {})
        has_mobile = False
        if d_pieces.get(LEADER) is not None:
            has_mobile = True
        for pt in (LEGION,):
            if d_pieces.get(pt, 0) > 0:
                has_mobile = True
        for pt in FLIPPABLE_PIECES:
            for ps in (HIDDEN, REVEALED, SCOUTED):
                if d_pieces.get(ps, {}).get(pt, 0) > 0:
                    has_mobile = True
        if not has_mobile:
            can_retreat = False

    if retreat_declaration is True and can_retreat:
        defender_retreats = True
    elif retreat_declaration is True and not can_retreat:
        # Caller declared retreat but can't — forced no retreat
        defender_retreats = False
    elif retreat_declaration is False:
        defender_retreats = False
    else:
        # None: auto — default no retreat
        defender_retreats = False

    result["defender_retreated"] = defender_retreats

    # ── Track if defender started with Citadel/Fort ──
    # §4.2.3: "A Defender with a Citadel still suffers only half Losses
    # that Battle, even after the Citadel is removed"
    d_pieces = state["spaces"][region].get("pieces", {}).get(
        defending_faction, {}
    )
    if citadel_at_start is None:
        had_citadel_at_start = d_pieces.get(CITADEL, 0) > 0
    else:
        had_citadel_at_start = citadel_at_start

    had_fort_at_start = d_pieces.get(FORT, 0) > 0
    # Provincia permanent Fort — §1.4.2: never absorbs Losses
    # but it DOES count for halving — it's still "in the Region"
    # The rule says "Defenders who... have a Citadel or Fort" — the Fort
    # just can't absorb individual Losses.

    # ── Besiege (§4.2.3) ──
    # "Before and in addition to any Losses... the (Roman) Attacker may
    # automatically remove (Subdue) a Defending Citadel or Allied Tribe"
    # Ariovistus: also Settlements — A4.2.3
    if besiege_target is not None:
        besiege_piece = besiege_target
        if besiege_piece == SETTLEMENT:
            # A4.2.3: "may remove a Settlement instead of an Ally"
            remove_piece(state, region, defending_faction, SETTLEMENT, 1)
        else:
            remove_piece(state, region, defending_faction, besiege_piece, 1)
        result["besiege"] = {"removed": besiege_piece}

    # ── Step 3: Attack ──
    # Determine if Ambush affects the roll mechanic
    # and if Caesar Defending gets a special roll

    # Caesar Defending check — §3.4.4, §4.3.3
    # When Caesar is Defending, no Citadel/Fort, no Retreat, and Ambush
    # or Germanic attack: Caesar rolls to retain roll ability.
    caesar_defending = (
        get_leader_in_region(state, region, defending_faction) == CAESAR
    )

    # Check current Fort/Citadel AFTER Besiege
    d_pieces_now = state["spaces"][region].get("pieces", {}).get(
        defending_faction, {}
    )
    has_fort_now = d_pieces_now.get(FORT, 0) > 0
    has_citadel_now = d_pieces_now.get(CITADEL, 0) > 0

    # Determine if the defender gets die rolls for hard targets
    # Default: yes (use_rolls = True)
    ambush_auto_remove = False
    caesar_counterattack_allowed = False

    if is_ambush or (attacking_faction == GERMANS
                     and scenario in BASE_SCENARIOS):
        # Ambush or Germanic (base game) attack: auto-remove hard targets
        ambush_auto_remove = True
        # But NOT if defender has Citadel or Fort (they still get half losses
        # and the normal roll mechanic) — Wait, re-read the rules...
        #
        # §3.4.4: "the Defender must remove a piece for each Loss suffered,
        # including Leader, Legion, Citadel, or Fort without first rolling
        # a 1-3."
        # §4.3.3: same text.
        #
        # So Ambush removes the roll ability regardless of Fort/Citadel.
        # Fort/Citadel only halves the total losses, doesn't restore rolls.
        #
        # EXCEPTION: Caesar — §3.4.4, §4.3.3
        if caesar_defending:
            # "Romans Defending in the same Region as Caesar on a die roll
            # of 4, 5, or 6 may absorb Losses by rolling a die and removing
            # Legion, Caesar, or Fort only on 1-3."
            #
            # But only if no Citadel/Fort for the branching path?
            # Re-reading the flowchart:
            # Step_3_Attack_No_Retreat → "Defender has Citadel or Fort?" →
            #   Yes: half losses, rolls still apply (Citadel/Fort path)
            #   No: "Ambush or Germanic Attack?" →
            #     Yes: auto-remove (no rolls)
            #       BUT "Caesar Defending?" → roll 4-6 to retain rolls
            #     No: normal losses with rolls
            #
            # Wait — looking at the flowchart more carefully:
            # The Citadel/Fort check is SEPARATE from the Ambush check.
            # If you have a Citadel or Fort → half losses, LAST priority,
            # and normal roll mechanics.
            # If NO Citadel/Fort → then check Ambush.
            #
            # So: Defender with Citadel/Fort ALWAYS gets rolls, even in Ambush.
            # Defender WITHOUT Citadel/Fort in Ambush → no rolls (unless Caesar).
            #
            # Re-reading §3.3.4: "A Defender taking such Losses when Ambiorix
            # is Attacking must take one for each Belgic Warband, not just ½."
            # Then later: same roll mechanic text as Roman Battle.
            # Then: "If the Faction taking Losses is a Defender who has opted
            # to Retreat..."
            #
            # And §4.3.3 specifically says "The Defender must remove a piece
            # for each Loss suffered, including Leader, Legion, Citadel, or
            # Fort without first rolling a 1-3."
            # EXCEPTION: Caesar on 4-6 retains rolls.
            #
            # But the flowchart has: No Retreat → Citadel/Fort? → Yes →
            # "half Losses, Allies/Forts/Citadels last" (with normal rolls)
            # That path doesn't go through the Ambush check at all.
            #
            # Hmm, but §4.3.3 says "(but may use any Fort or Citadel normally)"
            # This means Ambush + Citadel/Fort → half losses AND normal rolls.
            #
            # So: Fort/Citadel DOES restore rolls during Ambush. The auto-remove
            # only applies when NO Fort/Citadel. Let me fix this logic.
            if not has_fort_now and not has_citadel_now:
                # No Fort/Citadel → Caesar must roll to retain rolls
                # Determine threshold based on attacking faction
                if attacking_faction == BELGAE:
                    threshold = CAESAR_BELGIC_AMBUSH_ROLL_THRESHOLD
                else:
                    threshold = CAESAR_AMBUSH_ROLL_THRESHOLD
                roll = state["rng"].randint(DIE_MIN, DIE_MAX)
                success = roll >= threshold
                result["caesar_roll"] = (roll, success)
                if success:
                    ambush_auto_remove = False
                    caesar_counterattack_allowed = True
            else:
                # Has Fort/Citadel → "(but may use any Fort or Citadel
                # normally)" — §4.3.3. Normal rolls apply.
                ambush_auto_remove = False
        elif has_fort_now or has_citadel_now:
            # Non-Caesar defender with Fort/Citadel during Ambush
            # §4.3.3: "(but may use any Fort or Citadel normally)"
            ambush_auto_remove = False
        # else: no Caesar, no Fort/Citadel → auto-remove stays True

    # Calculate Attack Losses
    # For halving: use the original Fort/Citadel state (before Besiege)
    # — §4.2.3: "even after the Citadel is removed"
    attack_losses = _calculate_attack_losses(
        state, region, attacking_faction, defending_faction,
        is_retreat=defender_retreats,
        had_citadel_at_start=had_citadel_at_start,
        had_fort_at_start=had_fort_at_start,
    )

    # Resolve Attack Losses on Defender
    attack_result = resolve_losses(
        state, region, defending_faction, attack_losses,
        is_retreat=defender_retreats,
        is_ambush=ambush_auto_remove,
        caesar_counterattacks=caesar_counterattack_allowed,
        loss_order=attack_loss_order,
    )
    result["attack"] = attack_result

    # ── Step 4: Counterattack ──
    # Skip if Retreat — §3.2.4: "If the Defender declared a Retreat,
    # skip this step."
    # Skip if Ambush — §4.3.3: "There is no Counterattack"
    # EXCEPT: Caesar rolled successfully — §4.3.3: "except if Caesar
    # rolled a 4-6 above"
    counterattack = False
    if not defender_retreats:
        if is_ambush or (attacking_faction == GERMANS
                         and scenario in BASE_SCENARIOS):
            # No counterattack during Ambush/Germanic base
            if caesar_counterattack_allowed:
                counterattack = True
        else:
            counterattack = True

    if counterattack:
        # Counterattack: surviving Defenders cause Losses to Attackers
        # "Attacker takes normal Losses. Allies, Forts, Citadels last."
        counter_losses = calculate_losses(
            state, region,
            attacking_faction=defending_faction,
            defending_faction=attacking_faction,
            is_counterattack=True,
        )
        counter_result = resolve_losses(
            state, region, attacking_faction, counter_losses,
            is_retreat=False,
            is_ambush=False,
            loss_order=defend_loss_order,
        )
        result["counterattack"] = counter_result

    # ── Step 5: Reveal ──
    # Skip if Retreat — §3.2.4: "If a Retreat, skip this step."
    if not defender_retreats:
        _reveal_survivors(state, region, attacking_faction, defending_faction)
        result["reveal"] = True

    # ── Step 6: Retreat ──
    if defender_retreats:
        retreat_result = _execute_retreat(
            state, region, defending_faction, attacking_faction,
            retreat_region=retreat_region,
        )
        result["retreat"] = retreat_result

    # Refresh control after battle — pieces moved/removed
    refresh_all_control(state)

    return result


def _calculate_attack_losses(state, region, attacking_faction,
                             defending_faction, *, is_retreat,
                             had_citadel_at_start, had_fort_at_start):
    """Calculate Attack step losses, accounting for original Citadel state.

    The halving check uses the original Fort/Citadel state (before Besiege)
    per §4.2.3: "A Defender with a Citadel still suffers only half Losses
    that Battle, even after the Citadel is removed."
    """
    space = state["spaces"][region]
    enemy_pieces = space.get("pieces", {}).get(attacking_faction, {})
    defender_pieces = space.get("pieces", {}).get(defending_faction, {})

    # Count enemy pieces (attacker's forces that cause losses)
    enemy_leader = get_leader_in_region(state, region, attacking_faction)
    enemy_legions = enemy_pieces.get(LEGION, 0)
    enemy_auxilia = _count_all_flippable(enemy_pieces, AUXILIA)
    enemy_warbands = _count_all_flippable(enemy_pieces, WARBAND)

    scenario = state["scenario"]

    # Leader modifiers
    caesar_attacking = (enemy_leader == CAESAR)
    ambiorix_attacking = (enemy_leader == AMBIORIX)
    ariovistus_in_battle = (
        enemy_leader == ARIOVISTUS_LEADER
        and scenario in ARIOVISTUS_SCENARIOS
    )

    # Component A
    if caesar_attacking:
        component_a = enemy_legions * 2
    elif ambiorix_attacking:
        component_a = enemy_warbands * 1
    else:
        component_a = enemy_legions * 1 + enemy_warbands * 0.5

    # Component B
    leader_value = 1 if enemy_leader is not None else 0
    component_b = leader_value + enemy_auxilia * 0.5

    total = component_a + component_b

    # Ariovistus doubling — A3.2.4
    if ariovistus_in_battle:
        if not (had_fort_at_start or had_citadel_at_start):
            total *= 2

    # Halving — use original state
    if is_retreat or had_citadel_at_start or had_fort_at_start:
        total = total / 2

    return int(total)


def _count_all_flippable(faction_pieces, piece_type):
    """Count all instances of a flippable piece type across all states."""
    total = 0
    for ps in (HIDDEN, REVEALED, SCOUTED):
        total += faction_pieces.get(ps, {}).get(piece_type, 0)
    return total


def _reveal_survivors(state, region, attacking_faction, defending_faction):
    """Step 5 Reveal — Flip all surviving Hidden Warbands and Auxilia.

    §3.2.4/§3.3.4: "flip all Hidden Warbands and Auxilia of both the
    Attacker and Defender in the Region that survived to Revealed."
    """
    for faction in (attacking_faction, defending_faction):
        for piece_type in FLIPPABLE_PIECES:
            hidden_count = count_pieces_by_state(
                state, region, faction, piece_type, HIDDEN
            )
            if hidden_count > 0:
                flip_piece(state, region, faction, piece_type,
                           count=hidden_count,
                           from_state=HIDDEN, to_state=REVEALED)
            # Scouted pieces also become Revealed — they're already
            # Revealed with a Scouted marker. The Scouted state becomes
            # just Revealed (marker removed implicitly).
            scouted_count = count_pieces_by_state(
                state, region, faction, piece_type, SCOUTED
            )
            if scouted_count > 0:
                flip_piece(state, region, faction, piece_type,
                           count=scouted_count,
                           from_state=SCOUTED, to_state=REVEALED)


def _execute_retreat(state, region, defending_faction, attacking_faction,
                     *, retreat_region=None):
    """Step 6 Retreat — Move remaining mobile Defenders.

    §3.2.4: "The Defender must either move all its surviving Leader and
    Warbands to that Region or remove them."
    EXCEPTION: "The Defender may opt to have any Retreating Leader and/or
    Hidden Warbands stay put."

    §3.3.4: "Unlike in a Roman Attack, no Retreating Leaders nor Warbands
    may stay."

    A3.3.4 note: "Germanic and Gallic Leaders and Warbands Retreating from
    each other may not stay put; they must reach an adjacent Region under
    friendly Control or be removed."

    Args:
        state: Game state dict.
        region: Battle region.
        defending_faction: Faction retreating.
        attacking_faction: Faction that attacked.
        retreat_region: Adjacent region to retreat to. If None, pieces
            that cannot retreat are removed.

    Returns:
        dict with retreat results.
    """
    scenario = state["scenario"]
    result = {
        "moved": [],
        "removed": [],
        "stayed": [],
    }

    space = state["spaces"][region]
    d_pieces = space.get("pieces", {}).get(defending_faction, {})

    # Determine if the "stay" option is available
    # §3.2.4 (Roman Attack): Leader and Hidden Warbands may stay
    # §3.3.4 (Gallic Attack): NO Leaders or Warbands may stay
    # A3.3.4: Germanic and Gallic retreating from each other: may not stay
    roman_attacking = (attacking_faction == ROMANS)

    # In Ariovistus, Germans retreat like Gauls — A3.2.4
    # "Germans may declare Retreat and do so the same way as Gallic Factions,
    # including the option to stay put with their Leader and Hidden Warbands
    # when facing Romans."
    can_stay = False
    if roman_attacking:
        # Roman Attack: Defender may opt to have Hidden Warbands and/or
        # Leader stay — §3.2.4
        can_stay = True
    # Gallic attack: no staying — §3.3.4
    # Germanic base attack: no retreat at all (shouldn't reach here)

    # Collect mobile pieces to retreat
    mobile_pieces = []

    # Leader
    leader_name = d_pieces.get(LEADER)
    if leader_name is not None:
        mobile_pieces.append((LEADER, None, leader_name))

    # Legions
    legion_count = d_pieces.get(LEGION, 0)
    if legion_count > 0:
        mobile_pieces.append((LEGION, None, legion_count))

    # Auxilia — by state
    for ps in (HIDDEN, REVEALED, SCOUTED):
        aux_count = d_pieces.get(ps, {}).get(AUXILIA, 0)
        if aux_count > 0:
            mobile_pieces.append((AUXILIA, ps, aux_count))

    # Warbands — by state
    for ps in (HIDDEN, REVEALED, SCOUTED):
        wb_count = d_pieces.get(ps, {}).get(WARBAND, 0)
        if wb_count > 0:
            mobile_pieces.append((WARBAND, ps, wb_count))

    # Process retreat
    for piece_type, piece_state, count_or_name in mobile_pieces:
        if piece_type == LEADER:
            # Leader: may stay if Roman attack and can_stay
            if can_stay:
                # Default behavior: Leader stays (for bot, this is a decision)
                result["stayed"].append((LEADER, 1))
                continue
            # Must retreat or be removed
            if retreat_region is not None:
                move_piece(state, region, retreat_region,
                           defending_faction, LEADER)
                result["moved"].append((LEADER, 1))
            else:
                remove_piece(state, region, defending_faction, LEADER)
                result["removed"].append((LEADER, 1))

        elif piece_type == WARBAND:
            if can_stay and piece_state == HIDDEN:
                # Hidden Warbands may stay — §3.2.4
                result["stayed"].append((WARBAND, count_or_name))
                continue
            # Must retreat or be removed
            if retreat_region is not None:
                move_piece(state, region, retreat_region,
                           defending_faction, WARBAND,
                           count=count_or_name, piece_state=piece_state)
                result["moved"].append((WARBAND, count_or_name))
            else:
                remove_piece(state, region, defending_faction, WARBAND,
                             count=count_or_name, piece_state=piece_state)
                result["removed"].append((WARBAND, count_or_name))

        elif piece_type in (LEGION, AUXILIA):
            # Must retreat or be removed (no stay option)
            if retreat_region is not None:
                if piece_type == LEGION:
                    move_piece(state, region, retreat_region,
                               defending_faction, piece_type,
                               count=count_or_name)
                else:
                    move_piece(state, region, retreat_region,
                               defending_faction, piece_type,
                               count=count_or_name,
                               piece_state=piece_state)
                result["moved"].append((piece_type, count_or_name))
            else:
                if piece_type == LEGION:
                    # Legions removed go to Fallen — §1.4.1
                    remove_piece(state, region, defending_faction, piece_type,
                                 count=count_or_name, to_fallen=True)
                else:
                    remove_piece(state, region, defending_faction, piece_type,
                                 count=count_or_name,
                                 piece_state=piece_state)
                result["removed"].append((piece_type, count_or_name))

    # Allied Tribes, Citadels, and Forts stay in the Region — §3.2.4, §3.3.4
    # (no action needed — they're not moved)

    return result
